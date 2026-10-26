"""Immutable, input-hashed stage receipts for the reusable CPU processing chain."""
from pathlib import Path
import sys
import time
import traceback
import uuid
import numpy as np
from PIL import Image
from . import common
from .common import read,write,require,pin,verify,asset,manifest,bindings,source_version,digest,code_pins,python_package_pins,stage_code_pins,stage_file_pins,stage_source_version

# Every stage produces evidence that needs an explicit operator decision before consumption.
STAGES=('prepare','precluster','fit','repair','unwrap','bake','paint','ownership','tone','palette','export','native','render')


def stage_roles(stage,data):
    """Manifest input roles a stage may read. Receipts pin only the roles actually read, and reading one outside this
    declaration fails the stage, so launch input lists built from it stay complete."""
    inputs=set(data.get('inputs',{}));palettes=set(data.get('palette',{}).get('inputs',{}).values())
    roles={'prepare':{r for r in inputs if r in ('clay','detail','design') or r.endswith(('Clay','Detail'))},
        'precluster':{'raw'},'fit':{'fitReference','comfyExport'},'repair':{'comfyExport','shellInspection','bodyNeck'},'unwrap':{'repairedMesh'},'bake':{'field','uvMesh'},
        'paint':{'uvMesh','basecolor4k'},
        'ownership':{'uvMesh','basecolor4k','metallic4k','ownership4k'}|{row.get('maskInput') for row in data.get('ownership',{}).get('views',[])},
        'tone':{'uvMesh','basecolor4k','metallic4k','ownership4k','ownership1k','detail','frontDetail'}|palettes,
        'palette':{'uvMesh','runtimeColor','ownership1k'}|palettes,'export':{'uvMesh','runtimeShades','ownership1k'},'native':set(),
        'render':{'uvMesh'}|set(data.get('render',{}).get('mapInputs',{}).values())}[stage]
    return roles&inputs


# Manifest sections each stage's code reads. A receipt hashes only the sections (and declared input roles) of its stage
# and its dependency closure, so tuning a later stage's rules does not invalidate earlier, expensive stages.
# 'section.key' binds one key of a section: prepare reads only the design review, so later approvals (appearance field,
# texture maps) added to the same manifest do not stale the matte.
STAGE_SECTIONS={'prepare':{'profile','matte','alignment','features','approval.referenceDesignReviewed'},'precluster':set(),'fit':{'fit'},'repair':{'mesh','fit'},
    'unwrap':{'mesh'},'bake':{'mesh','approval'},'paint':{'paint','mesh','approval.textureMaps'},'ownership':{'ownership','paint','mesh','approval'},
    'tone':{'tone','palette.inputs','ownership','approval'},'palette':{'palette','ownership','approval'},'export':{'fit','palette','mesh','approval'},
    'native':{'fit'},'render':{'render','approval'}}


def stage_libraries(stage,data):
    """Byte-bound libraries a stage may load; enforced like stage_roles. Reviewed-UV reuse only audits, so it needs no xatlas."""
    if stage=='unwrap' and data.get('mesh',{}).get('reuseReviewedUvs',False):return set()
    return {'precluster':{'igl','pymeshlab'},'repair':{'igl','pymeshlab'},'unwrap':{'xatlas'}}.get(stage,set())


def unworded(value):
    """A manifest section without the wording of its `notes` keys (any depth). Stages read notes only as non-empty
    review gates, so a note keeps just that presence bit: rewording one never stales receipts, blanking one still does."""
    if isinstance(value,dict):return {k:(isinstance(v,str) and bool(v.strip())) if k=='notes' else unworded(v) for k,v in value.items()}
    return [unworded(v) for v in value] if isinstance(value,list) else value


def same_content(pin_row):
    """Comparable identity of a stage output: sha256 for binaries; JSON audits (which embed their own attempt folder,
    upstream attempt paths and wall-clock timings) compare after attempt-NN -> attempt-* and without *Seconds fields."""
    if not str(pin_row['path']).endswith('.json'):return pin_row['sha256']
    import re
    def walk(value):
        if isinstance(value,dict):return {k:walk(v) for k,v in value.items() if not (k=='seconds' or k.endswith('Seconds'))}
        if isinstance(value,list):return [walk(v) for v in value]
        return re.sub(r'attempt-\d+','attempt-*',value) if isinstance(value,str) else value
    return 'json:'+digest(walk(read(pin_row['path'])))


class Runner:
    def __init__(self, manifest_path, bindings_path, run, *, runtime=None):
        self.manifest_path=Path(manifest_path).resolve();self.bindings_path=Path(bindings_path).resolve()
        self.data=manifest(self.manifest_path);self.bindings=bindings(self.bindings_path);self.runtime=runtime
        self.run=Path(run).resolve();self.run.mkdir(parents=True,exist_ok=True)
        self.state_path=self.run/'state.json'
        self.state=read(self.state_path) if self.state_path.exists() else {'schemaVersion':1,'id':self.data['id'],'stages':{}}
        require(self.state['id']==self.data['id'],'Run belongs to a different head')
        self._verified=set();self._read=None

    def manifest_digest(self,stage):
        closure=set();pending=[stage]
        while pending:
            current=pending.pop()
            if current not in closure:closure.add(current);pending+=self.dependencies(current)
        sections=set().union(*(STAGE_SECTIONS[s] for s in closure));roles=set().union(*(stage_roles(s,self.data) for s in closure))
        sections={k for k in sections if k.split('.')[0]==k or k.split('.')[0] not in sections}  # a whole section covers its keys
        return digest({'schemaVersion':self.data['schemaVersion'],'id':self.data['id'],'closure':sorted(closure),
                       'dependencies':{s:self.dependencies(s) for s in sorted(closure)},
                       'sections':{k:unworded(self.data.get(k) if '.' not in k else (self.data.get(k.split('.')[0]) or {}).get(k.split('.',1)[1])) for k in sorted(sections)},'inputs':{r:self.data['inputs'][r] for r in sorted(roles)}})

    def _verify(self,pins):
        # Upstream receipts repeat the same files; hash each (path, digest) once per check before execution.
        # The post-execution check in execute stays uncached so changes during a stage are still caught.
        fresh={(p['path'],p['sha256']):p for p in pins if (p['path'],p['sha256']) not in self._verified}
        verify(list(fresh.values()));self._verified.update(fresh)

    def input(self,name):
        require(name in self.data['inputs'],'Missing manifest input: '+name)
        if self._read is not None:self._read.add(name)
        if name in ('ownership1k','ownership4k'):
            config=self.data.get('ownership',{})
            require(config.get('reviewed') is True,'Imported ownership needs reviewed UV-mesh binding')
            source=self.source('uvMesh','unwrap','mesh')
            require(config.get('sourceSha256')==pin(source)['sha256'],
                    'Imported ownership review must bind the exact UV mesh')
        if name=='field':
            review=self.data.get('approval',{}).get('appearanceField',{})
            geometry_role=next((role for role in ('uvMesh','repairedMesh','comfyExport','raw')
                                if role in self.data['inputs']),None)
            require(geometry_role is not None,'Generated field needs an active geometry input')
            # The approval binds the manifest's pinned geometry; bake does not read that mesh, so it is not re-hashed here.
            geometry=self.data['inputs'][geometry_role]
            field=self.data['inputs'][name]
            require(review.get('decision')=='approved' and isinstance(review.get('notes'),str)
                    and review['notes'].strip() and review.get('geometryInput')==geometry_role
                    and review.get('geometrySha256')==geometry['sha256']
                    and review.get('fieldSha256')==field['sha256'],
                    'Generated field approval must bind its exact bytes to the active geometry input: '+geometry_role)
        atlas_roles={'basecolor4k','metallic4k','runtimeColor','runtimeShades'}|set(self.data.get('render',{}).get('mapInputs',{}).values())
        if name in atlas_roles:
            review=self.data.get('approval',{}).get('textureMaps',{}).get(name,{})
            require(review.get('decision')=='approved' and bool(review.get('notes','').strip()),
                    'Imported texture needs explicit UV-mesh review: '+name)
            source=self.source('uvMesh','unwrap','mesh')
            require(review.get('sourceSha256')==pin(source)['sha256']
                    and review.get('textureSha256')==self.data['inputs'][name]['sha256'],
                    'Imported texture review must bind the exact UV mesh and texture: '+name)
        return asset(self.manifest_path,self.data['inputs'][name])['path']

    def result(self,stage,*,require_review=True,_checked=None):
        # Each top-level check starts a fresh hash memo; nested and sibling checks in one operation share it.
        if _checked is None:_checked={'results':{},'versions':{}};self._verified=set()
        if stage in _checked['results']:return _checked['results'][stage]
        row=self.state['stages'].get(stage);require(row is not None,'Stage not completed: '+stage)
        receipt=read(row['path']);self._verify([row]);self._verify(receipt['outputs'])
        if stage not in _checked['versions']:_checked['versions'][stage]=stage_source_version(stage)
        # Code, manifest and bindings first: a stage made stale by an edit is named as such, not as one of its code pins.
        require(receipt['codeVersion']==_checked['versions'][stage] and receipt['manifestHash']==self.manifest_digest(stage)
                and receipt['bindingsHash']==digest(self.bindings),'Stale stage; rerun with current input snapshot: '+stage)
        self._verify(receipt['inputs'])
        # The compiler a native receipt used is part of its identity: adding, removing or changing the local binding
        # (or the Blender/add-on files it pins) stales native only. Receipts without the key were client compiles.
        if stage=='native':require(receipt.get('compiler',[])==self.native_compiler(),'Stale stage; native compiler selection changed: native')
        require(receipt['state']=='complete','Failed stage: '+stage)
        if self.runtime is not None:require(receipt.get('runtimeIdentity')==self.runtime,'Stage runtime differs from active launcher')
        for dependency,expected in receipt.get('dependencies',{}).items():
            require(self.state['stages'].get(dependency)==expected,'Changed dependency; rerun stage: '+stage)
            self.result(dependency,_checked=_checked)
        if require_review:
            review_pin=self.state.get('reviews',{}).get(stage)
            require(review_pin is not None,'Visual review pending: '+stage)
            self._verify([review_pin]);review=read(review_pin['path'])
            require(review.get('stageReceipt')==row,'Stale visual review: '+stage)
            require(review.get('decision')=='approved','Visual review rejected: '+stage)
            _checked['results'][stage]=receipt['result']
        return receipt['result']

    def native_compiler(self):
        """Pins of the local Blender + Neverblender binding beside bindings.json and the files it consumes; [] selects the
        EE client compiler. It stays out of bindings.json, whose hash binds every stage."""
        from .native import MDL_COMPILER,mdl_compiler_files
        local=self.bindings_path.with_name(MDL_COMPILER)
        return mdl_compiler_files(local) if local.exists() else []

    def source(self,provided,stage,key):
        # Importing a reviewed artifact is explicit: it does not pretend its prior stages ran here.
        if provided in self.data['inputs']:return self.input(provided)
        row=self.result(stage)[key];self._verify([row]);return row['path']

    def dependencies(self,stage):
        """Reviewed upstream stages this manifest makes the stage consume."""
        require(stage in STAGES,'Unknown CPU stage')
        inputs=self.data['inputs']
        chained='raw' in inputs and 'comfyExport' not in inputs;staged=self._staged_fit()
        table={'prepare':[], 'precluster':[], 'fit':['precluster'] if chained else [],
            'repair':(['precluster'] if chained else [])+(['fit'] if staged else []),
            'unwrap':[] if 'repairedMesh' in inputs else ['repair'],
            'bake':[] if 'uvMesh' in inputs else ['unwrap'],
            'ownership':[] if 'uvMesh' in inputs else ['unwrap'],
            'tone':[] if 'basecolor4k' in inputs else ['bake'],
            'palette':[] if 'runtimeColor' in inputs else self._colour_stages() if self.tone_pass_through() else ['tone'],
            'export':([] if 'uvMesh' in inputs else ['unwrap'])+([] if 'runtimeShades' in inputs else ['palette'])+(['fit'] if staged else []),
            'native':['export'], 'render':([] if 'uvMesh' in inputs else ['unwrap'])+list(dict.fromkeys(self.data.get('render',{}).get('mapStages',{}).values()))
                +(['ownership'] if self.data.get('render',{}).get('ownershipView') else [])}
        self._texture_dependencies(stage,table);dependencies=table[stage]
        if stage=='tone' and not any(role in inputs for role in ('ownership1k','ownership4k')):dependencies.append('ownership')
        if stage=='palette' and 'ownership1k' not in inputs:dependencies.append('ownership')
        imported_atlases={'tone':('basecolor4k','ownership4k','ownership1k'),'palette':('runtimeColor','ownership1k'),
                          'export':('runtimeShades','ownership1k')}.get(stage,())
        if any(role in inputs for role in imported_atlases) and 'uvMesh' not in inputs and 'unwrap' not in dependencies:
            dependencies.append('unwrap')
        return dependencies

    def execute(self,stage):
        require(stage in STAGES,'Unknown CPU stage')
        # Package bytecode and installed modules must remain inside the frozen inventory.
        sys.dont_write_bytecode=True
        package_inputs=python_package_pins(self.bindings,require_imports=self.runtime is not None)
        if stage in self.state['stages']:
            try:return {'reused':True,'result':self.result(stage,require_review=False)}
            except (ValueError,OSError):pass
        parent=self.run/stage;parent.mkdir(exist_ok=True)
        old=list(parent.glob('attempt-*/receipt.json'))
        failures=[read(p) for p in old if read(p).get('manifestHash')==self.manifest_digest(stage)
                  and read(p).get('codeVersion')==stage_source_version(stage) and read(p).get('state')=='failed']
        require(len(failures)<2,'Two stage failures retained; fix the manifest or request a bounded exception before more trials')
        # The manifest is bound by the stage-scoped manifestHash, not by pinning the whole file.
        inputs=[pin(self.bindings_path)]+package_inputs+stage_code_pins(stage)
        for name in ('python','blender','client','embree'):
            if name in self.bindings:inputs.append(self.bindings[name])
        for name in ('toolchain','migrationReceipt'):
            if name in self.bindings:inputs.append(pin(self.bindings[name]))
        compiler=self.native_compiler() if stage=='native' else None
        if compiler:inputs+=compiler
        dependency_pins={};checked={'results':{},'versions':{}};self._verified=set()
        for dependency in self.dependencies(stage):
            self.result(dependency,_checked=checked);row=self.state['stages'][dependency]
            dependency_pins[dependency]=row
            previous=read(row['path']);inputs.append(row);inputs.extend(previous['outputs'])
            inputs.append(self.state['reviews'][dependency])
        folder=parent/f'attempt-{len(list(parent.glob("attempt-*")))+1:02d}';folder.mkdir()
        begun=time.monotonic();receipt={'stage':stage,'manifestHash':self.manifest_digest(stage),'bindingsHash':digest(self.bindings),
            'codeVersion':stage_source_version(stage),'inputs':inputs,'state':'running','outputs':[], 'dependencies':dependency_pins,'runtimeIdentity':self.runtime}
        if compiler is not None:receipt['compiler']=compiler
        write(folder/'intent.json',receipt,fresh=True)
        self._read=set();common.LIBRARIES_USED=set()
        try:
            result=self._execute(stage,folder);digest(result)
            undeclared=self._read-stage_roles(stage,self.data)
            require(not undeclared,'Stage read undeclared manifest inputs: '+', '.join(sorted(undeclared)))
            undeclared=common.LIBRARIES_USED-stage_libraries(stage,self.data)
            require(not undeclared,'Stage loaded undeclared libraries: '+', '.join(sorted(undeclared)))
            # Only what the stage read is pinned (and re-verified now, after execution).
            inputs+=[asset(self.manifest_path,self.data['inputs'][role]) for role in sorted(self._read)]
            for name in sorted(common.LIBRARIES_USED):inputs.extend(self.bindings['libraries'][name]['files'])
            python_package_pins(self.bindings,require_imports=self.runtime is not None)
            verify(inputs,fresh=True)
            receipt.update(state='complete',result=result,outputs=[pin(p) for p in sorted(folder.rglob('*')) if p.is_file() and p.name not in ('intent.json','receipt.json')])
        except Exception as exc:
            receipt.update(state='failed',error=str(exc),traceback=traceback.format_exc(),
                outputs=[pin(p) for p in sorted(folder.rglob('*')) if p.is_file() and p.name not in ('intent.json','receipt.json')])
            # A failed unwrap keeps its per-round repair log; one that cannot serialise is noted, never lost with the receipt.
            if hasattr(exc,'attempts'):
                try:digest(exc.attempts);receipt['attempts']=exc.attempts
                except (TypeError,ValueError):receipt['attempts']={'unserializable':repr(exc.attempts)[:4000]}
            raise
        finally:
            self._read=None;common.LIBRARIES_USED=None
            receipt['elapsedSeconds']=time.monotonic()-begun;write(folder/'receipt.json',receipt,fresh=True)
            self.state['stages'][stage]=pin(folder/'receipt.json');write(self.state_path,self.state)
        carried=self._carry_review(stage)
        return {'reused':False,'result':result,**({'carriedReview':carried} if carried else {})}

    def _carry_review(self,stage):
        """Carry the stage's latest review onto this attempt only when it approved an earlier attempt whose outputs are
        byte-identical (same relative paths and sha256) to this one's: the operator already judged exactly these bytes.
        Every runner stage is review-gated. Any added, missing or changed output, or a rejected or absent review, carries nothing."""
        old=self.state.get('reviews',{}).get(stage);row=self.state['stages'][stage]
        if old is None:return None
        def files(receipt,path):
            base=Path(path).parent;return {Path(p['path']).relative_to(base).as_posix():same_content(p) for p in receipt['outputs']}
        try:
            self._verify([old]);review=read(old['path']);bound=review.get('stageReceipt')
            if review.get('decision')!='approved' or not isinstance(bound,dict) or bound==row:return None
            self._verify([bound]);previous=read(bound['path']);current=read(row['path'])
            same=(previous.get('stage')==stage and previous.get('state')=='complete' and current.get('state')=='complete'
                  and current['outputs'] and files(previous,bound['path'])==files(current,row['path']))
        except (ValueError,OSError,KeyError):return None
        if not same:return None
        notes=(f"Carried from {Path(bound['path']).parent.name}: identical outputs (binary sha256; JSON equal apart from attempt "
               f"numbers and timings). {review['notes']}")
        return self._record_review(stage,{'stageReceipt':row,'decision':'approved','notes':notes,'productionAccepted':False,'carriedFrom':old})

    def _texture_dependencies(self,stage,dependencies):
        # Configured paint replaces the bake as colour source; rule ownership reads paint masks and the baked metallic.
        inputs=self.data['inputs'];baked=[] if 'basecolor4k' in inputs else ['bake']
        dependencies['paint']=baked+([] if 'uvMesh' in inputs else ['unwrap'])+(['repair'] if self._sealed() else [])
        if 'paint' in self.data and stage=='tone':dependencies['tone']=['paint']
        if stage=='ownership' and self.data.get('ownership',{}).get('mode')=='rules':
            dependencies['ownership']+=(['paint'] if 'paint' in self.data else [])+baked

    def tone_pass_through(self):
        """Tone without operations returns its input unchanged, so it is no stage: palette reads the colour itself and
        no review launch is spent on a byte copy. Imported 4K colour still goes through tone (it has no 1K map)."""
        tone=self.data.get('tone',{})
        return tone.get('mode')=='adjust' and not tone.get('operations') and 'basecolor4k' not in self.data['inputs']

    def _colour_stages(self):
        return ['paint'] if 'paint' in self.data else ['bake']

    def _staged_fit(self):
        return isinstance(self.data.get('fit'),dict) and self.data['fit'].get('matrixFrom')=='fit'

    def _fit(self):
        # A staged fit's matrix is the reviewed fit-stage proposal; its stage review is the fit review.
        fit=self.data.get('fit')
        if not self._staged_fit():return fit
        require('matrix' not in fit and 'reviewed' not in fit,'A staged fit takes its matrix and review from the fit stage only')
        return dict({k:v for k,v in fit.items() if k!='matrixFrom'},matrix=self.result('fit')['matrix'],reviewed=True)

    def _body_neck(self):
        # Only a neck cut reads the body's neck part (head-local), so other heads keep their repair inputs unchanged.
        return self.input('bodyNeck') if (((self.data.get('mesh') or {}).get('neck') or {}).get('cut')) else None

    def _sealed(self):
        # Paint can address the neck seal faces only when this run's repair produced the mesh.
        inputs=self.data['inputs']
        # A null mesh.neck is "no neck shaping" (neck.neck_policy), exactly like an absent one.
        return not {'uvMesh','repairedMesh'}&set(inputs) and bool(((self.data.get('mesh') or {}).get('neck') or {}).get('seal'))

    def _stage_color(self,stage):
        rows={'bake':lambda r:r['maps']['basecolor-4096.png'],'paint':lambda r:r['maps']['basecolor-4096.png'],
              'tone':lambda r:r['output'],'palette':lambda r:r['decoded']}
        require(stage in rows,'Render colour comes from bake, paint, tone or palette');return rows[stage](self.result(stage))['path']

    def _color4k(self,*,painted=True):
        if painted and 'paint' in self.data:return self.result('paint')['maps']['basecolor-4096.png']['path']
        return self.input('basecolor4k') if 'basecolor4k' in self.data['inputs'] else self.result('bake')['maps']['basecolor-4096.png']['path']

    def _execute(self,stage,folder):
        m=self.data;b=self.bindings
        if stage=='prepare':
            from .images import prepare,prepare_multiview
            require(m.get('approval',{}).get('referenceDesignReviewed') is True,'Review design and feature inventory before preparation')
            require(m.get('features') and all(row.get('placementReviewed') is True for row in m['features']),
                    'Explicitly review hair routing and all horn/tusk/cyberware counts and placement')
            if m.get('profile','pixal-single-v1')=='pixal-single-v1':
                if 'design' in m['inputs']:
                    # Bootstrap route: one front design image is both the geometry and the appearance condition.
                    from .images import matte
                    return matte(self.input('design'),m.get('matte',{}),folder/'images')
                return prepare(self.input('clay'),self.input('detail'),m['alignment'],folder/'images')
            pairs={view:(self.input(view+'Clay'),self.input(view+'Detail')) for view in ('front','left','back','right')}
            return prepare_multiview(pairs,m['alignment'],folder/'images')
        if stage=='precluster':
            from .mesh import precluster
            return precluster(self.input('raw'),folder/'oriented.glb',b)
        if stage=='fit':
            from .fit import propose
            require(self._staged_fit(),'The fit stage needs fit.matrixFrom: fit')
            source=self.input('comfyExport') if 'comfyExport' in m['inputs'] else self.result('precluster')['output']['path']
            return propose(source,self.input('fitReference'),folder/'fit',exclude_lower=m['fit'].get('excludeLower',.25),align=m['fit'].get('align','profile'))
        if stage=='repair':
            from .neck import repair
            if 'raw' not in m['inputs'] or 'comfyExport' in m['inputs']:
                return repair(self.input('comfyExport'),folder/'final.glb',b,m['mesh'],read(self.input('shellInspection')),fit=self._fit(),body=self._body_neck())
            # Chained route: the reviewed precluster output of this run, with the shell inspection declared inline
            # and bound here to that exact output (no hardlinked copy or second manifest edit).
            inspection=m['mesh'].get('shellInspection')
            require(isinstance(inspection,dict) and 'sourceSha256' not in inspection and 'shellInspection' not in m['inputs'],
                    "Chained repair needs an inline mesh.shellInspection without sourceSha256")
            source=self.result('precluster')['output'];self._verify([source])
            return repair(source['path'],folder/'final.glb',b,m['mesh'],dict(inspection,sourceSha256=source['sha256']),fit=self._fit(),body=self._body_neck())
        if stage=='unwrap':
            from .gltf import mesh,write_mesh
            from .uv import unwrap,raster_audit,audit_imported_uvs
            source=self.source('repairedMesh','repair','source')
            value=mesh(source);original=value['positions'][value['faces']].copy();normals=value['normals']
            subtexel=m['mesh'].get('maximumSubtexelFraction',.005)
            if m['mesh'].get('reuseReviewedUvs',False):
                result=audit_imported_uvs(value,subtexel,m['mesh'].get('uv',{}))
            else:
                value,result=unwrap(value,b,dict(m.get('mesh',{}).get('uv',{}),maximumSubtexelFraction=subtexel))
                audit,_=raster_audit(value['uv'],4096);require(not audit['overlapFaces'] and not audit['degenerateUvFaces'] and not audit['unmappedUvFaces'],'4K UV audit failed')
                result['source4kAudit']=audit
            require(np.array_equal(original,value['positions'][value['faces']]),'UV processing changed ordered triangle corners')
            path=folder/'uv.glb';write_mesh(path,value['positions'],value['faces'],value['uv'],normals)
            result['mesh']=pin(path);return result
        if stage=='bake':
            from .textures import bake
            source=self.source('uvMesh','unwrap','mesh')
            return bake(source,self.input('field'),folder/'maps',allow_decoder_overshoot=m['mesh'].get('allowDecoderOvershoot',False),
                        max_subtexel_fraction=m['mesh'].get('maximumSubtexelFraction',.005))
        if stage=='paint':
            require('paint' in m,'Stage not configured: the manifest has no paint section')
            from .paint import paint
            seal=None
            if self._sealed():seal=self.result('repair')['neck']['seal']['shellTriangles']
            return paint(self.source('uvMesh','unwrap','mesh'),self._color4k(painted=False),m['paint'],folder/'maps',seal_start=seal)
        if stage=='ownership':
            from .palette import project_ownership
            source=self.source('uvMesh','unwrap','mesh');config=m['ownership'];report={}
            # Rules are bbox-relative data, not a mesh-bound annotation; the stage review binds their exact output.
            require(config.get('reviewed') is True and (config.get('mode')=='rules' or config.get('sourceSha256')==pin(source)['sha256']),
                    'Ownership review must bind the exact UV mesh')
            if config['mode']=='rules':
                from .paint import rule_ownership,PREVIEW
                masks={name:row['path'] for name,row in self.result('paint')['masks'].items()} if 'paint' in m else {}
                metallic=self.input('metallic4k') if 'metallic4k' in m['inputs'] else None if 'basecolor4k' in m['inputs'] else self.result('bake')['maps']['metallic-4096.png']['path']
                labels,report=rule_ownership(source,self._color4k(),config,metallic=metallic,masks=masks)
                require(labels.shape==(4096,4096),'4K discrete ownership atlas required');image=Image.fromarray(labels)
                Image.fromarray(PREVIEW[labels]).resize((1024,1024),Image.Resampling.NEAREST).save(folder/'ownership-preview-1024.png')
            elif config['mode']=='atlas':
                image=Image.open(self.input('ownership4k'));require(image.mode=='L' and image.size==(4096,4096),'4K discrete ownership atlas required')
            else:
                require(config['mode']=='project','Unsupported ownership mode')
                views=[dict(row,mask=self.input(row['maskInput'])) for row in config['views']]
                project_ownership(source,views,b['embree'],folder/'projected.png',max_subtexel_fraction=m['mesh'].get('maximumSubtexelFraction',.005))
                image=Image.open(folder/'projected.png').resize((4096,4096),Image.Resampling.NEAREST)
            require(np.max(np.asarray(image))<=9,'Unknown ownership must be resolved before proceeding')
            image.save(folder/'ownership-4096.png');image.resize((1024,1024),Image.Resampling.NEAREST).save(folder/'ownership-1024.png')
            return {'fourk':pin(folder/'ownership-4096.png'),'onek':pin(folder/'ownership-1024.png'),'channelIdsNeverBlended':True,'visualReviewRequired':True,**report}
        if stage=='tone':
            from .textures import tone_match
            color=self._color4k()
            if 'ownership4k' in m['inputs']:
                ownership=self.input('ownership4k');ownership_source=ownership;ownership_role='ownership4k';upsampling=None
            elif 'ownership1k' in m['inputs']:
                ownership_source=self.input('ownership1k');ownership_role='ownership1k';upsampling='nearest'
                with Image.open(ownership_source) as mask:
                    require(mask.mode=='L' and mask.size==(1024,1024),
                            'Imported ownership1k must be an actual 1024x1024 eight-bit L image')
                    labels=np.asarray(mask)
                    require(np.max(labels)<=9,'Unknown ownership must be resolved before tone matching')
                    ownership=folder/'ownership-4096-nearest.png'
                    mask.resize((4096,4096),Image.Resampling.NEAREST).save(ownership)
            else:
                ownership=self.result('ownership')['fourk']['path'];ownership_source=ownership
                ownership_role='ownership';upsampling=None
            for path in (color,ownership):
                with Image.open(path) as image:
                    require(image.size==(4096,4096),'Tone inputs must be actual 4096x4096 images')
                    if path==ownership:
                        require(image.mode=='L','Tone ownership must be an eight-bit L image')
                        require(np.max(np.asarray(image))<=9,'Unknown ownership must be resolved before tone matching')
            output=folder/'tone-4096.png'
            if m['tone'].get('mode')=='adjust':
                # Reference-free per-channel adjustment; no operations is an explicit reviewed pass-through.
                from .paint import adjust
                keys={op['palette'] for op in m['tone'].get('operations',[]) if 'palette' in op}
                result=adjust(color,ownership,m['tone'],{key:self.input(m['palette']['inputs'][key]) for key in keys},output)
            else:result=tone_match(color,ownership,self.input('detail' if m.get('profile','pixal-single-v1')=='pixal-single-v1' else 'frontDetail'),m['tone'],output)
            result.update(ownershipInputRole=ownership_role,ownershipSource=pin(ownership_source),
                          ownershipForTone=pin(ownership),ownershipUpsampling=upsampling)
            image=Image.open(output)
            require(image.size==(4096,4096),'Tone output must be actual 4096x4096 before deriving review maps')
            result['maps']={}
            for size in (2048,1024):
                path=folder/f'tone-{size}.png';image.resize((size,size),Image.Resampling.BOX).save(path);result['maps'][str(size)]=pin(path)
            return result
        if stage=='palette':
            from .palette import quantize,rank_rows
            if 'runtimeColor' in m['inputs']:color=self.input('runtimeColor')
            elif self.tone_pass_through():color=self.result(self._colour_stages()[0])['maps']['basecolor-1024.png']['path']
            else:color=self.result('tone')['maps']['1024']['path']
            palettes={layer:self.input(name) for layer,name in m['palette']['inputs'].items()}
            ownership=self.input('ownership1k') if 'ownership1k' in m['inputs'] else self.result('ownership')['onek']['path']
            rows=m['palette']['rows'];rows={key:'auto' for key in palettes} if rows=='auto' else dict(rows);ranking=None
            tone=m['palette'].get('toneMatch') or {};ranked=[key for key,row in rows.items() if row=='auto' and key in palettes and key not in tone]
            if ranked:
                # Exact fast ranking picks the lowest-error stock row; the full top list stays in the receipt for review.
                # Tone-matched channels keep 'auto': quantize picks their row after matching, from the matched shades.
                ranking=rank_rows(color,ownership,{key:palettes[key] for key in ranked})
                rows.update({key:row['row'] for key,row in ranking.items()});write(folder/'row-ranking.json',ranking,fresh=True)
            result=quantize(color,ownership,palettes,rows,folder/'palette',shade_offsets=m['palette'].get('shadeOffsets'),
                            tone_match=m['palette'].get('toneMatch'))
            if ranking is not None:result['rowRanking']=ranking
            return result
        if stage=='export':
            from .native import prepare
            source=self.source('uvMesh','unwrap','mesh')
            shades=self.input('runtimeShades') if 'runtimeShades' in m['inputs'] else self.result('palette')['shades']['path']
            layers=self.input('ownership1k') if 'runtimeShades' in m['inputs'] else self.result('palette')['ownership']['path']
            require(m['fit'].get('model') is not None,'Choose a reserved model slot before native export')
            geometry_audit=None
            if 'uvMesh' in m['inputs'] or 'repairedMesh' in m['inputs']:
                from .mesh import audit
                audit_result=audit(source)
                audit_path=folder/'imported-mesh-audit.json'
                write(audit_path,audit_result,fresh=True)
                require(audit_result.get('passed') is True,
                        'Imported mesh failed topology/collision audit; retain the failed audit evidence')
                geometry_audit=pin(audit_path)
            uv_audit=None
            if 'uvMesh' in m['inputs']:
                from .gltf import mesh
                from .uv import audit_imported_uvs
                uv_result=audit_imported_uvs(mesh(source),m.get('mesh',{}).get('maximumSubtexelFraction',.005),m.get('mesh',{}).get('uv',{}))
                uv_path=folder/'imported-uv-audit.json';write(uv_path,uv_result,fresh=True)
                uv_audit=pin(uv_path)
            fit=self._fit();bound=False
            if fit.get('sourceStage')=='unwrap':
                # A reviewed matrix fit chosen before UVs exist binds to this run's reviewed unwrap output, never to an
                # imported mesh; the manifest cannot carry that hash without invalidating every earlier receipt.
                require('uvMesh' not in m['inputs'] and 'sourceSha256' not in fit,"sourceStage binding is only for this run's own unwrap")
                fit=dict(fit,sourceSha256=pin(source)['sha256']);bound=True
            result=prepare(source,shades,layers,fit,fit['model'],folder/'converted')
            if bound:result['fitBinding']={'sourceStage':'unwrap','unwrapReceipt':self.state['stages']['unwrap']}
            if self._staged_fit():result['fitStage']={'receipt':self.state['stages']['fit'],'matrix':fit['matrix']}
            if uv_audit is not None:result['uvAudit']=uv_audit
            if geometry_audit is not None:result['geometryAudit']=geometry_audit
            return result
        if stage=='native':
            from .native import compile_and_package,mdl_compiler,MDL_COMPILER
            # Blender + Neverblender when the head has its local compiler binding, else the EE client's compilemodel.
            local=self.bindings_path.with_name(MDL_COMPILER);mdl=mdl_compiler(local) if local.exists() else None
            # A `batch` launch compiles every head's export in one Blender run first (native.precompile) and hands each
            # runner its folder; the reused binary still passes this head's own decode audit.
            previous=self.result('export');prepared=Path(previous['ascii']['path']).parents[1]
            cache=getattr(self,'precompiled',{}).get(str(prepared.resolve())) if mdl else None
            return compile_and_package(prepared,b['client'],folder/'native',mdl,cache=cache)
        if stage=='render':
            require('render' in m,'Stage not configured: the manifest has no render section')
            import subprocess,sys
            from .common import ROOT
            from .review_images import resolutions,atlas_sets,sheets,render_plan,validate_frames
            begun=time.monotonic()
            source=self.source('uvMesh','unwrap','mesh');cfg=dict(m['render']);views=cfg.pop('views',None)
            if 'cameras' not in cfg:
                from .cameras import review_cameras
                from .gltf import mesh
                cfg['cameras']=review_cameras(mesh(source)['positions'],cfg['frontAngleDegrees'])
            if views is not None:
                named={row['name']:row for row in cfg['cameras']};require(views and set(views)<=set(named),'Unknown review view')
                cfg['cameras']=[named[name] for name in views]
            maps={name:self.input(role) for name,role in cfg.get('mapInputs',{}).items()}
            # Pre-native review: the run's own colour (bake, paint, tone or the quantized palette) and channel ownership.
            for name,stage_name in cfg.pop('mapStages',{}).items():
                require(name=='basecolor' and name not in maps,'mapStages supplies basecolor only, once');maps[name]=self._stage_color(stage_name)
            if cfg.pop('ownershipView',False):
                from .paint import PREVIEW
                labels=np.asarray(Image.open(self.result('ownership')['onek']['path']));path=folder/'ownership-preview-1024.png'
                Image.fromarray(PREVIEW[labels]).save(path);maps['ownership']=str(path)
            cfg.update(mesh=source,output=str(folder/'renders'),maps=maps)
            require('ownership' not in cfg.get('modes',[]) or 'ownership' in maps,'Ownership render mode needs ownershipView')
            render_plan(cfg)
            texture_sets,atlases=atlas_sets(cfg,folder/'renders',resolutions(cfg))
            cfg.update(textureSets={str(size):maps for size,maps in texture_sets.items()},atlases=atlases)
            cfg['inputs']=[pin(source),*[pin(p) for p in cfg['maps'].values()],*[row['image'] for row in atlases],*stage_file_pins('render')]
            write(folder/'render-config.json',cfg,fresh=True)
            write(folder/'render-inputs.json',cfg['inputs']+[pin(folder/'render-config.json')],fresh=True)
            command=[sys.executable,str(ROOT/'tools/phenotypes/launch_shared_tool.py'),'--toolchain',b['toolchain'],
                '--migration-receipt',b['migrationReceipt'],'--tool','blender','--output',str(folder/'blender-launch')]
            command+=['--input-manifest',str(folder/'render-inputs.json')]
            command+=['--','--python',str(Path(__file__).parent/'blender_render.py'),'--','--config',str(folder/'render-config.json')]
            execution=subprocess.run(command,capture_output=True,text=True,timeout=1800,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            (folder/'blender.log').write_text(execution.stdout+'\n'+execution.stderr);require(execution.returncode==0,'CPU render failed; inspect log')
            result=read(folder/'renders'/'renders.json');validate_frames(cfg,result['views'])
            result.update(sheets(result['views'],folder/'renders',result['triangles']),elapsedWithEvidenceSeconds=time.monotonic()-begun)
            write(folder/'renders'/'renders.json',result);return result
        raise ValueError('Stage not implemented')

    def review(self,stage,decision,notes):
        require(decision in ('approved','rejected') and notes.strip(),'Explicit visual decision and notes required')
        self.result(stage,require_review=False)
        return self._record_review(stage,{'stageReceipt':self.state['stages'][stage],'decision':decision,'notes':notes,'productionAccepted':False})

    def _record_review(self,stage,result):
        target=self.run/'reviews'/f'{stage}-{uuid.uuid4().hex}.json';write(target,result,fresh=True);review_pin=pin(target)
        self.state.setdefault('reviews',{})[stage]=review_pin;write(self.state_path,self.state)
        return review_pin

    def status(self):
        result={}
        for stage in STAGES:
            if stage not in self.state['stages']:result[stage]='not-run';continue
            try:
                self.result(stage,require_review=False)
                review_pin=self.state.get('reviews',{}).get(stage)
                if review_pin:
                    verify([review_pin]);review=read(review_pin['path'])
                    require(review.get('stageReceipt')==self.state['stages'][stage],'Stale visual review: '+stage)
                    decision=review['decision']
                else:decision='pending'
                result[stage]={'state':'complete','review':decision}
            except (ValueError,OSError) as exc:result[stage]={'staleOrFailed':str(exc)}
        return {'id':self.data['id'],'stages':result,'next':'Explicitly choose the next stage; no GPU job is started by status/resume'}
