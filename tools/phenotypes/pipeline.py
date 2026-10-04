"""Reproducible local ComfyUI multiview generation for SRN's 20 body variants.

Run with the bundled workspace Python. Generated files belong under output/.
No Meshy service, remote generation, or installed game files are used here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

import numpy as np
from PIL import Image, ImageDraw

RACES = {
    "human": {"family": "h", "appearance": 6, "height": {"male": 1.75, "female": 1.65}},
    "elf": {"family": "e", "appearance": 1, "height": {"male": 1.90, "female": 1.85}},
    "dwarf": {"family": "d", "appearance": 0, "height": {"male": 1.20, "female": 1.15}},
    "orc": {"family": "o", "appearance": 5, "height": {"male": 1.90, "female": 1.80}},
    "troll": {"family": "g", "appearance": 2, "height": {"male": 2.50, "female": 2.30}},
}
HEIGHT_TARGETS = json.loads(Path(__file__).with_name("height_targets.json").read_text())
for race, info in RACES.items():
    info["referenceHeight"] = HEIGHT_TARGETS["referenceHeights"][race]
    info["height"] = {sex: height * HEIGHT_TARGETS["uniformReferenceScale"]
                      for sex, height in info["referenceHeight"].items()}
VIEWS = ("front", "left", "back", "right")
WORKFLOW_NAME = "SR_NWN_3d_pixal3d_multi_views.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


class Comfy:
    def __init__(self, base: str):
        self.base = base.rstrip("/")

    def request(self, path: str, value=None):
        data = None if value is None else json.dumps(value).encode()
        req = urllib.request.Request(self.base + path, data=data,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=90) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"ComfyUI HTTP {exc.code}: {exc.read().decode()}") from exc

    def upload(self, image_path: Path, subfolder: str) -> str:
        boundary = "srn-" + uuid.uuid4().hex
        fields = {"type": "input", "subfolder": subfolder, "overwrite": "false"}
        chunks = []
        for name, value in fields.items():
            chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
        chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{image_path.name}"\r\nContent-Type: image/png\r\n\r\n'.encode())
        chunks.extend((image_path.read_bytes(), f"\r\n--{boundary}--\r\n".encode()))
        req = urllib.request.Request(self.base + "/upload/image", data=b"".join(chunks),
                                     headers={"Content-Type": "multipart/form-data; boundary=" + boundary})
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.load(response)
        return "/".join(filter(None, (result.get("subfolder"), result["name"])))


def prepare(reference_dir: Path, output: Path) -> dict:
    records = []
    overview = Image.new("RGB", (1024, 20 * 270), "#20242b")
    draw = ImageDraw.Draw(overview)
    for race, info in RACES.items():
        for gender in ("male", "female"):
            for body_type, phenotype in (("fit", 0), ("large", 2)):
                slug = f"{race}_{gender}_{body_type}"
                source = reference_dir / (slug + ".png")
                image = Image.open(source).convert("RGB")
                if image.size != (1916, 821):
                    raise ValueError(f"Review unfamiliar sheet dimensions for {source}: {image.size}")
                # Annotation hue is cyan; figures have warmer/neutral materials. Views
                # are not uniformly spaced, and heads sometimes extend above the title.
                arr = np.array(image).copy()
                rgb = arr.astype(np.int16)
                cyan = (rgb[:, :, 1] > rgb[:, :, 0] + 5) & (rgb[:, :, 2] > rgb[:, :, 0] + 5)
                arr[cyan] = 0
                profile = (arr[70:755].max(axis=2) > 20).sum(axis=0) > 8
                # Merge tiny gaps caused by disconnected fingers; leave view gaps.
                starts = np.flatnonzero(profile & ~np.r_[False, profile[:-1]])
                ends = np.flatnonzero(profile & ~np.r_[profile[1:], False]) + 1
                spans = []
                for start, end in zip(starts, ends):
                    if spans and start - spans[-1][1] < 25:
                        spans[-1][1] = int(end)
                    else:
                        spans.append([int(start), int(end)])
                spans = [s for s in spans if s[1] - s[0] > 60]
                if len(spans) != 4:
                    raise ValueError(f"Review ambiguous view spans for {slug}: {spans}")
                separators = [0] + [(spans[i][1] + spans[i + 1][0]) // 2 for i in range(3)] + [1916]
                columns = []
                for index, view in enumerate(VIEWS):
                    box = (separators[index], 0, separators[index + 1], 821)
                    column_arr = arr[:, box[0]:box[2]].copy()
                    mask = column_arr.max(axis=2) > 20
                    yy, xx = np.nonzero(mask)
                    if len(xx) < 15000:
                        raise ValueError(f"Insufficient figure coverage: {slug}/{view}")
                    bounds = (int(xx.min()), int(yy.min()), int(xx.max()) + 1, int(yy.max()) + 1)
                    if bounds[0] == 0 or bounds[2] == column_arr.shape[1] or bounds[1] == 0 or bounds[3] == 821:
                        raise ValueError(f"Figure touches crop boundary; adjust explicitly: {slug}/{view} {bounds}")
                    columns.append((view, Image.fromarray(column_arr), bounds, box))
                # Shared source pixel scale and shared vertical framing across all four views.
                top = min(c[2][1] for c in columns)
                bottom = max(c[2][3] for c in columns)
                side = int(np.ceil(max(bottom - top, max(c[2][2] - c[2][0] for c in columns)) * 1.1))
                view_records = {}
                for view, column, bounds, box in columns:
                    figure = column.crop((bounds[0], top, bounds[2], bottom))
                    square = Image.new("RGB", (side, side), "black")
                    square.paste(figure, ((side - figure.width) // 2, (side - figure.height) // 2))
                    square = square.resize((1024, 1024), Image.Resampling.LANCZOS)
                    path = output / slug / "views" / (view + ".png")
                    path.parent.mkdir(parents=True, exist_ok=True)
                    square.save(path)
                    view_records[view] = {"path": str(path.resolve()), "sha256": digest(path),
                                          "sheetCrop": box, "figureBounds": bounds, "sharedCanvas": side}
                    overview.paste(square.resize((256, 256)), (VIEWS.index(view) * 256, len(records) * 270 + 14))
                draw.text((4, len(records) * 270), slug, fill="white")
                records.append({"slug": slug, "race": race, "gender": gender, "bodyType": body_type,
                                "phenotype": phenotype, "family": info["family"], "appearance": info["appearance"],
                                "heightMeters": info["height"][gender], "source": str(source.resolve()),
                                "sourceSha256": digest(source), "views": view_records,
                                "status": {"generation": "pending", "geometry": "pending", "animations": "pending",
                                           "palette": "pending", "equipment": "pending", "client": "pending"}})
    overview.save(output / "prepared-views.png")
    result = {"schemaVersion": 1, "workflow": WORKFLOW_NAME, "combinations": records}
    save_json(output / "manifest.json", result)
    return result


def compile_prompt(workflow: dict, schemas: dict) -> dict:
    links = {link[0]: link for link in workflow["links"]}
    prompt = {}
    for node in workflow["nodes"]:
        kind = node["type"]
        if kind not in schemas or node.get("mode", 0) != 0:
            continue
        schema = schemas[kind].get("input", {})
        permitted = set(schema.get("required", {})) | set(schema.get("optional", {}))
        values = node.get("widgets_values_named") or {}
        inputs = {k: v for k, v in values.items() if k in permitted or "." in k}
        for item in node.get("inputs", []):
            if item.get("link") is not None:
                link = links[item["link"]]
                inputs[item["name"]] = [str(link[1]), link[2]]
        prompt[str(node["id"])] = {"class_type": kind, "inputs": inputs}
    return prompt


def ancestors(prompt: dict, outputs: tuple[str, ...]) -> dict:
    selected = set()
    def visit(key):
        if key in selected:
            return
        selected.add(key)
        for value in prompt[key]["inputs"].values():
            if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and value[0] in prompt:
                visit(value[0])
    for key in outputs:
        visit(key)
    return {k: v for k, v in prompt.items() if k in selected}


def submit(service: Comfy, output: Path, slug: str, resolution: int, texture_size=2048,
           compact_bake=False, reuse_failed_inputs=False) -> dict:
    manifest = json.loads((output / "manifest.json").read_text())
    record = next(r for r in manifest["combinations"] if r["slug"] == slug)
    if digest(Path(record["source"]))!=record["sourceSha256"]:
        raise RuntimeError("Reference source changed after normalization")
    for view in VIEWS:
        info=record["views"][view]
        if digest(Path(info["path"]))!=info["sha256"]:
            raise RuntimeError("Normalized reference changed: "+view)
    directory = output / slug
    receipt_path = directory / "generation.json"
    previous_prompt=None
    previous=None
    if receipt_path.exists():
        previous = json.loads(receipt_path.read_text())
        history = service.request("/history/" + previous["promptId"])
        if previous["promptId"] not in history or history[previous["promptId"]].get("status", {}).get("completed"):
            raise ValueError("Existing pending/completed prompt: use status; do not duplicate generation")
        if history[previous["promptId"]].get("status", {}).get("status_str") != "error":
            raise ValueError("Only a recorded failed generation may be retried")
        save_json(directory / ("generation-failed-" + previous["promptId"] + ".json"), previous)
        archive=directory/"attempts"/previous["promptId"]
        save_json(archive/"generation.json",previous)
        save_json(archive/"history.json",history[previous["promptId"]])
        prior_api=directory/"workflow-api.json"
        if prior_api.exists():
            previous_prompt=json.loads(prior_api.read_text())
            save_json(archive/"workflow-api.json",previous_prompt)
    workflow = service.request("/userdata/" + urllib.parse.quote("workflows/" + WORKFLOW_NAME, safe=""))
    schemas = service.request("/object_info")
    save_json(output / "workflow-source.json", workflow)
    prompt = compile_prompt(workflow, schemas)
    upload_id = uuid.uuid4().hex[:12]
    if reuse_failed_inputs:
        if previous_prompt is None or previous["sourceSha256"]!=record["sourceSha256"]:
            raise RuntimeError("Input reuse requires a recorded failed prompt with the same source")
        prompt=previous_prompt
    uploaded_inputs=[]
    for i, view in enumerate(VIEWS):
        key = str(1000 + i)
        if reuse_failed_inputs:
            name=prompt[key]["inputs"]["image"]
        else:
            name = service.upload(Path(record["views"][view]["path"]), f"srn_phenotypes/{slug}/{upload_id}")
        remote=Path(name)
        query=urllib.parse.urlencode({"filename":remote.name,"subfolder":str(remote.parent).replace("\\","/"),"type":"input"})
        with urllib.request.urlopen(service.base+"/view?"+query,timeout=30) as response:
            remote_hash=hashlib.sha256(response.read()).hexdigest()
        if remote_hash!=record["views"][view]["sha256"]:
            raise RuntimeError("Uploaded input changed: "+view)
        uploaded_inputs.append({"view":view,"serverImage":name,"sha256":remote_hash,
                                "sourcePath":record["views"][view]["path"]})
        prompt[key] = {"class_type": "LoadImage", "inputs": {"image": name}}
        prompt["324"]["inputs"][view] = [key, 0]
    for view in VIEWS:
        if view not in record.get("conditioningViews", VIEWS):
            prompt["324"]["inputs"].pop(view, None)
    prompt["288"]["inputs"]["value"] = texture_size
    if compact_bake:
        # The raw decoded mesh can exceed 100 million faces. Project to the
        # existing remeshed surface used by the workflow's normal/AO bakes.
        prompt["147"]["inputs"]["reference_mesh"]=["241",0]
    prompt["186"]["inputs"]["target_face_count"] = 50000
    prompt["94"]["inputs"]["target_resolution"] = resolution
    prefix = f"srn_phenotypes/{slug}/{upload_id}"
    prompt["372"]["inputs"]["filename_prefix"] = prefix + "/textured"
    # Preserve the shape master as a separate output for later rebakes/retopology.
    prompt["1010"] = {"class_type": "Save3DAdvanced", "inputs": {
        "model_3d": ["282", 0], "filename_prefix": prefix + "/shape-master",
        "viewport_state": "", "width": 1024, "height": 1024}}
    prompt = ancestors(prompt, ("372", "1010"))
    save_json(directory / "workflow-api.json", prompt)
    response = service.request("/prompt", {"prompt": prompt, "client_id": "srn-phenotypes-" + upload_id,
                                          "extra_data": {"extra_pnginfo": {"workflow": workflow}}})
    if response.get("node_errors"):
        raise RuntimeError(json.dumps(response["node_errors"]))
    receipt = {"slug": slug, "promptId": response["prompt_id"], "submitted": time.time(),
               "uploadedInputs":uploaded_inputs,"pipelineSha256":digest(Path(__file__)),
               "workflowSourceSha256":digest(output/"workflow-source.json"),
               "resolution": resolution, "sourceSha256": record["sourceSha256"],
               "textureSize":texture_size,"compactBakeReference":compact_bake,
               "reusedFailedInputs":reuse_failed_inputs,
               "apiSha256": digest(directory / "workflow-api.json"), "outputPrefix": prefix}
    save_json(receipt_path, receipt)
    archive=directory/"attempts"/receipt["promptId"]
    save_json(archive/"generation.json",receipt)
    save_json(archive/"workflow-api.json",prompt)
    save_json(archive/"workflow-source.json",workflow)
    print(json.dumps(receipt), flush=True)
    return receipt


def status(service: Comfy, output: Path, slug: str):
    path = output / slug / "generation.json"
    receipt = json.loads(path.read_text())
    history = service.request("/history/" + receipt["promptId"])
    if receipt["promptId"] not in history:
        queue = service.request("/queue")
        print(json.dumps({"slug": slug, "promptId": receipt["promptId"], "state": "queued/running",
                          "running": len(queue["queue_running"]), "pending": len(queue["queue_pending"])}))
        return
    result = history[receipt["promptId"]]
    save_json(output / slug / "history.json", result)
    save_json(output / slug / "attempts" / receipt["promptId"] / "history.json",result)
    files = []
    if result["status"].get("status_str") == "success":
        for node in result.get("outputs", {}).values():
            for group in node.values():
                if isinstance(group, list):
                    files += [v for v in group if isinstance(v, dict) and "filename" in v]
        destination = output / slug / "generated"
        destination.mkdir(exist_ok=True)
        for item in files:
            query = urllib.parse.urlencode({k: item[k] for k in ("filename", "subfolder", "type") if k in item})
            filename = Path(item["filename"]).name
            target = destination / filename
            with urllib.request.urlopen(service.base + "/view?" + query, timeout=120) as response:
                data = response.read()
            target.write_bytes(data)
            item["localPath"] = str(target.resolve())
            item["sha256"] = digest(target)
        receipt["outputs"] = files
        receipt["status"] = "success"
        save_json(path, receipt)
        manifest_path = output / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        next(r for r in manifest["combinations"] if r["slug"] == slug)["status"]["generation"] = "success"
        save_json(manifest_path, manifest)
    errors=[{k:data.get(k) for k in ("node_id","node_type","exception_type","exception_message")}
            for event,data in result["status"].get("messages",[]) if event=="execution_error"]
    print(json.dumps({"slug": slug, "promptId":receipt["promptId"],
                      "status":result["status"].get("status_str"),"errors":errors,"files": files}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "submit", "status"))
    parser.add_argument("--reference-dir", type=Path)
    parser.add_argument("--output", type=Path, default=Path("output/phenotypes"))
    parser.add_argument("--service", default="http://127.0.0.1:8188")
    parser.add_argument("--slug")
    parser.add_argument("--resolution", type=int, choices=(1024, 1536), default=1536)
    parser.add_argument("--texture-size",type=int,choices=(512,1024,2048),default=2048)
    parser.add_argument("--compact-bake-reference",action="store_true")
    parser.add_argument("--reuse-failed-inputs",action="store_true")
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.action == "prepare":
        if not args.reference_dir:
            parser.error("prepare requires --reference-dir")
        result = prepare(args.reference_dir, args.output)
        print(f"Prepared {len(result['combinations'])} combinations; inspect prepared-views.png")
    else:
        if not args.slug:
            parser.error("submit/status requires --slug")
        if args.action == "submit":
            submit(Comfy(args.service), args.output, args.slug, args.resolution,args.texture_size,
                   args.compact_bake_reference,args.reuse_failed_inputs)
        else:
            status(Comfy(args.service), args.output, args.slug)


if __name__ == "__main__":
    main()
