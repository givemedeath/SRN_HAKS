"""Freeze the completed root-owned native hand evidence without changing selection."""
from pathlib import Path
import hashlib
import json

WORKSPACE = Path(__file__).resolve().parents[3]
PILOT = Path(__file__).resolve().parent
ROOT = WORKSPACE / "output/phenotypes/human-male-complete-goal-v1"

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))

def pin(path):
    return {"path": str(path.resolve()), "sha256": sha(path)}

selection_path = PILOT / "selected-offline-v1/selection.json"
selection = read(selection_path)
assert sha(selection_path) == "10a51a41a8ec63689357c83d16fd311a50622639e465543719ae59dbec9951c2"
for entry in selection["parts"] + selection["evidence"]:
    assert sha(entry.get("source", entry.get("path"))) == entry["sha256"]

parts = []
for part in ("handl", "handr"):
    compile_path = ROOT / f"{part}-native-v1/human_male_fit/converted/native-compile.json"
    audit_path = ROOT / f"{part}-native-audit-v1/audit.json"
    compiled, audit = read(compile_path), read(audit_path)
    assert compiled["complete"] and compiled["executionMode"] == "compilemodel"
    assert not compiled["interactiveClientLaunched"]
    assert audit["pass"] and not audit["geometryModified"]
    assert all(audit["nativeCornersExactSourceFloat32"].values())
    assert all(v == 0 for v in audit["sourceToNativeOrderedCornerMaximumErrors"].values())
    assert audit["actualNativeTangentArrays"]["degenerateUvTriangles"] == 0
    assert audit["material"]["compileTimeDependenciesExact"]
    assert audit["material"]["normalTgaPixelsExact"]
    assert audit["material"]["pltExpectedDeclaredMaterialPixelsExact"]
    resource_dir = ROOT / f"{part}-native-v1/human_male_fit/converted/resources"
    for name, expected in compiled["materialResourceHashes"].items():
        assert sha(resource_dir / name) == expected
    model = compiled["models"][0]
    assert sha(resource_dir / model["name"]) == model["binarySha256"]
    parts.append({
        "part": part,
        "compileReceipt": pin(compile_path),
        "independentNativeAudit": pin(audit_path),
        "nativeModel": pin(resource_dir / model["name"]),
        "resources": [pin(path) for path in sorted(resource_dir.iterdir()) if path.is_file()],
        "nativeVertices": audit["nativeMesh"]["vertices"],
        "nativeTriangles": audit["nativeMesh"]["triangles"],
        "positionNormalUvFloat32Exact": audit["nativeCornersExactSourceFloat32"],
        "tangentSignMeasurement": audit["actualNativeTangentArrays"],
        "nativeMaterialDependenciesExact": True,
    })

assert parts[0]["tangentSignMeasurement"]["negativeHandednessVertices"] == parts[1]["tangentSignMeasurement"]["positiveHandednessVertices"]
assert parts[0]["tangentSignMeasurement"]["positiveHandednessVertices"] == parts[1]["tangentSignMeasurement"]["negativeHandednessVertices"]
material_path = ROOT / "hand-effective-materials-v1/material-operation.json"
material = read(material_path)
assert material["nativeGeometryAndNormalsExact"] and not material["clientAccepted"]
result = {
    "schemaVersion": 1,
    "status": "selected-hand-pair-compiled-and-independently-native-verified",
    "immutableOfflineSelection": pin(selection_path),
    "selectionReceiptChanged": False,
    "nativeCompilationPerformedBy": "coordinator, not hand worker",
    "parts": parts,
    "materialOperation": pin(material_path),
    "materialManifest": pin(ROOT / "hand-effective-materials-v1/body-resource-manifest.json"),
    "materialConfiguration": pin(ROOT / "hand-effective-materials-v1/executed-config.json"),
    "skinCalibration": pin(ROOT / "hand-calibrated-materials-v1/skin-calibration.json"),
    "materialScope": {
        "shadeOffset": -9,
        "currentForearm20mmMean": 107.4186,
        "newHand20mmMeanBeforeCalibration": 116.5448,
        "newHand20mmMeanAfterCalibration": 107.5448,
        "aoStrength": 0.35,
        "aoMaximumDarkenShades": 12,
        "aoMaximumBrightenShades": 3,
        "connectorProtectionMetres": 0.02,
        "connectorOutwardPlane": [0, 0, 1, 0],
        "normalMapStrength": 1,
        "roughness": "fresh ORM green to linear texture3 red",
        "acceptedNeighbourGeometryAndMaterialsModifiedByWorker": False,
    },
    "practicalMovingWrist": selection["practicalMovingWrist"],
    "disclosedGeometryAndEquipmentLimits": selection["disclosedLimits"][:3],
    "visualReviewScope": selection["visualReviewScope"],
    "clientTestedByWorker": False,
    "wholeBodyAccepted": False,
    "remainingCoordinatorGates": [
        "Cumulative complete-body assembly, inventory and packaging",
        "Authorized actual client palette, lighting, movement, equipment, stability and performance checks",
        "Full-body animation reference sheet and final goal evidence",
    ],
    "gpuRenderSlotReleased": True,
    "helper": pin(Path(__file__)),
}
destination = PILOT / "selected-offline-v1/native-handoff.json"
with destination.open("x", encoding="utf-8", newline="\n") as stream:
    json.dump(result, stream, indent=2)
    stream.write("\n")
assert sha(selection_path) == result["immutableOfflineSelection"]["sha256"]
print(json.dumps({"handoff": pin(destination), "nativeAudits": [p["independentNativeAudit"] for p in parts]}, indent=2))
