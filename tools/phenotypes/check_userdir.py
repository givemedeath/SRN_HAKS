"""Require NWN's configured resource aliases to match the isolated userdir."""
import argparse
import configparser
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("userdir", type=Path)
    args = parser.parse_args()
    root = args.userdir.resolve()
    config = configparser.ConfigParser(interpolation=None)
    config.read(root / "nwn.ini")
    required = {"HD0":"", "HAK":"hak", "MODULES":"modules", "OVERRIDE":"override",
                "LOGS":"logs", "CURRENTGAME":"currentgame", "MODELCOMPILER":"modelcompiler"}
    if not config.has_section("Alias"):
        raise RuntimeError("Missing Alias section; inspect the first client launch")
    errors = []
    for alias, relative in required.items():
        value = config.get("Alias", alias, fallback="")
        if not value or Path(value).resolve() != root / relative:
            errors.append(alias)
    if errors:
        raise RuntimeError("Resource aliases point outside the test userdir: " + ", ".join(errors))
    override = root / "override"
    if override.exists() and any(override.iterdir()):
        raise RuntimeError("Test override is not empty")
    print(json.dumps({"userDirectory": str(root), "aliasesVerified": list(required), "overrideEmpty":True}))


if __name__ == "__main__":
    main()
