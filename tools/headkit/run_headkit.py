# Minimal script bridge for shared-tool launcher (which takes a script path).
import json
import sys
from pathlib import Path


def package_root(argv):
    """The byte-bound site-packages declared by --bindings, which must win over the interpreter's own copies
    before NumPy/Pillow/SciPy are first imported (python_package_pins rejects modules loaded from elsewhere).
    `batch --heads HEADS.json` names each head's bindings instead; their shared directory is used (none if they differ)."""
    def directory(path):
        try:row=json.loads(Path(path).read_text(encoding='utf-8')).get('pythonPackages')
        except (OSError,ValueError,AttributeError):return None
        return row.get('directory') if isinstance(row,dict) and isinstance(row.get('directory'),str) else None
    def value(flag):return argv[argv.index(flag)+1] if flag in argv and argv.index(flag)+1<len(argv) else None
    if value('--bindings'):return directory(value('--bindings'))
    if not value('--heads'):return None
    try:heads=json.loads(Path(value('--heads')).read_text(encoding='utf-8'))
    except (OSError,ValueError):return None
    if not isinstance(heads,list) or not heads or not all(isinstance(h,dict) and isinstance(h.get('bindings'),str) for h in heads):return None
    roots={directory(h['bindings']) for h in heads}
    return roots.pop() if len(roots)==1 else None


root=package_root(sys.argv)
if root:sys.path.insert(0,root)
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from tools.headkit.__main__ import main
if __name__=='__main__':main()
