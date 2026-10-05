"""Blender: compare rigid parts using the archived NWN animation controllers.

This is an offline joint inspection, not proof of engine animation playback.
ASCII orientation keys are axis-angle; interpolate converted quaternions.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import sys

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_geometry import arrays
from pose_preview_bridge import pose
from run_preparation import PreparationContext
from pose_preview_render_settings import apply_render_settings
from retarget import NODE, nodes, transforms, rotations

JOINTS = dict(head="head_g", neck="neck_g", chest="torso_g", pelvis="pelvis_g",
              bicepl="lbicep_g", bicepr="rbicep_g", forel="lforearm_g", forer="rforearm_g",
              handl="lhand_g", handr="rhand_g", legl="lthigh_g", legr="rthigh_g",
              shinl="lshin_g", shinr="rshin_g", footl="lfoot_g", footr="rfoot_g")
OPTIONAL_JOINTS = dict(shol="lshoulder_g", shor="rshoulder_g")


def controller(rows, time, rotation=False):
    rows = np.array(rows)
    left = max(0, int(np.searchsorted(rows[:, 0], time, side="right")) - 1)
    right = min(left + 1, len(rows) - 1)
    t0, t1 = rows[left, 0], rows[right, 0]
    mix = min(1., max(0., (time-t0)/(t1-t0))) if t1 > t0 else 0.
    if rotation:
        def quat(values):
            axis = Vector(values[:3])
            return Quaternion(axis.normalized(), float(values[3])) if axis.length > 1e-9 else Quaternion()
        q = quat(rows[left, 1:]).slerp(quat(rows[right, 1:]), mix)
        axis, angle = q.to_axis_angle()
        return [*axis, angle]
    return rows[left, 1:4]*(1-mix) + rows[right, 1:4]*mix


def stock_part(path, name):
    result = []
    text = path.read_text(encoding="cp1252")
    for match in NODE.finditer(text.split("endmodelgeom")[0]):
        coords, faces = arrays(match[3], "verts"), arrays(match[3], "faces")
        if not coords or not faces:
            continue
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(coords, [], [[int(i) for i in face[:3]] for face in faces])
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.collection.objects.link(obj)
        # Preserve local mesh transforms in the stock part file.
        local = nodes("node "+match[1]+" "+match[2]+"\n"+match[3]+"endnode")[match[2].lower()]
        matrix = np.eye(4)
        matrix[:3,:3] = rotations(local["orientation"])
        matrix[:3,3] = local["position"]
        mesh.transform(Matrix(matrix))
        for polygon in mesh.polygons:
            polygon.use_smooth = True
        result.append(obj)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--converted", type=Path, action="append", default=[])
    parser.add_argument("--baseline", type=Path, default=Path("output/phenotypes/baseline"))
    parser.add_argument("--stock-prefix",default="pmh0",help="Actual stock comparator rig/model prefix")
    parser.add_argument("--stock-height",type=float,help="Measured target stock bind height; display reference only")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--clip", default="getlowlp")
    parser.add_argument("--time", type=float, default=0)
    parser.add_argument("--material-mode", choices=("clay", "color", "ownership", "attachments"), default="clay",
                        help="attachments highlights replacement ends separately from retained donor surfaces")
    parser.add_argument("--include-heads", action="store_true")
    parser.add_argument("--shoulder-style",type=int,choices=(0,1),default=0,
                        help="Actual bare fixture defaults0: no separate shoulder meshes.1 renders the measured optional stock shoulder001 diagnostic.")
    parser.add_argument("--focus",choices=("full-body","upper-body","pelvis"),default="full-body")
    parser.add_argument("--view",action="append",choices=("front","rear","oblique","left","right","top","bottom","rear-top"),
                        help="Explicit camera views; defaults to front/rear/oblique")
    parser.add_argument("--no-stock",action="store_true",help="Compare only the supplied custom candidates")
    parser.add_argument('--camera-scale',type=float,
                        help='Explicit positive orthographic scale for comparable full-body sheets; default fits each pose')
    parser.add_argument("--label",action="append",default=[],help="Display label for each supplied converted candidate")
    parser.add_argument("--stock-replacement",type=Path,action="append",default=[],
                        help="JSON candidate: label, modelPrefix, height, parts mapping; undeclared parts are actual stock ASCII")
    args = parser.parse_args(sys.argv[sys.argv.index("--")+1:])
    preparation=PreparationContext(target_revision='explicit-preview-inputs',rig_revision='content-bound-root',
        animation_revision='content-bound-chain',settings={'clip':args.clip,'time':args.time},
        dependencies=[Path(__file__).resolve()])
    if args.camera_scale is not None and args.camera_scale<=0:
        raise RuntimeError('Camera scale must be positive')
    args.output.mkdir(parents=True, exist_ok=False)
    code=Path(__file__).read_bytes();code_hash=hashlib.sha256(code).hexdigest()
    (args.output/"executed-pose-preview.py").write_bytes(code)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    stock_height=args.stock_height if args.stock_height is not None else 2.
    if args.converted:
        first=json.loads((args.converted[0]/"conversion.json").read_text())
        if args.stock_height is None:stock_height=first.get("stockReferenceHeight",stock_height)
    elif args.stock_replacement and args.stock_height is None:
        stock_height=json.loads(args.stock_replacement[0].read_text()).get("height",stock_height)
    if stock_height<=0:raise RuntimeError("Stock height must be positive")
    if args.label and len(args.label)!=len(args.converted):
        raise RuntimeError("Provide one label per converted candidate")
    stock_label="Stock Human" if args.stock_prefix=="pmh0" else "Stock "+args.stock_prefix
    specimens = [] if args.no_stock else [(stock_label, None, stock_height, args.stock_prefix, args.baseline/"ascii")]
    stock_replacements={}
    for i,directory in enumerate(args.converted):
        report = json.loads((directory/"conversion.json").read_text())
        label=args.label[i] if args.label else directory.parent.parent.name
        specimens.append((label, directory, report["height"], report["modelPrefix"], directory/"ascii"))
    for config_path in args.stock_replacement:
        config_path=config_path.resolve()
        candidate=json.loads(config_path.read_text())
        replacements={}
        for part,path in candidate["parts"].items():
            if part not in JOINTS and part not in OPTIONAL_JOINTS:raise RuntimeError("Unknown stock replacement part: "+part)
            source=Path(path)
            replacements[part]=(source if source.is_absolute() else config_path.parent/source).resolve()
            if not replacements[part].is_file():raise RuntimeError("Missing replacement: "+str(source))
        if not replacements:raise RuntimeError("Stock replacement requires at least one explicit part")
        shoulder_style=candidate.get('shoulderStyle',args.shoulder_style)
        if shoulder_style not in (0,1):raise RuntimeError('Shoulder style must be measured stock0/1')
        if set(replacements)&set(OPTIONAL_JOINTS) and shoulder_style!=1:
            raise RuntimeError('Declared shoulder replacement requires shoulderStyle1')
        stock_replacements[len(specimens)]={"parts":replacements,"config":config_path,"shoulderStyle":shoulder_style}
        specimens.append((candidate["label"],None,candidate.get("height",stock_height),
                          candidate.get("modelPrefix","pmh0"),args.baseline/"ascii"))
    receipts = [];specimen_objects=[]
    hues = [(0.20,0.43,0.75,1),(.76,.32,.14,1),(.22,.58,.31,1),(.65,.38,.66,1)]
    for index, (label, directory, height, prefix, ascii_dir) in enumerate(specimens):
        display_objects=[]
        matrices, receipt = pose(ascii_dir, prefix, args.clip, args.time, args.baseline/"ascii", context=preparation)
        root_path=(ascii_dir/(prefix+".mdl")).resolve()
        input_hashes = {str(root_path):hashlib.sha256(root_path.read_bytes()).hexdigest()}
        receipt["attachmentMaterialFaces"]={}
        receipt["attachmentHighlightColors"]={}
        replacement_spec=stock_replacements.get(index,{"parts":{}})
        shoulder_style=replacement_spec.get('shoulderStyle',args.shoulder_style)
        active_joints=dict(JOINTS)
        if shoulder_style:active_joints.update(OPTIONAL_JOINTS)
        receipt['bareAccessoryPolicy']={'shoulders':shoulder_style,'belt':0}
        receipt["jointWorldMatrices"]={joint:matrices[joint].tolist() for joint in active_joints.values()}
        if replacement_spec["parts"]:
            config_path=replacement_spec["config"]
            input_hashes[str(config_path)]=hashlib.sha256(config_path.read_bytes()).hexdigest()
            receipt["assemblyMode"]="actual-stock-parts-with-explicit-replacements"
            receipt["replacedParts"]=list(replacement_spec["parts"])
            receipt["allOtherPartsFromStockAscii"]=True
        if directory:
            input_hashes[str((directory/'conversion.json').resolve())] = hashlib.sha256((directory/'conversion.json').read_bytes()).hexdigest()
            if json.loads((directory/'conversion.json').read_text()).get("rigMode")=="stock-exact":
                stock_root=(args.baseline/'ascii'/(args.stock_prefix+'.mdl')).resolve()
                if root_path.read_bytes()!=stock_root.read_bytes():
                    raise RuntimeError("Exact stock candidate has a changed root")
                stock_matrices,_=pose(args.baseline/'ascii',args.stock_prefix,args.clip,args.time,context=preparation)
                discrepancy=max(float(np.max(abs(matrices[j]-stock_matrices[j]))) for j in active_joints.values())
                if discrepancy>1e-10:
                    raise RuntimeError("Candidate preview joint transforms differ from stock")
                receipt["maximumStockJointMatrixDifference"]=discrepancy
        # Explicit stock-part replacements already use the stock rig's native
        # coordinates. Height metadata must not rescale its head, limbs or rig.
        # Keep legacy converted-specimen display normalization separate.
        scale = stock_height/height if directory else 1.
        shift = (index-(len(specimens)-1)/2)*1.65
        for p, joint in active_joints.items():
            if p == "head" and not args.include_heads:
                continue
            if p in replacement_spec["parts"]:
                part_path=replacement_spec["parts"][p]
                input_hashes[str(part_path)]=hashlib.sha256(part_path.read_bytes()).hexdigest()
                before=set(bpy.context.scene.objects)
                bpy.ops.import_scene.gltf(filepath=str(part_path))
                objects=[o for o in bpy.context.scene.objects if o not in before and o.type=="MESH"]
                if not objects:raise RuntimeError("Replacement contains no mesh: "+str(part_path))
                for obj in objects:
                    # A lossless fitted part can carry its declared similarity
                    # on a parent node. Bake that effective world transform in
                    # this disposable preview before assigning the stock joint.
                    # Applying child-local transforms alone loses the fit.
                    fitted_world = obj.matrix_world.copy()
                    obj.parent = None
                    obj.matrix_world = fitted_world
                    bpy.ops.object.select_all(action="DESELECT")
                    obj.select_set(True);bpy.context.view_layer.objects.active=obj
                    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
                receipt.setdefault("replacementInputNodeTransformsBaked", []).append(p)
            elif directory:
                conversion = json.loads((directory/"conversion.json").read_text())
                entry = next(e for e in conversion["parts"] if e["part"]==p)
                kit_part = entry["kitReport"]["part"]
                part_path = directory/'parts'/(kit_part+'.glb')
                input_hashes[str(part_path.resolve())] = hashlib.sha256(part_path.read_bytes()).hexdigest()
                before = set(bpy.context.scene.objects)
                bpy.ops.import_scene.gltf(filepath=str((directory/"parts"/(kit_part+".glb")).resolve()))
                objects = [o for o in bpy.context.scene.objects if o not in before and o.type=="MESH"]
                for obj in objects:
                    bpy.ops.object.select_all(action="DESELECT")
                    obj.select_set(True)
                    bpy.context.view_layer.objects.active=obj
                    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
            else:
                stock_path=(ascii_dir/(prefix+"_"+p+"001.mdl")).resolve()
                input_hashes[str(stock_path)]=hashlib.sha256(stock_path.read_bytes()).hexdigest()
                objects = stock_part(stock_path, p)
            for obj in objects:
                obj.matrix_world = Matrix(matrices[joint])
                obj.location *= scale
                obj.location.x += shift
                obj.scale *= scale
                obj.name = label+":"+p
                display_objects.append((obj,obj.location.copy()))
                if args.material_mode != "color" or (not directory and p not in replacement_spec["parts"]):
                    replacements = [bool(m and m.get("attachmentSampledSkin")) for m in obj.data.materials]
                    if args.material_mode!="attachments":replacements=[False]
                    indices=[polygon.material_index for polygon in obj.data.polygons]
                    if args.material_mode=="attachments":
                        receipt["attachmentMaterialFaces"][p]=sum(replacements[i] for i in indices) if replacements else 0
                        receipt["attachmentHighlightColors"][p]=[.08,.4,1.,1.] if p.startswith("bicep") else [1.,.27,.035,1.]
                    obj.data.materials.clear()
                    for replacement in replacements or [False]:
                        material = bpy.data.materials.new(obj.name+(":graft" if replacement else ":donor"))
                        material.use_nodes = True
                        shader = material.node_tree.nodes.get("Principled BSDF")
                        shader.inputs["Base Color"].default_value = receipt["attachmentHighlightColors"][p] if replacement else (
                            hues[list(active_joints).index(p)%len(hues)] if args.material_mode=="ownership" else (.5,.5,.5,1))
                        shader.inputs["Roughness"].default_value=1
                        obj.data.materials.append(material)
                    if args.material_mode=="attachments":
                        for polygon,index in zip(obj.data.polygons,indices):polygon.material_index=index
        receipt.update(label=label, height=height, displayScale=scale,
                       displayScalePolicy="legacy-converted-height-normalization" if directory else "native-stock-coordinates",
                       partInputs=input_hashes)
        receipts.append(receipt)
        specimen_objects.append(display_objects)
    scene=bpy.context.scene
    render_settings=apply_render_settings(scene,'eevee')
    scene.eevee.use_gtao=True
    scene.eevee.gtao_distance=.08
    scene.world.color=(.15,.15,.15)
    scene.view_settings.view_transform="Standard"
    scene.view_settings.look="Medium High Contrast"
    scene.view_settings.exposure=-.8
    scene.render.resolution_x=(1280 if args.focus in ("upper-body","pelvis") else 640)*len(specimens)
    scene.render.resolution_y=800 if args.focus in ("upper-body","pelvis") else 960
    scene.render.resolution_percentage=100
    meshes=[o for o in scene.objects if o.type=="MESH"]
    bpy.context.view_layer.update()
    points=[o.matrix_world@v.co for o in meshes for v in o.data.vertices]
    zmin=min(p.z for p in points); zmax=max(p.z for p in points)
    label_z=zmax+.055
    if args.focus=="upper-body":
        zmin+=(zmax-zmin)*.58
        zmax+=.12
    elif args.focus=="pelvis":
        pelvis_points=[o.matrix_world@v.co for o in meshes if o.name.endswith(":pelvis") for v in o.data.vertices]
        if not pelvis_points:raise RuntimeError("Pelvis focus has no actual pelvis geometry")
        zmin=min(p.z for p in pelvis_points)-.08
        zmax=max(p.z for p in pelvis_points)+.18
        label_z=zmax+.035
        points=[p for p in points if zmin<=p.z<=zmax]
    target=Vector((0,0,(zmin+zmax)/2))
    bpy.ops.object.camera_add()
    camera=bpy.context.object;scene.camera=camera
    camera.data.type="ORTHO"
    # Blender's ortho scale uses the wider image dimension.
    camera.data.ortho_scale=max((zmax-zmin)*1.12*scene.render.resolution_x/scene.render.resolution_y,
                               (max(p.x for p in points)-min(p.x for p in points))*1.08)
    labels=[]
    for index,(label,*_) in enumerate(specimens):
        text=bpy.data.curves.new(label,"FONT");text.body=label;text.align_x="CENTER";text.size=.052
        obj=bpy.data.objects.new(label+" label",text);bpy.context.collection.objects.link(obj)
        obj.location=((index-(len(specimens)-1)/2)*1.65,0,label_z)
        material=bpy.data.materials.new(label+" label material");material.use_nodes=True
        material.node_tree.nodes.clear()
        emission=material.node_tree.nodes.new("ShaderNodeEmission")
        emission.inputs[0].default_value=(.9,.9,.9,1)
        out=material.node_tree.nodes.new("ShaderNodeOutputMaterial")
        material.node_tree.links.new(emission.outputs[0],out.inputs["Surface"])
        text.materials.append(material);labels.append(obj)
    bpy.context.view_layer.update()
    for obj in labels:
        # Keep long provenance labels within their own specimen column.
        obj.data.size*=min(1,1.45/max(obj.dimensions.x,1e-9))
    for pos, energy in (((-3,4,5),650),((3,2,4),350),((0,-4,4),450)):
        bpy.ops.object.light_add(type="AREA",location=pos)
        light=bpy.context.object;light.data.energy=energy;light.data.size=5
        light.rotation_euler=(target-light.location).to_track_quat("-Z","Y").to_euler()
    directions={"front":(0,1,0),"rear":(0,-1,0),"oblique":(1,3,0),"left":(-1,0,0),"right":(1,0,0),"top":(0,0,1),"bottom":(0,0,-1),"rear-top":(0,-1,1.5)}
    default_scale=camera.data.ortho_scale
    camera_receipts=[]
    coordinates=np.asarray([p[:] for p in points])
    for name in args.view or ("front","rear","oblique"):
        direction=directions[name]
        side=name in ("left","right")
        for index,objects in enumerate(specimen_objects):
            shift=(index-(len(specimens)-1)/2)*1.65
            delta=Vector((-shift,shift,0)) if side else Vector((0,0,0))
            for obj,location in objects:obj.location=location+delta
        bpy.context.view_layer.update()
        camera.data.ortho_scale=default_scale
        camera.location=target+Vector(direction).normalized()*8
        camera.rotation_euler=(target-camera.location).to_track_quat("-Z","Y").to_euler()
        if name in ("top","bottom","rear-top") or side:
            # Front-view label positions project onto the neck/back from above.
            # Fit the actual projected silhouette and put labels beyond it.
            rotation=camera.rotation_euler.to_matrix()
            up=rotation@Vector((0,1,0));right=rotation@Vector((1,0,0))
            projected=coordinates if not side else np.asarray([(obj.matrix_world@v.co)[:] for obj in meshes for v in obj.data.vertices])
            if args.focus=="upper-body":projected=projected[projected[:,2]>=zmin]
            elif args.focus=="pelvis":projected=projected[(projected[:,2]>=zmin)&(projected[:,2]<=zmax)]
            vertical=projected@np.asarray(up);horizontal=projected@np.asarray(right)
            high=float(vertical.max())+.09;low=float(vertical.min())
            adjusted=target+up*((high+low)/2-target.dot(up))
            camera.location=adjusted+Vector(direction).normalized()*8
            aspect=scene.render.resolution_x/scene.render.resolution_y
            camera.data.ortho_scale=max(float(np.ptp(horizontal))*1.1,(high-low+.09)*aspect*1.08)
            for index,obj in enumerate(labels):
                shift=(index-(len(specimens)-1)/2)*1.65
                base=Vector((0,shift,0)) if side else Vector((shift,0,0))
                obj.location=base+up*(float(vertical.max())+.055-base.dot(up))
        else:
            for index,obj in enumerate(labels):
                obj.location=((index-(len(specimens)-1)/2)*1.65,0,label_z)
        for obj in labels:
            obj.rotation_euler=camera.rotation_euler
            # Orthographic translation toward the camera leaves projection
            # unchanged while preventing cropped upper-body meshes occluding text.
            obj.location+=Vector(direction).normalized()*2
        if args.camera_scale is not None:camera.data.ortho_scale=args.camera_scale
        bpy.context.view_layer.update()
        camera_receipts.append({'view':name,'projection':'orthographic',
            'orthoScale':camera.data.ortho_scale,'matrixWorld':[list(row) for row in camera.matrix_world],
            'projectionMatrix':[list(row) for row in camera.calc_matrix_camera(
                bpy.context.evaluated_depsgraph_get(),x=scene.render.resolution_x,y=scene.render.resolution_y)],
            'renderWidth':scene.render.resolution_x,'renderHeight':scene.render.resolution_y,
            'scalePolicy':'explicit-shared-scale' if args.camera_scale is not None else 'per-pose-silhouette-fit'})
        scene.render.filepath=str((args.output/(name+".png")).resolve())
        bpy.ops.render.render(write_still=True)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in meshes:obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str((args.output/"assembly.glb").resolve()),export_format="GLB",use_selection=True)
    bpy.ops.wm.save_as_mainfile(filepath=str((args.output/"comparison.blend").resolve()))
    for receipt in receipts:
        for path, expected in receipt['partInputs'].items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
                raise RuntimeError('Preview input changed during rendering: '+path)
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest()!=code_hash:raise RuntimeError("Preview code changed during rendering")
    preparation.verify()
    (args.output/"comparison.json").write_text(json.dumps({"specimens":receipts,"focus":args.focus,"preparation":preparation.receipt(),"renderSettings":render_settings,
        "cameraViews":[{"name":name,"direction":directions[name],"labelsOutsideProjectedGeometry":name in ("top","rear-top","left","right"),"specimenDisplayOffsetAxis":"Y" if name in ("left","right") else "X"} for name in args.view or ("front","rear","oblique")],
        "materialMode":args.material_mode,"codeSnapshot":"executed-pose-preview.py","codeSha256":code_hash,
        'cameras':camera_receipts,
        "note":"Offline stock-controller comparison. Color uses declared GLB materials; undeclared stock ASCII fallback is clay. Actual client lighting/playback remain separate evidence."},indent=2)+"\n",encoding="utf-8")
    print(json.dumps(receipts))


if __name__=="__main__":main()
