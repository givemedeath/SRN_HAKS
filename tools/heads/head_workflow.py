"""Hash-bound head production, credit reservations and acceptance gates.

This module makes no paid requests. Meshy CLI/MCP results must be registered
explicitly. Operational sessions belong in ignored output/, never in Git.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil

import numpy as np

RACES = {"human": "h", "elf": "e", "dwarf": "d", "orc": "o", "troll": "g"}
STAGES = ("reference", "donor", "fitting", "assembly", "native", "client", "acceptance")
RECIPE = {
    "ai_model": "meshy-7", "geometry_resolution": "standard", "topology": "triangle",
    "target_polycount": 50000, "should_remesh": True,
    "save_pre_remeshed_model": True, "should_texture": False,
    "target_formats": ["glb"], "auto_size": False,
}
MAX_TRIANGLES = 20000
COSTS = {"multi-image-to-3d": 20, "remesh": 5, "retexture": 10}
TEXTURE_SIZE = 1024
MOTION = {"idle", "talk", "walk", "run", "cast", "combat", "crouch", "kneel", "death"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_fresh(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def pin(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": sha(path)}


def verify_pins(pins):
    require(bool(pins), "At least one consumed input must be declared")
    for item in pins:
        require(sha(item["path"]) == item["sha256"], "Frozen input changed: " + item["path"])


def task_fields(value):
    """Read CLI v1 envelopes without depending on presentation fields."""
    if not isinstance(value, dict):
        return {}
    for key in ("raw", "data", "task", "result"):
        if isinstance(value.get(key), dict):
            nested = task_fields(value[key])
            if nested.get("id"):
                return nested
    identity = value.get("id") or value.get("task_id") or value.get("taskId")
    if not identity and isinstance(value.get("result"), str):
        identity = value["result"]
    return {"id": identity, "status": value.get("status"), "credits": value.get("consumed_credits")}


def validate_remesh(payload):
    # Quad intermediates are triangulated in GLB. Their requested polygon count
    # must leave the same final triangle allowance; actual GLB counts are checked
    # again before selection because Meshy targets are approximate.
    topology=payload.get('topology')
    maximum=MAX_TRIANGLES//2 if topology=='quad' else MAX_TRIANGLES
    require(topology in ('triangle','quad') and type(payload.get('target_polycount')) is int
            and 100<=payload['target_polycount']<=maximum and payload.get('target_formats')==['glb']
            and 'decimation_mode' not in payload,'Explicit bounded remesh target and GLB output required')


def make_roster():
    entries = []
    for race, family in RACES.items():
        for sex in ("male", "female"):
            for number in range(1, 21):
                identity = f"{race}-{sex}-{number:02d}"
                pilot = identity in {"human-male-01", "human-male-02", "elf-female-01", "troll-male-01"}
                detail = (
                    "natural face, short modern hair" if number == 1 else
                    "subtle unilateral cyberware, short modern hair" if number == 2 else
                    "distinct adult face and modern hair; vary age, ancestry, scars and piercings"
                )
                anatomy = {
                    "human": "Human proportions",
                    "elf": "elongated pointed ears and refined facial structure",
                    "dwarf": "broad face and strong jaw",
                    "orc": "strong jaw and visible lower tusks",
                    "troll": "broad powerful facial structure, tusks and paired horns",
                }[race]
                entries.append({
                    "id": identity, "race": race, "sex": sex, "phenotype": 0,
                    "prefix": f"p{'m' if sex == 'male' else 'f'}{family}0",
                    "brief": f"{sex} adult; {anatomy}; {detail}; neutral closed-mouth expression",
                    "pilot": pilot, "slot": None, "selectedHashes": {},
                })
    return {"schemaVersion": 1, "kind": "srn-head-roster", "entries": entries}


def validate_roster(roster):
    require(roster.get("schemaVersion") == 1 and roster.get("kind") == "srn-head-roster", "Wrong roster")
    expected = {entry["id"]: entry for entry in make_roster()["entries"]}
    entries = roster["entries"]
    require(len(entries) == len(expected) and len({e["id"] for e in entries}) == len(expected),
            "Exactly 200 unique head designs required")
    allocated = set()
    for entry in entries:
        require(entry["id"] in expected, "Unknown head design")
        for key in ("race", "sex", "phenotype", "prefix", "pilot"):
            require(entry[key] == expected[entry["id"]][key], "Roster identity changed: " + key)
        require(isinstance(entry["brief"], str) and bool(entry["brief"].strip()), "Missing design brief")
        if entry["slot"] is not None:
            require(type(entry["slot"]) is int and 1 <= entry["slot"] <= 255, "Invalid head slot")
            name = model_name(entry["prefix"], entry["slot"])
            require(name not in allocated, "Duplicate allocated model")
            allocated.add(name)
    return roster


def model_name(prefix, slot):
    require(re.fullmatch(r"p[mf][hedog]0", prefix) and type(slot) is int and 1 <= slot <= 255,
            "Normal race/sex head identity required")
    return f"{prefix}_head{slot:03d}"


def allocate_slots(roster, resources, *, maximum):
    """Caller must prove the installed engine/consumer range; never infer it."""
    validate_roster(roster)
    require(type(maximum) is int and 20 <= maximum <= 255, "Verified engine slot maximum required")
    occupied = {Path(name).name.lower() for name in resources}
    allocated = json.loads(json.dumps(roster))
    for prefix in sorted({entry["prefix"] for entry in allocated["entries"]}):
        entries = [entry for entry in allocated["entries"] if entry["prefix"] == prefix]
        existing = [entry["slot"] for entry in entries]
        require(all(value is None for value in existing) or all(value is not None for value in existing),
                "Partial slot allocation must be reconciled explicitly")
        if existing[0] is not None:
            require(all(slot <= maximum for slot in existing), "Saved allocation exceeds verified range")
            require(all(model_name(prefix, slot) + ".mdl" not in occupied for slot in existing),
                    "Saved allocation now collides; do not silently renumber")
            continue
        start = next((number for number in range(1, maximum - 19 + 1)
                      if all(model_name(prefix, slot) + ".mdl" not in occupied
                             for slot in range(number, number + 20))), None)
        require(start is not None, "No contiguous block of 20 free slots: " + prefix)
        for entry, slot in zip(entries, range(start, start + 20)):
            entry["slot"] = slot
    return validate_roster(allocated)


def validate_target(target):
    require(target.get("schemaVersion") == 1 and target.get("kind") == "srn-head-target", "Wrong target contract")
    require(target["race"] in RACES and target["sex"] in ("male", "female"), "Unknown target race/sex")
    prefix = f"p{'m' if target['sex'] == 'male' else 'f'}{RACES[target['race']]}0"
    require(target["prefix"] == prefix and target["phenotype"] == 0, "Target family mismatch")
    require(target["bodyRevision"] and target["approved"] is True, "Approved body revision required")
    matrix = np.asarray(target["headBindMatrix"], dtype=float)
    require(matrix.shape == (4, 4) and np.isfinite(matrix).all(), "Invalid head attachment matrix")
    require(np.allclose(matrix[3], [0, 0, 0, 1]) and
            np.allclose(matrix[:3, :3].T @ matrix[:3, :3], np.eye(3), atol=1e-8) and
            abs(np.linalg.det(matrix[:3, :3]) - 1) < 1e-8, "Attachment frame must be rigid and proper")
    bounds = np.asarray(target["cranialEnvelope"], dtype=float)
    require(bounds.shape == (2, 3) and np.isfinite(bounds).all() and np.all(bounds[0] < bounds[1]),
            "Measured cranial envelope required")
    for key in ("neckGeometry", "bodyManifest", "palettes", "animations", "rig"):
        require(bool(target[key]), "Missing body input: " + key)
    verify_pins([target["neckGeometry"], target["bodyManifest"], target["rig"], *target["palettes"], *target["animations"]])
    require(len(target["palettes"]) == 2, "Both skin and hair palette references required")
    manifest = read(target["bodyManifest"]["path"])
    require(target['bodyRevision'] == target['bodyManifest']['sha256'], 'Body revision differs from publication pin')
    root = Path(target["bodyResourceRoot"]).resolve()
    require(manifest["resources"], "Body resource publication pins required")
    for item in manifest["resources"]:
        path = (root / item["path"]).resolve()
        require(path.is_relative_to(root) and sha(path) == item["sha256"], "Protected body resource changed")
    require(math.isfinite(target["landmarkTolerance"]) and target["landmarkTolerance"] > 0,
            "Measured landmark tolerance required")
    return target


def fit_similarity(source, destination, tolerance):
    source, destination = np.asarray(source, dtype=float), np.asarray(destination, dtype=float)
    require(source.shape == destination.shape and source.ndim == 2 and source.shape[1] == 3
            and len(source) >= 4 and np.isfinite(source).all() and np.isfinite(destination).all(),
            "At least four finite corresponding landmarks required")
    x, y = source - source.mean(0), destination - destination.mean(0)
    require(np.linalg.matrix_rank(x) == 3 and np.linalg.matrix_rank(y) == 3,
            "Landmarks must span three dimensions")
    u, singular, vt = np.linalg.svd(x.T @ y)
    rotation = vt.T @ u.T
    require(np.linalg.det(rotation) > 0, "Reflection rejected; recheck actual head orientation")
    scale = float(singular.sum() / (x * x).sum())
    require(scale > 0 and math.isfinite(scale), "Positive uniform scale required")
    translation = destination.mean(0) - scale * rotation @ source.mean(0)
    matrix = np.eye(4)
    matrix[:3, :3], matrix[:3, 3] = scale * rotation, translation
    error = float(np.linalg.norm(source @ matrix[:3, :3].T + translation - destination, axis=1).max())
    require(error <= tolerance, "Landmark residual exceeds approved target tolerance")
    return {"matrix": matrix.tolist(), "uniformScale": scale, "maximumLandmarkError": error}


class Session:
    """Immutable hash-linked events plus a lock for credit and gate updates."""
    def __init__(self, directory):
        self.root = Path(directory).resolve()
        self.config = read(self.root / "session.json")
        require(self.config["kind"] == "srn-head-session", "Wrong session binding")
        verify_pins([self.config["roster"]])
        if 'parentCheckpoint' in self.config:verify_pins(self.config['parentCheckpoint'])
        if 'budgetApproval' in self.config:
            verify_pins([self.config['budgetApproval']])
            approval=read(self.config['budgetApproval']['path'])
            require(approval['kind']=='srn-head-budget-approval' and approval['approved'] is True
                    and approval['newCap']==self.config['creditCap'] and bool(approval['userInstruction']),
                    'Explicit budget approval differs from session')
            verify_pins([self.config['budgetParent']]);parent=read(self.config['budgetParent']['path'])
            require(approval['previousCap']==parent['creditCap'], 'Budget approval parent differs')
        self.roster = validate_roster(read(self.config["roster"]["path"]))
        allocations = [e for e in self.events() if e["kind"] == "allocation"]
        if allocations:
            verify_pins([allocations[-1]["roster"], allocations[-1]["audit"]])
            self.roster = validate_roster(read(allocations[-1]["roster"]["path"]))

    @classmethod
    def create(cls, directory, roster, budget=300):
        require(type(budget) is int and 0 < budget <= 300, "Pilot credit cap must be between 1 and 300")
        validate_roster(read(roster))
        directory = Path(directory)
        require(not directory.exists(), "Fresh session directory required")
        write_fresh(directory / "session.json", {"schemaVersion": 1, "kind": "srn-head-session",
                    "roster": pin(roster), "creditCap": budget})
        write_fresh(directory / 'spending-owner.json', {'kind': 'srn-head-spending-owner',
                    'session': pin(directory / 'session.json')})
        return cls(directory)

    def spending_root(self):
        root, configuration, seen = self.root, self.config, {self.root}
        while configuration.get('parentCheckpoint'):
            parent = configuration['parentCheckpoint'][0]
            verify_pins([parent])
            root = Path(parent['path']).resolve().parent
            require(root not in seen, 'Cyclic spending ancestry')
            seen.add(root)
            configuration = read(root / 'session.json')
        return root

    @contextmanager
    def spending_lock(self):
        root = self.spending_root()
        path = root / 'spending.lock'
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as error:
            raise ValueError('Spending operation is active; reconcile a stale lock explicitly') from error
        try:
            os.close(fd)
            with self.lock():
                yield root / 'spending-owner.json'
        finally:
            path.unlink()

    def spending_owner(self, path):
        if not path.exists():
            raise ValueError('Legacy session has no spending owner; migrate ownership explicitly before paid work')
        owner = read(path)
        require(owner['kind'] == 'srn-head-spending-owner', 'Wrong spending owner binding')
        verify_pins([owner['session']])
        if owner.get('legacyReconciliation'):
            verify_pins([owner['legacyReconciliation']])
        return Path(owner['session']['path']).resolve().parent

    def adopt_spending(self, proof_file):
        """Explicit migration of an already settled legacy revision family."""
        proof = read(proof_file)
        require(proof.get('kind') == 'srn-head-spending-reconciliation' and proof.get('approved') is True
                and proof.get('session') == pin(self.root / 'session.json')
                and proof.get('creditUsed') == self.credit_used() and proof.get('creditCap') == self.config['creditCap'],
                'Approved legacy spending reconciliation required')
        verify_pins(proof['sessions'])
        verify_pins(proof['events'])
        require(pin(self.root / 'session.json') in proof['sessions'], 'Active session omitted from reconciliation')
        kinds = {'reserved', 'submitted', 'settled', 'reconciled-rejection'}
        financial = {sha(self.root / 'events' / f'{i:06d}.json')
                     for i, event in enumerate(self.events()) if event['kind'] in kinds}
        for item in proof['sessions']:
            member = Session(Path(item['path']).parent)
            require(member.spending_root() == self.spending_root(), 'Reconciliation crosses spending families')
            pins = [pin(member.root / 'events' / f'{i:06d}.json') for i in range(len(member.events()))]
            if pins:
                verify_pins(pins)
            require(all(p in proof['events'] for p in pins), 'Legacy event omitted from reconciliation')
            require(all(pins[i]['sha256'] in financial for i, event in enumerate(member.events()) if event['kind'] in kinds),
                    'Unmerged legacy spending; reconcile every branch before adoption')
        terminal = {e['requestId'] for e in self.events() if e['kind'] in ('settled', 'reconciled-rejection')}
        require(all(e['requestId'] in terminal for e in self.events() if e['kind'] == 'reserved'),
                'Reconcile outstanding submission before adopting spending ownership')
        with self.spending_lock() as owner_path:
            require(not owner_path.exists(), 'Spending owner already established')
            write_fresh(owner_path, {'kind': 'srn-head-spending-owner', 'session': pin(self.root/'session.json'),
                                    'legacyReconciliation': pin(proof_file)})

    @contextmanager
    def lock(self):
        path = self.root / "operation.lock"
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as error:
            raise ValueError("Session operation is active; reconcile a stale lock explicitly") from error
        try:
            os.close(fd)
            yield
        finally:
            path.unlink()

    def events(self):
        result, previous = [], None
        for number, path in enumerate(sorted((self.root / "events").glob("*.json"))):
            event = read(path)
            require(path.name == f"{number:06d}.json" and event["previousSha256"] == previous,
                    "Event chain changed or incomplete")
            result.append(event)
            previous = sha(path)
        return result

    def append(self, kind, **fields):
        events = self.events()
        previous = sha(self.root / "events" / f"{len(events)-1:06d}.json") if events else None
        write_fresh(self.root / "events" / f"{len(events):06d}.json", {
            "kind": kind, "createdUtc": datetime.now(timezone.utc).isoformat(),
            "previousSha256": previous, **fields})

    def design(self, identity):
        entry = next((row for row in self.roster["entries"] if row["id"] == identity), None)
        require(entry is not None, "Unknown design")
        return entry

    def allocate(self, roster_file, audit_file):
        roster, audit = validate_roster(read(roster_file)), read(audit_file)
        require(audit["kind"] == "srn-head-slot-audit" and audit["complete"] is True,
                "Complete installed-game and declared-consumer inventory required")
        verify_pins(audit["inputs"])
        require(audit["consumerScope"] == "installed-game-and-repository-packs",
                "Pilot consumer scope differs from user-approved declaration")
        proof = read(audit["engineRangeProof"]["path"])
        verify_pins([audit["engineRangeProof"]])
        require(proof["Appearance_Head"]["type"] == "byte", "Installed head storage range proof required")
        expected = allocate_slots(self.roster, audit["resources"], maximum=audit["maximum"])
        require(roster == expected, "Allocation differs from audited lowest contiguous blocks")
        with self.lock():
            require(not any(e["kind"] == "allocation" for e in self.events()), "Allocation already persisted")
            self.append("allocation", roster=pin(roster_file), audit=pin(audit_file))
        self.roster = roster

    def reviews(self, identity):
        result={}
        for row in self.events():
            if row['kind']=='revision' and identity in row['designs']:
                result={stage:event for stage,event in result.items() if STAGES.index(stage)<STAGES.index(row['fromStage'])}
            elif row['kind']=='review' and row['designId']==identity:result[row['stage']]=row
        return result

    def fork_revision(self, directory, identities, from_stage, inputs, *, credit_cap=None, budget_approval=None):
        require(from_stage in STAGES,'Explicit review stage required for a descendant revision')
        require(identities and len(set(identities))==len(identities),'Explicit unique revision designs required')
        for identity in identities:self.design(identity)
        configuration=dict(self.config)
        if credit_cap is not None:
            require(type(credit_cap) is int and credit_cap>self.config['creditCap'], 'Budget extension must increase the cap')
            require(budget_approval is not None, 'Explicit user budget approval required')
            approval_pin=pin(budget_approval);verify_pins([approval_pin]);approval=read(budget_approval)
            require(approval['kind']=='srn-head-budget-approval' and approval['approved'] is True
                    and approval['previousCap']==self.config['creditCap'] and approval['newCap']==credit_cap
                    and set(approval['designs'])==set(identities) and bool(approval['userInstruction']),
                    'Budget approval scope or ceiling differs')
            require(approval_pin in inputs, 'Budget approval omitted from frozen inputs')
            configuration.update(creditCap=credit_cap,budgetApproval=approval_pin,budgetParent=pin(self.root/'session.json'))
        else:require(budget_approval is None, 'Budget approval requires an explicit new cap')
        verify_pins(inputs);directory=Path(directory)
        require(not directory.exists(),'Fresh descendant session required')
        with self.spending_lock() as owner_path:
            owner = self.spending_owner(owner_path)
            events=self.events();files=[self.root/'session.json',*[self.root/'events'/f'{i:06d}.json' for i in range(len(events))]]
            if owner == self.root:
                terminal = {e['requestId'] for e in events if e['kind'] in ('settled', 'reconciled-rejection')}
                require(all(e['requestId'] in terminal for e in events if e['kind'] == 'reserved'),
                        'Reconcile outstanding submission before transferring spending ownership')
            checkpoint=[pin(path) for path in files]
            write_fresh(directory/'session.json',{**configuration,'parentCheckpoint':checkpoint})
            (directory/'events').mkdir()
            for path in files[1:]:shutil.copyfile(path,directory/'events'/path.name)
            verify_pins(checkpoint)
            descendant=Session(directory)
            with descendant.lock():
                descendant.append('revision',designs=identities,fromStage=from_stage,inputs=inputs)
            if owner == self.root:
                temporary = owner_path.with_suffix('.tmp')
                owner_binding = read(owner_path)
                write_fresh(temporary, {**owner_binding, 'session': pin(directory/'session.json')})
                temporary.replace(owner_path)
        return descendant

    def credit_used(self):
        events = self.events()
        for event in events:
            if event['kind']=='reconciled-rejection':verify_pins([event['result'],event['history']])
        settlements = {e["requestId"]: e["credits"] for e in events if e["kind"] in ("settled", "reconciled-rejection")}
        return sum(settlements.get(e["requestId"], e["estimatedCredits"])
                   for e in events if e["kind"] == "reserved")

    def reserve(self, identity, request_id, operation, estimated_credits, inputs, payload):
        self.design(identity)
        if 'budgetApproval' in self.config:
            require(identity in read(self.config['budgetApproval']['path'])['designs'], 'Design outside approved budget extension')
        require(re.fullmatch(r"[a-z0-9-]+", request_id), "Invalid request identity")
        require(operation in ("multi-image-to-3d", "retexture", "remesh"), "Unsupported paid operation")
        require(type(estimated_credits) is int and estimated_credits > 0, "Known positive cost required")
        require(estimated_credits >= COSTS[operation], "Reservation below verified operation price")
        if operation == "multi-image-to-3d":
            require(all(payload.get(key) == value for key, value in RECIPE.items()), "Generation recipe drift")
            require(len(payload.get("image_urls", [])) == 4, "Four frozen multiview images required")
            declared = {str(Path(p["path"]).resolve()) for p in inputs}
            require(all(str(Path(p).resolve()) in declared for p in payload["image_urls"]),
                    "Reference image omitted from frozen declaration")
        if operation == "retexture":
            require(payload.get("texture_resolution") == "2k" and payload.get("enable_original_uv") is True
                    and payload.get("enable_pbr") is True and payload.get('ai_model')=='meshy-7'
                    and payload.get('remove_lighting') is False and payload.get('target_formats')==['glb'],
                    "Retexture Meshy7/UV/2K/PBR recipe drift")
            require(len(payload.get('multiview_image_urls',[]))==4,'Four reviewed texture references required')
            declared={str(Path(p['path']).resolve()) for p in inputs}
            require(all(str(Path(p).resolve()) in declared for p in [payload['model_url'],*payload['multiview_image_urls']]),
                    'Retexture source/reference omitted from declaration')
        if operation == 'remesh':
            validate_remesh(payload)
        verify_pins(inputs)
        with self.spending_lock() as owner_path:
            require(self.spending_owner(owner_path) == self.root,
                    'Paid work belongs to another active revision; this session is read-only for dispatch')
            events = self.events()
            require(not any(e.get("requestId") == request_id for e in events), "Duplicate paid request")
            requests = [e for e in events if e["kind"] == "reserved"]
            terminal = {e["requestId"] for e in events if e["kind"] in ("settled", "reconciled-rejection")}
            require(all(e["requestId"] in terminal for e in requests), "Reconcile outstanding submission before another job")
            require(self.credit_used() + estimated_credits <= self.config["creditCap"], "Credit cap exceeded")
            reviews = self.reviews(identity)
            stage = {"multi-image-to-3d": "reference", "remesh": "donor", "retexture": "assembly"}[operation]
            require(stage in reviews, "Required review missing: " + stage)
            self.verify_review_chain(identity, stage)
            if operation=='retexture':
                assembly=read(reviews['assembly']['report']['path'])
                fitted=read(assembly['fit']['path'])
                require(Path(payload['model_url']).resolve()==Path(fitted['source']['path']).resolve(),
                        'Retexture must use the exact selected fitted geometry')
            if operation=='remesh' and payload.get('input_task_id'):
                task=next((e for e in events if e['kind']=='submitted' and e['taskId']==payload['input_task_id']),None)
                require(task is not None,'Remesh task source is not recorded')
                owner=next(e for e in requests if e['requestId']==task['requestId'])
                require(owner['designId']==identity and any(e['kind']=='settled' and e['requestId']==task['requestId']
                        and e['status']=='SUCCEEDED' for e in events),'Remesh source belongs to another or unfinished design')
            if operation == "multi-image-to-3d":
                require(sum(e["designId"] == identity and e["operation"] == operation for e in requests) < 2,
                        "Two generation attempts per pilot design exhausted")
            self.append("reserved", designId=identity, requestId=request_id, operation=operation,
                        estimatedCredits=estimated_credits, inputs=inputs, payload=payload)

    def record_task(self, request_id, task_id, resource, result_file):
        require(bool(task_id) and bool(resource), "Owning task resource and ID required")
        with self.lock():
            events = self.events()
            request = next((e for e in events if e["kind"] == "reserved" and e["requestId"] == request_id), None)
            require(request is not None, "Request was not reserved before dispatch")
            require(resource == request["operation"], "Task resource differs from paid request")
            require(not any(e["kind"] == "submitted" and e["requestId"] == request_id for e in events),
                    "Submission already recorded")
            require(not any(e["kind"] == "submitted" and e["taskId"] == task_id for e in events), "Task already owned")
            verify_pins(request["inputs"])
            require(task_fields(read(result_file))["id"] == task_id, "Submission response task differs")
            self.append("submitted", requestId=request_id, taskId=task_id, resource=resource, result=pin(result_file))

    def settle(self, request_id, status, credits, result_file):
        require(status in ("SUCCEEDED", "FAILED", "CANCELED"), "Timeout is not a terminal task")
        require(type(credits) is int and credits >= 0, "Actual consumed credits required; unknown remains reserved")
        with self.lock():
            events = self.events()
            submitted = next((e for e in events if e["kind"] == "submitted" and e["requestId"] == request_id), None)
            require(submitted is not None, "No recorded owning task")
            require(not any(e["kind"] == "settled" and e["requestId"] == request_id for e in events), "Already settled")
            actual = task_fields(read(result_file))
            require(actual == {"id": submitted["taskId"], "status": status, "credits": credits},
                    "Settlement differs from owning task response")
            self.append("settled", requestId=request_id, status=status, credits=credits, result=pin(result_file))

    def reconcile_rejection(self, request_id, result_file, history_file):
        """Release a definite API validation rejection only after task-history proof."""
        response,history=read(result_file),read(history_file)
        require(response.get('ok') is False and response.get('result') is None
                and response.get('error',{}).get('code')=='validation'
                and response['error'].get('http_status')==400,'Only a definite API validation rejection can be reconciled')
        listing=history.get('result',{})
        require(history.get('ok') is True and isinstance(listing.get('items'), list)
                and listing.get('page',{}).get('page_num')==1
                and listing['page'].get('sort_by')=='-created_at','Newest-first owning task history required')
        with self.lock():
            events=self.events()
            request=next((e for e in events if e['kind']=='reserved' and e['requestId']==request_id),None)
            require(request is not None and not any(e.get('requestId')==request_id and e['kind']!='reserved' for e in events),
                    'Only an unsubmitted, unreconciled reservation can be released')
            started=datetime.fromisoformat(request['createdUtc']).timestamp()*1000
            require(all(item['resource']==request['operation'] and item['created_at']<started for item in listing['items']),
                    'Task history contains a possible submission; reconcile its owning ID instead')
            self.append('reconciled-rejection',requestId=request_id,credits=0,
                        result=pin(result_file),history=pin(history_file))

    def review(self, identity, stage, report_file):
        self.design(identity)
        require(stage in STAGES, "Unknown acceptance stage")
        report = read(report_file)
        require(report.get("kind") == "srn-head-review" and report["designId"] == identity
                and report["stage"] == stage and report["passed"] is True, "Wrong or failed review")
        verify_pins(report["inputs"])
        verify_pins(report["evidence"])
        with self.lock():
            reviews = self.reviews(identity)
            require(stage not in reviews, "Stage already selected; create a fresh descendant session for revisions")
            index = STAGES.index(stage)
            if index:
                parent = STAGES[index-1]
                require(parent in reviews and report["parentReportSha256"] == reviews[parent]["report"]["sha256"],
                        "Missing or mismatched acceptance parent")
                self.verify_review_chain(identity, parent)
            if stage == "reference":
                require(report["views"] == ["front", "left", "back", "right"] and report["sharedScale"] is True,
                        "Coherent reviewed four-view references required")
            if stage == "donor":
                require(report["sourceUnmodified"] is True and report["geometryInspected"] is True,
                        "Donor geometry inspection required")
            if stage in ("fitting", "assembly", "native", "client", "acceptance"):
                target = validate_target(read(report["target"]["path"]))
                verify_pins([report["target"]])
                design = self.design(identity)
                require((target["race"], target["sex"]) == (design["race"], design["sex"]), "Wrong body target")
                if index > 2:
                    fitting_report = read(reviews["fitting"]["report"]["path"])
                    require(report["target"] == fitting_report["target"],
                            "Body target changed after fitting")
                    require(report.get("fit") == fitting_report["fit"],
                            "Fit changed after fitting")
                    verify_pins([report["fit"]])
            if stage == "fitting":
                verify_pins([report["fit"]])
                fitted = read(report["fit"]["path"])
                require(fitted["target"] == report["target"], "Fit belongs to another target")
                verify_pins([fitted["source"]])
                measured = fit_similarity(fitted["sourceLandmarks"], fitted["targetLandmarks"],
                                          target["landmarkTolerance"])
                require(np.allclose(measured["matrix"], fitted["matrix"], atol=1e-9), "Fit matrix differs from landmarks")
            if stage == "assembly":
                require(report["standingReviewed"] is True and report["worstCaseMotionReviewed"] is True
                        and report["bodyResourcesUnchanged"] is True, "Assembly and protected body review required")
                require(set(report["motions"]) >= MOTION, "Broader motion coverage incomplete")
            if stage == "native":
                verify_pins([report['neckClosure']])
                closure=read(report['neckClosure']['path'])
                require(closure['passed'] is True and closure['neckCutBoundaryEdges']==0
                        and closure['uncappedClosedNeckLoops']==0,'Head neck openings must be capped')
                selected_source=read(report['fit']['path'])['source']
                if closure.get('kind')=='srn-head-cap-only-closure':
                    verify_pins([closure['source'],closure['output']])
                    require(closure['output']==selected_source and closure['originalSurfacePreserved'] is True
                            and closure['originalVerticesMoved'] is False and closure['trimApplied'] is False
                            and closure['taperApplied'] is False and closure['remainingClosedBoundaryLoops']==0,
                            'Cap-only closure must preserve the selected skull and jaw without trimming or tapering')
                else:
                    require(closure['source']==selected_source,'Neck closure belongs to another geometry')
                if closure.get('taperDepthMetres',0):
                    verify_pins([report['neckConnector']]);connector=read(report['neckConnector']['path'])
                    require(connector['passed'] is True and connector['source']==closure['source']
                            and connector['capInsideStockNeckConvexEnvelope'] is True,'Lowered cap needs protected-neck containment proof')
                require(report["nativeDecoded"] is True and report["geometryUvNormalsVerified"] is True
                        and report["paletteMasksVerified"] is True and report["materialTransportVerified"] is True,
                        "Native attribute and palette proof incomplete")
                require(0 < report["triangles"] <= MAX_TRIANGLES and report["textureSize"] == TEXTURE_SIZE,
                        "Runtime head budget exceeded")
                verify_pins(report["resources"])
            if stage == "client":
                require(report["clientObserved"] is True and report["slotsSelectable"] is True and report["helmetsReviewed"] is True
                        and report["palettesReviewed"] is True and report["lightingReviewed"] is True, "Actual client checks incomplete")
                require(set(report["motions"]) >= MOTION, "Client motion coverage incomplete")
                require(report["packageSha256"] == read(reviews["native"]["report"]["path"])["packageSha256"],
                        "Client tested another package")
            if stage == "acceptance":
                require(report["rightsReviewed"] is True and report["bodyResourcesUnchanged"] is True, "Publication review incomplete")
            self.append("review", designId=identity, stage=stage, report=pin(report_file))

    def verify_review_chain(self, identity, through):
        reviews = self.reviews(identity)
        for stage in STAGES[:STAGES.index(through)+1]:
            require(stage in reviews, "Required review missing: " + stage)
            verify_pins([reviews[stage]["report"]])
            report = read(reviews[stage]["report"]["path"])
            verify_pins(report["inputs"])
            verify_pins(report["evidence"])
            if "target" in report:
                verify_pins([report["target"]])
                validate_target(read(report["target"]["path"]))
            if "resources" in report:
                verify_pins(report["resources"])
            if "fit" in report:
                verify_pins([report["fit"]])
                verify_pins([read(report["fit"]["path"])["source"]])
            if 'neckClosure' in report:verify_pins([report['neckClosure']])
            if 'neckConnector' in report:verify_pins([report['neckConnector']])

    def publication(self, identities, *, slot_audit=None, repository=None):
        require(bool(identities) and len(set(identities)) == len(identities), "Explicit unique selections required")
        resources = {}
        for identity in identities:
            self.verify_review_chain(identity, "acceptance")
            entry = self.design(identity)
            require(entry["slot"] is not None, "Verified slot allocation required")
            native = read(self.reviews(identity)["native"]["report"]["path"])
            model = model_name(entry["prefix"], entry["slot"])
            names = {Path(item["path"]).name for item in native["resources"]}
            require(model + ".mdl" in names and model + ".plt" in names, "Selected model/palette missing")
            require(all(re.fullmatch(re.escape(model) + r"[a-z0-9_]*\.(mdl|plt|mtr|tga|dds|txi)", name)
                        and len(Path(name).stem) <= 16 for name in names), "Undeclared resource ownership")
            for item in native["resources"]:
                name = Path(item["path"]).name
                require(name not in resources, "Publication resource collision")
                require(Path(item["path"]).stat().st_size <= 15 * 1024 * 1024, "Resource exceeds size policy")
                resources[name] = item
        from audit_slots import verify_publication_inventory
        require(slot_audit is not None and repository is not None,
                'Current slot audit and consumer repository required for publication')
        verify_publication_inventory(slot_audit, repository, self.roster, resources)
        return resources

    def publish(self, identities, output, *, slot_audit=None, repository=None):
        resources = self.publication(identities, slot_audit=slot_audit, repository=repository)
        output = Path(output)
        require(not output.exists(), "Fresh publication directory required")
        output.mkdir(parents=True)
        for name, item in resources.items():
            shutil.copyfile(item["path"], output / name)
            require(sha(output / name) == item["sha256"], "Publication copy differs")
        return {"schemaVersion": 1, "kind": "srn-head-publication", "designs": identities,
                "resources": [{"path": "srn_head/"+name, "sha256": item["sha256"],
                               "bytes": (output / name).stat().st_size} for name, item in resources.items()]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--roster", type=Path, required=True)
    init.add_argument("--output", type=Path, required=True)
    init.add_argument("--budget", type=int, default=300)
    status = sub.add_parser("status")
    status.add_argument("--session", type=Path, required=True)
    adopt = sub.add_parser('adopt-spending')
    adopt.add_argument('--session', type=Path, required=True)
    adopt.add_argument('--proof', type=Path, required=True)
    review = sub.add_parser("review")
    review.add_argument("--session", type=Path, required=True)
    review.add_argument("--report", type=Path, required=True)
    for name in ("reserve", "record-task", "settle"):
        command = sub.add_parser(name)
        command.add_argument("--session", type=Path, required=True)
        command.add_argument("--record", type=Path, required=True)
    allocation = sub.add_parser("allocate")
    allocation.add_argument("--session", type=Path, required=True)
    allocation.add_argument("--roster", type=Path, required=True)
    allocation.add_argument("--audit", type=Path, required=True)
    publish = sub.add_parser("publish")
    publish.add_argument("--session", type=Path, required=True)
    publish.add_argument("--design", action="append", required=True)
    publish.add_argument("--output", type=Path, required=True)
    publish.add_argument("--manifest", type=Path, required=True)
    publish.add_argument('--slot-audit', type=Path, required=True)
    publish.add_argument('--repository', type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.command == "init":
        session = Session.create(arguments.output, arguments.roster, arguments.budget)
    else:
        session = Session(arguments.session)
    if arguments.command == "review":
        report = read(arguments.report)
        session.review(report["designId"], report["stage"], arguments.report)
    elif arguments.command == 'adopt-spending':
        session.adopt_spending(arguments.proof)
    elif arguments.command in ("reserve", "record-task", "settle"):
        getattr(session, arguments.command.replace("-", "_"))(**read(arguments.record))
    elif arguments.command == "allocate":
        session.allocate(arguments.roster, arguments.audit)
    elif arguments.command == "publish":
        require(not arguments.manifest.exists(), "Fresh publication manifest required")
        write_fresh(arguments.manifest, session.publish(arguments.design, arguments.output,
                    slot_audit=arguments.slot_audit, repository=arguments.repository))
    print(json.dumps({"session": str(session.root), "reservedOrConsumedCredits": session.credit_used(),
                      "creditCap": session.config["creditCap"], "events": len(session.events())}))


if __name__ == "__main__":
    main()
