# SRN Orthographic Multi-View

## Overview
Additive six-view orthographic Pixal3D conditioning custom node extension for ComfyUI. It enables parallel-projection conditioning for measured phenotype part images by monkey-patching Trellis's `_project_points_to_image` function using negative camera span tags while preserving upstream perspective projections and weight samplers.

## Interface
- `SRNOrthographicMultiViewConditioning`: Custom ComfyUI node implementing six-view orthographic conditioning.
  - `define_schema()`: Declares input (`clip_vision_model`, `ortho_span`, view images: `front`, `left`, `back`, `right`, `top`, `bottom`) and output (`positive`, `negative`) schemas.
  - `execute(clip_vision_model, ortho_span, front, left=None, back=None, right=None, top=None, bottom=None)`: Prepares multi-view image batches and conditioning tensors with negative camera span tags.
- `SRNExtension`: ComfyUI extension class registering `SRNOrthographicMultiViewConditioning`.
  - `get_node_list()`: Returns `[SRNOrthographicMultiViewConditioning]`.
- `comfy_entrypoint()`: Async module entrypoint returning `SRNExtension()`.
- `project_points(points_world, transform_matrix, camera_angle_x, resolution)`: Orthographic and perspective point projection function replacing `trellis._project_points_to_image`.
- `checked_digest(module, expected)`: Verifies SHA-256 digests of upstream modules before patching.
- `self_test()`: CPU import validation gate checking camera bases, depth invariance, top/bottom camera orientations, and legacy perspective equality.
- Constants:
  - `MODEL_SHA256`: Expected SHA-256 digest (`baa8b081de2eada84754b867282bd21d498233816326f8842943857fe1d07e0c`) for `comfy.ldm.trellis2.model`.
  - `NODES_SHA256`: Expected SHA-256 digest (`5d99f8fd2d1a1cc252b860d941717fc4e53cfbc48b623730c9fdd9139dd7f98c`) for `comfy_extras.nodes_trellis2`.
  - `VIEWS`: View sequence tuple `('front', 'left', 'back', 'right', 'top', 'bottom')`.
  - `AZIMUTHS`: Azimuth angles `(0., 90., 180., 270., 0., 0.)`.
  - `ELEVATIONS`: Elevation angles `(0., 0., 0., 0., 90., -90.)`.
  - `IMPORT_TEST`: Result dictionary produced by import-time `self_test()`.

## Invariants
- `ortho_span` must be finite and within `[0.5, 2.0]` world units (`__init__.py:execute`, `__init__.py:project_points`).
- Upstream modules `trellis` and `upstream` must match exact pinned SHA-256 digests (`MODEL_SHA256`, `NODES_SHA256`) or `RuntimeError` is raised on import (`__init__.py:checked_digest`).
- Negative `camera_angle_x` values encode full orthographic world span (`-span`); non-negative values pass through unchanged to original perspective projector `_ORIGINAL` (`__init__.py:project_points`).
- In parallel projection, depth changes do not alter projected X/Y coordinates (`__init__.py:self_test`).
- Front view input image is required; remaining 5 views are optional (`__init__.py:define_schema`).
- Non-1024x1024 input images are resized to `1024x1024` using lanczos interpolation (`__init__.py:execute`).

## Side Effects
- Monkey-patches `trellis._project_points_to_image` on module import, restoring `_ORIGINAL` if `self_test()` raises (`__init__.py:71, 103`).
- Reads module file bytes to compute SHA-256 digests on import (`__init__.py:checked_digest`).
- Injects `srn_projection='orthographic-negative-span-v1'` and `srn_view_names` into ComfyUI conditioning output dictionaries (`__init__.py:execute`).

## Verification
- Run: `pytest tools/phenotypes`
