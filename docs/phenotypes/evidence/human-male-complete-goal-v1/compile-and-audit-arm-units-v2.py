import json
from pathlib import Path
import subprocess
import sys
root=Path(__file__).resolve().parent
helpers=root.parents[2]/'tools/phenotypes'
client=Path('C:/Program Files (x86)/GOG Galaxy/Games/Neverwinter Nights Enhanced Edition/bin/win32/nwmain.exe')
records=[]
for part in ('bicepl','bicepr','forel','forer'):
    stage=root/(part+'-native-v2'); converted=stage/'human_male_fit/converted'
    command=[sys.executable,str(helpers/'native_compile.py'),'--client',str(client),
             '--converted',str(converted),'--user-directory',str(root/(part+'-compile-userdir-v2')),
             '--timeout','180','--with-material-resources']
    if part=='bicepl':command+=['--reuse-from',str(root/'bicepl-native-v1/human_male_fit/converted')]
    subprocess.run(command,check=True)
    audit=root/(part+'-native-audit-v2')
    subprocess.run([sys.executable,str(helpers/'audit_native_limb_shading.py'),
        '--converted',str(converted),'--config',str(stage/'config.json'),
        '--effective-native-preparation',str(stage/'native-unit-preparation.json'),
        '--native-uv-max-ulps','1','--output',str(audit)],check=True)
    records.append({'part':part,'native':str(converted/'native-compile.json'),
                    'audit':str(audit/'audit.json')})
print(json.dumps({'parts':records,'interactiveClientLaunched':False}),flush=True)
