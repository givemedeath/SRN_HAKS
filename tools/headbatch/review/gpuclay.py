"""gpuclay.py HEAD: retry a missing raw geometry sheet without a new GPU submission."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import gpu_contract,guards
from head_files import read
head=Path(sys.argv[1])
# The geometry files and ledger are verified by make_geometry_evidence; an existing sheet is immutable.
print(gpu_contract.make_geometry_evidence(head,read(head/'gpu'/'gpu.json')))
