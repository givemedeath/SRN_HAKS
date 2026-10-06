"""Reservation-first Meshy CLI adapter and credit session for the robe trial.

The pinned plugin CLI (meshy-cli@0.4.0) owns credentials; this adapter never
reads them. Every paid submission is reserved against an explicit credit cap
before dispatch, one paid job may be open at a time, 3D generations need a
recorded reference approval, and every downloaded file is hashed unchanged.
"""
import argparse
import json
import os
import subprocess
from pathlib import Path

from robe_common import FLAGS, pin, read, read_pinned, require, sha, utc, verify_pins, write_fresh

CLI_PACKAGE = "--package=meshy-cli@0.4.0"
MAX_FACES = 100000
GENERATION = {"image-to-3d", "multi-image-to-3d"}
OPERATIONS = GENERATION | {"image-to-image", "remesh", "retexture"}
ESTIMATES = {"image-to-3d": 30, "multi-image-to-3d": 30, "image-to-image": 9, "remesh": 5, "retexture": 10}


def validate_request(request):
    """Static policy checks for one paid request; returns the CLI argument list."""
    operation, payload = request["operation"], request["payload"]
    require(operation in OPERATIONS, "Unsupported Meshy operation: " + operation)
    require(type(request["estimatedCredits"]) is int and request["estimatedCredits"] >= ESTIMATES[operation],
            "Estimate below the published price")
    pinned = {str(Path(item["path"]).resolve()) for item in request["inputs"]}
    local = lambda value: str(Path(value).resolve()) in pinned
    arguments = [operation, "create", "--async", "--operation-id", request["requestId"], "--include-raw"]
    if operation in GENERATION:
        require(payload.get("should_texture") is True and payload.get("enable_pbr") is True
                and payload.get("texture_resolution") == "4k" and payload.get("pose_mode") == "a-pose",
                "Generation must be textured 4K PBR in A-pose")
        require("glb" in payload.get("target_formats", []), "GLB master required")
        images = payload["image_urls"] if operation == "multi-image-to-3d" else [payload["image_url"]]
        require(images and all(local(image) for image in images), "Reference images must be pinned inputs")
        key = "--image-urls" if operation == "multi-image-to-3d" else "--image-url"
        arguments += [key, ",".join(images), "--model-type", payload.get("model_type", "standard"),
                      "--should-texture", "true", "--enable-pbr", "true", "--texture-resolution", "4k",
                      "--pose-mode", "a-pose", "--remove-lighting", str(payload.get("remove_lighting", True)).lower(),
                      "--image-enhancement", str(payload.get("image_enhancement", True)).lower(),
                      "--target-formats", ",".join(payload["target_formats"])]
        if payload.get("texture_prompt"):
            arguments += ["--texture-prompt", payload["texture_prompt"]]
    elif operation == "remesh":
        require(payload.get("topology") == "triangle" and type(payload.get("target_polycount")) is int
                and 100 <= payload["target_polycount"] <= MAX_FACES, "Triangle remesh within 100k faces required")
        require(bool(payload.get("input_task_id")), "Remesh the recorded generation task")
        arguments += ["--input-task-id", payload["input_task_id"], "--topology", "triangle",
                      "--target-polycount", str(payload["target_polycount"]),
                      "--target-formats", ",".join(payload.get("target_formats", ["glb", "fbx"]))]
    elif operation == "retexture":
        require(payload.get("enable_original_uv") is True and payload.get("enable_pbr") is True
                and payload.get("texture_resolution") == "4k", "UV-preserving 4K PBR retexture required")
        source = ["--input-task-id", payload["input_task_id"]] if payload.get("input_task_id") else \
            ["--model-url", payload["model_url"]]
        require(payload.get("input_task_id") or local(payload["model_url"]), "Retexture source must be pinned")
        arguments += [*source, "--enable-original-uv", "true", "--enable-pbr", "true", "--texture-resolution", "4k",
                      "--target-formats", ",".join(payload.get("target_formats", ["glb", "fbx"]))]
        if payload.get("multiview_image_urls"):
            require(all(local(image) for image in payload["multiview_image_urls"]), "Views must be pinned")
            arguments += ["--multiview-image-urls", ",".join(payload["multiview_image_urls"])]
        else:
            require(local(payload["image_style_url"]), "Style image must be pinned")
            arguments += ["--image-style-url", payload["image_style_url"]]
    else:
        require(payload.get("ai_model") == "nano-banana-pro" and payload.get("prompt"), "Explicit image edit required")
        require(all(local(image) for image in payload["reference_image_urls"]), "Edit references must be pinned")
        arguments += ["--ai-model", "nano-banana-pro", "--prompt", payload["prompt"],
                      "--reference-image-urls", ",".join(payload["reference_image_urls"])]
    return arguments


class Session:
    """Hash-chained credit events plus an exclusive operation lock."""

    def __init__(self, directory):
        self.root = Path(directory).resolve()
        self.config = read(self.root / "session.json")
        require(self.config["kind"] == "srn-robe-meshy-session", "Robe Meshy session required")

    @classmethod
    def create(cls, directory, cap, outfits, attempts=2):
        require(type(cap) is int and 0 < cap <= 300, "Credit cap must be between 1 and 300")
        directory = Path(directory)
        require(not directory.exists(), "Fresh session directory required")
        (directory / "events").mkdir(parents=True)
        write_fresh(directory / "session.json", {"schemaVersion": 1, "kind": "srn-robe-meshy-session",
                    "createdUtc": utc(), "creditCap": cap, "outfits": sorted(outfits),
                    "maxGenerationAttempts": attempts, "cliPackage": CLI_PACKAGE, **FLAGS})
        return cls(directory)

    def events(self):
        rows, previous = [], sha(self.root / "session.json")
        for path in sorted((self.root / "events").glob("*.json")):
            event = read(path)
            require(event["previous"] == previous, "Session event chain broken at " + path.name)
            previous = sha(path)
            rows.append(event)
        return rows

    def append(self, kind, **fields):
        events = self.events()
        previous = sha(self.root / "events" / f"{len(events) - 1:06d}.json") if events else sha(self.root / "session.json")
        return write_fresh(self.root / "events" / f"{len(events):06d}.json",
                           {"kind": kind, "createdUtc": utc(), "previous": previous, **fields})

    def lock(self):
        path = self.root / "operation.lock"
        try:
            handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise ValueError("Another Meshy operation holds the session lock")
        os.close(handle)
        return path

    def committed(self):
        events = self.events()
        settled = {event["requestId"]: event for event in events if event["kind"] == "settled"}
        total = 0
        for event in events:
            if event["kind"] == "reserved":
                actual = settled.get(event["requestId"])
                total += actual["credits"] if actual and type(actual["credits"]) is int else event["estimatedCredits"]
        return total

    def reserve(self, request, request_pin, approval_pin):
        events = self.events()
        require(request["outfit"] in self.config["outfits"], "Outfit outside session roster")
        require(not any(e["requestId"] == request["requestId"] for e in events if e["kind"] == "reserved"),
                "Request identity already reserved")
        open_jobs = {e["requestId"] for e in events if e["kind"] == "reserved"} - \
            {e["requestId"] for e in events if e["kind"] == "settled"}
        require(not open_jobs, "One paid Meshy job may be open at a time: " + ", ".join(sorted(open_jobs)))
        if request["operation"] in GENERATION:
            attempts = sum(1 for e in events if e["kind"] == "reserved" and e["operation"] in GENERATION
                           and e["outfit"] == request["outfit"])
            require(attempts < self.config["maxGenerationAttempts"], "Generation attempt limit reached")
            require(approval_pin is not None, "Recorded reference approval required before 3D generation")
        require(self.committed() + request["estimatedCredits"] <= self.config["creditCap"],
                "Credit cap would be exceeded")
        return self.append("reserved", requestId=request["requestId"], outfit=request["outfit"],
                           operation=request["operation"], estimatedCredits=request["estimatedCredits"],
                           request=request_pin, approval=approval_pin, inputs=request["inputs"])


def task_fields(response):
    result = response.get("result", response)
    task = result.get("task") or result.get("submission") or result
    identity = task.get("task_id") or task.get("id") or result.get("task_id")
    return {"id": identity, "status": task.get("status"), "credits": task.get("consumed_credits")}


def invoke(binding, arguments, folder):
    command = binding["command"]
    require(CLI_PACKAGE in command, "Pinned Meshy plugin CLI required")
    folder = Path(folder)
    require(not folder.exists(), "Fresh CLI operation folder required")
    folder.mkdir(parents=True)
    full = [*command, *arguments, "--output-schema", "v1", "--format", "json", "--no-update-check",
            "--workspace", binding["workspace"]]
    with (folder / "stdout.json").open("x", encoding="utf-8") as out, \
            (folder / "stderr.log").open("x", encoding="utf-8") as err:
        result = subprocess.run(full, stdout=out, stderr=err, check=False)
    write_fresh(folder / "operation.json", {"kind": "srn-robe-meshy-cli-operation", "createdUtc": utc(),
                "arguments": arguments, "exitCode": result.returncode, "stdout": pin(folder / "stdout.json"),
                "stderr": pin(folder / "stderr.log")})
    return result.returncode, folder / "stdout.json"


def _json(path):
    text = Path(path).read_text(encoding="utf-8").strip()
    return json.loads(text[text.index("{"):]) if "{" in text else {}


def dispatch(session, request_file, binding_file, approval_file, folder):
    request_bytes, request_pin = read_pinned(request_file)  # the arguments and the reservation name the same bytes
    request, binding = json.loads(request_bytes.decode("utf-8-sig")), read(binding_file)
    verify_pins(request["inputs"])
    arguments = validate_request(request)
    lock = session.lock()
    try:
        approval = None
        if approval_file:
            approval_bytes, approval = read_pinned(approval_file)  # validated and reserved bytes are the same
            record = json.loads(approval_bytes.decode("utf-8-sig"))
            require(record.get("kind") == "srn-robe-reference-approval" and record.get("outfit") == request["outfit"]
                    and record.get("request", {}).get("sha256") == request_pin["sha256"]
                    and bool(record.get("userInstruction")), "Approval does not cover this exact request")
        session.reserve(request, request_pin, approval)
        code, response = invoke(binding, arguments, folder)
        identity = task_fields(_json(response))["id"] if code == 0 else None
        require(code == 0 and identity, "Submission uncertain; reconcile CLI journal before any retry")
        try:  # an input replaced during upload means the paid task may not match the reserved hashes
            verify_pins([request_pin, *([approval] if approval else []), *request["inputs"]])
            unchanged, problem = True, None
        except Exception as error:  # any failure here must not lose the paid task's record
            unchanged, problem = False, f"{type(error).__name__}: {error}"
        # The task is paid either way, so the submission is recorded before refusing to attribute it.
        session.append("submitted", requestId=request["requestId"], taskId=identity,
                       resource=request["operation"], response=pin(response), inputsUnchanged=unchanged,
                       inputsCheckError=problem)
        require(unchanged, "Inputs changed during submission; task " + identity + " cannot be attributed to the pinned request")
        return identity
    finally:
        lock.unlink()


def wait(session, request_id, binding_file, folder):
    events = session.events()
    event = next((e for e in events if e["kind"] == "submitted" and e["requestId"] == request_id), None)
    require(event is not None, "Recorded submission required")
    require(not any(e["kind"] == "settled" and e["requestId"] == request_id for e in events), "Request already settled")
    lock = session.lock()
    try:
        code, response = invoke(read(binding_file), [event["resource"], "wait", event["taskId"], "--timeout", "1800",
                                                     "--include-raw", "--save-json",
                                                     str(Path(folder).resolve() / "task.json")], folder)
        fields = task_fields(_json(response))
        if fields["status"] in ("SUCCEEDED", "FAILED", "CANCELED"):
            session.append("settled", requestId=request_id, taskId=event["taskId"], resource=event["resource"],
                           status=fields["status"], credits=fields["credits"], response=pin(response),
                           task=pin(Path(folder) / "task.json") if (Path(folder) / "task.json").exists() else None)
        require(code == 0 and fields["status"] == "SUCCEEDED", "Task not succeeded; reservation stays until settled")
        # Settling keeps credit accounting true; a refused submission still cannot become source material.
        require(event.get("inputsUnchanged", True), "Settled, but the task cannot be attributed to its pinned inputs")
        return fields
    finally:
        lock.unlink()


def collect(session, request_id, binding_file, folder, bank):
    events = session.events()
    submitted = next((e for e in events if e["kind"] == "submitted" and e["requestId"] == request_id), None)
    require(submitted is not None and submitted.get("inputsUnchanged", True),
            "Submission inputs changed during upload; the task cannot be collected as source")
    settled = next((e for e in events if e["kind"] == "settled" and e["requestId"] == request_id), None)
    require(settled is not None and settled["status"] == "SUCCEEDED" and settled["task"], "Successful task required")
    verify_pins([settled["task"]])
    bank = Path(bank).resolve()
    require(not bank.exists(), "Fresh source bank folder required")
    code, _ = invoke(read(binding_file), ["download", "--task-json", settled["task"]["path"], "--all",
                                          "--output-dir", str(bank)], folder)
    require(code == 0 and bank.exists(), "Download incomplete; keep partial output and reconcile")
    verify_pins([settled["task"]])  # the CLI read this task record during the download
    files = [pin(path) for path in sorted(bank.rglob("*")) if path.is_file()]
    require(any(Path(item["path"]).suffix.lower() == ".glb" for item in files), "GLB master missing")
    write_fresh(bank.parent / (bank.name + "-collection.json"), {"kind": "srn-robe-meshy-collection",
                "createdUtc": utc(), "requestId": request_id, "taskId": settled["taskId"],
                "resource": settled["resource"], "credits": settled["credits"], "task": settled["task"],
                "files": files, **FLAGS})
    session.append("collected", requestId=request_id, files=files)
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["init", "status", "dispatch", "wait", "collect"])
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--binding", type=Path)
    parser.add_argument("--request", type=Path)
    parser.add_argument("--request-id")
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--bank", type=Path)
    parser.add_argument("--cap", type=int)
    parser.add_argument("--outfit", action="append", default=[])
    args = parser.parse_args()
    if args.command == "init":
        Session.create(args.session, args.cap, args.outfit)
        print(json.dumps({"session": str(args.session.resolve())}))
        return
    session = Session(args.session)
    if args.command == "status":
        print(json.dumps({"creditCap": session.config["creditCap"], "committed": session.committed(),
                          "events": [{k: e.get(k) for k in ("kind", "requestId", "operation", "taskId", "status",
                                                             "credits", "estimatedCredits")} for e in session.events()]},
                         indent=2))
    elif args.command == "dispatch":
        print(dispatch(session, args.request, args.binding, args.approval, args.output))
    elif args.command == "wait":
        print(json.dumps(wait(session, args.request_id, args.binding, args.output)))
    else:
        print(len(collect(session, args.request_id, args.binding, args.output, args.bank)))


if __name__ == "__main__":
    main()
