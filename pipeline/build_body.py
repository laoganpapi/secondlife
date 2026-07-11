"""Stage 1: build the rigged Ganondorf body and save body.blend + previews.

Run:  blender --background --factory-startup --python pipeline/build_body.py -- \
        --resources assets/sl_resources --out output
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from slkit import bl_utils  # noqa: E402
from slkit.body_builder import build_body  # noqa: E402


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    args = dict(zip(argv[::2], argv[1::2]))
    resources = args.get("--resources", "assets/sl_resources")
    out = args.get("--out", "output")

    bl_utils.reset_scene()
    sk, arm, body, eyes, lashes = build_body(resources)

    print(f"[body] verts={len(body.data.vertices)} tris~={len(body.data.polygons)}")
    print(f"[body] vertex groups: {len(body.vertex_groups)}")

    os.makedirs(f"{out}/blend", exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(f"{out}/blend/body.blend"))

    p = f"{out}/preview"
    bl_utils.render_preview(f"{p}/body_front.png", (3.2, 0.0, 1.1), (0.0, 0.0, 1.0), ortho_scale=2.3)
    bl_utils.render_preview(f"{p}/body_three_quarter.png", (2.4, 1.8, 1.3), (0.0, 0.0, 1.0))
    bl_utils.render_preview(f"{p}/body_back.png", (-3.2, 0.0, 1.1), (0.0, 0.0, 1.0), ortho_scale=2.3)
    bl_utils.render_preview(f"{p}/face_closeup.png", (0.72, 0.18, 1.78), (0.02, 0.0, 1.74), resolution=(900, 900))
    bl_utils.render_preview(f"{p}/hand_closeup.png", (0.5, 0.75, 1.85), (-0.02, 0.72, 1.53), resolution=(900, 900))
    print("[body] done")


main()
