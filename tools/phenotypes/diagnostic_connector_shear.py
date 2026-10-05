"""Unapplied Troll LEFT hip connector shear math; this module has no exporter.

F(p)=p+w(a)delta with a=(p-origin).axis and delta perpendicular to axis.
The continuous map preserves a, has determinant one and has an explicit inverse.
A future exporter must separately prove its serialized mesh/preserved lineage,
including discrete intersections; continuous injectivity alone is not that proof.
"""
from dataclasses import dataclass
import numpy as np


def require(ok, message):
    if not ok:
        raise ValueError(message)


@dataclass(frozen=True)
class ConnectorShear:
    origin: np.ndarray
    axis: np.ndarray
    delta: np.ndarray
    center: float
    inner: float = .005
    outer: float = .035

    def __post_init__(self):
        for name in ('origin', 'axis', 'delta'):
            a = np.asarray(getattr(self, name), dtype=float).copy()
            require(a.shape == (3,) and np.isfinite(a).all(), 'Finite explicit 3D frame/vector required')
            a.flags.writeable = False
            object.__setattr__(self, name, a)
        require(np.isfinite([self.center, self.inner, self.outer]).all(), 'Finite support parameters required')
        require(abs(np.linalg.norm(self.axis) - 1) < 1e-12, 'Declared unit axis required; no silent normalization')
        require(abs(self.axis @ self.delta) < 1e-12, 'Only radial delta permitted; axial changes rejected')
        require(0 < np.linalg.norm(self.delta) <= .020 + 1e-14, 'Unapplied first-trial delta must be positive and at most 20mm')
        require(self.inner == .005 and self.outer == .035, 'Exact proposed 5/35mm support required')
        require(self.center > self.outer, 'Proximal joint must lie outside the support')

    def weight(self, a):
        a = np.asarray(a, float)
        require(np.isfinite(a).all(), 'Finite axial coordinates required')
        r = np.abs(a - self.center)
        t = np.clip((r - self.inner) / (self.outer - self.inner), 0, 1)
        w = 1 - t**3 * (10 + t * (-15 + 6*t))
        dw = -30*t*t*(t-1)**2 * np.sign(a-self.center)/(self.outer-self.inner)
        # Representable knots: cancellation in abs(a-center) can create a tiny
        # derivative at an authored plateau endpoint. Snap only within 8 ULP
        # of explicit knots; strict outside support is always identity.
        knot_eps = 8*np.spacing(max(abs(self.center), self.outer))
        plateau = (a >= self.center-self.inner-knot_eps) & (a <= self.center+self.inner+knot_eps)
        outside = (a <= self.center-self.outer+knot_eps) | (a >= self.center+self.outer-knot_eps)
        w = np.where(plateau, 1., np.where(outside, 0., w))
        dw = np.where(plateau | outside, 0., dw)
        return w, dw

    def coordinates(self, p):
        p = np.asarray(p, float)
        require(p.ndim == 2 and p.shape[1] == 3 and np.isfinite(p).all(), 'Finite N by 3 positions required')
        return (p-self.origin) @ self.axis

    def transform(self, p, inverse=False):
        p = np.asarray(p, float)
        a = self.coordinates(p)
        w, _ = self.weight(a)
        q = p.copy()
        active = w != 0
        q[active] += (-1 if inverse else 1)*w[active, None]*self.delta
        return q

    def jacobian(self, p):
        a = self.coordinates(p)
        _, dw = self.weight(a)
        return np.eye(3)[None] + dw[:, None, None]*np.outer(self.delta, self.axis)

    def transport(self, p, normals, tangents):
        p = np.asarray(p, float)
        a = self.coordinates(p)
        n = np.asarray(normals)
        t = np.asarray(tangents)
        require(n.shape == p.shape and t.shape == (len(p), 4), 'Matching P/N/T rows required')
        require(np.issubdtype(n.dtype, np.floating) and np.issubdtype(t.dtype, np.floating), 'Floating authored shading rows required')
        require(np.isfinite(n).all() and np.isfinite(t).all(), 'Finite authored shading required')
        w, dw = self.weight(a)
        nn, tt = n.copy(), t.copy()
        affected = w != 0
        if affected.any():
            an, at = n[affected].astype(float), t[affected].astype(float)
            require((np.linalg.norm(an,axis=1)>1e-8).all() and (np.linalg.norm(at[:,:3],axis=1)>1e-8).all() and (abs(at[:,3])==1).all(), 'Active N/T/W cannot be degenerate')
        active = np.any(self.jacobian(p) != np.eye(3)[None], axis=(1,2))
        if not active.any():
            return nn, tt
        ns, ts = n[active].astype(float), t[active].astype(float)
        nl, tl = np.linalg.norm(ns, axis=1), np.linalg.norm(ts[:, :3], axis=1)
        require((nl > 1e-8).all() and (tl > 1e-8).all() and (abs(ts[:, 3]) == 1).all(), 'Active N/T/W cannot be degenerate')
        # J^-T covector transport, followed by original authored magnitude.
        outn = ns - (ns @ self.delta * dw[active])[:, None]*self.axis
        outn *= (nl/np.linalg.norm(outn, axis=1))[:, None]
        unit = outn/nl[:, None]
        # J tangent transport, GS against transported N, original magnitude/W.
        outt = ts[:, :3] + (ts[:, :3] @ self.axis * dw[active])[:, None]*self.delta
        outt -= np.sum(outt*unit, axis=1)[:, None]*unit
        length = np.linalg.norm(outt, axis=1)
        require((length > 1e-8).all(), 'Degenerate GS tangent rejected')
        outt *= (tl/length)[:, None]
        nn[active] = outn
        tt[active, :3] = outt
        # W, all rows with identity J, and all outside rows retain exact bytes.
        return nn, tt


def verify_triangle_orientation(before, after, faces):
    """Conservative discrete guard, without a global intersection-proof claim."""
    before, after, faces = np.asarray(before, float), np.asarray(after, float), np.asarray(faces)
    require(before.shape == after.shape and before.ndim == 2 and before.shape[1] == 3, 'Matching positions required')
    require(faces.ndim == 2 and faces.shape[1] == 3 and np.issubdtype(faces.dtype, np.integer), 'Original triangle index array required')
    require(np.isfinite(before).all() and np.isfinite(after).all(), 'Finite serialized positions required')
    require((faces >= 0).all() and (faces < len(before)).all(), 'Face index outside original attributes')
    old, new = before[faces], after[faces]
    on = np.cross(old[:, 1]-old[:, 0], old[:, 2]-old[:, 0])
    nn = np.cross(new[:, 1]-new[:, 0], new[:, 2]-new[:, 0])
    ol, nl = np.linalg.norm(on, axis=1), np.linalg.norm(nn, axis=1)
    require((ol > 2e-15).all() and (nl > 2e-15).all(), 'Source or new degenerate face rejected')
    dots = np.sum(on*nn, axis=1)/(ol*nl)
    require((dots > 0).all(), 'Serialized triangle orientation reversal rejected')
    return {'minimumFaceNormalDot': float(dots.min()), 'minimumDoubleArea': float(nl.min()),
            'faces': len(faces), 'intersectionProof': False, 'exportAuthorized': False}


@dataclass(frozen=True)
class ConnectorProfile(ConnectorShear):
    """Unapplied same-support positive radial profile plus bounded center shear.

    The approved outside bulk and all axial coordinates remain exact. At each
    axial plane the map is an invertible two-dimensional affine transform.
    q(a)>0 gives det(J)=q1*q2, independently of the center/profile derivatives.
    Serialized facets and exterior intersections still require independent proof.
    """
    radial_basis: np.ndarray = None
    ratios: np.ndarray = None

    def __post_init__(self):
        super().__post_init__()
        b=np.asarray(self.radial_basis,float).copy();r=np.asarray(self.ratios,float).copy()
        require(b.shape==(3,2) and np.isfinite(b).all(), 'Explicit proper radial basis required')
        require(np.max(abs(b.T@b-np.eye(2)))<1e-12 and np.max(abs(b.T@self.axis))<1e-12 and np.linalg.det(np.column_stack([b,self.axis]))>0, 'Orthonormal proper radial basis must match axis')
        require(r.shape==(2,) and np.isfinite(r).all() and (r>=.75).all() and (r<=1).all(), 'Positive bounded unapplied profile ratios .75..1 required')
        b.flags.writeable=False;r.flags.writeable=False;object.__setattr__(self,'radial_basis',b);object.__setattr__(self,'ratios',r)

    def transform(self,p,inverse=False):
        p=np.asarray(p,float);a=self.coordinates(p);w,_=self.weight(a);active=w!=0;q=p.copy()
        u=(p[active]-self.origin)@self.radial_basis
        factors=1+w[active,None]*(self.ratios-1)
        shift=w[active,None]*(self.delta@self.radial_basis)
        v=(u-shift)/factors if inverse else u*factors+shift
        q[active]+=(v-u)@self.radial_basis.T
        return q

    def jacobian(self,p):
        p=np.asarray(p,float);a=self.coordinates(p);w,dw=self.weight(a);u=(p-self.origin)@self.radial_basis
        r=self.ratios-1
        radial=np.einsum('ij,nj,kj->nik',self.radial_basis,w[:,None]*r,self.radial_basis)
        axial_derivative=(dw[:,None]*r*u)@self.radial_basis.T+dw[:,None]*self.delta
        return np.eye(3)[None]+radial+np.einsum('ni,j->nij',axial_derivative,self.axis)

    def transport(self,p,normals,tangents):
        p=np.asarray(p,float);a=self.coordinates(p);n=np.asarray(normals);t=np.asarray(tangents)
        require(n.shape==p.shape and t.shape==(len(p),4),'Matching P/N/T rows required')
        require(np.issubdtype(n.dtype,np.floating) and np.issubdtype(t.dtype,np.floating) and np.isfinite(n).all() and np.isfinite(t).all(),'Finite floating authored shading required')
        w,_=self.weight(a);affected=w!=0;nn,tt=n.copy(),t.copy()
        if affected.any():
            an,at=n[affected].astype(float),t[affected].astype(float)
            require((np.linalg.norm(an,axis=1)>1e-8).all() and (np.linalg.norm(at[:,:3],axis=1)>1e-8).all() and (abs(at[:,3])==1).all(),'Active N/T/W cannot be degenerate')
        active=np.any(self.jacobian(p)!=np.eye(3)[None],axis=(1,2))
        if not active.any():return nn,tt
        ns,ts=n[active].astype(float),t[active].astype(float);nl=np.linalg.norm(ns,axis=1);tl=np.linalg.norm(ts[:,:3],axis=1)
        require((nl>1e-8).all() and (tl>1e-8).all() and (abs(ts[:,3])==1).all(),'Active N/T/W cannot be degenerate')
        J=self.jacobian(p[active]);require((np.linalg.det(J)>0).all(),'Positive profile Jacobian required')
        outn=np.linalg.solve(np.swapaxes(J,1,2),ns[...,None])[...,0];outn*= (nl/np.linalg.norm(outn,axis=1))[:,None];unit=outn/nl[:,None]
        outt=np.einsum('nij,nj->ni',J,ts[:,:3]);outt-=np.sum(outt*unit,axis=1)[:,None]*unit;length=np.linalg.norm(outt,axis=1)
        require((length>1e-8).all(),'Degenerate GS tangent rejected');outt*= (tl/length)[:,None];nn[active]=outn;tt[active,:3]=outt
        return nn,tt
