"""Stage 3b: paint the full texture set (plain python: numpy + Pillow).

Inputs:  output/uvdump/*.json  (UV->3D correspondence per object)
         output/bake/ao_*.png  (Cycles AO bakes)
Outputs: output/textures/*.png (upload-ready)

The painter rasterizes each object's triangles into per-texel 3D position
maps, so every mask is expressed as a 3D predicate in avatar space
(brows, lips, trim bands, wrap stripes...) and lands exactly on the
geometry no matter how the UVs flow.  AO is multiplied into diffuse:
Bakes-on-Mesh carries no normal/spec channel, so form shading must be
baked into the skin itself (standard SL skin practice).
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

OUT = sys.argv[1] if len(sys.argv) > 1 else "output"
TEX = f"{OUT}/textures"
os.makedirs(TEX, exist_ok=True)

SIZE = 1024


# --------------------------------------------------------------------------
# rasterization
# --------------------------------------------------------------------------


def rasterize(dump_path: str, material, size: int = SIZE):
    """Rasterize material triangles -> (coverage, X, Y, Z) maps.
    `material` may be an int slot or a set of slots (shared bake channel)."""
    with open(dump_path) as f:
        data = json.load(f)
    slots = {material} if isinstance(material, int) else set(material)
    cov = np.zeros((size, size), bool)
    pos = np.zeros((size, size, 3), np.float32)
    nrm = np.zeros((size, size, 3), np.float32)

    for tri in data["tris"]:
        if tri["m"] not in slots:
            continue
        uv = np.array(tri["uv"], np.float64)
        co = np.array(tri["co"], np.float64)
        no = np.array(tri["n"], np.float64)
        # UV -> pixel (v flipped: image row 0 = v 1)
        px = uv[:, 0] * (size - 1)
        py = (1.0 - uv[:, 1]) * (size - 1)
        x0, x1 = int(max(0, np.floor(px.min()))), int(min(size - 1, np.ceil(px.max())))
        y0, y1 = int(max(0, np.floor(py.min()))), int(min(size - 1, np.ceil(py.max())))
        if x1 < x0 or y1 < y0:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
        d = (px[1] - px[0]) * (py[2] - py[0]) - (px[2] - px[0]) * (py[1] - py[0])
        if abs(d) < 1e-9:
            continue
        w1 = ((xs - px[0]) * (py[2] - py[0]) - (ys - py[0]) * (px[2] - px[0])) / d
        w2 = ((ys - py[0]) * (px[1] - px[0]) - (xs - px[0]) * (py[1] - py[0])) / d
        w0 = 1.0 - w1 - w2
        inside = (w0 >= -0.001) & (w1 >= -0.001) & (w2 >= -0.001)
        if not inside.any():
            continue
        p = (
            w0[..., None] * co[0][None, None]
            + w1[..., None] * co[1][None, None]
            + w2[..., None] * co[2][None, None]
        )
        nn = (
            w0[..., None] * no[0][None, None]
            + w1[..., None] * no[1][None, None]
            + w2[..., None] * no[2][None, None]
        )
        sub_cov = cov[y0 : y1 + 1, x0 : x1 + 1]
        sub_pos = pos[y0 : y1 + 1, x0 : x1 + 1]
        sub_nrm = nrm[y0 : y1 + 1, x0 : x1 + 1]
        write = inside & ~sub_cov
        sub_pos[write] = p[write]
        sub_nrm[write] = nn[write]
        sub_cov |= inside
    return cov, pos[..., 0], pos[..., 1], pos[..., 2], nrm


def dilate_colors(rgb: np.ndarray, cov: np.ndarray, rounds: int = 12) -> np.ndarray:
    """Bleed island colors outward so mipmaps/JPEG2000 don't pull in bg."""
    out = rgb.copy()
    filled = cov.copy()
    for _ in range(rounds):
        if filled.all():
            break
        grown = filled.copy()
        acc = np.zeros_like(out, np.float32)
        cnt = np.zeros(filled.shape, np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            shifted = np.roll(filled, (dy, dx), (0, 1))
            svals = np.roll(out, (dy, dx), (0, 1))
            take = shifted & ~filled
            acc[take] += svals[take]
            cnt[take] += 1.0
            grown |= shifted
        new = (cnt > 0) & ~filled
        out[new] = acc[new] / cnt[new][..., None]
        filled = grown
    return out


def fbm(size: int, octaves=5, seed=7, persistence=0.55) -> np.ndarray:
    rng = np.random.default_rng(seed)
    out = np.zeros((size, size), np.float32)
    amp, total = 1.0, 0.0
    for o in range(octaves):
        n = 2 ** (o + 2)
        grid = rng.random((n + 1, n + 1)).astype(np.float32)
        img = Image.fromarray((grid * 255).astype(np.uint8)).resize(
            (size, size), Image.BICUBIC
        )
        out += amp * (np.asarray(img, np.float32) / 255.0)
        total += amp
        amp *= persistence
    return out / total


def smooth01(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def load_ao(path: str, size: int = SIZE) -> np.ndarray:
    if not os.path.exists(path):
        return np.ones((size, size), np.float32)
    img = Image.open(path).convert("L").resize((size, size), Image.BILINEAR)
    return np.asarray(img, np.float32) / 255.0


def save(rgb: np.ndarray, name: str, alpha: np.ndarray | None = None) -> None:
    rgb8 = (np.clip(rgb, 0, 1) * 255).astype(np.uint8)
    if alpha is not None:
        a8 = (np.clip(alpha, 0, 1) * 255).astype(np.uint8)
        img = Image.fromarray(np.dstack([rgb8, a8]), "RGBA")
    else:
        img = Image.fromarray(rgb8, "RGB")
    img.save(f"{TEX}/{name}.png")
    print(f"[tex] {name}.png")


def boundary_band(cov: np.ndarray, width: int) -> np.ndarray:
    """Band of texels within `width` px of the island boundary (inside)."""
    img = Image.fromarray((cov * 255).astype(np.uint8))
    eroded = img.filter(ImageFilter.MinFilter(2 * width + 1))
    return cov & ~(np.asarray(eroded, np.uint8) > 127)


# --------------------------------------------------------------------------
# palette
# --------------------------------------------------------------------------

SKIN_BASE = np.array([0.302, 0.345, 0.228])       # gerudo olive-green (dark)
SKIN_SHADOW = np.array([0.184, 0.212, 0.137])
SKIN_WARM = np.array([0.386, 0.376, 0.243])       # sun-warmed highlights
LIP = np.array([0.240, 0.168, 0.138])  # dark olive-plum, keeps saturation
BROW_RED = np.array([0.478, 0.114, 0.055])
HAIR_DARK = np.array([0.26, 0.038, 0.026])
HAIR_MID = np.array([0.50, 0.085, 0.045])
HAIR_HI = np.array([0.66, 0.17, 0.07])
ROBE_BASE = np.array([0.086, 0.116, 0.098])       # deep teal-green
ROBE_WEAVE = np.array([0.128, 0.166, 0.140])
GOLD = np.array([0.788, 0.596, 0.184])
GOLD_DARK = np.array([0.478, 0.333, 0.090])
GEM_RED = np.array([0.62, 0.055, 0.09])
PANTS_BASE = np.array([0.124, 0.138, 0.114])
SASH_BASE = np.array([0.878, 0.773, 0.686])
SASH_SHADE = np.array([0.722, 0.573, 0.502])
LEATHER = np.array([0.357, 0.243, 0.118])
WRAP = np.array([0.663, 0.627, 0.529])


def base_layer(color, size=SIZE, mottle=0.06, seed=3):
    n = fbm(size, seed=seed)
    layer = np.ones((size, size, 3), np.float32) * color
    layer *= (1.0 - mottle) + (2 * mottle) * n[..., None]
    return layer


# --------------------------------------------------------------------------
# skin
# --------------------------------------------------------------------------


def paint_skin():
    dump = f"{OUT}/uvdump/GanondorfBody.json"
    with open(dump) as f:
        mats = json.load(f)["materials"]

    # group slots by bake channel (BAKED_UPPER + BAKED_UPPER2 -> one map)
    channels: dict[str, list[int]] = {}
    for slot, mat in enumerate(mats):
        ch = mat.rstrip("23456789")
        if ch in ("BAKED_HEAD", "BAKED_UPPER", "BAKED_LOWER"):
            channels.setdefault(ch, []).append(slot)

    for ch_i, (mat, slots) in enumerate(channels.items()):
        cov, X, Y, Z, NRM = rasterize(dump, set(slots))
        ao = load_ao(f"{OUT}/bake/ao_GanondorfBody_{mat}.png")
        # deeper AO floor + steeper curve: carve the musculature
        ao = np.clip(ao, 0.16, 1.0) ** 1.15

        # per-channel noise seeds so head/upper/lower get decorrelated
        # mottle and pore fields (ch_i, not the stale grouping-loop slot)
        rgb = base_layer(SKIN_BASE, seed=11 + ch_i, mottle=0.05)
        # vertical warm/cool variation
        warm = smooth01((Z - 0.6) / 1.2)
        rgb = rgb * (1 - 0.25 * (1 - warm[..., None])) + SKIN_WARM * 0.10 * warm[..., None]
        # pores / fine noise
        pores = fbm(SIZE, octaves=7, seed=23 + ch_i, persistence=0.7)
        rgb *= 0.96 + 0.08 * pores[..., None]
        # AO shading
        rgb *= ao[..., None]

        AY = np.abs(Y)
        if mat == "BAKED_HEAD":
            # heavy brows (flame red, Ganondorf signature)
            brow = (
                smooth01(1 - np.abs(Z - 1.7865) / 0.008)
                * smooth01((AY - 0.014) / 0.012) * smooth01((0.062 - AY) / 0.02)
                * smooth01((X - 0.05) / 0.03)
            )
            brow = np.asarray(Image.fromarray((brow * 255).astype(np.uint8)).filter(
                ImageFilter.GaussianBlur(2)), np.float32) / 255.0
            rgb = rgb * (1 - brow[..., None]) + BROW_RED * brow[..., None]

            # eye socket smoky shading: true 3D distance from each eyeball
            # center so the cheeks/temples are untouched
            for sgn in (1, -1):
                d = np.sqrt(
                    (X - 0.090) ** 2 + (Y - sgn * 0.036) ** 2 + (Z - 1.762) ** 2
                )
                sock = smooth01(1 - d / 0.026) * 0.5
                rgb *= 1 - 0.45 * sock[..., None]
            # lips: subtle darker olive, tight to the actual lip band
            lip = (
                smooth01(1 - np.abs(Z - 1.7075) / 0.006)
                * smooth01((0.033 - AY) / 0.015) * smooth01((X - 0.096) / 0.008)
            )
            lip = np.asarray(Image.fromarray((lip * 255).astype(np.uint8)).filter(
                ImageFilter.GaussianBlur(1.5)), np.float32) / 255.0
            rgb = rgb * (1 - 0.38 * lip[..., None]) + LIP * 0.38 * lip[..., None]
            # lip split line
            split = (
                smooth01(1 - np.abs(Z - 1.7078) / 0.0018)
                * (X > 0.098) * (AY < 0.030)
            )
            rgb *= 1 - 0.5 * split[..., None]
            # jaw beard shadow: red-tinted, densest at the sideburn line
            # in front of the ears, thinning toward the chin
            stubble = (
                smooth01((1.70 - Z) / 0.03) * smooth01((Z - 1.628) / 0.012)
                * smooth01((X - 0.015) / 0.03)
            )
            burnline = (
                smooth01((1.76 - Z) / 0.04) * smooth01((Z - 1.63) / 0.03)
                * smooth01((AY - 0.052) / 0.015) * smooth01((X - 0.02) / 0.025)
            )
            beard = np.maximum(stubble * 0.75, burnline)
            stub_noise = fbm(SIZE, octaves=7, seed=91, persistence=0.8)
            bmask = (beard * (0.55 + 0.45 * stub_noise))[..., None]
            rgb = rgb * (1 - 0.45 * bmask) + HAIR_DARK * 0.45 * bmask
            # scalp tint under hair (matches mane so edges vanish); gate by
            # surface normal -- scalp faces point up/back, while the pointed
            # ear tips (which also reach this height) point sideways
            NZ, NX = NRM[..., 2], NRM[..., 0]
            upface = np.maximum(smooth01((NZ - 0.25) / 0.25), smooth01((-NX - 0.55) / 0.25))
            scalp = smooth01((Z - 1.797) / 0.008) * (AY < 0.068) * (X < 0.095) * upface
            rgb = rgb * (1 - 0.85 * scalp[..., None]) + HAIR_DARK * 0.85 * scalp[..., None]
            # mouth interior: keep the bag/teeth zone dark so nothing pale
            # peeks through the lip slit
            interior = (
                smooth01(1 - np.abs(Z - 1.7075) / 0.010)
                * smooth01((0.036 - AY) / 0.012)
                * smooth01((0.0965 - X) / 0.012) * (X > 0.045)
            )
            rgb *= 1 - 0.72 * interior[..., None]
            # forehead warpaint-esque darkening toward hairline
            rgb *= 1 - 0.10 * smooth01((Z - 1.78) / 0.02)[..., None]

        if mat == "BAKED_UPPER":
            # nipples
            for sgn in (1, -1):
                d = np.sqrt((Y - sgn * 0.082) ** 2 + (Z - 1.408) ** 2)
                nip = smooth01(1 - d / 0.011) * (X > 0.05)
                rgb = rgb * (1 - 0.5 * nip[..., None]) + SKIN_SHADOW * 0.5 * nip[..., None]
            # palm lightening (gerudo palms)
            palm = smooth01((AY - 0.70) / 0.05) * smooth01((1.515 - Z) / 0.02)
            rgb = rgb * (1 - 0.25 * palm[..., None]) + SKIN_WARM * 0.25 * palm[..., None]
            # vein/manga muscle accent: reuse AO cavity
            rgb *= 0.94 + 0.06 * smooth01((ao - 0.55) / 0.3)[..., None]

        if mat == "BAKED_LOWER":
            navel_d = np.sqrt(Y**2 + (Z - 1.11) ** 2)
            navel = smooth01(1 - navel_d / 0.011) * (X > 0.08)
            rgb *= 1 - 0.5 * navel[..., None]
            # soles slightly warm
            sole = smooth01((0.03 - Z) / 0.02)
            rgb = rgb * (1 - 0.2 * sole[..., None]) + SKIN_WARM * 0.2 * sole[..., None]

        rgb = dilate_colors(rgb, cov)
        save(rgb, f"skin_{mat.split('_')[1].lower()}")


def paint_eyes():
    size = 512
    yy, xx = np.mgrid[0:size, 0:size]
    u = xx / (size - 1)
    v = 1 - yy / (size - 1)
    # iris centered per classic SL eye UV: front hemisphere maps to full square
    d = np.sqrt((u - 0.5) ** 2 + (v - 0.5) ** 2)
    rgb = np.ones((size, size, 3), np.float32) * np.array([0.93, 0.90, 0.85])
    rng = np.random.default_rng(5)
    theta = np.arctan2(v - 0.5, u - 0.5)
    streaks = 0.5 + 0.5 * np.sin(theta * 23 + fbm(size, seed=17) * 9)
    iris = smooth01((0.30 - d) / 0.02)
    amber = np.array([0.85, 0.55, 0.10]) * (0.7 + 0.5 * streaks[..., None])
    amber *= 1 - 0.6 * smooth01((d[..., None] - 0.18) / 0.12)  # darker rim
    rgb = rgb * (1 - iris[..., None]) + amber * iris[..., None]
    limbal = smooth01(1 - np.abs(d - 0.30) / 0.025)
    rgb *= 1 - 0.75 * limbal[..., None]
    pupil = smooth01((0.105 - d) / 0.02)
    rgb *= 1 - 0.97 * pupil[..., None]
    # sclera shading toward edges
    rgb *= 1 - 0.35 * smooth01((d - 0.38) / 0.2)[..., None]
    save(rgb, "eyes")


def paint_lashes():
    """The classic lash cards UV into a small corner region; everything
    outside their coverage must be fully transparent or the cards render
    as an opaque bar floating in front of the face."""
    size = 512
    cov, X, Y, Z, NRM = rasterize(f"{OUT}/uvdump/GanondorfLashes.json", 0, size=size)
    rgb = np.zeros((size, size, 3), np.float32) + 0.04
    # strand alpha inside the covered region only
    strands = fbm(size, octaves=7, seed=9, persistence=0.8)
    alpha = np.where(cov, 0.25 + 0.75 * smooth01((strands - 0.35) / 0.3), 0.0)
    # fade toward card tips (distance from the eye line)
    alpha *= np.where(cov, smooth01((0.028 - np.abs(Z - 1.760)) / 0.02), 0.0)
    alpha = np.asarray(Image.fromarray((alpha * 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(0.6)), np.float32) / 255.0
    save(rgb, "lashes", alpha=alpha)


# --------------------------------------------------------------------------
# hair
# --------------------------------------------------------------------------


def paint_hair_strands():
    """SL "mesh hair" convention: the geometry (see adornments.strand_card)
    is a plain tapered card -- individual strand definition comes
    entirely from an alpha-cutout texture, never from the mesh itself.
    Atlas layout: 4 tiles of a few parallel strand streaks each (fully
    transparent in the gaps between them, so neighbouring cards don't
    look identical), plus 1 solid opaque tile reserved for the
    HairScalp backing shell.  Alpha uses a sharp (~0.02) cutoff because
    in-world this must use Alpha MASKING, not blending, to avoid the
    classic multi-card sorting-order glitch."""
    size = SIZE
    n_tiles = 5
    tile_w = size // n_tiles
    yy, xx = np.mgrid[0:size, 0:size]
    v = 1.0 - yy / (size - 1)  # 0 root -> 1 tip
    rgb = np.zeros((size, size, 3), np.float32)
    alpha = np.zeros((size, size), np.float32)

    for t in range(n_tiles):
        x0 = t * tile_w
        x1 = (t + 1) * tile_w if t < n_tiles - 1 else size
        w = x1 - x0
        tv = v[:, x0:x1]
        col = HAIR_DARK[None, None] * (1 - tv[..., None]) + HAIR_MID[None, None] * tv[..., None]
        col = col + (HAIR_HI - HAIR_MID)[None, None] * 0.4 * smooth01((tv - 0.6) / 0.3)[..., None]

        if t == n_tiles - 1:
            rgb[:, x0:x1] = col
            alpha[:, x0:x1] = 1.0
            continue

        local_u = (xx[:, x0:x1] - x0) / w
        n_strands = 3 + (t % 2)
        tile_rgb = np.zeros((size, w, 3), np.float32)
        tile_a = np.zeros((size, w), np.float32)
        for s in range(n_strands):
            seed = 101 + t * 13 + s * 7
            center = (s + 0.5) / n_strands
            wiggle = 0.035 * np.sin(tv * (7 + s) + seed * 0.3)
            d = np.abs(local_u - center - wiggle)
            width = 0.055 + 0.015 * ((seed * 53) % 100) / 100.0
            strand_a = smooth01((width - d) / 0.014)
            strand_a = strand_a * smooth01(tv / 0.05) * smooth01((1.0 - tv) / 0.20)
            jitter = 0.82 + 0.32 * ((seed * 37) % 100) / 100.0
            mask = strand_a > tile_a
            tile_rgb[mask] = (col * jitter)[mask]
            tile_a = np.maximum(tile_a, strand_a)
        rgb[:, x0:x1] = tile_rgb
        alpha[:, x0:x1] = tile_a

    save(rgb, "hair", alpha=alpha)

    # gold tie
    save(_metal(256, seed=41), "gold")
    # gem
    size = 256
    yy, xx = np.mgrid[0:size, 0:size]
    d = np.sqrt((xx / size - 0.5) ** 2 + (yy / size - 0.5) ** 2) * 2
    gem = GEM_RED[None, None] * (1.25 - 0.8 * d[..., None])
    gem += np.array([1.0, 0.5, 0.4]) * smooth01((0.18 - d) / 0.1)[..., None] * 0.35
    save(gem, "gem")


def _metal(size, seed=41, base=GOLD, dark=GOLD_DARK):
    brush = fbm(size, octaves=6, seed=seed, persistence=0.8)
    row = fbm(size, octaves=4, seed=seed + 1)[:, 0]
    brushed = 0.65 * brush + 0.35 * row[:, None]
    t = np.clip(brushed, 0, 1)
    return dark[None, None] * (1 - t[..., None]) + base[None, None] * (0.4 + 0.8 * t[..., None])


# --------------------------------------------------------------------------
# garments
# --------------------------------------------------------------------------


def _weave(size, seed, scale=220):
    yy, xx = np.mgrid[0:size, 0:size]
    warp = np.sin(xx / size * scale * np.pi) * 0.5 + 0.5
    weft = np.sin(yy / size * scale * np.pi) * 0.5 + 0.5
    n = fbm(size, octaves=6, seed=seed, persistence=0.65)
    return 0.30 * warp + 0.30 * weft + 0.40 * n


def paint_robe():
    dump = f"{OUT}/uvdump/GanondorfRobe.json"
    with open(dump) as f:
        mats = json.load(f)["materials"]
    for slot, mat in enumerate(mats):
        cov, X, Y, Z, NRM = rasterize(dump, slot)
        if not cov.any():
            continue
        ao = load_ao(f"{OUT}/bake/ao_GanondorfRobe_{mat}.png")
        w = _weave(SIZE, seed=51 + slot)
        rgb = ROBE_BASE[None, None] * (1 - w[..., None] * 0.5) + ROBE_WEAVE[None, None] * w[..., None] * 0.5
        rgb *= np.clip(ao, 0.35, 1)[..., None] ** 0.9

        # gold embroidered trim along every garment border
        band = boundary_band(cov, 9)
        inner = boundary_band(cov, 12) & ~boundary_band(cov, 3)
        gold = _metal(SIZE, seed=57)
        rgb[band] = gold[band] * 0.9
        # embroidery pattern: dotted line inside the trim
        yy, xx = np.mgrid[0:SIZE, 0:SIZE]
        dots = (np.sin(xx * 0.35) * np.sin(yy * 0.35)) > 0.55
        rgb[inner & dots] = GOLD_DARK * 0.8

        # subtle gerudo geometric pattern on the cloth
        patt = ((np.sin(Z * 210) > 0.92) & (np.abs(np.sin(Y * 140)) > 0.55)) & cov
        rgb[patt] = rgb[patt] * 0.6 + GOLD_DARK * 0.4

        rgb = dilate_colors(rgb, cov)
        save(rgb, f"robe_{'upper' if mat == 'RobeUpper' else 'lower'}")


def paint_pants():
    dump = f"{OUT}/uvdump/GanondorfPants.json"
    cov, X, Y, Z, NRM = rasterize(dump, 0)
    ao = load_ao(f"{OUT}/bake/ao_GanondorfPants_Pants.png")
    w = _weave(SIZE, seed=61, scale=260)
    rgb = PANTS_BASE[None, None] * (0.75 + 0.5 * w[..., None])
    rgb *= np.clip(ao, 0.35, 1)[..., None] ** 0.9
    # vertical pleats: modulate by world angle around each leg
    pleat = 0.5 + 0.5 * np.sin(np.arctan2(Y - np.sign(Y) * 0.085, X) * 9)
    rgb *= 0.92 + 0.10 * (pleat * smooth01((Z - 0.25) / 0.1))[..., None]
    # gathered cuffs: bronze band
    cuff = (Z < 0.235) & (Z > 0.14) & cov
    gold = _metal(SIZE, seed=63)
    rgb[cuff] = gold[cuff] * 0.55 + rgb[cuff] * 0.45
    rgb = dilate_colors(rgb, cov)
    save(rgb, "pants")


def paint_sash():
    cov = np.ones((SIZE, SIZE), bool)
    yy, xx = np.mgrid[0:SIZE, 0:SIZE]
    v = 1 - yy / (SIZE - 1)
    silk = fbm(SIZE, octaves=5, seed=71, persistence=0.5)
    sheen = 0.5 + 0.5 * np.sin(v * np.pi * 6 + silk * 2.0)
    rgb = SASH_BASE[None, None] * (1 - 0.35 * sheen[..., None]) + SASH_SHADE[None, None] * 0.35 * sheen[..., None]
    rgb *= 0.94 + 0.09 * silk[..., None]
    # embroidered borders top/bottom
    border = (v < 0.07) | (v > 0.93)
    gold = _metal(SIZE, seed=73)
    rgb[border] = gold[border] * 0.8 + rgb[border] * 0.2
    stripe = np.abs(v - 0.5) < 0.015
    rgb[stripe] = GEM_RED * 0.6 + rgb[stripe] * 0.4
    save(rgb, "sash")


def paint_loincloth():
    dump = f"{OUT}/uvdump/GanondorfLoincloth.json"
    cov, X, Y, Z, NRM = rasterize(dump, 0)
    ao = load_ao(f"{OUT}/bake/ao_GanondorfLoincloth_Loincloth.png")
    n = fbm(SIZE, octaves=6, seed=141, persistence=0.6)
    rgb = LEATHER[None, None] * (0.75 + 0.4 * n[..., None])
    rgb *= np.clip(ao, 0.35, 1)[..., None] ** 0.9
    # gold trim along the waistband hem and flap edges
    band = boundary_band(cov, 10)
    gold = _metal(SIZE, seed=143)
    rgb[band] = gold[band] * 0.85
    # subtle gerudo geometric pattern
    patt = ((np.sin(Z * 200) > 0.9) & (np.abs(np.sin(Y * 130)) > 0.5)) & cov
    rgb[patt] = rgb[patt] * 0.6 + GOLD_DARK * 0.4
    rgb = dilate_colors(rgb, cov)
    save(rgb, "loincloth")


def paint_bracer_and_wraps():
    # bracer (SLUV upper coords)
    dump = f"{OUT}/uvdump/GanondorfBracerLeft.json"
    cov, X, Y, Z, NRM = rasterize(dump, 0)
    n = fbm(SIZE, octaves=6, seed=81, persistence=0.6)
    rgb = LEATHER[None, None] * (0.8 + 0.4 * n[..., None])
    AY = np.abs(Y)
    band = (0.5 + 0.5 * np.sin((AY - 0.42) / 0.18 * np.pi * 4.0)) > 0.72
    gold = _metal(SIZE, seed=83)
    rgb[band & cov] = gold[band & cov]
    rgb *= 0.9 + 0.1 * smooth01((Z - 1.44) / 0.1)[..., None]
    rgb = dilate_colors(rgb, cov)
    save(rgb, "bracer")

    # leg wraps (SLUV lower coords)
    dump = f"{OUT}/uvdump/GanondorfAnkletLeft.json"
    cov, X, Y, Z, NRM = rasterize(dump, 0)
    linen = fbm(SIZE, octaves=6, seed=85, persistence=0.6)
    rgb = WRAP[None, None] * (0.8 + 0.35 * linen[..., None])
    # diagonal wrap stripes
    stripes = 0.5 + 0.5 * np.sin(Z * 110 + np.arctan2(Y - np.sign(Y) * 0.08, X) * 3)
    rgb *= 0.85 + 0.18 * stripes[..., None]
    ankle_band = (Z > 0.150) & (Z < 0.185) & cov
    gold = _metal(SIZE, seed=87)
    rgb[ankle_band] = gold[ankle_band]
    rgb = dilate_colors(rgb, cov)
    save(rgb, "legwrap")


def paint_sword():
    save(_metal(256, seed=91), "sword_gold")
    n = fbm(256, octaves=6, seed=93, persistence=0.65)
    rgb = np.array([0.13, 0.10, 0.085])[None, None] * (0.75 + 0.5 * n[..., None])
    yy = np.mgrid[0:256, 0:256][0] / 255.0
    band = (yy > 0.9) | (yy < 0.06)
    gold = _metal(256, seed=95)
    rgb[band] = gold[band]
    save(rgb, "sheath")


def normal_from_height(h: np.ndarray, strength=2.0) -> np.ndarray:
    gy, gx = np.gradient(h.astype(np.float32))
    nx = -gx * strength
    ny = gy * strength
    nz = np.ones_like(h)
    l = np.sqrt(nx**2 + ny**2 + nz**2)
    n = np.dstack([nx / l, ny / l, nz / l])
    return n * 0.5 + 0.5


def paint_normals():
    n = fbm(SIZE, octaves=6, seed=141, persistence=0.6)
    save(normal_from_height(n, 1.5), "loincloth_normal")


if __name__ == "__main__":
    paint_skin()
    paint_eyes()
    paint_lashes()
    paint_hair_strands()
    paint_loincloth()
    paint_bracer_and_wraps()
    paint_sword()
    paint_normals()
    print("[tex] all done")
