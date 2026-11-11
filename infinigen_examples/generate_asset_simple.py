import argparse
import logging
import math
import traceback
from itertools import product
from pathlib import Path

import bpy
import gin
import numpy as np
from PIL import Image

# ruff: noqa: E402
# NOTE: logging config has to be before imports that use logging
logging.basicConfig(
    format="[%(asctime)s.%(msecs)03d] [%(module)s] [%(levelname)s] | %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
)

import infinigen
from infinigen.assets.lighting import sky_lighting
from infinigen.assets.utils.decorate import read_base_co, read_co
from infinigen.assets.utils.misc import assign_material
from infinigen.core import init, surface
from infinigen.core.init import configure_cycles_devices
from infinigen.core.placement import density
from infinigen.core.rendering.render import set_displacement_mode
from infinigen.core.tagging import tag_system

# noinspection PyUnresolvedReferences
from infinigen.core.util import blender as butil
from infinigen.core.util.camera import points_inview
from infinigen.core.util.logging import save_polycounts
from infinigen.core.util.math import FixedSeed
from infinigen.core.util.test_utils import import_item, load_txt_list

logging.basicConfig(
    format="[%(asctime)s.%(msecs)03d] [%(name)s] [%(levelname)s] | %(message)s",
    datefmt="%H:%M:%S",
    level=logging.WARNING,
)
logger = logging.getLogger(__name__)


def unified_asset_import(name):
    try:
        return import_item(name), name.split(".")[2][:-1]
    except Exception:
        pass

    """Unified import function using test lists."""
    test_lists = {
        "scatter": "tests/assets/list_scatters.txt",
        "material": "tests/assets/list_materials.txt",
        "material_deprec": "tests/assets/list_materials_deprecated_interface.txt",
        "object": "tests/assets/list_indoor_meshes.txt",
        "nature_object": "tests/assets/list_nature_meshes.txt"
    }

    # Create single list with (asset_path, asset_type) tuples
    all_assets = [
        (asset, asset_type)
        for asset_type, path in test_lists.items()
        for asset in load_txt_list(infinigen.repo_root() / path)
    ]

    # Check exact match first
    exact = next((asset for asset, atype in all_assets if asset == name), None)
    if exact:
        return import_item(exact), next(
            atype for asset, atype in all_assets if asset == exact
        )

    # Check partial match (class name)
    matches = [
        (asset, atype) for asset, atype in all_assets if asset.split(".")[-1] == name
    ]

    if len(matches) == 1:
        return import_item(matches[0][0]), matches[0][1]
    elif len(matches) > 1:
        print(f"Ambiguous '{name}': {[f'{a} ({t})' for a, t in matches]}")
        raise ValueError(f"Ambiguous asset name: {name}")

    # Show options and fail
    all_class_names = sorted(set(a.split(".")[-1] for a, _ in all_assets))
    raise ModuleNotFoundError(
        f"Options are {all_class_names}, {len(all_class_names)} could not find asset: {name}"
    )


def _strip_modifiers(args, asset, parent):
    """Helper function to strip modifiers and center asset."""
    if args.no_mod:
        return

    if parent.animation_data is not None:
        drivers = parent.animation_data.drivers.values()
        for d in drivers:
            parent.driver_remove(d.data_path)
    co = read_co(asset)
    x_min, x_max = np.amin(co, 0), np.amax(co, 0)
    parent.location = -(x_min[0] + x_max[0]) / 2, -(x_min[1] + x_max[1]) / 2, 0
    butil.apply_transform(parent, loc=True)


def build_scene_asset(args, cls, idx):
    factory = cls
    logger.info(f"Using factory {factory}")

    fac = factory(idx)
    try:
        asset = fac.spawn_asset(idx)
    except Exception as e:
        traceback.print_exc()
        print(f"{fac}.spawn_asset({idx=}) FAILED!! {e}")
        raise e
    fac.finalize_assets(asset)
    if args.fire:
        from infinigen.assets.fluid.fluid import set_obj_on_fire

        set_obj_on_fire(
            asset,
            0,
            resolution=args.fire_res,
            simulation_duration=args.fire_duration,
            noise_scale=2,
            add_turbulence=True,
            adaptive_domain=False,
        )
        bpy.context.scene.frame_set(args.fire_duration)
        bpy.context.scene.frame_end = args.fire_duration
        bpy.data.worlds["World"].node_tree.nodes["Background.001"].inputs[
            1
        ].default_value = 0.04
        bpy.context.scene.view_settings.exposure = -1
    bpy.context.view_layer.objects.active = asset
    parent = asset
    if asset.type == "EMPTY":
        meshes = [o for o in asset.children_recursive if o.type == "MESH"]
        sizes = []
        for m in meshes:
            co = read_co(m)
            sizes.append((np.amax(co, 0) - np.amin(co, 0)).sum())
        i = np.argmax(np.array(sizes))
        asset = meshes[i]
    _strip_modifiers(args, asset, parent)

    return asset


def build_scene_scatter(args, cls, idx):

    bpy.ops.mesh.primitive_grid_add(size=10, x_subdivisions=400, y_subdivisions=400)
    plane = bpy.context.active_object

    material = bpy.data.materials.new("plane")
    material.use_nodes = True
    material.node_tree.nodes["Principled BSDF"].inputs[0].default_value = (
        0.015,
        0.009,
        0.003,
        1,
    )
    assign_material(plane, material)

    scatter_instance = cls()
    scatter_instance.apply(plane, selection=density.placement_mask(0.15, 0.45))

    return plane


def build_scene_material(args, cls, idx):

    if hasattr(cls, "make_sphere"):
        asset = cls.make_sphere()
    else:
        bpy.ops.mesh.primitive_ico_sphere_add(radius=0.8, subdivisions=9)
        asset = bpy.context.active_object

    while len(asset.data.vertices) < 500000:
        with butil.ViewportMode(asset, mode="EDIT"):
            bpy.ops.mesh.subdivide(number_cuts=2)

    mat_gen = cls() if type(cls) is type else cls

    if hasattr(mat_gen, "apply"):
        mat_gen.apply(asset)
    else:
        surface.assign_material(asset, mat_gen())

    return asset

def build_and_save_asset(payload: dict):
    # unpack payload - args are packed into payload for compatibility with slurm/multiprocessing
    factory_name = payload["fac"]
    args = payload["args"]
    idx = payload["idx"]

    output_folder = infinigen.repo_root() / args.output_folder / f"{factory_name}_{idx:03d}"
    output_folder.mkdir(exist_ok=True)

    init.apply_gin_configs(
        ["infinigen_examples/configs_indoor", "infinigen_examples/configs_nature"],
        skip_unknown=True,
    )

    init.configure_blender()

    if args.gpu:
        init.configure_render_cycles()

    logger.info(f"Building scene for {factory_name} {idx}")

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.render.resolution_x, scene.render.resolution_y = map(
        int, args.resolution.split("x")
    )
    scene.cycles.samples = args.samples
    butil.clear_scene()

    if not args.fire:
        bpy.context.scene.render.film_transparent = args.film_transparent
        bg = bpy.context.scene.world.node_tree.nodes["Background"]
        bg.inputs[0].default_value[-1] = 0

    camera, center = setup_camera(args)

    # Use unified import to determine asset type
    with gin.unlock_config():
        cls, asset_type = unified_asset_import(factory_name)

    with FixedSeed(idx):
        match asset_type:
            case "object" | "nature_object":
                asset = build_scene_asset(args, cls, idx)
            case "sim_object":
                asset = build_scene_asset(args, cls, idx)
            case "scatter":
                asset = build_scene_scatter(args, cls, idx)
            case "material" | "material_deprec":
                asset = build_scene_material(args, cls, idx)
            case _:
                raise ValueError(f"Unsupported asset type: {asset_type}")

    # Apply displacement mode to all materials
    set_displacement_mode()

    with (output_folder / "polycounts.txt").open("w") as f:
        save_polycounts(f)

    configure_cycles_devices()
    set_displacement_mode()

    with FixedSeed(args.lighting + idx):
        sky_lighting.add_lighting(camera)
        nodes = bpy.data.worlds["World"].node_tree.nodes
        sky_texture = [n for n in nodes if n.name.startswith("Sky Texture")][-1]
        sky_texture.sun_elevation = np.deg2rad(args.elevation)
        sky_texture.sun_rotation = np.pi * 0.75

    if args.cam_center > 0 and asset:
        co = read_base_co(asset)
        location = (np.amin(co, 0) + np.amax(co, 0)) / 2
        center.location = (np.array(asset.matrix_world) @ np.array([*location, 1]))[:-1]
        center.location[-1] += args.cam_zoff

    if args.cam_dist <= 0 and asset:
        if "Factory" in factory_name:
            adjust_cam_distance(asset, camera, args.margin)
        else:
            adjust_cam_distance(asset, camera, args.margin, 0.75)

    cam_info_ng = bpy.data.node_groups.get("nodegroup_active_cam_info")
    if cam_info_ng is not None:
        cam_info_ng.nodes["Object Info"].inputs["Object"].default_value = camera

    if args.save_blend:
        butil.save_blend(output_folder / "scene.blend", autopack=True)
        tag_system.save_tag(output_folder / "MaskTag.json")

    if args.fire:
        bg = bpy.data.worlds["World"].node_tree.nodes["Background.001"]
        bg.inputs[1].default_value = 0.04
        bpy.context.scene.view_settings.exposure = -2

    if args.render == "image":
        image_path = output_folder / "Image.png"
        scene.render.filepath = str(image_path)
        bpy.ops.render.render(write_still=True)
    elif args.render == "none":
        pass
    else:
        raise ValueError(f"Unrecognized {args.render=}")


def parent(obj):
    return obj if obj.parent is None else obj.parent


def adjust_cam_distance(asset, camera, margin, percent=0.999):
    co = read_base_co(asset) * asset.scale
    co += asset.location
    lowest = np.amin(co, 0)
    highest = np.amax(co, 0)
    interp = np.linspace(lowest, highest, 11)
    bbox = np.array(list(product(*zip(*interp))))
    for cam_dist in np.exp(np.linspace(-1.0, 5.5, 500)):
        camera.location[1] = -cam_dist
        bpy.context.view_layer.update()
        inview = points_inview(bbox, camera)
        if inview.sum() / inview.size >= percent:
            camera.location[1] *= 1 + margin
            bpy.context.view_layer.update()
            break
    else:
        camera.location[1] = -6


def make_grid(args, name, files, n):
    path = args.output_folder

    with Image.open(files[0]) as i:
        x, y = i.size

    sz_x = list(
        sorted(
            range(1, n + 1),
            key=lambda x: abs(math.ceil(n / x) / x - args.best_ratio),
        )
    )[0]
    sz_y = math.ceil(n / sz_x)
    img = Image.new("RGBA", (sz_x * x, sz_y * y))
    for idx, file in enumerate(files):
        with Image.open(file) as i:
            img.paste(i, (idx % sz_x * x, idx // sz_x * y))
    img.save(f"{path}/{name}.png")


def setup_camera(args):
    cam_dist = args.cam_dist if args.cam_dist > 0 else 6
    bpy.ops.object.camera_add(location=(0, -cam_dist, 0), rotation=(np.pi / 2, 0, 0))
    camera = bpy.context.active_object
    camera.parent = butil.spawn_empty("Camera parent")
    camera.parent.location = (0, 0, args.cam_zoff)
    camera.parent.rotation_euler = np.deg2rad(np.array(args.cam_angle))
    bpy.data.scenes["Scene"].camera = camera
    scene = bpy.context.scene
    camera.data.sensor_height = (
        camera.data.sensor_width * scene.render.resolution_y / scene.render.resolution_x
    )
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            area.spaces.active.region_3d.view_perspective = "CAMERA"
            break
    cam_info_ng = bpy.data.node_groups.get("nodegroup_active_cam_info")
    if cam_info_ng is not None:
        cam_info_ng.nodes["Object Info"].inputs["Object"].default_value = camera
    return camera, camera.parent


@gin.configurable
def mapfunc(f, its):
    return [f(i) for i in its]


def main(args):
    bpy.context.window.workspace = bpy.data.workspaces["Geometry Nodes"]
    if args.output_folder is None:
        outputs = Path("outputs")
        assert outputs.exists(), outputs
        name = "_".join(args.factories)
        args.output_folder = Path("outputs") / name

    args.output_folder.mkdir(exist_ok=True, parents=True)
    factories = list(args.factories)
    targets = [
        {"args": args, "fac": fac, "idx": idx}
        for idx in range(args.n_images)
        for fac in factories
    ]
    mapfunc(build_and_save_asset, targets)


def make_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--output_folder", type=Path, default="outputs/corals")
    parser.add_argument(
        "-f",
        "--factories",
        default=["CoralFactory"],
        nargs="+",
        help="List factories/surface scatters/surface materials you want to render",
    )
    parser.add_argument(
        "-n", "--n_images", default=1, type=int, help="Number of scenes to render"
    )
    parser.add_argument(
        "-m",
        "--margin",
        default=0.01,
        help="Margin between the asset the boundary of the image when automatically adjusting "
        "the camera",
    )
    parser.add_argument(
        "-R",
        "--resolution",
        default="1024x1024",
        type=str,
        help="Image resolution widthxheight",
    )
    parser.add_argument(
        "-p", "--samples", default=200, type=int, help="Blender cycles samples"
    )
    parser.add_argument("-l", "--lighting", default=0, type=int, help="Lighting seed")
    parser.add_argument(
        "-Z",
        "--cam_zoff",
        "--z_offset",
        type=float,
        default=0.0,
        help="Additional offset on Z axis for camera look-at positions",
    )
    parser.add_argument(
        "-s", "--save_blend", action="store_true", help="Whether to save .blend file"
    )
    parser.add_argument(
        "-e", "--elevation", default=60, type=float, help="Elevation of the sun"
    )
    parser.add_argument(
        "--cam_dist",
        default=0,
        type=float,
        help="Distance from the camera to the look-at position",
    )
    parser.add_argument(
        "-a",
        "--cam_angle",
        default=(-30, 0, 45),
        type=float,
        nargs="+",
        help="Camera rotation in XYZ",
    )
    parser.add_argument(
        "-c", "--cam_center", default=1, type=int, help="Camera rotation in XYZ"
    )
    parser.add_argument(
        "-r",
        "--render",
        default="image",
        type=str,
        choices=["image", "none"],
        help="Whether to render the scene in images or video",
    )
    parser.add_argument(
        "-b",
        "--best_ratio",
        default=9 / 16,
        type=float,
        help="Best aspect ratio for compiling the images into asset grid",
    )
    parser.add_argument("-F", "--fire", action="store_true")
    parser.add_argument("-I", "--fire_res", default=100, type=int)
    parser.add_argument("-U", "--fire_duration", default=30, type=int)
    parser.add_argument(
        "-t",
        "--film_transparent",
        default=1,
        type=int,
        help="Whether the background is transparent",
    )
    parser.add_argument(
        "-E", "--frame_end", type=int, default=120, help="End of frame in videos"
    )
    parser.add_argument(
        "-g", "--gpu", action="store_true", help="Whether to use gpu in rendering"
    )
    parser.add_argument("-N", "--no-mod", action="store_true", help="No modification")

    return init.parse_args_blender(parser)


if __name__ == "__main__":
    args = make_args()
    args.no_mod = args.no_mod or args.fire
    with FixedSeed(1):
        main(args)
