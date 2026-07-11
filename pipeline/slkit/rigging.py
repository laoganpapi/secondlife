"""Rigging tools: fitted-mesh volume weights, Bento fingers/face, cleanup.

Fitted mesh background (wiki.secondlife.com/wiki/Mesh/Rigging_Fitted_Mesh,
Avastar docs): every classic mBone pairs with a collision-volume bone.
Appearance sliders move/scale the volume bones only, so the fraction of a
vertex's weight carried by the volume bone determines how much the body
responds to sliders; the mBone+volume pair together drive animation.  Top
bodies redistribute (never add) weight between the pair, with extra volume
share in fleshy regions (belly/butt/pecs/handles) that also get avatar
physics.
"""

from __future__ import annotations

import math

import bpy
from mathutils import Vector

# mBone -> primary paired collision volume
VOLUME_PAIR = {
    "mPelvis": "PELVIS",
    "mTorso": "BELLY",
    "mChest": "CHEST",
    "mNeck": "NECK",
    "mHead": "HEAD",
    "mCollarLeft": "L_CLAVICLE",
    "mCollarRight": "R_CLAVICLE",
    "mShoulderLeft": "L_UPPER_ARM",
    "mShoulderRight": "R_UPPER_ARM",
    "mElbowLeft": "L_LOWER_ARM",
    "mElbowRight": "R_LOWER_ARM",
    "mWristLeft": "L_HAND",
    "mWristRight": "R_HAND",
    "mHipLeft": "L_UPPER_LEG",
    "mHipRight": "R_UPPER_LEG",
    "mKneeLeft": "L_LOWER_LEG",
    "mKneeRight": "R_LOWER_LEG",
    "mAnkleLeft": "L_FOOT",
    "mAnkleRight": "R_FOOT",
}

# Fraction of each mBone weight moved to its paired volume (uniform base).
BASE_VOLUME_SHARE = 0.5

FINGERS = ("Thumb", "Index", "Middle", "Ring", "Pinky")


def get_weight_map(obj) -> list[dict[str, float]]:
    names = [g.name for g in obj.vertex_groups]
    out = []
    for v in obj.data.vertices:
        d = {}
        for ge in v.groups:
            if ge.weight > 1e-6:
                d[names[ge.group]] = ge.weight
        out.append(d)
    return out


def set_weight_map(obj, wmap: list[dict[str, float]]) -> None:
    for g in list(obj.vertex_groups):
        obj.vertex_groups.remove(g)
    groups: dict[str, object] = {}
    per_group: dict[str, list[tuple[int, float]]] = {}
    for vi, d in enumerate(wmap):
        for name, w in d.items():
            per_group.setdefault(name, []).append((vi, w))
    for name, pairs in per_group.items():
        vg = obj.vertex_groups.new(name=name)
        groups[name] = vg
        for vi, w in pairs:
            vg.add([vi], w, "REPLACE")


def _smooth01(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def apply_fitted_volumes(obj, sk) -> None:
    """Split mBone weights with paired collision volumes + fleshy-zone boost."""
    wmap = get_weight_map(obj)
    verts = obj.data.vertices

    # Fleshy zone boosts: (volume, mbone_source, predicate(co) -> 0..1 extra share)
    def belly(co):
        # front lower torso
        f = _smooth01((co.x - 0.02) / 0.08) * _smooth01(1.0 - abs(co.z - 1.12) / 0.14)
        return 0.35 * f * _smooth01(1.0 - abs(co.y) / 0.13)

    def butt(co):
        f = _smooth01((-co.x - 0.02) / 0.09) * _smooth01(1.0 - abs(co.z - 0.97) / 0.13)
        return 0.4 * f

    def pec(co, side):
        f = (
            _smooth01((co.x - 0.04) / 0.07)
            * _smooth01(1.0 - abs(co.z - 1.42) / 0.09)
            * _smooth01(1.0 - abs(co.y - side * 0.075) / 0.07)
        )
        return 0.4 * f

    def handle(co, side):
        f = _smooth01((abs(co.y) - 0.10) / 0.05) * _smooth01(
            1.0 - abs(co.z - 1.08) / 0.12
        )
        return 0.3 * f if co.y * side > 0 else 0.0

    for vi, d in enumerate(wmap):
        co = verts[vi].co
        new = {}
        for name, w in d.items():
            vol = VOLUME_PAIR.get(name)
            if vol is None:
                new[name] = new.get(name, 0.0) + w
                continue
            share = BASE_VOLUME_SHARE
            new[name] = new.get(name, 0.0) + w * (1.0 - share)
            new[vol] = new.get(vol, 0.0) + w * share
            # zone boosts redistribute from the mBone remainder
            extra = 0.0
            if name == "mTorso":
                extra = max(belly(co), handle(co, 1), handle(co, -1))
            elif name == "mPelvis":
                extra = butt(co)
            elif name == "mChest":
                extra = max(pec(co, 1), pec(co, -1))
            if extra > 0.0:
                zone_vol = vol
                if name == "mTorso" and abs(co.y) > 0.10:
                    zone_vol = "LEFT_HANDLE" if co.y > 0 else "RIGHT_HANDLE"
                elif name == "mPelvis":
                    zone_vol = "BUTT"
                elif name == "mChest" and co.x > 0.04:
                    zone_vol = "LEFT_PEC" if co.y > 0 else "RIGHT_PEC"
                moved = min(new[name], w * extra)
                new[name] -= moved
                new[zone_vol] = new.get(zone_vol, 0.0) + moved
        wmap[vi] = new

    set_weight_map(obj, wmap)


def _closest_param_on_segment(p: Vector, a: Vector, b: Vector) -> tuple[float, float]:
    ab = b - a
    denom = ab.length_squared
    if denom < 1e-12:
        return 0.0, (p - a).length
    t = max(0.0, min(1.0, (p - a).dot(ab) / denom))
    return t, (p - (a + ab * t)).length


def apply_bento_fingers(obj, sk, side: str) -> None:
    """Re-rig hand geometry from mWrist to Bento finger bone chains.

    side: 'Left' or 'Right'.  Palm keeps mWrist; finger tubes are assigned
    to the nearest finger chain with smooth blending along the chain.
    """
    wrist = f"mWrist{side}"
    wrist_pos = Vector(sk.world_pivot(wrist))
    sgn = 1.0 if side == "Left" else -1.0

    chains = {}
    for f in FINGERS:
        joints = [f"mHand{f}{i}{side}" for i in (1, 2, 3)]
        pts = [Vector(sk.world_pivot(j)) for j in joints]
        # chain end = last pivot + bone 'end' offset
        endoff = Vector(sk.joints[joints[-1]].end)
        pts.append(pts[-1] + endoff)
        chains[f] = (joints, pts)

    wmap = get_weight_map(obj)
    verts = obj.data.vertices

    # base of the fingers: min |y| of all finger-1 pivots
    base_y = min(abs(pts[0].y) for _, pts in chains.values())

    for vi, d in enumerate(wmap):
        if wrist not in d:
            continue
        co = verts[vi].co
        if co.y * sgn < base_y - 0.012:
            continue  # palm / wrist area stays on mWrist
        # find nearest chain segment
        best = None
        for f, (joints, pts) in chains.items():
            for si in range(3):
                t, dist = _closest_param_on_segment(co, pts[si], pts[si + 1])
                if best is None or dist < best[0]:
                    best = (dist, f, si, t)
        dist, f, si, t = best
        if dist > 0.05:
            continue
        joints, pts = chains[f]
        seg_len = (pts[si + 1] - pts[si]).length or 1e-6
        blend_r = 0.35  # blend zone near segment ends (as fraction)
        w_hand = d.pop(wrist)
        # keep a little wrist weight at the finger base for smooth knuckles
        root_keep = 0.25 if (si == 0 and t < 0.5) else 0.0
        wf = w_hand * (1.0 - root_keep)
        if root_keep:
            d[wrist] = w_hand * root_keep
        if t > 1.0 - blend_r and si < 2:
            fb = _smooth01((t - (1.0 - blend_r)) / blend_r) * 0.5
            d[joints[si]] = wf * (1.0 - fb)
            d[joints[si + 1]] = wf * fb
        elif t < blend_r and si > 0:
            fb = _smooth01((blend_r - t) / blend_r) * 0.5
            d[joints[si]] = wf * (1.0 - fb)
            d[joints[si - 1]] = wf * fb
        else:
            d[joints[si]] = wf
        wmap[vi] = d

    set_weight_map(obj, wmap)


# Face bone regions: (bone, radius, weight_cap, optional axis constraints)
def apply_bento_face(obj, sk, max_total: float = 0.85) -> None:
    """Layer Bento face-bone weights on top of mHead for animatable faces.

    Weights are proximity fields around each face bone pivot, capped so the
    remaining mHead share keeps the face stable.  The jaw uses a directional
    mask (below mouth line, in front of the jaw pivot).
    """
    specs = []

    def add(bone, radius, cap):
        if bone in sk.joints:
            specs.append((bone, Vector(sk.world_pivot(bone)), radius, cap))

    for side in ("Left", "Right"):
        add(f"mFaceEyebrowInner{side}", 0.020, 0.7)
        add(f"mFaceEyebrowCenter{side}", 0.020, 0.7)
        add(f"mFaceEyebrowOuter{side}", 0.020, 0.6)
        add(f"mFaceEyeLidUpper{side}", 0.014, 0.8)
        add(f"mFaceEyeLidLower{side}", 0.012, 0.7)
        add(f"mFaceCheekLower{side}", 0.030, 0.5)
        add(f"mFaceLipUpper{side}", 0.014, 0.7)
        add(f"mFaceLipLower{side}", 0.014, 0.6)
        add(f"mFaceLipCorner{side}", 0.014, 0.7)
        add(f"mFaceEar1{side}", 0.030, 0.9)
        add(f"mFaceForehead{side}", 0.030, 0.4)
    add("mFaceLipUpperCenter", 0.013, 0.7)
    add("mFaceLipLowerCenter", 0.013, 0.6)
    add("mFaceNoseCenter", 0.016, 0.6)
    add("mFaceNoseLeft", 0.012, 0.5)
    add("mFaceNoseRight", 0.012, 0.5)
    add("mFaceChin", 0.020, 0.5)

    jaw = Vector(sk.world_pivot("mFaceJaw"))
    mouth_z = sk.world_pivot("mFaceLipLowerCenter")[2]

    wmap = get_weight_map(obj)
    verts = obj.data.vertices

    for vi, d in enumerate(wmap):
        head_w = d.get("mHead", 0.0)
        if head_w <= 1e-5:
            continue
        co = verts[vi].co
        fields: dict[str, float] = {}

        # jaw: directional field
        if co.z < mouth_z + 0.012 and co.x > jaw.x - 0.02:
            depth = _smooth01((mouth_z + 0.012 - co.z) / 0.035)
            fwd = _smooth01((co.x - (jaw.x - 0.02)) / 0.04)
            lat = _smooth01(1.0 - abs(co.y) / 0.075)
            f = 0.9 * depth * fwd * lat
            if f > 0.01:
                fields["mFaceJaw"] = f

        for bone, pivot, radius, cap in specs:
            dist = (co - pivot).length
            if dist < radius * 2.0:
                f = cap * _smooth01(1.0 - dist / (radius * 2.0))
                if f > 0.01:
                    fields[bone] = max(fields.get(bone, 0.0), f)

        if not fields:
            continue
        total_f = sum(fields.values())
        scale = min(1.0, max_total / total_f) if total_f > 0 else 0.0
        moved_total = 0.0
        for bone, f in fields.items():
            moved = head_w * min(f * scale, 1.0)
            d[bone] = d.get(bone, 0.0) + moved
            moved_total += moved
        d["mHead"] = max(0.0, head_w - moved_total)
        wmap[vi] = d

    set_weight_map(obj, wmap)


def smooth_groups(obj, names=None, factor=0.5, repeat=2) -> None:
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="WEIGHT_PAINT")
    bpy.ops.object.vertex_group_smooth(
        group_select_mode="ALL", factor=factor, repeat=repeat, expand=0.0
    )
    bpy.ops.object.mode_set(mode="OBJECT")


def cleanup_weights(obj, limit: int = 4) -> None:
    """Keep the 4 strongest influences per vertex and normalize to 1.0."""
    wmap = get_weight_map(obj)
    for vi, d in enumerate(wmap):
        if not d:
            d = {"mPelvis": 1.0}
        top = sorted(d.items(), key=lambda kv: kv[1], reverse=True)[:limit]
        total = sum(w for _, w in top)
        wmap[vi] = {n: w / total for n, w in top}
    set_weight_map(obj, wmap)


def transfer_weights(src_obj, dst_obj) -> None:
    """Copy weights from body to garment (nearest-face interpolation)."""
    mod = dst_obj.modifiers.new("DataTransfer", "DATA_TRANSFER")
    mod.object = src_obj
    mod.use_vert_data = True
    mod.data_types_verts = {"VGROUP_WEIGHTS"}
    mod.vert_mapping = "POLYINTERP_NEAREST"
    bpy.context.view_layer.objects.active = dst_obj
    bpy.ops.object.datalayout_transfer(modifier=mod.name)
    bpy.ops.object.modifier_apply(modifier=mod.name)
