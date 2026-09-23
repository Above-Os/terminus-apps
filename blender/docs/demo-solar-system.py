"""Fast, presentable solar-system showcase for Blender on Olares.

One execute_blender_code call. Built from primitives only, no downloads.
Rendered through the GL viewport because bpy.ops.render.render() is a silent
no-op over MCP (scripts run off Blender's main thread).

With ANIMATE on it also writes a looping PNG sequence of the planets orbiting.
This Blender build has no FFmpeg, so encode the sequence outside Blender.
"""
import bpy
import math
from mathutils import Vector

OUT = "/config/Home/blender-renders"
NAME = "lares-solar-system"
ANIMATE = True
FRAMES = 72

# ---------------------------------------------------------------- clean slate
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras):
    for item in list(coll):
        if item.users == 0:
            coll.remove(item)

scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 1600
scene.render.resolution_y = 900
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.use_file_extension = True
scene.render.filepath = OUT + "/" + NAME + ".png"
scene.frame_start = 1
scene.frame_end = FRAMES
scene.render.fps = 24

# The OpenGL path uses viewport sampling, not render sampling.
eevee = scene.eevee
for attr, value in (("taa_samples", 48), ("use_raytracing", True), ("use_shadows", True)):
    if hasattr(eevee, attr):
        setattr(eevee, attr, value)

view = scene.view_settings
looks = [item.identifier for item in view.bl_rna.properties["look"].enum_items]
for candidate in ("AgX - Medium High Contrast", "Medium High Contrast", "None"):
    if candidate in looks:
        view.look = candidate
        break
view.exposure = 0.0


def socket(node, names, value):
    """Set the first matching input socket so 4.x/5.x naming both work."""
    for name in names:
        if name in node.inputs:
            node.inputs[name].default_value = value
            return


def smooth(obj):
    for poly in obj.data.polygons:
        poly.use_smooth = True


def look_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def spin(obj, turns, start=0.0):
    """Drive Z rotation linearly across the loop; drivers need no interpolation
    clean-up and land exactly on a seamless cycle."""
    step = turns * 2.0 * math.pi / FRAMES
    driver = obj.driver_add("rotation_euler", 2).driver
    driver.type = "SCRIPTED"
    driver.expression = "%.9f + %.9f * (frame - 1)" % (start, step)


def empty(name, location, parent=None, rotation=(0.0, 0.0, 0.0)):
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0.0, 0.0, 0.0))
    obj = bpy.context.object
    obj.name = name
    obj.empty_display_size = 0.2
    if parent is not None:
        obj.parent = parent
    obj.location = location
    obj.rotation_euler = rotation
    return obj


# ------------------------------------------------------------ procedural sky
world = scene.world
if world is None:
    world = bpy.data.worlds.new("Deep Space")
    scene.world = world
world.use_nodes = True
wnt = world.node_tree
wnt.nodes.clear()
w_out = wnt.nodes.new("ShaderNodeOutputWorld")
w_bg = wnt.nodes.new("ShaderNodeBackground")
socket(w_bg, ("Strength",), 1.2)
w_coord = wnt.nodes.new("ShaderNodeTexCoord")
w_noise = wnt.nodes.new("ShaderNodeTexNoise")
socket(w_noise, ("Scale",), 520.0)
socket(w_noise, ("Detail",), 2.0)
w_ramp = wnt.nodes.new("ShaderNodeValToRGB")
w_ramp.color_ramp.elements[0].position = 0.70
w_ramp.color_ramp.elements[0].color = (0.002, 0.004, 0.012, 1.0)
w_ramp.color_ramp.elements[1].position = 0.78
w_ramp.color_ramp.elements[1].color = (0.92, 0.95, 1.0, 1.0)
wnt.links.new(w_coord.outputs["Generated"], w_noise.inputs["Vector"])
wnt.links.new(w_noise.outputs["Fac"], w_ramp.inputs["Fac"])
wnt.links.new(w_ramp.outputs["Color"], w_bg.inputs["Color"])
wnt.links.new(w_bg.outputs["Background"], w_out.inputs["Surface"])


def plain(name, color, rough=0.5, emission=None, strength=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    socket(bsdf, ("Base Color",), (*color, 1.0))
    socket(bsdf, ("Roughness",), rough)
    if emission is not None:
        socket(bsdf, ("Emission Color", "Emission"), (*emission, 1.0))
        socket(bsdf, ("Emission Strength",), strength)
    return mat


def _ramp(node_tree, stops):
    ramp = node_tree.nodes.new("ShaderNodeValToRGB")
    elements = ramp.color_ramp.elements
    elements[0].position = stops[0][0]
    elements[0].color = (*stops[0][1], 1.0)
    elements[1].position = stops[-1][0]
    elements[1].color = (*stops[-1][1], 1.0)
    for position, color in stops[1:-1]:
        elements.new(position).color = (*color, 1.0)
    return ramp


def banded(name, stops, scale=6.0, distortion=0.3, rough=0.55):
    """Latitude cloud bands: a wave texture stacked along the object's own Z."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    socket(bsdf, ("Roughness",), rough)
    coord = nt.nodes.new("ShaderNodeTexCoord")
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    if hasattr(wave, "bands_direction"):
        wave.bands_direction = "Z"
    socket(wave, ("Scale",), scale)
    socket(wave, ("Distortion",), distortion)
    socket(wave, ("Detail",), 1.0)
    socket(wave, ("Detail Scale",), 0.6)
    ramp = _ramp(nt, stops)
    nt.links.new(coord.outputs["Object"], wave.inputs["Vector"])
    nt.links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


def mottled(name, stops, scale=3.0, detail=6.0, rough=0.5):
    """Continents / terrain blotches from object-space noise."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    socket(bsdf, ("Roughness",), rough)
    coord = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    socket(noise, ("Scale",), scale)
    socket(noise, ("Detail",), detail)
    socket(noise, ("Roughness",), 0.55)
    ramp = _ramp(nt, stops)
    nt.links.new(coord.outputs["Object"], noise.inputs["Vector"])
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


def sphere(name, radius, mat, parent=None):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=64, ring_count=32, radius=radius, location=(0.0, 0.0, 0.0)
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    if parent is not None:
        obj.parent = parent
        obj.location = (0.0, 0.0, 0.0)
    smooth(obj)
    return obj


def orbit(radius, mat):
    bpy.ops.mesh.primitive_torus_add(
        major_radius=radius, minor_radius=0.02,
        major_segments=256, minor_segments=6, location=(0, 0, 0),
    )
    band = bpy.context.object
    band.name = "Orbit %.1f" % radius
    band.data.materials.append(mat)
    smooth(band)
    return band


# ------------------------------------------------------------------ the star
def star_mat(name, core, edge, strength):
    """Hot core, saturated limb, noisy granulation. Keep green and blue low: a
    bright emission with all three channels over 1 clips to flat pastel."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emit = nt.nodes.new("ShaderNodeEmission")
    socket(emit, ("Strength",), strength)
    weight = nt.nodes.new("ShaderNodeLayerWeight")
    socket(weight, ("Blend",), 0.3)
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    elements = ramp.color_ramp.elements
    # Layer Weight "Facing" reads 0 straight at the camera and 1 at the limb.
    elements[0].position = 0.0
    elements[0].color = (*core, 1.0)
    elements[1].position = 0.55
    elements[1].color = (*edge, 1.0)
    coord = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    socket(noise, ("Scale",), 5.5)
    socket(noise, ("Detail",), 6.0)
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "OVERLAY"
    socket(mix, ("Factor", "Factor_Float"), 0.35)
    nt.links.new(weight.outputs["Facing"], ramp.inputs["Fac"])
    nt.links.new(coord.outputs["Object"], noise.inputs["Vector"])
    nt.links.new(ramp.outputs["Color"], mix.inputs[6])
    nt.links.new(noise.outputs["Color"], mix.inputs[7])
    nt.links.new(mix.outputs[2], emit.inputs["Color"])
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    return mat


sun_mat = star_mat("Sun", (1.0, 0.72, 0.30), (1.0, 0.18, 0.01), 2.6)
sphere("Sun", 1.5, sun_mat)


# No corona glow here: alpha-blended materials render as nothing through
# bpy.ops.render.opengl, and this build has no compositor for a glare node.
bpy.ops.object.light_add(type="POINT", location=(0, 0, 0))
solar = bpy.context.object
solar.name = "Solar Light"
solar.data.energy = 26000
solar.data.color = (1.0, 0.88, 0.72)
solar.data.shadow_soft_size = 1.5
if hasattr(solar.data, "use_shadow"):
    solar.data.use_shadow = False

orbit_mat = plain("Orbit Line", (0.05, 0.11, 0.24), 0.7,
                  emission=(0.10, 0.28, 0.68), strength=0.6)

# Wave scale is periods per object unit, and the mesh radius is baked into
# those units, so a big planet needs a low number or the bands alias away.
jupiter_mat = banded("Jupiter", [
    (0.05, (0.40, 0.24, 0.15)),
    (0.30, (0.82, 0.60, 0.37)),
    (0.52, (0.96, 0.88, 0.72)),
    (0.74, (0.64, 0.38, 0.21)),
    (0.95, (0.90, 0.76, 0.57)),
], scale=2.6, distortion=0.25)

saturn_mat = banded("Saturn", [
    (0.08, (0.72, 0.58, 0.32)),
    (0.45, (0.93, 0.83, 0.59)),
    (0.92, (0.99, 0.95, 0.80)),
], scale=2.4, distortion=0.18)

earth_mat = mottled("Earth", [
    (0.38, (0.03, 0.12, 0.45)),
    (0.48, (0.05, 0.25, 0.62)),
    (0.53, (0.16, 0.42, 0.18)),
    (0.66, (0.45, 0.52, 0.28)),
    (0.80, (0.92, 0.95, 0.98)),
], scale=3.4, detail=7.0, rough=0.45)

mars_mat = mottled("Mars", [
    (0.35, (0.46, 0.17, 0.08)),
    (0.55, (0.78, 0.33, 0.14)),
    (0.78, (0.88, 0.62, 0.38)),
], scale=4.2, detail=6.0, rough=0.7)

venus_mat = banded("Venus", [
    (0.20, (0.78, 0.58, 0.28)),
    (0.60, (0.96, 0.82, 0.50)),
    (0.90, (0.99, 0.93, 0.72)),
], scale=6.0, distortion=1.1, rough=0.6)

# name, orbit radius, planet radius, start angle, axial tilt, orbits, spins, material
planets = [
    ("Mercury", 3.0, 0.30, 2.55, 0.10, 8, 3, plain("Mercury", (0.48, 0.44, 0.40), 0.75)),
    ("Venus", 4.2, 0.48, 0.55, 0.30, 6, 2, venus_mat),
    ("Earth", 5.7, 0.54, 3.55, 0.41, 5, 6, earth_mat),
    ("Mars", 7.1, 0.38, 5.35, 0.44, 4, 5, mars_mat),
    ("Jupiter", 9.3, 1.45, 2.05, 0.52, 3, 4, jupiter_mat),
    ("Saturn", 11.4, 1.15, 4.45, 0.47, 2, 3, saturn_mat),
    ("Uranus", 13.0, 0.80, 0.30, 0.55, 2, 2, plain("Uranus", (0.42, 0.78, 0.82), 0.4)),
    ("Neptune", 14.3, 0.78, 5.95, 0.50, 1, 2, plain("Neptune", (0.13, 0.28, 0.80), 0.4)),
]

for name, distance, size, angle, tilt, turns, spins, mat in planets:
    orbit(distance, orbit_mat)

    # pivot at the star carries the orbit, a tilted child carries the spin axis
    pivot = empty(name + " Orbit", (0.0, 0.0, 0.0))
    spin(pivot, turns, start=angle)
    axis = empty(name + " Axis", (distance, 0.0, 0.0), parent=pivot, rotation=(tilt, 0.0, 0.0))
    body = sphere(name, size, mat, parent=axis)
    spin(body, spins)

    if name == "Saturn":
        ring_mat = plain("Saturn Ring", (0.88, 0.76, 0.54), 0.7,
                         emission=(0.85, 0.72, 0.50), strength=0.3)
        for major, minor in ((1.70, 0.30), (2.12, 0.20), (2.42, 0.12)):
            bpy.ops.mesh.primitive_torus_add(
                major_radius=major, minor_radius=minor,
                major_segments=128, minor_segments=6, location=(0, 0, 0),
            )
            ring = bpy.context.object
            ring.name = "Saturn Ring"
            ring.data.materials.append(ring_mat)
            ring.parent = axis
            ring.location = (0.0, 0.0, 0.0)
            ring.scale = (1.0, 1.0, 0.02)
            smooth(ring)

    if name == "Earth":
        moon_pivot = empty("Moon Orbit", (distance, 0.0, 0.0), parent=pivot)
        spin(moon_pivot, 10)
        moon_mat = plain("Moon", (0.52, 0.52, 0.55), 0.8)
        moon = sphere("Moon", 0.15, moon_mat, parent=moon_pivot)
        moon.location = (1.05, 0.0, 0.12)

# A cool fill keeps the night sides from reading as flat cut-out semicircles.
bpy.ops.object.light_add(type="AREA", location=(-24.0, -30.0, 18.0))
fill = bpy.context.object
fill.name = "Cool Fill"
fill.data.energy = 6000
fill.data.shape = "DISK"
fill.data.size = 40.0
fill.data.color = (0.40, 0.55, 1.0)
look_at(fill, (0, 0, 0))

# A dim rim from behind separates the outer planets from the starfield.
bpy.ops.object.light_add(type="AREA", location=(20.0, 26.0, 10.0))
rim = bpy.context.object
rim.name = "Rim"
rim.data.energy = 3000
rim.data.shape = "DISK"
rim.data.size = 36.0
rim.data.color = (0.62, 0.72, 1.0)
look_at(rim, (0, 0, 0))

# -------------------------------------------------------------------- camera
# A lower elevation keeps the cloud bands readable as stripes instead of
# looking down the poles, and 42 mm leaves margin outside Neptune's orbit.
bpy.ops.object.camera_add(location=(14.0, -36.0, 13.5))
camera = bpy.context.object
camera.name = "Hero Camera"
camera.data.lens = 42
look_at(camera, (0, 0, 0))
scene.camera = camera

# look_at aims -Z at the camera, which leaves the plane square to the view.
scene.frame_set(scene.frame_start)
bpy.ops.wm.save_as_mainfile(filepath=OUT + "/" + NAME + ".blend")

# ------------------------------------------------- render via the GL viewport
stills = None
frames = None
for window in bpy.context.window_manager.windows:
    for area in window.screen.areas:
        if area.type != "VIEW_3D":
            continue
        space = area.spaces.active
        space.region_3d.view_perspective = "CAMERA"
        space.shading.type = "RENDERED"
        for flag in ("use_scene_lights", "use_scene_world",
                     "use_scene_lights_render", "use_scene_world_render"):
            if hasattr(space.shading, flag):
                setattr(space.shading, flag, True)
        space.overlay.show_overlays = False
        region = next(r for r in area.regions if r.type == "WINDOW")
        with bpy.context.temp_override(window=window, area=area, region=region):
            stills = str(bpy.ops.render.opengl(write_still=True, animation=False))
            if ANIMATE:
                scene.render.resolution_x = 960
                scene.render.resolution_y = 540
                if hasattr(eevee, "taa_samples"):
                    eevee.taa_samples = 24
                # JPEG keeps the sequence small enough to copy out of the pod;
                # the video codec compresses it again anyway.
                scene.render.image_settings.file_format = "JPEG"
                scene.render.image_settings.quality = 92
                scene.render.filepath = OUT + "/" + NAME + "-frames/f"
                frames = str(bpy.ops.render.opengl(animation=True))
        break
    if stills:
        break

print("SOLAR_DONE", stills, frames, FRAMES)
