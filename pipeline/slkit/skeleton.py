"""Parse Second Life avatar_skeleton.xml (Bento v2.0) into a joint tree.

Pure python (xml.etree) so it can be used by the Blender build scripts,
the texture generator, and the DAE validator alike.

Coordinate conventions (SL avatar space): X forward, Y left, Z up, meters.
Bone `pos`/`pivot` values are offsets relative to the parent bone.
Collision volumes ("fitted mesh" bones) carry pos/rot/scale of their own.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field


@dataclass
class Joint:
    name: str
    parent: str | None
    pos: tuple[float, float, float]
    pivot: tuple[float, float, float]
    rot: tuple[float, float, float]
    scale: tuple[float, float, float]
    end: tuple[float, float, float]
    group: str
    support: str
    is_volume: bool = False
    aliases: list[str] = field(default_factory=list)
    children: list[str] = field(default_factory=list)


class Skeleton:
    def __init__(self, joints: dict[str, Joint], order: list[str]):
        self.joints = joints
        self.order = order  # depth-first document order (viewer traversal order)

    @property
    def bones(self) -> list[str]:
        return [n for n in self.order if not self.joints[n].is_volume]

    @property
    def volumes(self) -> list[str]:
        return [n for n in self.order if self.joints[n].is_volume]

    def world_pivot(self, name: str) -> tuple[float, float, float]:
        """Accumulated rest-pose pivot position from avatar origin."""
        x = y = z = 0.0
        j: str | None = name
        while j is not None:
            jt = self.joints[j]
            x += jt.pivot[0]
            y += jt.pivot[1]
            z += jt.pivot[2]
            j = jt.parent
        return (x, y, z)

    def world_pos(self, name: str) -> tuple[float, float, float]:
        """Accumulated rest-pose `pos` position from avatar origin."""
        x = y = z = 0.0
        j: str | None = name
        while j is not None:
            jt = self.joints[j]
            x += jt.pos[0]
            y += jt.pos[1]
            z += jt.pos[2]
            j = jt.parent
        return (x, y, z)

    def descendants(self, name: str) -> list[str]:
        out = []
        stack = list(self.joints[name].children)
        while stack:
            n = stack.pop(0)
            out.append(n)
            stack.extend(self.joints[n].children)
        return out


def _vec(s: str) -> tuple[float, float, float]:
    p = [float(v) for v in s.split()]
    while len(p) < 3:
        p.append(0.0)
    return (p[0], p[1], p[2])


def load_skeleton(path: str) -> Skeleton:
    tree = ET.parse(path)
    root = tree.getroot()
    joints: dict[str, Joint] = {}
    order: list[str] = []

    def walk(el: ET.Element, parent: str | None):
        name = el.get("name")
        j = Joint(
            name=name,
            parent=parent,
            pos=_vec(el.get("pos", "0 0 0")),
            pivot=_vec(el.get("pivot", el.get("pos", "0 0 0"))),
            rot=_vec(el.get("rot", "0 0 0")),
            scale=_vec(el.get("scale", "1 1 1")),
            end=_vec(el.get("end", "0 0 0.05")),
            group=el.get("group", ""),
            support=el.get("support", "base"),
            is_volume=(el.tag == "collision_volume"),
            aliases=(el.get("aliases", "").split() if el.get("aliases") else []),
        )
        joints[name] = j
        order.append(name)
        if parent is not None:
            joints[parent].children.append(name)
        for child in el:
            if child.tag in ("bone", "collision_volume"):
                walk(child, name)

    for el in root:
        if el.tag == "bone":
            walk(el, None)

    return Skeleton(joints, order)


def classic_render_joint_order(
    skeleton: Skeleton,
    mesh_joint_names: list[str],
    include_root_entry: bool = False,
) -> list[str | None]:
    """Reproduce LLViewerJointMesh::setupJoint()'s render-data array.

    The classic per-vertex float weight w skins a vertex between
    entry[floor(w)] and entry[floor(w)+1] of this array with blend
    fraction w-floor(w).  The array is built by walking the skeleton
    depth-first; each mesh skin joint appends (parentJoint, joint),
    reusing the previous entry when it already equals the parent.
    The avatar root (parent of mPelvis) is represented as None and is
    treated as static/pelvis by consumers.
    """
    entries: list[str | None] = []
    wanted = set(mesh_joint_names)
    for joint in skeleton.order:  # document order == depth-first traversal
        if skeleton.joints[joint].is_volume or joint not in wanted:
            continue
        parent = skeleton.joints[joint].parent
        if parent is None:
            # The skeleton root (mPelvis).  Empirically the shipped meshes
            # differ: avatar_upper_body's weights index an array WITHOUT
            # any root contribution, while avatar_lower_body's weights
            # need [<avatar root>, mPelvis] at the front.  The caller
            # resolves the ambiguity per mesh from max(int(weight)).
            if include_root_entry:
                entries.append(None)  # avatar root: static, acts as pelvis
                entries.append(joint)
            continue
        if not entries or entries[-1] != parent:
            entries.append(parent)
        entries.append(joint)
    return entries


def classic_entries_for_mesh(
    skeleton: Skeleton, mesh_joint_names: list[str], weights: list[float]
) -> list[str | None]:
    """Pick the entries variant whose length matches the encoded indices."""
    max_idx = max((int(w) for w in weights), default=0)
    for include_root in (False, True):
        entries = classic_render_joint_order(
            skeleton, mesh_joint_names, include_root_entry=include_root
        )
        if len(entries) == max_idx + 1:
            return entries
    # fallback: whichever is long enough, with clamping downstream
    entries = classic_render_joint_order(skeleton, mesh_joint_names, True)
    return entries


if __name__ == "__main__":
    import sys

    sk = load_skeleton(sys.argv[1] if len(sys.argv) > 1 else "assets/sl_resources/avatar_skeleton.xml")
    print(f"bones={len(sk.bones)} volumes={len(sk.volumes)}")
    for n in ("mPelvis", "mChest", "mHead", "mEyeLeft", "mWristLeft", "mHandMiddle1Left", "mFaceJaw"):
        if n in sk.joints:
            print(n, "world_pivot=", tuple(round(v, 4) for v in sk.world_pivot(n)))
    print("volumes:", ", ".join(sk.volumes))
