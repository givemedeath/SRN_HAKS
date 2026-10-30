# Head texture quality plan (prototype and test)

Date: 2026-10-29 (rev 2, after the crosscheck below). Status: plan, not started.

Scope: prototypes outside the approved pipeline. No stage runs and no ledger or shipped-asset changes until a step passes its gate and the user approves adoption into headkit.

## Problem summary

Generated heads read worse than stock in the EE client. The causes are mostly texture content and how it is split across PLT channels. Resolution is not the main cause.

| Problem | Evidence | Root cause |
|---|---|---|
| Soft, low-contrast features | featureFocus 1.2 vs stock 1.6; 1K keeps 93-97% of the 4K bake's eye detail | Baked colour from the 3D generator; no painted darks |
| White blotches on brow/forehead | Every elf-male-a client check | Lighting in the design image carried into the base colour, then stretched to the top shades |
| Staircase edges at eyes/brows | Close-ups; stock 256 PLT is smooth | Features split across PLT channels per texel |
| Narrow shade ramps | 70-head audit (RUNBOOK 121) | Fixed: `palette.fullShadeRange` (commit 4ac7add4) |
| Fragile eye/brow masks | New rules needed per head | Channels guessed afterwards by colour and UV position |
| Brows not following hair colour | Near-black or two-tone brows | Design paints brows into skin |
| Face gets no extra texture detail | 7.9 vs 9.1 texels/cm; face/rest 1.0x vs 2.8x | Uniform per-head unwrap |

Known facts to keep:
- PLT layers: 0 skin, 1 hair, 2-3 armor, 4-5 cloth, 6-7 leather, 8-9 tattoo.
- Each texel has exactly one layer. EE smooths the decoded colour, so a boundary between layers blends over about one texel at most.
- Never use shade 254 when 255 is transparent: it renders as a reflection in the client.
- Stock elf male 01 uses only skin (61%) and hair (39%).
- Channel roles (user rule 2026-10-29):

  | Channel | Use |
  |---|---|
  | skin (0) | Face skin, eye whites, lids, lips, nose |
  | hair (1) | Hair, eyebrows, beards and stubble (user 2026-10-29) |
  | metal1, metal2 (2-3) | Cyberwear |
  | tattoo1 (8) | Iris, so eye colour is always player-selectable |
  | tattoo2 (9) | Open to the design: tattoos, scars, markings |

## Crosscheck (independent research, 2026-10-29)

| Plan assumption | What research says | Change to the plan |
|---|---|---|
| Iris on tattoo1 | Community head packs use the same convention: eyes recoloured through Tattoo 1 ([Vault head pack](https://neverwintervault.org/project/nwn1/hakpak/original-hakpak/alfa-gnome-heads), [nwn.wiki](https://nwn.wiki/x/K4uiAw)). NPCs that are never given a tattoo colour use the default row. | Kept. Added a check that the default tattoo1 row gives plausible eyes on NPCs. |
| Face parsing gives reliable masks | BiSeNet/CelebAMask-HQ parsers are trained on photos with limited pose range ([BiSeNet notes](https://yakhyo.github.io/blog/2024/11/face-parsing-bisenet/), [pose robustness](https://arxiv.org/html/2510.08096v1)). MediaPipe gives 478 landmarks including iris rings ([model](https://huggingface.co/senty-au/face_landmarks_detector-ONNX)). No evidence for stylised or non-human faces. | Made it a feasibility test first (step 0), across all races, with a cheap fallback (landmarks, then manual masks on the design image). |
| Remove baked lighting from the bake | TRELLIS.2 outputs a separate base colour that is meant to be albedo ([TRELLIS.2](https://microsoft.github.io/TRELLIS.2)), so the highlights most likely come from the design image, but this is not verified. Image-to-3D generators are known to carry input shading into the texture ([LDM](https://arxiv.org/html/2405.14580v3)). 3D de-lighting methods exist but are research-grade and heavy ([DANTE-W](https://arxiv.org/abs/2606.30677), [VideoMat](https://arxiv.org/html/2506.09665v1)). | Added a source check (step 3.0). Moved the fix earlier: flat-lit design prompts, plus an optional 2D de-light of the design image before generation. Kept a simple 3D-smoothed luminance divide as the existing-head fallback. |
| Wrap onto a standard head with shared UVs | Proven for giving heads one topology and consistent texture placement ([Schneider & Eisert](https://www.jvrb.org/jvrb/article/download/7.2010.7/pdf/1651), [Laplacian ICP](https://arxiv.org/pdf/2302.02194)), but no ready open-source pipeline. Large effort. | Made it conditional: only if steps 1-3 cannot reach the gates on per-head meshes. |
| Darks and contrast make features read | Low-resolution game-art practice: high contrast and clear shapes; eyes often get extra texture space ([Roblox face texturing](https://create.roblox.com/docs/en-us/art/characters/creating/texturing-face), [Polycount](https://polycount.com/discussion/comment/2288317)). | Kept the darks pass. Added an optional eye-chart cut so the eyes can get extra density. |
| Masks remove staircase edges | One layer per texel means boundaries cannot be anti-aliased. Masks only make boundaries follow smooth shapes. | New rule: hide layer boundaries inside dark lines (iris rim, lid line, brow edge) painted on both sides, and keep the boundary count inside the face low. |

What the plan does not fix: the 3D shape quality and the design itself. A weak design or geometry still needs a regenerated design within the slot cap (5 geometry submissions, 3 designs).

## Test heads and baselines

- **Heads:**
  - elf-male-c (`pme0_head022`): tuned prompts, eyes painted in skin. Primary test head.
  - elf-male-a (`pme0_head020`): tattoo iris, pale design. Hard case.
  - In step 0 only: one human, one orc, one dwarf and one Troll head.
- **Baselines:** stock `pme0_head001`, the shipped heads, and the current prototypes:
  - `review-evidence-size/face-priority*/browhair-*`
  - `skinface-*`
- **Client harness:** a scratch trial via `scripts/trial.sh`. Compare stock 01 beside the variants.
  - Hair rows 117 (red-brown), 17 (light grey) and 5 (red).
  - Three tattoo1 rows, plus the default row.
  - Views at 2.5 m, 0.9 m, and an eye zoom.

## Step 0 - Mask feasibility (1 session, go/no-go)

1. Run MediaPipe Face Landmarker and a BiSeNet CelebAMask-HQ parser on the approved front design images of the six test heads. Use the pinned vendored models in the shared tools root.
2. Score each head on whether it finds the face, the eye and iris landmarks, and the brow, lip and hair masks. Judge by overlay review.
3. **Go:** the parser or landmarks work on the elves and humans.
4. **Partial:** any race that fails gets landmarks-only masks or manual masks painted on the 2D design image. A mask per head takes minutes and is reviewable.

**Result (2026-10-29): GO.** Evidence is in `race-heads-v1/trials/maskfeas-v1/` (`RESULTS.md`).
- Landmarks and the parser worked on all six races: brows, eyes, iris centre, lips, nose and scalp hair.
- Carry into steps 1-2:
  - The MediaPipe iris radius is a prior, 5-15% large on the orc, dwarf and troll. Refine it from the image behind guards (change of at most 15%, left and right agreeing within 10%).
  - Clip the parser's eye mask to the landmark eye contour.
  - No parser class for beards, cyberwear, tattoos, scars, horns or tusks. Get these from colour/contrast segmentation guided by the feature inventory, or from a manual mask. They override the parser's hair label.
  - Beards and stubble go on hair (user decision 2026-10-29). They need their own mask, since the parser leaves them in skin. Stubble must be blended in with the hair mid-tones, like the brows, so it does not become a hard-edged block.

## Step 1 - Masks onto the mesh

1. Project the design-image labels onto the mesh through the existing front registration (`palette.design_reference` / `front_labels`), then into the 4K and 1K UV maps. Keep the edges soft.
2. Fill regions the front view cannot see (sides of the brows, eye corners) using 3D neighbours, never UV neighbours.
3. Output: one soft mask per feature in the head's UV, plus QA overlays.

**Gate:** masks cover the brows, eyes, iris and lips with no spill into the lids, temples or nose shadow, on both elves.

**Result on elf-male-c (2026-10-29): passed.** Evidence is in `race-heads-v1/trials/maskplt-v1/elf-male-c/masks`; the script is `review-kit/mask_project_proto.py`.
- The parser and landmarks run on the head's own orthographic front render (4K bake through the mesh), not the design image. The labels then share the mesh's camera, so no design-to-mesh registration is needed.
- Texels the front view sees take the soft masks by depth match. Unseen texels take the nearest seen value in 3D.
- Masks are padded into the chart gutters.

## Step 2 - PLT encoding from the masks

1. **Channels** (roles table above):
   - Hair, brows and beards go to hair; the iris goes to tattoo1.
   - Eye whites, lids, lips and nose go to skin.
   - Cyberwear goes to metal1 and metal2.
   - Design tattoos, scars and markings go to tattoo2.
2. **Hide each boundary in a dark line:**
   - Paint a dark ring on the iris edge, with the iris rim on tattoo1 and the matching lid shadow on skin.
   - Use the lid line as the edge of the eye white.
   - Darken the brow's outer edge slightly in hair shades. Fill the skin side with plain skin colour using 3D neighbours.
3. **Brow shades:** map them into the hair's mid tones so any hair colour shows.
4. **Iris shades:** full range on tattoo1, with a dark rim, a mid iris and one highlight.
5. **Shade mapping:** quantize with `full_range=True` (never shade 254 when 255 is transparent). Smooth shades within each channel and UV island.

**Gate (client):**
- Brows follow hair rows 117, 17 and 5 with no fringe.
- The iris follows three tattoo1 rows, and the default row looks plausible on an NPC.
- No visible staircase at 0.9 m.

**Result on elf-male-c (2026-10-29): passed except the default eye colour.** Evidence: `race-heads-v1/trials/stockcmp-v8/evidence/maskplt-client-sheet.png`. Script: `review-kit/mask_plt_proto.py`.
- **Brows:** follow hair rows 117, 17 and 5 with no fringe or specks.
- **Iris:** follows tattoo1 rows 26 (blue) and 153 (green).
- **At 2.5 m:** the brows, eyes and mouth read close to stock 01. No staircase at 0.9 m.
- **Fixes this needed** (RUNBOOK 124-126):
  - Re-pad ownership into the gutters after edits.
  - Make each 4x4 block take its colour only from texels of its majority channel.
  - Measure the brow edge by 3D distance.
- **Fails: the default tattoo1 row 0 (NPCs) gives pale cream eyes.** Row 0 is cream above shade ~96. An iris shade curve (gamma 1.5, median 64) is not enough. **User decision (2026-10-29):** keep the plain full-range iris shades. NPC blueprints using these heads always set a tattoo1 (eye) colour.

**Result on elf-male-a (2026-10-29): passed.** Evidence: `race-heads-v1/trials/stockcmp-v9/evidence/elf-male-a-maskplt-client-sheet.png`.
- **Compared with the shipped head:** the shipped head had only pupils on white, red eye whites with hair row 5, and brows that barely show.
- **Brows:** follow hair rows 17, 117 and 5.
- **Irises:** now visible, and they follow tattoo1 rows 26 and 153. The circuit tattoo stays on tattoo2.
- **Fixes this head needed** (RUNBOOK 128-129):
  - Pale brows are found by colour around the parser's brow.
  - The brow edge is darkened only slightly.
  - Lash lines and the rings left by the old tattoo iris move to skin.
- **Remaining:** forehead white blotches (step 3) and a small spur at one brow tail.

## Step 3 - Lighting and darks

0. **Source check first:** compare the elf-male-a design image, the TRELLIS.2 base colour and our bake at the blotch locations. If the base colour is clean, the bake path is at fault, so fix that instead of de-lighting.
1. **Future heads:** design prompts ask for flat, even lighting with no shine.
2. **Optional:** a 2D de-light of the design image before generation. This changes the design input, so it is a new design attempt.
3. **Existing heads:** divide skin colour by a 3D-smoothed luminance (surface neighbours) to remove broad highlights. Clip the remaining top tail before tone matching.
4. **Darks inside skin, from the masks:**
   - upper-lid line;
   - socket shading around the eye mask;
   - lip line;
   - nostrils;
   - folds from the landmarks.
   Tune strengths against stock 01. Global geometry-based shadows were rejected: muddy sockets and seams.

**Gate:**
- At 2.5 m, the eyes, brows and mouth read at least as clearly as stock 01.
- No white blotches.
- featureFocus at or above the stock median (1.6); cheek noise at or below shipped.

## Step 4 - Optional texture density for the eyes

Cut each eye region into its own UV chart, from the mask, and give it about 2x the face density in the face-priority repack. The earlier eye-only weighting failed because the eyes shared charts with the face.

**Gate:** iris and lid edges visibly cleaner at 0.9 m than the face x3 layout alone.

## Step 5 - Automatic quality check

- Render a front preview at 100 px and a close-up (existing renderer, all triangles drawn).
- Metrics, each compared with the stock set:
  - featureFocus;
  - cheek noise;
  - shade span per channel;
  - share of top-shade texels;
  - number and length of layer boundaries inside the face.
- Calibrate the thresholds on steps 1-3 and stock. A head that fails is sent back before any client check.

## Step 6 - Conditional: standard head mesh with shared UVs

Start this only if steps 1-4 miss their gates because masks or density vary too much between heads.

- One base head per race and gender (or one shared base) with fixed feature positions in UV and face density about 3x the rest.
- A landmark-guided non-rigid fit, with colour transferred through 3D.
- It must respect the head/neck cut and keep the approved silhouette.
- Needs user approval, since it replaces the per-head unwrap.

## Step 7 - Design prompts (future heads only)

- Flat lighting.
- Distinct colours per feature (`claude/headkit-design-colours`).
- Brows in the hair colour with crisp edges.
- Defined dark lid lines.
- Non-glossy irises with a clear dark rim.
- No regeneration of existing heads without the user's decision (slot caps).

## Order and acceptance

1. Step 0, go/no-go.
2. Steps 1 and 2 on elf-male-c, then elf-male-a, with a client check each.
3. Step 3 with a client check, then step 4 if the eyes still look soft at 0.9 m.
4. Step 5, calibrated.
5. Decision point with the user: adopt steps 1-5 into headkit, or start step 6.
6. Step 7 for the next generation batch.

Every confirmed mistake gets a guard and a RUNBOOK row. Prototype scripts live in `S:/Scratch/claude-scratch/race-heads-v1/review-kit`, and evidence in the trials' `evidence/` folders.
