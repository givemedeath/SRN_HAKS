# Locked Human bodies: c8 (2026-11-26)

The current locked Human bodies are **c8**: the c7 lock with new necks. The user asked for a more realistic female
neck, better neck geometry and fixes to the male neck, approved the c8 candidate ("Approve c8"), then, after the
in-game check, found the female neck "still looks a bit long" and picked a 3.5 cm head drop from four renders.

Manifest with every hash: [`human-bodies-lock-c8.json`](human-bodies-lock-c8.json). It references the c7 manifest
by hash. The c7 record ([`human-bodies-lock-c7.md`](human-bodies-lock-c7.md)) stays as written. c8 is published in
contract 1.6.0; every changed resource and its 1.5.0 hash is in
[`neck-c8/release-1.6.0.json`](neck-c8/release-1.6.0.json).

## What changed from c7

| Area | c8 | Files |
|---|---|---|
| Female neck (`pfh0`, `pfh2`) | 24-sided anatomical neck: round, about 32 cm round at mid-neck, sternocleidomastoid ridges, a throat hollow, a nape groove, a domed top under the jaw. Replaces the stock 16-face diamond | `pfh0_neck001.mdl`, `pfh2_neck001.mdl` |
| Female head height | `head_g` 3.5 cm lower in the rig: the neck runs 7.6 cm joint to joint instead of 11.1 cm. Rest stature 1.803 m (was 1.838 m) | `pfh0.mdl`, `pfh2.mdl` |
| Female collar | The chest rises into a trapezius slope from the collarbones to the back of the neck (`pfh0`: up to 3.4 cm, plus 1 cm of bulk behind the neck; `pfh2`, which already sloped: up to 1.2 cm). UVs, materials and textures unchanged; moved vertices get updated normals and tangents | `pfh0_chest001.mdl`, `pfh2_chest001.mdl` |
| Male neck (`pmh0`, `pmh2`) | Round neck, about 38 cm round, with the same muscle detail and a slight Adam's apple. Replaces the diamond whose 16 cm side points stuck out in `worship`, `kdfntdmg`, `castup` and `victoryfr` | `pmh0_neck001.mdl`, `pmh2_neck001.mdl` |
| Human male heads | `pmh0_head086` to `092` scaled by 1.06 about `head_g`. They measured 8.4 heads to the body with faces the size of the female heads. No head was moved | `srn_head` |

Unchanged: `neck_g` (stock and armour neck parts ride it), the male rigs and chests, every other part, the textures and
the animation libraries. The neck textures are plain skin PLTs, so the new necks keep them with new UVs. Outfits and
armour are not refitted here: armorkit owns them.

## Review

* **Offline:** matched front, side, back and three-quarter views against c7; all 9 female and 7 male library heads in
  `pause1`, `kdfntdmg`, `worship` and `getlowlp`, plus `whirlwind`, `plslashr` and `meditate` on the first candidate.
  No head needed repositioning. Slices through the collar show a continuous slope with no shelf.
* **Motion:** no holes in `pause1`, `whirlwind`, `plslashr`, `kdfntdmg`, `2wslasho`, `worship`, `victoryfr` or `sit` on
  any of the four bodies, the same as c7. One stray pixel on `pfh2` in `plslashr` comes from the head mesh's own
  faces and is gone without the head.
* **Client** (repository-built HAKs, isolated fixtures, frame limiter on, keyholing off): bare bodies with stock and
  library heads, standing (front, side, back), `getlow`, head back with arms up, and stock scale and leather armour.
  A c7 run of the same views is the comparison: [client-c7-vs-c8.jpg](neck-c8/evidence/client-c7-vs-c8.jpg).
* Evidence images: [`neck-c8/evidence/`](neck-c8/evidence/).

## Known limits

* Long hair (heads 030 and 036) sits deeper in the raised female shoulders at the back. It already clipped there in
  c7.
* Head 090 shows a light band under the jaw when the head tips back. The c7 run shows the same band: it is the head's
  own underside.
* Stock heads (skinmeshes) were checked in the client only, not offline. Other races are unchanged and not reviewed
  here.
* `tools/armorkit/seam-contract.json` (version 5) and `head-envelopes.json` are re-measured on c8. Outfits baked
  on version 4 keep their bakes; whether a neck piece needs a rebake is armorkit's decision.

## Where the files are

Generated build files are ignored by git, under `output/phenomorpher/neck-c8/`: the c7 decompiles (`c7-ascii`), the
builds (`c8c`, `c8d` for the 3.5 cm female rig and neck, `c8a-heads`), the stage, the tools snapshot (`tools/`, with
`SHA256SUMS`) and the client fixtures (`client`, `client2`, `client-c7`). Check them against the manifest before
reuse. Retiring this worktree first needs a verified durable copy.
