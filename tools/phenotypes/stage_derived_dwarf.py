import argparse
from pathlib import Path
import shutil

REPO = Path(__file__).resolve().parents[2]
SRN_BODY = REPO / "srn_body"

PARTS = [
    "bicepl", "bicepr", "chest", "footl", "footr", "forel", "forer",
    "handl", "handr", "legl", "legr", "pelvis", "shinl", "shinr"
]


def stage(race: str = "dwarf", prefix: str = "pmd0"):
    ascii_source = REPO / f"output/phenotypes/derived-v1/parts/{race}-male/ascii"
    target_root = REPO / f"output/phenotypes/derived-{race}-male-v1/candidate/converted"

    ascii_dir = target_root / "ascii"
    resources_dir = target_root / "resources"
    if ascii_dir.exists():
        shutil.rmtree(ascii_dir)
    if resources_dir.exists():
        shutil.rmtree(resources_dir)
    ascii_dir.mkdir(parents=True, exist_ok=True)
    resources_dir.mkdir(parents=True, exist_ok=True)

    for stale in target_root.glob("native-compile*"):
        if stale.is_file():
            stale.unlink()

    for part in PARTS:
        model_name = f"{prefix}_{part}001.mdl"
        src_mdl = ascii_source / model_name
        dst_mdl = ascii_dir / model_name
        shutil.copyfile(src_mdl, dst_mdl)

        # Copy PLT
        src_plt = SRN_BODY / f"pmh0_{part}001.plt"
        dst_plt = resources_dir / f"{prefix}_{part}001.plt"
        shutil.copyfile(src_plt, dst_plt)

        # MTR
        if part == "pelvis":
            (resources_dir / f"{prefix}_pelvis001.mtr").write_text(
                "renderhint NormalTangents\n"
                "texture1 pmh0_pelvis001n\n"
                "parameter float Roughness 0\n"
                "parameter float Specularity 0.04\n"
                "parameter float Metallicness 0.001\n"
                "texture3 pmh0_pelvis001r\n",
                encoding="ascii"
            )
            shutil.copyfile(SRN_BODY / "pmh0_pelvis001f.tga", resources_dir / f"{prefix}_pelvis001f.tga")
            (resources_dir / f"{prefix}_pelvis001f.mtr").write_text(
                "renderhint NormalTangents\n"
                f"texture0 {prefix}_pelvis001f\n"
                "texture1 pmh0_pelvis001n\n"
                "parameter float Roughness 0.72\n"
                "parameter float Specularity 0.04\n"
                "parameter float Metallicness 0.001\n",
                encoding="ascii"
            )
        else:
            (resources_dir / f"{prefix}_{part}001.mtr").write_text(
                "renderhint NormalTangents\n"
                f"texture1 pmh0_{part}001n\n"
                "parameter float Roughness 0\n"
                "parameter float Specularity 0.04\n"
                "parameter float Metallicness 0.001\n"
                f"texture3 pmh0_{part}001r\n",
                encoding="ascii"
            )

    staged_models = list(ascii_dir.glob("*.mdl"))
    if len(staged_models) != 14:
        raise RuntimeError(f"Expected exactly 14 staged models in {ascii_dir}, found {len(staged_models)}")

    print(f"Staged 14 ASCII models and material dependencies for {race} ({prefix}) to {target_root}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--race", type=str, default="dwarf", choices=["dwarf", "troll", "elf", "orc"])
    parser.add_argument("--prefix", type=str, default=None)
    args = parser.parse_args()

    default_prefixes = {"dwarf": "pmd0", "troll": "pmg0", "elf": "pme0", "orc": "pmo0"}
    prefix = args.prefix or default_prefixes.get(args.race, "pmd0")
    stage(race=args.race, prefix=prefix)


if __name__ == "__main__":
    main()
