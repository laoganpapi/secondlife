"""Stage 2: build every outfit attachment on top of body.blend.

Run:  blender --background --factory-startup --python pipeline/build_outfit.py -- --out output
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from slkit import adornments, bl_utils, outfit  # noqa: E402
from slkit.skeleton import load_skeleton  # noqa: E402


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    args = dict(zip(argv[::2], argv[1::2]))
    out = args.get("--out", "output")
    resources = args.get("--resources", "assets/sl_resources")

    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(f"{out}/blend/body.blend"))
    sk = load_skeleton(f"{resources}/avatar_skeleton.xml")
    body = bpy.data.objects["GanondorfBody"]
    arm = bpy.data.objects["GanondorfRig"]

    items = []
    items.append(outfit.build_loincloth(body, sk))
    items += outfit.build_bracers(body, sk)
    items += outfit.build_anklets(body, sk)
    items.append(adornments.build_hair(body, sk))
    items.append(adornments.build_circlet(body, sk))
    items.append(adornments.build_earrings(body, sk))
    items.append(adornments.build_necklace(body, sk))

    for obj in items:
        outfit.bind_to_rig(obj, arm)
        print(f"[outfit] {obj.name}: {len(obj.data.polygons)} polys, "
              f"{len(obj.data.materials)} materials")

    sword = adornments.build_sword(body, sk)
    print(f"[outfit] {sword.name}: {len(sword.data.polygons)} polys (static)")

    # park the sword against the left hip for preview renders only
    # (hilt-up sheathed carry tucked through the sash at the left hip;
    # local +Y is the blade axis, so -90deg about X points it up)
    import math as _m
    sword.location = (-0.075, 0.165, 1.02)
    sword.rotation_euler = (_m.radians(-78), 0.0, _m.radians(8))

    # viewport display colors: preview the palette + identify objects
    palette = {
        "BAKED_HEAD": (0.45, 0.48, 0.33, 1), "BAKED_UPPER": (0.45, 0.48, 0.33, 1),
        "BAKED_LOWER": (0.45, 0.48, 0.33, 1), "BAKED_EYES": (0.85, 0.55, 0.15, 1),
        "LASHES": (0.08, 0.05, 0.04, 1),
        "Hair": (0.48, 0.08, 0.05, 1), "HairGold": (0.85, 0.65, 0.20, 1),
        "Gold": (0.85, 0.65, 0.20, 1), "Gem": (0.60, 0.06, 0.10, 1),
        "Loincloth": (0.30, 0.20, 0.10, 1),
        "Bracer": (0.38, 0.27, 0.13, 1), "LegWrap": (0.32, 0.30, 0.24, 1),
        "Sheath": (0.14, 0.11, 0.09, 1),
    }
    for name, col in palette.items():
        mat = bpy.data.materials.get(name)
        if mat:
            mat.diffuse_color = col

    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(f"{out}/blend/outfit.blend"))

    p = f"{out}/preview"
    bl_utils.render_preview(f"{p}/outfit_front.png", (3.2, 0.0, 1.1), (0.0, 0.0, 1.0), ortho_scale=2.3, shading="material")
    bl_utils.render_preview(f"{p}/outfit_three_quarter.png", (2.4, 1.8, 1.3), (0.0, 0.0, 1.0), shading="material")
    bl_utils.render_preview(f"{p}/outfit_back.png", (-3.2, 0.0, 1.1), (0.0, 0.0, 1.0), ortho_scale=2.3, shading="material")
    bl_utils.render_preview(f"{p}/outfit_head.png", (0.72, 0.22, 1.82), (0.0, 0.0, 1.76), resolution=(900, 900), shading="material")
    print("[outfit] done")


main()
