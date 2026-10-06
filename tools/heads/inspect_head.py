"""Read-only master inspection; never marks anatomy or body fitting accepted."""
import argparse
from pathlib import Path
import json
import time
import numpy as np
from head_export import triangles
from head_workflow import pin, sha, write_fresh


def inspect(source, output):
    started = time.monotonic()
    frozen = pin(source)
    p, n, uv = triangles(source, np.eye(4), maximum=3000000, require_uv=False)
    # Weld identical positions for topology only; authored corner attributes are
    # untouched. Edge direction counts expose winding independently of normals.
    vertices, inverse = np.unique(p.reshape(-1, 3), axis=0, return_inverse=True)
    faces = inverse.reshape(-1, 3)
    parents = list(range(len(vertices)))
    def root(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index
    edges = {}
    for a, b, c in faces:
        for first, second in ((int(a),int(b)),(int(b),int(c)),(int(c),int(a))):
            parents[root(first)] = root(second)
            key = tuple(sorted((first, second)))
            count, direction = edges.get(key, (0, 0))
            edges[key] = (count+1, direction+(1 if first < second else -1))
    components = {}
    for face in faces:
        components.setdefault(root(int(face[0])), {"faces":0,"watertight":True,"windingConsistent":True})["faces"] += 1
    for (first, _), (count, direction) in edges.items():
        component = components[root(first)]
        component["watertight"] &= count == 2
        component["windingConsistent"] &= count <= 2 and (count != 2 or direction == 0)
    cross = np.cross(p[:,1]-p[:,0], p[:,2]-p[:,0])
    alignment = np.einsum("ij,ij->i", cross, n.mean(1))
    record = {"kind": "srn-head-master-inspection", "source": frozen, "triangles": len(p),
              "nwnBasisBounds": [p.min((0,1)).tolist(), p.max((0,1)).tolist()],
              "topologyWeld": "exact position identity; corner attributes preserved",
              "topologyVertices":len(vertices),"topologyEdges":len(edges),
              "topologyEulerCharacteristic":len(vertices)-len(edges)+len(p),
              "components": sorted(components.values(), key=lambda row: -row["faces"]),
              "boundaryEdges":sum(count==1 for count,direction in edges.values()),
              "nonmanifoldEdges":sum(count>2 for count,direction in edges.values()),
              "inconsistentPairEdges":sum(count==2 and direction!=0 for count,direction in edges.values()),
              "authoredNormalWindingAgreement": float((alignment > 0).mean()),
              "uvRange": [uv.min((0,1)).tolist(), uv.max((0,1)).tolist()],
              "elapsedSeconds": time.monotonic()-started,
              "anatomyReviewed": False, "fittingAccepted": False, "productionAccepted": False}
    if sha(source) != frozen["sha256"]: raise ValueError("Master changed during inspection")
    write_fresh(output, record)
    return record


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args=parser.parse_args()
    print(json.dumps(inspect(args.source, args.output)))
