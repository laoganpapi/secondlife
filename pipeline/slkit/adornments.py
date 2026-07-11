"""Hair, jewelry and the sword: primitive/curve-based attachments.

Positions are computed against the shaped body in SL avatar space
(X forward, Y left, Z up).  Rigging: jewelry and hair weight to the bones
of the region they sit on; the sword is a static (unrigged) attachment.
"""

from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from .bl_utils import select_only


def _mat(name: str):
    return bpy.data.materials.get(name) or bpy.data.materials.new(name)


def _sm(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _new_obj(name: str, me) -> bpy.types.Object:
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _clear_groups(obj) -> None:
    """Remove every vertex group so weights can be reassigned from scratch.

    Meshes cut from the body (shell_from_body) inherit ALL of the body's
    vertex groups -- including fitted-mesh collision volumes (HEAD, NECK,
    ...).  Left in place, those give a worn attachment slider/physics
    response it must not have.  Adornments weight to plain mBones only, so
    the inherited groups must be cleared first."""
    for vg in list(obj.vertex_groups):
        obj.vertex_groups.remove(vg)


def _weight_all(obj, weights: dict[str, float]) -> None:
    idx = list(range(len(obj.data.vertices)))
    for bone, w in weights.items():
        vg = obj.vertex_groups.get(bone) or obj.vertex_groups.new(name=bone)
        vg.add(idx, w, "REPLACE")


def _smooth(obj) -> None:
    select_only(obj)
    bpy.ops.object.shade_smooth()


def curve_tube(
    name: str,
    points: list[tuple[Vector, float]],
    resolution: int = 12,
    bevel_resolution: int = 6,
) -> bpy.types.Object:
    """Tapered tube along a smooth curve: [(position, radius), ...]."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.resolution_u = resolution
    cu.bevel_depth = 1.0
    cu.bevel_resolution = bevel_resolution
    cu.use_fill_caps = True
    sp = cu.splines.new("NURBS")
    sp.points.add(len(points) - 1)
    for i, (co, r) in enumerate(points):
        sp.points[i].co = (co.x, co.y, co.z, 1.0)
        sp.points[i].radius = r
    sp.use_endpoint_u = True
    obj = _new_obj(name, cu)
    select_only(obj)
    bpy.ops.object.convert(target="MESH")
    obj = bpy.context.view_layer.objects.active
    # cylindrical UVs along the tube
    me = obj.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    zs = [v.co.z for v in me.vertices] or [0.0, 1.0]
    z0, z1 = min(zs), max(zs)
    span = max(1e-5, z1 - z0)
    uv = me.uv_layers.active
    for poly in me.polygons:
        for li in range(poly.loop_start, poly.loop_start + poly.loop_total):
            co = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = (
                (math.atan2(co.y, co.x) / (2 * math.pi)) % 1.0,
                (co.z - z0) / span,
            )
    return obj


def add_torus(
    name, center: Vector, major_r, minor_r, rot: Matrix | None = None,
    seg_major=32, seg_minor=12,
):
    bm = bmesh.new()  # bmesh has no torus op; build rings manually
    verts = []
    for i in range(seg_major):
        a = 2 * math.pi * i / seg_major
        ring_center = Vector((math.cos(a) * major_r, math.sin(a) * major_r, 0.0))
        ring = []
        for j in range(seg_minor):
            b = 2 * math.pi * j / seg_minor
            radial = Vector((math.cos(a), math.sin(a), 0.0))
            p = ring_center + radial * (math.cos(b) * minor_r)
            p.z = math.sin(b) * minor_r
            ring.append(bm.verts.new(p))
        verts.append(ring)
    for i in range(seg_major):
        for j in range(seg_minor):
            a0 = verts[i][j]
            a1 = verts[i][(j + 1) % seg_minor]
            b0 = verts[(i + 1) % seg_major][j]
            b1 = verts[(i + 1) % seg_major][(j + 1) % seg_minor]
            bm.faces.new((a0, b0, b1, a1))
    me = bpy.data.meshes.new(name)
    bm.transform((rot or Matrix.Identity(4)))
    bm.to_mesh(me)
    bm.free()
    me.update()
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    obj = _new_obj(name, me)
    obj.location = center
    select_only(obj)
    bpy.ops.object.transform_apply(location=True)
    bpy.ops.object.shade_smooth()
    return obj


def add_uv_sphere(name, center: Vector, r, seg=24, rings=16, squash=1.0):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=rings, radius=r)
    for v in bm.verts:
        v.co.z *= squash
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    obj = _new_obj(name, me)
    obj.location = center
    select_only(obj)
    bpy.ops.object.transform_apply(location=True)
    bpy.ops.object.shade_smooth()
    return obj


def _assign_single_material(obj, name):
    obj.data.materials.clear()
    obj.data.materials.append(_mat(name))


def _join(objs, name):
    select_only(objs)
    bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    obj.name = name
    return obj


# ---------------------------------------------------------------------------


def build_hair(body, sk):
    """Ganondorf's swept-back red mane gathered into a high back-knot,
    with long sideburn locks framing the face.

    The mane is a scalp shell whose inflation grows toward the crown-back
    and converges into the knot; strands come from the texture (aniso
    gradient painted along the front->back UV direction), not geometry.
    """
    knot_base = Vector((-0.055, 0.0, 1.885))

    def keep(c: Vector) -> bool:
        # top of the skull, above an arcing hairline:
        # front hairline high (z>1.795), dropping to 1.755 at the temples
        # and sweeping to the nape at the back -- but never over the
        # (pointed, visible) ears
        if abs(c.y) > 0.072 and c.z < 1.80 and c.x > -0.055:
            return False  # keep the ears clear
        if c.x > 0.02:
            return c.z > 1.795 - 0.05 * _sm((abs(c.y) - 0.03) / 0.05)
        if c.x > -0.05:
            return c.z > 1.755
        return c.z > 1.70

    def off(co: Vector, n: Vector) -> float:
        # teardrop mane: thin at hairline, gathering mass toward the knot
        toward = 1.0 - min(1.0, (co - knot_base).length / 0.16)
        up = max(0.0, min(1.0, (co.z - 1.74) / 0.12))
        return 0.005 + 0.012 * up + 0.016 * _sm(toward)

    from .outfit import shell_from_body

    scalp = shell_from_body(body, "HairScalp", keep, off, ["Hair"], None)
    # swept UVs: u around the head, v hairline->knot (strand direction)
    me = scalp.data
    uv = me.uv_layers.active
    for poly in me.polygons:
        for li in range(poly.loop_start, poly.loop_start + poly.loop_total):
            co = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = (
                0.5 + math.atan2(co.y, max(1e-4, co.z - 1.55)) / math.pi,
                (0.11 - co.x) / 0.24,
            )

    parts = [scalp]

    # topknot: modest bun + gold tie + short swept-back flame tail
    tie = add_torus("HairTie", knot_base + Vector((-0.004, 0, 0.018)), 0.020, 0.007)
    _assign_single_material(tie, "HairGold")
    bun = add_uv_sphere("HairBun", knot_base + Vector((0, 0, 0.008)), 0.024, squash=0.9)
    _assign_single_material(bun, "Hair")
    tail_pts = [
        (knot_base + Vector((-0.004, 0.000, 0.020)), 0.016),
        (knot_base + Vector((-0.052, 0.006, 0.042)), 0.012),
        (knot_base + Vector((-0.098, -0.004, 0.048)), 0.007),
        (knot_base + Vector((-0.132, 0.003, 0.040)), 0.0035),
    ]
    tail = curve_tube("HairTail", tail_pts)
    _assign_single_material(tail, "Hair")
    parts += [tie, bun, tail]

    # sideburns: slim locks hugging the cheeks, ending at the jawline
    for side, sgn in (("L", 1.0), ("R", -1.0)):
        pts = [
            (Vector((0.036, sgn * 0.0735, 1.762)), 0.0095),
            (Vector((0.049, sgn * 0.0760, 1.722)), 0.0085),
            (Vector((0.057, sgn * 0.0725, 1.682)), 0.0068),
            (Vector((0.062, sgn * 0.0650, 1.648)), 0.0038),
        ]
        burn = curve_tube(f"HairSideburn{side}", pts)
        for v in burn.data.vertices:  # flatten against the cheek
            v.co.y -= sgn * max(0.0, (abs(v.co.y) - 0.068)) * 0.45
        _assign_single_material(burn, "Hair")
        parts.append(burn)

    hair = _join(parts, "GanondorfHair")
    # consolidate to two material slots: Hair, HairGold
    me = hair.data
    slot_names = [m.name for m in me.materials]
    keep_names = []
    for n in ("Hair", "HairGold"):
        if n in slot_names:
            keep_names.append(n)
    remap = {}
    for i, n in enumerate(slot_names):
        tgt = "HairGold" if "Gold" in n else "Hair"
        remap[i] = keep_names.index(tgt)
    for p in me.polygons:
        p.material_index = remap.get(p.material_index, 0)
    # rebuild slots
    mats = [ _mat(n) for n in keep_names ]
    me.materials.clear()
    for m in mats:
        me.materials.append(m)

    # the scalp shell inherited the body's groups (mHead, mNeck, HEAD,
    # NECK, mFaceForehead...); clear them so the mane rigs to mHead only
    # and never reacts to head-size / appearance sliders
    _clear_groups(hair)
    _weight_all(hair, {"mHead": 1.0})
    # lower back locks get a touch of neck follow
    vg_head = hair.vertex_groups["mHead"]
    vg_neck = hair.vertex_groups.get("mNeck") or hair.vertex_groups.new(name="mNeck")
    for v in hair.data.vertices:
        if v.co.z < 1.70:
            f = min(0.35, (1.70 - v.co.z) * 3.0)
            vg_head.add([v.index], 1.0 - f, "REPLACE")
            vg_neck.add([v.index], f, "REPLACE")
    return hair


def build_circlet(body, sk):
    """Gold browpiece with the red forehead jewel."""
    parts = []
    # brow band: elliptical arc fitted to the measured forehead profile
    # (brow ridge reaches x=0.116 at center, 0.104 at |y|=0.04)
    band_pts = []
    for i in range(15):
        a = math.pi * (0.14 + 0.72 * i / 14)
        y = math.cos(a) * 0.0955
        x = 0.006 + math.sin(a) * 0.118
        z = 1.7825 + 0.005 * math.sin(a)
        band_pts.append((Vector((x, y, z)), 0.006))
    band = curve_tube("CircletBand", band_pts)
    _assign_single_material(band, "Gold")
    parts.append(band)

    jewel = add_uv_sphere("CircletJewel", Vector((0.1225, 0.0, 1.788)), 0.0135, squash=1.25)
    _assign_single_material(jewel, "Gem")
    parts.append(jewel)

    frame = add_torus(
        "CircletFrame", Vector((0.116, 0.0, 1.788)), 0.0152, 0.0038,
        rot=Matrix.Rotation(math.radians(90), 4, "Y"),
    )
    _assign_single_material(frame, "Gold")
    parts.append(frame)

    obj = _join(parts, "GanondorfCirclet")
    _dedupe_two_slots(obj, ("Gold", "Gem"))
    _weight_all(obj, {"mHead": 1.0})
    return obj


def _dedupe_two_slots(obj, names):
    me = obj.data
    slot_names = [m.name for m in me.materials]
    remap = {}
    for i, n in enumerate(slot_names):
        base = names[1] if names[1] in n else names[0]
        remap[i] = list(names).index(base)
    for p in me.polygons:
        p.material_index = remap.get(p.material_index, 0)
    me.materials.clear()
    for n in names:
        me.materials.append(_mat(n))


def build_earrings(body, sk):
    parts = []
    for side, sgn in (("L", 1.0), ("R", -1.0)):
        # hangs from the earlobe, below the ear
        hoop = add_torus(
            f"Earring{side}",
            Vector((0.014, sgn * 0.082, 1.692)),
            0.013, 0.0034,
            rot=Matrix.Rotation(math.radians(90), 4, "X"),
        )
        _assign_single_material(hoop, "Gold")
        parts.append(hoop)
    obj = _join(parts, "GanondorfEarrings")
    _assign_single_material(obj, "Gold")
    _weight_all(obj, {"mHead": 1.0})
    return obj


def build_necklace(body, sk):
    """Heavy gold collar with plates and center medallion + gem."""
    parts = []
    # collar: arc resting on the upper chest, standing clear of the traps
    pts = []
    for i in range(15):
        a = math.pi * (0.08 + 0.84 * i / 14)
        y = math.cos(a) * 0.118
        x = 0.030 + math.sin(a) * 0.118
        z = 1.560 - 0.075 * math.sin(a)
        pts.append((Vector((x, y, z)), 0.010))
    collar = curve_tube("NecklaceCollar", pts)
    _assign_single_material(collar, "Gold")
    parts.append(collar)

    # hanging plates, standing clear of the pecs
    for i, y in enumerate((-0.062, 0.0, 0.062)):
        cx = 0.152 - abs(y) * 0.45
        cz = 1.468 - (0.020 if y == 0.0 else 0.0)
        plate = add_uv_sphere(f"NecklacePlate{i}", Vector((cx, y, cz)), 0.030, squash=1.4)
        for v in plate.data.vertices:  # flatten into a plate
            v.co.x = (v.co.x - cx) * 0.28 + cx
        _assign_single_material(plate, "Gold")
        parts.append(plate)

    gem = add_uv_sphere("NecklaceGem", Vector((0.168, 0.0, 1.446)), 0.015, squash=1.3)
    _assign_single_material(gem, "Gem")
    parts.append(gem)

    obj = _join(parts, "GanondorfNecklace")
    _dedupe_two_slots(obj, ("Gold", "Gem"))
    _weight_all(obj, {"mChest": 0.75, "mNeck": 0.25})
    return obj


def build_sword(body, sk):
    """Sheathed great-blade worn at the left hip (static attachment).

    Built around the origin lying along +Y so it can be uploaded unrigged
    and attached to the Left Hip attachment point in-world.
    """
    parts = []
    L = 1.05  # overall sheathed length

    # scabbard: flattened tube
    pts = [
        (Vector((0.0, -0.18, 0.0)), 0.030),
        (Vector((0.0, 0.25, 0.0)), 0.027),
        (Vector((0.0, 0.62, 0.0)), 0.022),
        (Vector((0.0, 0.80, 0.0)), 0.012),
    ]
    sheath = curve_tube("SwordSheath", pts)
    for v in sheath.data.vertices:
        v.co.x *= 0.45  # flatten
    _assign_single_material(sheath, "Sheath")
    parts.append(sheath)

    # hilt: grip + guard + pommel
    grip = curve_tube(
        "SwordGrip",
        [(Vector((0.0, -0.42, 0.0)), 0.013), (Vector((0.0, -0.19, 0.0)), 0.015)],
    )
    _assign_single_material(grip, "Gold")
    parts.append(grip)
    guard = add_torus(
        "SwordGuard", Vector((0.0, -0.175, 0.0)), 0.034, 0.011,
        rot=Matrix.Rotation(math.radians(90), 4, "X"),
    )
    for v in guard.data.vertices:
        v.co.x *= 0.5
    _assign_single_material(guard, "Gold")
    parts.append(guard)
    pommel = add_uv_sphere("SwordPommel", Vector((0.0, -0.435, 0.0)), 0.020)
    _assign_single_material(pommel, "Gem")
    parts.append(pommel)

    obj = _join(parts, "GanondorfSword")
    # slots: Sheath, Gold, Gem
    me = obj.data
    slot_names = [m.name for m in me.materials]
    order = ["Sheath", "Gold", "Gem"]
    remap = {}
    for i, n in enumerate(slot_names):
        base = "Gem" if "Gem" in n else ("Gold" if "Gold" in n else "Sheath")
        remap[i] = order.index(base)
    for p in me.polygons:
        p.material_index = remap.get(p.material_index, 0)
    me.materials.clear()
    for n in order:
        me.materials.append(_mat(n))
    return obj
