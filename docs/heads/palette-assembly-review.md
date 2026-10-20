# Offline head palette assembly

`tools/heads/prepare_palette_assembly.py` decodes the actual head, body and neck PLTs into review atlases. Existing configurations keep `skinPalette`, `hairPalette`, `skinRow` and `hairRow` for channels0/1.

For any used channels2–9, add an explicit palette image and selector row under `paletteLayers`:

```json
{
  "paletteLayers": {
    "2": {"palette": {"path": "<metal palette image>", "sha256": "<SHA256>"}, "row": 0},
    "8": {"palette": {"path": "<tattoo palette image>", "sha256": "<SHA256>"}, "row": 87},
    "9": {"palette": {"path": "<tattoo palette image>", "sha256": "<SHA256>"}, "row": 89}
  }
}
```

These rows are illustrative; select the actual character's values for each review. Add every palette image to the configuration's frozen `inputs`, even when several channels use one image. String paths are also supported, with their matching pin in `inputs`. Palette images have256 shade columns and one RGB row per selector. Negative/out-of-range selectors, channel IDs outside0–9 and a used channel without a binding are rejected.

Channels2/3 are metals,4/5 cloth,6/7 leather and8/9 tattoos. Heads may intentionally use these selectors for hardware, horns/tusks or cybereyes. Bind them explicitly; do not substitute the skin or hair palette. The same channel bindings apply to head, body and stock-neck previews so their colors remain comparable. The generated `assembly.json` records the additional palette hashes and selected rows in `palettePreview.paletteLayers`.

Review decoded appearance and channel ownership at the hairline, ears, implants, horns and tusks. Vary the corresponding selectors independently and inspect joins against the body/neck. The legacy `semantic.png` fixed-material overlay remains separate from PLT channel IDs; semantic label2 is not automatically PLT channel2. Offline evidence does not replace in-game approval.
