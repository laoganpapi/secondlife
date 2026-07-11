"""Blender scene/rendering utilities for the headless pipeline."""

from __future__ import annotations

import math
import os

import bpy
from mathutils import Vector


def reset_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0


def look_at(cam_obj, target: Vector) -> None:
    direction = target - cam_obj.location
    cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def render_preview(
    filepath: str,
    cam_pos,
    target=(0.0, 0.0, 1.0),
    resolution=(720, 1080),
    ortho_scale: float | None = None,
    shading: str = "solid",
) -> None:
    """Workbench render for geometry inspection (fast, no GPU needed)."""
    scene = bpy.context.scene
    cam_data = bpy.data.cameras.new("PreviewCam")
    cam = bpy.data.objects.new("PreviewCam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = Vector(cam_pos)
    look_at(cam, Vector(target))
    if ortho_scale:
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = ortho_scale
    scene.camera = cam

    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL" if shading == "material" else "SINGLE"
    scene.display.shading.single_color = (0.62, 0.64, 0.66)
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "BOTH"
    scene.render.resolution_x, scene.render.resolution_y = resolution
    scene.render.film_transparent = False
    scene.world = scene.world or bpy.data.worlds.new("World")
    scene.render.filepath = filepath
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    bpy.ops.render.render(write_still=True)

    bpy.data.objects.remove(cam)
    bpy.data.cameras.remove(cam_data)


def render_cycles(
    filepath: str,
    cam_pos,
    target=(0.0, 0.0, 1.0),
    resolution=(720, 1080),
    samples: int = 48,
) -> None:
    """CPU Cycles render for textured beauty previews."""
    scene = bpy.context.scene
    cam_data = bpy.data.cameras.new("BeautyCam")
    cam = bpy.data.objects.new("BeautyCam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = Vector(cam_pos)
    look_at(cam, Vector(target))
    scene.camera = cam

    # simple three-point light
    lights = []
    for name, pos, energy in (
        ("key", (2.5, 1.5, 2.4), 400),
        ("fill", (2.0, -2.2, 1.4), 150),
        ("rim", (-2.5, 0.5, 2.2), 250),
    ):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy = energy
        ld.size = 1.5
        lo = bpy.data.objects.new(name, ld)
        lo.location = pos
        look_at(lo, Vector(target))
        scene.collection.objects.link(lo)
        lights.append((lo, ld))

    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = resolution
    if not scene.world:
        scene.world = bpy.data.worlds.new("World")
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.18, 0.18, 0.2, 1.0)
        bg.inputs[1].default_value = 0.6
    scene.render.filepath = filepath
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    bpy.ops.render.render(write_still=True)

    bpy.data.objects.remove(cam)
    bpy.data.cameras.remove(cam_data)
    for lo, ld in lights:
        bpy.data.objects.remove(lo)
        bpy.data.lights.remove(ld)


def select_only(objs) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    if not isinstance(objs, (list, tuple)):
        objs = [objs]
    for o in objs:
        o.select_set(True)
    if objs:
        bpy.context.view_layer.objects.active = objs[0]
