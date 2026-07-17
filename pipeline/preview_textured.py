"""Textured beauty renders (Cycles CPU): the end-to-end check that every
texture lands correctly on its UVs, plus hero shots for documentation.

Run: blender --background --factory-startup --python pipeline/preview_textured.py -- --out output
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402

from slkit import bl_utils  # noqa: E402

# material name -> (texture file, roughness, metallic, extras)
TEXMAP = {
    "BAKED_HEAD": ("skin_head.png", 0.55, 0.0, {}),
    "BAKED_UPPER": ("skin_upper.png", 0.55, 0.0, {}),
    "BAKED_UPPER2": ("skin_upper.png", 0.55, 0.0, {}),
    "BAKED_LOWER": ("skin_lower.png", 0.55, 0.0, {}),
    "BAKED_EYES": ("eyes.png", 0.15, 0.0, {}),
    "LASHES": ("lashes.png", 0.6, 0.0, {"alpha": True}),
    "Hair": ("hair.png", 0.78, 0.0, {"alpha": True}),
    "HairGold": ("gold.png", 0.25, 1.0, {}),
    "Gold": ("gold.png", 0.25, 1.0, {}),
    "Gem": ("gem.png", 0.1, 0.0, {"emission": 0.15}),
    "Loincloth": ("loincloth.png", 0.75, 0.0, {"normal": "loincloth_normal.png"}),
    "Bracer": ("bracer.png", 0.5, 0.3, {}),
    "LegWrap": ("legwrap.png", 0.8, 0.0, {}),
    "Sheath": ("sheath.png", 0.5, 0.1, {}),
}


def setup_materials(tex_dir: str) -> None:
    for name, (tex, rough, metal, extras) in TEXMAP.items():
        mat = bpy.data.materials.get(name)
        if mat is None:
            continue
        mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.clear()
        out_node = nt.nodes.new("ShaderNodeOutputMaterial")
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        nt.links.new(bsdf.outputs["BSDF"], out_node.inputs["Surface"])
        bsdf.inputs["Roughness"].default_value = rough
        bsdf.inputs["Metallic"].default_value = metal

        img_path = os.path.abspath(os.path.join(tex_dir, tex))
        if os.path.exists(img_path):
            img = bpy.data.images.load(img_path, check_existing=True)
            tex_node = nt.nodes.new("ShaderNodeTexImage")
            tex_node.image = img
            nt.links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])
            if extras.get("alpha"):
                nt.links.new(tex_node.outputs["Alpha"], bsdf.inputs["Alpha"])
                mat.blend_method = "BLEND"
            if extras.get("emission"):
                bsdf.inputs["Emission Strength"].default_value = extras["emission"]
                nt.links.new(tex_node.outputs["Color"], bsdf.inputs["Emission"])
        if extras.get("normal"):
            npath = os.path.abspath(os.path.join(tex_dir, extras["normal"]))
            if os.path.exists(npath):
                nimg = bpy.data.images.load(npath, check_existing=True)
                nimg.colorspace_settings.name = "Non-Color"
                ntex = nt.nodes.new("ShaderNodeTexImage")
                ntex.image = nimg
                nmap = nt.nodes.new("ShaderNodeNormalMap")
                nmap.inputs["Strength"].default_value = 0.6
                nt.links.new(ntex.outputs["Color"], nmap.inputs["Color"])
                nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    args = dict(zip(argv[::2], argv[1::2]))
    out = args.get("--out", "output")

    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(f"{out}/blend/outfit.blend"))
    setup_materials(f"{out}/textures")

    p = f"{out}/preview"
    bl_utils.render_cycles(f"{p}/final_front.png", (2.9, 0.35, 1.25), (0.0, 0.0, 1.0), resolution=(760, 1140), samples=40)
    bl_utils.render_cycles(f"{p}/final_face.png", (0.75, 0.20, 1.80), (0.02, 0.0, 1.74), resolution=(900, 900), samples=40)
    bl_utils.render_cycles(f"{p}/final_back.png", (-2.9, 0.4, 1.25), (0.0, 0.0, 1.0), resolution=(760, 1140), samples=40)
    print("[beauty] done")


main()
