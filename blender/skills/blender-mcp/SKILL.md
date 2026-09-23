---
name: blender-mcp
description: >
  Drive the live Blender scene on Olares through blender-mcp. Use when the
  user asks to model, animate, light, or render in Blender, or to inspect
  the viewport that is already open in the browser.
---

# Blender MCP

Agents and the browser GUI share one Blender process and one in-memory scene.
Changes made through MCP appear immediately in the Selkies window.

The upstream addon is [ahujasid/blender-mcp](https://github.com/ahujasid/blender-mcp).
On Olares it is already loaded; connect to the internal `blendermcp` entrance
(`https://<hash>.<user>.olares.com/mcp`). Do not open port 9876.

## This is Blender 5.2

Assume these facts instead of probing for them. Each one costs several
round trips to rediscover.

- The Eevee engine id is `BLENDER_EEVEE`. `BLENDER_EEVEE_NEXT` does not exist.
- **There is no usable compositor.** `Scene` has no `node_tree`, and
  `CompositorNodeComposite` is undefined. Do not attempt glare, bloom, or any
  compositor graph. Get glow from emission materials and light strength.
- `bpy.app.version_string` is the cheap way to confirm the version.

## Rendering

**`bpy.ops.render.render()` does not work over MCP.** Scripts run off the main
thread, so the render job is never pumped: the operator returns `FINISHED`,
the Render Result stays 0×0, and no file is written. This affects Eevee and
Cycles equally, survives a context override, and cannot be worked around with
`bpy.app.timers` because safe mode blocks timers.

Render with `bpy.ops.render.opengl` instead. It draws through the viewport's
existing GL context on the main thread and writes a real PNG at
`scene.render.resolution_x/y`:

```python
scene = bpy.context.scene
scene.render.filepath = "/config/Home/blender-renders/scene.png"
scene.render.image_settings.file_format = "PNG"

for window in bpy.context.window_manager.windows:
    for area in window.screen.areas:
        if area.type != "VIEW_3D":
            continue
        space = area.spaces[0]
        space.region_3d.view_perspective = "CAMERA"
        space.shading.type = "RENDERED"
        region = next(r for r in area.regions if r.type == "WINDOW")
        with bpy.context.temp_override(window=window, area=area, region=region):
            bpy.ops.render.opengl(write_still=True, animation=False)
        break
```

The override is what gives you the camera framing instead of whatever the user
is currently orbiting. Sample count comes from `scene.eevee.taa_samples`, the
viewport setting, not `taa_render_samples`.

`get_viewport_screenshot` is the quick alternative, but it captures the
viewport at its own size rather than the scene resolution.

Two limits of this path are worth knowing before you design a look:

- Alpha-blended materials render as nothing. A transparent-plus-emission mix
  set to `BLENDED` / `BLEND` silently disappears, so fake glows, halos, and
  atmospheres with geometry and emission gradients instead.
- Shading is what the viewport can draw, so keep `space.shading.type` on
  `RENDERED` and turn the `use_scene_lights*` / `use_scene_world*` flags on.

## Animation

`bpy.ops.render.opengl(animation=True)` does work over MCP, inside the same
`temp_override`, and writes one image per frame across
`scene.frame_start..frame_end`.

**This build has no FFmpeg.** `image_settings.file_format` offers image
formats only — no `FFMPEG`, no `AVI_*` — so Blender cannot write a video. Write
an image sequence to Drive and encode it wherever the calling agent runs:

```python
scene.frame_start, scene.frame_end, scene.render.fps = 1, 72, 24
scene.render.image_settings.file_format = "JPEG"   # far cheaper to copy out
scene.render.filepath = "/config/Home/blender-renders/shot-frames/f"
# inside the VIEW_3D temp_override:
bpy.ops.render.opengl(animation=True)
```

```bash
olares-cli files download drive/Home/blender-renders/shot-frames /data/workspace/
ffmpeg -framerate 24 -i /data/workspace/shot-frames/f%04d.jpg \
  -c:v libx264 -pix_fmt yuv420p -crf 20 shot.mp4
```

For motion itself, prefer drivers over keyframes: a scripted expression on
`frame` is exact, needs no interpolation clean-up, and loops seamlessly when
the per-frame step covers a whole number of turns.

```python
driver = pivot.driver_add("rotation_euler", 2).driver
driver.type = "SCRIPTED"
driver.expression = "%.9f + %.9f * (frame - 1)" % (start_angle, turns * 2 * math.pi / frames)
```

Orbit an object by parenting it to an empty at the centre and driving the
empty's Z rotation; nest a second, tilted empty if the body also needs to spin
on its own axis.

## Safe mode

`BLENDER_MCP_SAFE_MODE=1` is always on. These are rejected before the script
runs, so do not try them:

`os`, `sys`, `pathlib`, any other import outside `bpy` / `bmesh` /
`mathutils`; `dir()`; `__class__` and other dunder escapes; `bpy.data.texts`
(including iterating it during scene cleanup).

You therefore cannot create directories or stat files from Python. You do not
need to: Blender's own save and render operators create missing parent
directories.

## Files

Blender cannot see another app's workspace, and the calling agent's shell
cannot see Blender's. Paths such as `/data`, `/data/workspace`, `/tmp`, and
`/dev/shm` are local to one container and are not a way to hand files over.

The only durable, cross-app location is Drive Home, mounted at
`/config/Home`. Write `.blend` files and stills there:

```python
bpy.ops.wm.save_mainfile(filepath="/config/Home/blender-renders/scene.blend")

scene = bpy.context.scene
scene.render.filepath = "/config/Home/blender-renders/frame.png"
scene.render.image_settings.file_format = "PNG"
# Use the VIEW_3D temp_override recipe from the Rendering section.
bpy.ops.render.opengl(write_still=True, animation=False)
```

From another Olares app, copy the result with `olares-cli` (`ls`, not `list`):

```bash
olares-cli files ls drive/Home/blender-renders
olares-cli files download drive/Home/blender-renders/frame.png /data/workspace/
```

## Working efficiently

Build the whole scene in one `execute_blender_code` call when you can; each
call is a round trip. Prefer primitives (`bpy.ops.mesh.primitive_*`) and
`shade_smooth` over bmesh work. Keep sample counts low — 32 to 64 is enough
for a preview still. Set `scene.render.resolution_x/y` explicitly.

Do not call `bpy_api_lookup` for sockets you can set defensively:

```python
bsdf = mat.node_tree.nodes["Principled BSDF"]
for name, value in (("Base Color", color), ("Metallic", 0.8), ("Roughness", 0.3)):
    if name in bsdf.inputs:
        bsdf.inputs[name].default_value = value
```

Two look pitfalls that cost a render each:

- Procedural texture `Scale` counts periods per *object* unit, and a mesh's
  radius is baked into those units. A big sphere needs a small scale or the
  pattern aliases into flat mush.
- The default AgX view transform desaturates bright values, so an emission with
  all three channels above 1 clips to pale pastel. Keep green and blue low for
  a saturated glow, and build brightness variation with a `Layer Weight`
  gradient — its `Facing` output is 0 straight at the camera, 1 at the limb.

## After a change

1. Save or render under `/config/Home/blender-renders/`.
2. Tell the user the Drive path (`drive/Home/blender-renders/...`).
3. If they need the file in the current agent workspace, download it with
   `olares-cli files download`.
