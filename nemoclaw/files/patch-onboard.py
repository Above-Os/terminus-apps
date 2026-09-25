#!/usr/bin/env python3
"""Adapt the pinned NemoClaw installer to the Olares DinD build network."""
import pathlib, sys
p = pathlib.Path(sys.argv[1]) / "dist/lib/onboard.js"
if not p.exists():
    raise SystemExit("Build NemoClaw CLI before applying onboarding patch")
s = p.read_text()
marker = "// olares-chart: host-network build"
if marker not in s:
    anchor = '    const envArgs = [formatEnvAssignment("CHAT_UI_URL", chatUiUrl)];'
    if s.count(anchor) != 1:
        raise SystemExit("Unexpected NemoClaw build invocation; refusing patch")
    s = s.replace(anchor, '''    // olares-chart: host-network build
    const olaresImage = "nemoclaw-sandbox-olares:" + buildId;
    const olaresBuild = run(["docker", "build", "--network=host", "-t", olaresImage, buildCtx], { ignoreError: true });
    if (olaresBuild.status !== 0) {
        throw new Error("Olares sandbox image build failed");
    }
    createArgs[createArgs.indexOf("--from") + 1] = olaresImage;
''' + anchor)
    anchor2 = 'function pullAndResolveBaseImageDigest() {'
    if s.count(anchor2) != 1:
        raise SystemExit("Unexpected NemoClaw base-image resolver; refusing patch")
    s = s.replace(anchor2, anchor2 + '''
    // The chart already pulled the configured, versioned base image.
    const configuredBase = process.env.NEMOCLAW_SANDBOX_IMAGE;
    if (configuredBase) {
        const raw = dockerImageInspectFormat("{{json .RepoDigests}}", configuredBase, { ignoreError: true });
        const refs = JSON.parse(raw || "[]");
        const ref = refs.find((item) => item.startsWith(configuredBase.split("@")[0].replace(/:[^/:]+$/, "") + "@sha256:"));
        if (ref) return { digest: ref.split("@")[1], ref };
    }
''')
    p.write_text(s)
if "// olares-chart: import built image" not in s:
    anchor3 = '    createArgs[createArgs.indexOf("--from") + 1] = olaresImage;'
    if s.count(anchor3) != 1:
        raise SystemExit("Unexpected prebuilt image handoff")
    s = s.replace(anchor3, '''    // olares-chart: import built image
    const olaresCluster = process.env.NEMOCLAW_CLUSTER_CTR || "openshell-cluster-" + (process.env.NEMOCLAW_GATEWAY_NAME || "nemoclaw");
    const olaresImport = run(["bash", "-o", "pipefail", "-c",
        "docker save " + shellQuote(olaresImage) + " | docker exec -i " + shellQuote(olaresCluster) +
        " ctr -a /run/k3s/containerd/containerd.sock -n k8s.io images import -"], { ignoreError: true });
    if (olaresImport.status !== 0) throw new Error("Olares sandbox image import failed");
''' + anchor3)
    p.write_text(s)
print("Olares onboarding patch ready")
