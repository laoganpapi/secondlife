"""Stage 3a (Blender): bake AO maps + export UV/3D correspondence dumps.

For every textured object we export a JSON "uvdump": one record per
triangle loop with its UV coords and 3D positions/normals.  The texture
painter (pipeline/textures.py, plain python) rasterizes region masks from
3D predicates through these dumps -- that is how brows, lips, trim bands
etc. land exactly where the geometry is.

AO is baked in Cycles (CPU) per body material slot and per garment, and
multiplied into the diffuse by the painter for baked-in form shading
(BoM textures carry no normal channel, so shading must live in diffuse).

Run: blender --background --factory-startup --python pipeline/bake_maps.py -- --out output
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402


def uvdump(obj, path: str) -> None:
    me = obj.data
    uv = me.uv_layers.active
    recs = []
    for poly in me.polygons:
        slot = poly.material_index
        loops = list(range(poly.loop_start, poly.loop_start + poly.loop_total))
        for i in range(1, len(loops) - 1):
            tri = [loops[0], loops[i], loops[i + 1]]
            rec = {"m": slot, "uv": [], "co": [], "n": []}
            for li in tri:
                vi = me.loops[li].vertex_index
                u, v = uv.data[li].uv
                co = me.vertices[vi].co
                n = me.vertices[vi].normal
                rec["uv"].append([round(u, 5), round(v, 5)])
                rec["co"].append([round(co.x, 5), round(co.y, 5), round(co.z, 5)])
                rec["n"].append([round(n.x, 4), round(n.y, 4), round(n.z, 4)])
            recs.append(rec)
    with open(path, "w") as f:
        json.dump({"materials": [m.name for m in me.materials], "tris": recs}, f)
    print(f"[bake] uvdump {obj.name}: {len(recs)} tris -> {path}")


def bake_ao(obj, out_dir: str, size: int = 1024, samples: int = 24) -> None:
    """Bake AO once, writing each material slot to its own image (SLUV
    slots each cover the full 0-1 UV square, so they cannot share one)."""
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.render.bake.use_selected_to_active = False
    scene.render.bake.margin = 8

    # material slots that share a bake channel (e.g. BAKED_UPPER and
    # BAKED_UPPER2) occupy disjoint UV regions and share one image
    def channel(mat_name: str) -> str:
        return mat_name.rstrip("23456789")

    images = []
    by_channel: dict[str, object] = {}
    for mat in obj.data.materials:
        if mat is None:
            images.append(None)
            continue
        ch = channel(mat.name)
        img = by_channel.get(ch)
        if img is None:
            img = bpy.data.images.new(f"bake_{obj.name}_{ch}", size, size, alpha=False)
            by_channel[ch] = img
        mat.use_nodes = True
        nt = mat.node_tree
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = img
        nt.nodes.active = node
        images.append(img)

    from slkit.bl_utils import select_only

    select_only(obj)
    bpy.ops.object.bake(type="AO")

    for mat, img in zip(obj.data.materials, images):
        if mat is None or img is None:
            continue
        for n in [n for n in mat.node_tree.nodes if n.type == "TEX_IMAGE" and n.image == img]:
            mat.node_tree.nodes.remove(n)
    for ch, img in by_channel.items():
        out_png = os.path.join(out_dir, f"ao_{obj.name}_{ch}.png")
        img.filepath_raw = os.path.abspath(out_png)
        img.file_format = "PNG"
        img.save()
        print(f"[bake] AO {obj.name}/{ch} -> {out_png}")
        bpy.data.images.remove(img)


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    args = dict(zip(argv[::2], argv[1::2]))
    out = args.get("--out", "output")

    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(f"{out}/blend/outfit.blend"))

    os.makedirs(f"{out}/uvdump", exist_ok=True)
    os.makedirs(f"{out}/bake", exist_ok=True)

    names = [
        "GanondorfBody", "GanondorfLoincloth",
        "GanondorfBracerLeft", "GanondorfBracerRight",
        "GanondorfAnkletLeft", "GanondorfAnkletRight",
        "GanondorfHair", "GanondorfLashes", "GanondorfEyeLeft",
    ]
    for name in names:
        obj = bpy.data.objects.get(name)
        if obj:
            uvdump(obj, f"{out}/uvdump/{name}.json")

    # AO bakes: body (SLUV: shading for skin) and main garments
    for name in ("GanondorfBody", "GanondorfLoincloth"):
        obj = bpy.data.objects.get(name)
        if obj:
            bake_ao(obj, f"{out}/bake")

    print("[bake] done")


main()
