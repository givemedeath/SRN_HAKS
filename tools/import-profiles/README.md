# HAK import profiles

A profile supplies archive-specific policy to `tools/Import-Hak.ps1`; generic inventory analysis can
run without one, but `Repair` and `Apply` always require a reviewed profile.

Required fields for schema version 1:

- `name`, `reportStem`, `expectedSha256`, and `expectedResourceCount` identify the import.
- `promotedTilesets` and `packNames` select clean SET files and their candidate landing packs.
- `paletteFiles` and `lightmapPrefixes` declare indirect resources that cannot be inferred reliably
  from ASCII model bitmap directives.
- `resourcePrefixes` assigns otherwise unreferenced legacy variants and indirect filename families
  to a candidate tileset pack. Prefixes must be narrow enough to avoid speculative ownership.
- `promotedEdges`, `deferredCompleteEdges`, and `edgesWithKnownAssetGaps` document edge-table status without treating localized missing assets as whole-tileset failures.
- `edgeModelExperiments` defines optional, quarantine-only edge-model remaps. Every target MDL
  must exist, every source must be referenced, and generated experiments are never activated by
  `Apply`.
- `customDoorRows` declares source and target `doortypes.2da` rows. Use an empty array when unused.
- `extensionPacks` maps simple resource extensions such as BMU and WAV to component packs.
- `genericDoorMerge`, `skyboxMerge`, and `indexedResourceTableMerges` generate reviewed global
  tables from the supplied EE baseline. Their tables must land in `srn_2da`; an optional
  `assetPack` keeps companion models and textures in their category pack.
- `stringRefRemaps` maps exact numeric tokens in generated 2DAs to active canonical TLK allocation
  keys and rejects any unexpected replacement count.
- `gffTransforms` supports reviewed binary GFF resources such as palettes. It can remove specifically
  identified list structures and uses `stringRefRemaps` to replace legacy TLK references before
  recompiling the resource; both removal and replacement counts are mandatory invariants.
- `indexedResourceTableMerges.allowedTargetTokens` permits named reservation markers such as
  `OS_RESERVED` while still refusing active baseline rows. `reportResourceColumn` identifies the
  source column recorded in allocation reports when it is not the table's second column.
- `futureDoorRows` scopes deferred source-to-target door-row rewrites to a specific tileset.
- `candidateDoorRows` records the complete reviewed row allocation for later candidate validation.
- `excludedBaseResources` prevents known unsafe base-game overrides.
- `quarantinedResources` explicitly defers named resources even when another rule would land them.
- `excludedResources` explicitly drops named resources from promoted output while retaining source accounting.
- `resourceRenames` repairs an explicitly reviewed invalid source identity at landing time while the
  original name and bytes remain in quarantine. Analyze records both names and rejects duplicate
  target identities.
- `registerPacks` lists the packs that `Apply` adds to `hakbuilder.json`.
- `expectedOverrides` declares reviewed cross-HAK duplicate identities and their complete provider
  lists. Apply merges these into `hakbuilder.json` and refuses a conflicting prior declaration.
- `reportNotes` contains archive-specific findings included in the generated report.

Every pack name must follow the repository's lowercase `srn_*` convention and remain at most 16
characters. `OutputRelativePath` is never stored in a profile: callers choose a contained workspace
beneath `.quarantine/` for every run.

A schema-version-1 TLK import profile for `tools/Import-Tlk.ps1` uses `name`, `reportStem`,
`expectedSha256`, and `entries`. Each entry declares a stable `key`, `owner`, and either a
pinned `sourceId` plus `expectedText`, or explicit synthesized `text` with a documented
`reason`. Exact normalized payloads are deduplicated against active canonical entries, with the
requested key retained as a validated alias of the canonical allocation.
