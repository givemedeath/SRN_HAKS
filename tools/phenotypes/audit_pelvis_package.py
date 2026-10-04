"""Verify actual packed pelvis fixture bytes, ownership and stock male actors."""
import argparse, hashlib, json, re, struct, subprocess
from collections import Counter
from pathlib import Path


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition,message):
    if not condition:raise RuntimeError(message)


def archive(path):
    data=Path(path).read_bytes()
    require(len(data)>=160 and data[:4] in (b'HAK ',b'MOD '),'Invalid fixture archive')
    count=struct.unpack_from('<I',data,16)[0]
    keys,resources=struct.unpack_from('<II',data,24)
    require(keys+24*count<=len(data) and resources+8*count<=len(data),'Invalid archive table bounds')
    rows=[]
    for index in range(count):
        name,rid,kind=struct.unpack_from('<16sIH',data,keys+24*index)
        require(rid<count,'Invalid archive resource ID')
        offset,size=struct.unpack_from('<II',data,resources+8*rid)
        require(offset+size<=len(data),'Invalid archive payload bounds')
        rows.append((name.split(b'\0')[0].decode('ascii'),kind,data[offset:offset+size]))
    require(len({(n,k) for n,k,_ in rows})==len(rows),'Duplicate packed resref/type')
    return rows


def run(args):
    stage=args.stage.resolve();receipt=stage/'test-module/receipt.json'
    build=json.loads(receipt.read_text());hak=Path(build['hak']);module=Path(build['module'])
    require(sha(hak)==build['hakSha256'] and sha(module)==build['moduleSha256'],'Package changed since build')
    packed=archive(hak);models={n:b for n,k,b in packed if k==2002}
    staging=stage/'test-module/hak-resources'
    expected=Counter((p.stem,sha(p)) for p in staging.iterdir() if p.is_file())
    actual=Counter((n,hashlib.sha256(b).hexdigest()) for n,k,b in packed)
    require(actual==expected,'Packed payloads differ from allowlisted staging')
    human={n for n in models if n.startswith('pmh')}
    require(human=={'pmh0_chest001','pmh0_pelvis001'},'Unexpected Human model ownership')
    require(not any(n.startswith(('pf','a_')) for n,k,b in packed),'Female or animation overrides packed')
    frozen=args.frozen_torso.resolve()
    resources=stage/'human_male_fit/converted/resources'
    protected=['pmh0_chest001.mdl','pmh0_chest001.mtr','pmh0_chest001.plt','pmh0_chest001n.tga']
    protected_hashes={n:sha(frozen/n) for n in protected}
    for n,digest in protected_hashes.items():
        require(sha(resources/n)==digest,'Frozen torso dependency changed: '+n)
        require((Path(n).stem,digest) in actual,'Frozen torso payload missing: '+n)
    bank=args.stock_bank.resolve();appearance=next(b.decode('cp1252') for n,k,b in packed if n=='appearance')
    original=(bank/'raw/appearance.2da').read_text(encoding='cp1252')
    def row(text):return next(line.split()[1:] for line in text.splitlines() if re.match(r'^\s*6\s',line))
    require(row(appearance)==row(original),'Stock Human appearance row changed')
    override=stage/'userdir/override';require(override.is_dir() and not list(override.iterdir()),'Stale override resources')
    source=stage/'human_male_fit/converted/ascii/pmh0_pelvis001.mdl';text=source.read_text()
    require(not re.search(r'(?mi)^newanim\s',text),'Pelvis defines animations')
    require(re.search(r'(?mi)^setsupermodel\s+pmh0_pelvis001\s+NULL',text),'Unexpected pelvis supermodel')
    native=stage/'human_male_fit/converted/native-compile.json';compile_receipt=json.loads(native.read_text())
    entry=next(r for r in compile_receipt['models'] if r['name']==source.name)
    require(sha(source)==entry['sourceSha256'] and hashlib.sha256(models[source.stem]).hexdigest()==entry['binarySha256'],'Packed pelvis differs from actual compile')
    args.output.mkdir(parents=True,exist_ok=False)
    floor=next(b for n,k,b in archive(module) if n=='sr_pt_floor' and b[:4]==b'GIT ')
    git=args.output/'packed-floor.git';git.write_bytes(floor)
    actors_path=args.output/'packed-floor.json'
    subprocess.run([str(args.tool_directory/'nwn_gff.exe'),'-i',str(git),'-o',str(actors_path),'-p'],capture_output=True,check=True)
    actors=json.loads(actors_path.read_text())['Creature List']['value']
    actor_rows=[{k:a[field]['value'] for k,field in [('gender','Gender'),('phenotype','Phenotype'),('appearance','Appearance_Type')]} for a in actors]
    require(actor_rows and all(a['gender']==0 and a['phenotype']==0 and a['appearance'] in (6,15100) for a in actor_rows),'Unexpected fixture actor rig selection')
    report={'hakSha256':sha(hak),'moduleSha256':sha(module),'buildReceiptSha256':sha(receipt),
        'payloads':len(packed),'exactStagedPayloads':True,'humanReplacementModels':sorted(human),
        'frozenTorsoResourceHashes':protected_hashes,'stockHumanAppearanceRowExact':True,
        'packedActors':actor_rows,'overrideEmpty':True,'rootOrAnimationOverrides':[],
        'pelvisCompileReceiptSha256':sha(native),'skinColor':build['configuration'].get('skinColor',3),
        'cameraLocked':build['configuration']['cameraLock'],'scriptSha256':sha(__file__),
        'limitation':'Actual packed-resource integrity. Visual motion, palette, equipment and performance need separate client evidence.'}
    (args.output/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ['stage','stock-bank','frozen-torso','tool-directory','output']:ap.add_argument('--'+name,type=Path,required=True)
    run(ap.parse_args())


if __name__=='__main__':main()
