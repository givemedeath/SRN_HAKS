"""Collect a finished trial robe into one self-describing package folder.

Copies the trial HAK, demo module and robe item from a fixture build, extracts the
padded parts_robe.2da, checks that the robe model, PLT and textures are byte-identical
to the ones the operator validated in the client, and writes manifest.json (hashes,
lineage, gate states, known limits) plus a short README. Gate states come from the
package configuration's operator records; production acceptance is never set here.
"""
import argparse
import json
import shutil
from pathlib import Path

from robe_common import pin, read, require, sha, utc, write_fresh

GATES = ("referenceApproval", "workingSelection", "nativeValidation", "clientValidation", "productionAcceptance")


def validated_matches(package_resources, validated_resources, names):
    """Names whose package bytes differ from (or are missing in) the client-validated build."""
    return sorted(n for n in names if package_resources.get(n) is None or package_resources.get(n) != validated_resources.get(n))


def row_line(path, row):
    lines = [line for line in Path(path).read_text(encoding="ascii").splitlines()[3:] if line.strip()]
    require(int(lines[row].split()[0]) == row, f"parts_robe.2da row {row} is not at its position")
    return lines[row]


def row_visibility(path, row):
    """Body parts the packaged parts_robe row hides and leaves visible (HIDE* columns)."""
    from parts_robe import read_2da
    columns, rows = read_2da(path)
    flags = {c[4:].lower(): rows[row][c] for c in columns if c.startswith("HIDE")}
    return sorted(p for p, v in flags.items() if v == "1"), sorted(p for p, v in flags.items() if v != "1")


def readme(config, manifest):
    gates = "\n".join(f"- **{name}**: {'yes' if gate['status'] else 'no'}. {gate['note']}"
                      for name, gate in manifest["gates"].items())
    limits = "\n".join("- " + item for item in config["knownLimits"])
    return f"""# {config['title']}

Trial package for stock human male phenotype 0. Not registered in srn_2da or hakbuilder.

## Contents

- `srn_robetrial.hak`: robe model `{config['model']}.mdl` (client-compiled binary), its skin PLT,
  fixed-colour MTR/TGA and a `parts_robe.2da` whose row {config['row']} hides {', '.join(manifest['hides']) or 'nothing'}
  and leaves {', '.join(manifest['visible']) or 'nothing'} visible.
- `{manifest['item']['file']}`: armour item (cloth base) using robe row {config['row']}.
- `srn_robetrial.mod`: demo module, stock robe004 beside the pilot on light and dark skin and with sword and shield.
- `parts_robe.2da`: the same table as a loose file. The engine reads 2DA rows by position, so any merge
  must keep row {config['row']} on line {config['row']} (pad unused rows with `****`).

## Gates

{gates}

## Known limits

{limits}

## Use

Put the HAK in a user `hak` folder and the module in `modules`, then load `srn_robetrial`. Polycount: {manifest['triangles']} triangles.
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--fixture-receipt", type=Path, required=True, help="fixture.json of the final package fixture build")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    config = read(args.config)
    require(config["kind"] == "srn-robe-package", "Robe package configuration required")
    require(not config["gates"]["productionAcceptance"]["status"], "Trial packages never claim production acceptance")
    require(set(config["gates"]) == set(GATES), "Gate set must be " + ", ".join(GATES))
    run_root = args.run_root.resolve()
    output = Path(args.output).resolve()
    require(not output.exists(), "Fresh package directory required")
    receipt = read(args.fixture_receipt)
    staging = Path(args.fixture_receipt).resolve().parent
    validated = read(run_root / config["validatedFixture"])
    row, model = config["row"], config["model"]
    shipped = [model + ".mdl", model + ".plt"] + sorted(n for n in receipt["hakResources"]
                                                         if n.endswith((".mtr", ".tga")))
    mismatched = validated_matches(receipt["hakResources"], validated["hakResources"], shipped)
    require(not mismatched, "Not the client-validated bytes: " + ", ".join(mismatched))
    require(receipt["partsRobeRows"][str(row)] == validated["partsRobeRows"][str(row)], "parts_robe row differs from the validated build")
    output.mkdir(parents=True)
    hak, module = Path(receipt["hak"]["path"]), Path(receipt["module"]["path"])
    require(sha(hak) == receipt["hak"]["sha256"] and sha(module) == receipt["module"]["sha256"], "Fixture outputs changed since the build")
    item = staging / "binary" / f"sr_rt_r{row}.uti"
    table = staging / "hak-resources" / "parts_robe.2da"
    require(sha(item) == receipt.get("items", {}).get(item.name), "Robe item missing from or changed since the fixture receipt")
    require(sha(table) == receipt["hakResources"]["parts_robe.2da"], "parts_robe.2da changed since the fixture build")
    for source in (hak, module, item, table):
        shutil.copyfile(source, output / source.name)
    line = row_line(output / "parts_robe.2da", row)
    hides, visible = row_visibility(output / "parts_robe.2da", row)
    model_report = read(run_root / config["lineage"]["model"])
    manifest = {"schemaVersion": 1, "kind": "srn-robe-trial-package", "createdUtc": utc(), "outfit": config["outfit"],
                "title": config["title"], "row": row, "model": model, "triangles": model_report["triangles"],
                "partsRobeRow": line.split(), "hides": hides, "visible": visible, "item": {"file": item.name, "label": config["itemLabel"]},
                "files": {p.name: sha(p) for p in sorted(output.iterdir())},
                "hakResources": receipt["hakResources"], "validatedAgainst": pin(run_root / config["validatedFixture"]),
                "fixtureReceipt": pin(args.fixture_receipt), "configuration": pin(args.config),
                "lineage": {key: pin(run_root / value) for key, value in config["lineage"].items()},
                "gates": config["gates"], "knownLimits": config["knownLimits"],
                "referenceApproved": config["gates"]["referenceApproval"]["status"],
                "nativeValidated": config["gates"]["nativeValidation"]["status"],
                "clientValidated": config["gates"]["clientValidation"]["status"],
                "productionAccepted": False, "gameClientTesting": False}
    (output / "README.md").write_text(readme(config, manifest), encoding="utf-8", newline="\n")
    manifest["files"]["README.md"] = sha(output / "README.md")
    print(json.dumps(write_fresh(output / "manifest.json", manifest)))


if __name__ == "__main__":
    main()
