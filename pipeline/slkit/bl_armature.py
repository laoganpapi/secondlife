"""Build the SL Bento armature inside Blender from avatar_skeleton.xml.

Design notes:
- We work directly in SL avatar space: +X forward, +Y left, +Z up, meters.
- Every bone (including collision volumes) gets its rest HEAD at the
  accumulated `pivot` position and a short tail so that its rest matrix is
  a pure translation (bone axis +Y, roll 0).  SL's skeleton rest pose has
  zero rotation on all mBones, so pure-translation rest matrices produce
  inverse bind matrices that match the SL skeleton exactly.
- Collision volumes carry non-zero rest rotations in the XML; those are
  baked into the edit-bone matrix so exported inverse bind matrices agree
  with the viewer's volume rest transforms.
- Bones are exported by the Collada exporter with open_sim=True, which is
  the documented SL-compatible path.
"""

from __future__ import annotations

import math

import bpy
from mathutils import Euler, Matrix, Vector

BONE_LEN = 0.03


def build_armature(sk, name: str = "Armature") -> bpy.types.Object:
    arm_data = bpy.data.armatures.new(name)
    arm_obj = bpy.data.objects.new(name, arm_data)
    bpy.context.scene.collection.objects.link(arm_obj)
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="EDIT")

    world_rot: dict[str, Euler] = {}

    for jname in sk.order:
        j = sk.joints[jname]
        eb = arm_data.edit_bones.new(jname)
        # viewer builds the skeleton from `pos` (llavatarappearance.cpp:
        # setPosition(mPos)); `pivot` is only the legacy skin offset.
        head = Vector(sk.world_pos(jname))

        # accumulated rest rotation (only volumes have any)
        rot = Euler(
            (
                math.radians(j.rot[0]),
                math.radians(j.rot[1]),
                math.radians(j.rot[2]),
            ),
            "XYZ",
        )
        world_rot[jname] = rot

        mat = Matrix.Translation(head) @ rot.to_matrix().to_4x4()
        eb.head = head
        eb.tail = head + Vector((0.0, BONE_LEN, 0.0))
        eb.matrix = mat
        eb.length = BONE_LEN

        if j.parent:
            eb.parent = arm_data.edit_bones[j.parent]
            eb.use_connect = False

        eb.use_deform = True

    bpy.ops.object.mode_set(mode="OBJECT")
    return arm_obj


def bind_mesh(obj: bpy.types.Object, arm_obj: bpy.types.Object) -> None:
    """Attach mesh to armature with an armature modifier (no auto weights)."""
    mod = obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm_obj
    mod.use_vertex_groups = True
    obj.parent = arm_obj
