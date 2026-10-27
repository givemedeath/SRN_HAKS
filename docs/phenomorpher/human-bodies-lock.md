# Locked Human bodies: c6 (2026-10-26)

> **Superseded as the current lock by [c7](human-bodies-lock-c7.md) (2026-10-27)**, which adds the Large male `pmh2`.
> The c6 record below is unchanged.

The current locked Human bodies are **combo-c6**, the build installed in the
`client-1.2.0-root-rebase/profile-combo` client. The user reviewed it in game. After an animation tour on
2026-10-26 they said "looks good", then asked to "record this as the current locked human bodies".

Manifest with every hash: [`human-bodies-lock-c6.json`](human-bodies-lock-c6.json).

## What is locked

| Area | Locked state | User review |
|---|---|---|
| Female hip and knee joins, pfh0 (Fit) and pfh2 (Large) | b13: male-style overlapping rounded thigh tops, rounded front pelvis hem, v39 knee fix | 2026-10-25 in-game tour: "Looks good" |
| Female torso polish, pfh0 and pfh2 | c6, built on b13: pelvis top-back rolled under the chest, rounded shoulder corners, rounded front-side belly hem (pfh2) | 2026-10-26 in-game tour: "looks good" |
| Skin textures | the rebuilt skin (re-bake on the final geometry, seam normals, normal blend) for every human-textured body, both genders | seen in the same client |

The pack holds 220 files that differ from the tracked `srn_body/` and `srn_body_tex/` trees:

* the 12 female models (pfh0 and pfh2 pelvis, legs, shins and chest);
* the re-baked PLT, normal and roughness textures;
* the `*2` MTRs.

Every other pack file is byte-identical to the tracked tree. The recipes, gates and evidence are in
[`female-joins/plan.md`](female-joins/plan.md) (the b13 and c6 entries).

## Status

* **Locked working selection.** This is the reference for any further body work. Later changes start from it
  and get a new, separately versioned lock; this record stays as written.
* **Not published.** `srn_body/` and `srn_body_tex/` in git are unchanged. Promoting c6 into them is the
  separate publication step. That step updates the asset manifests and publication validation
  (`game-ready-assets.json`, `publication-validation.json`, `docs/phenotypes/human-*-assets.json`) and runs the
  full target and client validation. It needs explicit approval and a PR.
* **Where the files are.** The locked files are generated output and ignored by git:
  * the ASCII sources: `output/phenomorpher/joins-pilot/c6-ascii-{pfh0,pfh2}`;
  * the compiled models: `joins-pilot/c6-compiled`;
  * the stage and haks: `output/phenomorpher/combo-c6`;
  * the tools snapshot: `joins-pilot/scratchpad-snapshot-2026-10-25`.

  Check them against the manifest before reuse. Retiring this worktree first needs a verified durable copy of
  them.
