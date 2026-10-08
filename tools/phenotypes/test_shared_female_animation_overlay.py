"""Synthetic wire-layout tests; no installed model or engine acceptance."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import target_contract as contract
import target_animation_overlay as human
import shared_female_animation_overlay as overlay
import shared_female_native_contract as native
from test_target_animation_overlay import NativeFixture, control, PART_JOINTS, SyntheticOverlay, pin, sha

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return pin(path)


class FamilyFixture:
    """Independent declarative source/parent/result writer; decoder is not used."""
    def __init__(self, folder, root="pfa0"):
        self.folder = Path(folder); self.folder.mkdir(parents=True)
        self.root, self.carrier = root, "srn_fa_"+root[2:]
        self.parent, self.owner, scale = native.expected_identity(root)
        self.scale = {"a":"0.64", "d":"0.65", "e":"0.894", "g":"0.64", "h":"1.0", "o":"1.0"}[root[2]]
        self.names = ["rootdummy", *PART_JOINTS.values(), *["fixture"+str(i).zfill(2) for i in range(38)]]
        self.parents = {n:"rootdummy" for n in self.names}; self.parents["rootdummy"] = root
        self.parents.update(lthigh_g="pelvis_g", rthigh_g="pelvis_g", lshin_g="lthigh_g",
            rshin_g="rthigh_g", lfoot_g="lshin_g", rfoot_g="rshin_g")
        lines = [f"newmodel {root}", f"setsupermodel {root} {self.parent}", f"setanimationscale {self.scale}",
            f"beginmodelgeom {root}", f"node dummy {root}", " parent null",
            " position 0 0 0", " orientation 0 0 0 0", "endnode"]
        for name in self.names:
            lines += [f"node dummy {name}", f" parent {self.parents[name]}", " position 0 0 0",
                      " orientation 0 0 0 0", "endnode"]
        lines += [f"endmodelgeom {root}", f"donemodel {root}"]
        self.source_root = self.folder/"installed-root.mdl"
        self.source_root.write_bytes(("\r\n".join(lines)+"\r\n").encode())
        self.linked_root = self.folder/(root+".mdl")
        token = self.source_root.read_bytes().index(f"{root} {self.parent}".encode())+len(root)+1
        self.token = [token, token+len(self.parent)]
        raw = self.source_root.read_bytes()
        self.linked_root.write_bytes(raw[:token]+self.carrier.encode()+raw[self.token[1]:])
        controls = [control(8, [[0,0,0]]), control(20, [[0,0,0,1]])]
        def geometry(alias, inherited):
            result = [{"name":alias,"parent":None,"controls":copy.deepcopy(controls)}]
            result += [{"name":n,"parent":alias if self.parents[n]==root else self.parents[n],
                        "controls":copy.deepcopy(controls)} for n in self.names]
            if inherited:
                result += [{"name":n,"parent":"pelvis_g","flags":33,"faces":1,"vertices":3,
                    "texture":"stock_cloth","controls":copy.deepcopy(controls)} for n in sorted(native.INHERITED)]
            return result
        untouched = ["fixture"+str(i).zfill(2) for i in range(38)]+["torso_g","neck_g","head_g","lbicep_g"]
        if self.owner=="a_ba": untouched=untouched[:39]
        self.numeric = {}
        def clips(alias):
            result=[]
            for clip in ("pause1","pause2"):
                nodes=[{"name":alias,"parent":None,"controls":[]}]
                for name in self.names:
                    cs=[]
                    if name in native.ALTERED:
                        typ=native.ALTERED[name]; values=[[0,0,0],[0,0,0]] if typ==8 else [[0,0,0,1],[0,0,0,1]]
                        cs.append(control(typ, values, [0,1]))
                        self.numeric[root+"|"+clip+"|"+name+"|times"]=np.array([0,1],dtype="<f4")
                        self.numeric[root+"|"+clip+"|"+name+"|values"]=np.array(values,dtype="<f4")
                    if name in untouched:cs.append(control(20,[[0,0,0,1],[0,0,0,1]],[0,1]))
                    nodes.append({"name":name,"parent":alias if self.parents[name]==root else self.parents[name],"controls":cs})
                result.append({"name":clip,"nodes":nodes})
            return result
        self.source_fixture=NativeFixture(self.owner,geometry(self.owner,True),clips(self.owner),parent="null")
        self.final_fixture=NativeFixture(self.carrier,geometry(self.carrier,False),clips(self.carrier),parent=self.parent)
        self.source_native=self.folder/"source-native.mdl";self.source_native.write_bytes(self.source_fixture.blob())
        self.result=self.folder/(self.carrier+".mdl");self.result.write_bytes(self.final_fixture.blob())
        self.compiled=self.folder/"compiled-parent.mdl"
        parent_bytes=bytearray(self.result.read_bytes())
        location=self.final_fixture.locations[("pause1","fixture00")]["ranges"][20]["dataRange"][0]
        struct.pack_into("<f",parent_bytes,location,.001);self.compiled.write_bytes(parent_bytes)
        source_spans=self.source_fixture.locations[("pause1","fixture00")]["ranges"][20]
        dest_spans=self.final_fixture.locations[("pause1","fixture00")]["ranges"][20]
        self.rows=[]
        for field,generic in (("timeRange","timeAbsoluteRange"),("dataRange","valueAbsoluteRange")):
            sr,dr=source_spans[field],dest_spans[field]
            self.rows.append({"clip":"pause1","node":"fixture00","type":20,"field":generic,
                "sourceRange":sr,"destinationRange":dr,
                "sourceBytesSHA256":hashlib.sha256(self.source_native.read_bytes()[sr[0]:sr[1]]).hexdigest(),
                "destinationBytesSHA256":hashlib.sha256(self.compiled.read_bytes()[dr[0]:dr[1]]).hexdigest()})
        omissions=[]
        for name in sorted(native.INHERITED):
            declared={}
            for typ,values in ((8,[[0,0,0]]),(20,[[0,0,0,1]])):
                spans=self.source_fixture.locations[("geometry",name)]["ranges"][typ]
                tt,vv=np.array([0],dtype="<f4"),np.array(values,dtype="<f4")
                declared[str(typ)]={"times":tt.tolist(),"values":vv.tolist(),
                    "timeWords":tt.view("<u4").tolist(),"valueWords":vv.view("<u4").tolist(),
                    "timeRange":spans["timeRange"],"valueRange":spans["dataRange"],
                    "timePayloadSha256":hashlib.sha256(tt.tobytes()).hexdigest(),
                    "valuePayloadSha256":hashlib.sha256(vv.tobytes()).hexdigest()}
            omissions.append({"name":name,"owner":self.owner,"native":pin(self.source_native),"nativeFlags":33,
                "parent":"pelvis_g","faceCount":1,"nativeVertexCount":3,"textures":["stock_cloth","","",""],
                "literalNativeStaticControllers":declared})
        original_archive=self.folder/"original.npz";np.savez(original_archive,**self.numeric)
        owner_ascii=self.folder/"owner.mdl";owner_ascii.write_text(f"newmodel {self.owner}\nsetsupermodel {self.owner} null\n")
        self.row={"root":root,"carrier":self.carrier,"originalParent":self.parent,"winningIdleOwner":self.owner,
            "carrierScale":1,"literalActorScaleToken":self.scale,"actorOwnedCarrierStaticNodes":56,
            "expectedEditedControllers":16,"expectedUntouchedControllers":78 if self.owner=="a_ba" else 84,
            "actorCases":[{"raceId":r,"appearanceId":a,"phenotypeId":int(root[3]),"femaleRoot":root}
                          for r,a in overlay.RACES[root[2]]],
            "sourceActorRoot":pin(self.source_root),"sourceIdleNative":pin(self.source_native),
            "sourceIdleASCII":pin(owner_ascii),"originalNativeArchive":pin(original_archive),
            "sourceAncestry":[{"name":root,"native":pin(self.source_root),"ascii":pin(self.source_root)},
                              {"name":self.owner,"native":pin(self.source_native),"ascii":pin(owner_ascii)}],
            "inheritedStaticOmissions":omissions,
            "rootLinkPlan":{"absoluteParentTokenRangeBytes":self.token,"originalParentTokenASCII":self.parent,
                "newSupermodelName":self.carrier,"protectedPrefixSHA256":hashlib.sha256(raw[:token]).hexdigest(),
                "protectedSuffixSHA256":hashlib.sha256(raw[self.token[1]:]).hexdigest()}}
        self.corrected_ranges=[]
        for clip in ("pause1","pause2"):
            for name,typ in native.ALTERED.items():
                ranges=self.final_fixture.locations[(clip,name)]["ranges"][typ]
                self.corrected_ranges += [ranges["timeRange"],ranges["dataRange"]]

    def measured(self):
        skeleton=native.inherited_bind(self.row,native.ascii_bind(self.source_root.read_bytes(),self.root),
                                      lambda row:Path(row["path"]))
        return native.check_native(self.row,self.source_native.read_bytes(),self.compiled.read_bytes(),
                                   self.result.read_bytes(),skeleton,self.numeric)

    def entry(self, family_pin, numeric_pin, compiler):
        source=self.folder/"authored.mdl";source.write_bytes(b"synthetic author source")
        expected=self.folder/"expected.npz"
        np.savez(expected,**{k.removeprefix(self.root+"|"):v for k,v in self.numeric.items()})
        reservation=write(self.folder/"reservation.json",{"kind":"fresh-one-family-authoring-reservation"})
        prep=write(self.folder/"preparation.json",{"kind":"one-family-source-native-carrier-preparation",
            "targetId":overlay.TARGET,"familyPreparation":family_pin,"sourceActorRoot":pin(self.source_root),
            "sourceNativeOwner":pin(self.source_native),"compileCalls":0,"sourceASCII":pin(source),
            "numericExpectedArrays":pin(expected),"reservation":reservation})
        stdout=self.folder/"stdout.log";stdout.write_text("compile completed")
        stderr=self.folder/"stderr.log";stderr.write_text("")
        execution=write(self.folder/"execution.json",{"compileCalls":1,"exitCode":0,
            "interactiveClientLaunched":False,"native":pin(self.compiled),"stdout":pin(stdout),"stderr":pin(stderr),
            "command":[compiler["path"],"-userdirectory","isolated","compilemodel",self.carrier]})
        compilation=write(self.folder/"compile.json",{"kind":"one-family-source-native-compile",
            "rootId":self.root,"carrier":self.carrier,"familyPreparation":family_pin,"preparation":prep,
            "native":pin(self.compiled),"execution":execution,"restorationApplied":False,"resolvedNativeCompiler":compiler})
        plan=write(self.folder/"plan.json",{"kind":"independent-family-source-native-restoration-plan",
            "pass":True,"executed":False,"rootId":self.root,"carrier":self.carrier,
            "familyPreparation":family_pin,"compile":compilation,"preparation":prep,
            "parentNative":pin(self.compiled),"sourceNativeOriginal":pin(self.source_native),
            "numericArchive":numeric_pin,"rows":self.rows,"modifiedControllerRanges":self.corrected_ranges,
            "expectedResultSha256":sha(self.result),"copyRangeCount":len(self.rows),
            "copyByteCount":sum(x["destinationRange"][1]-x["destinationRange"][0] for x in self.rows)})
        restoration=write(self.folder/"restoration.json",{"kind":"executed-family-source-native-payload-restoration",
            "rootId":self.root,"carrier":self.carrier,"familyPreparation":family_pin,"rangePlan":plan,
            "source":pin(self.source_native),"parentNative":pin(self.compiled),"native":pin(self.result),
            "clientEvidence":False,"runtimeSelected":False,"ranges":2,
            "copiedBytes":sum(x["destinationRange"][1]-x["destinationRange"][0] for x in self.rows)})
        review=write(self.folder/"review.json",{"kind":"independent-family-source-native-posture-review",
            "pass":True,"phase":"after-restoration","targetId":overlay.TARGET,"rootId":self.root,
            "carrier":self.carrier,"familyPreparation":family_pin,"compile":compilation,
            "parentNative":pin(self.compiled),"native":pin(self.result),"originalSourceOwner":pin(self.source_native),
            "root":pin(self.source_root),"numericArchive":numeric_pin,"executedRestorationReceipt":restoration,
            "pendingRestoration":False,"allUneditedNativePayloadsExact":True,"outsideRestorationRangesByteExact":True,
            "editedTimestampWordsExact":True,"uneditedControllers":self.row["expectedUntouchedControllers"],
            "editedControllers":16,"staticOwners":56,"clientEvidence":False,"runtimeSelected":False})
        link=write(self.folder/"link.json",{"kind":"executed-family-parent-token-root-descendant",
            "targetId":overlay.TARGET,"rootId":self.root,"carrier":self.carrier,"familyPreparation":family_pin,
            "sourceRoot":pin(self.source_root),"rootResource":pin(self.linked_root),"carrierResource":pin(self.result),
            "sourceNativeOwner":pin(self.source_native),"preparation":prep,"compile":compilation,"rangePlan":plan,
            "restoration":restoration,"independentReview":review,"originalActorScaleToken":self.scale,"compilerCalls":0,
            "allOtherRootBytesExact":True,"staticHierarchyBytesPreserved":True,"productionAccepted":False,
            "clientEvidence":False,"runtimeSelected":False,"parentTokenEdit":{"sourceStart":self.token[0],
                "sourceEnd":self.token[1],"originalToken":self.parent,"newToken":self.carrier}})
        return {"kind":"executed-family-source-native-idle-overlay","sourceRoot":pin(self.source_root),
            "sourceNativeOwner":pin(self.source_native),"preparation":prep,"compile":compilation,
            "rangePlan":plan,"restoration":restoration,"independentReview":review,"rootLink":link,
            "resources":{self.root+".mdl":pin(self.linked_root),self.carrier+".mdl":pin(self.result)}}


class NativeFamilyTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.folder=Path(t.name)

    def test_source_exact_native_restoration_normal_and_dwarf(self):
        for root,count in (("pfa0",84),("pfd2",78)):
            f=FamilyFixture(self.folder/root,root);result=f.measured()
            self.assertEqual(result["rows"],f.rows);self.assertEqual(result["uneditedControllers"],count)
            self.assertEqual(result["finitePose"]["sourceFootDistanceMm"],0)
            self.assertFalse(result["finitePose"]["ancestorScaleProductApplied"])

    def test_root_token_only_with_original_scale_and_crlf(self):
        f=FamilyFixture(self.folder/"elf","pfe2")
        self.assertEqual(native.verify_root_token(f.row,f.source_root.read_bytes(),f.linked_root.read_bytes()),f.token)
        with self.assertRaisesRegex(ValueError,"parent token"):
            native.verify_root_token(f.row,f.source_root.read_bytes(),f.linked_root.read_bytes()+b"\r\n")

    def test_root_and_carrier_scale_identity_rejected(self):
        f=FamilyFixture(self.folder/"dwarf","pfd0")
        f.row["literalActorScaleToken"]="0.6565"
        with self.assertRaisesRegex(ValueError,"scale"):
            native.verify_root_token(f.row,f.source_root.read_bytes(),f.linked_root.read_bytes())

    def test_changed_unedited_native_payload_rejected(self):
        f=FamilyFixture(self.folder/"base")
        blob=bytearray(f.result.read_bytes())
        at=f.final_fixture.locations[("pause1","fixture00")]["ranges"][20]["dataRange"][0]
        struct.pack_into("<f",blob,at,.002);f.result.write_bytes(blob)
        with self.assertRaisesRegex(ValueError,"Untouched"):f.measured()

    def test_changed_edited_native_payload_and_time_rejected(self):
        for field in ("dataRange","timeRange"):
            f=FamilyFixture(self.folder/field)
            blob=bytearray(f.result.read_bytes())
            at=f.final_fixture.locations[("pause1","rootdummy")]["ranges"][8][field][0]
            struct.pack_into("<f",blob,at,.02);f.result.write_bytes(blob)
            with self.assertRaises(ValueError):f.measured()

    def test_native_static_shape_and_parent_mismatch_rejected(self):
        f=FamilyFixture(self.folder/"static")
        blob=bytearray(f.result.read_bytes())
        at=f.final_fixture.locations[("geometry","rootdummy")]["ranges"][8]["timeRange"][0]
        struct.pack_into("<f",blob,at,1);f.result.write_bytes(blob)
        with self.assertRaisesRegex(ValueError,"Static"):f.measured()

    def test_incomplete_bind_hierarchy_rejected(self):
        f=FamilyFixture(self.folder/"hierarchy")
        f.row["inheritedStaticOmissions"].pop()
        with self.assertRaisesRegex(ValueError,"four"):f.measured()

    def test_inherited_controller_words_are_independently_checked(self):
        f=FamilyFixture(self.folder/"inherited")
        f.row["inheritedStaticOmissions"][0]["literalNativeStaticControllers"]["8"]["valueWords"][0][0]=1
        with self.assertRaisesRegex(ValueError,"words"):f.measured()

    def test_actual_outside_restoration_bytes_rejected(self):
        f=FamilyFixture(self.folder/"outside")
        blob=bytearray(f.result.read_bytes());blob[-1]^=1;f.result.write_bytes(blob)
        with self.assertRaises(ValueError):f.measured()


class SharedOverlayTests(unittest.TestCase):
    def setUp(self):
        area=overlay.REPO/"output/phenotypes"/overlay.TARGET;area.mkdir(parents=True,exist_ok=True)
        t=tempfile.TemporaryDirectory(prefix="shared-overlay-test-",dir=area)
        self.addCleanup(t.cleanup);self.folder=Path(t.name)
        (self.folder/"human").mkdir()
        self.human=SyntheticOverlay(self.folder/"human")
        self.fixtures={root:FamilyFixture(self.folder/root,root) for root in native.ROOTS if root!="pfh0"}
        human_row=copy.deepcopy(self.fixtures["pfh2"].row)
        human_row.update(root="pfh0",carrier="srn_fa_h0",originalParent="a_fa",winningIdleOwner="a_fa",
            actorCases=[{"raceId":r,"appearanceId":a,"phenotypeId":0,"femaleRoot":"pfh0"} for r,a in ((4,4),(6,6))])
        rows=[human_row if r=="pfh0" else self.fixtures[r].row for r in native.ROOTS]
        self.family=write(self.folder/"families.json",{"kind":"UNEXECUTED-source-native-female-family-extension-preparation",
            "pass":True,"totalRoots":12,"standingActorCases":14,"productionAnimationResourceTotal":24,"rows":rows})
        arrays={}
        for f in self.fixtures.values():arrays.update(f.numeric)
        arrays.update(self.human.corrected_arrays)
        numeric=self.folder/"numeric.npz";np.savez(numeric,**arrays);self.numeric=pin(numeric)
        client=self.folder/"never-launched.exe";client.write_bytes(b"synthetic compiler identity")
        self.compiler={"path":str(client),"sha256":sha(client),"name":"nwn","origin":"installed"}
        self.entries={root:f.entry(self.family,self.numeric,self.compiler) for root,f in self.fixtures.items()}
        self.entries["pfh0"]={"kind":"existing-human-overlay","receipt":pin(self.human.receipt_path)}
        self.receipt={"schemaVersion":1,"kind":overlay.KIND,**contract.binding(self.human.target_path,self.human.target,"runtime"),
            "executed":True,"scope":"all-shared-female-standing-races","clientAccepted":False,"runtimeSelected":False,
            "productionAccepted":False,"familyPreparation":self.family,"numericCorrectedArrays":self.numeric,"families":self.entries}
        self.path=self.folder/"overlay.json";self.refresh()
        self.patchers=[patch.object(overlay,"FAMILY_SHA",self.family["sha256"]),
            patch.object(overlay,"NUMERIC_SHA",self.numeric["sha256"]),patch.object(overlay,"COMPILER_SHA",self.compiler["sha256"]),
            patch.object(human,"verify_animation_overlay",side_effect=self.human_report)]
        for p in self.patchers:p.start();self.addCleanup(p.stop)

    def refresh(self):write(self.path,self.receipt)

    def human_report(self,pin_,target):
        self.assertEqual(pin_,self.entries["pfh0"]["receipt"])
        resources=self.human.receipt["resources"]
        return {"resourceHashes":{n:p["sha256"] for n,p in resources.items()},
            "resourcePaths":{n:p["path"] for n,p in resources.items()},
            "frozenInputs":{self.human.receipt_path.resolve().as_posix():sha(self.human.receipt_path)},
            "compilerClientSha256":self.compiler["sha256"],"clientAccepted":False,"runtimeSelected":False}

    def verify(self,declared=None):
        return overlay.verify_shared_female_animation_overlay(pin(self.path),self.human.target_path,declared)

    def test_complete_24_resource_native_proof_and_human_delegation(self):
        result=self.verify();self.assertEqual(len(result["resourceHashes"]),24)
        self.assertEqual(result["familyReports"]["pfd2"]["uneditedControllers"],78)
        self.assertFalse(result["clientAccepted"]);self.assertFalse(result["productionAccepted"])
        human.verify_animation_overlay.assert_called_once()

    def test_exact_consumed_manifest_complete_and_missing_file_rejected(self):
        declared=overlay.collect_overlay_inputs(pin(self.path),self.human.target_path)
        self.verify(declared)
        del declared[str(self.fixtures["pfa0"].compiled.resolve())]
        with self.assertRaisesRegex(ValueError,"undeclared"):self.verify(declared)

    def test_acceptance_and_schema_flags_rejected(self):
        for key,value in (("executed",1),("schemaVersion",True),("clientAccepted",True),("runtimeSelected",True),
                          ("productionAccepted",True),("scope","production")):
            original=self.receipt[key];self.receipt[key]=value;self.refresh()
            with self.assertRaises(ValueError):self.verify()
            self.receipt[key]=original
        self.refresh()

    def test_missing_extra_and_cross_family_resources_rejected(self):
        entry=self.entries["pfa0"];original=copy.deepcopy(entry["resources"])
        for resources in ({}, {**original,"a_fa.mdl":pin(self.fixtures["pfa0"].source_native)},
                          self.entries["pfa2"]["resources"]):
            entry["resources"]=resources;self.refresh()
            with self.assertRaises(ValueError):self.verify()
        entry["resources"]=original;self.refresh()

    def test_forged_review_pass_cannot_hide_corrupted_native(self):
        f=self.fixtures["pfa0"];blob=bytearray(f.result.read_bytes())
        at=f.final_fixture.locations[("pause1","fixture00")]["ranges"][20]["dataRange"][0]
        struct.pack_into("<f",blob,at,.03);f.result.write_bytes(blob)
        new=pin(f.result);entry=self.entries["pfa0"];entry["resources"][f.carrier+".mdl"]=new
        for key in ("independentReview","restoration","rootLink"):
            doc=overlay.strict_json(entry[key]["path"])
            doc["carrierResource" if key=="rootLink" else "native"]=new
            entry[key]=write(Path(entry[key]["path"]),doc)
        self.refresh()
        # Updated descendants can still fail prior immutable review/restoration references.
        with self.assertRaises(ValueError):self.verify()

    def test_duplicate_json_field_rejected(self):
        self.path.write_text('{"kind":"x","kind":"y"}')
        with self.assertRaisesRegex(ValueError,"Duplicate"):self.verify()

    def test_extra_top_level_field_rejected(self):
        self.receipt["assetApproved"]=True;self.refresh()
        with self.assertRaises(ValueError):self.verify()

    def test_plan_wrong_family_static_or_actor_case_rejected(self):
        plan=overlay.strict_json(self.family["path"]);plan["rows"][0]["actorCases"][0]["raceId"]=6
        with self.assertRaisesRegex(ValueError,"actor cases"):overlay.validate_family_plan(plan)

    def test_conflicting_input_hash_rejected(self):
        inputs=overlay.Inputs(self.folder);path=self.folder/"probe.bin";path.write_bytes(b"a")
        inputs.add(path);path.write_bytes(b"b")
        with self.assertRaisesRegex(ValueError,"Conflicting"):inputs.add(path)



class InstalledActorASCIITests(unittest.TestCase):
    """Real hash-pinned stock export quirks; no asset mutation or approval."""
    @classmethod
    def setUpClass(cls):
        cls.plan_path = overlay.REPO/"output/phenotypes"/overlay.TARGET/"posture-source-native-family-extension-preparation-v1/plan.json"
        if not cls.plan_path.is_file():
            raise unittest.SkipTest("Hash-pinned installed stock parser fixtures are absent in this clean clone")
        if sha(cls.plan_path) != overlay.FAMILY_SHA:
            raise ValueError("Installed parser fixture family plan changed")
        cls.rows = overlay.validate_family_plan(overlay.strict_json(cls.plan_path))

    def source(self, root):
        pin_ = self.rows[root]["sourceActorRoot"]
        path = Path(pin_["path"])
        self.assertEqual(sha(path), pin_["sha256"])
        return path.read_bytes()

    def test_all_eleven_remaining_real_stock_bind_hierarchies(self):
        for root in native.ROOTS:
            if root == "pfh0":
                continue  # Human uses its unchanged independent verifier.
            with self.subTest(root=root):
                skeleton = native.ascii_bind(self.source(root), root)
                self.assertEqual(len(skeleton), 56)
                self.assertEqual(skeleton[root]["parent"], "null")
                self.assertEqual(skeleton["rootdummy"]["parent"], root)
                self.assertTrue(all(n["parent"] == "null" or n["parent"] in skeleton for n in skeleton.values()))

    def test_pfh2_exact_export_selects_last_proven_impact_declaration(self):
        raw = self.source("pfh2")
        self.assertEqual(hashlib.sha256(raw).hexdigest(), native.PFH2_DUPLICATE_IMPACT_SHA)
        skeleton = native.ascii_bind(raw, "pfh2")
        np.testing.assert_array_equal(skeleton["impact"]["position"], [-.00936768, .0934759, .222395])
        self.assertEqual(skeleton["impact"]["parent"], "torso_g")

    def test_modified_pfh2_source_cannot_use_duplicate_exception(self):
        raw = self.source("pfh2")
        # An irrelevant wirecolor edit must still remove the source-specific rule.
        changed = raw.replace(b"wirecolor", b"wirecol0r", 1)
        self.assertNotEqual(changed, raw)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            native.ascii_bind(changed, "pfh2")

    def test_duplicate_export_under_other_family_rejected(self):
        raw = self.source("pfh2")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            native.ascii_bind(raw, "pfa2")

    def test_non_dummy_in_remaining_real_stock_rejected(self):
        raw = self.source("pfa0").replace(b"node dummy torso_g", b"node trimesh torso_g", 1)
        with self.assertRaisesRegex(ValueError, "Non-dummy"):
            native.ascii_bind(raw, "pfa0")


class InstalledFixturePortabilityTests(unittest.TestCase):
    def test_absent_frozen_plan_is_explicitly_skipped(self):
        with patch.object(Path, "is_file", return_value=False):
            with self.assertRaises(unittest.SkipTest):
                InstalledActorASCIITests.setUpClass()

    def test_present_but_changed_frozen_plan_is_rejected(self):
        with patch.object(Path, "is_file", return_value=True), patch(__name__+".sha", return_value="f"*64):
            with self.assertRaisesRegex(ValueError, "plan changed"):
                InstalledActorASCIITests.setUpClass()

if __name__=="__main__":unittest.main()
