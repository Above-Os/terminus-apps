# Create a Blender scene with Lares

This example shows the recommended Olares workflow: describe a scene in Lares,
watch it appear in Blender, and retrieve the finished render from Olares Drive.

## Before you start

1. Install Blender and Lares from Olares Market.
2. Open Blender once and leave its browser window running.
3. In **Lares → Settings → MCP**, add:

   - **Server name:** `blender`
   - **Transport:** `Streamable HTTP`
   - **MCP URL:** the internal Blender MCP entrance ending in `/mcp`
   - **Headers:** `{}`

The Blender Market page recommends Lares because both apps run on Olares and
the MCP connection remains internal to your system.

## Example: solar system

Start a new Lares conversation and paste this prompt. The block of facts at
the end matters: without it the model spends most of its turns probing the
Blender API instead of building the scene.

```text
Use the Blender MCP tools to create and render a solar system.

Requirements:
- Clear the current scene.
- Place a glowing sun at the origin and eight planets on the XY plane, each on
  its own circular orbit, coloured per planet and spaced so the outermost
  orbit fills most of the frame.
- Exaggerate the planet radii heavily so each one reads clearly at 1280x720 —
  this is an illustration, not a scale model.
- Draw each orbit as a thin, faintly glowing emission torus in the XY plane.
- Give Saturn a ring made from a flattened torus.
- Light with a strong point light at the sun, plus a dim fill light off to one
  side so the planets read as discs rather than thin crescents. Use a
  near-black world background.
- Frame the whole system from above at an angle with a 50 mm camera.
- Render one 1280x720 PNG at 32 samples.
- Save the project to /config/Home/blender-renders/lares-solar-system.blend
  and the render to /config/Home/blender-renders/lares-solar-system.png.
- Report the two Olares Drive paths when you are done.

Build the entire scene in ONE execute_blender_code call. Known facts, do not
verify them:
- This is Blender 5.2. The Eevee engine id is "BLENDER_EEVEE".
- There is no compositor. Scene has no node_tree and CompositorNodeComposite
  does not exist. Get the sun's glow from an emission material, not glare.
- bpy.ops.render.render() is a no-op over MCP: it returns FINISHED but leaves
  a 0x0 buffer and writes nothing. Render with
  bpy.ops.render.opengl(write_still=True, animation=False) inside a
  temp_override of the VIEW_3D area, after setting that viewport's
  region_3d.view_perspective to "CAMERA" and shading.type to "RENDERED".
- Safe mode is on: os, sys, pathlib, dir() and bpy.data.texts are all blocked.
  Use only bpy, bmesh and mathutils.
- Save and render operators create missing directories, so the output folder
  does not need to be checked or created.
- Do not write to /data/workspace, /tmp, or /dev/shm; those are not shared
  with Lares.
```

Lares should call the Blender MCP server, build the scene in the same Blender
process shown in the browser, render the still, and report:

```text
drive/Home/blender-renders/lares-solar-system.blend
drive/Home/blender-renders/lares-solar-system.png
```

This takes a handful of tool calls and about a minute. A scene that needs
many separate build steps, or one that tempts the model into compositor
effects, will take considerably longer.

## Make the planets orbit

Once the still looks right, ask for motion as a follow-up:

```text
Now animate it: 72 frames at 24 fps, with every planet orbiting the sun and
looping seamlessly.

- Parent each planet to an empty at the origin and drive that empty's Z
  rotation with a scripted expression on `frame` rather than keyframes, so the
  motion is exactly linear.
- Give each planet a whole number of turns over the 72 frames (inner planets
  more turns than outer ones) so the last frame runs back into the first.
- Render the sequence with bpy.ops.render.opengl(animation=True) inside the
  same VIEW_3D temp_override, at 960x540 and 24 samples, as JPEG frames to
  /config/Home/blender-renders/lares-solar-system-frames/f.

This Blender build has no FFmpeg — image_settings.file_format offers no
FFMPEG option — so do not try to write a video from Blender.
```

The 72 frames take roughly twenty seconds. To turn them into a video, copy the
folder out of Drive and encode it anywhere ffmpeg is available:

```bash
olares-cli files download \
  drive/Home/blender-renders/lares-solar-system-frames /data/workspace/
ffmpeg -framerate 24 -i /data/workspace/lares-solar-system-frames/f%04d.jpg \
  -c:v libx264 -pix_fmt yuv420p -crf 20 solar-system.mp4
```

## Retrieve the result

Open **Files → Home → blender-renders**, or ask Lares to copy the image into
its current workspace. The equivalent commands are:

```bash
olares-cli files ls drive/Home/blender-renders
olares-cli files download \
  drive/Home/blender-renders/lares-solar-system.png \
  /data/workspace/lares-solar-system.png
```

Use `files ls`, not `files list`.

## Why the output path matters

Lares and Blender run in separate containers. Lares's `/data/workspace` is not
mounted in Blender, and Blender's `/tmp` and `/dev/shm` are not visible to
Lares. Blender's `/config/Home` is the durable Olares Drive Home mount and is
the supported handoff point between the two apps.

## Troubleshooting

- **Permission denied under `/data/workspace`:** render to
  `/config/Home/blender-renders` instead.
- **Lares cannot see Blender tools:** confirm that the MCP server is enabled
  and that its URL ends in `/mcp`.
- **The render exists but is not attached to the conversation:** ask Lares to
  download the Drive file into `/data/workspace`.
- **Lares takes many turns before building anything:** it is probing the
  Blender 5 API. Include the "known facts" block from the prompt above, and
  ask for the scene in a single `execute_blender_code` call.
- **The `.blend` saves but no PNG appears:** the script used
  `bpy.ops.render.render()`, which silently produces nothing over MCP. It must
  use `bpy.ops.render.opengl()` as described in the prompt above.
- **A glow, halo, or atmosphere is missing from the render:** alpha-blended
  materials are dropped by the OpenGL render path. Ask for the effect to be
  built from emission gradients on solid geometry instead.
- **Asked for a video and got nothing, or an error about `FFMPEG`:** Blender
  here cannot encode video. Render an image sequence and encode it outside.
- **Changes do not appear in Blender:** make sure the Blender browser window
  belongs to the same installed app and leave Blender running while Lares
  works.
