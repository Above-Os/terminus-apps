# English validation

Tested on 2026-09-24 on Olares 1.12.7-20260908, Linux amd64, using the r9 image.
The dedicated demo project was `Market-Studio-English-20260924-v2`.
Existing user projects were not changed.

## Passed

- MCP initialize, discovery of seven tools, help and status.
- Create a 1280x720, 30 fps project; import four original abstract images and
  an original music track; trim clips and arrange multiple tracks.
- Eight English text clips, fade animations, cross-fade transitions, scale
  keyframes and music volume/fades.
- Render four preview frames and a 16-second H.264/AAC MP4; probe confirms
  1280x720, 30 fps and stereo 48 kHz audio. Machine report is in `tests/`.
- Close and reopen the project after restarting the CLI editing session.
- Open the same project in the English desktop UI and inspect the preview.
- Export through the actual English GUI at 1920x1080, 30 fps, H.264,
  Balanced quality. The UI reported **Exported**.

## Listing assets

The icon is the real upstream v0.2.2 Concat mark. The two 1440x900 images use
actual screenshots captured from the running Olares instance. Background and
typography were generated with the built-in image tool; original UI pixels
were composited back with Pillow. No generated UI is shipped.
Copy follows the upstream README's free/open-source positioning and the
observed export controls. Both images use the same top-text/bottom-image layout.

- Icon: https://cdn.olares.com/images/2026/09/ab76a2eb1f91773844b5d97728d0f22d.png
- Editor: https://cdn.olares.com/images/2026/09/499e2f54339f5605a908eabca162ba74.png
- Export: https://cdn.olares.com/images/2026/09/368150b942f17ca45a5996783d3e9b04.png

## Scope

Only amd64 CPU rendering was tested. ARM64, GPU and optional AI model features
are not claimed. This package retains upstream's Beta status.
The image was already deployed; this publication changes chart metadata and
adds listing assets, source disclosure and documentation.

## Final publication package

Chart 0.2.4 passed `olares-cli chart lint --with-security-context --with-rbac`
and was uploaded to Local Sources / Upload, then upgraded successfully to
`running` on the test instance. The pod remained 3/3 Ready with zero restarts.
Post-upgrade `tests/smoke.py` confirmed GUI HTTP 200, health, authenticated API,
MCP tool discovery, desktop restoration, and HTTP 401 without a bearer token.
All three CDN URLs returned HTTP 200 with image/png content type.
