"""Independent ASCII controller inventory and parent-frame compatibility checks.

Model roots are namespaced aliases of the same identity frame. Translations of
parent origins may differ between source and target: bind-relative retargeting
explicitly replaces them. Parent axes must agree if rotation controllers are
preserved without a basis change.
"""
import copy
import re
import numpy as np

from retarget import NODE, nodes, rotations
from target_contract import require

CLIP = re.compile(r'(?mis)^newanim\s+(\S+)\s+\S+\s*\n(.*?)^doneanim[^\n]*')
ARRAY = re.compile(r'(?m)^([ \t]*)(\w+key)(?:[ \t]+(\d+))?[ \t]*\n')


def effective_nodes(name, chain_nodes, parents, root_nodes):
    """Resolve inherited geometry, with the phenotype root as last fallback."""
    order, current = [], name
    while current != 'null':
        require(current not in order, 'Supermodel inheritance cycle')
        require(current in chain_nodes and current in parents,
                'Missing supermodel bind inventory: ' + current)
        order.append(current)
        current = parents[current]
    result = copy.deepcopy(root_nodes)
    for owner in reversed(order):
        result.update(copy.deepcopy(chain_nodes[owner]))
    return result


def world_frames(skeleton):
    """Strict hierarchy evaluation: reject missing parents and cycles."""
    output, visiting = {}, set()
    def visit(name):
        if name in output:
            return output[name]
        require(name in skeleton, 'Unresolved parent bind: ' + name)
        require(name not in visiting, 'Geometry parent cycle: ' + name)
        visiting.add(name)
        row = skeleton[name]
        matrix = np.eye(4)
        matrix[:3, :3] = rotations(row['orientation'])
        matrix[:3, 3] = row['position']
        if row['parent'] != 'null':
            matrix = visit(row['parent']) @ matrix
        visiting.remove(name)
        output[name] = matrix
        return matrix
    for name in skeleton:
        visit(name)
    return output


def compatible_parent_basis(source_row, target_row, source_frames, target_frames,
                            *, tolerance=1e-6):
    """Prove parent-local vector axes agree; return measured rotation error."""
    def basis(row, frames):
        name = row['parent']
        if name == 'null':
            return np.eye(3)
        require(name in frames, 'Unresolved controller parent frame: ' + name)
        return frames[name][:3, :3]
    error = float(np.max(np.abs(basis(source_row, source_frames) -
                                basis(target_row, target_frames))))
    require(error <= tolerance, 'Incompatible controller parent-local axes: ' +
            source_row['parent'] + ' -> ' + target_row['parent'])
    return error


def arrays(body):
    result = []
    for match in ARRAY.finditer(body):
        remaining=body[match.end():].splitlines(keepends=True)
        if match[3] is not None:
            count=int(match[3]);lines=remaining[:count]
            require(len(lines)==count,'Truncated controller array: '+match[2])
            end=match.end()+sum(len(line) for line in lines)
        else:
            terminator=next((i for i,line in enumerate(remaining)
                             if line.strip().lower()=='endlist'),None)
            require(terminator is not None,'Missing controller endlist: '+match[2])
            lines=remaining[:terminator]
            end=match.end()+sum(len(line) for line in remaining[:terminator+1])
        lines=[line for line in lines if line.strip() and not line.lstrip().startswith('#')]
        values = [[float(v) for v in line.split()] for line in lines]
        require(values and len({len(row) for row in values}) == 1,
                'Inconsistent controller row arity: ' + match[2])
        require(np.isfinite(values).all(), 'Nonfinite controller array')
        result.append((match[2].lower(), values, match.start(), end))
    return result


def controller_signature(text):
    """Inventory all node/controller ownership, ignoring formatting only."""
    output = []
    for clip in CLIP.finditer(text):
        entries = []
        for node in NODE.finditer(clip[2]):
            body = node[3]
            keyed = [(label, values) for label, values, _, _ in arrays(body)]
            static_body = body
            for _, _, start, end in reversed(arrays(body)):
                static_body = static_body[:start] + static_body[end:]
            static = [tuple(line.split()) for line in static_body.splitlines()
                      if line.strip() and not line.strip().startswith('#')]
            entries.append({'name':node[2].lower(), 'type':node[1].lower(),
                            'keyed':keyed, 'static':static})
        output.append({'clip':clip[1].lower(), 'nodes':entries})
    return output


def preserved_controller_signature(text, aliases=None):
    """Discard only authorized position and parent/model-name substitutions."""
    aliases = aliases or {}
    result = controller_signature(text)
    for clip in result:
        for node in clip['nodes']:
            node['name'] = aliases.get(node['name'], node['name'])
            node['keyed'] = [(name, values) for name, values in node['keyed']
                             if name not in ('positionkey','positionbezierkey')]
            node['static'] = [row for row in node['static']
                              if row[0].lower() not in ('parent','position')]
    return result
