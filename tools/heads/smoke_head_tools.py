"""Fresh bundled-Python smoke for rigid head mathematics and dependencies."""
import json
import sys
import numpy as np
import PIL
from head_workflow import fit_similarity

points = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype=float)
fit = fit_similarity(points, points * 2 + [1, 2, 3], 1e-8)
assert abs(fit["uniformScale"] - 2) < 1e-8
print(json.dumps({"kind": "srn-head-python-smoke", "executable": sys.executable,
                  "version": sys.version, "numpy": np.__version__, "pillow": PIL.__version__,
                  "positiveSimilarityPassed": True}))
