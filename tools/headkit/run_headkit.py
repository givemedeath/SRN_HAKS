# Minimal script bridge for shared-tool launcher (which takes a script path).
import json
import sys
from pathlib import Path


def package_root(argv):
    """The byte-bound site-packages declared by --bindings, which must win over the interpreter's own copies
    before NumPy/Pillow/SciPy are first imported (python_package_pins rejects modules loaded from elsewhere)."""
    if '--bindings' not in argv or argv.index('--bindings')+1>=len(argv):return None
    try:row=json.loads(Path(argv[argv.index('--bindings')+1]).read_text(encoding='utf-8')).get('pythonPackages')
    except (OSError,ValueError):return None
    return row.get('directory') if isinstance(row,dict) and isinstance(row.get('directory'),str) else None


root=package_root(sys.argv)
if root:sys.path.insert(0,root)
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from tools.headkit.__main__ import main
if __name__=='__main__':main()
