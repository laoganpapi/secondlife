"""Rig verification: load body.blend, strike poses, render.

Checks that the classic-weight decode, fitted volumes, Bento fingers and
face weights deform sanely: elbow/shoulder/knee bends, fist, jaw open.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402
from mathutils import Euler  # noqa: E402

from slkit import bl_utils  # noqa: E402


def rot(arm, bone, xyz_deg):
    pb = arm.pose.bones[bone]
    pb.rotation_mode = "XYZ"
    pb.rotation_euler = Euler([math.radians(a) for a in xyz_deg], "XYZ")


def main():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    args = dict(zip(argv[::2], argv[1::2]))
    out = args.get("--out", "output")

    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(f"{out}/blend/body.blend"))
    arm = bpy.data.objects["GanondorfRig"]

    # Pose A: arms down-ish, elbows bent, knee raised, fist, jaw open.
    # Bone axes: bones point +Y (world), avatar faces +X.
    rot(arm, "mShoulderLeft", (0, 0, -60))   # arm down
    rot(arm, "mElbowLeft", (0, 0, -45))      # elbow bend forward
    rot(arm, "mShoulderRight", (0, 0, 60))
    rot(arm, "mElbowRight", (60, 0, 0))
    rot(arm, "mHipLeft", (0, -45, 0))
    rot(arm, "mKneeLeft", (0, 60, 0))
    rot(arm, "mFaceJaw", (0, 25, 0))
    # left fist
    for f in ("Index", "Middle", "Ring", "Pinky"):
        for i in (1, 2, 3):
            rot(arm, f"mHand{f}{i}Left", (0, 0, 55 if f != "Thumb" else 30))
    for i in (1, 2, 3):
        rot(arm, f"mHandThumb{i}Left", (-30, 0, 20))
    # head turn
    rot(arm, "mNeck", (0, 0, 20))

    p = f"{out}/preview"
    bl_utils.render_preview(f"{p}/pose_front.png", (3.2, 0.4, 1.1), (0.0, 0.0, 1.0))
    bl_utils.render_preview(f"{p}/pose_arm_closeup.png", (1.4, 1.0, 1.3), (0.0, 0.35, 1.35), resolution=(900, 900))
    bl_utils.render_preview(f"{p}/pose_hand_closeup.png", (0.8, 0.9, 1.2), (-0.02, 0.55, 1.35), resolution=(900, 900))
    bl_utils.render_preview(f"{p}/pose_face.png", (0.75, 0.25, 1.8), (0.0, -0.02, 1.72), resolution=(900, 900))
    print("[pose] done")


main()
