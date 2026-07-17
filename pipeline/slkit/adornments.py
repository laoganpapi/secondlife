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


def _assign_slots(obj, names, active):
    """Give obj the item's FULL canonical slot table, all faces on `active`.

    Every part of a multi-material item gets the same slot list before
    joining, so bpy.ops.object.join merges slots 1:1 and no post-join
    remap is needed.  (materials.clear() resets every polygon's
    material_index to 0, so any clear-and-rebuild AFTER assigning face
    indices silently collapses the item to one material -- the indices
    must be set last, as done here.)"""
    me = obj.data
    me.materials.clear()
    for n in names:
        me.materials.append(_mat(n))
    idx = names.index(active)
    for p in me.polygons:
        p.material_index = idx


def _join(objs, name):
    select_only(objs)
    bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    obj.name = name
    return obj


# ---------------------------------------------------------------------------


def strand_card(name: str, points: list, widths: list, uv_u: tuple, thickness=0.0018):
    """A flat tapered ribbon (real front+back faces + edge caps, so it
    reads solidly from any angle without depending on a double-sided
    render flag).  This is the SL "mesh hair" primitive: the geometry is
    a plain card -- individual strand definition comes entirely from an
    alpha-cutout texture sampled across `uv_u` (see paint_hair_strands),
    not from the mesh itself."""
    bm = bmesh.new()
    uv_layer = bm.loops.layers.uv.new("UVMap")
    n = len(points)
    front, back = [], []
    for i in range(n):
        p = points[i]
        if i == 0:
            tangent = (points[1] - points[0]).normalized()
        elif i == n - 1:
            tangent = (points[i] - points[i - 1]).normalized()
        else:
            tangent = (points[i + 1] - points[i - 1]).normalized()
        side = tangent.cross(Vector((0.0, 0.0, 1.0)))
        if side.length < 1e-5:
            side = Vector((1.0, 0.0, 0.0))
        side.normalize()
        normal = tangent.cross(side).normalized()
        half_w = widths[i] * 0.5
        left, right = p - side * half_w, p + side * half_w
        front.append((bm.verts.new(left + normal * thickness * 0.5),
                      bm.verts.new(right + normal * thickness * 0.5)))
        back.append((bm.verts.new(left - normal * thickness * 0.5),
                     bm.verts.new(right - normal * thickness * 0.5)))

    u0, u1 = uv_u

    def set_uv(face, uvs):
        for loop, uv in zip(face.loops, uvs):
            loop[uv_layer].uv = uv

    for i in range(n - 1):
        v0, v1 = i / (n - 1), (i + 1) / (n - 1)
        fl0, fr0 = front[i]; fl1, fr1 = front[i + 1]
        bl0, br0 = back[i]; bl1, br1 = back[i + 1]
        set_uv(bm.faces.new((fl0, fr0, fr1, fl1)), [(u0, v0), (u1, v0), (u1, v1), (u0, v1)])
        set_uv(bm.faces.new((br0, bl0, bl1, br1)), [(u1, v0), (u0, v0), (u0, v1), (u1, v1)])
        set_uv(bm.faces.new((fl0, fl1, bl1, bl0)), [(u0, v0)] * 4)
        set_uv(bm.faces.new((fr1, fr0, br0, br1)), [(u1, v1)] * 4)
    fl0, fr0 = front[0]; bl0, br0 = back[0]
    set_uv(bm.faces.new((fr0, fl0, bl0, br0)), [(0.5 * (u0 + u1), 0.0)] * 4)
    fln, frn = front[-1]; bln, brn = back[-1]
    set_uv(bm.faces.new((fln, frn, brn, bln)), [(0.5 * (u0 + u1), 1.0)] * 4)

    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    return _new_obj(name, me)


# approximate scalp ellipsoid used to place hair-card roots -- purely a
# placement aid; the HairScalp shell below backs it so any mismatch with
# the true head surface never shows through as a bald gap
def _scalp_root(lat: float, lon_deg: float) -> Vector:
    """lat: 0 (crown) -> 1 (nape).  lon_deg: 0 = straight back, +-100 =
    wraps toward the temple/ear, never into the face."""
    s = lon_deg / 100.0
    z = 1.90 - lat * 0.35
    y_max = 0.065 + 0.045 * _sm(lat / 0.35) * _sm((1.0 - lat) / 0.5)
    y = s * y_max
    depth = -0.02 - 0.055 * _sm(lat / 0.3)
    bulge = _sm(lat / 0.45) * _sm((1.0 - lat) / 0.55)
    x = depth - 0.045 * bulge + 0.10 * abs(s) ** 1.4
    return Vector((x, y, z))


def build_hair(body, sk):
    """Ganondorf's long voluminous red mane, built the way quality SL
    "mesh hair" is built: a thin scalp shell for coverage, plus ~50 flat
    tapered strand cards fanned across the crown, temples and a long
    back cascade.  Every card shares one texture atlas whose alpha
    channel cuts each card into 3-4 individual visible strands -- a
    smooth shell never reads as hair in SL; the strand definition has to
    come from the alpha mask, not the geometry.
    """
    # the scalp shell is ONLY root coverage right where the crown cards
    # emerge -- it must never be the visible hair surface itself (a big
    # opaque OR alpha-cutout dome both read as "a cap"; a strand tile
    # spread across the full head width is mostly transparent gap, which
    # left dark voids).  Keep it small, opaque, and hidden under the
    # cards; every card below this line gets true see-through gaps to
    # skin, which is what actually reads as individual strands.
    SCALP_Z = 1.74

    def keep(c: Vector) -> bool:
        ay = abs(c.y)
        if ay > 0.072 and c.z < 1.80 and c.x > -0.055:
            return False  # keep the (pointed, visible) ears clear
        if c.x > 0.09 and ay < 0.018 and c.z > 1.772:
            return True  # widow's peak
        if c.x > 0.02:
            return c.z > 1.795 - 0.05 * _sm((ay - 0.03) / 0.05)
        if c.x > -0.05:
            return c.z > 1.755
        return c.z > SCALP_Z and ay < 0.10  # crown only, not the nape

    def off(co: Vector, n: Vector) -> float:
        up = max(0.0, min(1.0, (co.z - 1.72) / 0.14))
        return 0.003 + 0.005 * up

    from .outfit import shell_from_body

    scalp = shell_from_body(body, "HairScalp", keep, off, ["Hair"], None)
    # opaque solid-fill tile (u in [0.8,1.0]) -- deliberately flat, since
    # it should never be the dominant visible surface
    me = scalp.data
    uv = me.uv_layers.active
    for poly in me.polygons:
        for li in range(poly.loop_start, poly.loop_start + poly.loop_total):
            co = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = (0.9, min(1.0, max(0.0, (1.92 - co.z) / 0.20)))
    _assign_single_material(scalp, "Hair")
    parts = [scalp]

    def add_card(lat, lon, direction, length, w0, w1, bow, tile, segs=4):
        root = _scalp_root(lat, lon)
        side_axis = Vector((0.0, 1.0 if lon >= 0 else -1.0, 0.0))
        pts, widths = [], []
        for i in range(segs + 1):
            t = i / segs
            p = root + direction * (length * t)
            p += Vector((0.0, 0.0, -0.10 * length * t * t))  # gravity droop
            p += side_axis * (bow * math.sin(t * math.pi * 0.5))
            pts.append(p)
            widths.append(w0 * (1 - t) + w1 * t)
        u0 = tile / 5.0
        card = strand_card(f"HairCard{tile}_{lat:.2f}_{lon:.0f}", pts, widths, (u0, u0 + 1.0 / 5.0))
        _assign_single_material(card, "Hair")
        return card

    idx = 0
    # crown: short, swept back over the top, radiating from the part
    for lon in (-95, -65, -40, -20, -6, 6, 20, 40, 65, 95):
        for lat in (0.03, 0.14):
            idx += 1
            direction = Vector((-0.35, math.copysign(0.25, lon or 1), -0.55)).normalized()
            parts.append(add_card(
                lat, lon, direction, 0.11 + 0.02 * (idx % 3),
                0.0065, 0.0018, 0.012 * math.copysign(1, lon or 1), idx % 4,
            ))

    # temple/face-framing cards, medium length sweeping past the jaw
    for side, sgn in ((0, 1.0), (1, -1.0)):
        for i, lat in enumerate((0.05, 0.14, 0.24, 0.34)):
            idx += 1
            lon = sgn * (78 + 5 * i)
            direction = Vector((0.12, sgn * -0.10, -0.92)).normalized()
            parts.append(add_card(
                lat, lon, direction, 0.14 + 0.015 * i,
                0.0072, 0.0021, sgn * 0.006, idx % 4,
            ))

    # long back cascade: three depth layers falling past the shoulders to
    # roughly mid-back.  Cards stay thin (individual strand definition
    # needs gaps, not width), so volume comes from CARD COUNT/density
    # instead -- the standard mesh-hair fix for "sparse" vs "solid slab".
    # Jittered length/angle so the silhouette reads as separated locks.
    LON_STEPS = (-88, -77, -66, -55, -46, -37, -28, -20, -12, -6, 0,
                 6, 12, 20, 28, 37, 46, 55, 66, 77, 88)
    for layer, (z_bias, len_base) in enumerate(((0.0, 0.46), (-0.010, 0.41), (-0.020, 0.36))):
        for i, lon in enumerate(LON_STEPS):
            if (i + layer) % 2:
                continue  # stagger: each layer covers half the angles
            idx += 1
            lat = 0.40 + layer * 0.075
            jitter = ((idx * 37) % 100) / 100.0
            length = len_base + 0.10 * jitter
            direction = Vector((-0.10 + z_bias, math.copysign(0.06, lon or 1) * 0.4, -0.98)).normalized()
            parts.append(add_card(
                lat, lon, direction, length,
                0.0090, 0.0026, math.copysign(0.018, lon or 1) * (0.5 + jitter),
                idx % 4, segs=5,
            ))

    # sideburns: fuller face-framing locks reaching below the jaw
    for side, sgn in (("L", 1.0), ("R", -1.0)):
        pts = [
            (Vector((0.036, sgn * 0.0740, 1.775)), 0.0135),
            (Vector((0.051, sgn * 0.0790, 1.720)), 0.0120),
            (Vector((0.060, sgn * 0.0745, 1.665)), 0.0095),
            (Vector((0.064, sgn * 0.0650, 1.612)), 0.0050),
        ]
        burn = curve_tube(f"HairSideburn{side}", pts)
        for v in burn.data.vertices:  # flatten against the cheek
            v.co.y -= sgn * max(0.0, (abs(v.co.y) - 0.068)) * 0.45
        _assign_single_material(burn, "Hair")
        parts.append(burn)

    hair = _join(parts, "GanondorfHair")

    # the scalp shell inherited the body's groups (mHead, mNeck, HEAD,
    # NECK, mFaceForehead...); clear them, then grade weights by height:
    # crown pure mHead -> nape blends mNeck -> lowest locks pick up a
    # little mChest so the long mane follows head/neck naturally
    _clear_groups(hair)
    vg_head = hair.vertex_groups.new(name="mHead")
    vg_neck = hair.vertex_groups.new(name="mNeck")
    vg_chest = hair.vertex_groups.new(name="mChest")
    for v in hair.data.vertices:
        z = v.co.z
        wn = min(0.45, max(0.0, (1.70 - z) * 2.2))
        wc = min(0.30, max(0.0, (1.48 - z) * 1.2))
        wh = 1.0 - wn - wc
        vg_head.add([v.index], wh, "REPLACE")
        if wn > 0.0:
            vg_neck.add([v.index], wn, "REPLACE")
        if wc > 0.0:
            vg_chest.add([v.index], wc, "REPLACE")
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
    _assign_slots(band, ("Gold", "Gem"), "Gold")
    parts.append(band)

    jewel = add_uv_sphere("CircletJewel", Vector((0.1225, 0.0, 1.788)), 0.0135, squash=1.25)
    _assign_slots(jewel, ("Gold", "Gem"), "Gem")
    parts.append(jewel)

    frame = add_torus(
        "CircletFrame", Vector((0.116, 0.0, 1.788)), 0.0152, 0.0038,
        rot=Matrix.Rotation(math.radians(90), 4, "Y"),
    )
    _assign_slots(frame, ("Gold", "Gem"), "Gold")
    parts.append(frame)

    obj = _join(parts, "GanondorfCirclet")
    _weight_all(obj, {"mHead": 1.0})
    return obj


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
    _assign_slots(collar, ("Gold", "Gem"), "Gold")
    parts.append(collar)

    # hanging plates, standing clear of the pecs
    for i, y in enumerate((-0.062, 0.0, 0.062)):
        cx = 0.152 - abs(y) * 0.45
        cz = 1.468 - (0.020 if y == 0.0 else 0.0)
        plate = add_uv_sphere(f"NecklacePlate{i}", Vector((cx, y, cz)), 0.030, squash=1.4)
        for v in plate.data.vertices:  # flatten into a plate
            v.co.x = (v.co.x - cx) * 0.28 + cx
        _assign_slots(plate, ("Gold", "Gem"), "Gold")
        parts.append(plate)

    gem = add_uv_sphere("NecklaceGem", Vector((0.168, 0.0, 1.446)), 0.015, squash=1.3)
    _assign_slots(gem, ("Gold", "Gem"), "Gem")
    parts.append(gem)

    obj = _join(parts, "GanondorfNecklace")
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
    _assign_slots(sheath, ("Sheath", "Gold", "Gem"), "Sheath")
    parts.append(sheath)

    # hilt: grip + guard + pommel
    grip = curve_tube(
        "SwordGrip",
        [(Vector((0.0, -0.42, 0.0)), 0.013), (Vector((0.0, -0.19, 0.0)), 0.015)],
    )
    _assign_slots(grip, ("Sheath", "Gold", "Gem"), "Gold")
    parts.append(grip)
    guard = add_torus(
        "SwordGuard", Vector((0.0, -0.175, 0.0)), 0.034, 0.011,
        rot=Matrix.Rotation(math.radians(90), 4, "X"),
    )
    for v in guard.data.vertices:
        v.co.x *= 0.5
    _assign_slots(guard, ("Sheath", "Gold", "Gem"), "Gold")
    parts.append(guard)
    pommel = add_uv_sphere("SwordPommel", Vector((0.0, -0.435, 0.0)), 0.020)
    _assign_slots(pommel, ("Sheath", "Gold", "Gem"), "Gem")
    parts.append(pommel)

    obj = _join(parts, "GanondorfSword")
    return obj
