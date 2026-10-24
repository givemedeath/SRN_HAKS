"""Item fitting, atlas baking and inspection. Run in the pinned Blender 4.0 runtime."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.headkit.common import pin, require, verify, write,digest
from tools.headkit.gltf import load as load_glb
from tools.headkit.uv import raster_audit, gutter_audit
from tools.itemkit.geometry import similarity_matrix, transform, topology, protected_checks, hidden_cap_faces,loop_shadow_proxy,camera_basis,cap_fan_center
from tools.itemkit.transfer import finished_colour,validate_texture_patch
from tools.itemkit.parts import active_parts, assembly_budget, firearm_views

def arrays(obj):
    mesh = obj.data; mesh.calc_loop_triangles()
    vertices = np.array([tuple(obj.matrix_world @ v.co) for v in mesh.vertices])
    faces = np.array([tuple(t.vertices) for t in mesh.loop_triangles], dtype=np.int64)
    return vertices, faces


def corners(obj): v,f=arrays(obj);return v[f]


def combined(objects):
    points, faces, offset = [], [], 0
    for obj in objects:
        v, f = arrays(obj); points.extend(v); faces.extend(f+offset); offset += len(v)
    return np.asarray(points), np.asarray(faces, dtype=np.int64)


def world_bounds(objects):
    """Camera bounds need no triangle arrays or copies of applied mesh vertices."""
    bounds = []
    for obj in objects:
        require(len(obj.data.vertices) > 0, 'Empty inspection mesh')
        if np.array_equal(np.asarray(obj.matrix_world), np.eye(4)):
            points = np.asarray(obj.bound_box, dtype=float)
        else:
            # Keep exact world extrema for rotated/sheared objects: transformed
            # local bounding-box corners would overestimate their occupied bounds.
            points = np.asarray([tuple(obj.matrix_world @ v.co) for v in obj.data.vertices])
        bounds.extend((points.min(0), points.max(0)))
    require(bool(bounds), 'Empty inspection assembly')
    bounds = np.asarray(bounds)
    return bounds.min(0), bounds.max(0)


def set_active(objects):
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects: obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]


def reset():
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)


def duplicate(obj, name):
    result = obj.copy(); result.data = obj.data.copy(); result.name = name
    bpy.context.collection.objects.link(result)
    return result


def import_source(path, name):
    load_glb(Path(path).read_bytes())  # No silently ignored skins, instances or transforms.
    bpy.ops.import_scene.gltf(filepath=str(path))
    objects = [obj for obj in bpy.context.selected_objects if obj.type == 'MESH']
    require(len(objects) == 1, 'Exactly one static generated donor mesh required')
    obj = objects[0]; obj.name = name
    set_active([obj]); bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return obj


def apply_fit(obj, matrix, evidence=None):
    """Apply the affine map to mesh data without object-transform decomposition."""
    from tools.itemkit.grip import affine_corners
    require(np.allclose(np.asarray(obj.matrix_world), np.eye(4), atol=1e-9, rtol=0),
            'Imported fit source must have an identity object transform')
    mesh = obj.data; mesh.calc_normals_split()
    def bulk(collection, attribute, size, dtype=np.float32):
        result = np.empty(len(collection)*size, dtype)
        collection.foreach_get(attribute, result)
        return result.reshape(-1, size)
    positions = bulk(mesh.vertices, 'co', 3)
    normals = bulk(mesh.loops, 'normal', 3)
    def uv_hashes():
        return [(layer.name, hashlib.sha256(bulk(layer.data, 'uv', 2).tobytes()).hexdigest())
                for layer in mesh.uv_layers]
    uvs = uv_hashes()
    expected, authored, _ = affine_corners(positions, normals, np.empty((0, 2)), matrix)
    mesh.vertices.foreach_set('co', expected.astype(np.float32).ravel())
    mesh.update()
    for polygon in mesh.polygons: polygon.use_smooth = True
    mesh.use_auto_smooth = True
    mesh.normals_split_custom_set(authored); mesh.calc_normals_split()
    actual = bulk(mesh.vertices, 'co', 3)
    require(np.allclose(actual, expected, atol=2e-6, rtol=0), 'Affine mesh fit changed correspondence')
    require(uvs == uv_hashes(), 'Affine fit changed source UVs')
    display = bulk(mesh.loops, 'normal', 3)
    errors = np.linalg.norm(display-authored, axis=1)
    angles = np.degrees(2*np.arcsin(np.clip(errors/2, 0, 1)))
    maximum_angle = float(angles.max()); percentile_angle = float(np.quantile(angles, .99))
    result = {'maximumCoordinateError': float(np.abs(actual-expected).max()),
              'displayNormalMaximumError': float(errors.max()),
              'displayNormalMaximumDegrees': maximum_angle,
              'displayNormal99thPercentileDegrees': percentile_angle,
              'normalTransform': 'analytic inverse transpose', 'uvExact': True,
              'objectTransformDecomposed': False}
    if evidence is not None:
        # Preserve the analytic values independently of Blender's lossy encoding.
        evidence = Path(evidence)
        np.savez(evidence, sourceNormals=normals, fittedNormals=authored,
                 loopVertices=bulk(mesh.loops, 'vertex_index', 1, np.int32).ravel(), matrix=matrix)
        result['analyticNormals'] = pin(evidence)
        write(evidence.with_suffix('.json'), result, fresh=True)
    # The dense donor measured a 0.608-degree worst encoding error on 0.027%
    # of corners. Keep a bounded display gate, distinct from exact native data.
    require(maximum_angle <= 1 and percentile_angle <= .05,
            'Blender normal encoding exceeds the measured display tolerance')
    return result


def cut(obj, plane_y, keep_above):
    mesh = bmesh.new(); mesh.from_mesh(obj.data)
    # glTF splits vertices at normal/UV seams. Weld exact positions explicitly;
    # Blender's distance merge becomes unreliable at sub-nanometre thresholds.
    positions, targetmap = {}, {}
    for vertex in mesh.verts:
        key = tuple(vertex.co)
        if key in positions: targetmap[vertex] = positions[key]
        else: positions[key] = vertex
    if targetmap: bmesh.ops.weld_verts(mesh, targetmap=targetmap)
    layer = mesh.faces.layers.int.get('item_cap') or mesh.faces.layers.int.new('item_cap')
    result = bmesh.ops.bisect_plane(mesh, geom=list(mesh.verts)+list(mesh.edges)+list(mesh.faces),
        dist=1e-8, plane_co=(0, plane_y, 0), plane_no=(0, 1, 0),
        clear_inner=keep_above, clear_outer=not keep_above)
    edges = [edge for edge in result['geom_cut'] if isinstance(edge, bmesh.types.BMEdge) and edge.is_boundary]
    if edges:
        caps = bmesh.ops.holes_fill(mesh, edges=edges, sides=0)['faces']
        for face in caps:
            face[layer] = 1
            rim = list(face.verts)
            center = cap_fan_center([v.co for v in rim])
            if center is not None:
                mesh.faces.remove(face)
                middle = mesh.verts.new(center)
                for a, b in zip(rim, rim[1:]+rim[:1]):
                    mesh.faces.new((a, b, middle))[layer] = 1
    bmesh.ops.triangulate(mesh, faces=list(mesh.faces))
    bmesh.ops.recalc_face_normals(mesh, faces=list(mesh.faces))
    mesh.to_mesh(obj.data); mesh.free(); obj.data.update()


def measure(objects, config, kind='visible'):
    counts, reports = {}, {}
    require(len(objects)==len(active_parts(config['family'])), 'Visible processing part count differs')
    for part, obj in zip(active_parts(config['family']), objects):
        from tools.itemkit.preflight import geometry_report
        v, f = arrays(obj); early = geometry_report(v, f, {})
        reports[part] = early['topology']; counts[part] = len(f)
        reports[part]['totalGenus'] = early['totalGenus']
        reports[part]['shadowRecommendation'] = early['shadowRecommendation']
        require(reports[part]['closedWound'], 'Repair/classify nonclosed or inconsistently wound part: '+part+' '+json.dumps(reports[part]))
    v, f = combined(objects)
    report = protected_checks(v, f, config['processing'])
    report['geometryCornerHash']=hashlib.sha256(np.asarray(v[f],dtype='<f8').tobytes()).hexdigest()
    expected=config['processing'].get('missCorrection',{}).get('unorientedSourcePatch',{}).get('targetCornerHash')
    if kind!='shadow' and expected:require(report['geometryCornerHash']==expected,'Visible assembly differs from the exact reviewed texture-patch geometry')
    report['topology'] = reports
    if kind: report['budget'] = assembly_budget(config['family'], counts, kind)
    return report


def fit(cfg, out):
    reset(); donor = import_source(cfg['source'], 'donor')
    # Measure the retained working mesh before transformation. Re-importing a
    # dense donor solely to measure it duplicates geometry and image residency.
    working = import_source(cfg['workingSource'], 'working-source') if cfg.get('workingSource') else donor
    if cfg['family']['family']=='firearm-sling':
        require(cfg.get('gripStandard'), 'Whole-firearm fitting requires the approved measured grip standard')
    matrix = similarity_matrix(cfg['fit'], pin(cfg['source'])['sha256'])
    grip_report = None
    if cfg.get('gripStandard'):
        from tools.itemkit.grip import calibration
        standard=json.loads(Path(cfg['gripStandard']).read_text())
        require(abs(cfg['family']['native']['gripLength']-standard['usableLength'])<1e-9,
                'Native target length differs from the approved grip standard')
        mv,mf=arrays(working)
        if cfg['family']['family']=='firearm-sling':
            from tools.itemkit.firearm_grip import measured_fit, GripDeparture
            try:
                matrix,grip_report=measured_fit(mv,mf,cfg['fit'],pin(cfg['source'])['sha256'],
                    pin(cfg.get('workingSource',cfg['source']))['sha256'],standard,cfg['family']['native']['gripOrigin'])
            except GripDeparture as exc:
                write(out/'grip-measurement.json',exc.report,fresh=True)
                raise
        else:
            matrix,grip_report=calibration(mv,mf,matrix,cfg['family']['native']['gripOrigin'],standard)
    donor_fit = apply_fit(donor, matrix, out/'donor-fit-normals.npz')
    if working != donor:
        working_fit = apply_fit(working, matrix, out/'working-fit-normals.npz')
    points = np.asarray(cfg['fit']['gripEndpoints'], float)
    require(points.shape == (2, 3), 'Measured source grip endpoints required')
    fitted = transform(points, matrix)
    length = float(np.linalg.norm(fitted[1]-fitted[0]))
    native = cfg['family']['native']
    require(abs(length/native['gripLength']-1) <= .02, 'Fitted grip differs from the measured native hand')
    require(np.linalg.norm(fitted.mean(0)-np.asarray(native['gripOrigin'])) <= .002, 'Grip origin differs from native hand')
    joins = cfg['processing'].get('joinY', [])
    firearm = cfg['family']['family']=='firearm-sling'
    if firearm: require(not joins, 'A whole firearm must not inherit melee part cuts')
    else: require(len(joins) == 2 and np.isfinite(joins).all() and joins[0] < joins[1], 'Two ordered natural part cuts required')
    objects = []
    for part in active_parts(cfg['family']):
        obj = duplicate(working, 'item_'+part); objects.append(obj)
        if firearm: continue
        if part == 'b': cut(obj, joins[0], False)
        if part == 'm': cut(obj, joins[0], True); cut(obj, joins[1], False)
        if part == 't': cut(obj, joins[1], True)
    donor.hide_render = True; donor.hide_set(True)
    if working != donor: working.hide_render = True; working.hide_set(True)
    report = measure(objects, cfg, kind=None)
    report.update(fitMatrix=matrix.tolist(), gripLength=length, donorAndTargetTransformIdentical=True)
    report['affineApplication'] = {'donor': donor_fit, 'working': working_fit if working != donor else donor_fit}
    if grip_report is not None: report['gripCalibration']=grip_report
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'scene.blend'))
    return report


def reduce(cfg, out, shadow=False):
    bpy.ops.wm.open_mainfile(filepath=cfg['scene'])
    objects = [];pommel_construction=None;proxy_reports={}
    for part in active_parts(cfg['family']):
        obj = bpy.data.objects['item_'+part]
        if shadow: obj = duplicate(obj, 'shadow_'+part)
        obj.hide_set(False); set_active([obj])
        proxy = cfg['processing'].get('shadowProxies', {}).get(part)
        if shadow and proxy:
            require(proxy.get('method') == 'projected-silhouette', 'Unknown shadow proxy method')
            source_p,source_f=arrays(obj)
            candidate=cfg.get('shadowCandidates',{}).get(part)
            require(candidate is not None and candidate['arrays'] in cfg['inputs'], 'Declare the checked CPU shadow candidate')
            verify([candidate['arrays']])
            require(candidate['sourceCornerHash']==hashlib.sha256(np.asarray(source_p[source_f],dtype='<f8').tobytes()).hexdigest(), 'Shadow candidate source changed')
            require(candidate['policyHash']==digest({'settings':proxy,'openingProbes':cfg['processing'].get('openingProbes',[]),
                    'budget':cfg['family']['budgets']['parts'][part]['shadow']}), 'Shadow candidate policy changed')
            with np.load(candidate['arrays']['path'],allow_pickle=False) as data:proxy_p=data['positions'];proxy_f=data['faces']
            proxy_reports[part]=candidate['checks']
            require(len(proxy_f)<=cfg['family']['budgets']['parts'][part]['shadow'] and topology(proxy_p,proxy_f)['closedWound'], 'Invalid CPU shadow candidate')
            mesh=bpy.data.meshes.new('measured-shadow-'+part);mesh.from_pydata(proxy_p.tolist(),[],proxy_f.tolist());mesh.update()
            obj.data=mesh;obj.matrix_world=Matrix.Identity(4)
        if shadow and not proxy and part=='b' and cfg['processing'].get('shadowPommel',{}).get('method')=='projected-loop':
            source_p,source_f=arrays(obj);settings=cfg['processing']['shadowPommel']
            probe=next(r for r in cfg['processing']['openingProbes'] if r['name']==settings['centreProbe'])
            proxy_p,proxy_f,pommel_construction=loop_shadow_proxy(source_p,source_f,probe)
            mesh=bpy.data.meshes.new('closed-pommel-loop-shadow');mesh.from_pydata(proxy_p.tolist(),[],proxy_f.tolist());mesh.update()
            obj.data=mesh;obj.matrix_world=Matrix.Identity(4)
        before_vertices, _ = arrays(obj)
        seam_before = [np.unique(before_vertices[np.abs(before_vertices[:, 1]-y) < 1e-7], axis=0)
                       for y in cfg['processing'].get('joinY', [])]
        budget = cfg['family']['budgets']['parts'][part]['shadow' if shadow else 'visible']
        _, faces = arrays(obj)
        if len(faces) > budget:
            modifier = obj.modifiers.new('Measured reduction', 'DECIMATE')
            modifier.decimate_type = 'COLLAPSE'; modifier.ratio = max(4, budget-4)/len(faces)
            modifier.use_collapse_triangulate = True
            bpy.ops.object.modifier_apply(modifier=modifier.name)
        mesh = bmesh.new(); mesh.from_mesh(obj.data)
        bmesh.ops.triangulate(mesh, faces=list(mesh.faces))
        mesh.to_mesh(obj.data); mesh.free()
        if not shadow:
            after_vertices, _ = arrays(obj)
            for y, before in zip(cfg['processing'].get('joinY', []), seam_before):
                after = np.unique(after_vertices[np.abs(after_vertices[:, 1]-y) < 1e-7], axis=0)
                require(before.shape == after.shape and np.allclose(before, after, atol=2e-6, rtol=0),
                        'Reduction changed a mating contour; use a constrained repair before retrying')
        objects.append(obj)
        if shadow: obj.hide_render = True; obj.hide_set(True)
    report = measure(objects, cfg, kind='shadow' if shadow else 'visible')
    if pommel_construction:report['pommelConstruction']=pommel_construction
    if proxy_reports:report['shadowProxies']=proxy_reports;report['visualReviewRequired']=True
    if not shadow and cfg['processing'].get('shadowProxies'):
        require(set(cfg['processing']['shadowProxies'])<=set(active_parts(cfg['family'])), 'Shadow proxy names must be active parts')
        source_arrays={}
        for part,obj in zip(active_parts(cfg['family']),objects):
            p,f=arrays(obj)
            source_arrays[part+'_positions']=p;source_arrays[part+'_faces']=f
        target=out/'shadow-source.npz';np.savez_compressed(target,**source_arrays);report['shadowSource']=pin(target)
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'scene.blend'))
    return report


def uv_corners(obj):
    mesh = obj.data; mesh.calc_loop_triangles()
    require(mesh.uv_layers.active is not None, 'Missing final atlas')
    return np.array([[tuple(mesh.uv_layers.active.data[i].uv) for i in tri.loops] for tri in mesh.loop_triangles])


def image_rgba(image):
    """Read Blender's bottom-up float pixels without a Python float tuple."""
    values = np.empty(len(image.pixels), np.float32)
    image.pixels.foreach_get(values)
    return values.reshape(image.size[1], image.size[0], 4)


def unwrap(cfg, out):
    bpy.ops.wm.open_mainfile(filepath=cfg['scene'])
    objects = [bpy.data.objects['item_'+p] for p in active_parts(cfg['family'])]
    before = [corners(obj) for obj in objects]
    if cfg.get('atlas'):
        with np.load(cfg['atlas'],allow_pickle=False) as archive:
            for part,obj in zip(active_parts(cfg['family']),objects):
                p,f=arrays(obj);require(np.array_equal(p,archive[part+'_positions']) and np.array_equal(f,archive[part+'_faces']),'Final atlas geometry binding differs')
                mesh=obj.data;mesh.calc_loop_triangles();layer=mesh.uv_layers.active or mesh.uv_layers.new(name='item-atlas')
                for triangle,coords in zip(mesh.loop_triangles,archive[part+'_uv']):
                    for loop,coordinate in zip(triangle.loops,coords):layer.data[loop].uv=coordinate
                if part+'_uvRegions' in archive.files:
                    from tools.itemkit.preflight import region_hash
                    labels=archive[part+'_uvRegions']
                    require(len(mesh.polygons)==len(labels) and all(len(poly.vertices)==3 for poly in mesh.polygons), 'UV-region lineage requires triangulated parts')
                    attribute=mesh.attributes.get('itemkit_uv_region') or mesh.attributes.new('itemkit_uv_region','INT','FACE')
                    attribute.data.foreach_set('value',labels)
                    obj['itemkit_uv_region_hash']=region_hash(p[f],uv_corners(obj),labels)
        require(all(np.array_equal(old,corners(obj)) for old,obj in zip(before,objects)),'Atlas application changed final geometry')
        bpy.ops.wm.save_as_mainfile(filepath=str(out/'scene.blend'))
        return {'atlas':pin(cfg['atlas']),'geometryUnchanged':True}
    set_active(objects); bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=cfg['processing']['uvMargin'])
    bpy.ops.uv.pack_islands(rotate=True, margin=cfg['processing']['uvMargin'])
    bpy.ops.object.mode_set(mode='OBJECT')
    require(all(np.array_equal(old, corners(obj)) for old, obj in zip(before, objects)),
            'UV pass changed ordered triangle positions')
    uv = np.concatenate([uv_corners(obj) for obj in objects]); report = {}
    for size in (4096, 2048, 1024, 512):
        audit, owners = raster_audit(uv, size)
        require(not audit['overlapFaces'] and not audit['degenerateUvFaces'], 'UV overlap or degeneracy')
        require(set(np.unique(owners[owners >= 0])) == set(range(len(uv))), 'Atlas misses small faces at '+str(size))
        gutters = gutter_audit(uv, size, owners)
        if size == cfg['family']['runtimeTextureSize']:
            require(gutters['nearbyChartPixelsByRadius']['2'] == 0,
                    'Runtime atlas needs a clear two-pixel filtering gutter')
        report[str(size)] = {'raster': audit, 'gutters': gutters}
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'scene.blend'))
    return report


def flat_material(name, colour):
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    shader = mat.node_tree.nodes.get('Principled BSDF'); shader.inputs['Base Color'].default_value = (*colour, 1)
    shader.inputs['Roughness'].default_value = .65
    return mat


def uv_arrays(cfg,out):
    bpy.ops.wm.open_mainfile(filepath=cfg['scene']);values={}
    for part in active_parts(cfg['family']):
        p,f=arrays(bpy.data.objects['item_'+part]);values[part+'_positions']=p;values[part+'_faces']=f
        values[part+'_hiddenCaps']=hidden_cap_faces(p,f,cfg['processing'].get('joinY', []))
    target=out/'uv-source.npz';np.savez_compressed(target,**values);return {'arrays':pin(target)}


def finish(cfg, out):
    """Non-destructive reference projection on the fitted donor, before colour transfer."""
    bpy.ops.wm.open_mainfile(filepath=cfg['scene']); settings = cfg['processing'].get('donorFinish')
    donor = bpy.data.objects['donor']; before = arrays(donor)
    if settings:
        require(settings.get('kind') == 'reference-grip' and settings.get('reviewed') is True,
                'Review reference projection bounds before finishing')
        image = bpy.data.images.load(cfg['reference'], check_existing=False)
        width, height = image.size; image.colorspace_settings.name = 'sRGB'
        yrange = settings['nativeY']; zrange = settings['nativeZ']
        require(yrange[0] < yrange[1] and zrange[0] < zrange[1], 'Positive grip projection extents required')
        for slot in donor.material_slots:
            material = slot.material.copy(); slot.material = material
            nodes = material.node_tree.nodes; links = material.node_tree.links
            shader = nodes.get('Principled BSDF'); require(shader is not None, 'Diffuse donor shader required')
            geometry = nodes.new('ShaderNodeNewGeometry'); xyz = nodes.new('ShaderNodeSeparateXYZ')
            normal = nodes.new('ShaderNodeSeparateXYZ'); links.new(geometry.outputs['Position'], xyz.inputs[0]); links.new(geometry.outputs['Normal'], normal.inputs[0])
            def math_node(operation, first, second=0):
                node = nodes.new('ShaderNodeMath'); node.operation = operation
                for index, value in enumerate((first, second)):
                    if isinstance(value, (float, int)): node.inputs[index].default_value = value
                    else: links.new(value, node.inputs[index])
                return node.outputs[0]
            u = math_node('DIVIDE', math_node('SUBTRACT', yrange[1], xyz.outputs['Y']), yrange[1]-yrange[0])
            v = math_node('DIVIDE', math_node('SUBTRACT', xyz.outputs['Z'], zrange[0]), zrange[1]-zrange[0])
            border = .025; mask = 1
            for fraction in (u, v):
                low = math_node('DIVIDE', fraction, border); high = math_node('DIVIDE', math_node('SUBTRACT', 1, fraction), border)
                mask = math_node('MINIMUM', mask, math_node('MINIMUM', low, high))
            mask = math_node('MAXIMUM', 0, mask)
            def projected_texture(pixels, across):
                corners = np.asarray(pixels, float)/np.array([width, height]); corners[:, 1] = 1-corners[:, 1]
                p00, p10, p11, p01 = corners
                components = []
                for axis in (0, 1):
                    value = math_node('ADD', float(p00[axis]), math_node('MULTIPLY', u, float(p10[axis]-p00[axis])))
                    value = math_node('ADD', value, math_node('MULTIPLY', across, float(p01[axis]-p00[axis])))
                    value = math_node('ADD', value, math_node('MULTIPLY', math_node('MULTIPLY', u, across), float(p00[axis]-p10[axis]+p11[axis]-p01[axis])))
                    components.append(value)
                vector = nodes.new('ShaderNodeCombineXYZ'); links.new(components[0], vector.inputs['X']); links.new(components[1], vector.inputs['Y'])
                texture = nodes.new('ShaderNodeTexImage'); texture.image = image; texture.extension = 'CLIP'
                links.new(vector.outputs[0], texture.inputs['Vector']); return texture.outputs['Color']
            front = projected_texture(settings['frontPixelQuad'], v)
            if settings.get('backPattern')=='carbon-weave':
                fy,fz=settings['backFrequency']
                wave1=math_node('SINE',math_node('MULTIPLY',math_node('ADD',math_node('MULTIPLY',u,fy),math_node('MULTIPLY',v,fz)),2*math.pi))
                wave2=math_node('SINE',math_node('MULTIPLY',math_node('SUBTRACT',math_node('MULTIPLY',u,fy),math_node('MULTIPLY',v,fz)),2*math.pi))
                back=math_node('ADD',settings['backBaseLinear'],math_node('MULTIPLY',settings['backAmplitudeLinear'],math_node('MULTIPLY',wave1,wave2)))
            else:
                repeat = math_node('FRACT', math_node('MULTIPLY', v, settings.get('backRepeat', 8)))
                back = projected_texture(settings['backPixelStrip'], repeat)
            base = shader.inputs['Base Color']; require(base.is_linked, 'Textured donor base colour required')
            source = base.links[0].from_socket
            for colour, facing in ((front, math_node('GREATER_THAN', normal.outputs['X'], .7)),
                                   (back, math_node('LESS_THAN', normal.outputs['X'], -.7))):
                mix = nodes.new('ShaderNodeMixRGB'); mix.blend_type = 'MIX'
                links.new(math_node('MULTIPLY', mask, facing), mix.inputs[0]); links.new(source, mix.inputs[1]); links.new(colour, mix.inputs[2]); source = mix.outputs[0]
            links.new(source, base)
    after = arrays(donor)
    require(all(np.array_equal(a, b) for a, b in zip(before, after)), 'Appearance finishing changed fitted donor geometry')
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'scene.blend'))
    return {'donorGeometryUnchanged': True, 'reference': pin(cfg['reference']), 'projection': settings,
            'reverseBrandingRequired': False, 'visualReviewRequired': True}


def transfer_preflight(cfg, out, donor, low):
    from tools.itemkit.preflight import uv_report
    p,f=arrays(low);uv=uv_corners(low);caps=hidden_cap_faces(p,f,cfg['processing'].get('joinY',[]))
    regions=None
    if low.get('itemkit_uv_regions_verified'):
        attribute=low.data.attributes['itemkit_uv_region']
        regions=np.array([attribute.data[tri.polygon_index].value for tri in low.data.loop_triangles])
    report=uv_report(p[f],uv,caps,cfg['family']['runtimeTextureSize'],regions=regions)
    if not report['passed']:
        write(out/'preflight.json',report,fresh=True)
        raise ValueError('Runtime UV preflight failed; inspect preflight.json before baking')
    dp,df=arrays(donor);tree=BVHTree.FromPolygons([Vector(row) for row in dp],df.tolist(),all_triangles=True)
    policy=cfg['processing'].get('missCorrection',{})
    maximum=policy.get('maximumDistance',.003);alignment=policy.get('minimumNormalAlignment',.5)
    require(0<maximum<=.003 and 0<alignment<=1, 'Bounded preflight donor policy required')
    patch=policy.get('unorientedSourcePatch');allowed=set()
    if patch:
        allowed=validate_texture_patch(p[f],patch,maximum_distance=min(maximum,policy.get('maximumUnorientedDistance',.0021)))
    failed=[];distances=[]
    for index in np.flatnonzero(~caps):
        triangle=p[f[index]];normal=np.cross(triangle[1]-triangle[0],triangle[2]-triangle[0]);length=np.linalg.norm(normal)
        require(length>1e-12, 'Degenerate transfer target');normal/=length
        point=Vector(triangle.mean(0));nearest=tree.find_nearest(point)
        require(nearest[0] is not None, 'Empty donor surface');distances.append(float(nearest[3]))
        candidates=tree.find_nearest_range(point,maximum)
        if not any(np.dot(row[1],normal)>=alignment for row in candidates):
            if int(index) not in allowed or nearest[3]>patch['maximumDistance']:failed.append(int(index))
    report['donorSampling']={'sample':'visible-face-centroids','faces':len(distances),'maximumDistance':max(distances),
        'failedFaces':failed,'policyDistance':maximum,'minimumNormalAlignment':alignment,
        'continuousSurfaceProof':False}
    if failed:report['blockers'].append('donor-distance-or-facing')
    report['passed']=not report['blockers']
    write(out/'preflight.json',report,fresh=True)
    require(report['passed'], 'Transfer preflight failed; inspect preflight.json before baking')
    return report


def joined_target(cfg):
    objects=[bpy.data.objects['item_'+p] for p in active_parts(cfg['family'])]
    qualified=[]
    for obj in objects:
        attribute=obj.data.attributes.get('itemkit_uv_region')
        if attribute:
            from tools.itemkit.preflight import region_hash
            p,f=arrays(obj);labels=np.array([attribute.data[tri.polygon_index].value for tri in obj.data.loop_triangles])
            require(obj.get('itemkit_uv_region_hash')==region_hash(p[f],uv_corners(obj),labels), 'Stale atlas UV-region lineage')
        qualified.append(attribute is not None)
    copies=[duplicate(obj,'bake_'+obj.name) for obj in objects]
    set_active(copies);bpy.ops.object.join()
    bpy.context.object['itemkit_uv_regions_verified']=all(qualified)
    return bpy.context.object


def preflight(cfg, out):
    bpy.ops.wm.open_mainfile(filepath=cfg['scene'])
    objects=[bpy.data.objects['item_'+p] for p in active_parts(cfg['family'])]
    geometry=measure(objects,cfg)
    low=joined_target(cfg)
    return {'geometry':geometry,'transfer':transfer_preflight(cfg,out,bpy.data.objects['donor'],low),
            'visualReviewRequired':True}


def bake(cfg, out):
    bpy.ops.wm.open_mainfile(filepath=cfg['scene'])
    donor = bpy.data.objects['donor']; donor.hide_set(False); donor.hide_render = False
    low=joined_target(cfg)
    preflight_report=transfer_preflight(cfg,out,donor,low)
    # Base colour emission bake works for metallic as well as dielectric donor materials.
    for slot in donor.material_slots:
        original = slot.material; require(original and original.use_nodes, 'Textured donor material required')
        mat = original.copy(); slot.material = mat
        bsdf = mat.node_tree.nodes.get('Principled BSDF'); require(bsdf is not None, 'Unsupported donor shader')
        output = next(n for n in mat.node_tree.nodes if n.type == 'OUTPUT_MATERIAL')
        emission = mat.node_tree.nodes.new('ShaderNodeEmission')
        colour = bsdf.inputs['Base Color']
        if colour.is_linked: mat.node_tree.links.new(colour.links[0].from_socket, emission.inputs['Color'])
        else: emission.inputs['Color'].default_value = colour.default_value
        mat.node_tree.links.new(emission.outputs[0], output.inputs['Surface'])
    uv = uv_corners(low); cap_vertices, cap_triangles = arrays(low)
    cap_faces = hidden_cap_faces(cap_vertices,cap_triangles,cfg['processing'].get('joinY', []))
    visible_ids=np.flatnonzero(~cap_faces); cap_ids=np.flatnonzero(cap_faces)
    audit, owners = raster_audit(uv[visible_ids], cfg['family']['bakeSize'])
    require(not audit['overlapFaces'] and not audit['degenerateUvFaces'], 'Invalid bake UVs')
    mapped=owners>=0;owners[mapped]=visible_ids[owners[mapped]]
    cap_audit,cap_owners=raster_audit(uv[cap_ids],cfg['family']['bakeSize'])
    require(not cap_audit['degenerateUvFaces'],'Degenerate hidden cap UVs')
    caps=cap_owners>=0;require(not np.any(caps & mapped),'Hidden cap palette overlaps visible UVs')
    owners[caps]=cap_ids[cap_owners[caps]]
    size = cfg['family']['bakeSize']
    image = bpy.data.images.new('item-source-4k', width=size, height=size, alpha=False, float_buffer=True)
    image.generated_color = (1, 0, 1, 1); image.colorspace_settings.name = 'Non-Color'
    material = flat_material('item-atlas', (.5, .5, .5))
    texture = material.node_tree.nodes.new('ShaderNodeTexImage'); texture.image = image
    material.node_tree.nodes.active = texture
    low.data.materials.clear(); low.data.materials.append(material)
    scene = bpy.context.scene; scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = 1
    scene.render.threads_mode = 'FIXED'; scene.render.threads = 4
    scene.render.bake.use_clear = False; scene.render.bake.margin = 0
    scene.render.bake.use_selected_to_active = True
    scene.render.bake.cage_extrusion = cfg['processing']['cageExtrusion']
    scene.render.bake.max_ray_distance = cfg['processing']['maxRayDistance']
    set_active([low, donor]); bpy.ops.object.bake(type='EMIT', use_selected_to_active=True)
    pixels = image_rgba(image)
    # Do not trust a face attribute interpolated by a decimator to classify hidden caps.
    pixels[caps, :3] = cfg['processing']['capColour']
    misses = np.all(np.abs(pixels[..., :3]-[1, 0, 1]) < 1e-5, axis=2) & (owners >= 0) & ~caps
    # Keep failed atlas and masks before refusing to fill anything.
    image.pixels.foreach_set(pixels.reshape(-1)); image.filepath_raw = str(out/'bake-unpadded.exr'); image.file_format = 'OPEN_EXR'; image.save()
    np.savez_compressed(out/'bake-masks.npz', owners=owners, hiddenCaps=caps, visibleMisses=misses)
    projected_misses=int(misses.sum());correction=None
    if projected_misses:
        save_bake_recovery(cfg,out,donor,low,owners,caps,misses)
        correction=correct_projection_misses(cfg,out,donor,low,pixels,owners,misses)
        misses[:]=False
        np.savez_compressed(out/'bake-masks.npz',owners=owners,hiddenCaps=caps,visibleMisses=misses)
    # Use Blender's own bake margin only after the independently audited unpadded pass.
    # Padding is implemented in the bound CPU postprocessor; it never overwrites mapped texels.
    np.save(out/'bake-linear.npy', pixels[..., :3])
    donor.hide_render = True; donor.hide_set(True); bpy.data.objects.remove(low, do_unlink=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'scene.blend'))
    return {'visibleMisses': 0,'projectedMisses':projected_misses,'missCorrection':correction, 'preflight':preflight_report,'hiddenCapTexels': int(caps.sum()), 'mappedTexels': int((owners >= 0).sum()),
            'linear': pin(out/'bake-linear.npy'), 'masks': pin(out/'bake-masks.npz')}


def save_bake_recovery(cfg,out,donor,low,owners,caps,misses):
    from tools.itemkit.preflight import target_hash
    np.savez_compressed(out/'bake-masks-original.npz',owners=owners,hiddenCaps=caps,visibleMisses=misses)
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'recovery-scene.blend'))
    images={}
    for slot in donor.material_slots:
        for node in slot.material.node_tree.nodes:
            if node.type=='TEX_IMAGE' and node.image and not node.image.packed_file:
                require(node.image.filepath, 'Pack generated donor images before recovery')
                row=pin(bpy.path.abspath(node.image.filepath));images[row['path']]=row
    if cfg.get('reference'):
        row=pin(cfg['reference']);images[row['path']]=row
    p,f=arrays(low);dp,df=arrays(donor)
    proof={'schemaVersion':1,'kind':'item-bake-recovery','scene':pin(out/'recovery-scene.blend'),
           'sourceScene':pin(cfg['scene']),
           'pixels':pin(out/'bake-unpadded.exr'),'masks':pin(out/'bake-masks-original.npz'),
           'externalImages':list(images.values()),'family':cfg['family'],'processing':cfg['processing'],
           'reference':cfg.get('reference'),'targetName':low.name,'donorName':donor.name,
           'targetHash':target_hash(p[f],uv_corners(low)), 'donorHash':target_hash(dp[df],uv_corners(donor))}
    write(out/'bake-recovery.json',proof,fresh=True)
    return proof


def recover_bake(cfg,out):
    from tools.itemkit.recovery import recovery_inputs,validate_pixels,successful_pixel_hash
    from tools.itemkit.preflight import target_hash
    proof_path=cfg['recoveryProof'];require(pin(proof_path) in cfg['inputs'],'Declare the recovery proof')
    proof=json.loads(Path(proof_path).read_text(encoding='utf-8-sig'))
    inputs=recovery_inputs(proof)
    require(all(row in cfg['inputs'] for row in inputs),'Declare all recovery artifacts and external images')
    require(pin(cfg['scene'])==proof['sourceScene'], 'Recovery source scene differs')
    require(cfg['family']==proof['family'],'Recovery family differs')
    without_policy=lambda d:{k:v for k,v in d.items() if k!='missCorrection'}
    require(without_policy(cfg['processing'])==without_policy(proof['processing']), 'Only the reviewed miss-correction policy may change')
    bpy.ops.wm.open_mainfile(filepath=proof['scene']['path'])
    donor=bpy.data.objects[proof['donorName']];low=bpy.data.objects[proof['targetName']]
    p,f=arrays(low);dp,df=arrays(donor)
    require(target_hash(p[f],uv_corners(low))==proof['targetHash'] and target_hash(dp[df],uv_corners(donor))==proof['donorHash'],
            'Recovery mesh/UV correspondence differs')
    image=bpy.data.images.load(proof['pixels']['path'],check_existing=False);image.colorspace_settings.name='Non-Color'
    pixels=image_rgba(image)
    with np.load(proof['masks']['path'],allow_pickle=False) as masks:
        require(set(masks.files)=={'owners','hiddenCaps','visibleMisses'},'Explicit retained masks required')
        owners=masks['owners'];caps=masks['hiddenCaps'];misses=masks['visibleMisses']
    require(owners.shape==(cfg['family']['bakeSize'],)*2,'Recovery bake size differs')
    count=validate_pixels(pixels,owners,caps,misses,len(f));before=successful_pixel_hash(pixels,misses)
    recovery_cfg={**cfg,'reference':proof.get('reference')}
    correction=correct_projection_misses(recovery_cfg,out,donor,low,pixels,owners,misses) if count else None
    require(before==successful_pixel_hash(pixels,misses) and np.isfinite(pixels).all(),'Recovery changed successful pixels')
    np.save(out/'bake-linear.npy',pixels[...,:3]);np.savez_compressed(out/'bake-masks.npz',owners=owners,hiddenCaps=caps,visibleMisses=np.zeros_like(misses))
    donor.hide_render=True;donor.hide_set(True);bpy.data.objects.remove(low,do_unlink=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'scene.blend'));verify(inputs, fresh=True)
    return {'visibleMisses':0,'projectedMisses':count,'missCorrection':correction,'recoveryProof':pin(proof_path),
            'linear':pin(out/'bake-linear.npy'),'masks':pin(out/'bake-masks.npz'),
            'reusedCompletedBake':True,'successfulBakeTexelsUnchanged':True,'visualReviewRequired':True}


def correct_projection_misses(cfg,out,donor,low,pixels,owners,misses):
    policy=cfg['processing'].get('missCorrection',{})
    require(policy.get('method')=='nearest-finished-donor','Visible bake misses require an explicit bounded donor correction; padding cannot repair them')
    maximum=policy['maximumDistance'];alignment=policy['minimumNormalAlignment']
    require(0<maximum<=.003 and 0<alignment<=1,'Bounded outward donor transfer required')
    y,x=np.nonzero(misses);ids=owners[y,x];size=len(owners);uv=uv_corners(low)[ids]
    p,f=arrays(low);tri=p[f[ids]];ab=uv[:,1]-uv[:,0];ac=uv[:,2]-uv[:,0];q=np.c_[(x+.5)/size,(y+.5)/size]-uv[:,0]
    det=ab[:,0]*ac[:,1]-ab[:,1]*ac[:,0];u=(q[:,0]*ac[:,1]-q[:,1]*ac[:,0])/det;v=(ab[:,0]*q[:,1]-ab[:,1]*q[:,0])/det
    points=tri[:,0]+u[:,None]*(tri[:,1]-tri[:,0])+v[:,None]*(tri[:,2]-tri[:,0])
    normals=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);normals/=np.linalg.norm(normals,axis=1)[:,None]
    dp,df=arrays(donor);bvh=BVHTree.FromPolygons([Vector(row) for row in dp],df.tolist(),all_triangles=True)
    patch=policy.get('unorientedSourcePatch');patch_faces=set()
    if patch:
        patch_bound=policy.get('maximumUnorientedDistance',.0021)
        require(patch_bound<=maximum,'Texture patch qualification exceeds this transfer distance')
        patch_faces=validate_texture_patch(p[f],patch,maximum_distance=patch_bound)
    locations=[];sources=[];distances=[];dots=[];unoriented=[]
    for face,point,normal in zip(ids,points,normals):
        candidates=[row for row in bvh.find_nearest_range(Vector(point),maximum) if np.dot(row[1],normal)>=alignment]
        patched=False
        if not candidates and int(face) in patch_faces:
            nearest=bvh.find_nearest(Vector(point))
            if nearest[3]<=patch['maximumDistance']:candidates=[nearest];patched=True
        require(bool(candidates),'No compatible donor surface within the recorded miss-correction bound; target face '+str(face))
        position,source_normal,index,distance=min(candidates,key=lambda row:row[3])
        locations.append(position);sources.append(index);distances.append(distance);dots.append(np.dot(source_normal,normal));unoriented.append(patched)
    require(not any(unoriented) or sum(unoriented)/np.count_nonzero(owners>=0)<=patch['maximumTextureFraction'],'Unoriented donor repair exceeds its reviewed texel scope')
    locations=np.asarray(locations);sources=np.asarray(sources);source_tri=dp[df[sources]]
    a=source_tri[:,1]-source_tri[:,0];b=source_tri[:,2]-source_tri[:,0];c=locations-source_tri[:,0]
    aa=np.einsum('ij,ij->i',a,a);bb=np.einsum('ij,ij->i',b,b);ab=np.einsum('ij,ij->i',a,b)
    ca=np.einsum('ij,ij->i',c,a);cb=np.einsum('ij,ij->i',c,b);det=aa*bb-ab*ab
    require(np.all(det>1e-25),'Degenerate donor triangle in colour transfer')
    u=(bb*ca-ab*cb)/det;v=(aa*cb-ab*ca)/det;bary=np.c_[1-u-v,u,v]
    source_uv=np.einsum('ij,ijk->ik',bary,uv_corners(donor)[sources])
    require(len(donor.material_slots)==1,'Miss correction requires the verified single donor material')
    material=donor.material_slots[0].material
    # bake() replaced the output with emission, while the original diffuse graph
    # remains available at the Principled input for this colour-only correction.
    node=material.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].links[0].from_node
    while node.type=='MIX_RGB':node=node.inputs[1].links[0].from_node
    require(node.type=='TEX_IMAGE' and node.image is not None,'Unsupported donor colour graph for miss correction')
    colour_probes={}
    def raw_image(image,role):
        copy=image.copy();copy.colorspace_settings.name='Non-Color'
        result=image_rgba(copy)[...,:3].copy()
        xy=np.array([[(k*811)%copy.size[0],(k*137)%copy.size[1]] for k in range(16)])
        colour_probes[role+'XY']=xy;colour_probes[role+'RGB']=result[xy[:,1],xy[:,0]]
        bpy.data.images.remove(copy);return result
    base=raw_image(node.image,'base');reference=raw_image(bpy.data.images.load(cfg['reference'],check_existing=True),'reference') if cfg.get('reference') else None
    donor.data.calc_normals_split();corner_normals=np.array([[tuple(donor.data.loops[i].normal) for i in t.loops] for t in donor.data.loop_triangles])
    smooth=np.einsum('ij,ijk->ik',bary,corner_normals[sources]);smooth/=np.linalg.norm(smooth,axis=1)[:,None]
    colours=finished_colour(base,source_uv,locations,smooth,reference,cfg['processing'].get('donorFinish'))
    require(np.isfinite(colours).all() and np.all((colours>=0)&(colours<=1)),'Invalid transferred donor colour')
    pixels[y,x,:3]=colours
    proof=out/'donor-miss-transfer.npz';np.savez_compressed(proof,y=y,x=x,targetFaces=ids,sourceFaces=sources,sourceUV=source_uv,sourcePositions=locations,distances=distances,normalAlignment=dots,unorientedPatch=unoriented,colours=colours,**colour_probes)
    return {'method':'nearest-finished-donor','correctedTexels':len(y),'unorientedPatchTexels':sum(unoriented),'maximumDistance':float(max(distances)),'minimumNormalAlignment':float(min(dots)),'policy':policy,'proof':pin(proof),'successfulBakeTexelsUnchanged':True,'appearanceFieldSampled':False,'visualReviewRequired':True}


def render_still():
    bpy.ops.render.render(write_still=True)


def render(cfg, out, source=False, *, _clay_review=None):
    firearm=cfg['family']['family']=='firearm-sling'
    if source:
        reset(); obj = import_source(cfg['source'], 'review-source'); objects = [obj]
    else:
        bpy.ops.wm.open_mainfile(filepath=cfg['scene']); objects = [bpy.data.objects['item_'+p] for p in active_parts(cfg['family'])]
    for obj in bpy.data.objects:
        if obj.type == 'MESH': obj.hide_render = obj not in objects
    minimum, maximum = world_bounds(objects); center = (maximum+minimum)/2
    spans = maximum-minimum; extent = np.linalg.norm(spans)
    require(extent > 0, 'Empty inspection mesh')
    clay = flat_material('inspection-clay', (.65, .65, .65))
    texture_mat = unlit_mat = None
    if not source:
        texture_mat = flat_material('inspection-runtime', (.5, .5, .5))
        tex = texture_mat.node_tree.nodes.new('ShaderNodeTexImage'); tex.image = bpy.data.images.load(cfg['texture'])
        shader = texture_mat.node_tree.nodes.get('Principled BSDF'); texture_mat.node_tree.links.new(tex.outputs['Color'], shader.inputs['Base Color'])
        unlit_mat=texture_mat.copy();emission=unlit_mat.node_tree.nodes.new('ShaderNodeEmission')
        unlit_tex=next(n for n in unlit_mat.node_tree.nodes if n.type=='TEX_IMAGE')
        unlit_output=next(n for n in unlit_mat.node_tree.nodes if n.type=='OUTPUT_MATERIAL')
        unlit_mat.node_tree.links.new(unlit_tex.outputs['Color'],emission.inputs['Color']);unlit_mat.node_tree.links.new(emission.outputs[0],unlit_output.inputs['Surface'])
    scene = bpy.context.scene; scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'; scene.cycles.samples = 16
    scene.render.threads_mode = 'FIXED'; scene.render.threads = 4
    scene.render.resolution_x = scene.render.resolution_y = 1024; scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'; scene.world.color = (.18, .18, .18)
    bpy.ops.object.camera_add(); camera = bpy.context.object; scene.camera = camera
    camera.data.type = 'ORTHO'; camera.data.ortho_scale = extent*1.1
    bpy.ops.object.light_add(type='AREA', location=tuple(center+extent*np.array([1, 1, 2])))
    light = bpy.context.object; light.data.energy = cfg.get('render',{}).get('keyLightEnergy',80)*extent**2; light.data.shape = 'DISK'; light.data.size = extent*2
    fill_energy = cfg.get('render',{}).get('fillLightEnergy',0)
    require(type(fill_energy) in (int,float) and np.isfinite(fill_energy) and fill_energy >= 0, 'Invalid inspection fill light')
    if fill_energy:
        bpy.ops.object.light_add(type='AREA', location=tuple(center+extent*np.array([-1,-1,-2])))
        fill = bpy.context.object; fill.data.energy = fill_energy*extent**2; fill.data.shape = 'DISK'; fill.data.size = extent*2
        fill.rotation_euler = (Vector(center)-fill.location).to_track_quat('-Z','Y').to_euler()
    directions = {'front': (1, 0, 0), 'rear': (-1, 0, 0), 'edge-left': (0, 0, 1), 'edge-right': (0, 0, -1),
                  'tip': (0, 1, 0), 'pommel-underside': (0, -1, 0), 'oblique': (1, .4, 1)}
    views=firearm_views(cfg.get('render',{}).get('firearmViews')) if firearm else {
        name:{'direction':direction,'target':center,'up':(0,0,-1),'scale':1.1} for name,direction in directions.items()}
    frames = [];camera_records=[]
    if _clay_review is not None:
        require(not source, 'Source inspection cannot reuse final clay')
        from tools.itemkit.review import reuse_clay
        frames, camera_records = reuse_clay(cfg, out, _clay_review)
    def aim(target,up=(0,0,-1)):
        camera.rotation_euler=Matrix(camera_basis(np.asarray(camera.location),np.asarray(target),up).tolist()).to_euler()
    def record(mode,name):
        camera_records.append({'mode':mode,'view':name,'matrix':np.asarray(camera.matrix_world).tolist(),'orthoScale':camera.data.ortho_scale,'size':[scene.render.resolution_x,scene.render.resolution_y]})
    original_view=(scene.view_settings.view_transform,scene.view_settings.look)
    for mode in (['clay'] if source else ['textured','unlit'] if _clay_review is not None else ['clay', 'textured','unlit']):
        scene.view_settings.view_transform='Standard' if mode=='unlit' else original_view[0]
        scene.view_settings.look='None' if mode=='unlit' else original_view[1]
        for obj in objects:
            obj.data.materials.clear(); obj.data.materials.append(clay if mode == 'clay' else unlit_mat if mode=='unlit' else texture_mat)
        for name, view in views.items():
            camera.data.ortho_scale=extent*view['scale']
            camera.location = Vector(view['target'])+Vector(view['direction']).normalized()*extent*2
            aim(view['target'],view['up'])
            scene.render.filepath = str(out/f'{mode}-{name}.png'); render_still()
            frames.append(pin(scene.render.filepath))
            record(mode,name)
        if not source and not firearm:
            grip_min, grip_max = world_bounds([bpy.data.objects['item_m']]); target = (grip_max+grip_min)/2
            camera.data.ortho_scale = np.linalg.norm(grip_max-grip_min)*1.8
            camera.location = Vector(target)+Vector((1, 0, 0))*extent*2
            aim(target)
            scene.render.filepath = str(out/f'{mode}-grip-joins.png'); render_still()
            frames.append(pin(scene.render.filepath));record(mode,'grip-joins');camera.data.ortho_scale = extent*1.1
    require(len(frames) == ((8 if firearm else 7) if source else 24), 'Incomplete inspection views')
    icons = {}
    if not source:
        dimensions = cfg['family']['native'].get('iconDimensions')
        require(isinstance(dimensions, dict) and set(dimensions) == set(active_parts(cfg['family'])), 'Measure active-part inventory icon dimensions')
        scene.render.film_transparent = True; scene.render.image_settings.color_mode = 'RGBA'
        for part in active_parts(cfg['family']):
            obj = bpy.data.objects['item_'+part]
            for other in objects: other.hide_render = other != obj
            width, height = dimensions[part]
            require(type(width) is type(height) is int and width > 0 and height > 0 and width % 32 == height % 32 == 0,
                    'Invalid native icon cell dimensions')
            scene.render.resolution_x = width; scene.render.resolution_y = height
            camera.data.ortho_scale = max(spans[1], spans[2]*height/width)*1.1
            camera.location = Vector(center)+Vector((1, 0, 0))*extent*2
            aim(center,up=(0,1,0))
            scene.render.filepath = str(out/f'icon-{part}.png'); render_still()
            icons[part] = pin(scene.render.filepath)
        for obj in objects:
            obj.hide_render=False;obj.data.materials.clear();obj.data.materials.append(texture_mat)
        scene.render.resolution_x=scene.render.resolution_y=1024;scene.render.film_transparent=False
        scene.view_settings.view_transform=original_view[0];scene.view_settings.look=original_view[1]
        camera.data.ortho_scale=extent*1.1;camera.location=Vector(center)+Vector((1,0,0))*extent*2
        aim(center)
        mesh_name='item-runtime.glb' if firearm else 'cougar-4956tri-runtime.glb'
        set_active(objects);bpy.ops.export_scene.gltf(filepath=str(out/mesh_name),export_format='GLB',use_selection=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(out/'scene.blend'))
    return {'frames': frames, 'icons': icons,'cameras':camera_records, 'threads': 4, 'runtimeTexture': cfg.get('texture'), 'visualApproval': False,
            'reusedClayFrames': 8 if _clay_review is not None else 0,
            'alignedMultipartIconCamera':not source,'texturedMesh':pin(out/mesh_name) if not source else None}


def export_arrays(cfg, out):
    bpy.ops.wm.open_mainfile(filepath=cfg['scene']); report = {}
    for part in active_parts(cfg['family']):
        obj = bpy.data.objects['item_'+part]; v, f = arrays(obj); obj.data.calc_normals_split()
        normals = np.array([[tuple(obj.data.loops[i].normal) for i in t.loops] for t in obj.data.loop_triangles])
        shadow = bpy.data.objects['shadow_'+part]; sv, sf = arrays(shadow)
        require(topology(sv, sf)['closedWound'], 'Invalid shadow proxy')
        target = out/f'{part}.npz'
        np.savez(target, positions=v[f], normals=normals, uv=uv_corners(obj), shadowVertices=sv, shadowFaces=sf)
        report[part] = pin(target)
    return {'parts': report}


def render_finish_variants(cfg, out):
    from tools.itemkit.review import render_variants
    for path in [cfg['scene'], *cfg['textures'].values()]:
        require(pin(path) in cfg['inputs'], 'Variant render input is not declared')
    return render_variants(cfg, cfg['textures'], out/'variants', renderer=render)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--config', required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:]); cfg = json.loads(Path(args.config).read_text())
    verify(cfg['inputs']); output = Path(cfg['output']); output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    actions = {'fit': fit, 'reduce': reduce, 'uv-arrays': uv_arrays, 'unwrap': unwrap, 'finish': finish, 'bake': bake,
               'preflight-transfer':preflight, 'recover-bake':recover_bake,
               'shadow': lambda c, o: reduce(c, o, shadow=True), 'render': render,
               'inspect': lambda c, o: render(c, o, source=True), 'export-arrays': export_arrays,
               'render-variants': render_finish_variants}
    result = actions[cfg['stage']](cfg, output); verify(cfg['inputs'], fresh=True)
    if (output/'scene.blend').exists(): result['scene'] = pin(output/'scene.blend')
    result['elapsedSeconds'] = time.monotonic()-started
    write(output/'result.json', result, fresh=True)


if __name__ == '__main__': main()
