"""Fresh bundled-Python smoke for robe weight mathematics and dependencies."""
import json
import sys

import numpy as np
import PIL

from robe_weights import limit_and_normalize

weights = np.array([[0.5, 0.3, 0.1, 0.06, 0.04], [0.0, 0.0, 2.0, 0.0, 0.0]])
limited = limit_and_normalize(weights, 4, 0.001)
assert np.allclose(limited.sum(axis=1), 1.0) and (limited > 0).sum(axis=1).max() <= 4
print(json.dumps({"kind": "srn-robe-python-smoke", "executable": sys.executable,
                  "version": sys.version, "numpy": np.__version__, "pillow": PIL.__version__,
                  "weightLimitPassed": True}))
