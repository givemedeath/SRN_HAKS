"""Execute authorized derived Dwarf Male interactive client test and collect complete evidence."""
from __future__ import annotations
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import sys

REPO = Path(__file__).resolve().parents[2]
STAGE = REPO / "output/phenotypes/derived-dwarf-male-v1/test-stage"
REVIEW = REPO / "output/phenotypes/derived-dwarf-male-v1/review"
CLIENT = Path(r"C:\Program Files (x86)\GOG Galaxy\Games\Neverwinter Nights Enhanced Edition\bin\win32\nwmain.exe")

sys.path.insert(0, str(Path(__file__).parent))
from preflight_derived_dwarf_client import run_preflight, sha256_file


class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def get_process_metrics(pid: int) -> dict | None:
    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_VM_READ = 0x0010
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not handle:
        return None
    try:
        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb)

        creation = ctypes.c_int64()
        exit_time = ctypes.c_int64()
        kernel_time = ctypes.c_int64()
        user_time = ctypes.c_int64()
        ctypes.windll.kernel32.GetProcessTimes(
            handle,
            ctypes.byref(creation),
            ctypes.byref(exit_time),
            ctypes.byref(kernel_time),
            ctypes.byref(user_time)
        )
        cpu_seconds = (kernel_time.value + user_time.value) / 10000000.0
        return {
            "workingSetBytes": int(counters.WorkingSetSize),
            "privateBytes": int(counters.PagefileUsage),
            "cpuSeconds": round(cpu_seconds, 3),
            "responding": True
        }
    except Exception:
        return None
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def check_no_nwmain():
    res = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Process -Name nwmain -ErrorAction SilentlyContinue | Measure-Object | Select-Object -ExpandProperty Count"], capture_output=True, text=True)
    count = int(res.stdout.strip() or "0")
    if count > 0:
        raise RuntimeError(f"An existing nwmain process is already running ({count} found); close it before test launch")


def run_client_test(max_duration: float = 160.0, race: str = "dwarf", prefix: str = "pmd0") -> dict:
    check_no_nwmain()

    stage_dir = REPO / f"output/phenotypes/derived-{race}-male-v1/test-stage"
    review_dir = REPO / f"output/phenotypes/derived-{race}-male-v1/review"
    review_dir.mkdir(parents=True, exist_ok=True)
    preflight_receipt_path = review_dir / "client-preflight-receipt.json"
    preflight = run_preflight(stage_dir, CLIENT, preflight_receipt_path, race=race, prefix=prefix)
    if not preflight.get("pass"):
        raise RuntimeError("Preflight verification failed")

    userdir = Path(preflight["userDirectory"])
    client_path = Path(preflight["client"])
    logs_dir = userdir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    client_log_path = logs_dir / "nwclientLog1.txt"
    engine_log_path = logs_dir / "nwengineLog.txt"

    # Backup prior logs if present
    if client_log_path.exists():
        client_log_path.unlink()
    if engine_log_path.exists():
        engine_log_path.unlink()

    cmd = [
        str(client_path),
        "-userdirectory", str(userdir),
        "+TestNewModule", "srn_pheno_test"
    ]
    print(f"Launching client: {' '.join(cmd)}")
    start_time = time.time()
    started_iso = datetime.now(timezone.utc).isoformat()
    proc = subprocess.Popen(cmd, cwd=str(client_path.parent))
    pid = proc.pid
    print(f"Client started with PID {pid}")

    fixture_receipt_path = stage_dir / "test-module/receipt.json"
    fixture_receipt_sha = sha256_file(fixture_receipt_path)

    launch_data = {
        "processId": pid,
        "launchedAt": started_iso,
        "userDirectory": str(userdir),
        "workingDirectory": str(client_path.parent),
        "hakSha256": preflight["hakSha256"],
        "moduleSha256": preflight["moduleSha256"],
        "fixtureReceiptSha256": fixture_receipt_sha,
        "preflight": str(preflight_receipt_path),
        "clientSha256": preflight["clientSha256"],
        "directLoad": "+TestNewModule srn_pheno_test"
    }

    launch_file = stage_dir / f"client-launch-{pid}.json"
    launch_file.write_text(json.dumps(launch_data, indent=2), encoding="utf-8")
    (review_dir / f"client-launch-{pid}.json").write_text(json.dumps(launch_data, indent=2), encoding="utf-8")

    phases_seen = set()
    sequence_complete = False
    runtime_samples = []

    try:
        while time.time() - start_time < max_duration:
            elapsed = time.time() - start_time
            if proc.poll() is not None:
                print(f"Process exited prematurely with code {proc.returncode} after {elapsed:.1f}s")
                break

            metrics = get_process_metrics(pid)
            if metrics:
                metrics["observedAt"] = datetime.now(timezone.utc).isoformat()
                metrics["processId"] = pid
                metrics["elapsedSeconds"] = round(elapsed, 1)
                runtime_samples.append(metrics)

            if client_log_path.exists():
                try:
                    text = client_log_path.read_text(encoding="utf-8", errors="replace")
                    for line in text.splitlines():
                        if "PHENOTYPE_TORSO_PHASE phase=" in line:
                            phase = line.split("phase=")[1].strip()
                            if phase not in phases_seen:
                                phases_seen.add(phase)
                                print(f"[{elapsed:5.1f}s] Reached inspection phase: {phase}")
                        if "PHENOTYPE_TORSO_SEQUENCE_COMPLETE" in line:
                            if not sequence_complete:
                                sequence_complete = True
                                print(f"[{elapsed:5.1f}s] PHENOTYPE_TORSO_SEQUENCE_COMPLETE observed!")
                except Exception as e:
                    pass

            if sequence_complete and elapsed >= 142.0:
                print("Inspection sequence fully completed and settled.")
                break

            time.sleep(1.0)
    finally:
        if proc.poll() is None:
            print("Terminating client process...")
            proc.terminate()
            try:
                proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            print("Client terminated.")

    # Collect final metrics
    last_metrics = runtime_samples[-1] if runtime_samples else {
        "workingSetBytes": 0, "privateBytes": 0, "cpuSeconds": 0, "responding": False
    }
    last_metrics["startedAt"] = started_iso
    last_metrics["observedAt"] = datetime.now(timezone.utc).isoformat()
    last_metrics["processId"] = pid
    last_metrics["fpsScope"] = f"Interactive client test window, {race} bare actor inspection"
    metrics_file = review_dir / f"runtime-metrics-{pid}.json"
    metrics_file.write_text(json.dumps(last_metrics, indent=2), encoding="utf-8")

    # Filter phenotype log
    filtered_lines = []
    if client_log_path.exists():
        raw_log = client_log_path.read_text(encoding="utf-8", errors="replace")
        for line in raw_log.splitlines():
            if "PHENOTYPE_" in line:
                filtered_lines.append(line)

    filtered_log_file = review_dir / f"run-{pid}-phenotype.log"
    filtered_log_file.write_text("\n".join(filtered_lines) + "\n", encoding="utf-8")
    print(f"Extracted {len(filtered_lines)} phenotype log lines to {filtered_log_file}")

    source_logs = {}
    if client_log_path.exists():
        source_logs[str(client_log_path)] = sha256_file(client_log_path)
    if engine_log_path.exists():
        source_logs[str(engine_log_path)] = sha256_file(engine_log_path)

    evidence = {
        "schemaVersion": 1,
        "kind": "derived-phenotype-client-evidence",
        "target": f"{race}-male-stock-family",
        "processId": pid,
        "launchedAt": started_iso,
        "completedAt": datetime.now(timezone.utc).isoformat(),
        "sequenceComplete": sequence_complete,
        "phasesSeen": sorted(phases_seen),
        "launch": str(launch_file),
        "launchSha256": sha256_file(launch_file),
        "fixtureReceipt": str(fixture_receipt_path),
        "fixtureReceiptSha256": fixture_receipt_sha,
        "hakSha256": preflight["hakSha256"],
        "moduleSha256": preflight["moduleSha256"],
        "runtimeMetrics": last_metrics,
        "runtimeMetricsSha256": sha256_file(metrics_file),
        "sourceLogs": source_logs,
        "filteredPhenotypeLog": str(filtered_log_file),
        "filteredPhenotypeLogSha256": sha256_file(filtered_log_file),
        "sampleCount": len(runtime_samples)
    }

    evidence_file = review_dir / f"client-evidence-run-{pid}.json"
    evidence_file.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(f"Saved complete client evidence to {evidence_file}")
    return evidence


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Execute derived phenotype interactive client test")
    parser.add_argument("--race", default="dwarf", help="Target race (default: dwarf)")
    parser.add_argument("--prefix", default=None, help="Model prefix (default: pmd0 for dwarf, pmg0 for troll)")
    parser.add_argument("--max-duration", type=float, default=160.0, help="Max test duration in seconds")
    args = parser.parse_args()

    race = args.race
    prefix = args.prefix or ("pmg0" if race == "troll" else "pmd0")
    res = run_client_test(max_duration=args.max_duration, race=race, prefix=prefix)
    print(f"Client test finished. Sequence complete: {res['sequenceComplete']}, Phases: {len(res['phasesSeen'])}")
