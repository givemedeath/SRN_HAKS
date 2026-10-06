"""Meshy plugin CLI adapter with reservation-first dispatch and explicit resume.

Run through the shared launcher. Bind the executable command in ignored local
configuration; credentials stay in Meshy's own credential store. No API calls or
credential reads are performed by this adapter.
"""
import argparse
import os
from pathlib import Path
import subprocess

from head_workflow import Session, pin, read, require, task_fields, validate_remesh, verify_pins, write_fresh


def validate_binding(binding):
    """Use a direct offline Node entry point, never PATH/npx package resolution."""
    verify_pins(binding["inputs"])
    command = binding["command"]
    require(isinstance(command, list) and len(command) == 2
            and all(isinstance(value, str) and Path(value).is_absolute() for value in command),
            'Direct absolute byte-pinned Node and Meshy entry point required; PATH/npx dispatch is unsupported')
    declared = {str(Path(item['path']).resolve()) for item in binding['inputs']}
    require(all(str(Path(value).resolve()) in declared for value in command), 'CLI executable/entry point not declared')
    root = Path(binding['dependencyRoot']).resolve()
    package = root / 'meshy-cli'
    metadata = read(package / 'package.json')
    require(metadata.get('name') == 'meshy-cli' and metadata.get('version') == '0.4.0', 'Pinned Meshy plugin CLI 0.4.0 required')
    entry = metadata.get('bin')
    entry = entry.get('meshy') if isinstance(entry, dict) else entry
    require(isinstance(entry, str) and (package/entry).resolve().is_relative_to(package)
            and (package/entry).resolve() == Path(command[1]).resolve(), 'Command differs from the pinned Meshy package entry point')
    members = {str(path.resolve()) for path in root.rglob('*') if path.is_file()}
    pinned_members = {path for path in declared if Path(path).is_relative_to(root)}
    require(members and members == pinned_members, 'Declare the complete offline CLI dependency tree and refresh changed membership')
    require(isinstance(binding.get('workspace'), str) and Path(binding['workspace']).is_absolute(), 'Absolute ignored CLI workspace required')
    return command


def prepare_output(output):
    output = Path(output)
    require(not output.exists(), 'Fresh CLI operation folder required')
    output.mkdir(parents=True)
    for name in ('stdout.json', 'stderr.log'):
        with (output/name).open('x', encoding='utf-8'):
            pass


def invoke(binding, arguments, output, *, prepared=False, request_inputs=None):
    command = validate_binding(binding)
    output = Path(output)
    if not prepared:
        prepare_output(output)
    else:
        require(output.is_dir() and all((output/name).is_file() and (output/name).stat().st_size == 0
                for name in ('stdout.json', 'stderr.log')), 'Prepared CLI output changed before dispatch')
    env = os.environ.copy()
    for key in ('NODE_OPTIONS', 'NODE_PATH'):
        env.pop(key, None)
    if request_inputs:
        verify_pins(request_inputs)
    with (output / "stdout.json").open("w", encoding="utf-8") as stdout, \
            (output / "stderr.log").open("w", encoding="utf-8") as stderr:
        result = subprocess.run([*command, "--output-schema", "v1", "--format", "json",
                                 "--no-update-check", "--workspace", binding["workspace"], *arguments],
                                stdout=stdout, stderr=stderr, env=env, check=False)
    validate_binding(binding)
    write_fresh(output / "operation.json", {"kind": "srn-head-meshy-cli-operation", "exitCode": result.returncode,
                "cliInputs": binding["inputs"], "stdout": pin(output / "stdout.json"),
                "stderr": pin(output / "stderr.log")})
    return result.returncode, output / "stdout.json"


def dispatch(session, request_file, binding_file, output):
    request, binding = read(request_file), read(binding_file)
    validate_binding(binding)
    require(request["operation"] in ("multi-image-to-3d", "remesh", "retexture"), "Unsupported operation")
    verify_pins(request["inputs"])
    require(not any(Path(p["path"]).resolve() == Path(request_file).resolve() for p in request["inputs"]),
            "Request cannot pin itself")
    payload = Path(output).with_name(Path(output).name + "-payload.json")
    require(not payload.exists() and not Path(output).exists(), 'Fresh payload and CLI operation paths required')
    arguments = [request["operation"], "create", "--async", "--operation-id", request["requestId"],
                 "--include-raw", "--data", "@"+str(payload.resolve())]
    if request["operation"] == "multi-image-to-3d":
        arguments += ["--image-urls", ",".join(request["payload"]["image_urls"]),
                      "--should-texture", "false", "--remove-lighting", "false", "--target-formats", "glb"]
    elif request['operation']=='retexture':
        payload=request['payload']
        require(payload.get('enable_original_uv') is True and payload.get('enable_pbr') is True
                and payload.get('texture_resolution')=='2k','Qualified UV-preserving 2K PBR request required')
        require('input_task_id' not in payload,'Retexture the selected local geometry, not the generation master')
        arguments += ['--model-url',payload['model_url'],'--enable-original-uv','true',
                      '--enable-pbr','true','--texture-resolution','2k','--target-formats','glb',
                      '--remove-lighting','false']
        if payload.get('multiview_image_urls'):
            arguments += ['--multiview-image-urls',','.join(payload['multiview_image_urls'])]
        elif payload.get('image_style_url'):
            arguments += ['--image-style-url',payload['image_style_url']]
        else:
            arguments += ['--text-style-prompt',payload['text_style_prompt']]
    elif request['operation']=='remesh':
        payload=request['payload']
        validate_remesh(payload)
        arguments += ['--topology',payload['topology'],'--target-polycount',str(payload['target_polycount']),'--target-formats','glb']
        if payload.get('input_task_id'): arguments += ['--input-task-id',payload['input_task_id']]
        else: arguments += ['--model-url',payload['model_url']]
    if binding.get("project"):
        arguments += ["--project", binding["project"], "--stage", request["operation"]]
    require(all(isinstance(value, str) for value in arguments), 'CLI arguments must be strings')
    # Finish deterministic validation and writable-path setup before reserving.
    # Output files are kept as evidence if a later gate rejects the request.
    payload_path = Path(output).with_name(Path(output).name + '-payload.json')
    write_fresh(payload_path, request['payload'])
    payload_pin = pin(payload_path)
    require(read(payload_path) == request['payload'], 'Prepared payload differs from the frozen request')
    prepare_output(output)
    request_inputs = [*request['inputs'], *binding['inputs'], pin(request_file), pin(binding_file), payload_pin]
    session.reserve(request["designId"], request["requestId"], request["operation"],
                    request["estimatedCredits"], request_inputs, request["payload"])
    code, response = invoke(binding, arguments, output, prepared=True, request_inputs=request_inputs)
    if code:
        raise ValueError("Meshy submission is uncertain; reconcile CLI journal and task history before another attempt")
    task_id = task_fields(read(response))["id"]
    require(bool(task_id), "Submission task identity missing; reconcile history")
    session.record_task(request["requestId"], task_id, request["operation"], response)
    return task_id


def wait(session, request_id, binding_file, output):
    event = next((e for e in session.events() if e["kind"] == "submitted" and e["requestId"] == request_id), None)
    require(event is not None, "Explicit recorded task required for resume")
    binding = read(binding_file)
    arguments = [event["resource"], "wait", event["taskId"], "--timeout", "600", "--include-raw"]
    if binding.get("project"):
        arguments += ["--project", binding["project"]]
    code, response = invoke(binding, arguments, output)
    actual = task_fields(read(response))
    if actual.get("status") in ("SUCCEEDED", "FAILED", "CANCELED") and type(actual.get("credits")) is int:
        session.settle(request_id, actual["status"], actual["credits"], response)
    require(code == 0 and actual.get("status") == "SUCCEEDED", "Task incomplete/failed; reservation remains until reconciled")
    return actual["id"]


def collect(session, request_id, binding_file, output):
    settled = next((e for e in session.events() if e["kind"] == "settled" and e["requestId"] == request_id), None)
    require(settled is not None and settled["status"] == "SUCCEEDED", "Successful owning task required")
    verify_pins([settled["result"]])
    source = settled["result"]["path"]
    binding = read(binding_file)
    assets = Path(binding["workspace"]) / "source-bank" / Path(output).name
    require(not assets.exists(), "Fresh source bank required")
    code, response = invoke(binding, ["download", "--task-json", source, "--all",
                                               "--output-dir", str(assets.resolve())], output)
    require(code == 0 and assets.exists(), "Asset download incomplete; retain and reconcile partial output")
    files = [pin(path) for path in sorted(assets.rglob("*")) if path.is_file()]
    require(files and any(Path(item["path"]).suffix == ".glb" for item in files), "Source GLB master missing")
    verify_pins([settled["result"], *files])
    write_fresh(Path(output) / "collection.json", {"kind":"srn-head-collection", "requestId":request_id,
                "task":task_fields(read(source)), "response":settled["result"], "files":files,
                "productionAccepted":False})
    return task_fields(read(source))["id"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["dispatch", "wait", "collect"])
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--request", type=Path)
    parser.add_argument("--request-id")
    args = parser.parse_args()
    session = Session(args.session)
    if args.command == "dispatch":
        identity = dispatch(session, args.request, args.binding, args.output)
    elif args.command == "wait":
        identity = wait(session, args.request_id, args.binding, args.output)
    else:
        identity = collect(session, args.request_id, args.binding, args.output)
    print(identity)
