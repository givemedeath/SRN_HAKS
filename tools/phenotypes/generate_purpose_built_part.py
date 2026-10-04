"""Record and run isolated-part variants of the user's live Pixal3D workflow.

prepare is read-only against ComfyUI: it freezes the graph, schema and references.
submit uploads the already-reviewed four panels and queues exactly one attempt.
status preserves history and downloads the named GLBs without rerunning a job.
Use a fresh output directory for every generation; never replace prior attempts.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import time
import urllib.parse
import urllib.request
import uuid

from PIL import Image
from pipeline import Comfy, ancestors, compile_prompt, digest, save_json


VIEW_ORDER = ("front", "left", "back", "right")
ORTHO_VIEW_ORDER = (*VIEW_ORDER, "top", "bottom")
EXPECTED = {
    "324": "Pixal3DMultiViewConditioning", "94": "Trellis2UpsampleStage",
    "288": "PrimitiveInt", "147": "BakeTextureFromVoxel",
    "186": "DecimateMesh", "241": "RemeshMesh", "282": "MeshToFile3D",
    "372": "Save3DAdvanced", "224": "BakeNormalMapFromMesh",
    "3": "KSampler", "18": "KSampler", "23": "KSampler", "12": "KSampler",
}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def freeze(path, data):
    if path.exists():
        raise RuntimeError("Fresh output required; preserve existing " + str(path))
    save_json(path, data)


def verify_record(root):
    record = read_json(root / "preparation.json")
    for relative, expected in record["frozenFiles"].items():
        if digest(root / relative) != expected:
            raise RuntimeError("Frozen preparation changed: " + relative)
    for path, expected in record.get("externalDependencies", {}).items():
        if digest(Path(path)) != expected:
            raise RuntimeError("Installed conditioning dependency changed: " + path)
    return record


def configure_projection(prompt, config, schemas):
    """Extend only the conditioning node; leave the saved source workflow intact."""
    mode = config.get("projection", "perspective-four-view")
    order = ORTHO_VIEW_ORDER if mode == "orthographic-six-view" else VIEW_ORDER
    if mode not in ("perspective-four-view", "orthographic-six-view") or tuple(config["viewOrder"]) != order:
        raise RuntimeError("Require explicit camera projection and matching view order")
    if mode == "orthographic-six-view":
        kind = "SRNOrthographicMultiViewConditioning"
        schema = schemas.get(kind, {}).get("input", {})
        inputs = set(schema.get("required", {})) | set(schema.get("optional", {}))
        if inputs != {"clip_vision_model", "ortho_span", *ORTHO_VIEW_ORDER}:
            raise RuntimeError("Installed orthographic node schema changed/missing")
        span = float(config["orthoSpan"])
        if not .5 <= span <= 2.:
            raise RuntimeError("Orthographic span outside reviewed range")
        prompt["324"] = {"class_type": kind, "inputs": {
            "clip_vision_model": copy.deepcopy(prompt["324"]["inputs"]["clip_vision_model"]),
            "ortho_span": span}}
    else:
        prompt["324"]["inputs"]["fov"] = config["fovDegrees"]
    return order


def recorded_views(record):
    order = tuple(record.get("viewOrder", VIEW_ORDER))
    if order not in (VIEW_ORDER, ORTHO_VIEW_ORDER) or set(record["views"]) != set(order):
        raise RuntimeError("Invalid frozen view order")
    return order


def configured_remesh_inputs(original, settings, schema):
    """Make the selected mode explicit; never inherit another mode's widgets."""
    required = schema["input"]["required"]
    mode = settings.get("sign_mode")
    options = required["sign_mode"][1]["options"]
    option = next((item for item in options if item["key"] == mode), None)
    if option is None:
        raise RuntimeError("Unsupported explicit remesh sign mode: " + str(mode))
    expected = (set(required) - {"mesh"}) | {
        "sign_mode." + key for key in option.get("inputs", {}).get("required", {})}
    if set(settings) != expected:
        raise RuntimeError("Explicit remesh settings mismatch; missing=" + str(sorted(expected-set(settings))) +
                           " extra=" + str(sorted(set(settings)-expected)))
    # The mesh edge belongs to the reviewed workflow. All scalar/mode values
    # belong to the configuration, including SDF-only manifold vs UDF filters.
    return {"mesh": copy.deepcopy(original["mesh"]), **copy.deepcopy(settings)}


def add_raw_master(prompt, prefix):
    """Save the exact mesh edge entering RemeshMesh without decimation or repair."""
    if any(key in prompt for key in ("1013", "1014")):
        raise RuntimeError("Raw master node IDs collide with the live workflow")
    source = copy.deepcopy(prompt["241"]["inputs"]["mesh"])
    if not isinstance(source, list) or len(source) != 2 or str(source[0]) not in prompt:
        raise RuntimeError("Invalid raw pre-remesh mesh connection")
    prompt["1013"] = {"class_type": "MeshToFile3D", "inputs": {"mesh": source}}
    prompt["1014"] = {"class_type": "Save3DAdvanced", "inputs": {
        "model_3d": ["1013", 0], "filename_prefix": prefix + "/raw-master",
        "viewport_state": "", "width": 1024, "height": 1024}}
    return "1014"


def declared_save_nodes(record):
    """Older frozen preparations had exactly the original three save nodes."""
    nodes = record.get("saveNodes", ["372", "1010", "1012"])
    if not isinstance(nodes, list) or not nodes or not all(isinstance(key, str) for key in nodes) or len(set(nodes)) != len(nodes):
        raise RuntimeError("Invalid declared save nodes")
    return nodes


def prepare(args):
    root = args.output.resolve()
    if root.exists():
        raise RuntimeError("Use a fresh output directory")
    config = read_json(args.config)
    service = Comfy(args.service or config["service"])
    workflow = service.request("/userdata/" + urllib.parse.quote("workflows/" + config["workflow"], safe=""))
    schemas = service.request("/object_info")
    prompt = compile_prompt(workflow, schemas)
    for key, kind in EXPECTED.items():
        if prompt.get(key, {}).get("class_type") != kind:
            raise RuntimeError("Live workflow branch changed: " + key + " expected " + kind)
    order = configure_projection(prompt, config, schemas)
    external = {}
    if order == ORTHO_VIEW_ORDER:
        for path, expected in config["conditioningDependencies"].items():
            if digest(Path(path)) != expected:
                raise RuntimeError("Unreviewed installed conditioning source: " + path)
            external[str(Path(path).resolve())] = expected
        if len(external) != 3:
            raise RuntimeError("Freeze adapter plus both upstream dependencies")
    views = {}
    for view in order:
        source = (args.views_dir / (view + ".png")).resolve()
        with Image.open(source) as image:
            if image.size != (config["imageSize"], config["imageSize"]):
                raise RuntimeError("Require shared 1024-square normalization: " + view)
            # LoadImage emits RGB on its IMAGE output. Fully transparent pixels
            # with non-black RGB are not implicitly composited by that output.
            if image.mode not in ("RGB", "RGBA"):
                raise RuntimeError("Require black-background RGB/RGBA reference: " + view)
            rgba = image.convert("RGBA")
            pixels = getattr(rgba, "get_flattened_data", rgba.getdata)()
            if any(alpha < 255 and (r or g or b) for r, g, b, alpha in pixels):
                raise RuntimeError("Composite transparent panels over black before prepare: " + view)
        views[view] = {"source": str(source), "sha256": digest(source), "path": "views/" + view + ".png"}
        prompt[str(1000 + order.index(view))] = {
            "class_type": "LoadImage", "inputs": {"image": "__UPLOAD_" + view.upper() + "__"}}
        prompt["324"]["inputs"][view] = [str(1000 + order.index(view)), 0]
    prompt["94"]["inputs"]["target_resolution"] = int(config["shapeResolution"])
    prompt["288"]["inputs"]["value"] = int(config["textureSize"])
    prompt["224"]["inputs"]["resolution"] = int(config["normalBakeSize"])
    prompt["186"]["inputs"]["target_face_count"] = int(config["masterTriangleBudget"])
    prompt["241"]["inputs"] = configured_remesh_inputs(
        prompt["241"]["inputs"], config["remesh"], schemas["RemeshMesh"])
    if config["compactBakeReference"]:
        prompt["147"]["inputs"]["reference_mesh"] = ["241", 0]
    for key, seed in (("3", "structure"), ("18", "shape"), ("23", "shape"), ("12", "texture")):
        prompt[key]["inputs"]["seed"] = config["seeds"][seed]
    prefix = "srn_purpose_built_parts/" + config["name"] + "/" + uuid.uuid4().hex[:12]
    prompt["372"]["inputs"]["filename_prefix"] = prefix + "/textured"
    prompt["1010"] = {"class_type": "Save3DAdvanced", "inputs": {
        "model_3d": ["282", 0], "filename_prefix": prefix + "/shape-master",
        "viewport_state": "", "width": 1024, "height": 1024}}
    # Preserve the exterior remesh before 50K decimation/UV/normal baking, so
    # fitting is not forced to discard the source's available high detail.
    prompt["1011"] = {"class_type": "MeshToFile3D", "inputs": {"mesh": ["241", 0]}}
    prompt["1012"] = {"class_type": "Save3DAdvanced", "inputs": {
        "model_3d": ["1011", 0], "filename_prefix": prefix + "/remeshed-master",
        "viewport_state": "", "width": 1024, "height": 1024}}
    save_nodes = ["372", "1010", "1012"]
    if config.get("retainRawMaster", False):
        save_nodes.append(add_raw_master(prompt, prefix))
    prompt = ancestors(prompt, tuple(save_nodes))
    root.mkdir(parents=True)
    frozen = {}
    for name, value in (("workflow-source.json", workflow), ("object-info.json", schemas),
                        ("config.json", config), ("workflow-api-template.json", prompt)):
        freeze(root / name, value)
        frozen[name] = digest(root / name)
    for view, info in views.items():
        target = root / info["path"]
        target.parent.mkdir(exist_ok=True)
        data = Path(info["source"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != info["sha256"]:
            raise RuntimeError("Reference changed during freeze: " + view)
        target.write_bytes(data)
        frozen[info["path"]] = digest(target)
    script = root / "generate_purpose_built_part.py"
    script.write_bytes(Path(__file__).read_bytes())
    frozen[script.name] = digest(script)
    imported = root / "pipeline.py"
    imported.write_bytes(Path(__file__).with_name("pipeline.py").read_bytes())
    frozen[imported.name] = digest(imported)
    # pipeline imports height_targets, although isolated generation uses no race
    # sizing table. Freeze it as an executed import dependency as well.
    heights = root / "height_targets.json"
    heights.write_bytes(Path(__file__).with_name("height_targets.json").read_bytes())
    frozen[heights.name] = digest(heights)
    for index, (path, expected) in enumerate(external.items()):
        relative = "conditioning-dependency-"+str(index)+".py"
        (root / relative).write_bytes(Path(path).read_bytes())
        frozen[relative] = digest(root / relative)
        if frozen[relative] != expected:
            raise RuntimeError("Conditioning dependency changed during freeze")
    record = {"schemaVersion": 1, "state": "prepared-not-submitted", "created": time.time(),
              "service": service.base, "part": config["part"], "views": views,
              "viewOrder": list(order), "projection": config.get("projection", "perspective-four-view"),
              "externalDependencies": external,
              "frozenFiles": frozen, "outputPrefix": prefix,
              "saveNodes": save_nodes,
              "rawMaster": {"retained": bool(config.get("retainRawMaster", False)),
                            "meshConnection": prompt["241"]["inputs"]["mesh"],
                            "sourceGeometryModified": False},
              "queueAtPreparation": service.request("/queue"),
              "viewOrbit": {view: {"azimuth": (0,90,180,270,0,0)[i], "elevation": (0,0,0,0,90,-90)[i]} for i, view in enumerate(order)},
              "sourceReferenceFidelityReview": "required-before-submit",
              "normalStrength": {"value": config["postFitNormalStrength"], "applied": False,
                                 "stage": "matching post-fit 2K map bake; not an input to Pixal3D"},
              "clientAccepted": False}
    freeze(root / "preparation.json", record)
    print(json.dumps(record, indent=2), flush=True)


def submit(args):
    root = args.output.resolve()
    record = verify_record(root)
    receipt_path = root / "generation.json"
    if receipt_path.exists():
        raise RuntimeError("Attempt already exists; use status, never duplicate submission")
    service = Comfy(args.service or record["service"])
    queue = service.request("/queue")
    if queue["queue_running"] or queue["queue_pending"]:
        raise RuntimeError("ComfyUI queue is occupied; preserve other work and submit when idle")
    prompt = copy.deepcopy(read_json(root / "workflow-api-template.json"))
    uploaded = []
    for index, view in enumerate(recorded_views(record)):
        source = root / record["views"][view]["path"]
        name = service.upload(source, record["outputPrefix"] + "/references")
        remote = Path(name)
        query = urllib.parse.urlencode({"filename": remote.name,
                                      "subfolder": str(remote.parent).replace("\\", "/"), "type": "input"})
        with urllib.request.urlopen(service.base + "/view?" + query, timeout=30) as response:
            actual = hashlib.sha256(response.read()).hexdigest()
        if actual != digest(source):
            raise RuntimeError("Uploaded reference differs: " + view)
        prompt[str(1000 + index)]["inputs"]["image"] = name
        uploaded.append({"view": view, "serverImage": name, "sha256": actual})
    verify_record(root)
    freeze(root / "workflow-api.json", prompt)
    receipt = {"schemaVersion": 1, "state": "submission-started", "service": service.base,
               "submitted": time.time(), "uploadedInputs": uploaded,
               "preparationSha256": digest(root / "preparation.json"),
               "apiSha256": digest(root / "workflow-api.json"), "outputs": [], "clientAccepted": False}
    receipt["saveNodes"] = declared_save_nodes(record)
    # A crash after request dispatch must not silently queue the same job again.
    freeze(receipt_path, receipt)
    result = service.request("/prompt", {"prompt": prompt,
                            "client_id": "srn-purpose-built-" + uuid.uuid4().hex})
    receipt["response"] = result
    if result.get("node_errors") or not result.get("prompt_id"):
        receipt["state"] = "rejected"
        save_json(receipt_path, receipt)
        raise RuntimeError(json.dumps(result))
    receipt.update({"state": "queued", "promptId": result["prompt_id"]})
    save_json(receipt_path, receipt)
    print(json.dumps(receipt, indent=2), flush=True)


def status(args):
    root = args.output.resolve()
    record = verify_record(root)
    receipt = read_json(root / "generation.json")
    if digest(root / "preparation.json") != receipt["preparationSha256"]:
        raise RuntimeError("Preparation receipt changed after submission")
    if digest(root / "workflow-api.json") != receipt["apiSha256"]:
        raise RuntimeError("Submitted workflow changed")
    if "promptId" not in receipt:
        raise RuntimeError("Submission result is uncertain/rejected; inspect receipt, do not resubmit")
    service = Comfy(args.service or receipt["service"])
    history = service.request("/history/" + receipt["promptId"])
    if receipt["promptId"] not in history:
        queue = service.request("/queue")
        print(json.dumps({"state": "queued-or-running", "promptId": receipt["promptId"],
                          "runningPromptIds": [row[1] for row in queue.get("queue_running", [])],
                          "pendingPromptIds": [row[1] for row in queue.get("queue_pending", [])]}), flush=True)
        return
    result = history[receipt["promptId"]]
    save_json(root / "history.json", result)
    state = result.get("status", {}).get("status_str", "unknown")
    if state == "success":
        outputs = []
        save_nodes = declared_save_nodes(record)
        if "saveNodes" in receipt and receipt["saveNodes"] != save_nodes:
            raise RuntimeError("Submission save nodes differ from preparation")
        api = read_json(root / "workflow-api.json")
        if any(api.get(key, {}).get("class_type") != "Save3DAdvanced" for key in save_nodes):
            raise RuntimeError("Declared save node differs from submitted graph")
        for node_id in save_nodes:
            items = result.get("outputs", {}).get(node_id, {})
            files = [item for group in items.values() if isinstance(group, list)
                     for item in group if isinstance(item, dict) and "filename" in item
                     and item["filename"].lower().endswith(".glb")]
            if len(files) != 1:
                raise RuntimeError("Expected one recorded GLB per save node: " + node_id)
            item = files[0]
            target = root / "generated" / Path(item["filename"]).name
            target.parent.mkdir(exist_ok=True)
            query = urllib.parse.urlencode({key: item[key] for key in ("filename", "subfolder", "type") if key in item})
            with urllib.request.urlopen(service.base + "/view?" + query, timeout=120) as response:
                data = response.read()
            actual = hashlib.sha256(data).hexdigest()
            if target.exists() and digest(target) != actual:
                raise RuntimeError("Preserved downloaded GLB differs from server output")
            if not target.exists():
                target.write_bytes(data)
            outputs.append({**item, "nodeId": node_id, "localPath": str(target), "sha256": actual})
        receipt["outputs"] = outputs
    receipt["state"] = state
    receipt["clientAccepted"] = False
    save_json(root / "generation.json", receipt)
    messages = result.get("status", {}).get("messages", [])
    errors = [{key: data.get(key) for key in ("node_id", "node_type", "exception_type", "exception_message")}
              for event, data in messages if event in ("execution_error", "execution_interrupted")]
    print(json.dumps({"state": state, "promptId": receipt["promptId"],
                      "outputs": receipt["outputs"], "messageCount": len(messages), "errors": errors}, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "submit", "status"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--views-dir", type=Path)
    parser.add_argument("--service")
    args = parser.parse_args()
    if args.action == "prepare" and args.config is None:
        parser.error("prepare requires an explicit --config for the requested part")
    if args.action == "prepare" and args.views_dir is None:
        parser.error("prepare requires --views-dir")
    {"prepare": prepare, "submit": submit, "status": status}[args.action](args)


if __name__ == "__main__":
    main()
