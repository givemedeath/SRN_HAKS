"""Transition guards: real container bytes, injected decoders, no engine claim."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import target_contract as contract
import shared_female_transition_fixture as transition
from audit_thigh_package import TYPE_BY_EXTENSION


def pin(path):
    return {"path": str(path.resolve()), "sha256": contract.sha(path)}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value if isinstance(value, bytes) else json.dumps(value).encode())
    return pin(path)


def native_archive(path, resources):
    keys = 160
    count = len(resources)
    table = keys + count * 24
    payload = table + count * 8
    blob = bytearray(payload)
    blob[:8] = b"MOD V1.0"
    struct.pack_into("<I", blob, 16, count)
    struct.pack_into("<II", blob, 24, keys, table)
    for index, (name, data) in enumerate(resources.items()):
        struct.pack_into("<16sIH", blob, keys + index * 24, Path(name).stem.encode(),
                         index, TYPE_BY_EXTENSION[Path(name).suffix])
        struct.pack_into("<II", blob, table + index * 8, len(blob), len(data))
        blob.extend(data)
    return write(path, bytes(blob))


def rosters_fixture():
    roots = {0: "d", 1: "e", 2: "g", 3: "a", 4: "h", 5: "o", 6: "h"}
    rosters = []
    for index, races in enumerate(((0, 1), (2, 3), (4, 5), (6,))):
        actors = []
        for race in races:
            for phenotype in (0, 2):
                for pose in (0, 1):
                    n = len(actors)
                    actors.append({"tag": "tm_" + str(n), "purpose": "required-case",
                        "raceId": race, "appearanceId": race, "phenotypeId": phenotype,
                        "gender": 1, "femaleRoot": f"pf{roots[race]}{phenotype}", "headStyle": 1,
                        "bodyStyle": 1, "poseId": pose, "clip": ("pause1", "pause2")[pose],
                        "skinPalette": 3 if n < 4 else 8, "equipment": [],
                        "placement": {"XPosition": 16. + 6 * (n % 4), "YPosition": 16. if n < 4 else 24.,
                            "ZPosition": 0., "XOrientation": 0., "YOrientation": -1.}})
        if index == 3:
            for race, phenotype in ((0, 2), (1, 0)):
                for pose in (0, 1):
                    actor = copy.deepcopy(actors[pose])
                    actor.update(tag="tm_" + str(len(actors)), purpose="equipment-control",
                        raceId=race, appearanceId=race, phenotypeId=phenotype,
                        femaleRoot=f"pf{roots[race]}{phenotype}", skinPalette=8)
                    actor["placement"].update(XPosition=16. + 6 * (len(actors) % 4), YPosition=24.)
                    actors.append(actor)
        rosters.append({"batchId": "batch-" + str(index + 1), "actors": actors})
    return rosters


class TransitionFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.area = self.root / "output/phenotypes" / transition.TARGET
        self.area.mkdir(parents=True)
        self.target_path = self.area / "target.json"
        write(self.target_path, {})
        self.target = {"id": transition.TARGET, "rig": {"mode": "stock-exact", "revision": "stock-v1"},
                       "identity": {"gender": "female"}}
        self.binding = contract.binding(self.target_path, self.target, "runtime")
        self.rosters = rosters_fixture()
        self.roster_pins = [write(self.area / f"roster-{i}.json", roster)
                            for i, roster in enumerate(self.rosters)]
        self.coverage = write(self.area / "coverage.json", {"rosters": self.roster_pins})
        self.family = write(self.area / "families.json", {})
        self.native_idle = write(self.area / "stock-idle.mdl", b"test native idle")
        self.schedule = {"schemaVersion": 1, "kind": "shared-female-transition-schedule", **self.binding,
            "familyPreparation": self.family, "coverage": self.coverage, "rosters": self.roster_pins,
            "groups": [], "idleTimings": {root: {"owner": "a_fa", "sourceNative": self.native_idle,
                "pause1": {"length": 2., "transition": 1.},
                "pause2": {"length": 2., "transition": 1.}} for root in transition.ROOTS},
            "camera": {"distance": 20., "pitch": 75., "height": .95},
            "outboundDistanceMetres": 12., "arrivalToleranceMetres": .1, "postureHoldSeconds": 4.,
            "samplingLimit": "One group view; direct client review pending.",
            "sourceNSSHashes": {n: "a"*64 for n in transition.SOURCES}}
        for roster in self.rosters:
            for purpose in ("required-case", "equipment-control"):
                for race in dict.fromkeys(a["raceId"] for a in roster["actors"] if a["purpose"] == purpose):
                    self.schedule["groups"].append({"batchId": roster["batchId"],
                        "groupId": roster["batchId"] + "-" + purpose + "-race-" + str(race),
                        "actorTags": [a["tag"] for a in roster["actors"]
                                      if a["purpose"] == purpose and a["raceId"] == race]})
        self.schedule_pin = write(self.area / "schedule.json", self.schedule)

    def trace(self, batch=0):
        roster = self.rosters[batch]
        actors = {a["tag"]: a for a in roster["actors"]}
        events, now = [], 0.
        for group in (g for g in self.schedule["groups"] if g["batchId"] == roster["batchId"]):
            for phase, family in enumerate(("baseline", "walk", "run", "crouch", "kneel")):
                states = ["baseline-request", "baseline-complete"] if phase == 0 else (
                    [family + "-request"] + ([family + "-out-arrived", family + "-home-arrived"]
                    if phase in (1, 2) else [family + "-complete"]) + ["idle-request", "idle-complete"])
                for state in states:
                    if state in ("baseline-complete", "idle-complete"):
                        now += 5.
                    elif state.endswith("-arrived") or state.endswith("-complete"):
                        now += 4.
                    for tag in group["actorTags"]:
                        actor = actors[tag]
                        position = [actor["placement"][k] for k in ("XPosition", "YPosition", "ZPosition")]
                        if state.endswith("-out-arrived"):
                            position[1] += (-1 if position[1] < 20 else 1) * 12
                        events.append({"groupId": group["groupId"], "actorTag": tag, "runToken": 7,
                            "phase": phase, "state": state, "elapsedSeconds": now,
                            "requested": actor["poseId"] if state in ("baseline-request", "idle-request") else (
                                (0, 1, 12, 4)[phase - 1] if state.endswith("-request") else 0),
                            "action": 0, "position": position, "facing": 270., "pause": 0})
        return {"schemaVersion": 1, "kind": "shared-female-transition-logged-trace",
                "schedule": self.schedule_pin, "roster": self.roster_pins[batch],
                "runToken": 7, "events": events}


class ScheduleAndTraceTests(TransitionFixture):
    def test_complete_28_cells_and_nine_groups(self):
        report = transition.validate_schedule(self.schedule, self.rosters)
        self.assertEqual(len(report["requiredCells"]), 28)
        self.assertEqual(len(report["groups"]), 9)

    def test_trace_all_batches_grouped_both_idles_no_client_approval(self):
        for batch in range(4):
            with self.subTest(batch=batch):
                report = transition.validate_trace(self.schedule, self.rosters[batch], self.trace(batch))
                self.assertEqual(report["loggedActors"], 8)
                self.assertFalse(report["clientAccepted"])
                self.assertFalse(report["visibleMotionProven"])

    def serial_trace(self, batch):
        trace = self.trace(batch)
        grouped = {}
        for event in trace["events"]:
            grouped.setdefault((event["groupId"], event["phase"]), {}).setdefault(event["actorTag"], []).append(event)
        events, clock = [], 0.
        for actors in grouped.values():
            for rows in actors.values():
                for event in rows:
                    if event["state"] in ("baseline-complete", "idle-complete"):
                        clock += 5.1
                    elif event["state"].endswith("-arrived") or event["state"].endswith("-complete"):
                        clock += 4.1
                    event["elapsedSeconds"] = clock
                    events.append(event)
        trace["events"] = events
        return trace

    def test_serial_actor_camera_protocol_preserves_complete_phase_barriers(self):
        for batch in range(4):
            with self.subTest(batch=batch):
                report = transition.validate_trace(self.schedule, self.rosters[batch], self.serial_trace(batch))
                self.assertEqual(report["loggedActors"], 8)
                self.assertFalse(report["visibleMotionProven"])
                self.assertFalse(report["clientAccepted"])

    def test_serial_actor_cannot_advance_phase_before_neighbors_finish(self):
        trace = self.serial_trace(0)
        trace["events"][2]["phase"] = 1
        with self.assertRaisesRegex(ValueError, "phase"):
            transition.validate_trace(self.schedule, self.rosters[0], trace)

    def test_schedule_rejects_missing_duplicate_or_changed_members(self):
        for mutation in ("missing", "duplicate", "membership"):
            bad = copy.deepcopy(self.schedule)
            if mutation == "missing": bad["groups"].pop()
            if mutation == "duplicate": bad["groups"].append(bad["groups"][0])
            if mutation == "membership": bad["groups"][0]["actorTags"].reverse()
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                transition.validate_schedule(bad, self.rosters)

    def test_schedule_counts_boolean_invalid_idle_camera_and_nonfinite(self):
        for key, value in (("schemaVersion", True), ("outboundDistanceMetres", float("inf")),
                           ("arrivalToleranceMetres", True), ("postureHoldSeconds", -1)):
            bad = copy.deepcopy(self.schedule); bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                transition.validate_schedule(bad, self.rosters)
        bad = copy.deepcopy(self.schedule); bad["camera"]["pitch"] = 90
        with self.assertRaises(ValueError): transition.validate_schedule(bad, self.rosters)
        rosters = copy.deepcopy(self.rosters); rosters[0]["actors"][0]["clip"] = "pause2"
        with self.assertRaises(ValueError): transition.validate_schedule(self.schedule, rosters)

    def test_wrong_return_idle_and_premature_barrier(self):
        bad = self.trace()
        next(e for e in bad["events"] if e["state"] == "idle-request" and e["actorTag"] == "tm_1")["requested"] = 0
        with self.assertRaisesRegex(ValueError, "same assigned idle"):
            transition.validate_trace(self.schedule, self.rosters[0], bad)
        bad = self.trace(); bad["events"][1]["phase"] = 1
        with self.assertRaisesRegex(ValueError, "phase"):
            transition.validate_trace(self.schedule, self.rosters[0], bad)

    def test_incomplete_duplicate_stale_paused_and_queue_intervention(self):
        for mutation in ("incomplete", "duplicate", "stale", "pause", "clear"):
            bad = self.trace()
            if mutation == "incomplete": bad["events"].pop()
            if mutation == "duplicate": bad["events"].insert(1, copy.deepcopy(bad["events"][0]))
            if mutation == "stale": bad["events"][5]["runToken"] = 6
            if mutation == "pause": bad["events"][5]["pause"] = 1
            if mutation == "clear": bad["events"][8]["state"] = "ClearAllActions"
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                transition.validate_trace(self.schedule, self.rosters[0], bad)

    def test_false_arrival_and_wrong_home(self):
        for state in ("walk-out-arrived", "walk-home-arrived"):
            bad = self.trace()
            next(e for e in bad["events"] if e["state"] == state)["position"][0] += 1
            with self.subTest(state=state), self.assertRaisesRegex(ValueError, "arrival"):
                transition.validate_trace(self.schedule, self.rosters[0], bad)

    def test_idle_requires_actual_blend_plus_two_cycles(self):
        bad = self.trace()
        for event in bad["events"]:
            if event["state"] == "baseline-complete": event["elapsedSeconds"] = 4.9
        with self.assertRaisesRegex(ValueError, "two complete cycles"):
            transition.validate_trace(self.schedule, self.rosters[0], bad)

    def test_strict_json_rejects_duplicates_constants_and_numeric_overflow(self):
        for text in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '{"nested":[1e999]}'):
            path = self.area / "bad.json"; path.write_text(text)
            with self.subTest(text=text), self.assertRaises(ValueError):
                transition.strict_json(path)

    def test_pin_rejects_extra_fields_relative_changed_and_conflicts(self):
        for value in ({"path": "relative", "sha256": "a"*64},
                      {**self.schedule_pin, "approval": True},
                      {**self.schedule_pin, "sha256": "f"*64}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                transition.Inputs().pin(value)
        inputs = transition.Inputs(); inputs.pin(self.schedule_pin)
        Path(self.schedule_pin["path"]).write_text("{}")
        with self.assertRaises(ValueError): inputs.finish()


class NativeSourceTests(TransitionFixture):
    def setUp(self):
        super().setUp()
        self.parent_dir = self.area / "parent"; self.parent_dir.mkdir()
        self.parent_resources = {n: ("parent:" + n).encode() for n in transition.MODULE}
        self.decoded = {"Creature List": {"type": "list", "value": self.actor_rows(self.rosters[0])}}
        for name, data in self.parent_resources.items(): write(self.parent_dir / "module-resources" / name, data)
        self.parent_module = native_archive(self.parent_dir / "parent.mod", self.parent_resources)
        self.stock = write(self.area / "stock.json", {})
        parent_proof = write(self.parent_dir / "source-proof.json", {"kind": "original-GIT-only-test-proof"})
        self.parent = {"sourceProof": parent_proof, "postureRoster": self.roster_pins[0],
            "postureStockBinding": self.stock, "module": self.parent_module["path"],
            "moduleSha256": self.parent_module["sha256"],
            "moduleResourceHashes": {n: contract.sha(self.parent_dir / "module-resources" / n)
                                     for n in self.parent_resources},
            "fixtureResourceHashes": {n: hashlib.sha256(n.encode()).hexdigest() for n in transition.FIXTURES},
            "stockTableBaselines": {}}
        parent_pin = write(self.parent_dir / "preparation.json", self.parent)
        tool = write(self.area / "tools/compiler.exe", b"test compiler")
        self.gff = write(self.area / "tools/gff.exe", b"test decoder")
        self.header = write(self.area / "header.nss", b"test installed header")
        source_pins, output_pins, commands = {}, {}, []
        for name in sorted(transition.SOURCES):
            source_pins[name] = write(self.area / "compiled" / name, ("new reviewed " + name).encode())
            out = Path(name).with_suffix(".ncs").name
            payload = name.encode()
            output_pins[out] = write(self.area / "compiled" / out,
                                    b"NCS V1.0B" + struct.pack(">I", 13 + len(payload)) + payload)
            log = write(self.area / "compiled" / (name + ".log"), b"")
            commands.append({"source": name, "output": out, "argv": [tool["path"], source_pins[name]["path"]],
                             "exitCode": 0, "stdout": log, "stderr": log})
        self.compiled = {"schemaVersion": 1, "kind": "executed-shared-female-transition-script-compile",
            **self.binding, **{flag: False for flag in transition.FALSE_FLAGS}, "compilerTool": tool,
            "header": self.header, "sources": source_pins, "outputs": output_pins, "commands": commands,
            "scriptCompileCalls": 2,
            "frozenInputs": {p["path"]: p["sha256"] for p in (tool, self.header, *source_pins.values())}}
        self.compile_pin = write(self.area / "compile.json", self.compiled)
        self.schedule["sourceNSSHashes"] = {n: p["sha256"] for n, p in source_pins.items()}
        self.schedule_pin = write(self.area / "schedule.json", self.schedule)
        self.resources = dict(self.parent_resources)
        for name, entry in {**source_pins, **output_pins}.items():
            self.resources[name] = Path(entry["path"]).read_bytes()
        self.child_module = native_archive(self.area / "child.mod", self.resources)
        self.proof = {"schemaVersion": 1, "kind": "shared-female-stockbody-transition-native-source-proof",
            **self.binding, **{flag: False for flag in transition.FALSE_FLAGS},
            "parentPreparation": parent_pin, "parentSourceProof": parent_proof,
            "postureRoster": self.roster_pins[0], "postureStockBinding": self.stock,
            "selectedOverlay": write(self.area / "selected-overlay.json", {}),
            "schedule": self.schedule_pin, "compileExecution": self.compile_pin,
            "nativeModule": self.child_module,
            "nativeGIT": pin(self.parent_dir / "module-resources/sr_tm_floor.git"),
            "decodedNativeGIT": write(self.area / "decoded-git.json", self.decoded),
            "moduleResourceHashes": {n: hashlib.sha256(b).hexdigest() for n, b in self.resources.items()},
            "protected11ModuleResourceHashes": {n: hashlib.sha256(b).hexdigest() for n, b in self.parent_resources.items()
                                                if n not in transition.CHANGED},
            "fixtureResourceHashes": self.parent["fixtureResourceHashes"], "stockTableBaselines": {},
            "operationCounts": {"nativeMODPackCalls": 1, "nativeGITEncodeCalls": 0, "modelCompileCalls": 0}}

    def actor_rows(self, roster):
        from shared_female_posture_fixture import GFF_FIELDS
        rows = []
        for actor in roster["actors"]:
            row = {"Tag": {"type": "cexostring", "value": actor["tag"]}}
            for name, (kind, key) in GFF_FIELDS.items(): row[name] = {"type": kind, "value": actor[key]}
            for name, value in actor["placement"].items(): row[name] = {"type": "float", "value": value}
            row["Equip_ItemList"] = {"type": "list", "value": []}
            row["VarTable"] = {"type": "list", "value": [{"Name": {"type": "cexostring", "value": name},
                "Type": {"type": "dword", "value": 1}, "Value": {"type": "int", "value": value}}
                for name, value in (("TM_POSE", actor["poseId"]), ("TM_PALETTE", actor["skinPalette"]))]}
            rows.append(row)
        return rows

    def run_factory(self):
        from contextlib import ExitStack
        proof_pin = write(self.area / "proof.json", self.proof)
        reports = {p["path"]: {"document": r, "frozenInputs": {p["path"]: p["sha256"]}}
                   for p, r in zip(self.roster_pins, self.rosters)}
        family = {root: {"sourceIdleNative": self.native_idle, "winningIdleOwner": "a_fa"}
                  for root in transition.ROOTS}
        native = {"clips": {c: {"length": 2., "transition": 1.} for c in ("pause1", "pause2")}}
        with ExitStack() as stack:
            stack.enter_context(patch.object(transition, "REPO", self.root))
            stack.enter_context(patch.object(transition, "current_helper_closure",
                                            side_effect=lambda inputs: inputs.add(Path(transition.__file__).resolve())))
            stack.enter_context(patch("shared_female_transition_fixture.contract.load", return_value=self.target))
            parent_guard = stack.enter_context(patch("pack_stock_target_fixture.verified_posture_stock_basis",
                return_value={"kind": "verified-shared-female-installed-stock-basis",
                    "postureStockBinding": self.stock, "postureRoster": self.roster_pins[0],
                    "coverage": self.coverage, "frozenInputs": {}}))
            stack.enter_context(patch("pack_stock_target_fixture.verified_animation_overlay",
                return_value={"resourceHashes": {n: "a"*64 for root in transition.ROOTS
                    for n in (root + ".mdl", "srn_fa_" + root[2:] + ".mdl")}, "frozenInputs": {}}))
            stack.enter_context(patch("shared_female_posture_fixture.verify_cumulative_coverage",
                                     return_value={"frozenInputs": {}}))
            stack.enter_context(patch("shared_female_posture_fixture.verify_roster",
                                     side_effect=lambda p, target: reports[p["path"]]))
            stack.enter_context(patch("shared_female_animation_overlay.load_family_plan", return_value=family))
            stack.enter_context(patch("target_animation_overlay.NativeIdleReader.decode", return_value=native))
            stack.enter_context(patch("target_animation_overlay.NativeIdleReader.__init__", return_value=None))
            stack.enter_context(patch("preflight_target_body_client.decode_gff", return_value=self.decoded))
            stack.enter_context(patch("shared_tools.resolve_tool", side_effect=lambda name, **kw:
                                     self.gff if name == "gff" else self.compiled["compilerTool"]))
            report = transition.verify_source(proof_pin, self.target_path, self.root, self.gff["path"],
                                             selected_overlay_pin=self.proof["selectedOverlay"])
            self.assertEqual(parent_guard.call_count, 1)
            self.assertEqual(parent_guard.call_args.args[2], self.parent)
            return report

    def test_end_to_end_native_container_preserves_parent_and_pending_acceptance(self):
        original = Path(self.parent_module["path"]).read_bytes()
        report = self.run_factory()
        self.assertEqual(len(report["moduleResourceHashes"]), 15)
        self.assertEqual(Path(self.parent_module["path"]).read_bytes(), original)
        self.assertFalse(report["visibleMotionProven"])
        self.assertFalse(report["clientAccepted"])

    def test_every_protected_resource_corruption_rejected(self):
        for name in transition.MODULE - transition.CHANGED:
            old = self.proof["moduleResourceHashes"][name]
            self.proof["moduleResourceHashes"][name] = "f"*64
            with self.subTest(name=name), self.assertRaises(ValueError): self.run_factory()
            self.proof["moduleResourceHashes"][name] = old

    def test_actual_archive_tamper_rejected_even_with_source_metadata(self):
        Path(self.child_module["path"]).write_bytes(b"invalid native module")
        with self.assertRaises(ValueError): self.run_factory()

    def test_stale_canonical_source_and_uncompiled_ncs_rejected(self):
        Path(self.compiled["sources"]["sr_tm_next.nss"]["path"]).write_bytes(b"stale source")
        with self.assertRaises(ValueError): self.run_factory()

    def test_parent_lineage_mismatch_and_approval_rejected(self):
        original = copy.deepcopy(self.proof)
        self.proof["parentSourceProof"] = self.stock
        with self.assertRaises(ValueError): self.run_factory()
        self.proof = copy.deepcopy(original); self.proof["clientAccepted"] = True
        with self.assertRaises(ValueError): self.run_factory()

    def test_boolean_operations_and_schema_rejected(self):
        self.proof["operationCounts"]["nativeMODPackCalls"] = True
        with self.assertRaises(ValueError): self.run_factory()
        self.proof["operationCounts"]["nativeMODPackCalls"] = 1
        self.proof["schemaVersion"] = True
        with self.assertRaises(ValueError): self.run_factory()

    def test_compiler_missing_consumed_header_and_failed_command_rejected(self):
        original = copy.deepcopy(self.compiled)
        self.compiled["frozenInputs"].pop(self.header["path"])
        self.proof["compileExecution"] = write(Path(self.compile_pin["path"]), self.compiled)
        with self.assertRaises(ValueError): self.run_factory()
        self.compiled = original; self.compiled["commands"][0]["exitCode"] = 1
        self.proof["compileExecution"] = write(Path(self.compile_pin["path"]), self.compiled)
        with self.assertRaises(ValueError): self.run_factory()

    def test_changed_fixture_and_extra_source_proof_field_rejected(self):
        self.proof["fixtureResourceHashes"] = {}
        with self.assertRaises(ValueError): self.run_factory()
        self.proof["fixtureResourceHashes"] = self.parent["fixtureResourceHashes"]
        self.proof["generalScriptExemption"] = True
        with self.assertRaises(ValueError): self.run_factory()


