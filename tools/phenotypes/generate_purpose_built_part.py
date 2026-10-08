"""Record and run isolated-part variants of the user's live Pixal3D workflow.

prepare is read-only against ComfyUI: it freezes the graph, schema and references.
submit uploads the already-reviewed panels and queues exactly one attempt.
status preserves history and downloads the named GLBs without rerunning a job.
Use a fresh output directory for every generation; never replace prior attempts.
Optional textureViewOrder=[front,left,back,right] keeps six-view orthographic
shape conditioning and uses a separate four-cardinal texture pack.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import time
import urllib.parse
import urllib.request
import uuid

from PIL import Image
from pipeline import Comfy, ancestors, compile_prompt, digest, save_json


VIEW_ORDER = ("front", "left", "back", "right")
ORTHO_VIEW_ORDER = (*VIEW_ORDER, "top", "bottom")
TEXTURE_CONDITIONER_ID = "1016"
TEXTURE_RECORD_FIELDS = ("textureViewOrder", "textureViewOrbit", "textureConditioning")
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
    if record.get('generationBinding'):
        import target_contract as contract
        pin = record['generationBinding']; target = contract.load(pin['targetContract'])
        if contract.sha(pin['targetContract']) != pin['targetContractSha256'] or target['id'] != pin['targetId'] or target['rig']['revision'] != pin['rigRevision']:
            raise RuntimeError('Generation belongs to a stale/different target')
    verify_texture_record(root, record)
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


def texture_view_order(config):
    """The optional split supports exactly the four canonical cardinal cameras."""
    if "textureViewOrder" not in config:
        return None
    if type(config.get("schemaVersion")) is not int or config["schemaVersion"] != 1:
        raise RuntimeError("Separate texture conditioning requires configuration schemaVersion 1")
    if (config.get("projection") != "orthographic-six-view" or
            type(config.get("viewOrder")) is not list or config["viewOrder"] != list(ORTHO_VIEW_ORDER)):
        raise RuntimeError("Separate texture conditioning requires canonical six-view orthographic shape inputs")
    if type(config["textureViewOrder"]) is not list or config["textureViewOrder"] != list(VIEW_ORDER):
        raise RuntimeError("textureViewOrder must be exactly front,left,back,right in canonical order")
    span = config.get("orthoSpan")
    if type(span) not in (int, float) or not math.isfinite(span) or not .5 <= span <= 2.:
        raise RuntimeError("Separate texture conditioning requires a finite numeric orthographic span")
    return VIEW_ORDER


def exact_link(value, expected):
    return (type(value) is list and len(value) == 2 and type(value[0]) is str and
            type(value[1]) is int and value == expected)


def json_identical(left, right):
    return json.dumps(left, sort_keys=True, separators=(",", ":")) == json.dumps(right, sort_keys=True, separators=(",", ":"))


def texture_schemas(schemas):
    """Require current typed interfaces rather than matching input names alone."""
    expected = {
        "SRNOrthographicMultiViewConditioning": (
            {"clip_vision_model":"CLIP_VISION", "ortho_span":"FLOAT", "front":"IMAGE"},
            {name:"IMAGE" for name in ORTHO_VIEW_ORDER[1:]}, ["CONDITIONING", "CONDITIONING"]),
        "Trellis2TextureStage": (
            {"positive":"CONDITIONING", "negative":"CONDITIONING", "shape_latent":"LATENT"},
            {}, ["CONDITIONING", "CONDITIONING", "LATENT"])}
    if not isinstance(schemas, dict):
        raise RuntimeError("Separate texture conditioning schemas must be an object")
    for kind, (required, optional, outputs) in expected.items():
        schema = schemas.get(kind, {})
        if not isinstance(schema, dict) or not isinstance(schema.get("input"), dict):
            raise RuntimeError("Separate texture conditioning schema changed: " + kind)
        inputs = schema["input"]
        for group, types in (("required", required), ("optional", optional)):
            actual = inputs.get(group, {})
            if not isinstance(actual, dict) or set(actual) != set(types):
                raise RuntimeError("Separate texture conditioning schema changed: " + kind + " " + group)
            for name, expected_type in types.items():
                declaration = actual[name]
                if not isinstance(declaration, (list, tuple)) or not declaration or declaration[0] != expected_type:
                    raise RuntimeError("Separate texture conditioning schema type changed: " + kind + "." + name)
        lists = schema.get("output_is_list")
        if (schema.get("output") != outputs or type(lists) is not list or
                len(lists) != len(outputs) or any(value is not False for value in lists)):
            raise RuntimeError("Separate texture conditioning output schema changed: " + kind)


def texture_graph_metadata(prompt, config, schemas, split=False):
    """Validate reviewed edges and return deterministic independent camera metadata."""
    if texture_view_order(config) is None:
        return None
    texture_schemas(schemas)
    kind = "SRNOrthographicMultiViewConditioning"
    shape = prompt.get("324", {})
    shape_inputs = shape.get("inputs", {})
    if (shape.get("class_type") != kind or not isinstance(shape_inputs, dict) or
            set(shape_inputs) != {"clip_vision_model", "ortho_span", *ORTHO_VIEW_ORDER} or
            type(shape_inputs["ortho_span"]) not in (int,float) or
            shape_inputs["ortho_span"] != float(config["orthoSpan"])):
        raise RuntimeError("Separate texture conditioning shape graph/camera mismatch")
    clip = shape_inputs["clip_vision_model"]
    if (not isinstance(clip, list) or len(clip) != 2 or not isinstance(clip[0], str) or type(clip[1]) is not int or clip[1] != 0 or
            prompt.get(clip[0], {}).get("class_type") != "CLIPVisionLoader"):
        raise RuntimeError("Separate texture conditioning CLIP graph mismatch")
    cardinal_inputs = {"clip_vision_model":copy.deepcopy(clip), "ortho_span":float(config["orthoSpan"])}
    for index, view in enumerate(ORTHO_VIEW_ORDER):
        image_id = str(1000 + index)
        image = prompt.get(image_id, {})
        if (not exact_link(shape_inputs[view], [image_id, 0]) or image.get("class_type") != "LoadImage" or
                not isinstance(image.get("inputs", {}).get("image"), str)):
            raise RuntimeError("Separate texture conditioning loaded image graph mismatch: " + view)
        if view in VIEW_ORDER:
            cardinal_inputs[view] = copy.deepcopy(shape_inputs[view])
    # Only the texture stage may read the new conditioning pack. The actual
    # shape latent continues through the original reviewed cascade unchanged.
    links = {
        "3": ("KSampler", {"positive":["324",0], "negative":["324",1]}),
        "119": ("VaeDecodeStructureTrellis2", {"samples":["3",0]}),
        "91": ("Trellis2ShapeStage", {"positive":["324",0], "negative":["324",1], "voxel":["119",0]}),
        "18": ("KSampler", {"positive":["91",0], "negative":["91",1], "latent_image":["91",2]}),
        "94": ("Trellis2UpsampleStage", {"positive":["91",0], "negative":["91",1], "shape_latent":["18",0]}),
        "23": ("KSampler", {"positive":["94",0], "negative":["94",1], "latent_image":["94",2]}),
        "98": ("Trellis2TextureStage", {"positive":[TEXTURE_CONDITIONER_ID if split else "94",0],
            "negative":[TEXTURE_CONDITIONER_ID if split else "94",1], "shape_latent":["23",0]}),
        "12": ("KSampler", {"positive":["98",0], "negative":["98",1], "latent_image":["98",2]})}
    for key, (node_kind, edges) in links.items():
        node = prompt.get(key, {})
        if node.get("class_type") != node_kind or any(not exact_link(node.get("inputs", {}).get(name), edge) for name, edge in edges.items()):
            raise RuntimeError("Separate texture conditioning reviewed graph edge mismatch: " + key)
    if set(prompt["98"]["inputs"]) != {"positive", "negative", "shape_latent"}:
        raise RuntimeError("Separate texture conditioning texture-stage graph inputs changed")
    expected_node = {"class_type":kind, "inputs":cardinal_inputs}
    if split:
        if not json_identical(prompt.get(TEXTURE_CONDITIONER_ID), expected_node):
            raise RuntimeError("Frozen separate texture conditioner graph differs")
        for key, node in prompt.items():
            for name, value in node.get("inputs", {}).items():
                if (isinstance(value, list) and len(value) == 2 and value[0] == TEXTURE_CONDITIONER_ID and
                        (key != "98" or name not in ("positive", "negative"))):
                    raise RuntimeError("Separate texture conditioner leaks into another graph branch")
    elif TEXTURE_CONDITIONER_ID in prompt:
        raise RuntimeError("Separate texture conditioner node ID collides with the live workflow")
    return {"nodeId":TEXTURE_CONDITIONER_ID, "classType":kind, "shapeConditionerNodeId":"324",
            "projection":"orthographic-cardinal-texture", "viewOrder":list(VIEW_ORDER),
            "orthoSpan":float(config["orthoSpan"]), "clipVisionConnection":copy.deepcopy(clip),
            "imageConnections":{view:copy.deepcopy(cardinal_inputs[view]) for view in VIEW_ORDER},
            "shapeLatentConnection":["23",0],
            "viewOrbit":{view:{"azimuth":(0,90,180,270)[i], "elevation":0} for i,view in enumerate(VIEW_ORDER)}}


def configure_texture_conditioning(prompt, config, schemas):
    """Add a texture-only pack when explicitly requested; omission is a no-op."""
    metadata = texture_graph_metadata(prompt, config, schemas)
    if metadata is None:
        return None
    shape = prompt["324"]["inputs"]
    prompt[TEXTURE_CONDITIONER_ID] = {"class_type":"SRNOrthographicMultiViewConditioning", "inputs":{
        name:copy.deepcopy(shape[name]) for name in ("clip_vision_model", "ortho_span", *VIEW_ORDER)}}
    prompt["98"]["inputs"]["positive"] = [TEXTURE_CONDITIONER_ID, 0]
    prompt["98"]["inputs"]["negative"] = [TEXTURE_CONDITIONER_ID, 1]
    return texture_graph_metadata(prompt, config, schemas, split=True)


def texture_record_fields(metadata):
    if metadata is None:
        return {}
    return {"textureViewOrder":copy.deepcopy(metadata["viewOrder"]),
            "textureViewOrbit":copy.deepcopy(metadata["viewOrbit"]), "textureConditioning":copy.deepcopy(metadata)}


def verify_texture_record(root, record):
    config_path = root / "config.json"
    config = read_json(config_path) if config_path.exists() else {}
    enabled = texture_view_order(config) is not None
    present = [key in record for key in TEXTURE_RECORD_FIELDS]
    if not enabled:
        if any(present):
            raise RuntimeError("Unexpected separate texture conditioning provenance")
        return
    if not all(present) or recorded_views(record) != ORTHO_VIEW_ORDER or record.get("projection") != "orthographic-six-view":
        raise RuntimeError("Missing/malformed separate texture conditioning provenance")
    prompt = read_json(root / "workflow-api-template.json")
    metadata = texture_graph_metadata(prompt, config, read_json(root / "object-info.json"), split=True)
    if any(not json_identical(record[key], expected) for key, expected in texture_record_fields(metadata).items()):
        raise RuntimeError("Frozen separate texture conditioning provenance differs from graph/cameras")


def verify_texture_submission(record, receipt):
    fields = [key for key in TEXTURE_RECORD_FIELDS if key in record]
    if any(key not in fields for key in TEXTURE_RECORD_FIELDS if key in receipt) or any(not json_identical(receipt.get(key), record[key]) for key in fields):
        raise RuntimeError("Submission separate texture conditioning provenance differs from preparation")


def verify_texture_api(root, record, prompt):
    if "textureConditioning" not in record:
        return
    metadata = texture_graph_metadata(prompt, read_json(root / "config.json"),
                                      read_json(root / "object-info.json"), split=True)
    if not json_identical(metadata, record["textureConditioning"]):
        raise RuntimeError("Submitted separate texture conditioning graph/cameras differ")


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
    texture_view_order(config)  # Reject malformed explicit options before service access.
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
    generation_binding = None
    if config.get('targetContract'):
        import target_contract as contract
        target_path = Path(config['targetContract']).resolve()
        if digest(target_path) != config['targetContractSha256']:
            raise RuntimeError('Generation target contract changed')
        target = contract.load(target_path)
        if config['part'] not in contract.BODY_PARTS:
            raise RuntimeError('Generation donor is not a target body part')
        generation_binding = {key:value for key,value in contract.binding(target_path,target,'working').items() if key != 'coordinateSpace'}
        generation_binding['part'] = config['part']
        external[str(target_path)] = digest(target_path)
        for key in ('sourceReference','styleReference'):
            path = Path(config[key]).resolve()
            if digest(path) != config[key+'Sha256']:
                raise RuntimeError('Approved generation reference changed: '+key)
            external[str(path)] = digest(path)
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
    texture_metadata = configure_texture_conditioning(prompt, config, schemas)
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
    for index, (path, expected) in enumerate((item for item in external.items() if Path(item[0]).suffix == '.py')):
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
    record.update(texture_record_fields(texture_metadata))
    if generation_binding:
        for helper_name in ('target_contract.py', 'retarget.py', 'rig_controller_audit.py'):
            helper = Path(__file__).with_name(helper_name)
            (root/helper_name).write_bytes(helper.read_bytes())
            frozen[helper_name] = digest(root/helper_name)
        record['generationBinding'] = generation_binding
    record['modelIdentifiers'] = {key:{'class_type':row['class_type'],'inputs':{name:value for name,value in row['inputs'].items() if isinstance(value,str) and ('model' in name or name.endswith('_name'))}} for key,row in prompt.items() if any(isinstance(value,str) and ('model' in name or name.endswith('_name')) for name,value in row['inputs'].items())}
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
    verify_texture_api(root, record, prompt)
    freeze(root / "workflow-api.json", prompt)
    receipt = {"schemaVersion": 1, "state": "submission-started", "service": service.base,
               "submitted": time.time(), "uploadedInputs": uploaded,
               "preparationSha256": digest(root / "preparation.json"),
               "apiSha256": digest(root / "workflow-api.json"), "outputs": [], "clientAccepted": False}
    receipt["saveNodes"] = declared_save_nodes(record)
    for key in TEXTURE_RECORD_FIELDS:
        if key in record:
            receipt[key] = copy.deepcopy(record[key])
    receipt['clientId'] = 'srn-purpose-built-' + uuid.uuid4().hex
    if record.get('generationBinding'):
        receipt['generationBinding'] = record['generationBinding']
    # A crash after request dispatch must not silently queue the same job again.
    freeze(receipt_path, receipt)
    result = service.request("/prompt", {"prompt": prompt,
                            "client_id": receipt["clientId"]})
    receipt["response"] = result
    if result.get("node_errors") or not result.get("prompt_id"):
        receipt["state"] = "rejected"
        save_json(receipt_path, receipt)
        raise RuntimeError(json.dumps(result))
    receipt.update({"state": "queued", "promptId": result["prompt_id"]})
    save_json(receipt_path, receipt)
    print(json.dumps(receipt, indent=2), flush=True)



def recover_prompt_id(receipt, api, queue, history):
    """Recover a dispatched attempt without ever posting another prompt."""
    entries = list(queue.get('queue_running', [])) + list(queue.get('queue_pending', []))
    entries += [row.get('prompt', []) for row in history.values()]
    matches = {entry[1] for entry in entries if isinstance(entry, (list, tuple)) and len(entry) >= 4
               and entry[2] == api and isinstance(entry[3], dict)
               and entry[3].get('client_id') == receipt.get('clientId')}
    if len(matches) != 1:
        raise RuntimeError('Uncertain submission needs exactly one matching client ID/graph; found '+str(len(matches))+'. Do not resubmit.')
    return matches.pop()


def status(args):
    root = args.output.resolve()
    record = verify_record(root)
    receipt = read_json(root / "generation.json")
    if digest(root / "preparation.json") != receipt["preparationSha256"]:
        raise RuntimeError("Preparation receipt changed after submission")
    if digest(root / "workflow-api.json") != receipt["apiSha256"]:
        raise RuntimeError("Submitted workflow changed")
    verify_texture_submission(record, receipt)
    verify_texture_api(root, record, read_json(root / "workflow-api.json"))
    service = Comfy(args.service or receipt['service'])
    if 'promptId' not in receipt:
        if not receipt.get('clientId') or receipt.get('state') == 'rejected':
            raise RuntimeError('Submission result is uncertain/rejected; inspect receipt, do not resubmit')
        api = read_json(root / 'workflow-api.json')
        queue = service.request('/queue')
        history = service.request('/history')
        receipt['promptId'] = recover_prompt_id(receipt, api, queue, history)
        receipt['recoveredBy'] = 'persisted client ID and exact submitted graph in queue/history'
        save_json(root / 'generation.json', receipt)
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
