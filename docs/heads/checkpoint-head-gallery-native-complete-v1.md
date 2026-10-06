# Head and gallery checkpoint: native complete

Six male heads and the refreshable gallery are complete through native validation. Interactive client testing and production acceptance remain pending, as requested.

The saved module is `output/srn_gallery.mod`, with inspection overlay `output/srn_gallery_test.hak`. The isolated user tree is `output/gallery/run-v8/build/user`. These generated files remain ignored; the reusable builder, staging configuration and compact [validation evidence](../../test-modules/srn_gallery/validation.json) are tracked.

The current explicit local resume binding is `output/gallery/local/resume-ledger-gallery-complete-v1.json`, SHA-256 `2aec1407e54eb6941e8b840ab054b538cf7231bb1d9ae4b7a39b420bf3a87583`. It links the previous head ledger, working selection, fresh migration receipt, completed gallery launch, catalog, payload audit and saved copies. Use this binding to resume; historical stop checkpoints remain unchanged. The prior head migration receipt is historical; new launches use the gallery migration bound here.

All 237 helper tests, repository and item-import regressions pass. The complete gallery freezes its inputs before dispatch, verifies native payloads and rechecks input bytes afterward. Opening the saved module in NWN does not run those checks.

Meshy spend remains 345 of 405 credits, with no outstanding reservations. Source masters remain in ignored primary-checkout banks; no retirement or deletion occurred. Client slot, palette, lighting, equipment and motion inspection is the next acceptance gate.
