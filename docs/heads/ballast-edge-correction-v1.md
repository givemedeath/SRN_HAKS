# Ballast brow and ear correction

Ballast remains pmg0_head019. Shade stretching amplified a soft brow fringe and baked ear highlights into pale outlines even though ownership was correct.

Headbatch face-v1 now enables palette.repairFeatureHighlights automatically. Brow repair uses nearby same-channel surface samples before the existing automatic game-size contrast search. Excessive ear highlights receive a continuous shoulder relative to plain face skin after seam repair. Authored skin masks, ownership and other materials remain protected. Eligible shades and corrected chart gutters are checked before shade-span statistics and the independent quality gate.

Feature-mask growth requires nearby same-channel anchors in 3D. This prevents UV adjacency alone from moving the ear treatment onto another surface, including skin beside a feature owned by a different material. Regression tests cover both cases. The helper and tests are registered in CI's dependency and measured-duration catalogs.

The saved approved palette/tone/UV checkpoint was replayed through this maintained quantizer. The final replay produced identical PLT bytes. The mesh and all 125 other pack resources are byte-identical; only Ballast's PLT changed. The existing contrast search chose 0.9 to retain feature clarity after removing the artificial white edge.

The rebuilt 126-resource srn_head HAK was checked in NWN:EE, loaded above srn_body with Ballast from the base HAK. Front, all four three-quarter views, gameplay distance and hair rows 63/117 were visually checked. Brows recolor with hair; the white brow fringe is removed and ear highlights are substantially reduced. Small pre-existing bright flecks in the back hair remain. Motion, equipment, multiplayer and server deployment were not repeated.

![Corrected client views](evidence/ballast-edge-correction-v1/client.png)

[Portable hashes and measurements](ballast-edge-correction-v1.json) record the original checkpoint hashes, unchanged geometry, final texture, quality metrics and loaded HAK. Historical reindex records remain unchanged. This revision is a pull request candidate; it has not been deployed to a server.

Validation: all 647 headkit tests and 45 CI catalog/scope tests passed after review. The nine feature-highlight regressions include distant UV islands, missing same-channel anchors, protected ink, same-channel gutters and light hair. The independent PLT quality gate, exact HAK payload check and client slot/row verification passed. Replaying with the surface-growth guard produced the same PLT bytes as the client-checked correction, so the gallery remains valid.
