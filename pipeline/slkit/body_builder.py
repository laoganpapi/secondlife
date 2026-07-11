"""Assemble the rigged Ganondorf body from the classic avatar meshes.

Stages:
  1. Bento armature from avatar_skeleton.xml (pos values, identity rest).
  2. Import head/upper/lower .llm meshes with UVs, weights and morph keys.
  3. Bake the Ganondorf morph recipe, then procedural sculpting.
  4. Join into one Body object, weld the neck/waist seam rings
     (cross-part vertex pairs only) so subdivision keeps them sealed.
  5. Fitted-mesh volume weights, Bento finger + face weights, cleanup.
  6. One level of subdivision, smooth shading.
  7. Eyes (rigged to eye bones) and eyelashes as separate linked meshes.

Materials are named for their Bakes-on-Mesh channel so the upload guide
can map them 1:1 (BAKED_HEAD / BAKED_UPPER / BAKED_LOWER / BAKED_EYES).
"""

from __future__ import annotations

import bpy
import bmesh
from mathutils import Vector, kdtree

from . import bl_armature, bl_llm, rigging, shaping
from .llm_parser_bridge import parse_llm
from .skeleton import load_skeleton


def _assign_material(obj, name: str) -> None:
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def _find_seam_pairs(raw_coords_a, raw_coords_b, dist=1e-5):
    """Exact-coincident vertex pairs between two parts on RAW (pre-morph)
    coordinates.  The classic meshes were authored with identical rings at
    the neck and waist seams; morph baking may pull the two sides apart,
    so pairing must happen on pristine data."""
    kd = kdtree.KDTree(len(raw_coords_b))
    for i, co in enumerate(raw_coords_b):
        kd.insert(Vector(co), i)
    kd.balance()
    pairs = []
    for i, co in enumerate(raw_coords_a):
        hit = kd.find_range(Vector(co), dist)
        if hit:
            pairs.append((i, hit[0][1]))
    return pairs


def _snap_and_weld_pairs(obj, pairs_with_offsets) -> int:
    """Snap each cross-part seam pair to its midpoint, then weld."""
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    targetmap = {}
    for ia, ib in pairs_with_offsets:
        va, vb = bm.verts[ia], bm.verts[ib]
        mid = (va.co + vb.co) / 2.0
        va.co = mid
        vb.co = mid
        targetmap[vb] = va
    n = len(targetmap)
    if targetmap:
        bmesh.ops.weld_verts(bm, targetmap=targetmap)
    bm.to_mesh(me)
    bm.free()
    me.update()
    return n


def _weld_seam_duplicates(obj, dist=1e-5, normal_dot=0.6) -> int:
    """Weld vertices duplicated along UV seams so subdivision cannot crack
    the surface open.  Pairs whose normals disagree (touching lips, eyelid
    contact rims) are intentionally split surfaces and are left alone —
    per-loop UVs survive the weld, so texture seams stay intact."""
    me = obj.data
    me.calc_normals()
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()

    kd = kdtree.KDTree(len(bm.verts))
    for v in bm.verts:
        kd.insert(v.co, v.index)
    kd.balance()

    targetmap = {}
    for v in bm.verts:
        if v in targetmap:
            continue  # already merged into another vertex
        for co, idx, d in kd.find_range(v.co, dist):
            if idx <= v.index:
                continue
            w = bm.verts[idx]
            if w in targetmap:
                continue
            if v.normal.dot(w.normal) > normal_dot:
                targetmap[w] = v
    n = len(targetmap)
    if targetmap:
        bmesh.ops.weld_verts(bm, targetmap=targetmap)
    bm.to_mesh(me)
    bm.free()
    me.update()
    return n


def _cap_crown_hole(obj, z_min=1.782) -> int:
    """The classic head mesh ships with an open scalp (covered by the system
    hair mesh).  Close it with a smooth UV-mapped fan dome so the body is
    watertight even without the hair attachment."""
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    uv_layer = bm.loops.layers.uv.active

    boundary_edges = [e for e in bm.edges if e.is_boundary]
    if not boundary_edges:
        bm.free()
        return 0

    # group boundary edges into connected components and pick the one whose
    # centroid sits highest: that is the scalp opening (eye sockets and the
    # mouth slit sit lower on the head).
    adj: dict = {}
    for e in boundary_edges:
        a, b = e.verts
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)

    seen = set()
    components = []
    for v0 in adj:
        if v0 in seen:
            continue
        comp = []
        stack = [v0]
        seen.add(v0)
        while stack:
            v = stack.pop()
            comp.append(v)
            for n in adj[v]:
                if n not in seen:
                    seen.add(n)
                    stack.append(n)
        components.append(comp)

    def centroid_z(c):
        return sum(v.co.z for v in c) / len(c)

    comp = max(components, key=centroid_z)
    if centroid_z(comp) < z_min:
        # nothing above the eye line: scalp is already watertight
        bm.free()
        return 0
    comp_set = set(comp)
    if any(len([n for n in adj[v] if n in comp_set]) != 2 for v in comp):
        bm.free()
        return 0

    start = comp[0]
    loop = [start]
    prev = None
    while True:
        nxts = [v for v in adj[loop[-1]] if v in comp_set and v is not prev]
        if not nxts:
            break
        prev = loop[-1]
        loop.append(nxts[0])
        if loop[-1] is start:
            loop.pop()
            break

    centroid = Vector((0, 0, 0))
    for v in loop:
        centroid += v.co
    centroid /= len(loop)
    centroid.z += 0.012  # dome the cap

    # ring UV centroid from existing loops
    uv_of = {}
    for v in loop:
        for l in v.link_loops:
            uv_of[v] = Vector(l[uv_layer].uv)
            break
    uv_c = Vector((0, 0))
    for v in loop:
        uv_c += uv_of.get(v, Vector((0, 0)))
    uv_c /= len(loop)

    center = bm.verts.new(centroid)
    n_faces = 0
    for i in range(len(loop)):
        a, b = loop[i], loop[(i + 1) % len(loop)]
        try:
            f = bm.faces.new((a, b, center))
        except ValueError:
            continue
        f.smooth = True
        # head material is slot 0 (first assigned part)
        f.material_index = 0
        for l in f.loops:
            if l.vert is center:
                l[uv_layer].uv = uv_c
            else:
                l[uv_layer].uv = uv_of.get(l.vert, uv_c)
        n_faces += 1

    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    me.update()

    # weight the new center vert like the ring (mHead)
    vg = obj.vertex_groups.get("mHead")
    if vg:
        vg.add([len(me.vertices) - 1], 1.0, "REPLACE")
    return n_faces


def build_body(resources_dir: str):
    sk = load_skeleton(f"{resources_dir}/avatar_skeleton.xml")
    arm = bl_armature.build_armature(sk, "GanondorfRig")

    # --- import + shape the three body parts -------------------------------
    recipes = {
        "avatar_head": shaping.HEAD_MORPHS,
        "avatar_upper_body": shaping.UPPER_MORPHS,
        "avatar_lower_body": shaping.LOWER_MORPHS,
    }
    parts = []
    raw_coords = {}
    for llm_name, recipe in recipes.items():
        mesh = parse_llm(f"{resources_dir}/{llm_name}.llm")
        raw_coords[llm_name] = mesh.coords
        obj = bl_llm.import_llm(mesh, sk, name=llm_name)
        bl_llm.bake_shape_keys(obj, recipe)
        parts.append(obj)

    # pair seam rings on raw coordinates before any morphing
    neck_pairs = _find_seam_pairs(
        raw_coords["avatar_head"], raw_coords["avatar_upper_body"]
    )
    waist_pairs = _find_seam_pairs(
        raw_coords["avatar_lower_body"], raw_coords["avatar_upper_body"]
    )

    head, upper, lower = parts
    shaping.sculpt_head(head)
    _assign_material(head, "BAKED_HEAD")
    _assign_material(upper, "BAKED_UPPER")
    _assign_material(lower, "BAKED_LOWER")

    # --- join and weld seams -------------------------------------------------
    ranges = []
    offset = 0
    for obj in parts:
        n = len(obj.data.vertices)
        ranges.append((offset, offset + n))
        offset += n

    from .bl_utils import select_only

    select_only(parts)
    bpy.ops.object.join()
    body = bpy.context.view_layer.objects.active
    body.name = "GanondorfBody"

    # join order == parts order: head, upper, lower
    off_head, off_upper, off_lower = (r[0] for r in ranges)
    seam_pairs = [(a + off_head, b + off_upper) for a, b in neck_pairs] + [
        (a + off_lower, b + off_upper) for a, b in waist_pairs
    ]
    welded = _snap_and_weld_pairs(body, seam_pairs)
    print(f"[body] snapped+welded {welded} seam vertex pairs "
          f"(neck {len(neck_pairs)}, waist {len(waist_pairs)})")
    dups = _weld_seam_duplicates(body)
    print(f"[body] welded {dups} UV-seam duplicate vertices")
    capped = _cap_crown_hole(body)
    print(f"[body] crown capped with {capped} faces")

    shaping.sculpt_body(body)

    # --- rigging quality passes ----------------------------------------------
    rigging.apply_fitted_volumes(body, sk)
    rigging.apply_bento_fingers(body, sk, "Left")
    rigging.apply_bento_fingers(body, sk, "Right")
    rigging.apply_bento_face(body, sk)
    rigging.cleanup_weights(body)

    # --- subdivision ----------------------------------------------------------
    select_only(body)
    mod = body.modifiers.new("Subd", "SUBSURF")
    mod.levels = 1
    mod.render_levels = 1
    mod.use_creases = False
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.ops.object.shade_smooth()
    rigging.cleanup_weights(body)  # re-limit after interpolation

    # SL allows max 21844 tris per material; the subdivided upper body
    # exceeds it, so the arms/hands move to a second slot that in-world is
    # simply set to the same BAKED_UPPER bake channel (disjoint UV regions,
    # zero visual difference).
    mat2 = bpy.data.materials.get("BAKED_UPPER2") or bpy.data.materials.new("BAKED_UPPER2")
    body.data.materials.append(mat2)
    slot_names = [m.name for m in body.data.materials]
    upper_i = slot_names.index("BAKED_UPPER")
    upper2_i = slot_names.index("BAKED_UPPER2")
    moved = 0
    for p in body.data.polygons:
        if p.material_index == upper_i and abs(p.center.y) > 0.30:
            p.material_index = upper2_i
            moved += 1
    print(f"[body] moved {moved} arm/hand tris to BAKED_UPPER2 slot")

    bl_armature.bind_mesh(body, arm)

    # --- eyes ------------------------------------------------------------------
    eye_mesh = parse_llm(f"{resources_dir}/avatar_eye.llm")
    eyes = []
    for side in ("Left", "Right"):
        obj = bl_llm.import_llm(eye_mesh, sk, name=f"GanondorfEye{side}", with_weights=False)
        bl_llm.bake_shape_keys(obj, {})
        pivot = Vector(sk.world_pos(f"mEye{side}"))
        for v in obj.data.vertices:
            v.co += pivot
        vg = obj.vertex_groups.new(name=f"mEye{side}")
        vg.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
        _assign_material(obj, "BAKED_EYES")
        select_only(obj)
        bpy.ops.object.shade_smooth()
        bl_armature.bind_mesh(obj, arm)
        eyes.append(obj)

    # --- eyelashes ---------------------------------------------------------------
    lash_mesh = parse_llm(f"{resources_dir}/avatar_eyelashes.llm")
    lashes = bl_llm.import_llm(lash_mesh, sk, name="GanondorfLashes")
    bl_llm.bake_shape_keys(lashes, shaping.HEAD_MORPHS)
    _assign_material(lashes, "LASHES")
    bl_armature.bind_mesh(lashes, arm)

    return sk, arm, body, eyes, lashes
