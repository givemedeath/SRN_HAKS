"""Read-only native proof for the shared female standing-idle experiment.

The bounded reader is current repository code. No historical script is executed.
These finite offline checks do not establish engine or visual acceptance.
"""
import hashlib
import re
import numpy as np
from target_animation_overlay import NativeIdleReader
from target_contract import require

ROOTS = tuple(f"pf{family}{phenotype}" for family in "adegho" for phenotype in (0, 2))
ALTERED = {"rootdummy": 8, **{n: 20 for n in
    ("pelvis_g", "lthigh_g", "rthigh_g", "lshin_g", "rshin_g", "lfoot_g", "rfoot_g")}}
INHERITED = {"belt_pelvis", "g_ashto_011a", "lshould_g", "rshould_g"}
NODE = re.compile(r"(?m)^\s*node\s+(\S+)\s+(\S+)\s*\n(.*?)^\s*endnode", re.S)

# In the installed pfh2 exporter output, Impact is declared twice.  The proven
# source-specific static ownership is the last declaration; no other duplicate
# or changed source acquires this compatibility rule.
PFH2_DUPLICATE_IMPACT_SHA = "644185fdb13b263b1a6d767baf5acfd18ceb44c8cbe48edea3c4d1e5c0c001f1"

COMPONENT_BOUND = 1e-6
DISTANCE_BOUND_MM = .05
ANGLE_BOUND_DEGREES = .01
sha_bytes = lambda value: hashlib.sha256(value).hexdigest()


def expected_identity(root):
    require(root in ROOTS, "Undeclared female root")
    family, phenotype = root[2], int(root[3])
    parent = ("a_dfa" if family in "do" else "a_fa") + ("2" if phenotype else "")
    owner = "a_ba" if family in "do" else "a_fa" + ("2" if phenotype else "")
    return parent, owner, {"a": ".64", "d": ".65", "e": ".894", "g": ".64",
                          "h": "1", "o": "1"}[family]


def qmatrix(value):
    q = np.asarray(value, float)
    require(q.shape == (4,) and np.isfinite(q).all() and np.linalg.norm(q) > 1e-14,
            "Invalid native quaternion")
    x, y, z, w = q / np.linalg.norm(q)
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])


def axis_q(value):
    a = np.asarray(value, float)
    require(a.shape == (4,) and np.isfinite(a).all(), "Invalid source axis angle")
    length = np.linalg.norm(a[:3])
    return np.array([0., 0., 0., 1.]) if length < 1e-14 else np.r_[
        a[:3]/length*np.sin(a[3]/2), np.cos(a[3]/2)]


def ascii_bind(blob, root):
    text = blob.decode("cp1252")
    out = {}
    duplicate_impact_count = 0
    pinned_pfh2 = root == "pfh2" and sha_bytes(blob) == PFH2_DUPLICATE_IMPACT_SHA
    for match in NODE.finditer(text.split("endmodelgeom", 1)[0]):
        kind, name, body = match[1].lower(), match[2].lower(), match[3]
        require(kind == "dummy", "Non-dummy actor static")
        if name in out:
            require(pinned_pfh2 and name == "impact" and duplicate_impact_count == 0,
                    "Unpinned or unexpected duplicate actor static")
            duplicate_impact_count += 1
        def field(label, default):
            values = re.findall(r"(?mi)^\s*" + label + r"\s+([^\r\n]+)", body)
            require(len(values) <= 1, "Duplicate source static field")
            return values[0] if values else default
        p = np.array([float(x) for x in field("position", "0 0 0").split()])
        q = np.array([float(x) for x in field("orientation", "0 0 0 0").split()])
        require(p.shape == (3,) and np.isfinite(p).all() and
                float(field("scale", "1")) == 1, "Invalid source static position/scale")
        out[name] = {"parent": field("parent", "null").lower(),
                     "position": p, "rotation": qmatrix(axis_q(q))}
    require(not pinned_pfh2 or duplicate_impact_count == 1,
            "Pinned pfh2 duplicate Impact inventory differs")
    require(len(out) == 56 and root in out and out[root]["parent"] == "null",
            "Exactly 56 installed actor-owned nodes required")
    return out


def verify_root_token(row, original, descendant):
    root, carrier = row["root"], row["carrier"]
    parent, owner, scale = expected_identity(root)
    require(row["originalParent"] == parent and row["winningIdleOwner"] == owner and
            row["carrierScale"] == 1 and float(row["literalActorScaleToken"]) == float(scale),
            "Family owner/caller scale policy differs")
    require(carrier == "srn_fa_" + root[2:], "Foreign carrier alias")
    pattern = rb"(?im)^setsupermodel[ \t]+" + root.encode() + rb"[ \t]+(" + parent.encode() + rb")(?=[ \t]*\r?$)"
    matches = list(re.finditer(pattern, original))
    require(len(matches) == 1, "Installed parent token must be unique")
    a, b = matches[0].span(1)
    require(descendant == original[:a] + carrier.encode() + original[b:],
            "Root changes exceed the parent token")
    plan = row["rootLinkPlan"]
    require(plan["absoluteParentTokenRangeBytes"] == [a, b] and
            plan["originalParentTokenASCII"] == parent and
            plan["newSupermodelName"] == carrier and
            plan["protectedPrefixSHA256"] == sha_bytes(original[:a]) and
            plan["protectedSuffixSHA256"] == sha_bytes(original[b:]),
            "Frozen root token/protected byte proof differs")
    model = re.findall(rb"(?im)^newmodel[ \t]+(\S+)", original)
    scales = re.findall(rb"(?im)^setanimationscale[ \t]+(\S+)", original)
    require(model == [root.encode()] and
            scales == [row["literalActorScaleToken"].encode()], "Installed model/scale token differs")
    return [a, b]


def inherited_bind(row, skeleton, read_pin):
    require({x["name"] for x in row["inheritedStaticOmissions"]} == INHERITED and
            len(row["inheritedStaticOmissions"]) == 4 and not INHERITED & set(skeleton),
            "Exactly four inherited omissions required")
    cache = {}
    for entry in row["inheritedStaticOmissions"]:
        path = read_pin(entry["native"])
        key = str(path)
        if key not in cache:
            cache[key] = NativeIdleReader(path.read_bytes()).decode(set())
        decoded = cache[key]
        require(decoded["name"] == entry["owner"], "Inherited native owner differs")
        node = decoded["nodes"].get(entry["name"])
        require(node is not None and node["flags"] == entry["nativeFlags"] and
                node["parent"] == entry["parent"] and node["mesh"] is not None,
                "Inherited typed owner/parent differs")
        mesh = node["mesh"]
        require(mesh["faces"] == entry["faceCount"] and mesh["vertices"] == entry["nativeVertexCount"] and
                mesh["textures"] == entry["textures"], "Inherited mesh/material header differs")
        declared = entry["literalNativeStaticControllers"]
        require(set(declared) == {str(t) for t in node["controls"]}, "Inherited control inventory differs")
        for typ, control in node["controls"].items():
            old = declared[str(typ)]
            for field, span in (("times", "timeRange"), ("values", "dataRange")):
                value = control[field]
                expected = np.asarray(old[field], dtype="<f4")
                require(value.shape == expected.shape and value.tobytes() == expected.tobytes(),
                        "Inherited literal native control differs")
                words = "timeWords" if field == "times" else "valueWords"
                digest = "timePayloadSha256" if field == "times" else "valuePayloadSha256"
                require(value.view("<u4").tolist() == old[words] and
                        list(control[span]) == old["timeRange" if field == "times" else "valueRange"] and
                        sha_bytes(value.tobytes()) == old[digest], "Inherited native words/ranges differ")
        require({8, 20} <= set(node["controls"]), "Inherited bind position/orientation missing")
        p, q = node["controls"][8], node["controls"][20]
        require(p["times"].shape == q["times"].shape == (1,) and
                p["times"][0] == q["times"][0] == 0 and
                p["values"].shape == (1, 3) and q["values"].shape == (1, 4),
                "Inherited zero-time bind shape differs")
        require(36 not in node["controls"] or np.all(node["controls"][36]["values"] == 1),
                "Inherited local scale differs")
        skeleton[entry["name"]] = {"parent": node["parent"],
            "position": p["values"][0].astype(float), "rotation": qmatrix(q["values"][0])}
    require(len(skeleton) == 60, "Complete 56+4 hierarchy required")
    for name in skeleton:
        seen = set()
        while name != "null":
            require(name in skeleton and name not in seen, "Missing or cyclic bind hierarchy")
            seen.add(name)
            name = skeleton[name]["parent"]
    return skeleton


def verify_static(decoded, row, skeleton):
    root, carrier = row["root"], row["carrier"]
    expected = {(carrier if n == root else n) for n in skeleton if n not in INHERITED}
    require(set(decoded["nodes"]) == expected and len(expected) == 56,
            "Carrier static ownership differs")
    ranges = []
    for name, node in decoded["nodes"].items():
        old_name = root if name == carrier else name
        old = skeleton[old_name]
        want_parent = None if old["parent"] == "null" else carrier if old["parent"] == root else old["parent"]
        require(node["flags"] == 1 and node["mesh"] is None and node["parent"] == want_parent and
                set(node["controls"]) == {8, 20}, "Carrier typed static/control/parent differs")
        for typ, width in ((8, 3), (20, 4)):
            control = node["controls"][typ]
            require(control["times"].shape == (1,) and control["times"][0] == 0 and
                    control["values"].shape == (1, width), "Static zero-time controller shape differs")
            ranges.extend((control["timeRange"], control["dataRange"]))
        p = node["controls"][8]["values"][0]
        q = node["controls"][20]["values"][0]
        require(np.max(abs(p-old["position"])) <= COMPONENT_BOUND and
                np.max(abs(qmatrix(q)-old["rotation"])) <= COMPONENT_BOUND,
                "Carrier installed static frame differs")
    return ranges


def check_native(row, source_blob, parent_blob, final_blob, skeleton, numeric):
    owner, carrier = row["winningIdleOwner"], row["carrier"]
    original = NativeIdleReader(source_blob).decode({"pause1", "pause2"})
    parent = NativeIdleReader(parent_blob).decode()
    final = NativeIdleReader(final_blob).decode()
    require(original["name"] == owner and original["scale"] == 1 and
            set(original["clips"]) == {"pause1", "pause2"}, "Winning original idle owner differs")
    for model in (parent, final):
        require((model["name"], model["parent"], model["scale"]) ==
                (carrier, row["originalParent"], 1) and
                set(model["clips"]) == {"pause1", "pause2"}, "Carrier name/parent/scale/clips differ")
    static_ranges = verify_static(parent, row, skeleton)
    verify_static(final, row, skeleton)
    expected = bytearray(parent_blob)
    rows, changed_ranges, all_ranges = [], [], list(static_ranges)
    edited = untouched = 0
    for clip_name in ("pause1", "pause2"):
        old = original["clips"][clip_name]
        for new in (parent["clips"][clip_name], final["clips"][clip_name]):
            require(all(old[k] == new[k] for k in ("length", "transition", "animroot", "events")),
                    "Native idle timing/events/root differs")
            require(set(new["nodes"]) == (set(old["nodes"])-{owner}) | {carrier},
                    "Typed idle node inventory differs")
        for name, src_node in old["nodes"].items():
            destination = carrier if name == owner else name
            nodes = [m["clips"][clip_name]["nodes"][destination] for m in (parent, final)]
            wanted_parent = carrier if src_node["parent"] == owner else src_node["parent"]
            require(all(n["flags"] == src_node["flags"] and n["mesh"] == src_node["mesh"] and
                        n["parent"] == wanted_parent and set(n["controls"]) == set(src_node["controls"])
                        for n in nodes), "Native typed clip node/controller differs")
            for typ, src in src_node["controls"].items():
                dst, current = [n["controls"][typ] for n in nodes]
                require(current["timeRange"] == dst["timeRange"] and current["dataRange"] == dst["dataRange"],
                        "Native restored layout differs")
                all_ranges.extend((dst["timeRange"], dst["dataRange"]))
                if ALTERED.get(name) == typ:
                    prefix = row["root"]+"|"+clip_name+"|"+name
                    tt, vv = numeric[prefix+"|times"], numeric[prefix+"|values"]
                    require(tt.dtype == vv.dtype == np.dtype("<f4") and
                            current["times"].tobytes() == tt.tobytes() and
                            current["values"].shape == vv.shape, "Corrected native grids differ")
                    if typ == 8:
                        error = np.max(abs(current["values"].astype(float)-vv.astype(float)))
                    else:
                        a, b = current["values"].astype(float), vv.astype(float)
                        error = np.minimum(abs(a-b).max(axis=1), abs(a+b).max(axis=1)).max()
                        require(np.min(np.sum(a[:-1]*a[1:], axis=1), initial=1.) > 0,
                                "Corrected quaternion phase differs")
                    require(error <= COMPONENT_BOUND, "Corrected native values differ")
                    changed_ranges.extend((dst["timeRange"], dst["dataRange"]))
                    edited += 1
                    continue
                require(src["times"].shape == dst["times"].shape and src["values"].shape == dst["values"].shape,
                        "Untouched controller shape differs")
                require(all(src[k].tobytes() == current[k].tobytes() for k in ("times", "values")),
                        "Untouched native payload differs")
                if any(src[k].tobytes() != dst[k].tobytes() for k in ("times", "values")):
                    for field, generic in (("timeRange", "timeAbsoluteRange"), ("dataRange", "valueAbsoluteRange")):
                        sr, dr = src[field], dst[field]
                        require(sr[1]-sr[0] == dr[1]-dr[0], "Restoration widths differ")
                        payload = source_blob[sr[0]:sr[1]]
                        expected[dr[0]:dr[1]] = payload
                        rows.append({"clip": clip_name, "node": name, "type": typ, "field": generic,
                            "sourceRange": list(sr), "destinationRange": list(dr),
                            "sourceBytesSHA256": sha_bytes(payload),
                            "destinationBytesSHA256": sha_bytes(parent_blob[dr[0]:dr[1]])})
                untouched += 1
    count = 78 if owner == "a_ba" else 84
    require(edited == 16 and untouched == count == row["expectedUntouchedControllers"],
            "Family controller inventory differs")
    ordered = sorted(all_ranges)
    require(all(12 <= a < b <= len(parent_blob) for a, b in ordered) and
            all(a[1] <= b[0] for a, b in zip(ordered, ordered[1:])),
            "Static/animation native float ranges overlap or escape")
    require(len(final_blob) == len(parent_blob) and bytes(expected) == final_blob,
            "Restoration changed bytes outside exact derived ranges")
    return {"rows": rows, "modifiedControllerRanges": [list(x) for x in changed_ranges],
            "expectedResultSha256": sha_bytes(expected), "editedControllers": edited,
            "uneditedControllers": untouched, "staticOwners": 56,
            "finitePose": finite_pose(row, skeleton, original, final, numeric)}


def interpolate(control, time, typ):
    times, values = control["times"].astype(float), control["values"].astype(float)
    require(len(times) and np.all(np.diff(times) >= 0), "Unordered native times")
    if len(times) == 1 or time <= times[0]:
        return values[0]
    if time >= times[-1]:
        return values[-1]
    index = int(np.searchsorted(times, time, side="right")-1)
    a, b = values[index:index+2]
    w = (time-times[index])/(times[index+1]-times[index])
    if typ != 20:
        return a*(1-w)+b*w
    a, b = a/np.linalg.norm(a), b/np.linalg.norm(b)
    dot = a@b
    if dot < 0:
        b, dot = -b, -dot
    if dot > .9995:
        q = (1-w)*a+w*b
    else:
        angle = np.arccos(np.clip(dot, -1, 1))
        q = (np.sin((1-w)*angle)*a+np.sin(w*angle)*b)/np.sin(angle)
    return q/np.linalg.norm(q)


def world_pose(skeleton, clip, time, root, alias, scale, numeric=None):
    worlds, visiting = {}, set()
    controls = {(root if n == alias else n): row["controls"] for n, row in clip["nodes"].items()}
    require(set(controls) <= set(skeleton), "Animation node absent complete bind hierarchy")
    def visit(name):
        if name in worlds:
            return worlds[name]
        require(name in skeleton and name not in visiting, "Unresolved pose hierarchy")
        visiting.add(name)
        node = skeleton[name]
        p, rotation = node["position"].copy(), node["rotation"]
        for typ, control in controls.get(name, {}).items():
            if typ == 8:
                require(name == "rootdummy", "Unexpected animated child position")
                p = interpolate(control, time, typ)*scale
            elif typ == 20:
                rotation = qmatrix(interpolate(control, time, typ))
            else:
                require(typ == 36 and np.all(control["values"] == 1), "Unexpected animated scale")
        if numeric is not None and name in ALTERED:
            key = root+"|"+clip["name"]+"|"+name
            value = interpolate({"times": numeric[key+"|times"], "values": numeric[key+"|values"]},
                                time, ALTERED[name])
            if name == "rootdummy":
                p = value*scale
            else:
                rotation = qmatrix(value)
        local = np.eye(4)
        local[:3, :3], local[:3, 3] = rotation, p
        worlds[name] = local if node["parent"] == "null" else visit(node["parent"])@local
        visiting.remove(name)
        return worlds[name]
    for name in skeleton:
        visit(name)
    return worlds


def finite_pose(row, skeleton, original, final, numeric):
    foot = orientation = numeric_error = 0.
    samples = 0
    for name in ("pause1", "pause2"):
        old, new = dict(original["clips"][name], name=name), dict(final["clips"][name], name=name)
        times = numeric[row["root"]+"|"+name+"|rootdummy|times"].astype(float)
        probes = sorted(set(times.tolist()+[float(a+(b-a)*f) for a, b in zip(times, times[1:])
                                            for f in (.25, .5, .75)]))
        for time in probes:
            args = (time, row["root"])
            old_pose = world_pose(skeleton, old, *args, row["winningIdleOwner"], float(row["literalActorScaleToken"]))
            new_pose = world_pose(skeleton, new, *args, row["carrier"], float(row["literalActorScaleToken"]))
            expected = world_pose(skeleton, old, *args, row["winningIdleOwner"], float(row["literalActorScaleToken"]), numeric)
            for node in ("lfoot_g", "rfoot_g"):
                foot = max(foot, float(np.linalg.norm(new_pose[node][:3, 3]-old_pose[node][:3, 3])*1000))
                delta = new_pose[node][:3, :3].T@old_pose[node][:3, :3]
                orientation = max(orientation, float(np.degrees(np.arccos(np.clip((np.trace(delta)-1)/2, -1, 1)))))
            numeric_error = max(numeric_error, max(float(np.linalg.norm(new_pose[n][:3, 3]-expected[n][:3, 3])*1000) for n in skeleton))
            samples += 1
    require(foot <= DISTANCE_BOUND_MM and orientation <= ANGLE_BOUND_DEGREES and
            numeric_error <= DISTANCE_BOUND_MM, "Finite native pose bounds exceeded")
    return {"samples": samples, "sourceFootDistanceMm": foot,
            "sourceFootOrientationDegrees": orientation, "allNodePositionVsSourceNativeNumericMm": numeric_error,
            "actorScale": float(row["literalActorScaleToken"]), "ancestorScaleProductApplied": False,
            "distanceBoundMm": DISTANCE_BOUND_MM, "angleBoundDegrees": ANGLE_BOUND_DEGREES,
            "continuousEngineBehaviorProven": False}
