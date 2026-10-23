# ShowDoc PHP security rebuild

Source: https://github.com/star7th/showdoc/tree/5c4e2be155232905dfcc176fd8c5b56e954e92d7 (v3.9.5).
The original v3.9.5 ARM64 image runs PHP 8.3.35; the AMD64 image runs 8.3.36.
This rebuild uses the upstream Dockerfile with its base pinned to the fixed
multiarch webdevops/php-nginx manifest. The published image has PHP 8.3.36 on
both AMD64 and ARM64. The Chart supplies the non-root runtime configuration.

Download the upstream archive from
https://codeload.github.com/star7th/showdoc/tar.gz/5c4e2be155232905dfcc176fd8c5b56e954e92d7
and verify SHA256 `1c0f3c23feb27ea7af20c229410405f26c0993edb4ec1617e1e40062480db6a8`.
Extract it, use the extracted directory as the build context, and use this
Dockerfile with `docker buildx build --platform linux/amd64,linux/arm64 -f
/path/to/this/Dockerfile --tag YOUR_NEW_TAG --push .`. Do not use the Chart
directory as the build context. Never reuse an existing release tag.

Published source: `harveyff/showdoc:v3.9.5-php8.3.36-20261023`.
Verified mirror: `beclab/harveyff-showdoc:v3.9.5-php8.3.36-20261023`.
The source OCI index is
`sha256:e4d61b8f8978fcf38d5daa5510cd6bed9515354d5ce6caad99acaaa4bfdf9773`.
Mirror conversion changes the index; platform config digests and layers match.
Upstream npm dependencies are retained. The build reports existing npm audit
findings; this rebuild does not claim to fix all application dependencies.
