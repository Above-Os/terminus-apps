#!/bin/bash
# Image versions match beclab/harveyff-openshell-cluster:v1.17.
# Import through DinD because the nested k3s network cannot reach registries.
set -u
: "${NEMOCLAW_OPENSHELL_VERSION:=v0.0.36}"
cache=/workspace/.nemoclaw-k3s-images
mkdir -p "$cache"
images=(rancher/mirrored-pause:3.6 rancher/mirrored-coredns-coredns:1.14.2 rancher/klipper-helm:v0.9.14-build20260309 rancher/local-path-provisioner:v0.0.35 rancher/mirrored-metrics-server:v0.8.1 registry.k8s.io/agent-sandbox/agent-sandbox-controller:v0.1.0 rancher/mirrored-library-busybox:1.37.0 ghcr.io/nvidia/openshell/gateway:${NEMOCLAW_OPENSHELL_VERSION#v})
for img in "${images[@]}"; do
 ( name=$(echo "$img" | tr '/:' '__'); [ -s "$cache/$name.tar" ] && exit 0; if docker image inspect "$img" >/dev/null 2>&1 || docker pull "$img"; then if docker save "$img" -o "$cache/$name.tmp" && mv "$cache/$name.tmp" "$cache/$name.tar"; then echo "SAVED $img"; fi; fi ) &
done
wait
for attempt in $(seq 1 180); do
 ctr=$(docker ps --format '{{.Names}}' | grep '^openshell-cluster-' | head -1)
 if [ -n "$ctr" ] && docker exec "$ctr" test -S /run/k3s/containerd/containerd.sock; then
   for archive in "$cache"/*.tar; do
     [ -f "$archive" ] || continue
     name=$(basename "$archive")
     marker="$cache/$ctr-$(docker inspect --format '{{.Id}}' "$ctr")-$name.done"
     [ -f "$marker" ] && continue
     if docker exec -i "$ctr" ctr -a /run/k3s/containerd/containerd.sock -n k8s.io images import - < "$archive"; then
       for ref in $(tar -xOf "$archive" manifest.json | python3 -c 'import json,sys; print(" ".join(t for m in json.load(sys.stdin) for t in m.get("RepoTags", [])))'); do
         case "$ref" in ghcr.io/*|registry.k8s.io/*|docker.io/*) ;; *) ref="docker.io/$ref" ;; esac
         docker exec "$ctr" ctr -a /run/k3s/containerd/containerd.sock -n k8s.io images label "$ref" io.cri-containerd.pinned=pinned || true
       done
       touch "$marker"
     fi
   done
 fi
 sleep 5
done
