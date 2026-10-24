"""CPU-only repeatable verifier benchmark; never imports Comfy or loads models."""
import argparse
import ast
import gc
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import sys
import tempfile
import time
import tracemalloc
import types
from unittest.mock import patch


def run(source_path, repeats=3, instances=100):
    spec=importlib.util.spec_from_file_location('_verification_benchmark',source_path,
                                               submodule_search_locations=[str(source_path.parent)])
    snapshot=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=snapshot;spec.loader.exec_module(snapshot)
    measurements=[]
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'model.py'
        source=('class Model:\n    def __init__(self, mode):\n        self.mode=mode\n'
                '        if self.mode == "a":\n            self.enabled=True\n'
                '        else:\n            self.enabled=False\n'
                'def callback(value=7): return value\n'
                + ''.join(f'def helper_{i}(value={i}): return value\n' for i in range(150))
                + f'items=[Model("a" if i%2 else "b") for i in range({instances})]\n')
        path.write_text(source,encoding='utf-8')
        module=types.ModuleType('verifier_bench_model');module.__file__=str(path)
        exec(compile(source,str(path),'exec'),vars(module))
        foreign=types.ModuleType('foreign')
        foreign.holders=[types.SimpleNamespace(callback=module.callback,cache=list(range(20)))
                         for _ in range(instances*10)]
        for _ in range(repeats):
            gc.collect();tracemalloc.start();start=time.perf_counter()
            with patch.dict(sys.modules,{module.__name__:module,'foreign':foreign},clear=True):
                with patch.object(ast,'parse',wraps=ast.parse) as parse:
                    rows=snapshot.loaded_source_code([Path(directory)])
                    parses=parse.call_count
            elapsed=time.perf_counter()-start
            _,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
            measurements.append({'seconds':elapsed,'pythonPeakBytes':peak,'astParses':parses,'sourceRows':len(rows)})
    return {'schemaVersion':1,'scope':'Synthetic CPU verifier, conservative state checks; tracing enabled in both variants; no GPU/model residency',
            'sourceSha256':hashlib.sha256(source_path.read_bytes()).hexdigest(),'instances':instances,
            'verifiedIdentities':[{key:row[key] for key in ('sourceSha256','loadedCodeSha256')} for row in rows],
            'measurements':measurements,'medianSeconds':statistics.median(row['seconds'] for row in measurements),
            'medianPythonPeakBytes':statistics.median(row['pythonPeakBytes'] for row in measurements)}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--repeats',type=int,default=3)
    args=parser.parse_args()
    result=run(args.source.resolve(),args.repeats)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    print(json.dumps(result))
