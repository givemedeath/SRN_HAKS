# Minimal script bridge for shared-tool launcher (which takes a script path).
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from tools.headkit.__main__ import main
if __name__=='__main__':main()
