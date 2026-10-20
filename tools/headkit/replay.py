"""Read-only replay of accepted head inputs, with honest imported-stage provenance."""
from pathlib import Path
import numpy as np
from PIL import Image
from .common import verify,pin,write,require
from .gltf import mesh
from .mesh import topology
from .native import prepare,audit_native,helpers


def replay(config, output):
    """Validate existing reviewed artifacts; this never samples, repairs or recompiles."""
    verify(config['inputs']);output=Path(output);output.mkdir(parents=True,exist_ok=False)
    source=config['source'];value=mesh(source)
    report=topology(value['positions'],value['faces'])
    require(report['triangles']<=20000 and report['closed'],'Reviewed source no longer meets closed 20K profile')
    prepared=prepare(source,config['shades'],config['layers'],config['fit'],config['model'],output/'export')
    require(Path(prepared['plt']['path']).read_bytes()==Path(config['expectedPlt']).read_bytes(),'Imported layer/shade roundtrip changed PLT')
    sanitized,audit=audit_native(config['binary'],config['model'],prepared['expected']['path'])
    target=output/(config['model']+'.mdl');target.write_bytes(sanitized)
    result={'id':config['id'],'source':pin(source),'topology':report,'nativeAudit':audit,'sanitized':pin(target),
            'plt':prepared['plt'],'importedReviewedInputs':True,'generationPerformed':False,'repairPerformed':False,
            'colorOrOwnershipRecomputed':False,'clientValidationReusedAsHistoricalEvidenceOnly':True}
    verify(config['inputs']);write(output/'replay.json',result,fresh=True);return result
