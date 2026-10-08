"""Lossless face-index descendants and exact-coordinate diagnostic topology.

No attribute rows, authored normals, UVs, tangents, image bytes, vertex positions,
materials, or scene transforms are replaced. Coordinate welding is read-only.
"""
import copy
import hashlib
from pathlib import Path

import numpy as np

from place_purposebuilt_pelvis import accessor, embedded_maps, read_glb, require, write_glb


def mesh_arrays(document, binary):
    require(not document.get('animations') and not document.get('skins'), 'Detached static source required')
    require(len(document['nodes']) == 1 and document['nodes'][0].get('mesh') == 0 and
            not set(document['nodes'][0])-{'mesh','name'}, 'One identity-node source mesh required')
    require(len(document['meshes']) == 1 and len(document['meshes'][0]['primitives']) == 1,
            'One explicit source primitive required')
    primitive=document['meshes'][0]['primitives'][0]
    require(primitive.get('mode',4)==4 and not primitive.get('targets') and not primitive.get('extensions'),
            'Uncompressed indexed source triangles required')
    require({'POSITION','NORMAL','TEXCOORD_0'} <= set(primitive['attributes']),
            'Authored source position, normal and UV required')
    positions=accessor(document,binary,primitive['attributes']['POSITION'])
    faces=accessor(document,binary,primitive['indices']).reshape(-1,3).astype(np.int64)
    require(positions.shape[1]==3 and np.isfinite(positions).all() and len(faces)>0 and
            faces.min()>=0 and faces.max()<len(positions), 'Finite indexed source positions required')
    return positions,faces,primitive


def topology(positions,faces):
    """Account for referenced exact positions; leave original serialized rows alone."""
    referenced=np.unique(faces)
    welded,inverse=np.unique(positions[referenced],axis=0,return_inverse=True)
    lookup=np.full(len(positions),-1,dtype=np.int64);lookup[referenced]=inverse
    triangles=lookup[faces]
    edge_rows=triangles[:,[[0,1],[1,2],[2,0]]].reshape(-1,2)
    ordered=np.sort(edge_rows,axis=1)
    edges,edge_inverse,counts=np.unique(ordered,axis=0,return_inverse=True,return_counts=True)
    signs=np.where(edge_rows[:,0]<edge_rows[:,1],1,-1)
    winding=np.bincount(edge_inverse,weights=signs,minlength=len(edges))
    face_ids=np.repeat(np.arange(len(faces)),3)
    neighbors=[[] for _ in edges]
    for edge,face in zip(edge_inverse,face_ids):neighbors[int(edge)].append(int(face))
    boundary_ids=np.flatnonzero(counts==1);nonmanifold_ids=np.flatnonzero(counts>2)
    boundary=edges[boundary_ids]
    graph={}
    for a,b in boundary:
        graph.setdefault(int(a),[]).append(int(b));graph.setdefault(int(b),[]).append(int(a))
    pending=set(graph);loops=[]
    while pending:
        first=min(pending);component={first};stack=[first]
        while stack:
            current=stack.pop()
            for other in graph[current]:
                if other not in component:component.add(other);stack.append(other)
        pending-=component
        closed=all(len(graph[v])==2 for v in component)
        if closed:
            row=[first];previous=None;current=first
            while True:
                next_vertex=next(v for v in graph[current] if v!=previous)
                if next_vertex==first:break
                require(next_vertex not in row,'Ambiguous boundary cycle')
                row.append(next_vertex);previous,current=current,next_vertex
        else:row=sorted(component)
        coords=welded[row].astype(float)
        loops.append({'closedDegreeTwoRing':closed,'exactPositionIds':row,'positions':coords.tolist(),
                      'vertexCount':len(row),'minimum':coords.min(0).tolist(),'maximum':coords.max(0).tolist(),
                      'maximumChord':float(np.linalg.norm(coords[:,None,:]-coords[None,:,:],axis=2).max()) if len(row)<=256 else None,
                      'maximumChordUpperBound':float(np.linalg.norm(np.ptp(coords,axis=0))),
                      'perimeter':float(np.linalg.norm(np.roll(coords,-1,axis=0)-coords,axis=1).sum()) if closed else None})
    corners=welded[triangles].astype(float)
    cross=np.cross(corners[:,1]-corners[:,0],corners[:,2]-corners[:,0])
    area=np.linalg.norm(cross,axis=1)/2
    roots=list(range(len(welded)))
    def find(v):
        while roots[v]!=v:roots[v]=roots[roots[v]];v=roots[v]
        return v
    for a,b in edges:
        a,b=find(int(a)),find(int(b))
        if a!=b:roots[b]=a
    components=len({find(i) for i in range(len(welded))})
    links=[[] for _ in welded]
    for a,b,c in triangles:
        links[int(a)].append((int(b),int(c)))
        links[int(b)].append((int(c),int(a)))
        links[int(c)].append((int(a),int(b)))
    bad_links=[]
    for vertex,pairs in enumerate(links):
        link_graph={}
        for a,b in pairs:
            link_graph.setdefault(a,[]).append(b);link_graph.setdefault(b,[]).append(a)
        first=next(iter(link_graph));seen={first};stack=[first]
        while stack:
            for other in link_graph[stack.pop()]:
                if other not in seen:seen.add(other);stack.append(other)
        degrees=[len(v) for v in link_graph.values()]
        if len(seen)!=len(link_graph) or any(degree>2 for degree in degrees) or degrees.count(1) not in (0,2):
            bad_links.append(vertex)
    return {'referencedSerializedVertices':len(referenced),'exactPositionVertices':len(welded),'faces':len(faces),
            'boundaryEdges':len(boundary_ids),'nonmanifoldEdges':len(nonmanifold_ids),
            'inconsistentManifoldEdgeWindings':int(np.count_nonzero((counts==2)&(winding!=0))),
            'zeroAreaFaces':int(np.count_nonzero(area<=1e-15)),
            'nonmanifoldVertexLinks':len(bad_links),'nonmanifoldVertexPositions':welded[bad_links].tolist(),
            'surfaceArea':float(area.sum()),
            'signedVolume':float(np.einsum('ij,ij->i',corners[:,0],cross).sum()/6),
            'components':components,'eulerCharacteristic':len(welded)-len(edges)+len(faces),
            'boundaryLoops':loops,
            'nonmanifoldEdgeRecords':[{'exactPositionIds':edges[i].tolist(),
                'positions':welded[edges[i]].astype(float).tolist(),'incidentFaces':neighbors[i]} for i in nonmanifold_ids],
            'boundaryIncidentFaceIds':sorted({neighbors[i][0] for i in boundary_ids})}


def face_components(positions,faces):
    """Connected face sets through exact-position shared edges, never UV welding."""
    _,inverse=np.unique(positions,axis=0,return_inverse=True)
    triangles=inverse[faces];edges=np.sort(triangles[:,[[0,1],[1,2],[2,0]]].reshape(-1,2),axis=1)
    _,labels=np.unique(edges,axis=0,return_inverse=True)
    order=np.argsort(labels,kind='stable');owners=np.repeat(np.arange(len(faces)),3)
    roots=list(range(len(faces)))
    def find(v):
        while roots[v]!=v:roots[v]=roots[roots[v]];v=roots[v]
        return v
    previous=None;first=None
    for index in order:
        label=int(labels[index]);owner=find(int(owners[index]))
        if label!=previous:first=owner;previous=label
        else:
            first=find(first)
            if first!=owner:roots[owner]=first
    component=np.fromiter((find(i) for i in range(len(faces))),np.int64,count=len(faces))
    return sorted([np.flatnonzero(component==label) for label in np.unique(component)],key=len,reverse=True)


def cap_one_micro_boundary(positions,faces,max_chord,max_area):
    """Close one measured tiny ring using only source positions/attribute rows."""
    before=topology(positions,faces)
    require(len(before['boundaryLoops'])==1 and before['boundaryLoops'][0]['closedDegreeTwoRing'],
            'Exactly one unbranched boundary ring required')
    loop=before['boundaryLoops'][0];coords=np.asarray(loop['positions'],float)
    require(3<=len(coords)<=8 and loop['maximumChord']<=max_chord,
            'Measured small connector ring exceeds the explicit repair bound')
    _,inverse=np.unique(positions,axis=0,return_inverse=True)
    source_welded=np.unique(positions,axis=0)
    ring=[int(np.flatnonzero(np.all(source_welded==point,axis=1))[0]) for point in coords]
    edges={}
    for original,mapped in zip(faces,inverse[faces]):
        for i,j in ((0,1),(1,2),(2,0)):
            key=tuple(sorted((int(mapped[i]),int(mapped[j]))))
            edges.setdefault(key,[]).append((int(mapped[i]),int(mapped[j]),int(original[i]),int(original[j])))
    direction=edges[tuple(sorted(ring[:2]))]
    require(len(direction)==1,'Boundary ring edge ownership differs')
    if direction[0][:2]==tuple(ring[:2]):ring.reverse();coords=coords[::-1]
    for a,b in zip(ring,ring[1:]+ring[:1]):
        row=edges[tuple(sorted((a,b)))];require(len(row)==1 and row[0][:2]==(b,a),
            'Micro cap must oppose every existing boundary edge winding')
    # Reuse a serialized row from the neighboring retained source face. Existing
    # UV seam variants remain exact; this chooses one variant only for new faces.
    original_ids=[edges[tuple(sorted((a,b)))][0][3] for a,b in zip(ring,ring[1:]+ring[:1])]
    _,_,axes=np.linalg.svd(coords-coords.mean(0));normal=axes[-1]
    polygon_normal=np.sum(np.cross(coords,np.roll(coords,-1,axis=0)),axis=0)
    require(np.linalg.norm(polygon_normal)>1e-12,'Degenerate repair boundary')
    if np.dot(normal,polygon_normal)<0:normal=-normal
    projected=(coords-coords.mean(0))@axes[:2].T
    def triangulations(poly):
        if len(poly)<3:return [[]]
        if len(poly)==3:return [[tuple(poly)]]
        result=[]
        for k in range(1,len(poly)-1):
            for left in triangulations(poly[:k+1]):
                for right in triangulations(poly[k:]):
                    result.append(left+right+[(poly[0],poly[k],poly[-1])])
        return result
    choices=[]
    shifted=np.roll(projected,-1,axis=0)
    polygon_area=abs(float(np.sum(projected[:,0]*shifted[:,1]-projected[:,1]*shifted[:,0])/2))
    for triangles in triangulations(list(range(len(coords)))):
        indices=np.asarray(triangles,int);corners=coords[indices]
        cross=np.cross(corners[:,1]-corners[:,0],corners[:,2]-corners[:,0])
        length=np.linalg.norm(cross,axis=1)
        if np.any(length<=1e-12) or np.any(cross@normal<=0):continue
        uv=projected[indices];a=uv[:,1]-uv[:,0];b=uv[:,2]-uv[:,0]
        area=np.abs(a[:,0]*b[:,1]-a[:,1]*b[:,0])/2
        if abs(float(area.sum())-polygon_area)>1e-10:continue
        surface=float(length.sum()/2)
        if surface>max_area:continue
        choices.append((float(np.max(1-(cross/length[:,None])@normal)),surface,indices,cross/length[:,None]))
    require(choices,'No bounded coherent source-vertex triangulation exists')
    choices.sort(key=lambda row:(row[0],row[1]));score,area,indices,normals=choices[0]
    added=np.asarray(original_ids,dtype=np.int64)[indices]
    after=topology(positions,np.concatenate((faces,added)))
    require(after['boundaryEdges']==after['nonmanifoldEdges']==after['inconsistentManifoldEdgeWindings']==
            after['nonmanifoldVertexLinks']==after['zeroAreaFaces']==0 and after['components']==1 and
            after['signedVolume']>0,'Micro repair fails closed coherent retained exterior topology')
    return added,{'sourceBoundary':loop,'addedSourceVertexFaces':added.tolist(),
        'addedFaceGeometricNormals':normals.tolist(),'addedSurfaceArea':area,
        'maximumPlaneNormalDeviation':score,'maximumChordBound':max_chord,'maximumAreaBound':max_area,
        'attributePolicy':'Only existing neighboring source vertex rows reused; no new UV/normal/position data',
        'beforeTopology':before,'afterTopology':after}


def descendant(source, output, kept_ids, added_source_vertex_faces=()):
    """Append only an index accessor; verify all kept corner encodings byte-for-byte."""
    document,binary=read_glb(source);positions,faces,primitive=mesh_arrays(document,binary)
    kept=np.asarray(kept_ids,dtype=np.int64)
    require(kept.ndim==1 and len(kept)>0 and np.all(np.diff(kept)>0) and
            kept[0]>=0 and kept[-1]<len(faces), 'Ordered unique kept source face IDs required')
    added=np.asarray(added_source_vertex_faces,dtype=np.int64).reshape(-1,3)
    require(not len(added) or (added.min()>=0 and added.max()<len(positions)),
            'Added connector indices must reuse original source vertex rows')
    selected=np.concatenate((faces[kept],added)).reshape(-1).astype('<u4')
    result=copy.deepcopy(document);payload=bytearray(binary);payload.extend(b'\0'*(-len(payload)%4))
    offset=len(payload);payload.extend(selected.tobytes());payload.extend(b'\0'*(-len(payload)%4))
    result['bufferViews'].append({'buffer':0,'byteOffset':offset,'byteLength':selected.nbytes,'target':34963})
    result['accessors'].append({'bufferView':len(result['bufferViews'])-1,'componentType':5125,
        'count':len(selected),'type':'SCALAR','min':[int(selected.min())],'max':[int(selected.max())]})
    result['meshes'][0]['primitives'][0]['indices']=len(result['accessors'])-1
    result['buffers'][0]['byteLength']=len(payload)
    output=Path(output);require(not output.exists(),'Fresh face-selection descendant required')
    write_glb(output,result,bytes(payload))
    actual,actualbin=read_glb(output);ap,af,apr=mesh_arrays(actual,actualbin)
    require(actualbin[:len(binary)]==binary,'Original padded source BIN prefix changed')
    require(actual['materials']==document['materials'] and
            embedded_maps(actual,actualbin)==embedded_maps(document,binary),'Source materials/image bytes changed')
    require(apr['attributes']==primitive['attributes'] and
            np.array_equal(af[:len(kept)],faces[kept]),'Kept source attributes/triangle order changed')
    for semantic,index in primitive['attributes'].items():
        old=accessor(document,binary,index,allow_normalized=True)
        new=accessor(actual,actualbin,index,allow_normalized=True)
        require(old.dtype==new.dtype and np.array_equal(old,new) and old.tobytes()==new.tobytes(),
                'Authored accessor bytes changed: '+semantic)
    # JSON dictionaries other than new indexing bookkeeping remain exact.
    restored=copy.deepcopy(actual);restored['buffers']=copy.deepcopy(document['buffers'])
    restored['bufferViews']=restored['bufferViews'][:len(document['bufferViews'])]
    restored['accessors']=restored['accessors'][:len(document['accessors'])]
    restored['meshes'][0]['primitives'][0]['indices']=primitive['indices']
    require(restored==document,'Undeclared scene/material/accessor metadata change')
    return {'sourceBinPrefixExact':True,'allOriginalAttributeAccessorsExact':True,
            'keptCornerEncodedBytesExact':True,'materialsAndEmbeddedImagesExact':True,
            'onlyAppendedIndexAccessorAndPrimitiveIndexReferenceChanged':True,
            'keptSourceFaces':len(kept),'deletedSourceFaces':len(faces)-len(kept),
            'addedConnectorFaces':len(added),'addedVertexRows':0,'positionMovement':0,'normalChanges':0,
            'keptFaceIdsSha256':hashlib.sha256(kept.astype('<i8').tobytes()).hexdigest(),
            'afterTopology':topology(ap,af)}
