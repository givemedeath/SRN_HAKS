"""Transfer saved-field appearance from intact neighboring hair onto reviewed scalp repairs."""
import numpy as np
from scipy.ndimage import map_coordinates
from .common import verify, require
from .gltf import positions
from .rays import EmbreeScene
from .scalp_patch import angular_region


class ScalpDonor:
    def __init__(self, corrected, dll):
        source = corrected['output']
        verify([source], fresh=True)
        vertices, faces = positions(source['path'])
        self.patches = []
        for kind in ('scalpPatch','templeHair'):
            if kind not in corrected:
                continue
            patch = corrected[kind]
            recipe = patch['recipe']
            # Each outline was measured before that correction. The final scalp
            # can have different bounds, especially after a second temple patch.
            verify([patch['source']], fresh=True)
            original, _ = positions(patch['source']['path'])
            low = original.min(axis=0)
            extent = np.ptp(original, axis=0)
            temple = kind == 'templeHair'
            yaw, elev, distance = angular_region(recipe['outline'], temple)
            self.patches.append((low+extent*recipe['center'], extent.max(), yaw[0], elev[0],
                                 distance, recipe.get('donorYawOffset',40)))
        require(self.patches, 'Missing reviewed geometry patch for scalp appearance')
        self.scene = EmbreeScene(dll,vertices.astype(np.float32),faces.astype(np.uint32))
        self.transferred = 0

    def close(self):
        self.scene.close()

    def transfer(self, field, positions, sampled, fallback):
        for start in range(0,len(positions),65536):
            points = positions[start:start+65536]
            for origin, scale, yaw0, elev0, distance, offset in self.patches:
                delta = points-origin
                radius = np.linalg.norm(delta,axis=1)
                yaw = np.rad2deg(np.arctan2(delta[:,0],delta[:,2]))
                elev = np.arcsin(np.clip(delta[:,1]/np.maximum(radius,1e-10),-1,1))
                coords = [(np.rad2deg(elev)-elev0)/.4,(np.abs(yaw)-yaw0)/.4]
                inside = map_coordinates(distance,coords,order=1,mode='constant',cval=-100)
                selected = np.flatnonzero(inside > -2)
                if not len(selected):
                    continue
                angle = np.deg2rad(yaw[selected]+np.sign(yaw[selected])*offset)
                vertical = elev[selected]
                rays = np.column_stack((np.sin(angle)*np.cos(vertical),np.sin(vertical),np.cos(angle)*np.cos(vertical)))
                origins = origin+2*scale*rays
                depth,ids,_ = self.scene.query(origins,-rays)
                require(np.all(ids>=0),'A measured scalp appearance donor missed the hair surface')
                donor, missed = field.sample(origins-depth[:,None]*rays)
                blend = np.clip((inside[selected]+2)/3,0,1)[:,None]
                blend *= blend*(3-2*blend)
                indices = start+selected
                sampled[indices] += blend*(donor-sampled[indices])
                fallback[indices] |= missed
                self.transferred += len(indices)
