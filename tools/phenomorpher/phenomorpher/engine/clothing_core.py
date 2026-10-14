"""Diagnostic clothing foundation. No native writer, source fitting or approval.

Column-vector equations are implemented with row-array storage. All matrices are
explicit; no filesystem/runtime discovery happens in this pure numerical module.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import numpy as np


class ContractError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ContractError(message)


def finite(value, shape, label):
    result = np.asarray(value, dtype=np.float64)
    require(result.shape == shape and np.isfinite(result).all(), label + " shape/data invalid")
    return result


def points(value):
    result = np.asarray(value, dtype=np.float64)
    require(result.ndim == 2 and result.shape[1] == 3 and len(result) > 0
            and np.isfinite(result).all(), "finite nonempty Nx3 positions required")
    return result


def homogeneous(value, label="matrix"):
    result = finite(value, (4, 4), label)
    require(np.allclose(result[3], [0, 0, 0, 1], atol=1e-12, rtol=0),
            label + " must be affine")
    return result


def rigid_frame(value, label="frame"):
    result = homogeneous(value, label)
    linear = result[:3, :3]
    require(np.allclose(linear.T @ linear, np.eye(3), atol=1e-9, rtol=0)
            and abs(np.linalg.det(linear) - 1) < 1e-9, label + " must be proper rigid")
    return result


def transform(value, matrix):
    p = points(value)
    m = homogeneous(matrix)
    return p @ m[:3, :3].T + m[:3, 3]


def similarity(value, label="similarity"):
    matrix = homogeneous(value, label)
    a = matrix[:3, :3]
    scale = float(np.cbrt(np.linalg.det(a)))
    require(np.isfinite(scale) and scale > 0, label + " reflection/collapse")
    require(np.allclose(a.T @ a, np.eye(3) * scale * scale, atol=1e-9, rtol=1e-9),
            label + " must not shear or scale anisotropically")
    return matrix


def hierarchy_frame(nodes, mesh_name):
    """Resolve and validate every declared static node, including unused cycles."""
    require(isinstance(nodes, list) and len(nodes) > 0, "node list required")
    inventory = {}
    for node in nodes:
        name = node.get("name", "").casefold()
        require(name and name not in inventory, "duplicate/empty node name")
        require(node.get("type") in ("dummy", "trimesh"), "unsupported mesh class")
        require(not node.get("weights") and not node.get("animations")
                and not node.get("supermodel"), "bind/animated/inherited path unsupported")
        inventory[name] = node
    frames, visiting = {}, set()

    def visit(name):
        if name in frames:
            return frames[name]
        require(name in inventory, "unresolved parent: " + name)
        require(name not in visiting, "parent cycle")
        visiting.add(name)
        node = inventory[name]
        local = similarity(node["matrix"], "node transform")
        parent = str(node.get("parent", "null")).casefold()
        frame = local if parent == "null" else visit(parent) @ local
        visiting.remove(name)
        frames[name] = frame
        return frame

    for name in inventory:
        visit(name)
    require(mesh_name.casefold() in frames, "missing mesh node")
    return frames[mesh_name.casefold()].copy()


def armory_matrix(profile):
    """Pinned 1.3.4 SRT: Rz(+z) Ry(-y) Rx(-x), pivot converted to translation."""
    scale = finite(profile["scale"], (3,), "scale")
    require(np.all(scale > 0), "positive structural scale required")
    angles = np.deg2rad(finite(profile.get("rotate", [0, 0, 0]), (3,), "rotate"))
    pivot = finite(profile.get("pivot", [0, 0, 0]), (3,), "pivot")
    translation = finite(profile.get("translate", [0, 0, 0]), (3,), "translate")
    require(set(profile) <= {"scale", "rotate", "pivot", "translate"}, "unsupported SRT field")
    x, y, z = -angles[0], -angles[1], angles[2]
    cx, sx, cy, sy, cz, sz = np.cos(x), np.sin(x), np.cos(y), np.sin(y), np.cos(z), np.sin(z)
    rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    matrix = np.eye(4)
    matrix[:3, :3] = rz @ ry @ rx @ np.diag(scale)
    matrix[:3, 3] = pivot + translation - matrix[:3, :3] @ pivot
    return matrix


IDENTITY_KEYS = ("sourceModelId", "gender", "geometryTopology", "staticFrames",
                 "canonicalPose", "animationClosure")
HASH_KEYS = IDENTITY_KEYS[2:]


def source_identity(value):
    require(isinstance(value, dict) and set(value) == set(IDENTITY_KEYS), "exact source identity fields required")
    gender = value["gender"]
    require(gender in ("male", "female"), "source gender required")
    require(value["sourceModelId"] == {"male": "human-male-v2", "female": "human-female-v1"}[gender],
            "source model/gender mismatch")
    for key in HASH_KEYS:
        require(isinstance(value[key], str) and re.fullmatch(r"[0-9a-f]{64}", value[key]),
                "source hash invalid: " + key)
    return value


def target_identity(value):
    require(isinstance(value, dict) and set(value) == {"id", "gender", *HASH_KEYS}, "exact target identity fields required")
    allowed = {f"{race}_{gender}_{size}" for race in ("human", "dwarf", "elf", "orc", "troll")
               for gender in ("male", "female") for size in ("fit", "large")}
    require(value["id"] in allowed and value["gender"] == value["id"].split("_")[1], "target identity/gender mismatch")
    for key in HASH_KEYS:
        require(isinstance(value[key], str) and re.fullmatch(r"[0-9a-f]{64}", value[key]), "target hash invalid: " + key)
    return value


def validate_descriptor(value, observed_source, observed_target):
    require(value.get("schemaVersion") == 1 and value.get("kind") == "phenomorpher-clothing-diagnostic",
            "explicit clothing diagnostic descriptor required")
    require(value.get("mode") == "diagnostic" and value.get("productionAccepted") is False,
            "foundation is diagnostic only; production gates are not implemented")
    source_identity(value["source"])
    source_identity(observed_source)
    require(value["source"] == observed_source, "source body/pose/animation identity mismatch")
    target_identity(value["target"])
    target_identity(observed_target)
    require(value["target"] == observed_target, "target body/pose/animation identity mismatch")
    require(value["target"]["gender"] == value["source"]["gender"], "cross-gender route unsupported")
    require(value.get("garmentClass") in ("modular-close", "modular-loose", "rigid-island"), "unsupported garment class")
    require(value.get("inputSpace") == "source-attachment-local-metres", "undeclared input space")
    require(value.get("morphApplications") == 0 and value.get("runtimeApplications") == 0,
            "repeated morphology/runtime conversion")
    require(value.get("axisConvention") == "right-handed-xyz", "axis contract unsupported")
    frames = {name: rigid_frame(value[name], name) for name in
              ("sourceCanonicalFrame", "targetCanonicalFrame", "targetBindFrame", "runtimeBindFrame")}
    factor = value["runtimeScale"]
    require(type(factor) in (int, float) and np.isfinite(factor) and factor > 0, "positive runtime scale required")
    bind, runtime = frames["targetBindFrame"], frames["runtimeBindFrame"]
    require(np.allclose(runtime[:3, :3], bind[:3, :3], atol=1e-12, rtol=0)
            and np.allclose(runtime[:3, 3], factor * bind[:3, 3], atol=1e-12, rtol=0),
            "runtime attachment frame already scaled incorrectly")
    structural = armory_matrix(value["structural"])
    if value["garmentClass"] == "rigid-island":
        similarity(structural, "rigid structural map")
    return frames, structural


def _slopes(x, y):
    """Shape-preserving scalar cubic slopes; works on N positive radii."""
    h = np.diff(x)
    delta = np.diff(y) / h
    if len(x) == 2:
        return np.array([delta[0], delta[0]])
    m = np.zeros(len(x))
    for i in range(1, len(x) - 1):
        if delta[i - 1] * delta[i] > 0:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / delta[i - 1] + w2 / delta[i])
    for endpoint, adjacent, next_delta, h0, h1 in (
            (0, delta[0], delta[1], h[0], h[1]),
            (-1, delta[-1], delta[-2], h[-1], h[-2])):
        slope = ((2 * h0 + h1) * adjacent - h0 * next_delta) / (h0 + h1)
        if slope * adjacent <= 0:
            slope = 0.
        elif adjacent * next_delta < 0 and abs(slope) > abs(3 * adjacent):
            slope = 3 * adjacent
        m[endpoint] = slope
    return m


def profile_value(stations, radii, query):
    x = np.asarray(stations, float)
    y = np.asarray(radii, float)
    q = np.asarray(query, float)
    require(np.isfinite(q).all() and np.all(q >= x[0] - 1e-12)
            and np.all(q <= x[-1] + 1e-12), "point outside field domain")
    q = np.clip(q, x[0], x[-1])
    i = np.clip(np.searchsorted(x, q, side="right") - 1, 0, len(x) - 2)
    h = x[i + 1] - x[i]
    t = (q - x[i]) / h
    m = _slopes(x, y)
    value = ((2*t**3-3*t**2+1)*y[i] + (t**3-2*t**2+t)*h*m[i]
             + (-2*t**3+3*t**2)*y[i+1] + (t**3-t**2)*h*m[i+1])
    derivative = ((6*t*t-6*t)*y[i]/h + (3*t*t-4*t+1)*m[i]
                  + (-6*t*t+6*t)*y[i+1]/h + (3*t*t-2*t)*m[i+1])
    return value, derivative


@dataclass(frozen=True)
class EnvelopeField:
    """Broad radial envelope in one explicit region; no source-body topology."""
    origin: np.ndarray
    basis: np.ndarray
    stations: np.ndarray
    before: np.ndarray
    after: np.ndarray
    maximum_offset: float = 0.05

    def __post_init__(self):
        origin = finite(self.origin, (3,), "field origin")
        basis = finite(self.basis, (3, 3), "field basis")
        frame = np.eye(4)
        frame[:3, :3] = basis
        rigid_frame(frame, "field basis")
        x = np.asarray(self.stations, float)
        require(x.ndim == 1 and len(x) >= 2 and np.isfinite(x).all()
                and np.all(np.diff(x) > 0), "ordered field stations required")
        before = finite(self.before, (len(x), 2), "source envelope")
        after = finite(self.after, (len(x), 2), "target envelope")
        require(np.all(before > 0) and np.all(after > 0), "positive endpoint contours required")
        require(np.isfinite(self.maximum_offset) and self.maximum_offset > 0, "bounded envelope offset required")
        for name, array in (("origin", origin), ("basis", basis), ("stations", x),
                            ("before", before), ("after", after)):
            frozen = np.array(array, copy=True)
            frozen.setflags(write=False)
            object.__setattr__(self, name, frozen)

    def local(self, values):
        return (points(values) - self.origin) @ self.basis

    def radii(self, t, target=False):
        table = self.after if target else self.before
        values = [profile_value(self.stations, table[:, k], t) for k in (0, 1)]
        return np.column_stack([row[0] for row in values]), np.column_stack([row[1] for row in values])

    def evaluate(self, values):
        q = self.local(values)
        a, _ = self.radii(q[:, 2])
        b, _ = self.radii(q[:, 2], True)
        q[:, :2] *= b / a
        return q @ self.basis.T + self.origin

    def associate(self, values):
        q = self.local(values)
        radii, _ = self.radii(q[:, 2])
        normalized = q[:, :2] / radii
        require(np.all(np.linalg.norm(normalized, axis=1) > 1e-9), "ambiguous envelope center association")
        return np.column_stack((q[:, 2], np.arctan2(normalized[:, 1], normalized[:, 0])))

    def surface(self, associations, target=False):
        a = np.asarray(associations, float)
        require(a.ndim == 2 and a.shape[1] == 2 and len(a) > 0 and np.isfinite(a).all(), "invalid associations")
        t, theta = a[:, 0], a[:, 1]
        radii, slopes = self.radii(t, target)
        cs, sn = np.cos(theta), np.sin(theta)
        anchor = np.column_stack((radii[:, 0]*cs, radii[:, 1]*sn, t))
        tangent = np.column_stack((-radii[:, 0]*sn, radii[:, 1]*cs, np.zeros(len(t))))
        longitudinal = np.column_stack((slopes[:, 0]*cs, slopes[:, 1]*sn, np.ones(len(t))))
        tangent /= np.linalg.norm(tangent, axis=1)[:, None]
        normal = np.cross(tangent, longitudinal)
        normal /= np.linalg.norm(normal, axis=1)[:, None]
        axial = np.cross(normal, tangent)
        frames = np.stack((normal, tangent, axial), axis=2)
        return anchor @ self.basis.T + self.origin, np.einsum("ij,njk->nik", self.basis, frames)

    def preserve_offsets(self, original, associations=None):
        p = points(original)
        a = self.associate(p) if associations is None else np.asarray(associations, float)
        require(len(a) == len(p), "association count differs from garment")
        source, source_frames = self.surface(a)
        target, target_frames = self.surface(a, True)
        local_offset = np.einsum("nji,nj->ni", source_frames, p-source)
        require(np.all(np.linalg.norm(local_offset, axis=1) <= self.maximum_offset), "garment outside supported offset domain")
        result = target + np.einsum("nij,nj->ni", target_frames, local_offset)
        return result, a.copy(), local_offset

    def checked_jacobian(self, values, step=1e-6):
        p = points(values)
        q = self.local(p)
        columns = []
        for axis in range(3):
            plus = np.full(len(p), step)
            minus = np.full(len(p), step)
            if axis == 2:
                plus = np.clip(self.stations[-1]-q[:, 2], 0, step)
                minus = np.clip(q[:, 2]-self.stations[0], 0, step)
            require(np.all(plus+minus > 1e-12), "field differential has no domain")
            a = self.preserve_offsets(p+plus[:, None]*self.basis[:, axis])[0]
            b = self.preserve_offsets(p-minus[:, None]*self.basis[:, axis])[0]
            columns.append((a-b)/(plus+minus)[:, None])
        local = np.stack(columns, axis=2)
        jacobian = np.einsum("nij,jk->nik", local, self.basis.T)
        determinants = np.linalg.det(jacobian)
        require(np.isfinite(jacobian).all() and np.all(determinants > 1e-8), "field/offset transport folds or collapses")
        return jacobian


def fit_rigid(source, target, allow_uniform_scale=False, maximum_residual=1e-6):
    a, b = points(source), points(target)
    require(a.shape == b.shape and len(a) >= 3, "paired rigid seating anchors required")
    require(type(allow_uniform_scale) is bool, "explicit rigid scale policy required")
    require(np.isfinite(maximum_residual) and maximum_residual >= 0, "finite anchor residual bound required")
    ac, bc = a-a.mean(axis=0), b-b.mean(axis=0)
    require(np.linalg.matrix_rank(ac, tol=1e-10) >= 2 and np.linalg.matrix_rank(bc, tol=1e-10) >= 2,
            "noncollinear rigid seating anchors required")
    u, singular, vt = np.linalg.svd(ac.T @ bc)
    sign = np.ones(3)
    sign[-1] = np.linalg.det(vt.T @ u.T)
    rotation = vt.T @ np.diag(sign) @ u.T
    scale = float(np.dot(singular, sign) / np.sum(ac*ac)) if allow_uniform_scale else 1.
    require(np.isfinite(scale) and scale > 0, "invalid rigid size factor")
    matrix = np.eye(4)
    matrix[:3, :3] = scale * rotation
    matrix[:3, 3] = b.mean(axis=0)-matrix[:3, :3] @ a.mean(axis=0)
    residual = float(np.max(np.linalg.norm(transform(a, matrix)-b, axis=1)))
    require(residual <= maximum_residual, "rigid seating residual exceeds declared bound")
    similarity(matrix, "rigid fit")
    return matrix, residual


def convert(value, descriptor, observed_source, observed_target, *, field=None, source_hierarchy=None,
            mesh_name=None, seating_anchors=None):
    """Diagnostic positions only. Topology/materials remain caller-owned unchanged."""
    frames, structural = validate_descriptor(descriptor, observed_source, observed_target)
    original = points(value)
    h = np.eye(4) if source_hierarchy is None else hierarchy_frame(source_hierarchy, mesh_name)
    normalized = transform(original, h)
    source_canonical = transform(normalized, frames["sourceCanonicalFrame"])
    structural_world = frames["targetCanonicalFrame"] @ structural @ np.linalg.inv(frames["sourceCanonicalFrame"])
    fitted = transform(source_canonical, structural_world)
    broad = fitted.copy() if field is None else field.evaluate(fitted)
    rigid_proof = None
    minimum_jacobian = None
    if descriptor["garmentClass"] == "rigid-island":
        if field is None:
            final = fitted.copy()
        else:
            require(seating_anchors is not None, "rigid field requires explicit seating anchors")
            anchors = transform(transform(points(seating_anchors), h), frames["targetCanonicalFrame"] @ structural)
            destination = field.evaluate(anchors)
            policy = descriptor.get("rigidPolicy", {})
            require(set(policy) == {"allowUniformScale", "maximumAnchorResidual"}, "rigid policy required")
            adjustment, residual = fit_rigid(anchors, destination, policy["allowUniformScale"], policy["maximumAnchorResidual"])
            final = transform(fitted, adjustment)
            rigid_proof = {"adjustment": adjustment.tolist(), "maximumAnchorResidual": residual}
    else:
        final = fitted.copy() if field is None else field.preserve_offsets(fitted)[0]
        if field is not None:
            minimum_jacobian = float(np.min(np.linalg.det(field.checked_jacobian(fitted))))
    local = transform(final, np.linalg.inv(frames["targetCanonicalFrame"]))
    working_actor = transform(local, frames["targetBindFrame"])
    runtime_local = local * descriptor["runtimeScale"]
    runtime_actor = transform(runtime_local, frames["runtimeBindFrame"])
    residual = float(np.max(abs(runtime_actor-descriptor["runtimeScale"]*working_actor)))
    require(residual < 1e-9, "runtime conversion applied incorrectly")
    return {
        "attachmentLocal": local, "canonical": final, "broadFieldBeforeEase": broad,
        "bindAssembled": working_actor, "runtimeLocal": runtime_local, "runtimeAssembled": runtime_actor,
        "proof": {"kind": "clothing-diagnostic-position-proof", "mode": "diagnostic",
                  "morphApplications": 1, "runtimeApplications": 1,
                  "runtimeActorMaximumError": residual, "rigid": rigid_proof,
                  "sampledMinimumFieldJacobian": minimum_jacobian,
                  "sourceIdentity": dict(observed_source), "targetIdentity": dict(observed_target), "nativeCompiled": False,
                  "sourceFitAccepted": False, "clearanceAccepted": False,
                  "lightingAttributesImplemented": False, "clientAccepted": False,
                  "productionAccepted": False,
                  "stages": ["hierarchy", "canonical normalization", "structural", "broad field",
                             "class design-offset preservation", "target attachment", "runtime once"]}
    }
