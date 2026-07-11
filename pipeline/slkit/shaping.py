"""Ganondorf physique: morph recipe + procedural sculpt adjustments.

The morph values below drive the official appearance-slider shape keys
extracted from the .llm meshes.  On top of the morph space we apply a few
procedural deformation fields for the parts sliders cannot reach
(Gerudo-scale shoulder breadth, forearms, trapezius, brow mass).

The body is kept on the STANDARD skeleton (no joint offsets) so every
shape slider keeps working in-world; height comes from the Height slider
(recipe in docs/UPLOAD_GUIDE.md).
"""

from __future__ import annotations

import math

from mathutils import Vector

# --- morph recipe -----------------------------------------------------------

HEAD_MORPHS = {
    "Male_Head": 1.0,
    "Square_Head": 0.45,
    "Square_Jaw": 0.55,
    "Jaw_Angle": 0.4,
    "Deep_Chin": 0.3,
    "Cleft_Chin": 0.3,
    "Jaw_Jut": 0.35,
    "Weak_Chin": -0.2,
    "Big_Brow": 0.9,
    "Lower_Eyebrows": 0.8,
    "Pointy_Eyebrows": 0.4,
    "Nose_Big_Out": 0.55,
    "Broad_Nostrils": 0.4,
    "Noble_Nose_Bridge": 0.7,
    "Wide_Nose_Bridge": 0.45,
    "Low_Septum_Nose": 0.0,
    "High_Cheek_Bones": 0.55,
    "Sunken_Cheeks": 0.35,
    "Pointy_Ears": 1.0,
    "Ears_Out": 0.25,
    "Big_Ears": 0.35,
    "Wide_Lips": 0.18,
    "Lips_Thin": 0.12,
    "Mouth_Height": 0.0,
    "Baggy_Eyes": 0.3,
    "Upper_Eyelid_Fold": 0.4,
    "Eye_Spread": 0.2,
    "Old": 0.15,
    "Egg_Head": -0.3,
    "Forehead_Slant": 0.45,
}

UPPER_MORPHS = {
    "Male_Torso": 1.0,
    "Muscular_Torso": 1.0,
    "Big_Chest": 0.35,
    "Hands_Relaxed": 0.55,
    "Love_Handles": -0.2,
    "Fat_Torso": 0.1,
}

LOWER_MORPHS = {
    "Male_Legs": 1.0,
    "Muscular_Legs": 1.0,
    "Big_Butt_Legs": 0.2,
    "Foot_Size": 0.5,
    "Low_Crotch": 0.1,
}


# --- procedural sculpt fields ------------------------------------------------


def _s(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _gauss(d: float, r: float) -> float:
    return math.exp(-(d * d) / (2.0 * r * r))


def sculpt_body(obj) -> None:
    """Gerudo-scale silhouette: broad shoulders/traps, thick neck and
    forearms, V-taper.  Operates in avatar space (X fwd, Y left, Z up)."""
    for v in obj.data.vertices:
        co = v.co
        x, y, z = co.x, co.y, co.z
        ay = abs(y)

        # shoulder / deltoid breadth: push outward around z~1.45-1.58, |y|>0.12
        if 1.36 < z < 1.62 and ay > 0.10:
            f = _s((z - 1.36) / 0.10) * _s((1.62 - z) / 0.10) * _s((ay - 0.10) / 0.08)
            co.y += math.copysign(0.018 * f, y)
            co.z += 0.006 * f

        # trapezius mass: neck-shoulder slope fill
        if 1.50 < z < 1.62 and 0.03 < ay < 0.16 and x < 0.06:
            f = _s((z - 1.50) / 0.06) * _s((1.62 - z) / 0.07) * _s((ay - 0.03) / 0.06) * _s((0.16 - ay) / 0.06)
            co.z += 0.014 * f
            co.x -= 0.004 * f

        # thick neck
        if 1.57 < z < 1.68:
            f = _s((z - 1.57) / 0.05) * _s((1.68 - z) / 0.05)
            r = math.hypot(x + 0.01, y)
            if r < 0.09:
                co.x += (x + 0.01) / max(r, 1e-5) * 0.010 * f
                co.y += y / max(r, 1e-5) * 0.010 * f

        # forearm girth (arms along +-Y in T-pose): y in elbow..wrist band
        if 0.38 < ay < 0.62 and 1.42 < z < 1.60:
            t = _s((ay - 0.38) / 0.08) * _s((0.62 - ay) / 0.12)
            co.z += (0.007 * t) if z > 1.51 else (-0.007 * t)
            co.x += math.copysign(0.006 * t, x - (-0.036))

        # lat / back V-taper: widen upper back, slim waist sides
        if 1.20 < z < 1.42 and ay > 0.10 and x < 0.03:
            f = _s((z - 1.20) / 0.10) * _s((1.42 - z) / 0.08) * _s((ay - 0.10) / 0.05)
            co.y += math.copysign(0.010 * f, y)
        if 1.02 < z < 1.18 and ay > 0.09:
            f = _s((z - 1.02) / 0.06) * _s((1.18 - z) / 0.06) * _s((ay - 0.09) / 0.05)
            co.y -= math.copysign(0.006 * f, y)

        # bigger hands
        if ay > 0.66:
            f = _s((ay - 0.66) / 0.04)
            co.y += math.copysign(0.008 * f, y)
    obj.data.update()


def sculpt_head(obj) -> None:
    """Ganondorf facial mass: heavy brow ridge, tall forehead, wide jaw."""
    for v in obj.data.vertices:
        co = v.co
        x, y, z = co.x, co.y, co.z
        ay = abs(y)

        # brow ridge forward
        d = math.sqrt((x - 0.09) ** 2 + (z - 1.77) ** 2)
        if d < 0.045 and ay < 0.05:
            co.x += 0.006 * _gauss(d, 0.02) * _s(1.0 - ay / 0.05)

        # jaw width
        if 1.66 < z < 1.73 and ay > 0.03 and x > -0.02:
            f = _s((1.73 - z) / 0.05) * _s((ay - 0.03) / 0.03)
            co.y += math.copysign(0.0035 * f, y)

        # taller cranium
        if z > 1.80:
            co.z += 0.008 * _s((z - 1.80) / 0.06)

        # philtrum tuck: the big-nose morphs leave a flat forward shelf
        # under the septum -- pull it back toward the lip plane
        if 1.708 < z < 1.736 and ay < 0.038 and x > 0.126:
            f = _s(1.0 - abs(z - 1.722) / 0.014) * _s(1.0 - ay / 0.038)
            co.x -= (x - 0.126) * 0.75 * f
    obj.data.update()
