"""Pack converted candidates and build an isolated, repeatable client fixture."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from tool_runtime import tool as resolved_tool

from pipeline import digest, save_json


def field(kind, value):
    return {"type": kind, "value": value}


def structure(kind, **values):
    return {"__data_type": kind, "__struct_id": -1, **values}


def torso_inspection_phases():
    """One-shot schedule, measured from the first PC entry into the module."""
    phases = [
        {"seconds": 10, "phase": "front-idle", "facing": 90.0, "pose": "idle"},
        {"seconds": 30, "phase": "rear-idle", "facing": 270.0, "pose": "idle"},
        {"seconds": 50, "phase": "side-idle", "facing": 180.0, "pose": "idle"},
        {"seconds": 70, "phase": "rear-crouch", "facing": 270.0, "pose": "crouch"},
        {"seconds": 95, "phase": "front-raised", "facing": 90.0, "pose": "conjure1"},
        {"seconds": 115, "phase": "rear-raised", "facing": 270.0, "pose": "conjure1"},
        {"seconds": 135, "phase": "complete-front-idle", "facing": 90.0, "pose": "idle"},
    ]
    animations = {"idle": "ANIMATION_LOOPING_PAUSE2", "crouch": "ANIMATION_LOOPING_GET_LOW",
                  "conjure1": "ANIMATION_LOOPING_CONJURE1"}
    for index, phase in enumerate(phases):
        next_onset = phases[index + 1]["seconds"] if index + 1 < len(phases) else None
        phase["animationConstant"] = animations[phase["pose"]]
        phase["durationSeconds"] = next_onset - phase["seconds"] + 5 if next_onset is not None else 6
        phase["screenshotStartSeconds"] = phase["seconds"] + 3
        phase["screenshotBeforeSeconds"] = next_onset
    return phases


def torso_inspection_script(slugs, target, pitch, distance, height):
    """Generate fixture commands only; no model, rig or material operations."""
    phases = torso_inspection_phases()
    source = '''void ObserveTorsoInspectionActor(string phase) {
  WriteTimestampedLogEntry("PHENOTYPE_TORSO_OBSERVED_STATE phase="+phase+" actor="+GetTag(OBJECT_SELF)+" action="+IntToString(GetCurrentAction())+" dead="+IntToString(GetIsDead(OBJECT_SELF)));
}
void SetTorsoInspectionPose(string phase, int animation, float duration) {
  ClearAllActions(TRUE); SetFacing(270.0);
  if(animation>=0) ActionPlayAnimation(animation,1.0,duration);
  WriteTimestampedLogEntry("PHENOTYPE_TORSO_POSE_COMMAND phase="+phase+" actor="+GetTag(OBJECT_SELF)+" animation="+IntToString(animation));
  DelayCommand(2.0,ObserveTorsoInspectionActor(phase));
}
void SetTorsoInspectionCamera(string phase, float facing) {
  object p=OBJECT_SELF;
  LockCameraPitch(p,FALSE); LockCameraDistance(p,FALSE); SetCameraLimits(p);
  AttachCamera(p,p,FALSE); SetCameraMode(p,CAMERA_MODE_TOP_DOWN);
  SetCameraHeight(p,HEIGHT);
  object target=GetObjectByTag("TARGET");
  if(!GetIsObjectValid(target)) {
    WriteTimestampedLogEntry("PHENOTYPE_TORSO_CAMERA_MISSING phase="+phase); return;
  }
  AttachCamera(p,target,FALSE); SetCameraFacing(facing,DISTANCE,PITCH);
  WriteTimestampedLogEntry("PHENOTYPE_TORSO_CAMERA_COMMAND phase="+phase+" target="+GetTag(target)+" facing="+FloatToString(facing));
}
void RunTorsoInspectionPhase(object p, string phase, float facing, int animation, float duration) {
  WriteTimestampedLogEntry("PHENOTYPE_TORSO_PHASE phase="+phase);
  if(GetIsObjectValid(p)) {
    AssignCommand(p,SetTorsoInspectionCamera(phase,facing));
    SendMessageToPC(p,"Torso inspection: "+phase);
  }
  int i=0; for(i=0;i<ACTOR_COUNT;i++) {
    object actor=GetObjectByTag("pt_"+IntToString(i));
    if(GetIsObjectValid(actor)) AssignCommand(actor,SetTorsoInspectionPose(phase,animation,duration));
    else WriteTimestampedLogEntry("PHENOTYPE_TORSO_ACTOR_MISSING phase="+phase+" tag=pt_"+IntToString(i));
  }
  if(phase=="complete-front-idle") {
    SetLocalInt(GetModule(),"TORSO_INSPECTION_COMPLETE",1);
    WriteTimestampedLogEntry("PHENOTYPE_TORSO_SEQUENCE_COMPLETE");
  }
}
void StartTorsoInspection(object p) {
  if(GetLocalInt(GetModule(),"TORSO_INSPECTION_STARTED")) return;
  SetLocalInt(GetModule(),"TORSO_INSPECTION_STARTED",1);
  WriteTimestampedLogEntry("PHENOTYPE_TORSO_SEQUENCE_START");
'''
    for key, value in {"HEIGHT": height, "DISTANCE": distance, "PITCH": pitch,
                       "TARGET": "pt_" + str(slugs.index(target)), "ACTOR_COUNT": len(slugs)}.items():
        source = source.replace(key, str(value))
    animations = {"idle": "ANIMATION_LOOPING_PAUSE2", "crouch": "ANIMATION_LOOPING_GET_LOW",
                  "conjure1": "ANIMATION_LOOPING_CONJURE1"}
    for phase in phases:
        source += ('  AssignCommand(GetModule(),DelayCommand(' + str(float(phase["seconds"])) +
                   ',RunTorsoInspectionPhase(p,"' + phase["phase"] + '",' +
                   str(phase["facing"]) + ',' + animations[phase["pose"]] + ',' +
                   str(float(phase["durationSeconds"])) + ')));\n')
    return source + '}\n'


def validate_owned_normal_dependencies(resources, material_hashes):
    """Reject native promotion when owned tangent materials were absent at compile time."""
    owned = {p.name.lower(): p for p in resources.iterdir() if p.is_file()}
    for material in sorted(resources.glob("*.mtr")):
        text = re.sub(r"//[^\n]*", "", material.read_text(encoding="ascii"))
        if not re.search(r'(?im)^\s*renderhint\s+"?NormalTangents"?\s*$', text):
            continue
        if material_hashes.get(material.name) != digest(material):
            raise RuntimeError("Missing/stale compile-time NormalTangents material: " + material.name)
        # Fixed pelvis underwear also owns a diffuse texture0. Both bindings
        # must match the actual compiler dependencies, not only the normal map.
        for match in re.finditer(r'(?im)^\s*texture[01]\s+"?([^\s"]+)"?\s*$', text):
            reference = match.group(1).lower()
            names = [reference] if reference.endswith((".tga", ".dds")) else [reference + ".tga", reference + ".dds"]
            # Installed textures outside this candidate are not newly owned dependencies.
            # Require every locally owned variant; both formats may exist and resolution
            # precedence must not silently pick an unrecorded compile-time image.
            for name in names:
                texture = owned.get(name)
                if texture is not None and material_hashes.get(texture.name) != digest(texture):
                    raise RuntimeError("Missing/stale compile-time NormalTangents texture: " + texture.name)


def locomotion_script(mode):
    """Arrival-driven route: never interrupt movement on a timed heartbeat."""
    return '''void ObserveLocomotion() {
  vector v=GetPosition(OBJECT_SELF);
  WriteTimestampedLogEntry("PHENOTYPE_LOCOMOTION_STATE actor="+GetTag(OBJECT_SELF)+" mode=MODE cycle="+IntToString(GetLocalInt(OBJECT_SELF,"LOCO_CYCLE"))+" action="+IntToString(GetCurrentAction())+" x="+FloatToString(v.x)+" y="+FloatToString(v.y)+" z="+FloatToString(v.z));
  DelayCommand(2.0,ObserveLocomotion());
}
void main() {
  if(!GetLocalInt(OBJECT_SELF,"LOCO_OBSERVING")) {
    SetLocalInt(OBJECT_SELF,"LOCO_OBSERVING",1);
    DelayCommand(2.0,ObserveLocomotion());
  }
  int cycle=GetLocalInt(OBJECT_SELF,"LOCO_CYCLE")+1;
  SetLocalInt(OBJECT_SELF,"LOCO_CYCLE",cycle);
  location home=GetLocalLocation(OBJECT_SELF,"HOME");
  vector out=GetPositionFromLocation(home); out.y+=24.0;
  WriteTimestampedLogEntry("PHENOTYPE_LOCOMOTION_ROUTE actor="+GetTag(OBJECT_SELF)+" mode=MODE cycle="+IntToString(cycle));
  ActionMoveToLocation(Location(GetArea(OBJECT_SELF),out,90.0),RUN);
  ActionMoveToLocation(home,RUN);
  ActionDoCommand(ExecuteScript("sr_pt_loco",OBJECT_SELF));
}
'''.replace('MODE', mode).replace('RUN', 'TRUE' if mode == 'run' else 'FALSE')


def validate_single_stock_part_inventory(converted, conversion):
    """Reject legacy/undeclared assets entering a purpose-built one-part HAK."""
    if conversion.get('geometryStatus') != 'single-stock-part-diagnostic':
        return
    models = {p['model'] + '.mdl' for p in conversion['parts']}
    if {p.name for p in (converted/'ascii').iterdir()} != models:
        raise RuntimeError('Undeclared ASCII part in stock-part stage')
    owned = conversion.get('ownedResourceHashes')
    if not owned:
        raise RuntimeError('Stock-part stage lacks explicit owned resource inventory')
    resources = converted/'resources'
    if {p.name for p in resources.iterdir()} - (set(owned) | models):
        raise RuntimeError('Undeclared resource in stock-part stage')
    for name, checksum in owned.items():
        if digest(resources/name) != checksum:
            raise RuntimeError('Stock-part owned resource changed: ' + name)


def stock_equipment_models(records, root, item):
    """Allow game fallback only for proved stock-height male Human candidates."""
    from stage_equipment_item import ARMOR_PARTS
    if item.get('ArmorPart_Robe', {}).get('value', 0):
        raise RuntimeError('Stock rigid-equipment fixture cannot prove robe behavior')
    if not any(not record.get('fixtureControl') for record in records):
        raise RuntimeError('Stock equipment fixture has no candidate to validate')
    for record in records:
        if record.get('fixtureControl'):continue
        conversion=json.loads((root/record['slug']/'converted/conversion.json').read_text())
        if (conversion.get('modelPrefix')!='pmh0'
                or conversion.get('rigMode')!='stock-exact-game-fallback'
                or conversion.get('stockOtherPartsFromGame') is not True
                or not (0<conversion.get('height',0)<10
                    and 0<conversion.get('stockReferenceHeight',-1)<10
                    and abs(conversion['height']-conversion['stockReferenceHeight'])<=1e-7)):
            raise RuntimeError('Stock equipment fallback requires exact stock-height male Human rig')
    return sorted({'pmh0_'+part+f'{int(item["ArmorPart_"+key]["value"]):03}.mdl'
        for key,part in ARMOR_PARTS.items() if 'ArmorPart_'+key in item
        and int(item['ArmorPart_'+key]['value'])>1})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("output/phenotypes"))
    parser.add_argument("--tool-directory", type=Path)
    parser.add_argument("--game-root", type=Path, required=True)
    parser.add_argument("--slugs", required=True)
    parser.add_argument("--skin-color",type=int,default=3,
                        help="Skin palette byte for all fixture actors; recorded for native palette checks")
    parser.add_argument("--lighting-profile",choices=("original","ambient","directional"),default="original",
                        help="Declared material comparison lighting; geometry and actor rigs are unchanged")
    parser.add_argument("--texture-mode", choices=("native", "rgb"), default="native",
                        help="RGB is a temporary geometry/UV diagnostic, not palette acceptance")
    parser.add_argument("--ascii-models", action="store_true", help="Use runtime compilation for diagnostics")
    parser.add_argument("--material-patch", action="store_true", help="Explicit verified runtime pelvis PLT diagnostic; preserve original compiler receipts")
    parser.add_argument("--effective-materials", action="store_true",
                        help="Verified current native body inventory with preserved compiler provenance")
    parser.add_argument("--motion-tests", action="store_true", help="Run the repeatable animation smoke sequence")
    parser.add_argument("--motion-route-distance", type=float, default=4.0,
                        help="Outward meters in the combined walk/run smoke phase (1-12)")
    parser.add_argument("--locomotion", choices=("walk", "run"),
                        help="Repeat 24-meter out/home routes with stock movement animations and unlocked camera")
    parser.add_argument("--torso-inspection-sequence", action="store_true",
                        help="One-shot 135-second bare-actor inspection; requires camera target, keeps camera unlocked")
    parser.add_argument("--gameplay-tests",action="store_true",help="Follow motion smoke with actual attacks, spells, damage and death")
    parser.add_argument("--gameplay-only",action="store_true",help="Skip the pose sequence and start gameplay after the initial inspection interval")
    parser.add_argument("--gameplay-repeat",action="store_true",help="Resurrect fixture actors and repeat gameplay for camera inspection")
    parser.add_argument("--pose", choices=("sit","kneel","crouch","pause","talk","dead-front","dead-back","conjure1","conjure2"),
                        help="Hold a repeatable pose for seam inspection")
    parser.add_argument("--equipment-template",type=Path,
                        help="Installed armor UTI JSON for staged chest020/021 proof specimens")
    parser.add_argument("--full-equipment-template",type=Path,
                        help="Installed armor UTI JSON with its complete original part selection")
    parser.add_argument("--stock-equipment-fallback",action="store_true",
                        help="Verify installed rigid armor and use game fallback on stock-height male Human; no resizing or armor overrides")
    parser.add_argument("--weapon-template",type=Path,help="Installed one-handed weapon UTI JSON for grip tests on every specimen")
    parser.add_argument("--shield-template",type=Path,help="Installed shield UTI JSON for left-hand attachment tests")
    parser.add_argument("--camera-pitch",type=float,help="Repeatable fixture camera pitch, in degrees (1-89)")
    parser.add_argument("--camera-distance",type=float)
    parser.add_argument("--camera-height",type=float,
                        help="Camera aim height in meters; zero restores the racial default")
    parser.add_argument("--camera-facing",type=float,default=90.0,
                        help="Repeatable fixture camera facing, in degrees (0-360)")
    parser.add_argument("--camera-target",help="Attach the inspection camera to this specimen slug")
    parser.add_argument("--camera-equipment-target",action="store_true",
                        help="Attach to the chosen slug's actual full-equipment actor instead of its bare actor")
    parser.add_argument("--camera-lock",action="store_true",help="Hold fixture camera pitch and distance during seam inspection")
    parser.add_argument("--entry-x",type=float,default=14.0,help="Player start on the isolated test floor")
    parser.add_argument("--entry-y",type=float,default=13.0,help="Player start on the isolated test floor")
    args = parser.parse_args()
    if args.effective_materials and (args.material_patch or args.ascii_models or args.texture_mode!='native'):
        parser.error('Effective body materials require native mode and no legacy material patch')
    if not 0 <= args.skin_color <= 255:
        parser.error('skin color must be a palette byte between 0 and 255')
    if not 1 <= args.motion_route_distance <= 12:
        parser.error('Combined motion route must be 1-12 meters to finish before the next pose')
    if args.stock_equipment_fallback and (not args.full_equipment_template or args.equipment_template):
        parser.error('Stock equipment fallback requires full-equipment-template and no adapted equipment-template')
    if args.camera_target and args.camera_target not in args.slugs.split(','):
        parser.error('Camera target must be in --slugs')
    if args.camera_equipment_target:
        if not args.full_equipment_template or not args.camera_target or args.camera_pitch is None:
            parser.error('Equipment camera requires full-equipment-template, camera-target and camera-pitch')
        if args.torso_inspection_sequence:
            parser.error('Equipment camera cannot use the bare torso inspection sequence')
    if args.locomotion:
        if args.pose or args.torso_inspection_sequence or args.motion_tests or args.gameplay_tests or args.gameplay_only or args.gameplay_repeat:
            parser.error('Standalone locomotion cannot use held-pose, torso inspection, motion or gameplay flags')
        if args.camera_lock:
            parser.error('Standalone locomotion requires an unlocked camera')
    if args.torso_inspection_sequence:
        if args.motion_tests or args.gameplay_tests or args.gameplay_only or args.gameplay_repeat or args.pose:
            parser.error("Torso inspection sequence cannot use motion, gameplay or held-pose flags")
        if args.camera_lock:
            parser.error("Torso inspection sequence requires an unlocked camera")
        if not args.camera_target or args.camera_target not in args.slugs.split(","):
            parser.error("Torso inspection sequence requires a camera target in --slugs")
        if args.camera_facing != 90.0:
            parser.error("Torso inspection sequence uses fixed front/rear/side facings; omit --camera-facing")
        if args.camera_pitch is None:
            args.camera_pitch = 75.0
    if args.camera_distance is None:
        args.camera_distance = 3.5 if args.torso_inspection_sequence else 8.0
    if args.camera_height is None:
        args.camera_height = 1.2 if args.torso_inspection_sequence else 0.0
    if args.gameplay_only or args.gameplay_repeat:
        args.gameplay_tests=True
    if args.gameplay_tests:
        if args.pose:parser.error("Gameplay tests cannot use a held pose")
        args.motion_tests=True
    if args.camera_pitch is not None and not 1 <= args.camera_pitch <= 89:
        parser.error("camera pitch must be between 1 and 89 degrees")
    if not 1 <= args.camera_distance <= 25:
        parser.error("camera distance must be between 1 and 25 meters")
    if not 0 <= args.camera_facing <= 360:
        parser.error("camera facing must be between 0 and 360 degrees")
    if not 0 <= args.camera_height <= 10:
        parser.error("camera height must be between 0 and 10 meters")
    if not (1<=args.entry_x<=79 and 1<=args.entry_y<=79):
        parser.error("entry coordinates must stay on the test floor")
    root = args.output.resolve()
    userdir = root / "userdir"
    staging = root / "test-module"
    configuration = {"slugs":args.slugs,"motion":args.motion_tests,"pose":args.pose,
                     "skinColor":args.skin_color,
                     "gameplay":args.gameplay_tests,
                     "gameplayOnly":args.gameplay_only,
                     "gameplayRepeat":args.gameplay_repeat,
                     "cameraPitch":args.camera_pitch,"cameraDistance":args.camera_distance,
                     "cameraFacing":args.camera_facing,
                     "cameraHeight":args.camera_height,
                     "cameraTarget":args.camera_target,"cameraLock":args.camera_lock,
                     "entryPosition":[args.entry_x,args.entry_y],
                     "equipmentTemplateSha256":digest(args.equipment_template) if args.equipment_template else None,
                     "fullEquipmentTemplateSha256":digest(args.full_equipment_template) if args.full_equipment_template else None,
                     "stockEquipmentFallback":args.stock_equipment_fallback,
                     "weaponTemplateSha256":digest(args.weapon_template) if args.weapon_template else None,
                     "shieldTemplateSha256":digest(args.shield_template) if args.shield_template else None,
                     "builderSha256":digest(Path(__file__))}
    if args.motion_route_distance!=4.0:
        configuration['motionRouteDistanceMeters']=args.motion_route_distance
    if args.lighting_profile!='original':
        configuration['lightingProfile']=args.lighting_profile
    if args.locomotion:
        configuration['locomotion']={'mode':args.locomotion,'outwardOffsetMeters':[0.0,24.0,0.0],
            'repeat':'arrival-driven-action-queue','arrivalTolerance':'installed-engine-default',
            'observedStateIntervalSeconds':2.0,'start':'first-actor-heartbeat-after-PC-entry',
            'bareActorsOnly':True,'floorMeters':[80,80],'cameraLocked':False,
            'animationOverride':False}
    if args.camera_equipment_target:
        configuration['cameraEquipmentTarget']=True
    configuration["fixtureResourceHashes"]={p.name:digest(p) for p in sorted((root/"fixture-resources").glob("*")) if p.is_file()}
    if args.material_patch:
        if args.ascii_models or args.texture_mode!='native':
            raise RuntimeError('Runtime material patch requires actual native-binary mode')
        configuration['runtimeMaterialPatch']=True
    if args.effective_materials:
        configuration['effectiveNativeBodyMaterials']=True
    configuration["bareAccessoryPolicy"]={"belt":0,"rightShoulder":0,"leftShoulder":0,"fleshParts":1,"head":1}
    if args.torso_inspection_sequence:
        configuration["torsoInspectionSequence"] = {
            "phases": torso_inspection_phases(), "repeat": False, "cameraLocked": False,
            "actorTags": ["pt_" + str(i) for i in range(len(args.slugs.split(",")))],
            "targetSlug": args.camera_target, "observedStateDelaySeconds": 2.0,
            "cameraPitch": args.camera_pitch, "cameraDistance": args.camera_distance,
            "cameraHeight": args.camera_height, "actorFacing": 270.0,
            "settleBeforeScreenshotSeconds": 3.0,
            "timingOrigin": "first-PC-module-entry", "idleAnimation": "ANIMATION_LOOPING_PAUSE2"}
    config_id = hashlib.sha256(json.dumps(configuration,sort_keys=True).encode()).hexdigest()[:16]
    binary = staging / "configurations" / config_id / "binary"
    json_dir = staging / "json"
    resources = staging / "hak-resources"
    for directory in (binary, json_dir, resources, userdir / "modules", userdir / "hak", userdir / "override"):
        directory.mkdir(parents=True, exist_ok=True)
    tool = args.tool_directory
    def run(name, arguments, **kwargs):
        result = subprocess.run([str(resolved_tool(name, tool)), *map(str, arguments)],
                                capture_output=True, check=True, **kwargs)
        return result.stdout.decode(errors="replace")
    manifest = json.loads((root / "manifest.json").read_text())
    slugs = args.slugs.split(",")
    records = [next(r for r in manifest["combinations"] if r["slug"] == slug) for slug in slugs]
    if args.camera_target and args.camera_target not in slugs:
        raise RuntimeError("Camera target must be a specimen in this fixture")
    if (args.camera_target or args.camera_lock) and args.camera_pitch is None:
        raise RuntimeError("Camera target/lock requires an explicit pitch")
    expected = set()
    material_patches = {}
    effective_bodies = {}
    for record in records:
        converted = root / record["slug"] / "converted"
        conversion = json.loads((converted / "conversion.json").read_text())
        validate_single_stock_part_inventory(converted, conversion)
        compile_receipt = converted / "native-compile.json"
        compile_models = {}
        if not args.ascii_models and args.texture_mode != "rgb":
            if not compile_receipt.exists():
                raise RuntimeError("Missing native compilation receipt: " + record["slug"])
            compile_data = json.loads(compile_receipt.read_text())
            if not compile_data.get("complete"):
                raise RuntimeError("Incomplete native compilation: " + record["slug"])
            material_hashes=compile_data.get("materialResourceHashes", {})
            effective_inventory=converted/'effective-material-inventory.json'
            if effective_inventory.exists():
                if not args.effective_materials or record.get('fixtureControl'):
                    raise RuntimeError('Effective native inventory requires explicit candidate-only flag')
                from effective_body_contract import validate_effective_body
                compile_data,material_hashes,effective_bodies[record['slug']]=validate_effective_body(converted)
            if (converted/'material-patch.json').exists():
                if not args.material_patch or record.get('fixtureControl'):
                    raise RuntimeError('Material patch requires explicit candidate-only diagnostic flag')
                from material_patch_contract import validate_material_patch
                material_hashes,material_patches[record['slug']]=validate_material_patch(converted)
            for name, checksum in material_hashes.items():
                dependency = converted / "resources" / name
                if not dependency.exists() or digest(dependency) != checksum:
                    raise RuntimeError("Stale compiled material dependency: " + name)
            if record['slug'] not in effective_bodies:
                validate_owned_normal_dependencies(converted / "resources",
                                                   compile_data.get("materialResourceHashes", {}))
            compile_models = {r["name"]:r for r in compile_data["models"]}
        for directory in (converted / "ascii", converted / "resources"):
            for path in directory.iterdir():
                if path.suffix not in (".mdl", ".plt", ".tga", ".dds", ".txi", ".mtr"):
                    continue
                if (args.texture_mode == "rgb" or args.ascii_models) and path.suffix == ".mdl" and directory.name == "resources":
                    continue
                if len(path.stem) > 16 or path.name.lower() != path.name:
                    raise RuntimeError("Invalid resref: " + path.name)
                if path.stat().st_size > 15 * 1024 * 1024:
                    raise RuntimeError("Oversized resource: " + path.name)
                if path.suffix == ".mdl" and directory.name == "resources":
                    cached = compile_models.get(path.name)
                    source = converted / "ascii" / path.name
                    if not cached or cached["sourceSha256"] != digest(source) or cached["binarySha256"] != digest(path):
                        raise RuntimeError("Stale compiled model: " + path.name)
                # Resources may have a binary counterpart of the same ASCII
                # model. Prefer it only when an actual output exists.
                if args.texture_mode == "rgb" and path.suffix == ".mdl" and "_" in path.stem and not path.stem.startswith("sr_a"):
                    text = path.read_text(encoding="ascii")
                    text = re.sub(r"(?m)^\s*bitmap \S+(?:\n\s*materialname \S+)?",
                                  "  bitmap " + conversion["textures"]["fixed"] +
                                  "\n  materialname " + conversion["textures"]["fixed"], text)
                    (resources / path.name).write_text(text, encoding="ascii")
                else:
                    shutil.copyfile(path, resources / path.name)
                expected.add(path.name)
    if args.material_patch and len(material_patches)!=1:
        raise RuntimeError('Exactly one verified candidate material patch required')
    if args.effective_materials and len(effective_bodies)!=1:
        raise RuntimeError('Exactly one verified candidate effective native body required')
    for path in (root/"fixture-resources").glob("*"):
        if not path.is_file() or path.suffix not in (".2da", ".set") or len(path.stem)>16:
            raise RuntimeError("Unsupported fixture-only resource: "+str(path))
        if path.name in expected:
            raise RuntimeError("Fixture resource collision: "+path.name)
        shutil.copyfile(path,resources/path.name)
        expected.add(path.name)
    fixture_set = (root / "baseline/ttr01.set").read_text(encoding="cp1252")
    fixture_set = re.sub(r"(?m)^Name=TTR01$", "Name=SR_PT", fixture_set)
    fixture_set = re.sub(r"(?m)^Density=[^\n]+", "Density=0.000", fixture_set)
    (resources / "sr_pt.set").write_text(fixture_set, encoding="cp1252")
    expected.add("sr_pt.set")
    # SET renaming also changes the engine's implicit edge-table demand.
    edge=root/"baseline/ttr01_edge.2da"
    if not edge.exists():
        data=subprocess.run([str(resolved_tool("nwn_resman_cat", tool)),"--root",str(args.game_root),
            "--userdirectory",str(userdir),"--no-ovr","ttr01_edge.2da"],capture_output=True,check=True).stdout
        if not data.startswith(b"2DA"):raise RuntimeError("Missing stock rural edge table")
        edge.write_bytes(data)
    shutil.copyfile(edge,resources/"sr_pt_edge.2da")
    expected.add("sr_pt_edge.2da")
    stale = set(p.name for p in resources.iterdir()) - expected
    if stale:
        raise RuntimeError("Staging contains stale resources: " + str(sorted(stale)))
    hak = userdir / "hak/srn_pheno_test.hak"
    if hak.exists():
        hak.unlink()
    run("nwn_erf", ["-c", "-f", hak, "-e", "HAK", resources])
    inventory = run("nwn_erf", ["-t", "-f", hak]).splitlines()
    if len(inventory) != len(expected):
        raise RuntimeError("HAK inventory mismatch")
    template = json.loads((root / "baseline/human-template.json").read_text())
    creatures = []
    columns=min(4,len(records)) if args.full_equipment_template and not args.equipment_template else 4
    for i, record in enumerate(records):
        creature = copy.deepcopy(template)
        creature.pop("__data_type", None)
        creature["__struct_id"] = 4
        for key in list(creature):
            if key.startswith("Script"):
                creature[key] = field("resref", "")
        creature.update({"Appearance_Type": field("word", record["appearance"]),
                         "Race": field("byte", record.get("raceId",record["appearance"])),
                         "Gender": field("byte", int(record["gender"] == "female")),
                         "Phenotype": field("int", record["phenotype"]),
                         "FirstName": field("cexolocstring", {"0": record["slug"].replace("_", " ")}),
                         "LastName": field("cexolocstring", {}),
                         "Tag": field("cexostring", "pt_" + str(i)),
                         "TemplateResRef": field("resref", "sr_pt_" + str(i)),
                         "FactionID": field("word", 2), "Plot": field("byte", 1),
                         "Conversation": field("resref", ""),
                         "Equip_ItemList": field("list", []), "ItemList": field("list", []),
                         "ScriptSpawn": field("resref", "sr_pt_spawn"),
                         "ScriptHeartbeat": field("resref", "sr_pt_hb"),
                         "XPosition": field("float", 12 + (i % columns) * 4),
                         "YPosition": field("float", 15 + (i // columns) * 6),
                         "ZPosition": field("float", 0),
                         "XOrientation": field("float", 0), "YOrientation": field("float", -1)})
        creatures.append(creature)
    if args.equipment_template:
        for record in records:
            if record.get("fixtureControl"):continue
            converted = root / record["slug"] / "converted"
            prefix = json.loads((converted/"conversion.json").read_text())["modelPrefix"]
            for suffix in ("chest020","chest021"):
                if not (converted/"resources"/(prefix+"_"+suffix+".mdl")).exists():
                    raise RuntimeError("Stage and compile equipment first: "+record["slug"]+" "+suffix)
        for armor_id in (20,21):
            item = json.loads(args.equipment_template.read_text())
            name = "sr_pt_a"+str(armor_id)
            for key in list(item):
                if key.startswith("ArmorPart_"):
                    item[key] = field("byte",0 if key in ("ArmorPart_Belt","ArmorPart_LShoul","ArmorPart_RShoul") else 1)
            item["ArmorPart_Torso"] = field("byte",armor_id)
            item["TemplateResRef"] = field("resref",name)
            item["Tag"] = field("cexostring",name)
            item["LocalizedName"] = field("cexolocstring",{"0":"NWNArmory chest "+str(armor_id)})
            item["Identified"] = field("byte",1)
            item["PropertiesList"] = field("list",[])
            path = json_dir/(name+".uti.json")
            save_json(path,item)
            run("nwn_gff",["-i",path,"-o",binary/(name+".uti")])
            for bare_index, bare in enumerate(creatures[:len(records)]):
                if records[bare_index].get("fixtureControl"):continue
                armored = copy.deepcopy(bare)
                index = len(creatures)
                armored["FirstName"] = field("cexolocstring",{"0":bare["FirstName"]["value"]["0"]+" armor "+str(armor_id)})
                armored["Tag"] = field("cexostring","pt_a"+str(armor_id)+"_"+str(index))
                armored["TemplateResRef"] = field("resref","sr_pt_"+str(index))
                # GIT instances do not reliably expand UTC EquippedRes
                # references. Spawn scripts create and equip these items.
                armored["Equip_ItemList"] = field("list",[])
                # The stock template is a Commoner without armor proficiency.
                # ActionEquipItem requires proficiency even for proof fixtures.
                feats = armored.setdefault("FeatList",field("list",[]))["value"]
                existing = {f["Feat"]["value"] for f in feats}
                for feat in (2,3,4):  # Installed nwscript: heavy, light, medium.
                    if feat not in existing:
                        feats.append({"__struct_id":1,"Feat":field("word",feat)})
                armored["XPosition"] = field("float",12+(index%4)*4)
                armored["YPosition"] = field("float",15+(index//4)*6)
                creatures.append(armored)
    equipment_camera_tag = None
    if args.full_equipment_template:
        from stage_equipment_item import ARMOR_PARTS
        item=json.loads(args.full_equipment_template.read_text())
        if item.get("ArmorPart_Robe",{}).get("value",0):
            raise RuntimeError("Full equipment fixture currently supports rigid armor only")
        styles={part:int(item["ArmorPart_"+key]["value"]) for key,part in ARMOR_PARTS.items()
                if "ArmorPart_"+key in item and int(item["ArmorPart_"+key]["value"])>1}
        stock_armor_proof=None
        if args.stock_equipment_fallback:
            models=stock_equipment_models(records,root,item)
            proof_dir=staging/'stock-equipment-proof';proof_dir.mkdir(exist_ok=True)
            reader=proof_dir/'reader-userdir';reader.mkdir(exist_ok=True)
            hashes={}
            for name in models:
                raw=subprocess.run([str(resolved_tool("nwn_resman_cat", args.tool_directory)),
                    '--root',str(args.game_root),'--userdirectory',str(reader),
                    '--no-ovr',name],capture_output=True,check=True).stdout
                if not raw:raise RuntimeError('Installed stock equipment missing: '+name)
                target=proof_dir/name
                if target.exists() and target.read_bytes()!=raw:
                    raise RuntimeError('Installed stock equipment changed during fixture rebuild: '+name)
                target.write_bytes(raw);hashes[name]=digest(target)
            stock_armor_proof={'modelHashes':hashes,'gameRoot':str(args.game_root.resolve()),
                'templateSha256':digest(args.full_equipment_template),'resmanSha256':digest(resolved_tool("nwn_resman_cat", args.tool_directory)),
                'identityScaling':True,'armorOverridesPacked':False,
                'limitation':'Installed-resource presence and fixture commands; actual equipped waist/hip coverage requires client evidence.'}
            save_json(proof_dir/'proof.json',stock_armor_proof)
        else:
            for record in records:
                converted=root/record["slug"]/"converted"
                prefix=json.loads((converted/"conversion.json").read_text())["modelPrefix"]
                for part,style in styles.items():
                    if not (converted/"resources"/(prefix+"_"+part+f"{style:03}.mdl")).exists():
                        raise RuntimeError("Stage and compile full equipment first: "+record["slug"]+" "+part)
        name="sr_pt_full"
        item.update({"TemplateResRef":field("resref",name),"Tag":field("cexostring",name),
                     "LocalizedName":field("cexolocstring",{"0":"Full armor fit specimen"}),
                     "Identified":field("byte",1),"PropertiesList":field("list",[])})
        path=json_dir/(name+".uti.json")
        save_json(path,item)
        run("nwn_gff",["-i",path,"-o",binary/(name+".uti")])
        for bare_index,bare in enumerate(creatures[:len(records)]):
            if args.stock_equipment_fallback and records[bare_index].get('fixtureControl'):continue
            armored=copy.deepcopy(bare);index=len(creatures)
            armored["FirstName"]=field("cexolocstring",{"0":bare["FirstName"]["value"]["0"]+" full armor"})
            armored["Tag"]=field("cexostring","pt_full_"+str(index))
            if records[bare_index]['slug'] == args.camera_target:
                equipment_camera_tag = 'pt_full_' + str(index)
            armored["TemplateResRef"]=field("resref","sr_pt_"+str(index))
            feats=armored.setdefault("FeatList",field("list",[]))["value"]
            existing={f["Feat"]["value"] for f in feats}
            for feat in (2,3,4):
                if feat not in existing:feats.append({"__struct_id":1,"Feat":field("word",feat)})
            armored["XPosition"]=field("float",12+(index%columns)*4)
            armored["YPosition"]=field("float",15+(index//columns)*6)
            creatures.append(armored)
    if args.camera_equipment_target and equipment_camera_tag is None:
        raise RuntimeError('Selected camera target has no actual full-equipment actor')
    if args.camera_equipment_target:
        configuration['cameraEquipmentActorTag'] = equipment_camera_tag
    if args.locomotion:
        configuration['locomotion']['routes'] = []
        for actor in creatures[:len(records)]:
            home = [actor[k]['value'] for k in ('XPosition','YPosition','ZPosition')]
            out = [home[0],home[1]+24.0,home[2]]
            if not (1 <= out[0] <= 79 and 1 <= out[1] <= 79):
                raise RuntimeError('Locomotion route leaves the test floor')
            configuration['locomotion']['routes'].append({'actorTag':actor['Tag']['value'],'home':home,'outward':out})
    hand_items = []
    for template_path, name, slot, proficiency in (
        (args.weapon_template,"sr_pt_sword",4,45),
        (args.shield_template,"sr_pt_shield",5,32)):
        if not template_path:continue
        item=json.loads(template_path.read_text())
        item["TemplateResRef"]=field("resref",name)
        item["Tag"]=field("cexostring",name)
        item["Identified"]=field("byte",1)
        item["PropertiesList"]=field("list",[])
        path=json_dir/(name+".uti.json")
        save_json(path,item)
        run("nwn_gff",["-i",path,"-o",binary/(name+".uti")])
        hand_items.append((name,slot))
        for creature in creatures:
            feats=creature.setdefault("FeatList",field("list",[]))["value"]
            if proficiency not in {f["Feat"]["value"] for f in feats}:
                feats.append({"__struct_id":1,"Feat":field("word",proficiency)})
    # Installed tile 120 has level grass corners and geometry at z=0 only.
    # The isolated fixture SET disables grass, which otherwise hides seams.
    tiles = [{"__struct_id": 1, "Tile_ID": field("int", 120), "Tile_Height": field("int", 0),
              "Tile_Orientation": field("int", 0), **{k: field("byte", v) for k, v in
              {"Tile_AnimLoop1": 1, "Tile_AnimLoop2": 1, "Tile_AnimLoop3": 1,
               "Tile_MainLight1": 0, "Tile_MainLight2": 0, "Tile_SrcLight1": 0, "Tile_SrcLight2": 0}.items()}}
             for _ in range(64)]
    are = structure("ARE ", Tileset=field("resref", "sr_pt"), Width=field("int", 8), Height=field("int", 8),
                    Name=field("cexolocstring", {"0": "Phenotype test floor"}),
                    Tag=field("cexostring", "sr_pt_floor"), ResRef=field("resref", "sr_pt_floor"),
                    Tile_List=field("list", tiles), Version=field("dword", 2), Flags=field("dword", 4),
                    DayNightCycle=field("byte", 0), IsNight=field("byte", 0),
                    SunAmbientColor=field("dword", 11579568), SunDiffuseColor=field("dword", 15658734),
                    MoonAmbientColor=field("dword", 11579568), MoonDiffuseColor=field("dword", 15658734),
                    FogClipDist=field("float", 80), SunShadows=field("byte", 1),
                    ShadowOpacity=field("byte", 20), SkyBox=field("byte", 0))
    if args.lighting_profile!='original':
        ambient,diffuse=(0xc0c0c0,0) if args.lighting_profile=='ambient' else (0x505050,0xeeeeee)
        for key,value in [('SunAmbientColor',ambient),('MoonAmbientColor',ambient),
                          ('SunDiffuseColor',diffuse),('MoonDiffuseColor',diffuse)]:
            are[key]=field('dword',value)
        are['SunShadows']=field('byte',int(args.lighting_profile=='directional'))
        configuration['lightingFields']={'ambientRGB':ambient,'diffuseRGB':diffuse,
                                          'sunShadows':args.lighting_profile=='directional'}
    git = structure("GIT ", **{"Creature List": field("list", creatures), "Door List": field("list", []),
                    "Placeable List": field("list", []), "TriggerList": field("list", []),
                    "WaypointList": field("list", []), "StoreList": field("list", [])})
    if args.gameplay_tests:
        dummy=copy.deepcopy(template)
        for key in list(dummy):
            if key.startswith("Script"):dummy[key]=field("resref","")
        control=next((r for r in records if r.get("fixtureControl")),None)
        dummy.update({"Appearance_Type":field("word",control["appearance"] if control else 6),
            "Race":field("byte",6),"Gender":field("byte",0),"Phenotype":field("int",0),
            "FirstName":field("cexolocstring",{"0":"Fixture target"}),"LastName":field("cexolocstring",{}),
            "Tag":field("cexostring","sr_pt_target"),"TemplateResRef":field("resref","sr_pt_target"),
            "Plot":field("byte",0),"FactionID":field("word",1),
            "CurrentHitPoints":field("short",300),"MaxHitPoints":field("short",300),"HitPoints":field("short",300),
            "Equip_ItemList":field("list",[]),"ItemList":field("list",[]),
            "ScriptSpawn":field("resref","sr_pt_tspawn"),
            "ScriptDamaged":field("resref","sr_pt_hit"),"ScriptSpellAt":field("resref","sr_pt_spell")})
        path=json_dir/"sr_pt_target.utc.json"
        save_json(path,dummy)
        run("nwn_gff",["-i",path,"-o",binary/"sr_pt_target.utc"])
        for creature in creatures:
            creature.update({"Plot":field("byte",0),"CurrentHitPoints":field("short",100),
                "MaxHitPoints":field("short",100),"HitPoints":field("short",100),
                "Int":field("byte",14),
                "ClassList":field("list",[
                    {"__struct_id":2,"Class":field("int",4),"ClassLevel":field("short",5)},
                    {"__struct_id":2,"Class":field("int",10),"ClassLevel":field("short",5)}]),
                "ScriptDamaged":field("resref","sr_pt_damage"),"ScriptDeath":field("resref","sr_pt_death")})
    ifo = structure("IFO ", Mod_Name=field("cexolocstring", {"0": "SRN Phenotype Test"}),
                    Mod_Description=field("cexolocstring", {"0": "Body, palette, motion and equipment validation."}),
                    Mod_Tag=field("cexostring", "SRN_PHENOTYPE_TEST"), Mod_Version=field("dword", 3),
                    Mod_MinGameVer=field("cexostring", "1.69"), Mod_IsSaveGame=field("byte", 0),
                    Mod_Entry_Area=field("resref", "sr_pt_floor"), Mod_Entry_X=field("float", args.entry_x),
                    Mod_Entry_Y=field("float", args.entry_y), Mod_Entry_Z=field("float", 0),
                    Mod_Entry_Dir_X=field("float", 0), Mod_Entry_Dir_Y=field("float", 1),
                    Mod_Area_list=field("list", [{"__struct_id": 6, "Area_Name": field("resref", "sr_pt_floor")}]),
                    Mod_HakList=field("list", [{"__struct_id": 8, "Mod_Hak": field("cexostring", "srn_pheno_test")}]),
                    Mod_CustomTlk=field("cexostring", ""), Mod_OnClientEntr=field("resref", "sr_pt_enter"),
                    Mod_StartYear=field("dword", 1372), Mod_StartMonth=field("byte", 1),
                    Mod_StartDay=field("byte", 1), Mod_StartHour=field("byte", 12),
                    Mod_DawnHour=field("byte", 6), Mod_DuskHour=field("byte", 18),
                    Mod_MinPerHour=field("byte", 2), Mod_XPScale=field("byte", 10))
    factions = [{"__struct_id": i, "FactionName": field("cexostring", name),
                 "FactionGlobal": field("word", 1), "FactionParentID": field("dword", 4294967295)}
                for i, name in enumerate(("PC", "Hostile", "Commoner", "Merchant", "Defender"))]
    reps = [{"__struct_id": i * 5 + j, "FactionID1": field("dword", i), "FactionID2": field("dword", j),
             "FactionRep": field("dword", 0 if args.gameplay_tests and {i,j} == {1,2} else 50)}
            for i in range(5) for j in range(5) if i != j]
    fac = structure("FAC ", FactionList=field("list", factions), RepList=field("list", reps))
    for filename, document in (("module.ifo", ifo), ("sr_pt_floor.are", are), ("sr_pt_floor.git", git), ("repute.fac", fac)):
        path = json_dir / (filename + ".json")
        save_json(path, document)
        run("nwn_gff", ["-i", path, "-o", binary / filename])
    scripts = {
        "sr_pt_spawn": """void main() {
  int i=0; for(i=0;i<18;i++) SetCreatureBodyPart(i,1);
  SetCreatureBodyPart(CREATURE_PART_BELT,0);
  SetCreatureBodyPart(CREATURE_PART_RIGHT_SHOULDER,0);
  SetCreatureBodyPart(CREATURE_PART_LEFT_SHOULDER,0);
  SetCreatureBodyPart(CREATURE_PART_HEAD,1);
  WriteTimestampedLogEntry("PHENOTYPE_BARE_PARTS "+GetName(OBJECT_SELF)+" belt="+IntToString(GetCreatureBodyPart(CREATURE_PART_BELT))+" rightShoulder="+IntToString(GetCreatureBodyPart(CREATURE_PART_RIGHT_SHOULDER))+" leftShoulder="+IntToString(GetCreatureBodyPart(CREATURE_PART_LEFT_SHOULDER)));
  SetColor(OBJECT_SELF,COLOR_CHANNEL_SKIN,3);
  SetColor(OBJECT_SELF,COLOR_CHANNEL_HAIR,5);
  string equipment=GetStringLeft(GetTag(OBJECT_SELF),7);
  if(equipment=="pt_a20_" || equipment=="pt_a21_" || GetStringLeft(GetTag(OBJECT_SELF),8)=="pt_full_") {
    string res="sr_pt_a20"; if(equipment=="pt_a21_") res="sr_pt_a21";
    if(GetStringLeft(GetTag(OBJECT_SELF),8)=="pt_full_") res="sr_pt_full";
    object armor=CreateItemOnObject(res,OBJECT_SELF);
    ActionEquipItem(armor,INVENTORY_SLOT_CHEST);
    WriteTimestampedLogEntry("PHENOTYPE_EQUIPMENT_CREATE "+GetName(OBJECT_SELF)+" valid="+IntToString(GetIsObjectValid(armor)));
  }
  SetLocalLocation(OBJECT_SELF,"HOME",GetLocation(OBJECT_SELF));
  SetLocalInt(OBJECT_SELF,"STEP",0);
  SetLocalInt(OBJECT_SELF,"READY",1);
  WriteTimestampedLogEntry("PHENOTYPE_READY "+GetName(OBJECT_SELF)+" creatureSize="+IntToString(GetCreatureSize(OBJECT_SELF)));
} """,
        "sr_pt_hb": """void main() {
  if(!GetLocalInt(OBJECT_SELF,"READY")) ExecuteScript("sr_pt_spawn",OBJECT_SELF);
  int n=GetLocalInt(OBJECT_SELF,"STEP"); SetLocalInt(OBJECT_SELF,"STEP",n+1);
  if(GetLocalInt(GetModule(),"GAMEPLAY_ONLY") && n==5) { n=22; SetLocalInt(OBJECT_SELF,"STEP",23); }
  if(GetStringLeft(GetTag(OBJECT_SELF),5)=="pt_a2" || GetStringLeft(GetTag(OBJECT_SELF),8)=="pt_full_") {
    object worn=GetItemInSlot(INVENTORY_SLOT_CHEST);
    string res="sr_pt_a20"; if(GetStringLeft(GetTag(OBJECT_SELF),7)=="pt_a21_") res="sr_pt_a21";
    if(GetStringLeft(GetTag(OBJECT_SELF),8)=="pt_full_") res="sr_pt_full";
    if(GetResRef(worn)!=res) {
      object armor=GetItemPossessedBy(OBJECT_SELF,res);
      ClearAllActions(); ActionEquipItem(armor,INVENTORY_SLOT_CHEST);
      WriteTimestampedLogEntry("PHENOTYPE_EQUIPMENT_RETRY "+GetName(OBJECT_SELF)+" valid="+IntToString(GetIsObjectValid(armor)));
      return;
    }
    if(!GetLocalInt(OBJECT_SELF,"EQUIPMENT_VERIFIED")) {
      WriteTimestampedLogEntry("PHENOTYPE_EQUIPMENT_WORN "+GetName(OBJECT_SELF)+" item="+GetResRef(worn));
      SetLocalInt(OBJECT_SELF,"EQUIPMENT_VERIFIED",1);
    }
  }
  int pose=GetLocalInt(GetModule(),"FORCED_POSE");
  if(pose) {
    if(n%8==1) { ClearAllActions(); ActionPlayAnimation(pose-1,1.0,60.0);
      WriteTimestampedLogEntry("PHENOTYPE_HELD_POSE "+GetName(OBJECT_SELF)+" animation="+IntToString(pose-1)); }
    return;
  }
  if(n>=5)
    WriteTimestampedLogEntry("PHENOTYPE_MOTION "+GetName(OBJECT_SELF)+" step="+IntToString(n)+" enabled="+IntToString(GetLocalInt(GetModule(),"RUN_MOTION_TESTS")));
  if(!GetLocalInt(GetModule(),"RUN_MOTION_TESTS")) return;
  if(n<5) return;
  if(n==5) { ClearAllActions(); ActionPlayAnimation(ANIMATION_LOOPING_PAUSE2,1.0,6.0); }
  if(n==6) { ClearAllActions(); ActionPlayAnimation(ANIMATION_LOOPING_TALK_NORMAL,1.0,6.0); }
  if(n==7) { ClearAllActions(); ActionPlayAnimation(ANIMATION_FIREFORGET_BOW); }
  if(n==8) { ClearAllActions(); ActionPlayAnimation(ANIMATION_LOOPING_SIT_CHAIR,1.0,6.0); }
  if(n==9) { ClearAllActions(); location h=GetLocalLocation(OBJECT_SELF,"HOME");
    vector v=GetPositionFromLocation(h); v.y+=4.0;
    ActionMoveToLocation(Location(GetArea(OBJECT_SELF),v,90.0),FALSE);
    ActionMoveToLocation(h,TRUE); }
  if(n==12) { ClearAllActions(); ActionPlayAnimation(ANIMATION_LOOPING_WORSHIP,1.0,6.0); }
  if(n==13) { ClearAllActions(); ActionPlayAnimation(ANIMATION_LOOPING_GET_LOW,1.0,6.0); }
  if(n==14) { ClearAllActions(); ActionPlayAnimation(ANIMATION_LOOPING_CONJURE1,1.0,6.0); }
  if(n==15) { ClearAllActions(); ActionPlayAnimation(ANIMATION_LOOPING_CONJURE2,1.0,6.0); }
  if(n==16) { ClearAllActions(); ActionPlayAnimation(ANIMATION_FIREFORGET_DODGE_SIDE); }
  if(n==17) { ClearAllActions(); ActionPlayAnimation(ANIMATION_FIREFORGET_DODGE_DUCK); }
  if(n==18) { ClearAllActions(); ActionPlayAnimation(ANIMATION_FIREFORGET_SPASM); }
  if(n==19) { ClearAllActions(); ActionPlayAnimation(ANIMATION_LOOPING_DEAD_FRONT,1.0,6.0); }
  if(n==20) { ClearAllActions(); ActionPlayAnimation(ANIMATION_LOOPING_DEAD_BACK,1.0,6.0); }
  if(n==21) { ClearAllActions(); SetFacing(270.0); SetLocalInt(OBJECT_SELF,"STEP",0); }
} """,
        "sr_pt_enter": """void main() {
  object p=GetEnteringObject(); if(!GetIsPC(p)) return;
    SendMessageToPC(p,"SRN phenotype fixture: candidates remain under validation.");
  WriteTimestampedLogEntry("PHENOTYPE_CLIENT_ENTER "+GetName(p));
} """}
    if args.locomotion:
        scripts['sr_pt_loco'] = locomotion_script(args.locomotion)
        scripts['sr_pt_enter'] = scripts['sr_pt_enter'].replace('object p=GetEnteringObject();',
            'SetLocalInt(GetModule(),"LOCOMOTION_ENABLED",1); object p=GetEnteringObject();',1)
        scripts['sr_pt_hb'] = scripts['sr_pt_hb'].replace('  int n=GetLocalInt(OBJECT_SELF,"STEP");',
            '  if(GetLocalInt(GetModule(),"LOCOMOTION_ENABLED")) {\n'
            '    if(GetStringLeft(GetTag(OBJECT_SELF),3)=="pt_" && GetStringLeft(GetTag(OBJECT_SELF),8)!="pt_full_" && GetStringLeft(GetTag(OBJECT_SELF),5)!="pt_a2" && !GetLocalInt(OBJECT_SELF,"LOCO_STARTED")) {\n'
            '      SetLocalInt(OBJECT_SELF,"LOCO_STARTED",1); ClearAllActions(TRUE); ExecuteScript("sr_pt_loco",OBJECT_SELF); }\n'
            '    return; }\n  int n=GetLocalInt(OBJECT_SELF,"STEP");',1)
    for item_name, slot in hand_items:
        scripts["sr_pt_spawn"]=scripts["sr_pt_spawn"].replace('  SetLocalLocation(OBJECT_SELF,"HOME",',
            '  object '+item_name+'=CreateItemOnObject("'+item_name+'",OBJECT_SELF); ActionEquipItem('+item_name+','+str(slot)+');\n  SetLocalLocation(OBJECT_SELF,"HOME",')
        scripts["sr_pt_hb"]=scripts["sr_pt_hb"].replace('  int n=GetLocalInt(OBJECT_SELF,"STEP");',
            '  object '+item_name+'=GetItemInSlot('+str(slot)+');\n'
            '  if(GetResRef('+item_name+')!="'+item_name+'") { object item=GetItemPossessedBy(OBJECT_SELF,"'+item_name+'");\n'
            '    if(!GetIsObjectValid(item)) item=CreateItemOnObject("'+item_name+'",OBJECT_SELF);\n'
            '    ClearAllActions(); ActionEquipItem(item,'+str(slot)+');\n'
            '    WriteTimestampedLogEntry("PHENOTYPE_HAND_RETRY actor="+GetName(OBJECT_SELF)+" slot='+str(slot)+' size="+IntToString(GetCreatureSize(OBJECT_SELF))+" right="+GetResRef(GetItemInSlot(4))+" left="+GetResRef(GetItemInSlot(5))); return; }\n'
            '  if(!GetLocalInt(OBJECT_SELF,"'+item_name+'_verified")) {\n'
            '    WriteTimestampedLogEntry("PHENOTYPE_HAND_WORN actor="+GetName(OBJECT_SELF)+" slot='+str(slot)+' item="+GetResRef('+item_name+'));\n'
            '    SetLocalInt(OBJECT_SELF,"'+item_name+'_verified",1); }\n'
            '  int n=GetLocalInt(OBJECT_SELF,"STEP");')
    if args.gameplay_tests:
        scripts.update({
            "sr_pt_tspawn":'''void main() {
  int i=0; for(i=0;i<18;i++) SetCreatureBodyPart(i,1);
  SetCreatureBodyPart(CREATURE_PART_BELT,0);
  SetCreatureBodyPart(CREATURE_PART_RIGHT_SHOULDER,0);
  SetCreatureBodyPart(CREATURE_PART_LEFT_SHOULDER,0);
  SetCreatureBodyPart(CREATURE_PART_HEAD,1);
  SetColor(OBJECT_SELF,COLOR_CHANNEL_SKIN,3); SetColor(OBJECT_SELF,COLOR_CHANNEL_HAIR,5);
  SetImmortal(OBJECT_SELF,TRUE); SetIsDestroyable(FALSE,FALSE,TRUE);
  ClearAllActions(TRUE); SetCommandable(FALSE);
  WriteTimestampedLogEntry("PHENOTYPE_GAMEPLAY_TARGET appearance="+IntToString(GetAppearanceType(OBJECT_SELF))+" hp="+IntToString(GetCurrentHitPoints(OBJECT_SELF)));
}''',
            "sr_pt_hit":'''void main() {
  WriteTimestampedLogEntry("PHENOTYPE_GAMEPLAY_HIT actor="+GetName(GetLastDamager())+" damage="+IntToString(GetTotalDamageDealt())+" targetHP="+IntToString(GetCurrentHitPoints(OBJECT_SELF)));
}''',
            "sr_pt_spell":'''void main() {
  WriteTimestampedLogEntry("PHENOTYPE_GAMEPLAY_SPELL actor="+GetName(GetLastSpellCaster())+" spell="+IntToString(GetLastSpell()));
}''',
            "sr_pt_damage":'''void main() {
  WriteTimestampedLogEntry("PHENOTYPE_GAMEPLAY_DAMAGE actor="+GetName(OBJECT_SELF)+" damage="+IntToString(GetTotalDamageDealt())+" hp="+IntToString(GetCurrentHitPoints(OBJECT_SELF)));
}''',
            "sr_pt_death":'''void main() {
  WriteTimestampedLogEntry("PHENOTYPE_GAMEPLAY_DEATH actor="+GetName(OBJECT_SELF));
}'''})
        scripts["sr_pt_enter"]=scripts["sr_pt_enter"].replace("object p=GetEnteringObject();",'SetLocalInt(GetModule(),"RUN_GAMEPLAY_TESTS",1); object p=GetEnteringObject();')
        if args.gameplay_only:
            scripts["sr_pt_enter"]=scripts["sr_pt_enter"].replace("object p=GetEnteringObject();",'SetLocalInt(GetModule(),"GAMEPLAY_ONLY",1); object p=GetEnteringObject();')
        if args.gameplay_repeat:
            scripts["sr_pt_raise"]='''void main() {
  ApplyEffectToObject(DURATION_TYPE_INSTANT,EffectResurrection(),OBJECT_SELF);
  ApplyEffectToObject(DURATION_TYPE_INSTANT,EffectHeal(1000),OBJECT_SELF);
  ClearAllActions(TRUE); JumpToLocation(GetLocalLocation(OBJECT_SELF,"HOME"));
  SetLocalInt(OBJECT_SELF,"STEP",22);
  WriteTimestampedLogEntry("PHENOTYPE_GAMEPLAY_RESTART actor="+GetName(OBJECT_SELF)+" dead="+IntToString(GetIsDead(OBJECT_SELF)));
}'''
            scripts["sr_pt_death"]=scripts["sr_pt_death"].replace('void main() {', 'void main() { object corpse=OBJECT_SELF; AssignCommand(GetModule(),DelayCommand(15.0,ExecuteScript("sr_pt_raise",corpse)));')
        scripts["sr_pt_spawn"]=scripts["sr_pt_spawn"].replace("int i=0;", "SetIsDestroyable(FALSE,TRUE,TRUE); int i=0;")
        heartbeat=scripts["sr_pt_hb"].replace('SetLocalInt(OBJECT_SELF,"STEP",0);','if(!GetLocalInt(GetModule(),"RUN_GAMEPLAY_TESTS")) SetLocalInt(OBJECT_SELF,"STEP",0);')
        scripts["sr_pt_hb"]=heartbeat.rsplit("}",1)[0]+'''
  if(!GetLocalInt(GetModule(),"RUN_GAMEPLAY_TESTS")) return;
  if(n==22) {
    ClearAllActions(); location h=GetLocalLocation(OBJECT_SELF,"HOME"); vector v=GetPositionFromLocation(h); v.y+=2.0;
    object target=GetLocalObject(OBJECT_SELF,"TARGET");
    if(!GetIsObjectValid(target)) target=CreateObject(OBJECT_TYPE_CREATURE,"sr_pt_target",Location(GetArea(OBJECT_SELF),v,270.0));
    ApplyEffectToObject(DURATION_TYPE_INSTANT,EffectHeal(1000),target);
    SetLocalObject(OBJECT_SELF,"TARGET",target); SetImmortal(target,TRUE);
    SetIsTemporaryEnemy(target,OBJECT_SELF);
    if(!GetLocalInt(OBJECT_SELF,"ATTACK_BOOST")) { ApplyEffectToObject(DURATION_TYPE_PERMANENT,EffectAttackIncrease(20),OBJECT_SELF); SetLocalInt(OBJECT_SELF,"ATTACK_BOOST",1); }
    ActionAttack(target); WriteTimestampedLogEntry("PHENOTYPE_GAMEPLAY_ATTACK "+GetName(OBJECT_SELF)+" targetValid="+IntToString(GetIsObjectValid(target))+" enemy="+IntToString(GetIsEnemy(target))+" distance="+FloatToString(GetDistanceBetween(OBJECT_SELF,target)));
  }
  if(n==23 || n==25) {
    object target=GetLocalObject(OBJECT_SELF,"TARGET");
    WriteTimestampedLogEntry("PHENOTYPE_GAMEPLAY_STATE actor="+GetName(OBJECT_SELF)+" step="+IntToString(n)+" action="+IntToString(GetCurrentAction())+" targetValid="+IntToString(GetIsObjectValid(target))+" targetHP="+IntToString(GetCurrentHitPoints(target))+" distance="+FloatToString(GetDistanceBetween(OBJECT_SELF,target)));
  }
  if(n==24) { ClearAllActions(TRUE);
    WriteTimestampedLogEntry("PHENOTYPE_GAMEPLAY_CAST_REQUEST actor="+GetName(OBJECT_SELF)+" wizardLevel="+IntToString(GetLevelByClass(CLASS_TYPE_WIZARD))+" armorFailure="+IntToString(GetArcaneSpellFailure(OBJECT_SELF)));
    int cast=0; for(cast=0;cast<3;cast++) { ActionCastSpellAtObject(SPELL_MAGIC_MISSILE,GetLocalObject(OBJECT_SELF,"TARGET"),METAMAGIC_NONE,TRUE); ActionWait(0.5); }
  }
  if(n==26) { ClearAllActions(TRUE); ApplyEffectToObject(DURATION_TYPE_INSTANT,EffectDamage(3,DAMAGE_TYPE_MAGICAL),OBJECT_SELF); }
  if(n==28) { ClearAllActions(TRUE); SetIsDestroyable(FALSE,TRUE,TRUE); SetImmortal(OBJECT_SELF,FALSE); SetPlotFlag(OBJECT_SELF,FALSE);
    ApplyEffectToObject(DURATION_TYPE_INSTANT,EffectDeath(FALSE,FALSE),OBJECT_SELF); }
}'''
    for name, text in scripts.items():
        if name == "sr_pt_hb" and args.motion_route_distance != 4.0:
            route_token = "v.y+=4.0;"
            if text.count(route_token) != 1:
                raise RuntimeError("Expected one generic motion route distance")
            text = text.replace(route_token, "v.y+=" + str(args.motion_route_distance) + ";", 1)
        if name == "sr_pt_enter" and args.torso_inspection_sequence:
            text = text.replace('    SendMessageToPC(p,',
                                '  StartTorsoInspection(p);\n    SendMessageToPC(p,', 1)
            text = torso_inspection_script(slugs,args.camera_target,args.camera_pitch,
                                           args.camera_distance,args.camera_height) + text
        if name == "sr_pt_enter" and args.camera_pitch is not None and not args.torso_inspection_sequence:
            camera_setup='object p=OBJECT_SELF; LockCameraPitch(p,FALSE); LockCameraDistance(p,FALSE); SetCameraLimits(p); AttachCamera(p,p,FALSE); SetCameraMode(p,CAMERA_MODE_TOP_DOWN); '
            camera_setup+='SetCameraHeight(p,'+str(args.camera_height)+'); '
            if args.camera_target:
                camera_tag = equipment_camera_tag if args.camera_equipment_target else 'pt_' + str(slugs.index(args.camera_target))
                camera_setup+='AttachCamera(p,GetObjectByTag("'+camera_tag+'"),FALSE); '
            if args.camera_lock:
                camera_setup+='SetCameraLimits(p,'+str(args.camera_pitch)+','+str(args.camera_pitch)+','+str(args.camera_distance)+','+str(args.camera_distance)+'); '
            text = ('void SetFixtureCamera() { '+camera_setup+'SetCameraFacing('+str(args.camera_facing)+','+
                str(args.camera_distance)+','+str(args.camera_pitch)+'); '+
                ('DelayCommand(1.0,LockCameraPitch(p,TRUE)); DelayCommand(1.0,LockCameraDistance(p,TRUE)); ' if args.camera_lock else '')+
                'WriteTimestampedLogEntry("PHENOTYPE_CAMERA_SET"); }\n'+text)
            text = text.replace('SendMessageToPC(p,',
                'AssignCommand(p,DelayCommand(10.0,SetFixtureCamera()));\n  SendMessageToPC(p,')
        if name == "sr_pt_enter" and args.motion_tests:
            text = text.replace("object p=GetEnteringObject();", 'SetLocalInt(GetModule(),"RUN_MOTION_TESTS",1); object p=GetEnteringObject();')
        if name == "sr_pt_enter" and args.pose:
            animation = {"sit":"ANIMATION_LOOPING_SIT_CHAIR", "kneel":"ANIMATION_LOOPING_WORSHIP",
                         "crouch":"ANIMATION_LOOPING_GET_LOW",
                         "dead-front":"ANIMATION_LOOPING_DEAD_FRONT", "dead-back":"ANIMATION_LOOPING_DEAD_BACK",
                         "conjure1":"ANIMATION_LOOPING_CONJURE1", "conjure2":"ANIMATION_LOOPING_CONJURE2",
                         "pause":"ANIMATION_LOOPING_PAUSE2", "talk":"ANIMATION_LOOPING_TALK_NORMAL"}[args.pose]
            text = text.replace("object p=GetEnteringObject();", 'SetLocalInt(GetModule(),"FORCED_POSE",'+animation+'+1); object p=GetEnteringObject();')
        text=text.replace('SetColor(OBJECT_SELF,COLOR_CHANNEL_SKIN,3);',
                          'SetColor(OBJECT_SELF,COLOR_CHANNEL_SKIN,'+str(args.skin_color)+');')
        if name in ('sr_pt_spawn','sr_pt_tspawn'):
            text=text.replace('void main() {','void main() {\n  WriteTimestampedLogEntry("PHENOTYPE_SKIN_PALETTE actor="+GetName(OBJECT_SELF)+" index='+str(args.skin_color)+'");',1)
        path = binary / (name + ".nss")
        path.write_text(text, encoding="ascii")
        run("nwn_script_comp", ["--root", args.game_root, "--userdirectory", userdir, "--no-ovr", path])
        if not path.with_suffix(".ncs").exists():
            raise RuntimeError("Script compiler produced no output: " + name)
    module = userdir / "modules/srn_pheno_test.mod"
    if module.exists():
        module.unlink()
    run("nwn_erf", ["-c", "-f", module, "-e", "MOD", binary])
    receipt = {"module": str(module), "moduleSha256": digest(module), "hak": str(hak),
               "hakSha256": digest(hak), "resources": len(expected), "specimens": slugs,
               "userDirectory": str(userdir), "textureMode": args.texture_mode,
               "modelMode":"ascii" if args.ascii_models or args.texture_mode=="rgb" else "native-binary",
               "motionTests":args.motion_tests, "heldPose":args.pose,
               "equipmentChestProof":bool(args.equipment_template),"specimenCount":len(creatures),"engineObserved": False}
    receipt["fullEquipmentProof"]=bool(args.full_equipment_template)
    receipt['stockEquipmentProof']=stock_armor_proof if args.full_equipment_template else None
    receipt["actorNames"]=[c["FirstName"]["value"]["0"] for c in creatures]
    receipt["armorEquipment"]=[{"actor":c["FirstName"]["value"]["0"],
        "resref":"sr_pt_full" if c["Tag"]["value"].startswith("pt_full_") else
                 "sr_pt_a20" if c["Tag"]["value"].startswith("pt_a20_") else "sr_pt_a21"}
        for c in creatures if c["Tag"]["value"].startswith(("pt_full_","pt_a20_","pt_a21_"))]
    receipt["handEquipment"]=[{"resref":name,"slot":slot} for name,slot in hand_items]
    receipt["configuration"] = configuration
    if material_patches:
        receipt['runtimeMaterialPatches']=material_patches
    if effective_bodies:
        receipt['effectiveNativeBodies']={slug:{
            'inventorySha256':digest(root/slug/'converted/effective-material-inventory.json'),
            'completeBodySelected':data['completeBodySelected'],
            'acceptedSixBytesExact':data['acceptedSixBytesExact'],
            'resourceHashes':data['resourceHashes']} for slug,data in effective_bodies.items()}
    if args.locomotion:
        receipt['locomotion'] = copy.deepcopy(configuration['locomotion'])
        receipt['locomotion']['limitation'] = ('Movement commands and sampled action/position logs do not prove visual animation acceptance. '
            'Routes repeat until module unload; pathfinding, collision and turning can affect observed speed. Camera follows its selected actor unlocked.')
    if args.camera_equipment_target:
        receipt['cameraEquipmentTarget'] = {'slug':args.camera_target,'actorTag':equipment_camera_tag}
    if args.torso_inspection_sequence:
        receipt["torsoInspectionSequence"] = copy.deepcopy(configuration["torsoInspectionSequence"])
        receipt["torsoInspectionSequence"]["limitation"] = (
            "Scheduled camera/animation commands and delayed action-state logs are not visual acceptance. "
            "Inspect screenshots at least three seconds after each phase; no commands repeat after 135 seconds.")
    receipt["gameplayTests"]=args.gameplay_tests
    if args.gameplay_tests:
        receipt["gameplayPhases"]={22:"actual-attack",24:"actual-magic-missile",26:"actual-damage",28:"actual-death"}
        receipt["gameplayLimitation"]=("Equipped melee" if args.weapon_template else "Unarmed melee")+" and cheat-cast magic missile against stationary fixture targets; remaining weapon, robe and stance variants require separate checks. " + ("Actors resurrect after 15 seconds for repeated observation." if args.gameplay_repeat else "Reload after terminal death phase.")
    if args.motion_tests:
        receipt["motionPhases"]={} if args.gameplay_only else {5:"idle",6:"talk",7:"bow",8:"chair",9:"walk-and-run",
            12:"worship",13:"crouch",14:"conjure1",15:"conjure2",16:"dodge-side",17:"dodge-duck",
            18:"spasm",19:"dead-front-pose",20:"dead-back-pose",21:"turn-and-repeat"}
        receipt["motionLimitation"]="Pose sequence skipped for gameplay debugging." if args.gameplay_only else "Pose smoke test; actual attacks, spells, damage, death and equipped stances require gameplay checks."
    save_json(staging / "receipt.json", receipt)
    # Preserve actual packed builds, not only their hashes. Evidence must
    # remain reproducible after later fixture or geometry revisions.
    archive = root / "build-archive"
    for artifact, checksum in ((hak,receipt["hakSha256"]),(module,receipt["moduleSha256"])):
        destination = archive / checksum / artifact.name
        destination.parent.mkdir(parents=True,exist_ok=True)
        if destination.exists():
            if digest(destination) != checksum:
                raise RuntimeError("Archived artifact changed: " + str(destination))
        else:
            shutil.copyfile(artifact,destination)
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
