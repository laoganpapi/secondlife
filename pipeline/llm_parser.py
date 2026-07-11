"""Parser for Linden Lab binary avatar mesh files (.llm).

Format reverse-engineered directly from the official viewer source
(indra/llappearance/llpolymesh.cpp / llpolymorph.cpp):

    char   header[128]        -- starts with "Linden Binary Mesh 1.0"
    U8     hasWeights
    U8     hasDetailTexCoords
    F32[3] position
    F32[3] rotationAngles (degrees)
    U8     rotationOrder
    F32[3] scale
    U16    numVertices
    F32[3] baseCoords    * numVertices
    F32[3] baseNormals   * numVertices
    F32[3] baseBinormals * numVertices
    F32[2] texCoords     * numVertices
    F32[2] detailTexCoords * numVertices   (if hasDetailTexCoords)
    F32    weights       * numVertices     (if hasWeights)
    U16    numFaces
    U16[3] faces * numFaces
    if hasWeights:
        U16      numSkinJoints
        char[64] jointName * numSkinJoints
    morphs, repeated until name == "End Morphs":
        char[64] morphName
        S32      numMorphVertices
        per vertex: U32 index, F32[3] coord, F32[3] normal,
                    F32[3] binormal, F32[2] texCoord
    S32 numRemaps
    (S32 src, S32 dst) * numRemaps

Classic per-vertex weight encoding: for weight value w, the vertex is
skinned between skin-joint chain index floor(w) and floor(w)+1 with
blend fraction w - floor(w).  The chain is mesh-specific (mJointNames).

All values little-endian.  Pure python + struct; no external deps, so it
runs both under system python and inside Blender's bundled interpreter.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

HEADER_BINARY = b"Linden Binary Mesh 1.0"


@dataclass
class Morph:
    name: str
    indices: list[int] = field(default_factory=list)
    coords: list[tuple[float, float, float]] = field(default_factory=list)
    normals: list[tuple[float, float, float]] = field(default_factory=list)
    binormals: list[tuple[float, float, float]] = field(default_factory=list)
    texcoords: list[tuple[float, float]] = field(default_factory=list)


@dataclass
class LLMesh:
    name: str
    has_weights: bool
    position: tuple[float, float, float]
    rotation_angles: tuple[float, float, float]
    rotation_order: int
    scale: tuple[float, float, float]
    coords: list[tuple[float, float, float]]
    normals: list[tuple[float, float, float]]
    binormals: list[tuple[float, float, float]]
    texcoords: list[tuple[float, float]]
    detail_texcoords: list[tuple[float, float]]
    weights: list[float]
    faces: list[tuple[int, int, int]]
    joint_names: list[str]
    morphs: dict[str, Morph]
    remaps: dict[int, int]

    @property
    def num_vertices(self) -> int:
        return len(self.coords)

    @property
    def num_faces(self) -> int:
        return len(self.faces)

    def expanded_weights(self) -> list[tuple[str, float, str, float]]:
        """Decode classic weights -> [(jointA, wA, jointB, wB)] per vertex."""
        out = []
        n = len(self.joint_names)
        for w in self.weights:
            i = int(w)
            f = w - i
            i = max(0, min(i, n - 1))
            j = min(i + 1, n - 1)
            out.append((self.joint_names[i], 1.0 - f, self.joint_names[j], f))
        return out


def _read(fp, fmt):
    size = struct.calcsize(fmt)
    data = fp.read(size)
    if len(data) != size:
        raise EOFError(f"short read wanting {fmt}")
    return struct.unpack("<" + fmt, data)


def _read_cstr(fp, size):
    raw = fp.read(size)
    if len(raw) != size:
        raise EOFError("short read on string")
    return raw.split(b"\0", 1)[0].decode("ascii", "replace")


def parse_llm(path: str) -> LLMesh:
    with open(path, "rb") as fp:
        header = fp.read(128)
        if not header.startswith(HEADER_BINARY):
            raise ValueError(f"{path}: not a Linden Binary Mesh")
        fp.seek(24)  # data begins right after the 24-byte header string

        has_weights = _read(fp, "B")[0] != 0
        has_detail = _read(fp, "B")[0] != 0
        position = _read(fp, "3f")
        rot_angles = _read(fp, "3f")
        rot_order = _read(fp, "B")[0]
        scale = _read(fp, "3f")
        (num_vertices,) = _read(fp, "H")

        def vec3s():
            flat = _read(fp, f"{num_vertices * 3}f")
            return [tuple(flat[i : i + 3]) for i in range(0, len(flat), 3)]

        def vec2s():
            flat = _read(fp, f"{num_vertices * 2}f")
            return [tuple(flat[i : i + 2]) for i in range(0, len(flat), 2)]

        coords = vec3s()
        normals = vec3s()
        binormals = vec3s()
        texcoords = vec2s()
        detail_texcoords = vec2s() if has_detail else []
        weights = list(_read(fp, f"{num_vertices}f")) if has_weights else []

        (num_faces,) = _read(fp, "H")
        flat = _read(fp, f"{num_faces * 3}H")
        faces = [tuple(flat[i : i + 3]) for i in range(0, len(flat), 3)]

        joint_names = []
        if has_weights:
            (num_skin_joints,) = _read(fp, "H")
            for _ in range(num_skin_joints):
                joint_names.append(_read_cstr(fp, 64))

        morphs: dict[str, Morph] = {}
        while True:
            name = _read_cstr(fp, 64)
            if name == "End Morphs":
                break
            (n,) = _read(fp, "i")
            m = Morph(name)
            for _ in range(n):
                (idx,) = _read(fp, "I")
                m.indices.append(idx)
                m.coords.append(_read(fp, "3f"))
                m.normals.append(_read(fp, "3f"))
                m.binormals.append(_read(fp, "3f"))
                m.texcoords.append(_read(fp, "2f"))
            morphs[name] = m

        remaps = {}
        try:
            (num_remaps,) = _read(fp, "i")
            for _ in range(num_remaps):
                src, dst = _read(fp, "2i")
                remaps[src] = dst
        except EOFError:
            pass

    import os

    return LLMesh(
        name=os.path.splitext(os.path.basename(path))[0],
        has_weights=has_weights,
        position=position,
        rotation_angles=rot_angles,
        rotation_order=rot_order,
        scale=scale,
        coords=coords,
        normals=normals,
        binormals=binormals,
        texcoords=texcoords,
        detail_texcoords=detail_texcoords,
        weights=weights,
        faces=faces,
        joint_names=joint_names,
        morphs=morphs,
        remaps=remaps,
    )


if __name__ == "__main__":
    import sys

    for p in sys.argv[1:]:
        m = parse_llm(p)
        print(
            f"{m.name}: {m.num_vertices} verts, {m.num_faces} tris, "
            f"joints={m.joint_names}, morphs={len(m.morphs)}"
        )
