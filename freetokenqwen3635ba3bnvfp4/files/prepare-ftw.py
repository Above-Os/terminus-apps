#!/opt/venv/bin/python
"""Prepare a persistent FTW checkpoint, then replace this process with ft serve."""

import argparse
import fcntl
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time


def log(message):
    print(f"[ftw] {message}", file=sys.stderr, flush=True)


def valid_checkpoint(path):
    """Reject interrupted conversions and missing/truncated shards, without reading GBs."""
    try:
        index = json.loads((path / "freetoken_weight.json").read_text())
        return (
            (path / "config.json").is_file()
            and bool(index["tensors"])
            and bool(index["shards"])
            and all(
                Path(shard["file"]).name == shard["file"]
                and (path / shard["file"]).stat().st_size == shard["nbytes"]
                for shard in index["shards"]
            )
        )
    except (OSError, ValueError, KeyError, TypeError):
        return False


def prepare(source, cache, identity, convert):
    """Publish only complete conversions; serialize conversion across engine relaunches."""
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:24]
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / key
    stage = cache / f"{key}.partial"
    with (cache / ".conversion.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if (target / ".complete").is_file() and valid_checkpoint(target):
            log(f"reusing {target}")
            return target
        # These are only this helper's derived files, never the shared HF source.
        for stale in (stage, target):
            if stale.exists():
                shutil.rmtree(stale)
        # This NVFP4 preset remains packed in FTW. Reserve source size + 2 GiB
        # for alignment/metadata; do not start a conversion on an already full disk.
        required = sum(p.stat().st_size for p in source.glob("*.safetensors")) + (2 << 30)
        if shutil.disk_usage(cache).free < required:
            raise RuntimeError(f"FTW conversion needs at least {required / (1 << 30):.1f} GiB free in {cache}")
        started = time.monotonic()
        log(f"converting {source} -> {stage}")
        try:
            convert(stage)
            if not valid_checkpoint(stage):
                raise RuntimeError("ft checkpoint returned an incomplete FTW checkpoint")
            # Persist the files before publishing the completion marker and directory.
            for path in stage.rglob("*"):
                if path.is_file():
                    with path.open("rb") as data:
                        os.fsync(data.fileno())
            with (stage / ".complete").open("w") as marker:
                json.dump(identity, marker, sort_keys=True)
                marker.flush()
                os.fsync(marker.fileno())
            stage.rename(target)
        except BaseException:
            shutil.rmtree(stage, ignore_errors=True)
            raise
        log(f"conversion completed in {time.monotonic() - started:.1f}s: {target}")
        return target


def main():
    ft_bin, model_path, *serve_args = sys.argv[1:]
    source = Path(model_path).resolve()
    model = source
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--dtype", default="bfloat16")
    parser.add_argument("--quant-backend")
    parser.add_argument("--moe-strategy", default="auto")
    options, _ = parser.parse_known_args(serve_args)
    enabled = os.environ.get("FREETOKEN_FTW_ENABLED", "true").lower() == "true"
    if enabled and options.moe_strategy in ("auto", "offload", "hybrid"):
        import torch
        import freetoken

        # Source snapshot, relevant converter/runtime implementation, dtype, kernel
        # selection and GPU capability define compatibility. Context/KV settings do not.
        package = Path(freetoken.__file__).parent
        code_hash = hashlib.sha256()
        for relative in ("checkpoint", "models", "layers/quantization", "moe"):
            for path in sorted((package / relative).rglob("*.py")):
                code_hash.update(str(path.relative_to(package)).encode())
                code_hash.update(path.read_bytes())
        identity = {
            "schema": 1,
            "source": str(source),
            "files": [(str(p.relative_to(source)), p.stat().st_size, p.stat().st_mtime_ns)
                      for p in sorted(source.rglob("*")) if p.is_file()],
            "freetoken": importlib.metadata.version("freetoken"),
            "implementation": code_hash.hexdigest(),
            "capability": torch.cuda.get_device_capability(),
            "dtype": options.dtype,
            "quant_backend": options.quant_backend,
        }

        def convert(stage):
            command = [ft_bin, "checkpoint", "--model", str(source), "--out", str(stage),
                       "--dtype", options.dtype, "--moe-backend", "offload"]
            if options.quant_backend:
                command += ["--quant-backend", options.quant_backend]
            # A converter must not survive Model Console stopping this engine PID.
            child = subprocess.Popen(command)

            def stop(signum, _frame):
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
                raise SystemExit(128 + signum)

            old = {sig: signal.signal(sig, stop) for sig in (signal.SIGTERM, signal.SIGINT)}
            try:
                if child.wait() != 0:
                    raise RuntimeError("ft checkpoint failed; refusing to serve a partial checkpoint")
            finally:
                for sig, handler in old.items():
                    signal.signal(sig, handler)

        model = prepare(source, Path(os.environ["FREETOKEN_FTW_CACHE"]), identity, convert)
    elif enabled:
        log(f"moe-strategy={options.moe_strategy}: using original checkpoint")
    os.execv(ft_bin, [ft_bin, "serve", "--model", str(model), *serve_args])


if __name__ == "__main__":
    main()
