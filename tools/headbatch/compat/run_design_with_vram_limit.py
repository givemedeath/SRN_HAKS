"""Run one headbatch design with sampled whole-device VRAM supervision.

Invoke through headbatch env with WORKSPACE HEAD SEED. Workspace comfy settings
supply memoryLimitBytes and optionally gpuIndex (default 0). Uses nvidia-smi.
A measured limit breach interrupts only this design's identified prompt.
Sampling is evidence of observed use, not an allocator-level hard limit.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.request

RUNNER = Path(__file__).resolve().parents[1]/"run_headbatch.py"
sys.path.insert(0, str(RUNNER.parent))
from workspace import Workspace
from launcher import free_memory_gb


def request(endpoint, route, data=None):
    body = None if data is None else json.dumps(data).encode()
    query = urllib.request.Request(endpoint+route, body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(query, timeout=10) as reply:
        return json.load(reply) if data is None else reply.read()


def design_prompts(rows, base, input_root):
    found = []
    for row in rows:
        for node in row[2].values():
            prefix = node.get("inputs", {}).get("filename_prefix", "")
            parts = prefix.split("/")
            if (len(parts) == 3 and parts[0] == "headkit-design" and parts[2] == base
                    and len(parts[1]) == 32 and all(c in "0123456789abcdef" for c in parts[1])
                    and (input_root/parts[0]/parts[1]).is_dir()):
                found.append(row[1])
                break
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace")
    parser.add_argument("head")
    parser.add_argument("seed", type=int)
    args = parser.parse_args()
    ws = Workspace.load(args.workspace)
    race = ws.head_ids()[args.head][0]
    limit = ws.data["comfy"]["memoryLimitBytes"]
    if type(limit) is not int or limit <= 0:
        raise ValueError("Positive integer memoryLimitBytes required")
    ram_floor = float(ws.data["comfy"].get("minimumFreeRAMGiB", 0))
    if ram_floor < 0:
        raise ValueError("minimumFreeRAMGiB must be nonnegative")
    endpoint = ws.data["comfy"]["url"].rstrip("/")
    bindings = json.loads(ws.require("designBindings").read_text(encoding="utf-8-sig"))
    config = Path(bindings["comfyStartupConfig"])
    baseline = request(endpoint, "/headkit/preparation-identity")["runtimeIdentity"]
    expected = {"path": str(config.resolve()), "sha256": hashlib.sha256(config.read_bytes()).hexdigest()}
    if baseline["session"]["configuration"] != expected:
        raise ValueError("Live session differs from the bound startup configuration")
    initial = request(endpoint, "/queue")
    if initial["queue_running"] or initial["queue_pending"]:
        raise ValueError("GPU queue is busy")
    base = f"{args.head}-s{args.seed}"
    destination = ws.root/"runtime/vram"/base
    destination.mkdir(parents=True, exist_ok=False)
    index = str(ws.data["comfy"].get("gpuIndex", 0))
    sampler = subprocess.Popen(["nvidia-smi", "-i", index, "--query-gpu=memory.used",
                                "--format=csv,noheader,nounits", "-lms", "250"],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    state = {"peak": 0, "last": 0, "error": None, "minimumRAMGiB": None}
    lock = threading.Lock()
    stopped = threading.Event()
    def sample():
        try:
            with (destination/"samples.csv").open("x", newline="") as output:
                writer = csv.writer(output)
                writer.writerow(("utc", "deviceUsedMiB", "availableRAMGiB"))
                for line in sampler.stdout:
                    value = int(line.strip()) * 1048576
                    available = free_memory_gb()
                    with lock:
                        state["minimumRAMGiB"] = available if state["minimumRAMGiB"] is None else min(state["minimumRAMGiB"], available)
                        state["peak"] = max(state["peak"], value)
                        state["last"] = time.monotonic()
                    writer.writerow((datetime.now(timezone.utc).isoformat(), value//1048576, round(available, 3)))
                    output.flush()
        except Exception as error:
            with lock:
                state["error"] = str(error)
        finally:
            stopped.set()
    worker = threading.Thread(target=sample, daemon=True)
    worker.start()
    child = None
    owned = set()
    interrupted = set()
    violated = False
    reason = None
    try:
        deadline = time.monotonic()+10
        while not state["last"] and not stopped.is_set() and time.monotonic() < deadline:
            time.sleep(.1)
        if not state["last"] or state["peak"] > limit or state["minimumRAMGiB"] < ram_floor:
            raise ValueError("Memory sampler unavailable or current memory violates the configured budgets")
        command = [sys.executable, "-B", str(RUNNER), "--workspace", str(ws.file),
                   "design", race, f"{args.head}:{args.seed}:1"]
        with (destination/"dispatch.log").open("x") as output:
            child = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT)
            while child.poll() is None:
                with lock:
                    reading = dict(state)
                if (reading["peak"] > limit or reading["minimumRAMGiB"] < ram_floor
                        or reading["error"] or stopped.is_set() or time.monotonic()-reading["last"] > 5):
                    violated = True
                    reason = reading["error"] or "VRAM/RAM budget exceeded or monitoring stopped"
                try:
                    queue = request(endpoint, "/queue")
                    ids = design_prompts(queue["queue_running"], base, Path(bindings["comfyInput"]))
                    owned.update(ids)
                    if violated:
                        for prompt in set(ids)-interrupted:
                            request(endpoint, "/interrupt", {"prompt_id": prompt})
                            interrupted.add(prompt)
                except OSError as error:
                    if violated:
                        print("Waiting to reconcile owned prompt:", str(error), flush=True)
                time.sleep(.5)
            code = child.returncode
    finally:
        sampler.terminate()
        sampler.wait(timeout=10)
        worker.join(timeout=10)
        report = {"limitBytes": limit, "sampledPeakDeviceBytes": state["peak"], "limitBreached": state["peak"] > limit,
                  "minimumAvailableRAMGiB": state["minimumRAMGiB"], "minimumFreeRAMGiB": ram_floor,
                  "monitoringFailed": state["error"], "promptIds": sorted(owned), "interrupted": sorted(interrupted),
                  "exitCode": child.returncode if child is not None else None, "reason": reason,
                  "samplingPeriodMilliseconds": 250}
        (destination/"summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report), flush=True)
    return 1 if violated or state["peak"] > limit or state["minimumRAMGiB"] < ram_floor or state["error"] else code


if __name__ == "__main__":
    raise SystemExit(main())
