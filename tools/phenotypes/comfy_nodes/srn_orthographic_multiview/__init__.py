"""Additive six-view orthographic Pixal3D conditioning for measured part images.

Standard positive-FOV conditioning is passed to the original projector exactly.
Only this node emits the negative-span orthographic transport tag. No installed
source file is edited. Pinned installed internals are checked before patching.
"""
import hashlib
import math
from pathlib import Path

import torch
from comfy_api.latest import ComfyExtension, IO
from comfy.ldm.trellis2 import model as trellis
from comfy_extras import nodes_trellis2 as upstream

MODEL_SHA256 = 'baa8b081de2eada84754b867282bd21d498233816326f8842943857fe1d07e0c'
NODES_SHA256 = '5d99f8fd2d1a1cc252b860d941717fc4e53cfbc48b623730c9fdd9139dd7f98c'
VIEWS = ('front', 'left', 'back', 'right', 'top', 'bottom')
AZIMUTHS = (0., 90., 180., 270., 0., 0.)
ELEVATIONS = (0., 0., 0., 0., 90., -90.)


def checked_digest(module, expected):
    path = Path(module.__file__)
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise RuntimeError('SRN orthographic adapter requires reviewed upstream source: ' + str(path))


checked_digest(trellis, MODEL_SHA256)
checked_digest(upstream, NODES_SHA256)
_ORIGINAL = getattr(trellis._project_points_to_image, '_srn_perspective_original', trellis._project_points_to_image)


def project_points(points_world, transform_matrix, camera_angle_x, resolution):
    """Negative camera tag encodes full orthographic world span, not a FOV.

    The upstream stage pack transports only camera matrices/FOV. A reserved
    negative value lets all original shape/texture stages dispatch our exact
    parallel projection without changing their sampler or weight code.
    """
    ortho = camera_angle_x < 0
    if not bool(ortho.any()):
        return _ORIGINAL(points_world, transform_matrix, camera_angle_x, resolution)
    span = -camera_angle_x[ortho]
    if not bool(torch.isfinite(span).all()) or not bool(((span >= .5) & (span <= 2.)).all()):
        raise ValueError('SRN orthographic span outside reviewed .5..2 world units')
    b, n, _ = points_world.shape
    uv = torch.empty((b, n, 2), device=points_world.device, dtype=points_world.dtype)
    depth = torch.empty((b, n), device=points_world.device, dtype=points_world.dtype)
    valid = torch.empty((b, n), device=points_world.device, dtype=torch.bool)
    perspective = ~ortho
    if bool(perspective.any()):
        puv, pd, pv = _ORIGINAL(points_world[perspective], transform_matrix[perspective], camera_angle_x[perspective], resolution)
        uv[perspective], depth[perspective], valid[perspective] = puv, pd, pv
    p = points_world[ortho]
    homo = torch.cat((p, torch.ones_like(p[:, :, :1])), dim=-1)
    inverse = torch.linalg.inv(transform_matrix[ortho].float()).to(transform_matrix.dtype)
    camera = torch.bmm(homo, inverse.transpose(-2, -1))[:, :, :3]
    scale = (resolution / span.to(camera.dtype))[:, None]
    x = camera[:, :, 0] * scale + resolution / 2
    y = -camera[:, :, 1] * scale + resolution / 2
    d = -camera[:, :, 2]
    uv[ortho] = torch.stack((x, y), -1)
    depth[ortho] = d
    valid[ortho] = (x >= 0) & (x < resolution) & (y >= 0) & (y < resolution) & (d > 0)
    return uv, depth, valid


project_points._srn_perspective_original = _ORIGINAL
trellis._project_points_to_image = project_points


def self_test():
    """CPU import gate: known projections, depth invariance and legacy equality."""
    matrices = upstream._orbit_camera_to_world(AZIMUTHS, ELEVATIONS, 2.)
    if not torch.allclose(torch.linalg.det(matrices[:, :3, :3]), torch.ones(6), atol=1e-6):
        raise RuntimeError('Improper six-view camera basis')
    # Depth changes cannot change projected X/Y in parallel projection.
    local = torch.tensor([[[.2, .1, -.5], [.2, .1, -1.5]]]).expand(6, -1, -1)
    homo = torch.cat((local, torch.ones_like(local[:, :, :1])), -1)
    world = torch.bmm(homo, matrices.transpose(-2, -1))[:, :, :3]
    uv, _, valid = project_points(world, matrices, torch.full((6,), -1.1), 110)
    if not torch.allclose(uv, torch.tensor([75., 45.]).expand(6, 2, 2), atol=1e-4) or not bool(valid.all()):
        raise RuntimeError('Orthographic projection/depth-invariance fixture failed')
    # Top view uses world X right and world Y up; bottom reverses Y.
    point = torch.tensor([[[.2, .1, .3]]]).expand(2, -1, -1)
    tb, _, _ = project_points(point, matrices[4:], torch.full((2,), -1.1), 110)
    if not torch.allclose(tb, torch.tensor([[[75.,45.]], [[75.,65.]]]), atol=1e-4):
        raise RuntimeError('Top/sole camera orientation fixture failed')
    angles = torch.full((6,), math.radians(20.))
    before = _ORIGINAL(world, matrices, angles, 110)
    after = project_points(world, matrices, angles, 110)
    if not all(torch.equal(a,b) for a,b in zip(before,after)):
        raise RuntimeError('Existing perspective behavior changed')
    return {'orthographicDepthInvariant': True, 'topBottomOrientationCorrect': True,
            'legacyPerspectiveByteExact': True, 'properCameraBases': True}


try:
    IMPORT_TEST = self_test()
except Exception:
    trellis._project_points_to_image = _ORIGINAL
    raise


class SRNOrthographicMultiViewConditioning(IO.ComfyNode):
    @classmethod
    def define_schema(cls):
        return IO.Schema(node_id='SRNOrthographicMultiViewConditioning',
            display_name='SRN Pixal3D Orthographic Multi-View', category='SRN/conditioning',
            inputs=[IO.ClipVision.Input('clip_vision_model'),
                IO.Float.Input('ortho_span', default=1.1, min=.5, max=2., step=.01,
                    tooltip='Shared full world span of each square parallel-projection image; 1.1 gives 1/1.1 framing. All views share one image scale and centered origin.')]
                + [IO.Image.Input(name, optional=(name!='front'), tooltip='True orthographic '+name+' view. No object tilt; shared isotropic magnification and centered origin.') for name in VIEWS],
            outputs=[IO.Conditioning.Output(display_name='positive'),IO.Conditioning.Output(display_name='negative')])

    @classmethod
    def execute(cls, clip_vision_model, ortho_span, front, left=None, back=None, right=None, top=None, bottom=None):
        views=dict(zip(VIEWS,(front,left,back,right,top,bottom)))
        names=[name for name in VIEWS if views[name] is not None]
        if not math.isfinite(ortho_span) or not .5<=ortho_span<=2.:
            raise ValueError('Finite shared orthographic span required')
        batch_size=front.shape[0];items=[]
        for b in range(batch_size):
            for name in names:
                view=views[name][b%views[name].shape[0]][None]
                if view.shape[-1]==4:view=view[:,:,:,:3]*view[:,:,:,3:4]
                if view.shape[1:3]!=(1024,1024):
                    view=upstream.comfy.utils.common_upscale(view.movedim(-1,1),1024,1024,'lanczos','disabled').movedim(1,-1)
                items.append(view)
        ids=[VIEWS.index(name) for name in names]
        c2w=upstream._orbit_camera_to_world([AZIMUTHS[i] for i in ids],[ELEVATIONS[i] for i in ids],2.)
        result=upstream._build_pixal3d_conditioning(clip_vision_model,torch.cat(items,0),
            c2w.repeat(batch_size,1,1),torch.full((batch_size*len(names),),-ortho_span),torch.ones(batch_size),num_views=len(names))
        for conditioning in result.result:
            for _,extra in conditioning:
                extra['proj_feat_pack']['srn_projection']='orthographic-negative-span-v1'
                extra['proj_feat_pack']['srn_view_names']=names
        return result


class SRNExtension(ComfyExtension):
    async def get_node_list(self):
        return [SRNOrthographicMultiViewConditioning]


async def comfy_entrypoint():
    return SRNExtension()
