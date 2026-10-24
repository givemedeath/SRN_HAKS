"""Controlled Comfy startup. Execute this file with the pinned Python using -I -B.

Trusted reviewed plugins are supported; hot reload and attaching an unmanaged
server are unsupported. This is deployment provenance, not a Python sandbox.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import socket
import sys
import tempfile
import types
from urllib.parse import urlsplit
import uuid

def _bootstrap_snapshot():
    # A package shell supplies relative imports without running the GPU adapter.
    # An empty cache prefix prevents stale bytecode before deployment verification.
    import importlib
    package=types.ModuleType('_headkit_bootstrap')
    package.__path__=[str(Path(__file__).resolve().parent)]
    sys.modules[package.__name__]=package
    old_cache=sys.pycache_prefix
    try:
        with tempfile.TemporaryDirectory(prefix='headkit-bootstrap-') as cache:
            sys.pycache_prefix=cache
            return importlib.import_module(package.__name__+'.source_snapshot')
    finally:
        sys.pycache_prefix=old_cache


if __package__:
    from .source_snapshot import capture_inventory,load_inventory,same_inventory,_sha256,require
else:
    snapshot=_bootstrap_snapshot()
    capture_inventory,load_inventory,same_inventory,_sha256,require=(
        getattr(snapshot,name) for name in ('capture_inventory','load_inventory','same_inventory','_sha256','require'))

SESSION_MODULE='_srn_headkit_session'
_STARTED=[]


def pin(path):
    path=Path(path).resolve(strict=True)
    return {'path':str(path),'sha256':_sha256(path)}


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def runtime_inventory(roots):
    def fail_walk(error):raise error
    paths=set();resolved=[Path(root).resolve(strict=True) for root in roots]
    require(resolved and len(set(resolved))==len(resolved),'Unique runtime roots required')
    for root in resolved:
        require(root.is_dir(),'Runtime root must be a directory')
        for current,dirs,files in os.walk(root,followlinks=False,onerror=fail_walk):
            current=Path(current);dirs[:]=[name for name in dirs if name not in ('__pycache__','.git')]
            for name in dirs+files:
                path=current/name
                require(not path.is_symlink() and not getattr(os.path,'isjunction',lambda value:False)(path)
                        and path.resolve(strict=True)==path.absolute(),'Linked runtime files are unsupported')
            paths.update((current/name).resolve(strict=True) for name in files)
    return [pin(path) for path in sorted(paths,key=lambda value:str(value).casefold())]


def launch_arguments(config):
    launch=config['launch'];url=urlsplit(launch['endpoint'])
    require(url.scheme=='http' and url.hostname=='127.0.0.1' and url.port and 0<url.port<65536
            and not url.username and not url.password and url.path in ('','/') and not url.query and not url.fragment,
            'Controlled Comfy endpoint must be an explicit http://127.0.0.1:PORT')
    args=launch['arguments'];env=launch['environment']
    require(isinstance(args,list) and all(isinstance(value,str) for value in args),'Explicit startup arguments required')
    require('--' not in args,'Controlled startup does not support an option terminator')
    options=[value.split('=',1)[0] for value in args if value.startswith('--')]
    protected=('--listen','--port','--input-directory','--output-directory','--user-directory')
    require(not any(flag.startswith(option) and option!=flag for option in options for flag in protected),
            'Use full option names; abbreviations cannot override the bound endpoint or directories')
    require(not any(option in ('--listen','--port') for option in options),
            'Listen address and port come only from the bound endpoint')
    users=[args[index+1] for index,value in enumerate(args[:-1]) if value=='--user-directory']
    users += [value.split('=',1)[1] for value in args if value.startswith('--user-directory=')]
    require(options.count('--user-directory')==1 and len(users)==1 and Path(users[0]).is_absolute(),'One explicit absolute user directory required')
    user=Path(users[0]);core=Path(config['inventory']['core'])
    require(user.is_dir() and user.resolve(strict=True)==user.absolute()
            and user in [Path(root) for root in config['inventory']['roots']]
            and not user.is_relative_to(core) and not core.is_relative_to(user),
            'Comfy user directory must be a separate inventoried source root')
    require(isinstance(env,dict) and all(isinstance(key,str) and isinstance(value,str) for key,value in env.items())
            and not any(key.upper().startswith('PYTHON') for key in env),
            'Explicit clean startup environment required; Python path injection is unsupported')
    return [str(Path(config['inventory']['core'])/'main.py'),'--listen','127.0.0.1','--port',str(url.port),*args]


def verify_deployment(path):
    before=pin(path);config=json.loads(Path(path).read_text(encoding='utf-8'))
    require(set(config)=={'schemaVersion','inventory','runtime','adapterSnapshot','launch'}
            and config['schemaVersion']==1,'Controlled startup configuration required')
    inventory=config['inventory'];runtime=config['runtime']
    require(set(runtime)=={'python','roots','files'},'Pinned startup runtime required')
    require(pin(runtime['python']['path'])==runtime['python'],'Pinned Comfy Python changed')
    require(runtime_inventory(runtime['roots'])==runtime['files'],'Comfy runtime membership or bytes changed; restart/reprepare')
    require(runtime['python'] in runtime['files'],'Runtime inventory must include the pinned interpreter')
    require(same_inventory(capture_inventory(inventory['core'],inventory['roots']),inventory),
            'Comfy source membership or bytes changed; restart/reprepare')
    snapshot=config['adapterSnapshot']
    # An external custom_nodes root is allowed, but it must contain this bootstrap.
    adapter=Path(__file__).resolve().parent
    require(Path(snapshot['path']).resolve()==adapter/'source-roots.json', 'Startup snapshot must belong to the executing adapter')
    require(pin(snapshot['path'])==snapshot and same_inventory(load_inventory(snapshot['path'],inventory['core']),inventory),
            'Installed adapter snapshot changed')
    require(pin(__file__) in inventory['files'],'Controlled bootstrap is absent from the source inventory')
    launch_arguments(config)
    require(pin(path)==before,'Startup configuration changed during verification')
    return config,before


def session_context(expected_core):
    holder=sys.modules.get(SESSION_MODULE);session=getattr(holder,'value',None)
    require(isinstance(session,dict) and session.get('pid')==os.getpid(),
            'Unmanaged Comfy process: start a new controlled session; leave other processes untouched')
    config,current=verify_deployment(session['configuration']['path'])
    require(current==session['configuration'] and digest(config['launch'])==session['settingsSha256'],
            'Startup configuration changed; restart and prepare again')
    require(Path(config['inventory']['core']).resolve()==Path(expected_core).resolve(),'Wrong controlled Comfy root')
    require(sys.argv==launch_arguments(config),'Startup arguments changed')
    require(all(os.environ.get(key)==value for key,value in config['launch']['environment'].items()),
            'Declared startup environment changed; restart and prepare again')
    require(pin(sys.executable)==config['runtime']['python'],'Executing Python differs from controlled startup')
    return dict(session),config


def start(path,receipt,*,execute=None):
    global _STARTED
    require(not _STARTED,'A startup already ran in this interpreter; launch a fresh process')
    require(sys.flags.isolated and sys.dont_write_bytecode,'Start with pinned Python -I -B')
    config,configuration=verify_deployment(path)
    require(pin(sys.executable)==config['runtime']['python'],'Executing Python differs from controlled startup')
    require(SESSION_MODULE not in sys.modules,'A controlled session is already active in this process')
    args=launch_arguments(config);port=int(args[4]);receipt=Path(receipt)
    require(not receipt.exists(),'Use a fresh startup receipt')
    # Check only our requested listen port. Never contact, terminate or free another server.
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as probe:
        if os.name=='nt':probe.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        try:probe.bind(('127.0.0.1',port))
        except OSError as error:raise ValueError('Comfy endpoint is occupied; stop and wait, do not disturb its owner') from error
    _STARTED.append(True)
    session={'id':uuid.uuid4().hex,'pid':os.getpid(),'configuration':configuration,'settingsSha256':digest(config['launch'])}
    holder=types.ModuleType(SESSION_MODULE);holder.value=session
    old_argv,old_path,old_env,old_cache=sys.argv,list(sys.path),dict(os.environ),sys.pycache_prefix
    evidence={'schemaVersion':1,'session':session,'state':'failed','inputsUnchanged':False}
    try:
        os.environ.clear();os.environ.update(config['launch']['environment'])
        sys.argv=args;sys.path[:]=[config['inventory']['core'],*config['inventory']['roots'][1:],*old_path]
        # A fresh empty cache path prevents stale .pyc reads; -B prevents new cache writes.
        with tempfile.TemporaryDirectory(prefix='headkit-bytecode-',dir=os.environ.get('TEMP') or None) as cache:
            sys.pycache_prefix=cache;sys.modules[SESSION_MODULE]=holder
            try:
                if execute is None:
                    # Controlled deployment and import-time source proof are complementary.
                    runpy.run_path(str(Path(__file__).with_name('verified_startup.py')),run_name='__main__')
                else:
                    execute(args[0],run_name='__main__')
                evidence['state']='complete'
            finally:
                session_context(config['inventory']['core']);evidence['inputsUnchanged']=True
    except BaseException as error:
        evidence['state']='failed';evidence['error']=str(error)
        raise
    finally:
        sys.modules.pop(SESSION_MODULE,None);sys.argv=old_argv;sys.path[:]=old_path;sys.pycache_prefix=old_cache
        os.environ.clear();os.environ.update(old_env)
        receipt.parent.mkdir(parents=True,exist_ok=True)
        with receipt.open('x',encoding='utf-8') as stream:json.dump(evidence,stream,indent=2)
    return evidence


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True,type=Path);parser.add_argument('--receipt',required=True,type=Path)
    args=parser.parse_args();start(args.config,args.receipt)


if __name__=='__main__':main()
