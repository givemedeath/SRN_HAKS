# Head pilot review artifact origins

Contributor: SRN project operator with Codex. Date: 2026-10-05.

`reference-*.png` and corresponding `*-prompt.txt` are original SRN project
prompts and OpenAI-generated isolated-head turnaround sheets, edited to remove
projecting neck while preserving the complete skull, rounded chin and mandible. No external
photographs, identifiable-person references, third-party meshes or copied
character assets were supplied. The selected references were normalized to four
1024-square views; original prompts, source hashes and normalization ancestry are
in [the pilot catalog](../pilot-catalog.json).

`donor-*.png`, `human*-motion.png`, `human*-materials.png`, and
`troll-*-derived-v1.png` and `*-male-palette-motion-v1.png` contain renders of
**Meshy-generated assets (Meshy 7)**, created from those original reference views.
Meshy attribution: [Meshy](https://www.meshy.ai/). These images record modified
geometry (separately versioned local surface LOD, high-source normal bake,
uniform fit and hole caps; no neck trimming or taper), runtime palette materials,
and compact offline review layouts. Generated GLBs, maps, pre-remesh sources and
task receipts remain in the ignored source bank; their hashes and owning task IDs
are recorded in the catalog. AI provenance is preserved in this notice and manifest.

The account's paid/free tier has not been verified. Meshy's published
[license guidance](https://help.meshy.ai/en/articles/9992001-can-i-use-meshy-assets-commercially-license-copyright-explained)
states that paid users own generated assets when inputs are authorized, while
Free-plan assets use [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
with Meshy attribution. This delivery preserves Meshy attribution and identifies
all changes rather than claiming paid-tier ownership. If the Free-plan terms
apply, those rights remain CC BY 4.0; the repository's default PolyForm license
does not restrict or replace them. Production asset acceptance must verify the
applicable account terms and input rights before runtime publication.

The guidance and [Meshy terms](https://www.meshy.ai/terms-of-use) were checked on
2026-10-05. [API retention](https://docs.meshy.ai/en/api/asset-retention) is limited;
verified local copies preserve recovery and provenance. A source hash alone does
not establish backup coverage or authorize deleting a checkout.

Human assembly images also show the already published custom `srn_body` body
under its existing repository provenance. Troll assembly images use the male
body derived from that frozen Human master. Elf, Dwarf and Orc assembly images
also use their independently copied derived male bodies from `codex/derived-phenotypes`
at `be6391b437332eeae64ca3df54e952c9749a288d`; body bytes and rig node transforms
are preserved. Fixture rig serialization is separately versioned and parent-first;
original animation tails are retained and effective transforms audited.
`stock-neck-control.png` and neck/rig/
palette comparisons use locally installed NWN assets as offline validation
references. Installed stock models, rigs, palettes, animation libraries and
fixture templates are not redistributed in Git. The images are review evidence,
not an assertion of ownership over installed game content.

All artifacts in this directory are offline evidence. They do not record an
interactive client test or production acceptance.
