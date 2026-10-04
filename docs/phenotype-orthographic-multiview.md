# Orthographic six-view Pixal3D extension

Use this scoped branch for isolated parts that benefit from genuine top and
sole conditioning. The selected v5 feet and gripping hands used this branch and
completed native/full-body practical client checks. The hand remesh required
separate measured recovery. Node registration or camera tests alone do not prove
anatomical improvement; [the current delivery](phenotype-human-male-delivery.md)
records the selected outcomes and limits.
That Human hand recovery is a case record, not an expected outcome for future
hands. Inspect each new reconstruction and proceed normally when it is sound;
diagnostics and repair depend on the defect actually observed.

The installed `Pixal3DMultiViewConditioning` provides four side cameras at
elevation zero using perspective projection. The additive workspace node is
`tools/phenotypes/comfy_nodes/srn_orthographic_multiview/__init__.py`, installed
as `custom_nodes/srn_orthographic_multiview` by the guarded installer. It checks
exact upstream source hashes before patching the in-memory projection dispatcher;
no installed core file or saved workflow is edited. Positive-FOV conditioning
calls the original projector byte-exact. Removing the additive node and restarting
restores the original runtime behavior.

## Camera contract

Read the actual installed camera matrices before arranging asymmetric end views.
In this adapter, top preserves world X/Y in image X/up, while bottom preserves
world X and reverses world Y. Its import test projects world point (0.2,0.1,0.3)
to top (75,45) and bottom (75,65) at span1.1/resolution110: image X does not reverse.
Therefore a thumb at a fixed world X stays on the same image side in both axial
views. Generic camera conventions do not override this frozen tested basis.
End views must also show actual foreshortened anatomy, not a side/front view
relabeled as top or bottom. Count distinguishable fingers and check occlusion
against the full reference sheet before reconstruction.

| View | Azimuth | Elevation |
| --- | ---: | ---: |
| Front | 0 | 0 |
| Left | 90 | 0 |
| Back | 180 | 0 |
| Right | 270 | 0 |
| Top | 0 | 90 |
| Sole | 0 | -90 |

All cameras use proper bases and parallel projection: pixel XY depends on
camera-space XY and a shared world span, not depth. The existing stage pack
transports camera matrices and FOV; the adapter uses a reserved negative value
to transport orthographic span (.5–2 world units, default1.1), dispatching only
that explicit tag. This is not a physical negative FOV. Existing model weights,
feature extraction, samplers and aggregation are unchanged. Model support for
additional views comes from the existing `num_views` conditioning pack.

Import tests check known projection, depth invariance, top/sole orientation,
proper camera bases and exact legacy perspective output. Failed tests restore
the original projector and prevent registration. Freeze adapter and both upstream
sources at preparation and verify installed bytes again before submission.
Upstream version changes require source review rather than bypassing pins.

## References and execution

Use a 2-column/3-row sheet: front,left/back,right/top,sole. Keep the part upright
with no diagonal object tilt. For toes toward -Y, top has toes down and sole has
toes up, both with the left big toe at image left. These are image design axes;
inspect actual reconstructed geometry before rotating into stock axes.

`normalize_part_turnaround.py --layout-components --six-views --center-origin`
preserves complete silhouettes, one isotropic magnification and centered bounds.
It cannot make AI-generated views a calibrated scan. Relative silhouette
disparities and any inferred shared origin remain review limitations.

`generate_purpose_built_part.py` with explicit `orthographic-six-view` configuration
freezes the original live `SR_NWN_3d_pixal3d_multi_views` graph, then changes only
conditioning node324 and six image inputs in the submission variant. It preserves
all four source masters and one dispatch receipt. The saved live workflow remains
unchanged. Existing four-view preparations retain their original path.

Use ordinary closed part ends in reference images. Apply measured hidden tapers
after generation and uniform fitting if needed. Hands must use nearly
closed gripping fingers and a weapon-ready thumb, with stock wrist/weapon
measurements before image design. The Human male hand phase is complete;
the current checkpoint and latest user direction control any new target or job.
