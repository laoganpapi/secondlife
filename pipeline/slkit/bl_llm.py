"""Import a parsed Linden .llm mesh into Blender.

Reconstructs: geometry, the SLUV texture coordinates (per-loop), the
classic skin weights (decoded exactly the way LLViewerJointMesh::setupJoint
builds its render-data array), and every morph target as a relative shape
key so appearance-slider shapes can be baked at chosen values.
"""

from __future__ import annotations

import bpy

from .skeleton import Skeleton, classic_entries_for_mesh


def import_llm(
    mesh,
    sk: Skeleton,
    name: str | None = None,
    with_morphs: bool = True,
    with_weights: bool = True,
) -> bpy.types.Object:
    name = name or mesh.name
    me = bpy.data.meshes.new(name)
    me.from_pydata([list(c) for c in mesh.coords], [], [list(f) for f in mesh.faces])
    me.update()

    # UVs: per-vertex in .llm -> per-loop in Blender.  Same GL bottom-left
    # origin convention on both sides, no flip needed.
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in range(poly.loop_start, poly.loop_start + poly.loop_total):
            vi = me.loops[li].vertex_index
            uv.data[li].uv = mesh.texcoords[vi]

    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)

    if with_weights and mesh.has_weights:
        entries = classic_entries_for_mesh(sk, mesh.joint_names, mesh.weights)
        # The Bento mSpine1-4 bones fold back on themselves between
        # mPelvis/mTorso/mChest and are rigid unless explicitly animated;
        # substituting their nearest animated ancestor is exactly
        # equivalent under standard animations and keeps the joint list
        # (and 110-joint budget) clean.
        spine_remap = {
            "mSpine1": "mPelvis",
            "mSpine2": "mPelvis",
            "mSpine3": "mTorso",
            "mSpine4": "mTorso",
        }
        entries = [spine_remap.get(e, e) if e else e for e in entries]
        groups: dict[str, object] = {}

        def group(jn: str):
            if jn not in groups:
                groups[jn] = obj.vertex_groups.new(name=jn)
            return groups[jn]

        n = len(entries)
        for vi, w in enumerate(mesh.weights):
            i = int(w)
            f = w - i
            i = max(0, min(i, n - 1))
            k = min(i + 1, n - 1)
            a = entries[i] or "mPelvis"  # avatar root behaves as pelvis
            b = entries[k] or "mPelvis"
            if a == b or f <= 0.0:
                group(a).add([vi], 1.0, "REPLACE")
            elif f >= 1.0:
                group(b).add([vi], 1.0, "REPLACE")
            else:
                group(a).add([vi], 1.0 - f, "REPLACE")
                group(b).add([vi], f, "ADD")

    if with_morphs and mesh.morphs:
        obj.shape_key_add(name="Basis", from_mix=False)
        for mname, morph in mesh.morphs.items():
            key = obj.shape_key_add(name=mname, from_mix=False)
            key.slider_min = -1.5
            key.slider_max = 1.5
            for idx, delta in zip(morph.indices, morph.coords):
                if idx < len(me.vertices):
                    base = me.vertices[idx].co
                    key.data[idx].co = (
                        base[0] + delta[0],
                        base[1] + delta[1],
                        base[2] + delta[2],
                    )

    return obj


def bake_shape_keys(obj: bpy.types.Object, values: dict[str, float]) -> None:
    """Set shape key values then collapse everything into the base mesh."""
    if not obj.data.shape_keys:
        return
    kbs = obj.data.shape_keys.key_blocks
    for k in kbs:
        if k.name == "Basis":
            continue
        k.value = values.get(k.name, 0.0)
    # bake the mix into a new key, then delete all others
    mix = obj.shape_key_add(name="__baked", from_mix=True)
    coords = [d.co.copy() for d in mix.data]
    for k in list(kbs):
        obj.shape_key_remove(k)
    for v, co in zip(obj.data.vertices, coords):
        v.co = co
    obj.data.update()
