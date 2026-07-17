"""Stage 4 (Blender): export every attachment as SL-ready Collada.

Uses the documented SL-compatible exporter settings (the "SL + OpenSim
Rigged" preset): open_sim=True is the critical flag for bone-orientation
compatibility; deform_bones_only strips nothing here (all bones deform)
but is part of the blessed preset.

Per item we export:
  <name>.dae            rigged high LOD
  <name>_LOD2.dae       medium LOD (decimated, same materials, node
  <name>_LOD1.dae       low LOD    names suffixed per the uploader's
  <name>_LOD0.dae       lowest LOD name-matching convention)
plus one shared physics file with a node named default_physics_shape.

Run: blender --background --factory-startup --python pipeline/export_dae.py -- --out output
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from slkit.bl_utils import select_only  # noqa: E402
from slkit.rigging import cleanup_weights  # noqa: E402

# attachment -> object names (multi-object DAEs upload as one linkset)
ITEMS = {
    "ganondorf_body": ["GanondorfBody", "GanondorfEyeLeft", "GanondorfEyeRight", "GanondorfLashes"],
    "ganondorf_loincloth": ["GanondorfLoincloth"],
    "ganondorf_bracer_left": ["GanondorfBracerLeft"],
    "ganondorf_bracer_right": ["GanondorfBracerRight"],
    "ganondorf_anklet_left": ["GanondorfAnkletLeft"],
    "ganondorf_anklet_right": ["GanondorfAnkletRight"],
    "ganondorf_hair": ["GanondorfHair"],
    "ganondorf_circlet": ["GanondorfCirclet"],
    "ganondorf_earrings": ["GanondorfEarrings"],
    "ganondorf_necklace": ["GanondorfNecklace"],
}
STATIC_ITEMS = {"ganondorf_sword": ["GanondorfSword"]}

LODS = [("_LOD2", 0.45), ("_LOD1", 0.20), ("_LOD0", 0.08)]


def export_collada(filepath: str, rigged: bool) -> None:
    bpy.ops.wm.collada_export(
        filepath=filepath,
        apply_modifiers=True,
        export_mesh_type_selection="view",
        selected=True,
        include_children=False,
        include_armatures=rigged,
        include_shapekeys=False,
        deform_bones_only=True,
        open_sim=True,
        triangulate=True,
        use_object_instantiation=False,
        apply_global_orientation=False,
        export_object_transformation_type_selection="matrix",
        keep_bind_info=False,
        limit_precision=False,
    )


def duplicate_decimated(objs, suffix: str, ratio: float):
    dups = []
    for src in objs:
        dup = src.copy()
        dup.data = src.data.copy()
        dup.name = f"{src.name}{suffix}"
        dup.data.name = dup.name
        bpy.context.scene.collection.objects.link(dup)
        mod = dup.modifiers.new("Decimate", "DECIMATE")
        mod.ratio = ratio
        mod.use_collapse_triangulate = True
        select_only(dup)
        bpy.ops.object.modifier_apply(modifier=mod.name)
        if dup.vertex_groups:
            # collapse blends weights; SL allows max 4 influences/vertex
            cleanup_weights(dup)
        dups.append(dup)
    return dups


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    args = dict(zip(argv[::2], argv[1::2]))
    out = args.get("--out", "output")

    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(f"{out}/blend/outfit.blend"))
    dae_dir = os.path.abspath(f"{out}/dae")
    os.makedirs(dae_dir, exist_ok=True)

    arm = bpy.data.objects["GanondorfRig"]

    # the sword was parked/rotated for previews; reset to its build pose
    sword = bpy.data.objects.get("GanondorfSword")
    if sword:
        sword.location = (0, 0, 0)
        sword.rotation_euler = (0, 0, 0)

    for item, names in {**ITEMS, **STATIC_ITEMS}.items():
        rigged = item in ITEMS
        objs = [bpy.data.objects[n] for n in names]

        # high LOD
        select_only(objs + ([arm] if rigged else []))
        export_collada(f"{dae_dir}/{item}.dae", rigged)
        tris = sum(len(o.data.polygons) for o in objs)
        print(f"[export] {item}.dae ({tris} polys, rigged={rigged})")

        # lower LODs (decimated copies, name-suffixed for the uploader)
        for suffix, ratio in LODS:
            dups = duplicate_decimated(objs, suffix, ratio)
            select_only(dups + ([arm] if rigged else []))
            export_collada(f"{dae_dir}/{item}{suffix}.dae", rigged)
            for d in dups:
                bpy.data.objects.remove(d)

    # shared physics file: one simple cube named default_physics_shape
    me = bpy.data.meshes.new("default_physics_shape")
    s = 0.2
    verts = [(x, y, z) for x in (-s, s) for y in (-s, s) for z in (0.6, 1.4)]
    faces = [
        (0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1),
        (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3),
    ]
    me.from_pydata(verts, [], faces)
    me.update()
    cube = bpy.data.objects.new("default_physics_shape", me)
    bpy.context.scene.collection.objects.link(cube)
    select_only(cube)
    export_collada(f"{dae_dir}/ganondorf_physics.dae", rigged=False)
    print("[export] ganondorf_physics.dae")
    print("[export] done")


main()
