"""Typed actor coverage and actual matched-package payload regressions."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import target_contract as contract
import shared_female_animation_overlay as overlay
import shared_female_posture_fixture as fixture
from shared_female_native_contract import ROOTS
from test_shared_female_animation_overlay import write
from test_target_animation_overlay import pin, sha

def simple_rows():
    return {root:{"actorCases":[{"raceId":r,"appearanceId":a,"phenotypeId":int(root[3]),"femaleRoot":root}
        for r,a in overlay.RACES[root[2]]]} for root in ROOTS}

def actor(tag,root,race,appearance,pose,purpose="required-case"):
    return {"tag":tag,"purpose":purpose,"raceId":race,"appearanceId":appearance,"gender":1,
        "phenotypeId":int(root[3]),"femaleRoot":root,"headStyle":1,"bodyStyle":1,
        "skinPalette":3 if int(tag[3:])<4 else 8,"poseId":pose,"clip":("pause1","pause2")[pose],
        "equipment":[],"placement":{"XPosition":16+int(tag[3:])*3,"YPosition":16,
            "ZPosition":0,"XOrientation":0,"YOrientation":-1}}

def roster(batch="batch-1",cases=None):
    if cases is None:cases=[("pfa0",3,3),("pfd0",0,0),("pfe0",1,1),("pfg0",2,2)]
    actors=[]
    for root,race,appearance in cases:
        for pose in (0,1):actors.append(actor("tm_"+str(len(actors)),root,race,appearance,pose))
    while len(actors)<8:
        actors.append(actor("tm_"+str(len(actors)),"pfh0",6,6,len(actors)%2,"equipment-control"))
    return {"schemaVersion":1,"kind":"shared-female-posture-actor-roster",
        "familyPreparation":{"path":"family.json","sha256":"a"*64},"batchId":batch,
        "moduleName":"srn_female_test","actorAreaResref":"sr_tm_floor","bodySource":"installed-stock-shared-female",
        "actors":actors,**{k:"synthetic" for k in overlay.BINDING_FIELDS}}

def native_rows(roster_):
    result=[]
    for a in roster_["actors"]:
        row={"Tag":{"type":"cexostring","value":a["tag"]},
            "Equip_ItemList":{"type":"list","value":[{"__struct_id":g["slotMask"],
                "EquippedRes":{"type":"resref","value":g["resref"]}} for g in a["equipment"]]},
            "VarTable":{"type":"list","value":[{"Name":{"type":"cexostring","value":k},
                "Type":{"type":"dword","value":1},"Value":{"type":"int","value":v}}
                for k,v in (("TM_POSE",a["poseId"]),("TM_PALETTE",a["skinPalette"]))]}}
        row.update({field:{"type":kind,"value":a[key]} for field,(kind,key) in fixture.GFF_FIELDS.items()})
        row.update({field:{"type":"float","value":value} for field,value in a["placement"].items()})
        result.append(row)
    return result

def archive_file(path,resources,kind=b"HAK "):
    header=bytearray(160);header[:4]=kind;header[4:8]=b"V1.0"
    count=len(resources);keys_at=160;resources_at=160+24*count;payload_at=resources_at+8*count
    struct.pack_into("<I",header,16,count);struct.pack_into("<II",header,24,keys_at,resources_at)
    keys=bytearray();locations=bytearray();payload=bytearray()
    for i,(name,typ,data) in enumerate(resources):
        keys.extend(struct.pack("<16sIHH",name.encode(),i,typ,0))
        locations.extend(struct.pack("<II",payload_at+len(payload),len(data)));payload.extend(data)
    path.write_bytes(header+keys+locations+payload)


class RosterBoundaryTests(unittest.TestCase):
    def setUp(self):self.roster=roster();self.rows=simple_rows()

    def test_complete_typed_actor_rows(self):
        cells=fixture.validate_roster_document(self.roster,self.rows)
        self.assertEqual(len(cells),8)
        self.assertEqual(fixture.validate_native_actor_rows(self.roster,native_rows(self.roster))["typedActors"],8)

    def test_missing_or_wrong_typed_head_rejected(self):
        for value in (None,{"type":"word","value":1},{"type":"byte","value":0}):
            rows=native_rows(self.roster)
            if value is None:del rows[0]["Appearance_Head"]
            else:rows[0]["Appearance_Head"]=value
            with self.assertRaisesRegex(ValueError,"Appearance_Head"):fixture.validate_native_actor_rows(self.roster,rows)

    def test_all_identity_types_are_checked(self):
        for key in ("Race","Gender","Phenotype","Appearance_Type"):
            rows=native_rows(self.roster);rows[0][key]["type"]="float"
            with self.assertRaises(ValueError):fixture.validate_native_actor_rows(self.roster,rows)

    def test_cross_family_and_extra_fields_rejected(self):
        self.roster["actors"][0]["raceId"]=6
        with self.assertRaisesRegex(ValueError,"identity"):fixture.validate_roster_document(self.roster,self.rows)
        self.roster=roster();self.roster["actors"][0]["assetApproved"]=True
        with self.assertRaisesRegex(ValueError,"purpose"):fixture.validate_roster_document(self.roster,self.rows)

    def test_duplicate_tags_or_coverage_do_not_pass(self):
        self.roster["actors"][0]["tag"]="tm_1"
        with self.assertRaises(ValueError):fixture.validate_roster_document(self.roster,self.rows)
        self.roster=roster();self.roster["actors"][1]["clip"]="pause1";self.roster["actors"][1]["poseId"]=0
        with self.assertRaisesRegex(ValueError,"Duplicate"):fixture.validate_roster_document(self.roster,self.rows)

    def test_boolean_identity_and_nonfinite_placement_rejected(self):
        self.roster["actors"][0]["gender"]=True
        with self.assertRaises(ValueError):fixture.validate_roster_document(self.roster,self.rows)
        self.roster=roster();self.roster["actors"][0]["placement"]["ZPosition"]=float("nan")
        with self.assertRaises(ValueError):fixture.validate_roster_document(self.roster,self.rows)

    def test_native_schedule_palette_and_equipment_are_checked(self):
        rows=native_rows(self.roster);rows[0]["VarTable"]["value"][0]["Value"]["value"]=1
        with self.assertRaisesRegex(ValueError,"schedule"):fixture.validate_native_actor_rows(self.roster,rows)
        rows=native_rows(self.roster);rows[0]["Equip_ItemList"]["value"].append(
            {"__struct_id":2,"EquippedRes":{"type":"resref","value":"unexpected"}})
        with self.assertRaisesRegex(ValueError,"equipment"):fixture.validate_native_actor_rows(self.roster,rows)

    def test_unknown_equipment_slot_inputs_rejected(self):
        self.roster["actors"][0]["equipment"]=[{"slotMask":2,"resref":"robe"}]
        with self.assertRaisesRegex(ValueError,"equipment"):fixture.validate_roster_document(self.roster,self.rows)

    def test_halfelf_is_distinct_from_human_even_with_shared_root(self):
        r=roster(cases=[("pfh0",4,4),("pfh0",6,6),("pfh2",4,4),("pfh2",6,6)])
        cells=fixture.validate_roster_document(r,self.rows)
        self.assertEqual(len(cells),8);self.assertEqual({x[0] for x in cells},{4,6})


class MatchedPackagesTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.folder=Path(temporary.name)
        self.animations={name:hashlib.sha256(name.encode()).hexdigest() for root in ROOTS
                         for name in (root+".mdl","srn_fa_"+root[2:]+".mdl")}
        self.stock=self.build("stock",False);self.candidate=self.build("candidate",True)

    def build(self,name,candidate):
        hak=self.folder/(name+".hak");module=self.folder/(name+".mod")
        resources=[("sr_tm",2013,b"same installed fixture floor"),("sr_tm_edge",2017,b"same edge table")]
        if candidate:resources += [(Path(n).stem,2002,n.encode()) for n in self.animations]
        archive_file(hak,resources);archive_file(module,[("module",2014,b"same native module")],b"MOD ")
        return {"hak":str(hak),"hakSha256":sha(hak),"module":str(module),"moduleSha256":sha(module),
            "bodyConverted":None,"rigConverted":None,"provisionalConverted":None,"clientAccepted":False,
            "moduleResourceHashes":{"module.ifo":"same"},"fixtureResourceHashes":{"sr_tm.set":hashlib.sha256(b"same installed fixture floor").hexdigest(),"sr_tm_edge.2da":hashlib.sha256(b"same edge table").hexdigest()},
            "configuration":{"cameraLock":False},"postureRoster":{"path":str(self.folder/"roster.json"),"sha256":"b"*64},
            "postureStockBinding":{"path":str(self.folder/"stock-binding.json"),"sha256":"c"*64},"gameRoot":str(self.folder),
            "animationResourceHashes":self.animations if candidate else {}}

    def test_actual_archive_only_24_animation_resources_differ(self):
        result=fixture.matched_payloads(self.stock,self.candidate,self.animations)
        self.assertEqual(result["animationResources"],24);self.assertFalse(result["clientAccepted"])
        self.assertTrue(result["nativeActorValidationRequired"])

    def test_forged_hash_and_mismatched_module_rejected(self):
        Path(self.stock["module"]).write_bytes(b"changed module")
        with self.assertRaisesRegex(ValueError,"hash"):fixture.matched_payloads(self.stock,self.candidate,self.animations)
        self.stock["moduleSha256"]=sha(self.stock["module"])
        with self.assertRaises(ValueError):fixture.matched_payloads(self.stock,self.candidate,self.animations)

    def test_additional_shared_or_male_resource_rejected(self):
        p=Path(self.candidate["hak"])
        resources=[("sr_tm",2013,b"same installed fixture floor"),("sr_tm_edge",2017,b"same edge table")]+[
            (Path(n).stem,2002,n.encode()) for n in self.animations]+[("pmh0",2002,b"unexpected")]
        archive_file(p,resources);self.candidate["hakSha256"]=sha(p)
        with self.assertRaisesRegex(ValueError,"Only"):fixture.matched_payloads(self.stock,self.candidate,self.animations)

    def test_changed_config_roster_or_accepted_asset_rejected(self):
        for key,value in (("configuration",{"cameraLock":True}),("postureRoster",{}),("clientAccepted",True)):
            original=self.candidate[key];self.candidate[key]=value
            with self.assertRaises(ValueError):fixture.matched_payloads(self.stock,self.candidate,self.animations)
            self.candidate[key]=original

    def test_incomplete_group_does_not_pass(self):
        short=dict(self.animations);short.pop(next(iter(short)))
        with self.assertRaisesRegex(ValueError,"24-resource"):fixture.matched_payloads(self.stock,self.candidate,short)




    def test_missing_or_different_stock_binding_and_game_rejected(self):
        for key, value in (("postureStockBinding", None), ("postureStockBinding", {}),
                           ("postureStockBinding", {"path": str(self.folder/"other.json"), "sha256": "c"*64}),
                           ("gameRoot", None), ("gameRoot", str(self.folder/"other-game"))):
            with self.subTest(key=key, value=value):
                original = self.candidate[key]
                self.candidate[key] = value
                with self.assertRaisesRegex(ValueError, "stockBinding|postureStockBinding|game root"):
                    fixture.matched_payloads(self.stock, self.candidate, self.animations)
                self.candidate[key] = original

    def test_absent_or_malformed_shared_authority_cannot_pass_by_equal_claims(self):
        for key, value in (("postureStockBinding", None),
                           ("postureStockBinding", {"path": "relative.json", "sha256": "b"*64}),
                           ("postureStockBinding", {"path": str(self.folder/"basis.json"), "sha256": "forged"}),
                           ("postureRoster", None), ("gameRoot", "relative-game")):
            with self.subTest(key=key, value=value):
                stock, candidate = copy.deepcopy(self.stock), copy.deepcopy(self.candidate)
                stock[key] = candidate[key] = value
                with self.assertRaises(ValueError):
                    fixture.matched_payloads(stock, candidate, self.animations)

class MatchedInstalledAuthorityTests(unittest.TestCase):
    """Routing mocks isolate the amendment; core native/basis suites remain real."""
    build = MatchedPackagesTests.build

    def setUp(self):
        from test_target_animation_overlay import SyntheticOverlay
        import shared_female_stock_basis as basis
        area = overlay.REPO/"output/phenotypes"/overlay.TARGET
        area.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(prefix="matched-stock-binding-test-", dir=area)
        self.addCleanup(temp.cleanup); self.folder = Path(temp.name)
        (self.folder/"human").mkdir(); self.human = SyntheticOverlay(self.folder/"human")
        self.animations = {name:hashlib.sha256(name.encode()).hexdigest() for root in ROOTS
                           for name in (root+".mdl", "srn_fa_"+root[2:]+".mdl")}
        self.roster_pin = write(self.folder/"roster.json", {"routingOnlyFixture": True})
        self.overlay_pin = write(self.folder/"overlay.json", {"routingOnlyFixture": True})
        self.basis_pin = write(self.folder/"stock-binding.json", {"routingOnlyFixture": True})
        self.stock = self.build("stock", False); self.candidate = self.build("candidate", True)
        for document in (self.stock, self.candidate):
            document.update(contract.binding(self.human.target_path, self.human.target, "runtime"))
            document.update(postureRoster=self.roster_pin, postureStockBinding=self.basis_pin)
        self.archive = self.folder/"installed-small.bif"
        self.archive.write_bytes(bytes(2*1024*1024))
        self.archive_sha = sha(self.archive)
        self.installed = {"frozenInputs": {str(self.archive.resolve()):self.archive_sha,
            self.basis_pin["path"]:self.basis_pin["sha256"]},
            "sourceAncestryResources":22, "headNeckEquipmentIndividuallyDecoded":False,
            "dynamicLimits":basis.LIMITS}
        p = patch.object(basis, "verify_stock_basis", return_value=self.installed)
        self.basis_guard = p.start(); self.addCleanup(p.stop)
        p = patch.object(fixture, "verify_roster", return_value={"frozenInputs":{
            self.roster_pin["path"]:self.roster_pin["sha256"]}})
        p.start(); self.addCleanup(p.stop)
        p = patch.object(overlay, "verify_shared_female_animation_overlay", return_value={
            "resourceHashes":self.animations, "frozenInputs":{self.overlay_pin["path"]:self.overlay_pin["sha256"]}})
        p.start(); self.addCleanup(p.stop)
        self.refresh()

    def refresh(self):
        self.stock_pin = write(self.folder/"stock-build.json", self.stock)
        self.candidate_pin = write(self.folder/"candidate-build.json", self.candidate)

    def verify(self, declared=None):
        return fixture.verify_matched_packages(self.stock_pin, self.candidate_pin, self.overlay_pin,
            self.roster_pin, self.human.target_path, declared_inputs=declared)

    def test_stock_basis_guard_runs_with_exact_authority_and_no_live_tool(self):
        result = self.verify()
        self.basis_guard.assert_called_once_with(self.basis_pin, self.human.target_path, self.roster_pin,
            game_root=self.stock["gameRoot"], live_source_lookup=False)
        self.assertEqual(result["postureStockBinding"], self.basis_pin)
        self.assertEqual(result["sourceAncestryResources"], 22)
        self.assertFalse(result["clientAccepted"]); self.assertFalse(result["productionAccepted"])
        self.assertFalse(result["liveSourceLookupExecuted"])
        self.assertEqual(result["frozenInputs"][str(self.archive.resolve())], self.archive_sha)

    def test_forged_pair_pass_claim_cannot_replace_basis_verification(self):
        self.stock["stockBasisVerified"] = self.candidate["stockBasisVerified"] = True
        self.refresh(); self.basis_guard.side_effect = ValueError("Fresh actual stock binding rejected")
        with self.assertRaisesRegex(ValueError, "actual stock binding"):
            self.verify()

    def test_cross_roster_and_cross_target_builds_fail_before_basis_use(self):
        self.candidate["postureRoster"] = self.roster_pin | {"sha256":"f"*64}
        self.refresh()
        with self.assertRaisesRegex(ValueError, "roster"): self.verify()
        self.basis_guard.assert_not_called()
        self.candidate["postureRoster"] = self.roster_pin
        self.candidate["targetId"] = "other-body"; self.refresh()
        with self.assertRaisesRegex(ValueError, "another target"): self.verify()
        self.basis_guard.assert_not_called()

    def test_streaming_collector_never_reads_installed_archive_into_memory(self):
        original = Path.read_bytes
        def bounded(path):
            if path.resolve() == self.archive.resolve():
                raise AssertionError("Installed archive must be streamed")
            return original(path)
        with patch.object(Path, "read_bytes", bounded):
            consumed = fixture.collect_matched_package_inputs(self.stock_pin, self.candidate_pin,
                self.overlay_pin, self.roster_pin, self.human.target_path)
        self.assertEqual(consumed[str(self.archive.resolve())], self.archive_sha)
        self.assertTrue({self.stock_pin["path"], self.candidate_pin["path"],
                         self.basis_pin["path"], self.roster_pin["path"],
                         self.overlay_pin["path"]} <= set(consumed))

    def test_complete_declared_union_required_including_installed_archive(self):
        consumed = self.verify()["frozenInputs"]
        self.assertEqual(self.verify(consumed)["frozenInputs"], consumed)
        incomplete = dict(consumed); incomplete.pop(str(self.archive.resolve()))
        with self.assertRaisesRegex(ValueError, "undeclared"): self.verify(incomplete)
        changed = dict(consumed); changed[str(self.archive.resolve())] = "0"*64
        with self.assertRaisesRegex(ValueError, "undeclared"): self.verify(changed)

    def test_conflicting_consumed_archive_digest_rejected(self):
        self.installed["frozenInputs"][str(self.archive.resolve())] = "f"*64
        with self.assertRaisesRegex(ValueError, "hash differs"): self.verify()

class CumulativeCoverageTests(unittest.TestCase):
    def setUp(self):
        from test_target_animation_overlay import SyntheticOverlay
        area=overlay.REPO/"output/phenotypes"/overlay.TARGET;area.mkdir(parents=True,exist_ok=True)
        temp=tempfile.TemporaryDirectory(prefix="shared-roster-test-",dir=area);self.addCleanup(temp.cleanup)
        self.folder=Path(temp.name);(self.folder/"human").mkdir();self.human=SyntheticOverlay(self.folder/"human")
        rows=[];cases=[]
        for root in ROOTS:
            parent,owner,scale=overlay.expected_identity(root)
            actor_cases=simple_rows()[root]["actorCases"];cases += [(root,x["raceId"],x["appearanceId"]) for x in actor_cases]
            rows.append({"root":root,"carrier":"srn_fa_"+root[2:],"originalParent":parent,"winningIdleOwner":owner,
                "carrierScale":1,"literalActorScaleToken":scale,"actorOwnedCarrierStaticNodes":56,
                "expectedEditedControllers":16,"expectedUntouchedControllers":78 if owner=="a_ba" else 84,
                "actorCases":actor_cases})
        self.family=write(self.folder/"families.json",{"kind":"UNEXECUTED-source-native-female-family-extension-preparation",
            "pass":True,"totalRoots":12,"standingActorCases":14,"productionAnimationResourceTotal":24,"rows":rows})
        self.rosters=[]
        for index in range(4):
            doc=roster(fixture.BATCHES[index],cases[index*4:index*4+4])
            doc.update(contract.binding(self.human.target_path,self.human.target,"runtime"))
            doc["familyPreparation"]=self.family
            self.rosters.append(write(self.folder/("batch"+str(index)+".json"),doc))
        self.manifest={"schemaVersion":1,"kind":"shared-female-posture-cumulative-coverage",
            **contract.binding(self.human.target_path,self.human.target,"runtime"),
            "familyPreparation":self.family,"rosters":self.rosters}
        self.path=self.folder/"coverage.json";self.refresh()
        p=patch.object(overlay,"FAMILY_SHA",self.family["sha256"]);p.start();self.addCleanup(p.stop)

    def refresh(self):write(self.path,self.manifest)

    def verify(self):return fixture.verify_cumulative_coverage(pin(self.path),self.human.target_path)

    def test_all_four_batches_cover_28_distinct_identity_idle_cells(self):
        result=self.verify();self.assertEqual(len(result["requiredCells"]),28)
        self.assertFalse(result["clientAccepted"])
        self.assertEqual(sum(c[0] in (4,6) for c in result["requiredCells"]),8)

    def test_equipment_control_cannot_replace_a_missing_required_cell(self):
        doc=overlay.strict_json(self.rosters[0]["path"]);doc["actors"][0]["purpose"]="equipment-control"
        self.manifest["rosters"][0]=write(Path(self.rosters[0]["path"]),doc);self.refresh()
        with self.assertRaisesRegex(ValueError,"28-cell"):self.verify()

    def test_duplicate_batch_or_missing_roster_fails_closed(self):
        self.manifest["rosters"][1]=self.manifest["rosters"][0];self.refresh()
        with self.assertRaises(ValueError):self.verify()
        self.manifest["rosters"]=self.rosters[:3];self.refresh()
        with self.assertRaises(ValueError):self.verify()

    def test_cross_target_roster_binding_rejected(self):
        doc=overlay.strict_json(self.rosters[0]["path"]);doc["targetId"]="another-body"
        self.manifest["rosters"][0]=write(Path(self.rosters[0]["path"]),doc);self.refresh()
        with self.assertRaisesRegex(ValueError,"another target"):self.verify()

    def test_cold_historical_metadata_is_not_scanned(self):
        result=self.verify()
        self.assertTrue(all("missing historical" not in path for path in result["frozenInputs"]))

if __name__=="__main__":unittest.main()
