# Gallery startup investigation

The installed NWN EE 89.8193.37-17 client crashes during module loading when the
generated inspection SET resources use LF line endings. Explicit CRLF exports
allow the complete 75-area gallery to start and load starting-area objects.
This establishes a startup gate, not visual approval of heads or tile geometry.

The investigation preserved the failed fixtures and ran sequential client tests
with fixed module resources, HAK payloads and order, area layout, and launch
method. Each client observation lasted 24 seconds; the full-gallery test lasted
30 seconds. Success required both a live process and evidence of starting-area
placeable loading. Surviving at a missing-HAK error screen did not count.

| Controlled comparison | Result |
| --- | --- |
| 64-entry SET, LF | Crashed, repeated twice |
| Identical 64-entry SET, CRLF | Started and loaded starting-area objects |
| 429-entry SET, CRLF | Started and loaded starting-area objects |
| 64-entry SET under a seven-character alias, CRLF | Started and loaded starting-area objects |
| Stock edge table absent versus present, CRLF | Both started |
| Original archive versus native repack, identical resource bytes, CRLF | Both started |
| All 75 areas, 74 inspection SETs changed from LF to CRLF | Started and loaded starting-area objects |

Earlier comparisons suggested an entry-count limit, but mixed line endings
invalidated that inference. The controlled results do not support that limit.
The precise internal engine failure has not been established; no engine code or
installed hooks were changed.

The exporter now writes CP1252 SET payloads with explicit CRLF independently of
the host platform. Its regression test rejects lone LF bytes. Inspection sheets
preserve original tile model identities and use stock display metadata; their
catalog maps each runtime tile to its original SET and tile ID. Production HAKs
and source models remain byte-identical. Imported production SET files are still
LF in the repository; these sheet tests do not establish that their unmodified
production metadata loads safely in a consumer module.

Operational fixtures, full logs, runtime bindings, and launch receipts remain
ignored. Compact hashes and observations are recorded in
`test-modules/srn_gallery/startup-validation.json`. Full visual client inspection,
motion, recoloring, helmets, and production acceptance remain separate gates.

## Starting-area objects and layout

After startup was fixed, the user reported missing NPCs and inaccessible page
controls. Embedded creature and placeable records retained blueprint struct IDs
instead of GIT instance IDs 4 and 9. The builder now creates typed instances
without mutating their source blueprints. Controls use visible floor levers
instead of wall-mounted buttons, and stand ahead of the player spawn.

Two matching NPC rows occupy a separate eastern bay: six body specimens and six
wearing the installed Clothing 1 item (`nw_aarcl001`). The installed item was
extracted and inspected locally; no stock item binary is redistributed. Client
script logs confirm 12 NPC instances, the selected head slots, and six equipped
clothing items. This does not approve clothing fit on the derived bodies.

The configured bay starts at (104, 28), uses six-unit column spacing and twelve-unit
row spacing, and lies beyond the object grid's maximum anchor x=74. The
**Male race rows** control and `.gallery pilots` jump to (114, 16).
`.gallery home` returns to the ordinary spawn. Layout is editable in `gallery.json`.
