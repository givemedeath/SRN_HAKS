"""Soft feature masks for a head's UV layout from face landmarks and parsing of the head's own front render.

The orthographic front render (glTF +z) of the UV mesh with its 4K colour shares the mesh's camera exactly, so MediaPipe
landmarks and BiSeNet labels on it need no design-to-mesh registration. Texels the render sees read the masks by depth match;
texels it cannot see take the nearest seen texel's value within a short 3D distance, never UV neighbours (steps 1-2 of
docs/heads/head-texture-quality-plan.md; RUNBOOK 124-129, 133)."""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter, binary_dilation, distance_transform_edt, label
from scipy.spatial import cKDTree
from .common import require, pin, write, library
from .gltf import mesh
from .rays import EmbreeScene
from .textures import surface, pad
from .palette import lab as to_lab

RENDER = 1024; BACKGROUND = 165.0
# BiSeNet CelebAMask-HQ classes (yakhyo/face-parsing resnet18.onnx).
SKIN, BROWS, EYES, EARS, NOSE, MOUTH, LIPS, HAIR = 1, (2, 3), (4, 5), (7, 8, 9), 10, 11, (12, 13), 17
IRIS = {'R': (468, range(469, 473)), 'L': (473, range(474, 478))}   # subject's right / left
EYE_RING = {'R': [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246],
            'L': [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398]}
SILHOUETTE = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
              172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]
LIP_LINE = (61, 78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308, 291)
SOFT = 1.0                 # render-space mask softening (px)
IRIS_GUARD = (.15, .10)    # refined radius within 15% of MediaPipe's, left/right within 10% (step 0)
BROW_BAND = 24             # px around the parser brow searched by colour (RUNBOOK 128)
LOCK_RATIO, LOCK_SEPARATION = .6, 30   # hair locks: nearer hair than skin by this ratio; colours at least this far apart (RUNBOOK 133)
SEEN_DEPTH, SEEN_FACING, FILL = .002, .1, .012   # depth match and unseen-texel fill distance, fractions of head width
MASKS = ('brow', 'eye', 'iris', 'lips', 'nose', 'hair', 'skin', 'ear', 'hairlock', 'lipline', 'socket')


def front_view(value, embree, size=RENDER):
    """Orthographic front view (camera on glTF +z): per pixel the hit face, barycentrics and depth."""
    P = value['positions'].astype(float); F = value['faces']
    lo, hi = P.min(0), P.max(0); span = max(hi[0]-lo[0], hi[1]-lo[1])*1.04; c = (lo+hi)/2
    ys, xs = np.mgrid[0:size, 0:size]; px = c[0]+((xs+.5)/size-.5)*span; py = c[1]-((ys+.5)/size-.5)*span
    org = np.c_[px.ravel(), py.ravel(), np.full(size*size, hi[2]+span)]
    scene = EmbreeScene(embree['path'], P.astype(np.float32), F.astype(np.uint32))
    try: depth, ids, _ = scene.query(org, np.array([0., 0, -1]))
    finally: scene.close()
    hit = ids >= 0; f = np.where(hit, ids, 0); p = org+np.where(hit, depth, 0)[:, None]*[0, 0, -1]
    A, B, C = P[F[f, 0]], P[F[f, 1]], P[F[f, 2]]; v0, v1, v2 = B-A, C-A, p-A
    d00, d01, d11 = (v0*v0).sum(1), (v0*v1).sum(1), (v1*v1).sum(1); d20, d21 = (v2*v0).sum(1), (v2*v1).sum(1)
    den = np.where(d00*d11-d01*d01 == 0, 1, d00*d11-d01*d01)
    b1 = (d11*d20-d01*d21)/den; b2 = (d00*d21-d01*d20)/den
    return {'hit': hit.reshape(size, size), 'face': f.reshape(size, size), 'bary': np.c_[1-b1-b2, b1, b2].reshape(size, size, 3),
            'zbuf': np.where(hit, p[:, 2], -np.inf).reshape(size, size), 'span': span, 'centre': c}


def bilinear(image, uv):
    n = image.shape[0]; xy = uv*n-.5; x0 = np.clip(np.floor(xy[:, 0]).astype(int), 0, n-2); y0 = np.clip(np.floor(xy[:, 1]).astype(int), 0, n-2)
    fx = np.clip(xy[:, 0]-x0, 0, 1); fy = np.clip(xy[:, 1]-y0, 0, 1)
    if image.ndim == 3: fx, fy = fx[:, None], fy[:, None]
    return image[y0, x0]*(1-fx)*(1-fy)+image[y0, x0+1]*fx*(1-fy)+image[y0+1, x0]*(1-fx)*fy+image[y0+1, x0+1]*fx*fy


def sample(view, image, uv):
    """A texture through UV set uv at every rendered pixel (background elsewhere)."""
    h = view['hit']; t = (view['bary'][h][:, :, None]*uv[view['face'][h]]).sum(1)
    out = np.full(h.shape+image.shape[2:], BACKGROUND if image.shape[-1] == 3 else 0, np.float32); out[h] = bilinear(image, t); return out


def nearest(view, image, uv):
    """Nearest texel (exact channel ids, no blending) at every rendered pixel; -1 where nothing is hit."""
    h = view['hit']; t = (view['bary'][h][:, :, None]*uv[view['face'][h]]).sum(1); n = image.shape[0]
    i = np.clip((t*n).astype(int), 0, n-1); out = np.full(h.shape, -1); out[h] = image[i[:, 1], i[:, 0]]; return out


def landmarks(rgb, mediapipe, model):
    """MediaPipe Face Landmarker (478 points, iris 468-477) in pixel coordinates, or None."""
    from mediapipe.tasks.python import BaseOptions, vision
    options = vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=str(model)), num_faces=1,
                                           min_face_detection_confidence=.2, min_face_presence_confidence=.2)
    with vision.FaceLandmarker.create_from_options(options) as detector:
        found = detector.detect(mediapipe.Image(image_format=mediapipe.ImageFormat.SRGB, data=np.ascontiguousarray(rgb)))
    if not found.face_landmarks: return None
    h, w = rgb.shape[:2]; return np.array([[p.x*w, p.y*h] for p in found.face_landmarks[0]])


def crop_box(shape, pts):
    """Square face-filling crop for the parser."""
    h, w = shape[:2]; cx, cy = pts[:, 0].mean(), pts[:, 1].mean(); side = 1.9*max(np.ptp(pts[:, 0]), np.ptp(pts[:, 1]))
    x0, y0 = int(max(0, cx-side/2)), int(max(0, cy-side/2-.1*side)); return x0, y0, int(min(w, x0+side)), int(min(h, y0+side))


def parse(rgb, box, onnxruntime, model):
    """BiSeNet CelebAMask-HQ labels over the crop (0 elsewhere)."""
    x0, y0, x1, y1 = box; crop = Image.fromarray(rgb).crop(box).resize((512, 512), Image.Resampling.BILINEAR)
    a = (np.asarray(crop, np.float32)/255-[.485, .456, .406])/[.229, .224, .225]
    session = onnxruntime.InferenceSession(str(model), providers=['CPUExecutionProvider'])
    out = session.run(None, {'input': a.transpose(2, 0, 1)[None].astype(np.float32)})[0][0]
    labels = np.zeros(rgb.shape[:2], np.uint8)
    labels[y0:y1, x0:x1] = np.asarray(Image.fromarray(out.argmax(0).astype(np.uint8)).resize((x1-x0, y1-y0), Image.Resampling.NEAREST))
    return labels


def refine_iris(luma, centre, radius):
    """Radial search for the iris/sclera edge left and right of the centre (+-35 deg, where lids rarely cover the limbus)."""
    spans = []
    for a in np.radians(np.arange(-35, 36, 5)):
        edges = []
        for sign in (1, -1):
            t = np.linspace(.5*radius, 1.5*radius, 60); xs = centre[0]+sign*t*np.cos(a); ys = centre[1]+t*np.sin(a)
            v = luma[np.clip(ys.astype(int), 0, luma.shape[0]-1), np.clip(xs.astype(int), 0, luma.shape[1]-1)]
            g = np.diff(np.convolve(v, np.ones(5)/5, mode='same'))[3:-3]; edges.append(t[3+int(np.argmax(g))])
        spans.append(edges)
    right, left = np.median(np.array(spans), 0); return np.array([centre[0]+(right-left)/2, centre[1]]), (right+left)/2


def iris_circles(luma, pts):
    """MediaPipe iris circles, refined from the image only within the step 0 guards."""
    prior = {s: (pts[c].copy(), float(np.linalg.norm(pts[list(r)]-pts[c], axis=1).mean())) for s, (c, r) in IRIS.items()}
    refined = {s: refine_iris(luma, c, r) for s, (c, r) in prior.items()}
    ok = (all(abs(refined[s][1]/prior[s][1]-1) <= IRIS_GUARD[0] for s in prior)
          and abs(refined['R'][1]/refined['L'][1]-1) <= IRIS_GUARD[1])
    return (refined if ok else prior), ok


def polygon(shape, pts, index):
    image = Image.new('L', shape[::-1], 0); ImageDraw.Draw(image).polygon([tuple(pts[i]) for i in index], fill=255)
    return np.asarray(image) > 0


def brow_mask(rgb, labels, eyes, hit):
    """Parser brows grown by colour (RUNBOOK 128): inside a band around the parser brow, a pixel nearer the brow median than the
    band's skin median and within 1.25x the parser brow's p90 colour distance, connected to the parser brow. Brows whose colour is
    within 30 of the skin keep the parser mask."""
    parser = np.isin(labels, BROWS); rgb = rgb.astype(np.float32)
    band = binary_dilation(parser, iterations=BROW_BAND) & ~np.isin(labels, EYES) & ~eyes & hit
    if not parser.any() or not (band & (labels == SKIN)).any(): return parser
    brow = np.median(rgb[parser], 0); skin = np.median(rgb[band & (labels == SKIN)], 0)
    if np.linalg.norm(brow-skin) < 30: return parser
    db = np.linalg.norm(rgb-brow, axis=2); grown = band & (db < 1.25*np.percentile(db[parser], 90)) & (db < np.linalg.norm(rgb-skin, axis=2))
    parts, _ = label(grown); keep = np.unique(parts[parser & grown]); return np.isin(parts, keep[keep > 0])


def face_hull(shape, pts): return polygon(shape, pts, SILHOUETTE)


def plain_skin(labels, face, eyes):
    """Parser skin inside the face, away from brows, eyes, nose and mouth."""
    return face & (labels == SKIN) & ~binary_dilation(np.isin(labels, BROWS) | eyes | np.isin(labels, (NOSE, MOUTH)+LIPS), iterations=6)


def hair_locks(rgb, labels, hit, face, plainskin):
    """Hair locks the parser labels skin (RUNBOOK 133): plain-skin pixels clearly nearer the parser-hair colour median (Lab) than the
    plain-skin median, in patches reaching the hairline or the face edge (locks hang from there; shadows, tattoo lines and plates
    sit inside). None when hair and skin colours are too close to tell apart."""
    S = labels.shape[0]; source = to_lab(rgb.reshape(-1, 3).astype(float)).reshape(rgb.shape)
    hair = (labels == HAIR) & hit
    if hair.sum() < 200 or not plainskin.any(): return None
    hair_median = np.median(source[hair], 0); skin_median = np.median(source[plainskin], 0)
    if np.linalg.norm(hair_median-skin_median) < LOCK_SEPARATION: return None
    lock = plainskin & (np.linalg.norm(source-hair_median, axis=-1) < LOCK_RATIO*np.linalg.norm(source-skin_median, axis=-1))
    parts, _ = label(lock, np.ones((3, 3))); edge = binary_dilation(hair | ~face, iterations=int(.01*S))
    return np.isin(parts, np.unique(parts[edge & lock])) & lock


def render_masks(rgb, labels, pts, circles, hit):
    """Soft render-space masks of every feature."""
    S = labels.shape[0]; ys, xs = np.mgrid[0:S, 0:S]
    eyes = binary_dilation(polygon(labels.shape, pts, EYE_RING['R']) | polygon(labels.shape, pts, EYE_RING['L']), iterations=1)
    opening = np.isin(labels, EYES) & eyes
    iris = np.zeros((S, S), np.float32)
    for c, r in circles.values(): iris = np.maximum(iris, np.clip(r+.75-np.hypot(xs+.5-c[0], ys+.5-c[1]), 0, 1.5)/1.5)   # 1.5 px soft rim
    face = face_hull(labels.shape, pts); locks = hair_locks(rgb, labels, hit, face, plain_skin(labels, face, eyes))
    locks = np.zeros((S, S), bool) if locks is None else locks
    hard = {'brow': brow_mask(rgb, labels, eyes, hit), 'eye': opening, 'lips': np.isin(labels, (MOUTH,)+LIPS), 'nose': labels == NOSE,
            'hair': (labels == HAIR) | locks, 'ear': np.isin(labels, EARS), 'skin': (labels == SKIN) & ~locks, 'hairlock': locks}
    soft = {k: gaussian_filter(v.astype(np.float32), SOFT) for k, v in hard.items()}
    soft['iris'] = iris*gaussian_filter(opening.astype(np.float32), .7); soft['eye'] = np.maximum(soft['eye'], soft['iris'])
    # Darks from landmarks: the lip line and an eye-socket shadow, full strength above the eye and 40% below (step 3).
    line = Image.new('L', (S, S), 0); ImageDraw.Draw(line).line([tuple(pts[i]) for i in LIP_LINE], fill=255, width=3)
    soft['lipline'] = gaussian_filter(np.asarray(line, np.float32)/255, 1.0)
    level = np.mean([c[1] for c, _ in circles.values()]); radius = np.mean([r for _, r in circles.values()])
    soft['socket'] = np.where(eyes, 0, np.exp(-distance_transform_edt(~eyes)/(.6*radius))*np.where(ys < level, 1.0, .4))*np.isin(labels, (SKIN, NOSE))
    return soft, hard


def project(value, view, soft, size=4096):
    """4K texel masks: seen texels (depth match, facing the camera) read the render; unseen texels take the nearest seen texel's
    value within FILL head widths in 3D, fading to zero; everything is padded into the chart gutters like the bake."""
    P = value['positions'].astype(float); F = value['faces']; width = np.ptp(P[:, 0]); S = view['hit'].shape[0]
    positions, owners, _ = surface(value, size, enforce=False); mapped = owners >= 0; points = positions[mapped].astype(float); faces = owners[mapped]
    normals = np.cross(P[F[:, 1]]-P[F[:, 0]], P[F[:, 2]]-P[F[:, 0]]); normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-12)
    u = ((points[:, 0]-view['centre'][0])/view['span']+.5)*S; v = (.5-(points[:, 1]-view['centre'][1])/view['span'])*S
    inside = (u >= 0) & (u < S-1) & (v >= 0) & (v < S-1); ui = np.clip(u.astype(int), 0, S-1); vi = np.clip(v.astype(int), 0, S-1)
    seen = inside & (np.abs(view['zbuf'][vi, ui]-points[:, 2]) < SEEN_DEPTH*width) & (normals[faces, 2] > SEEN_FACING)
    require(seen.any(), 'The front render sees no texel of this layout')
    distance, index = cKDTree(points[seen]).query(points[~seen], k=1, distance_upper_bound=FILL*width)
    found = np.isfinite(distance); weight = np.where(found, 1-np.where(found, distance, 0)/(FILL*width), 0); index = np.where(found, index, 0)
    uv = np.clip(np.c_[u, v]/S, 0, 1); out = {}
    for name, mask in soft.items():
        values = np.where(seen, bilinear(mask, uv), 0); values[~seen] = values[seen][index]*weight
        atlas = np.zeros((size, size, 1), np.float32); atlas[mapped, 0] = np.clip(values, 0, 1)*255
        out[name] = np.rint(pad(atlas, mapped)[..., 0]).astype(np.uint8)
    return out, {'texels': int(mapped.sum()), 'seenFromFront': int(seen.sum()), 'filled': int(found.sum())}


def overlay(rgb, labels, pts, circles):
    """Review sheet: landmarks, eye contours and iris circles left; parser labels right."""
    colours = np.array([[0, 0, 0], [255, 204, 153], [0, 160, 255], [0, 80, 255], [0, 255, 0], [0, 160, 0], [255, 255, 0], [255, 0, 255],
                        [160, 0, 160], [255, 128, 0], [255, 255, 160], [255, 0, 0], [200, 0, 80], [128, 0, 40], [128, 128, 128],
                        [64, 64, 64], [0, 255, 255], [140, 70, 20], [255, 255, 255]], np.uint8)
    keep = (labels == 0) | (labels == SKIN); base = rgb.astype(np.float32)
    parsed = np.where(keep[..., None], base, .45*base+.55*colours[labels]).astype(np.uint8)
    marked = Image.fromarray(rgb.copy()); d = ImageDraw.Draw(marked)
    for x, y in pts[:468]: d.point((x, y), fill=(0, 255, 0))
    for side, ring in EYE_RING.items(): d.line([tuple(pts[i]) for i in ring+ring[:1]], fill=(255, 255, 0), width=1)
    for c, r in circles.values(): d.ellipse((c[0]-r, c[1]-r, c[0]+r, c[1]+r), outline=(255, 0, 255), width=2)
    return Image.fromarray(np.concatenate([np.asarray(marked), parsed], 1))


def face_masks(source, colour, bindings, output, size=RENDER):
    """The masks stage: front render, landmarks, parse, iris, brows, hair locks, darks, projection; review sheets."""
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    mediapipe = library(bindings, 'mediapipe'); onnxruntime = library(bindings, 'onnxruntime')
    models = Path(bindings['libraries']['mediapipe']['directory'])/'models'
    value = mesh(source); uv = value['uv'].astype(float)
    with Image.open(colour) as image: atlas = np.asarray(image.convert('RGB'), np.float32)
    require(atlas.shape[:2] == (4096, 4096), 'Masks read the 4K colour atlas')
    view = front_view(value, bindings['embree'], size); rgb = np.clip(sample(view, atlas, uv), 0, 255).astype(np.uint8)
    pts = landmarks(rgb, mediapipe, models/'face_landmarker.task'); require(pts is not None, 'No face found on the front render')
    labels = parse(rgb, crop_box(rgb.shape, pts), onnxruntime, models/'resnet18.onnx')
    circles, refined = iris_circles(np.asarray(Image.fromarray(rgb).convert('L'), np.float32), pts)
    soft, hard = render_masks(rgb, labels, pts, circles, view['hit'])
    masks, coverage = project(value, view, soft)
    Image.fromarray(rgb).save(output/'front-render.png'); Image.fromarray(labels).save(output/'front-labels.png')
    np.save(output/'front-landmarks.npy', pts)
    np.savez(output/'front-view.npz', hit=view['hit'], face=view['face'], bary=view['bary'].astype(np.float32), zbuf=view['zbuf'],
             span=view['span'], centre=view['centre'])
    files = {'frontRender': pin(output/'front-render.png'), 'frontLabels': pin(output/'front-labels.png'),
             'frontLandmarks': pin(output/'front-landmarks.npy'), 'frontView': pin(output/'front-view.npz')}
    for name in MASKS:
        Image.fromarray(masks[name]).save(output/f'mask-{name}-4096.png'); files[name] = pin(output/f'mask-{name}-4096.png')
    overlay(rgb, labels, pts, circles).save(output/'review-labels.png')
    tint = rgb.astype(np.float32)
    for name, colour_ in (('brow', (0, 90, 255)), ('eye', (0, 255, 0)), ('iris', (255, 0, 255)), ('lips', (255, 0, 0)), ('nose', (255, 220, 0)), ('hairlock', (0, 255, 255))):
        a = sample(view, masks[name].astype(np.float32)[..., None]/255, uv)[..., :1]*.6; tint = tint*(1-a)+np.array(colour_, np.float32)*a
    Image.fromarray(np.concatenate([rgb, np.clip(tint, 0, 255).astype(np.uint8)], 1)).save(output/'review-masks.png')
    result = {'source': pin(source), 'colour': pin(colour), 'files': files, 'irisRefined': bool(refined),
              'iris': {k: [np.round(c, 1).tolist(), round(float(r), 2)] for k, (c, r) in circles.items()},
              'renderPixels': {k: int(v.sum()) for k, v in hard.items()}, 'coverage': coverage,
              'maskTexels': {k: int((v > 127).sum()) for k, v in masks.items()},
              'review': {'labels': pin(output/'review-labels.png'), 'masks': pin(output/'review-masks.png')}, 'visualReviewRequired': True}
    write(output/'masks.json', result, fresh=True); return result
