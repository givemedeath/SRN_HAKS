"""Synthetic stock lineage and live lookup guards; no installed game is run."""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import target_contract as contract
import shared_female_animation_overlay as overlay
import shared_female_posture_fixture as fixture
import shared_female_stock_basis as basis
from shared_female_native_contract import ROOTS, expected_identity


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pin(path):
    return {"path":str(Path(path).resolve()), "sha256":sha(path)}


def write(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")
    return pin(path)


class StockBasisTests(unittest.TestCase):
    def setUp(self):
        area = basis.REPO/"output/phenotypes"/overlay.TARGET
        temporary = tempfile.TemporaryDirectory(dir=area, prefix="stock-basis-test-")
        self.addCleanup(temporary.cleanup)
        self.area = Path(temporary.name).resolve()
        self.target_path = self.area/"target.json"
        self.target_path.write_text("{}")
        ascii_root = self.area/"stock-root.mdl"; ascii_root.write_bytes(b"installed stock root")
        proof = write(self.area/"stock-reference.json",
            {"rootAscii":pin(ascii_root), "frozenInputs":{str(ascii_root):sha(ascii_root)}})
        self.target = {"id":overlay.TARGET, "rig":{"mode":"stock-exact", "revision":"synthetic",
            "runtimeScale":1, "stockReferenceReceipt":proof}, "identity":{"gender":"female",
            "prefix":"pfh0", "raceId":6, "appearanceRow":6, "phenotype":0}, "frozenInputs":{}}
        self.binding = contract.binding(self.target_path, self.target, "runtime")
        self.rows = {}
        self.native_files = {}
        for name in (*ROOTS, "a_fa", "a_fa2", "a_ba"):
            path = self.area/(name+"-native.mdl"); path.write_bytes(("original native "+name).encode())
            self.native_files[name] = pin(path)
        for root in ROOTS:
            parent, owner, scale = expected_identity(root)
            ascii_ = self.area/(root+"-ascii.mdl"); ascii_.write_bytes(("original ascii "+root).encode())
            original = self.area/(root+"-original.npz"); original.write_bytes(b"recorded numeric input")
            self.rows[root] = {"root":root, "carrier":"srn_fa_"+root[2:], "originalParent":parent,
                "winningIdleOwner":owner, "carrierScale":1, "literalActorScaleToken":str(scale),
                "actorOwnedCarrierStaticNodes":56, "expectedEditedControllers":16,
                "expectedUntouchedControllers":78 if owner=="a_ba" else 84,
                "actorCases":[{"raceId":r, "appearanceId":a, "phenotypeId":int(root[3]), "femaleRoot":root}
                    for r,a in overlay.RACES[root[2]]],
                "sourceActorRoot":pin(ascii_), "sourceIdleNative":self.native_files[owner],
                "sourceIdleASCII":pin(ascii_), "originalNativeArchive":pin(original),
                "sourceAncestry":[{"name":root, "native":self.native_files[root], "ascii":pin(ascii_)},
                    {"name":owner, "native":self.native_files[owner], "ascii":pin(ascii_)}],
                "inheritedStaticOmissions":[]}
        family = {"kind":"UNEXECUTED-source-native-female-family-extension-preparation", "pass":True,
            "totalRoots":12, "standingActorCases":14, "productionAnimationResourceTotal":24,
            "rows":list(self.rows.values())}
        self.family = write(self.area/"family.json", family)
        self.addCleanup(patch.stopall)
        patch.object(contract, "load", return_value=self.target).start()
        patch.object(overlay, "FAMILY_SHA", self.family["sha256"]).start()
        identities = sorted([x for row in self.rows.values() for x in row["actorCases"]],
                            key=lambda x:(x["raceId"],x["phenotypeId"]))
        self.rosters = []
        for i,batch in enumerate(fixture.BATCHES):
            specs = [(case,pose,"required-case") for case in identities[i*4:(i+1)*4] for pose in (0,1)]
            while len(specs)<8:
                specs.append((identities[0],len(specs)%2,"equipment-control"))
            actors = []
            for index,(case,pose,purpose) in enumerate(specs):
                actors.append({"tag":"tm_"+str(index), "purpose":purpose, **case, "gender":1,
                    "headStyle":1, "bodyStyle":1, "skinPalette":3 if index<4 else 8,
                    "poseId":pose, "clip":("pause1","pause2")[pose], "equipment":[],
                    "placement":{"XPosition":16+index, "YPosition":16, "ZPosition":0,
                                 "XOrientation":0, "YOrientation":-1}})
            roster = {"schemaVersion":1, "kind":"shared-female-posture-actor-roster",
                **self.binding, "familyPreparation":self.family, "batchId":batch,
                "moduleName":"srn_female_test", "actorAreaResref":"sr_tm_floor",
                "bodySource":"installed-stock-shared-female", "actors":actors}
            self.rosters.append(write(self.area/(batch+".json"), roster))
        # A pinned native/decoded stock UTI is consumed by the complete roster closure.
        gear = self.area/"gear.uti"; gear.write_bytes(b"original installed equipment")
        gear_json = write(self.area/"gear.json",
            {"TemplateResRef":{"type":"resref", "value":"stock_robe"}})
        r = json.loads(Path(self.rosters[-1]["path"]).read_text())
        r["actors"][-1]["equipment"] = [{"slotMask":2, "resref":"stock_robe",
            "nativeUTI":pin(gear), "decodedUTI":gear_json}]
        self.rosters[-1] = write(Path(self.rosters[-1]["path"]), r)
        self.gear = gear
        self.coverage = write(self.area/"coverage.json", {"schemaVersion":1,
            "kind":"shared-female-posture-cumulative-coverage", **self.binding,
            "familyPreparation":self.family, "rosters":self.rosters})
        source = self.area/"source"
        self.user = source/"source-userdir"
        for name in ("override","hak"):
            (self.user/name).mkdir(parents=True)
        self.parent = write(source/"preparation.json", {"kind":"target-fixture-source", **self.binding,
            "runtimeBodySource":"stock-human-female", "clientAccepted":False, "hakBuilt":False})
        self.source_proof = write(source/"proof.json", {"historicalNativeProof":True})
        self.decoded = write(source/"decoded.json", {"historicalNativeDecode":True})
        self.game = self.area/"game"
        (self.game/"data").mkdir(parents=True)
        for i in range(63):
            (self.game/"data"/("archive"+str(i)+(".bif" if i<61 else ".key"))).write_bytes(
                ("installed archive "+str(i)).encode())
        self.hashes = {str(p):sha(p) for p in (self.game/"data").iterdir()}
        self.inventory = write(self.area/"inventory.json", {"schemaVersion":1,
            "kind":"unexecuted-installed-data-archive-binding-input", "gameRoot":str(self.game),
            "archiveHashes":self.hashes, "archiveCount":63, "BIFCount":61, "KEYCount":2,
            "resourceReadsExecuted":False, "clientLaunched":False, "clientAccepted":False})
        self.client = self.game/"bin/win32/nwmain.exe"; self.client.parent.mkdir(parents=True)
        self.client.write_bytes(b"nonexecutable test client")
        patch.object(overlay, "COMPILER_SHA", sha(self.client)).start()
        tool = self.area/"resman_cat.exe"; tool.write_bytes(b"nonexecutable test resolver")
        self.resolved = {"name":"resman_cat", "path":str(tool), "version":"synthetic",
            "sha256":sha(tool), "origin":"downloaded", "toolsRoot":str(self.area),
            "rootOrigin":"argument", "inventorySha256":basis.shared_tools.sha(basis.REPO/"tools/shared-tools.lock.json")}
        self.resolver = patch.object(basis.shared_tools, "resolve_tool", return_value=self.resolved).start()
        self.config = write(self.area/"config.json", {"kind":"unexecuted-shared-female-stockbody-roster-preparation",
            "targetContract":pin(self.target_path), "familyPreparation":self.family,
            "sourcePreparation":self.parent, "sourceProof":self.source_proof, "sourceGITDecoded":self.decoded,
            "gameRoot":str(self.game), "toolsRoot":str(self.area), "installedArchiveInventory":self.inventory})
        flags = {k:False for k in basis.FALSE_FLAGS}
        self.recipe = write(self.area/"recipe.json", {"schemaVersion":1,
            "kind":"prepared-shared-female-stockbody-roster-recipe", **self.binding, **flags,
            "config":self.config, "familyPreparation":self.family, "coverage":self.coverage,
            "sourcePreparation":self.parent, "sourceProof":self.source_proof, "sourceGITDecoded":self.decoded,
            "batches":[{"batchId":name, "roster":p} for name,p in zip(fixture.BATCHES,self.rosters)]})
        ancestors = {}
        for row in self.rows.values():
            for entry in row["sourceAncestry"]:
                ancestors[entry["name"]+".mdl"] = {"native":entry["native"],
                    "installedLookupSha256":entry["native"]["sha256"], "byteExactToPinnedSource":True}
        commands = [{"command":[str(tool),"--root",str(self.game),"--userdirectory",str(self.user),"--no-ovr",name],
            "exitCode":0, "resourceName":name, "stdoutSha256":value["native"]["sha256"],
            "stdoutBytes":Path(value["native"]["path"]).stat().st_size, "stderr":""}
            for name,value in sorted(ancestors.items())]
        self.document = {"schemaVersion":1, "kind":basis.KIND, **self.binding, **flags,
            "familyPreparation":self.family, "coverage":self.coverage, "rosters":self.rosters,
            "rosterRecipe":self.recipe, "gameRoot":str(self.game), "sourceUserDirectory":str(self.user),
            "noOverrideLookup":True, "installedArchiveHashes":self.hashes, "installedArchiveCount":63,
            "BIFCount":61, "KEYCount":2, "sourceAncestryByResource":ancestors,
            "sourceAncestryResourceCount":len(ancestors), "resmanTool":self.resolved,
            "clientExecutable":pin(self.client), "headNeckEquipmentIndividuallyDecoded":False,
            "effectiveHeadNeckMaterialResolution":"installed-archives-dynamic-per-actor",
            "dynamicLimits":list(basis.LIMITS), "commands":commands,
            # Unused historical claims are not current executable dependencies.
            "frozenInputs":{str(self.area/"unread-history.bin"):"a"*64}}
        self.receipt = self.area/"stock-binding.json"

    def call(self, doc=None, **kwargs):
        entry = write(self.receipt, self.document if doc is None else doc)
        return basis.verify_stock_basis(entry, self.target_path, self.rosters[0],
            game_root=self.game, client_path=self.client, **kwargs)

    def test_complete_record_lineage_is_pending_and_no_resource_tool_runs(self):
        with patch.object(basis.subprocess, "run", side_effect=AssertionError("No resource tool")):
            report = self.call()
        self.assertEqual(len(report["requiredCells"]),28)
        self.assertFalse(report["liveSourceLookupExecuted"])
        self.assertTrue(report["recordedLookupsProveExecutionLineageOnly"])
        self.assertFalse(report["clientAccepted"])
        self.assertEqual(report["dynamicLimits"],basis.LIMITS)
        self.resolver.assert_called_with("resman_cat",basis.REPO,str(self.area))

    def test_collector_covers_actual_archives_helpers_gear_recipe_and_ancestry(self):
        entry = write(self.receipt,self.document)
        with patch.object(basis.subprocess,"run",side_effect=AssertionError("No resource tool")):
            pins = basis.collect_stock_basis_inputs(entry,self.target_path,self.rosters[0])
        required = {str(self.receipt),str(self.target_path),str(self.client),str(self.gear),
            self.family["path"],self.recipe["path"],self.config["path"],self.coverage["path"],
            self.inventory["path"],self.resolved["path"],str(Path(basis.__file__).resolve()),
            str(Path(fixture.__file__).resolve()),*self.hashes,*[p["path"] for p in self.rosters]}
        required.update(x["native"]["path"] for row in self.rows.values() for x in row["sourceAncestry"])
        required.update(x["ascii"]["path"] for row in self.rows.values() for x in row["sourceAncestry"])
        self.assertTrue(required <= set(pins),required-set(pins))
        self.assertNotIn(str(self.area/"unread-history.bin"),pins)
        for path,digest in pins.items():
            self.assertEqual(basis.shared_tools.sha(path),digest)

    def test_archives_added_removed_and_changed_reject_claimed_counts(self):
        path = next((self.game/"data").iterdir()); raw=path.read_bytes()
        path.write_bytes(b"changed archive")
        with self.assertRaisesRegex(ValueError,"hash differs"): self.call()
        path.write_bytes(raw); path.unlink()
        with self.assertRaisesRegex(ValueError,"inventory differs"): self.call()
        path.write_bytes(raw)
        extra=self.game/"data/undeclared.key";extra.write_bytes(b"extra")
        with self.assertRaisesRegex(ValueError,"inventory differs"): self.call()
        extra.unlink()
        bad=copy.deepcopy(self.document);bad["KEYCount"]=True
        with self.assertRaisesRegex(ValueError,"counts differ"):self.call(bad)

    def test_missing_duplicate_foreign_commands_and_false_success_claims_reject(self):
        changes = []
        a=copy.deepcopy(self.document);a["commands"].pop();changes.append(a)
        a=copy.deepcopy(self.document);a["commands"][1]=a["commands"][0];changes.append(a)
        for key,value in (("exitCode",1),("exitCode",False),("stdoutSha256","a"*64),
                          ("stdoutBytes",1),("stdoutBytes",True),("resourceName","pfh0_head001.mdl")):
            a=copy.deepcopy(self.document);a["commands"][0][key]=value;changes.append(a)
        for doc in changes:
            with self.subTest(doc=doc["commands"][0]),self.assertRaises(ValueError):self.call(doc)

    def test_no_override_command_and_lookup_directory_cannot_drift(self):
        for index,value in ((1,"--wrong-root"),(2,str(self.area)),(4,str(self.area)),(5,"--ovr")):
            bad=copy.deepcopy(self.document);bad["commands"][0]["command"][index]=value
            with self.subTest(index=index),self.assertRaisesRegex(ValueError,"command/result"):self.call(bad)
        for folder in ("override","hak"):
            path=self.user/folder/"unexpected.mdl";path.write_bytes(b"override")
            with self.subTest(folder=folder),self.assertRaisesRegex(ValueError,"empty override"):self.call()
            path.unlink()

    def test_false_flags_exact_disclosure_and_dynamic_claims_are_enforced(self):
        for key in (*basis.FALSE_FLAGS,"headNeckEquipmentIndividuallyDecoded"):
            bad=copy.deepcopy(self.document);bad[key]=True
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,"Diagnostic flags"):self.call(bad)
        bad=copy.deepcopy(self.document);bad["dynamicLimits"]=bad["dynamicLimits"][:2]
        with self.assertRaisesRegex(ValueError,"dynamic stock limits"):self.call(bad)
        bad=copy.deepcopy(self.document);bad["productionAccepted"]=0
        with self.assertRaisesRegex(ValueError,"Diagnostic flags"):self.call(bad)

    def test_selected_roster_complete_coverage_and_family_are_exact(self):
        entry=write(self.receipt,self.document)
        with self.assertRaisesRegex(ValueError,"membership"):
            basis.verify_stock_basis(entry,self.target_path,{"path":"foreign","sha256":"a"*64})
        bad=copy.deepcopy(self.document);bad["rosters"][1]=bad["rosters"][0]
        with self.assertRaisesRegex(ValueError,"coverage"):self.call(bad)
        bad=copy.deepcopy(self.document);bad["familyPreparation"]["sha256"]="a"*64
        with self.assertRaisesRegex(ValueError,"Foreign family"):self.call(bad)

    def test_source_ancestry_native_identity_and_current_bytes_are_required(self):
        bad=copy.deepcopy(self.document);bad["sourceAncestryByResource"].pop("pfa0.mdl")
        with self.assertRaisesRegex(ValueError,"ancestry resource"):self.call(bad)
        bad=copy.deepcopy(self.document)
        bad["sourceAncestryByResource"]["pfa0.mdl"]["native"]=self.native_files["pfd0"]
        with self.assertRaisesRegex(ValueError,"source identity"):self.call(bad)
        path=Path(self.native_files["pfa0"]["path"]);path.write_bytes(b"changed original")
        with self.assertRaisesRegex(ValueError,"hash differs"):self.call()

    def test_resolver_client_target_and_recipe_provenance_reject(self):
        bad=copy.deepcopy(self.document);bad["resmanTool"]["version"]="foreign"
        with self.assertRaisesRegex(ValueError,"merged resolver"):self.call(bad)
        bad=copy.deepcopy(self.document);bad["clientExecutable"]["sha256"]="a"*64
        with self.assertRaisesRegex(ValueError,"hash differs"):self.call(bad)
        bad=copy.deepcopy(self.document);bad["rigRevision"]="other"
        with self.assertRaisesRegex(ValueError,"another target"):self.call(bad)
        recipe=json.loads(Path(self.recipe["path"]).read_text())
        recipe["familyPreparation"]={"path":"foreign","sha256":"a"*64}
        bad=copy.deepcopy(self.document);bad["rosterRecipe"]=write(Path(self.recipe["path"]),recipe)
        with self.assertRaisesRegex(ValueError,"recipe lineage"):self.call(bad)

    def test_explicit_live_lookup_checks_fresh_bytes_once_per_resource(self):
        def run(argv,**kwargs):
            name=argv[-1];source=self.document["sourceAncestryByResource"][name]["native"]["path"]
            return SimpleNamespace(returncode=0,stdout=Path(source).read_bytes(),stderr=b"")
        with patch.object(basis.subprocess,"run",side_effect=run) as invoked:
            report=self.call(live_source_lookup=True)
        self.assertEqual(invoked.call_count,len(self.document["commands"]))
        self.assertTrue(report["liveSourceLookupExecuted"])
        self.assertFalse(report["recordedLookupsProveExecutionLineageOnly"])
        self.assertEqual(len(report["liveSourceLookupResults"]),len(self.document["commands"]))

    def test_live_lookup_wrong_stdout_nonzero_and_midrun_archive_drift_reject(self):
        for code,raw in ((0,b"wrong bytes"),(1,b"")):
            with patch.object(basis.subprocess,"run",return_value=SimpleNamespace(
                returncode=code,stdout=raw,stderr=b"")),self.assertRaisesRegex(ValueError,"Fresh installed"):
                self.call(live_source_lookup=True)
        changed=next((self.game/"data").iterdir());original=changed.read_bytes()
        def run(argv,**kwargs):
            changed.write_bytes(b"changed during live lookup")
            source=self.document["sourceAncestryByResource"][argv[-1]]["native"]["path"]
            return SimpleNamespace(returncode=0,stdout=Path(source).read_bytes(),stderr=b"")
        with patch.object(basis.subprocess,"run",side_effect=run),self.assertRaisesRegex(ValueError,"input drift"):
            self.call(live_source_lookup=True)
        changed.write_bytes(original)

    def test_declared_closure_requires_every_actual_read(self):
        report=self.call()
        declared=dict(report["frozenInputs"]);declared.pop(str(self.gear))
        with self.assertRaisesRegex(ValueError,"undeclared"):self.call(declared_inputs=declared)
        self.call(declared_inputs=report["frozenInputs"])


if __name__=="__main__":
    unittest.main()