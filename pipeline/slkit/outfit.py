"""Outfit construction: cloth garments derived from the body surface.

Every garment is cut from the shaped body mesh itself:
  * perfect fit against this body's rest shape,
  * identical skin weights (the body's vertex groups ride along with the
    duplicated geometry) -- the same reason commercial clothes are rigged
    by copying the dev-kit body's weights,
  * identical SLUV texture coordinates, so garment textures are painted on
    the standard avatar UV layout with exact boundary control.

Displacement fields add cloth volume, flares and fold ripples on top.
"""

from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Vector

from .bl_utils import select_only


def _s(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def shell_from_body(
    body,
    name: str,
    keep_face,          # (center: Vector) -> bool
    offset,             # (co: Vector, normal: Vector) -> float (meters)
    material_names,     # ordered list for the new object
    material_of=None,   # (center: Vector, src_slot_name: str) -> mat name
):
    """Duplicate the body, keep only faces passing `keep_face`, offset the
    remaining vertices along their normals, remap materials."""
    src_slot_names = [m.name if m else "" for m in body.data.materials]

    new_mesh = body.data.copy()
    obj = bpy.data.objects.new(name, new_mesh)
    bpy.context.scene.collection.objects.link(obj)
    # recreate the body's vertex groups in the same order: the mesh deform
    # layer stores group indices, so order must match exactly
    for vg in body.vertex_groups:
        obj.vertex_groups.new(name=vg.name)

    bm = bmesh.new()
    bm.from_mesh(body.data)  # includes deform layer with group indices
    bm.faces.ensure_lookup_table()

    # keep a face if ANY of its vertices passes -> closes pinholes and gives
    # a one-ring dilation so garment borders follow clean topology
    doomed = [
        f for f in bm.faces if not any(keep_face(v.co) for v in f.verts)
    ]
    bmesh.ops.delete(bm, geom=doomed, context="FACES")

    # drop small disconnected islands (selection noise)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    seen = set()
    islands = []
    for f in bm.faces:
        if f in seen:
            continue
        island = []
        stack = [f]
        seen.add(f)
        while stack:
            cur = stack.pop()
            island.append(cur)
            for e in cur.edges:
                for nf in e.link_faces:
                    if nf not in seen:
                        seen.add(nf)
                        stack.append(nf)
        islands.append(island)
    if islands:
        biggest = max(len(i) for i in islands)
        doomed = [f for isl in islands if len(isl) < max(24, biggest // 20) for f in isl]
        if doomed:
            bmesh.ops.delete(bm, geom=doomed, context="FACES")

    loose = [v for v in bm.verts if not v.link_faces]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")

    # capture smooth pre-offset normals, then offset
    bm.normal_update()
    normals = {v: v.normal.copy() for v in bm.verts}
    for v in bm.verts:
        v.co = v.co + normals[v] * offset(v.co, normals[v])

    # relax the cloth: keeps borders from crumpling where offset varies
    interior = [v for v in bm.verts if not v.is_boundary]
    for _ in range(2):
        bmesh.ops.smooth_vert(
            bm, verts=interior, factor=0.5,
            use_axis_x=True, use_axis_y=True, use_axis_z=True,
        )
    boundary = [v for v in bm.verts if v.is_boundary]
    for _ in range(3):
        # smooth boundary along itself (Laplacian on the border ring)
        new_pos = {}
        for v in boundary:
            ns = [e.other_vert(v) for e in v.link_edges if e.is_boundary]
            if len(ns) >= 2:
                avg = sum((n.co for n in ns), Vector()) / len(ns)
                new_pos[v] = v.co.lerp(avg, 0.5)
        for v, p in new_pos.items():
            v.co = p

    bm.to_mesh(new_mesh)
    bm.free()

    # materials -- capture original indices BEFORE clearing slots
    # (materials.clear() resets every polygon's material_index to 0)
    orig_idx = [p.material_index for p in new_mesh.polygons]
    new_mesh.materials.clear()
    mats = {}
    for mn in material_names:
        mat = bpy.data.materials.get(mn) or bpy.data.materials.new(mn)
        new_mesh.materials.append(mat)
        mats[mn] = len(new_mesh.materials) - 1
    if material_of is None:
        for p in new_mesh.polygons:
            p.material_index = 0
    else:
        for p, oi in zip(new_mesh.polygons, orig_idx):
            src = src_slot_names[oi] if oi < len(src_slot_names) else ""
            mn = material_of(Vector(p.center), src)
            p.material_index = mats.get(mn, 0)

    new_mesh.update()
    select_only(obj)
    bpy.ops.object.shade_smooth()
    return obj


def bind_to_rig(obj, arm_obj):
    mod = obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm_obj
    mod.use_vertex_groups = True
    obj.parent = arm_obj


def ripple(co: Vector, axis_z: tuple[float, float], k: int, amp: float, phase: float = 0.0) -> float:
    """Vertical cloth fold ripples around the Z axis."""
    z0, z1 = axis_z
    if not (z0 < co.z < z1):
        return 0.0
    theta = math.atan2(co.y, co.x)
    band = _s((co.z - z0) / (0.15 * (z1 - z0))) * _s((z1 - co.z) / (0.15 * (z1 - z0)))
    return amp * band * math.sin(k * theta + phase)


# ---------------------------------------------------------------------------
# garments
# ---------------------------------------------------------------------------


def build_robe(body, sk):
    """Open sleeved robe: covers shoulders, back, upper arms; open chest."""

    def keep(c: Vector) -> bool:
        ay = abs(c.y)
        # sleeves: deltoid to just above the elbow (forearms stay bare
        # for the bracers, like the reference art)
        if 0.16 < ay < 0.34 and c.z > 1.30:
            return True
        # shoulders / traps (stop at the neck base -- never up the head)
        if 1.47 < c.z < 1.60 and 0.06 < ay < 0.24 and c.x < 0.09:
            return True
        # back panel from below the nape down to upper thigh
        if c.x < 0.005 and 0.88 < c.z < 1.58 and ay < 0.24:
            return True
        # side panels of torso
        if ay > 0.115 and 0.95 < c.z < 1.47 and c.x < 0.075:
            return True
        return False

    def off(co: Vector, n: Vector) -> float:
        ay = abs(co.y)
        base = 0.022
        # sleeve opening flares toward its hem above the elbow
        if ay > 0.24:
            base += 0.020 * _s((ay - 0.24) / 0.10)
        # skirt of the robe stands off the hips
        if co.z < 1.05:
            base += 0.012 * _s((1.05 - co.z) / 0.15)
        return base

    def mat_of(c: Vector, src: str) -> str:
        return "RobeUpper" if src != "BAKED_LOWER" else "RobeLower"

    obj = shell_from_body(
        body, "GanondorfRobe", keep, off, ["RobeUpper", "RobeLower"], mat_of
    )
    # fold ripples on the back panel / skirt
    me = obj.data
    for v in me.vertices:
        r = ripple(v.co, (0.88, 1.25), 9, 0.006, 0.6)
        if v.co.x < 0.0:
            v.co.x += r * 0.4
            v.co.z += 0.0
    me.update()
    return obj


def build_sash(body, sk):
    """Wide silk obi wrapped around the waist with a front knot."""

    def keep(c: Vector) -> bool:
        # slightly higher band at the back so the obi clears the butt
        z_min = 1.005 if c.x > 0.0 else 1.045
        return z_min < c.z < 1.15

    def off(co: Vector, n: Vector) -> float:
        # thick knotted wrap in front; tucks THIN at the back so it sits
        # under the robe's back panel (robe offset ~0.022) instead of
        # poking through it
        f = _s((co.x + 0.06) / 0.16)
        return 0.010 + 0.024 * f

    obj = shell_from_body(body, "GanondorfSash", keep, off, ["Sash"], None)

    # custom cylindrical UV (own silk texture, not SLUV)
    me = obj.data
    uv = me.uv_layers.active
    for poly in me.polygons:
        for li in range(poly.loop_start, poly.loop_start + poly.loop_total):
            co = me.vertices[me.loops[li].vertex_index].co
            theta = math.atan2(co.y, co.x)
            uv.data[li].uv = ((theta / (2 * math.pi)) % 1.0, (co.z - 1.005) / 0.145)

    # wrap ripples: horizontal wrap layers
    for v in me.vertices:
        band = math.sin((v.co.z - 1.005) / 0.145 * math.pi * 3.0)
        v.co.x += 0.004 * band * max(0.0, v.co.x / 0.15)
    me.update()

    # knot: braided bulge at front-left
    bm = bmesh.new()
    bm.from_mesh(me)
    for v in bm.verts:
        d = (v.co - Vector((0.14, 0.07, 1.08))).length
        if d < 0.06:
            v.normal_update()
            v.co += v.normal * 0.016 * _s(1.0 - d / 0.06)
    bm.to_mesh(me)
    bm.free()
    me.update()
    return obj


def build_pants(body, sk):
    """Wide gathered trousers from below the sash to the ankles."""

    def keep(c: Vector) -> bool:
        return 0.14 < c.z < 1.06 and abs(c.y) < 0.30

    def off(co: Vector, n: Vector) -> float:
        # keep a firm minimum standoff everywhere so the muscular legs
        # never poke through the cloth
        base = 0.020
        # bagginess peaks at mid-thigh/knee, gathers at ankle
        bag = _s((co.z - 0.20) / 0.30) * _s((0.95 - co.z) / 0.25)
        base += 0.028 * bag
        # concave back-of-knee: ease the offset a little to limit cloth
        # self-folding, but never below the safe standoff
        if n.x < -0.3 and 0.40 < co.z < 0.56:
            base = max(0.018, base * 0.7)
        # gathered cuff
        if co.z < 0.22:
            base = 0.012
        return base

    obj = shell_from_body(body, "GanondorfPants", keep, off, ["Pants"], None)

    me = obj.data
    for v in me.vertices:
        side = 1.0 if v.co.y > 0 else -1.0
        theta = math.atan2(v.co.y - side * 0.085, v.co.x)
        bag = _s((v.co.z - 0.22) / 0.25) * _s((0.9 - v.co.z) / 0.3)
        amp = 0.005 * bag
        v.co.x += amp * math.sin(7 * theta + 1.0)
        v.co.y += amp * math.cos(5 * theta)
    me.update()
    return obj


def build_bracers(body, sk):
    """Forearm guards; separate left and right attachments."""
    out = []
    for side, sgn in (("Left", 1.0), ("Right", -1.0)):

        def keep(c: Vector, sgn=sgn) -> bool:
            return 0.42 < c.y * sgn < 0.60 and c.z > 1.35

        def off(co: Vector, n: Vector) -> float:
            ay = abs(co.y)
            # ridged armor bands
            band = 0.5 + 0.5 * math.sin((ay - 0.42) / 0.18 * math.pi * 4.0)
            return 0.009 + 0.004 * band

        obj = shell_from_body(
            body, f"GanondorfBracer{side}", keep, off, ["Bracer"], None
        )
        out.append(obj)
    return out


def build_anklets(body, sk):
    """Shin wraps with a golden anklet ring, per leg."""
    out = []
    for side, sgn in (("Left", 1.0), ("Right", -1.0)):

        def keep(c: Vector, sgn=sgn) -> bool:
            return 0.06 < c.z < 0.30 and c.y * sgn > 0.01 and abs(c.y) < 0.30

        def off(co: Vector, n: Vector) -> float:
            band = 0.5 + 0.5 * math.sin(co.z / 0.30 * math.pi * 5.0)
            return 0.006 + 0.003 * band

        obj = shell_from_body(
            body, f"GanondorfAnklet{side}", keep, off, ["LegWrap"], None
        )
        out.append(obj)
    return out
