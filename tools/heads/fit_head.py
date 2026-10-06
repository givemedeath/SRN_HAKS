"""Fit annotated anatomical landmarks in NWN head-local coordinates."""
import argparse
from pathlib import Path
import numpy as np
from head_workflow import fit_similarity, pin, read, require, validate_target, verify_pins, write_fresh


def fit(config_path, output):
    config = read(config_path)
    require(config["kind"] == "srn-head-landmarks", "Explicit anatomical landmark declaration required")
    require(config["coordinateSpace"] == "nwn-head-local" and len(set(config["landmarkNames"])) >= 4,
            "Named landmarks in the approved head attachment frame required")
    verify_pins([config["source"], config["target"], *config["inputs"]])
    target = validate_target(read(config["target"]["path"]))
    require(len(config["landmarkNames"]) == len(config["sourceLandmarks"]) == len(config["targetLandmarks"]),
            "Landmark names/counts differ")
    result = fit_similarity(config["sourceLandmarks"], config["targetLandmarks"], target["landmarkTolerance"])
    result.update(kind="srn-head-fit", source=config["source"], target=config["target"],
                  sourceLandmarks=config["sourceLandmarks"], targetLandmarks=config["targetLandmarks"],
                  landmarkNames=config["landmarkNames"], localMatrix=result["matrix"], declaration=pin(config_path),
                  standingAccepted=False, motionAccepted=False, productionAccepted=False)
    write_fresh(output, result)
    return result


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args=parser.parse_args(); fit(args.config,args.output)
