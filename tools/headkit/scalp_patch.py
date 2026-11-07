"""Rebuild a reviewed pair of local scalp patches under duplicated multiview horns."""
import numpy as np
from PIL import Image, ImageDraw
from scipy.interpolate import RBFInterpolator
from scipy.ndimage import distance_transform_edt, gaussian_filter, map_coordinates, median_filter
from .common import pin, require
from .gltf import positions, write_mesh
from .rays import EmbreeScene


def angular_region(points, temple=False):
    polygon = np.asarray(points, dtype=float)
    require(polygon.ndim == 2 and polygon.shape[1] == 2 and 3 <= len(polygon) <= 32
            and np.isfinite(polygon).all(), 'Reviewed yaw/elevation outline required')
    low, high = polygon.min(axis=0), polygon.max(axis=0)
    require(low[0] >= 20 and high[0] <= 155 and low[1] >= (-30 if temple else 15) and high[1] <= 80
            and np.all(high-low < (68 if temple else 55)), 'Scalp correction exceeds local upper side of head')
    step = .4
    yaw = np.arange(low[0]-8, high[0]+8, step)
    elev = np.arange(low[1]-8, high[1]+8, step)
    image = Image.new('L',(len(yaw),len(elev)))
    ImageDraw.Draw(image).polygon([tuple(point) for point in (polygon-[yaw[0],elev[0]])/step],fill=255)
    mask = np.asarray(image)>0
    distance = (distance_transform_edt(mask)-distance_transform_edt(~mask))*step
    return yaw, elev, distance


def temple_hair_surface(scene, origin, scale, az, e, side, radius, distance, donor_offset):
    from scipy.sparse import coo_matrix
    from scipy.sparse.linalg import spsolve
    inner = distance > -1.5
    iy,ix=np.nonzero(inner)
    index=np.full(inner.shape,-1);index[iy,ix]=np.arange(len(iy))
    rows=[np.arange(len(iy))]; cols=[rows[0]]; values=[np.full(len(iy),4.)]
    rhs=np.zeros(len(iy))
    boundary=gaussian_filter(median_filter(radius,5),2.2)
    for dy,dx in ((0,-1),(0,1),(-1,0),(1,0)):
        j=index[iy+dy,ix+dx]; known=j<0
        rhs[known]+=boundary[iy[known]+dy,ix[known]+dx]
        rows.append(np.flatnonzero(~known));cols.append(j[~known]);values.append(-np.ones(np.sum(~known)))
    matrix=coo_matrix((np.concatenate(values),(np.concatenate(rows),np.concatenate(cols))),shape=(len(iy),len(iy)))
    base=boundary.copy()
    base[iy,ix]=spsolve(matrix.tocsr(),rhs)
    # Transfer the surface relief of adjacent intact hair into the interpolated volume.
    donor_a=np.deg2rad(side*(az+donor_offset)); donor_directions=np.stack([np.sin(donor_a)*np.cos(e),np.sin(e),np.cos(donor_a)*np.cos(e)],-1)
    donor_rays=donor_directions.reshape(-1,3)
    donor_depth,donor_ids,_=scene.query(origin+2*scale*donor_rays,-donor_rays)
    donor=(2-donor_depth/scale).reshape(az.shape)
    donor=np.where(donor_ids.reshape(az.shape)>=0,donor,base)
    relief=gaussian_filter(median_filter(donor,3),1.8)-gaussian_filter(donor,13)
    base+=np.clip(relief,-.025,.025)*np.clip(distance/4,0,1)
    return base


def patch_surface(scene, origin, scale, yaw, elev, distance, side, donor_offset=None):
    az, el = np.meshgrid(yaw, elev)
    a, e = np.deg2rad(side*az), np.deg2rad(el)
    directions = np.stack([np.sin(a)*np.cos(e),np.sin(e),np.cos(a)*np.cos(e)],-1)
    rays = directions.reshape(-1,3)
    depth, ids, _ = scene.query(origin+rays*scale*2,-rays)
    radius = (2-depth/scale).reshape(az.shape)
    missing = ~np.isfinite(radius) | (ids.reshape(az.shape)<0)
    require(missing.mean()<.03,'Too many missing exterior rays around the selected scalp')
    if missing.any():
        nearest = distance_transform_edt(missing,return_distances=False,return_indices=True)
        radius[missing] = radius[tuple(nearest[:,missing])]
    if donor_offset is None:
        coords = np.stack([az,el],-1)
        yy,xx = np.argwhere((distance>=-4)&(distance<0))[::8].T
        smooth = gaussian_filter(median_filter(radius,3),1.25)
        interp = RBFInterpolator(coords[yy,xx],smooth[yy,xx],smoothing=4,neighbors=50)
        base = interp(coords.reshape(-1,2)).reshape(radius.shape)
        # Cast again just above the interpolated scalp. Preserve actual hair hidden under the horn.
        near = base+.026
        depth, ids, _ = scene.query(origin+rays*(near.ravel()*scale)[:,None],-rays)
        under = (near.ravel()-depth/scale).reshape(radius.shape)
        reliable = (ids.reshape(radius.shape)>=0)&(under>base-.035)&(under<base+.025)
        recovered = gaussian_filter(median_filter(np.where(reliable,under,base),3),2)
    else:
        stretch = np.ptp(az,axis=1).max()
        require(stretch < donor_offset + 24, 'Donor hair region would overlap too much with the defect')
        recovered = temple_hair_surface(scene, origin, scale, az, e, side, radius, distance, donor_offset)
    blend = np.clip((distance+.75)/3,0,1)
    blend = blend*blend*(3-2*blend)
    height = radius*(1-blend)+recovered*blend
    points = origin+directions*(height*scale)[...,None]
    local = distance>=-1.5
    iy,ix = np.where(local[:-1,:-1]&local[:-1,1:]&local[1:,:-1]&local[1:,1:])
    first = iy*len(yaw)+ix
    faces = np.vstack([np.column_stack([first,first+1,first+len(yaw)+1]),
                       np.column_stack([first,first+len(yaw)+1,first+len(yaw)])])
    return points.reshape(-1,3), faces if side>0 else faces[:,::-1], height


def restore(source, output, bindings, recipe):
    """Keep the source outside the two angular patches. The repair stage closes their overlapping borders."""
    source_pin = pin(source)
    temple = recipe.get('kind') == 'paired-temple-hair-v1'
    require(recipe.get('sourceSha256')==source_pin['sha256'] and (temple or recipe.get('kind')=='paired-scalp-patch-v1'),
            'Scalp patch recipe must name this exact precluster output')
    require(isinstance(recipe.get('notes'),str) and recipe['notes'].strip(),'Explain the observed duplicate')
    center = np.asarray(recipe['center'],float)
    require(center.shape==(3,) and np.all((center>=.3)&(center<=.7)),'Scalp patch needs an interior head center')
    offset = recipe.get('donorYawOffset') if temple else None
    if temple:
        require(type(offset) in (int,float) and 25 <= offset <= 60, 'Measure the adjacent hair donor offset in degrees')
    yaw,elev,distance = angular_region(recipe['outline'], temple)
    vertices,faces = positions(source)
    lo = vertices.min(0)
    span = vertices.max(0)-lo
    origin,scale = lo+span*center,span.max()
    scene = EmbreeScene(bindings['embree']['path'],vertices.astype(np.float32),faces.astype(np.uint32))
    keep = np.ones(len(faces),bool)
    patches = []
    try:
        for side in (-1,1):
            points,tri,height = patch_surface(scene,origin,scale,yaw,elev,distance,side,offset)
            patches.append((points,tri))
            for index in range(0,len(faces),200000):
                p = (vertices[faces[index:index+200000]].mean(axis=1)-origin)/scale
                rad = np.linalg.norm(p,axis=1)
                az = np.rad2deg(np.arctan2(p[:,0],p[:,2]))*side
                el = np.rad2deg(np.arcsin(np.clip(p[:,1]/np.maximum(rad,1e-8),-1,1)))
                xy = [(el-elev[0])/.4,(az-yaw[0])/.4]
                inside = map_coordinates(distance,xy,order=1,mode='constant',cval=-100)>-.4
                surface = map_coordinates(height,xy,order=1,mode='nearest')
                keep[index:index+len(p)] &= ~(inside & (rad>surface-(.17 if temple else .065)))
    finally:
        scene.close()
    fraction = 1-float(keep.mean())
    require(0<fraction<=(.10 if temple else .07), 'Local correction exceeded its triangle limit')
    vertices_out,faces_out = [vertices],[faces[keep]]
    count = len(vertices)
    for points,tri in patches:
        vertices_out.append(points)
        faces_out.append(tri+count)
        count += len(points)
    merged = np.concatenate(faces_out)
    used,inverse = np.unique(merged,return_inverse=True)
    write_mesh(output,np.concatenate(vertices_out)[used],inverse.reshape(-1,3))
    return dict(source=source_pin,retainedFraction=1-fraction,output=pin(output),recipe=recipe)
