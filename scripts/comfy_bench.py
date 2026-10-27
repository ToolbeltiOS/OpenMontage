#!/usr/bin/env python3
"""Render ONE illustration locally and report what it cost in time and RAM.

The point is not the picture, it is the two numbers: seconds per image and
peak resident memory. This machine has 16GB of unified memory and the
schnell fp8 checkpoint is 17.2GB, so the question is whether it runs at all
or swaps.

Peak RAM is sampled from the ComfyUI process itself rather than read off a
summary at the end, because a run that swaps spends its time with a
*smaller* resident set than one that fits, and the number that matters is
how high it got before the OS started paging it out. Pageouts are counted
too, from vm_stat, because that is what "swaps hard" actually means.

    python3 scripts/comfy_bench.py --prompt "..." --out bench.json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
COMFY = Path("/Users/mac/Developer/ComfyUI")
HOST = "http://127.0.0.1:8188"
WORKFLOW = ROOT / "tools" / "_comfyui" / "workflows" / "flux1-schnell-txt2img.json"


def pageouts() -> int:
    out = subprocess.run(["vm_stat"], capture_output=True, text=True).stdout
    m = re.search(r"Pageouts:\s+(\d+)", out)
    return int(m.group(1)) if m else 0


def rss_mb(pid: int) -> float:
    out = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)],
                         capture_output=True, text=True).stdout.strip()
    return float(out) / 1024 if out else 0.0


def wait_ready(proc, timeout: float = 600) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        if proc.poll() is not None:
            return False
        try:
            urllib.request.urlopen(f"{HOST}/system_stats", timeout=3)
            return True
        except Exception:
            time.sleep(2)
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--negative", default="")
    ap.add_argument("--out", default=str(ROOT / "reports" / "comfy_bench.json"))
    ap.add_argument("--steps", type=int, default=4)
    ap.add_argument("--size", type=int, default=1024)
    args = ap.parse_args()

    wf = json.loads(WORKFLOW.read_text())
    wf.pop("_comment", None)
    wf["2"]["inputs"]["text"] = args.prompt
    wf["3"]["inputs"]["text"] = args.negative
    wf["4"]["inputs"]["width"] = args.size
    wf["4"]["inputs"]["height"] = args.size
    wf["5"]["inputs"]["steps"] = args.steps
    wf["5"]["inputs"]["seed"] = 1

    po_before = pageouts()
    proc = subprocess.Popen(
        [str(COMFY / ".venv/bin/python"), "main.py", "--listen", "127.0.0.1",
         "--port", "8188", "--disable-auto-launch"],
        cwd=str(COMFY), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True)

    peak = {"mb": 0.0}
    stop = threading.Event()

    def sample():
        while not stop.is_set():
            try:
                peak["mb"] = max(peak["mb"], rss_mb(proc.pid))
            except Exception:
                pass
            time.sleep(0.5)

    t = threading.Thread(target=sample, daemon=True)
    t.start()

    result = {"prompt": args.prompt, "steps": args.steps, "size": args.size}
    try:
        if not wait_ready(proc):
            result["error"] = "ComfyUI did not come up"
            raise SystemExit(1)
        result["startup_seconds"] = round(time.time() - time.time(), 1)

        cid = str(uuid.uuid4())
        body = json.dumps({"prompt": wf, "client_id": cid}).encode()
        t0 = time.time()
        req = urllib.request.Request(f"{HOST}/prompt", data=body,
                                     headers={"Content-Type": "application/json"})
        pid_resp = json.load(urllib.request.urlopen(req, timeout=60))
        prompt_id = pid_resp["prompt_id"]

        # poll history until the prompt is done
        while True:
            if time.time() - t0 > 3600:
                result["error"] = "timed out after 60 minutes"
                break
            try:
                h = json.load(urllib.request.urlopen(
                    f"{HOST}/history/{prompt_id}", timeout=10))
            except Exception:
                h = {}
            if h.get(prompt_id, {}).get("outputs"):
                result["seconds"] = round(time.time() - t0, 1)
                outs = h[prompt_id]["outputs"]
                imgs = [i for v in outs.values() for i in v.get("images", [])]
                result["images"] = [i["filename"] for i in imgs]
                break
            time.sleep(2)
    finally:
        stop.set()
        result["peak_rss_mb"] = round(peak["mb"], 1)
        result["pageouts_during_run"] = pageouts() - po_before
        proc.terminate()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=1) + "\n")
    for k, v in result.items():
        print(f"  {k}: {v}")
    return 0 if "seconds" in result else 1


if __name__ == "__main__":
    raise SystemExit(main())
