"""Stage 5: validate every exported DAE against Second Life's upload rules.

Checks (sources: SL wiki Limits / Mesh Technical Overview, viewer source
lldaeloader.cpp / llmodel.h / lljoint.h):
  - Collada 1.4.x, Z_UP, meter units
  - names ASCII, no forbidden characters
  - <= 8 materials per mesh, <= 21844 tris per material, < 65535 verts
  - <= 110 joints per mesh, all joint names in the official skeleton
  - <= 4 significant weights per vertex, weights normalized
  - inverse bind matrices consistent with the official skeleton rest pose
    (translation-only, matching accumulated `pos` within tolerance)
  - LOD files: node names must be <base>_LODn, material sets must match
    the high LOD's

Run: python3 pipeline/validate_dae.py output assets/sl_resources
"""

from __future__ import annotations

import os
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from slkit.skeleton import load_skeleton  # noqa: E402

NS = {"c": "http://www.collada.org/2005/11/COLLADASchema"}

MAX_MATERIALS = 8
MAX_TRIS_PER_MAT = 21844
MAX_VERTS = 65534
MAX_JOINTS = 110
MAX_WEIGHTS = 4

errors: list[str] = []
warnings: list[str] = []


def err(f, msg):
    errors.append(f"{os.path.basename(f)}: {msg}")


def warn(f, msg):
    warnings.append(f"{os.path.basename(f)}: {msg}")


def floats(text):
    return [float(x) for x in text.split()]


def validate(path: str, sk, expect_materials: dict[str, list[str]]):
    tree = ET.parse(path)
    root = tree.getroot()
    fname = os.path.basename(path)
    base = re.sub(r"(_LOD\d|_PHYS)?\.dae$", "", fname)
    is_lod = bool(re.search(r"_LOD\d\.dae$", fname))

    if not root.tag.endswith("COLLADA"):
        err(path, "not a COLLADA document")
        return
    version = root.get("version", "")
    if not version.startswith("1.4"):
        err(path, f"collada version {version}, SL needs 1.4.x")

    up = root.find("./c:asset/c:up_axis", NS)
    if up is not None and up.text != "Z_UP":
        err(path, f"up_axis {up.text}, expected Z_UP")
    unit = root.find("./c:asset/c:unit", NS)
    if unit is not None and abs(float(unit.get("meter", "1")) - 1.0) > 1e-9:
        err(path, f"unit meter={unit.get('meter')}, expected 1")

    valid_joints = set(sk.order)

    # geometries
    geoms = root.findall(".//c:library_geometries/c:geometry", NS)
    for g in geoms:
        gname = g.get("name") or g.get("id")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", gname or ""):
            err(path, f"geometry name not ASCII-safe: {gname!r}")
        mesh = g.find("c:mesh", NS)
        if mesh is None:
            continue
        pos_src = mesh.find(".//c:vertices/c:input[@semantic='POSITION']", NS)
        n_verts = 0
        if pos_src is not None:
            src_id = pos_src.get("source", "").lstrip("#")
            arr = mesh.find(f".//c:source[@id='{src_id}']/c:float_array", NS)
            if arr is not None:
                n_verts = int(arr.get("count", "0")) // 3
        if n_verts > MAX_VERTS:
            err(path, f"{gname}: {n_verts} verts > {MAX_VERTS}")

        tris_blocks = mesh.findall("c:triangles", NS)
        polylists = mesh.findall("c:polylist", NS)
        if polylists:
            err(path, f"{gname}: polylist present (not triangulated)")
        mats = []
        for t in tris_blocks:
            mats.append(t.get("material", ""))
            count = int(t.get("count", "0"))
            if count > MAX_TRIS_PER_MAT:
                err(path, f"{gname}: {count} tris in one material > {MAX_TRIS_PER_MAT}")
        if len(mats) > MAX_MATERIALS:
            err(path, f"{gname}: {len(mats)} materials > {MAX_MATERIALS}")

        node_base = re.sub(r"_LOD\d$", "", (gname or ""))
        expect_materials.setdefault(node_base, [])
        if not is_lod:
            expect_materials[node_base] = mats
        else:
            high = expect_materials.get(node_base)
            if high is not None and high and set(mats) - set(high):
                err(path, f"{gname}: LOD materials {mats} not subset of high {high}")

    # LOD node naming
    if is_lod:
        suffix = re.search(r"(_LOD\d)\.dae$", fname).group(1)
        nodes = root.findall(".//c:library_visual_scenes//c:node", NS)
        geom_nodes = [n for n in nodes if n.find("c:instance_geometry", NS) is not None
                      or n.find("c:instance_controller", NS) is not None]
        for n in geom_nodes:
            if not (n.get("name") or "").endswith(suffix):
                err(path, f"LOD node '{n.get('name')}' lacks suffix {suffix}")

    # controllers (rigging)
    for ctrl in root.findall(".//c:library_controllers/c:controller", NS):
        skin = ctrl.find("c:skin", NS)
        if skin is None:
            continue
        bsm = skin.find("c:bind_shape_matrix", NS)
        if bsm is not None:
            m = floats(bsm.text)
            ident = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
            if any(abs(a - b) > 1e-4 for a, b in zip(m, ident)):
                warn(path, "bind_shape_matrix is not identity")

        joint_names = []
        inv_binds = []
        for src in skin.findall("c:source", NS):
            name_arr = src.find("c:Name_array", NS)
            if name_arr is not None and name_arr.text:
                joint_names = name_arr.text.split()
            fa = src.find("c:float_array", NS)
            tech = src.find(".//c:param[@name='TRANSFORM']", NS)
            if fa is not None and tech is not None:
                vals = floats(fa.text)
                inv_binds = [vals[i : i + 16] for i in range(0, len(vals), 16)]

        if len(joint_names) > MAX_JOINTS:
            err(path, f"{len(joint_names)} joints > {MAX_JOINTS}")
        unknown = [j for j in joint_names if j not in valid_joints]
        if unknown:
            err(path, f"unknown joints: {unknown[:5]}")

        # inverse bind matrices: expect pure translation = -world_pos
        # (volumes carry their rest rotation)
        for jn, m in zip(joint_names, inv_binds):
            wx, wy, wz = sk.world_pos(jn)
            tx, ty, tz = m[3], m[7], m[11]
            j = sk.joints[jn]
            if not j.is_volume:
                if (abs(tx + wx) > 2e-3 or abs(ty + wy) > 2e-3 or abs(tz + wz) > 2e-3):
                    err(
                        path,
                        f"inv bind of {jn} translation ({tx:.4f},{ty:.4f},{tz:.4f}) "
                        f"!= -rest pos ({-wx:.4f},{-wy:.4f},{-wz:.4f})",
                    )
                rot = [m[0], m[1], m[2], m[4], m[5], m[6], m[8], m[9], m[10]]
                ident3 = [1, 0, 0, 0, 1, 0, 0, 0, 1]
                if any(abs(a - b) > 1e-3 for a, b in zip(rot, ident3)):
                    err(path, f"inv bind of {jn} has rotation (should be identity)")

        # weights: <=4 per vertex, normalized
        vw = skin.find("c:vertex_weights", NS)
        if vw is not None:
            vcount = [int(x) for x in vw.find("c:vcount", NS).text.split()]
            v = [int(x) for x in vw.find("c:v", NS).text.split()]
            weight_src = None
            for inp in vw.findall("c:input", NS):
                if inp.get("semantic") == "WEIGHT":
                    sid = inp.get("source", "").lstrip("#")
                    fa = skin.find(f"c:source[@id='{sid}']/c:float_array", NS)
                    weight_src = floats(fa.text)
            over = 0
            unnorm = 0
            idx = 0
            for c in vcount:
                ws = []
                for k in range(c):
                    ji, wi = v[idx], v[idx + 1]
                    idx += 2
                    ws.append(weight_src[wi])
                sig = [w for w in ws if w > 0.001]
                if len(sig) > MAX_WEIGHTS:
                    over += 1
                if abs(sum(ws) - 1.0) > 0.01:
                    unnorm += 1
            if over:
                err(path, f"{over} vertices with >{MAX_WEIGHTS} significant weights")
            if unnorm:
                warn(path, f"{unnorm} vertices with non-normalized weights")


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "output"
    res = sys.argv[2] if len(sys.argv) > 2 else "assets/sl_resources"
    sk = load_skeleton(f"{res}/avatar_skeleton.xml")

    dae_dir = f"{out}/dae"
    files = sorted(os.listdir(dae_dir))
    # validate high-LOD files first so LOD material subsets can be checked
    files.sort(key=lambda f: ("_LOD" in f, f))
    expect: dict[str, list[str]] = {}
    for f in files:
        if f.endswith(".dae"):
            validate(os.path.join(dae_dir, f), sk, expect)

    print(f"validated {sum(1 for f in files if f.endswith('.dae'))} files")
    for w in warnings:
        print(f"  WARN  {w}")
    for e in errors:
        print(f"  ERROR {e}")
    if errors:
        sys.exit(1)
    print("ALL CHECKS PASSED")


main()
