"""Execute authorized derived Dwarf Male interactive client test and collect complete evidence."""
from __future__ import annotations
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import sys
import uuid

REPO = Path(__file__).resolve().parents[2]
STAGE = REPO / "output/phenotypes/derived-dwarf-male-v1/test-stage"
REVIEW = REPO / "output/phenotypes/derived-dwarf-male-v1/review"
DEFAULT_CLIENT = Path(r"C:\Program Files (x86)\GOG Galaxy\Games\Neverwinter Nights Enhanced Edition\bin\win32\nwmain.exe")
CLIENT = DEFAULT_CLIENT

sys.path.insert(0, str(Path(__file__).parent))
from preflight_derived_dwarf_client import run_preflight, sha256_file


def resolve_client(explicit: Path | None = None, game_root: Path | None = None) -> Path:
    if explicit is not None:
        p = Path(explicit).resolve()
        if p.exists():
            return p
        raise FileNotFoundError(f"Specified client binary does not exist: {explicit}")

    env_client = os.environ.get("NWN_CLIENT")
    if env_client and Path(env_client).exists():
        return Path(env_client).resolve()

    # Check local runtime bindings if present
    for bindings_path in [
        REPO / ".tools/runtime_bindings.json",
        REPO / ".tools/runtime-bindings.json",
        REPO / "runtime_bindings.json",
    ]:
        if bindings_path.exists():
            try:
                bindings = json.loads(bindings_path.read_text(encoding="utf-8"))
                candidate = bindings.get("client") or bindings.get("nwmain") or bindings.get("NWN_CLIENT")
                if candidate and Path(candidate).exists():
                    return Path(candidate).resolve()
            except Exception:
                pass

    if game_root is not None:
        for candidate in [
            game_root / "bin/win32/nwmain.exe",
            game_root / "bin/linux-x86/nwmain",
            game_root / "nwmain.exe",
            game_root / "bin/win32/nwserver.exe",
        ]:
            if candidate.exists():
                return candidate.resolve()

    env_root = os.environ.get("NWN_ROOT") or os.environ.get("NWN_GAME_ROOT")
    if env_root:
        for candidate in [
            Path(env_root) / "bin/win32/nwmain.exe",
            Path(env_root) / "bin/linux-x86/nwmain",
            Path(env_root) / "nwmain.exe",
            Path(env_root) / "bin/win32/nwserver.exe",
        ]:
            if candidate.exists():
                return candidate.resolve()

    for candidate in [
        DEFAULT_CLIENT,
        Path(r"C:\Program Files (x86)\Steam\steamapps\common\Neverwinter Nights\bin\win32\nwmain.exe"),
    ]:
        if candidate.exists():
            return candidate.resolve()

    raise FileNotFoundError(
        "NWN client binary not found. Please provide --client, set NWN_CLIENT, or configure local runtime bindings."
    )


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


def scan_log_for_errors(log_path: Path) -> list[str]:
    """Scan client or engine log for relevant runtime errors.

    Detects model-loading failures, missing resource/texture/file errors,
    script runtime errors, fatal errors, and assertion failures, while
    allowing benign notices (such as non-fatal empty field label in MODULE.ifo).
    """
    if not log_path.is_file():
        return []

    error_patterns = [
        re.compile(r"\b(?:error|fatal|crash|assertion failed)\b", re.IGNORECASE),
        re.compile(r"\b(?:model|texture|resource)\b.*?\b(?:not found|failed to load|cannot find|missing)\b", re.IGNORECASE),
        re.compile(r"\b(?:failed to load|missing)\b.*?\b(?:model|texture|resource)\b", re.IGNORECASE),
        re.compile(r"\bscript\b.*?\b(?:error|failed)\b", re.IGNORECASE),
        re.compile(r"\bRuntime Error:\b", re.IGNORECASE),
    ]
    ignorable_patterns = [
        re.compile(r"empty field label in module\.ifo", re.IGNORECASE),
        re.compile(r"nonfatal", re.IGNORECASE),
    ]

    detected = []
    text = log_path.read_text(encoding="utf-8", errors="replace")
    for line_num, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if any(ign.search(stripped) for ign in ignorable_patterns):
            continue
        if any(pat.search(stripped) for pat in error_patterns):
            detected.append(f"[{log_path.name}:{line_num}] {stripped}")

    return detected


def check_no_nwmain():
    res = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Process -Name nwmain -ErrorAction SilentlyContinue | Measure-Object | Select-Object -ExpandProperty Count"], capture_output=True, text=True)
    count = int(res.stdout.strip() or "0")
    if count > 0:
        raise RuntimeError(f"An existing nwmain process is already running ({count} found); close it before test launch")


def preserve_file(source: Path, destination: Path) -> Path:
    """Keep exact source bytes in an exclusive, independently verifiable snapshot."""
    before = sha256_file(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as out:
        out.write(source.read_bytes())
    if sha256_file(destination) != before or sha256_file(source) != before:
        raise RuntimeError(f"Source changed during evidence snapshot: {source}")
    return destination


def run_client_test(
    max_duration: float = 160.0,
    race: str = "dwarf",
    prefix: str = "pmd0",
    client: Path | None = None,
    equipment_target: bool = False
) -> dict:
    check_no_nwmain()
    client_bin = resolve_client(client)

    stage_dir = REPO / f"output/phenotypes/derived-{race}-male-v1/test-stage"
    review_dir = REPO / f"output/phenotypes/derived-{race}-male-v1/review"
    review_dir.mkdir(parents=True, exist_ok=True)
    review_dir = review_dir / ("client-run-" + uuid.uuid4().hex)
    review_dir.mkdir(exist_ok=False)
    preflight_receipt_path = review_dir / "client-preflight-receipt.json"
    preflight = run_preflight(stage_dir, client_bin, preflight_receipt_path, race=race, prefix=prefix)
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
        preserve_file(client_log_path, review_dir / "previous-logs" / client_log_path.name)
        client_log_path.unlink()
    if engine_log_path.exists():
        preserve_file(engine_log_path, review_dir / "previous-logs" / engine_log_path.name)
        engine_log_path.unlink()

    fixture_receipt_path = stage_dir / "test-module/receipt.json"
    fixture_receipt_path = preserve_file(fixture_receipt_path, review_dir / "fixture-receipt.json")
    fixture_receipt_sha = sha256_file(fixture_receipt_path)
    fixture_receipt_data = {}
    if fixture_receipt_path.exists():
        try:
            fixture_receipt_data = json.loads(fixture_receipt_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    is_equipment_run = bool(
        equipment_target or
        fixture_receipt_data.get("cameraEquipmentTarget") or
        fixture_receipt_data.get("configuration", {}).get("cameraEquipmentTarget")
    )

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
        "directLoad": "+TestNewModule srn_pheno_test",
        "equipmentRun": is_equipment_run
    }

    launch_file = review_dir / f"client-launch-{pid}.json"
    launch_file.write_text(json.dumps(launch_data, indent=2), encoding="utf-8")

    phases_seen = set()
    sequence_complete = False
    camera_set = False
    equipment_worn = False
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
                        if is_equipment_run:
                            if "PHENOTYPE_CAMERA_SET" in line:
                                camera_set = True
                                if "camera-set" not in phases_seen:
                                    phases_seen.add("camera-set")
                                    print(f"[{elapsed:5.1f}s] PHENOTYPE_CAMERA_SET observed!")
                            if "PHENOTYPE_EQUIPMENT_WORN" in line:
                                equipment_worn = True
                                if "equipment-worn" not in phases_seen:
                                    phases_seen.add("equipment-worn")
                                    print(f"[{elapsed:5.1f}s] PHENOTYPE_EQUIPMENT_WORN observed!")
                            if camera_set and equipment_worn and not sequence_complete:
                                sequence_complete = True
                                print(f"[{elapsed:5.1f}s] Equipment inspection sequence complete!")
                        else:
                            if "PHENOTYPE_TORSO_PHASE phase=" in line:
                                phase = line.split("phase=")[1].strip()
                                if phase not in phases_seen:
                                    phases_seen.add("phase=" + phase)
                                    print(f"[{elapsed:5.1f}s] Reached inspection phase: {phase}")
                            if "PHENOTYPE_TORSO_SEQUENCE_COMPLETE" in line:
                                if not sequence_complete:
                                    sequence_complete = True
                                    print(f"[{elapsed:5.1f}s] PHENOTYPE_TORSO_SEQUENCE_COMPLETE observed!")
                except Exception:
                    pass

            if is_equipment_run and sequence_complete and elapsed >= 25.0:
                print("Equipment inspection sequence fully completed and settled.")
                break
            elif not is_equipment_run and sequence_complete and elapsed >= 142.0:
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
    last_metrics["fpsScope"] = (
        f"Interactive client test window, {race} equipped actor inspection"
        if is_equipment_run else
        f"Interactive client test window, {race} bare actor inspection"
    )
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

    missing_logs = [str(log_p.name) for log_p in [client_log_path, engine_log_path] if not log_p.exists()]
    if missing_logs:
        raise RuntimeError(
            f"Client test incomplete for {race}: missing required log file(s): {', '.join(missing_logs)}"
        )

    source_logs = {}
    detected_errors = []
    for log_p in [client_log_path, engine_log_path]:
        saved_log = preserve_file(log_p, review_dir / "source-logs" / log_p.name)
        source_logs[str(saved_log)] = sha256_file(saved_log)
        detected_errors.extend(scan_log_for_errors(saved_log))

    evidence = {
        "schemaVersion": 1,
        "kind": "derived-phenotype-client-evidence",
        "mode": "equipment-inspection" if is_equipment_run else "torso-inspection",
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
        "runtimeMetricsFile": str(metrics_file),
        "runtimeMetricsSha256": sha256_file(metrics_file),
        "sourceLogs": source_logs,
        "runtimeLogErrors": detected_errors,
        "cleanLogsVerified": len(detected_errors) == 0 and len(source_logs) == 2,
        "filteredPhenotypeLog": str(filtered_log_file),
        "filteredPhenotypeLogSha256": sha256_file(filtered_log_file),
        "sampleCount": len(runtime_samples)
    }
    if is_equipment_run:
        evidence["equipmentWornObserved"] = equipment_worn
        evidence["cameraSetObserved"] = camera_set

    evidence_file = review_dir / f"client-evidence-run-{pid}.json"
    evidence_file.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(f"Saved complete client evidence to {evidence_file}")

    if is_equipment_run:
        if not sequence_complete or not (camera_set and equipment_worn):
            raise RuntimeError(
                f"Equipment client test incomplete for {race}: sequenceComplete={sequence_complete}, "
                f"cameraSet={camera_set}, equipmentWorn={equipment_worn}"
            )
    else:
        REQUIRED_INSPECTION_PHASES = {
            "phase=front-idle", "phase=front-raised", "phase=side-idle",
            "phase=rear-idle", "phase=rear-raised", "phase=rear-crouch", "phase=complete-front-idle"
        }
        missing_phases = REQUIRED_INSPECTION_PHASES - phases_seen
        if not sequence_complete or missing_phases:
            raise RuntimeError(
                f"Client test incomplete for {race}: sequenceComplete={sequence_complete}, "
                f"missing required phases: {sorted(missing_phases)}"
            )

    if detected_errors or not evidence["cleanLogsVerified"]:
        err_sample = "\n  ".join(detected_errors[:10]) if detected_errors else "Failed clean log verification"
        raise RuntimeError(
            f"Client test rejected for {race}: detected runtime errors or invalid log state in logs:\n  {err_sample}"
        )

    return evidence


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Execute derived phenotype interactive client test")
    parser.add_argument("--race", default="dwarf", help="Target race (default: dwarf)")
    parser.add_argument("--prefix", default=None, help="Model prefix (default: pmd0 for dwarf, pmg0 for troll)")
    parser.add_argument("--client", type=Path, default=None, help="Path to NWN client executable (nwmain.exe)")
    parser.add_argument("--equipment-target", action="store_true", help="Expect equipment inspection run rather than bare torso sequence")
    parser.add_argument("--max-duration", type=float, default=160.0, help="Max test duration in seconds")
    args = parser.parse_args()

    race = args.race
    default_prefixes = {"dwarf": "pmd0", "troll": "pmg0", "elf": "pme0", "orc": "pmo0"}
    prefix = args.prefix or default_prefixes.get(race, "pmo0")
    try:
        res = run_client_test(
            max_duration=args.max_duration,
            race=race,
            prefix=prefix,
            client=args.client,
            equipment_target=args.equipment_target,
        )
        print(f"Client test finished. Sequence complete: {res['sequenceComplete']}, Phases: {len(res['phasesSeen'])}")
    except RuntimeError as err:
        print(f"ERROR: {err}", file=sys.stderr)
        sys.exit(1)
