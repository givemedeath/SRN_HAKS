"""Verify collision namespaces from small indexes, retaining selected resource bytes."""
from pathlib import Path
import struct
from tools.headkit.common import asset, read, require, verify

TYPES={3:'tga',2002:'mdl',2009:'nss',2017:'2da',2022:'txi',2025:'uti',2033:'dds',2072:'mtr'}


def key_names(path):
    data=Path(path).read_bytes()
    require(len(data)>=64 and data[:8]==b'KEY V1  ','Invalid native KEY index')
    count,offset=struct.unpack_from('<I',data,12)[0],struct.unpack_from('<I',data,20)[0]
    require(offset>=64 and offset+22*count<=len(data),'Native KEY table escapes its file')
    result=set()
    for i in range(count):
        name,kind,_=struct.unpack_from('<16sHI',data,offset+22*i)
        if kind in TYPES:
            name=name.split(b'\0')[0].decode('ascii').lower()+'.'+TYPES[kind]
            require(name==Path(name).name,'Native KEY resource contains a path')
            result.add(name)
    return result


def namespace(stack_path,layer):
    """Return occupied names, selected extraction hashes and actual consumed pins."""
    if 'nameInventory' not in layer:return set(),None,[]
    row=asset(stack_path,layer['nameInventory']);path=row['path'];data=read(path);pins=[row]
    require(data.get('complete') is True,'Incomplete native collision namespace')
    if data.get('kind')=='nwn-key-namespace-v1':
        require(data.get('scope')=='installed-stock-en-no-overrides','Unsupported native index scope')
        local=[asset(path,r) for r in data['keys']];origins=data['originKeys']
        require(local and len(local)==len(origins) and all(a['sha256']==b['sha256'] for a,b in zip(local,origins)),
                'Copied KEY indexes differ from their bound installation')
        current=sorted(str(p.resolve()) for directory in data['keyDirectories'] for p in Path(directory).glob('*.key'))
        require(current==sorted(str(Path(r['path']).resolve()) for r in origins),'Installed KEY membership changed')
        archives=data['sourceArchives'];require(archives and all(Path(r['path']).suffix.lower()=='.bif' for r in archives),
                                                   'Bind the selected source archives')
        verify(origins+archives);pins+=local+origins+archives
        proof_pin=asset(path,data['extractionProof']);launch_pin=asset(path,data['extractionLaunch'])
        proof=read(proof_pin['path']);launch=read(launch_pin['path']);pins += [proof_pin,launch_pin]
        require(proof.get('kind')=='verified-stock-native-extraction' and proof.get('noOverrides') is True
                and launch.get('exitCode')==0 and launch.get('inputsUnchanged') is True,'Qualified stock extraction required')
        frozen=launch['frozenInputs']
        require(all(frozen.get(str(Path(r['path']).resolve()))==r['sha256'] for r in origins+archives),
                'Extraction did not consume the bound indexes and source archives')
        names=set().union(*(key_names(r['path']) for r in local))
        selected={r['resource'].lower():r['file']['sha256'] for r in proof['resources']}
        require(set(selected)<=names,'Extracted resource missing from the native index')
        return names,selected,pins
    require(data.get('kind')=='published-human-namespace-v1','Unknown native namespace proof')
    names=set();genders=set()
    for source in data['manifests']:
        bound=asset(path,source);pins.append(bound);published=read(bound['path'])
        require(published.get('kind')=='published-validated-target-body' and published.get('productionAccepted') is True
                and published.get('pack')=='srn_body','Approved shipped Human resource manifest required')
        require(published.get('gender') in ('male','female'),'Unsupported fixture body namespace')
        genders.add(published['gender']);rows=published['resources']
        prefix={'male':'pmh0','female':'pfh0'}[published['gender']]
        require(published.get('prefix')==prefix and all(Path(r['path']).name.lower().startswith(prefix) for r in rows),
                'Published Human namespace contains unrelated resources')
        require(len(rows)==published['resourceCount'],'Incomplete published resource namespace')
        own={Path(r['path']).name.lower() for r in rows}
        require(len(own)==len(rows) and not names&own,'Duplicate published body resource names')
        names|=own
    require(genders=={'male','female'},'Both shipped Human namespaces required')
    return names,None,pins
