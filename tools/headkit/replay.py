"""Read-only replay of accepted head inputs, with honest imported-stage provenance."""
from pathlib import Path
from .common import verify,pin,write,require
from .mesh import audit
from .gltf import mesh
from .uv import audit_imported_uvs
from .native import prepare,audit_native


def replay(config, output):
    """Validate existing reviewed artifacts; this never samples, repairs or recompiles."""
    pins={}
    for row in config['inputs']:
        require(isinstance(row,dict) and set(row)>={'path','sha256'},'Expected replay input pin')
        path=Path(row['path']).resolve()
        require(path not in pins or pins[path]['sha256']==row['sha256'],'Conflicting replay input pins')
        pins[path]={'path':str(path),'sha256':row['sha256']}
    consumed={}
    for role in ('source','shades','layers','binary','expectedPlt'):
        path=Path(config[role]).resolve()
        require(path in pins,'Missing replay input pin: '+role)
        consumed[role]=pins[path]
    verify(pins.values());output=Path(output);output.mkdir(parents=True,exist_ok=False)
    source=consumed['source']['path'];geometry=audit(source)
    audit_path=output/'geometry-audit.json';write(audit_path,geometry,fresh=True)
    require(geometry.get('passed') is True,'Replay mesh failed topology/collision audit; retain the failed audit evidence')
    report=geometry['topology']
    require(report['triangles']<=20000,'Reviewed source no longer meets closed 20K profile')
    uv_result=audit_imported_uvs(mesh(source));uv_path=output/'uv-audit.json';write(uv_path,uv_result,fresh=True)
    prepared=prepare(source,consumed['shades']['path'],consumed['layers']['path'],config['fit'],config['model'],output/'export')
    require(Path(prepared['plt']['path']).read_bytes()==Path(consumed['expectedPlt']['path']).read_bytes(),'Imported layer/shade roundtrip changed PLT')
    sanitized,native_audit=audit_native(consumed['binary']['path'],config['model'],prepared['expected']['path'])
    target=output/(config['model']+'.mdl');target.write_bytes(sanitized)
    result={'id':config['id'],'consumedInputs':consumed,'source':consumed['source'],'topology':report,'geometryAudit':pin(audit_path),'uvAudit':pin(uv_path),'nativeAudit':native_audit,'sanitized':pin(target),
            'plt':prepared['plt'],'importedReviewedInputs':True,'generationPerformed':False,'repairPerformed':False,
            'colorOrOwnershipRecomputed':False,'clientValidationReusedAsHistoricalEvidenceOnly':True}
    verify(pins.values());write(output/'replay.json',result,fresh=True);return result
