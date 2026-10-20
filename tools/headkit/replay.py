"""Read-only replay of accepted head inputs, with honest imported-stage provenance."""
from pathlib import Path
from .common import verify,pin,write,require
from .gltf import mesh
from .mesh import topology
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
    source=consumed['source']['path'];value=mesh(source)
    report=topology(value['positions'],value['faces'])
    require(report['triangles']<=20000 and report['closed'],'Reviewed source no longer meets closed 20K profile')
    prepared=prepare(source,consumed['shades']['path'],consumed['layers']['path'],config['fit'],config['model'],output/'export')
    require(Path(prepared['plt']['path']).read_bytes()==Path(consumed['expectedPlt']['path']).read_bytes(),'Imported layer/shade roundtrip changed PLT')
    sanitized,audit=audit_native(consumed['binary']['path'],config['model'],prepared['expected']['path'])
    target=output/(config['model']+'.mdl');target.write_bytes(sanitized)
    result={'id':config['id'],'consumedInputs':consumed,'source':consumed['source'],'topology':report,'nativeAudit':audit,'sanitized':pin(target),
            'plt':prepared['plt'],'importedReviewedInputs':True,'generationPerformed':False,'repairPerformed':False,
            'colorOrOwnershipRecomputed':False,'clientValidationReusedAsHistoricalEvidenceOnly':True}
    verify(pins.values());write(output/'replay.json',result,fresh=True);return result
