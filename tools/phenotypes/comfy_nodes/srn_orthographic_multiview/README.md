# SRN Orthographic Multi-View

## Overview
Additive six-view orthographic Pixal3D conditioning node for measured phenotype part images. It adapts upstream Trellis and Pixal3D projection pipelines using a negative-span camera angle convention to dispatch parallel projection without modifying upstream model weights or sampling pipelines.

## Interface
- `SRNOrthographicMultiViewConditioning`: ComfyUI node class providing multi-view orthographic conditioning.
- `SRNOrthographicMultiViewConditioning.define_schema()`: Defines node input schema (`clip_vision_model`, `ortho_span`, six view images) and output schema (`positive`, `negative` conditioning).
- `SRNOrthographicMultiViewConditioning.execute(clip_vision_model, ortho_span, front, left=None, back=None, right=None, top=None, bottom=None)`: Batch-processes view images to 1024x1024 and constructs Pixal3D conditioning tagged with `orthographic-negative-span-v1`.
- `SRNExtension`: ComfyUI extension registering the node.
- `comfy_entrypoint()`: Async entrypoint returning the `SRNExtension` instance.
- `project_points(points_world, transform_matrix, camera_angle_x, resolution)`: Orthographic and perspective projection dispatcher monkey-patched onto Trellis.
- `checked_digest(module, expected)`: Verifies upstream module SHA-256 hashes against reviewed digests.
- `self_test()`: CPU validation gate verifying depth invariance, camera basis, and perspective exactness.
- `MODEL_SHA256`: Expected SHA-256 hash for upstream `trellis.py` (`baa8b081de2eada84754b867282bd21d498233816326f8842943857fe1d07e0c`).
- `NODES_SHA256`: Expected SHA-256 hash for upstream `nodes_trellis2.py` (`5d99f8fd2d1a1cc252b860d941717fc4e53cfbc48b623730c9fdd9139dd7f98c`).
- `VIEWS`: Tuple of supported view identifiers (`front`, `left`, `back`, `right`, `top`, `bottom`).
- `AZIMUTHS`: Camera azimuth rotations for the 6 views.
- `ELEVATIONS`: Camera elevation angles for the 6 views.
- `IMPORT_TEST`: Execution results of import self-tests.

## Invariants
- `[__init__.py:checked_digest]` Upstream modules `trellis` and `nodes_trellis2` must match `MODEL_SHA256` and `NODES_SHA256` SHA-256 hashes upon import or `RuntimeError` is raised.
- `[__init__.py:project_points]` Orthographic span `span = -camera_angle_x[ortho]` must be finite and within `0.5..2.0` world units.
- `[__init__.py:self_test]` Camera orientation determinants must equal 1 within `1e-6` tolerance.
- `[__init__.py:self_test]` Parallel projection must be depth-invariant (depth variation does not alter projected X/Y screen coordinates).
- `[__init__.py:self_test]` Unmodified positive FOV inputs must produce byte-exact results matching upstream perspective projection.
- `[__init__.py:SRNOrthographicMultiViewConditioning.execute]` `ortho_span` must be finite and satisfy `0.5 <= ortho_span <= 2.0`.
- `[__init__.py:SRNOrthographicMultiViewConditioning.execute]` `front` view image is required; any non-1024x1024 inputs are rescaled via Lanczos filtering.

## Side Effects
- `[__init__.py:trellis._project_points_to_image]` Monkey-patches upstream Trellis projection function `trellis._project_points_to_image` at import time (restored to original if `self_test` fails).
- `[__init__.py:checked_digest]` Reads upstream module files from disk to compute SHA-256 checksums.
- `[__init__.py:SRNOrthographicMultiViewConditioning.execute]` Allocates PyTorch tensors on target device and mutates conditioning dictionary metadata (`extra['proj_feat_pack']`).

## Verification
- Run: `pytest tools/phenotypes`
