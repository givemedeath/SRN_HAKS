"""Create isolated tile sheets without activating imported SET metadata."""
import re


def sections(text):
    matches=list(re.finditer(r'(?m)^\[([^\]\r\n]+)\][ \t]*\r?$',text))
    return {m.group(1).upper():text[m.end():matches[i+1].start() if i+1<len(matches) else len(text)].strip()
            for i,m in enumerate(matches)}


def inspection_set(stock,source,identities,name):
    """Keep each model identity; use stock non-transitioning display metadata.

    Source SET terrain/crosser/group/door metadata is not activated by a sheet.
    Model geometry and matching model walkmeshes remain unchanged.
    """
    base=sections(stock);original=sections(source)
    if not identities or len(name)>16:raise ValueError('Nonempty tile sheet and valid resref required')
    general=re.sub(r'(?m)^Name=[^\r\n]*','Name='+name.upper(),base['GENERAL'])
    grass=re.sub(r'(?m)^Density=[^\r\n]*','Density=0.000',base['GRASS'])
    template=base['TILE120']
    parts=['[GENERAL]\n'+general,'[GRASS]\n'+grass]
    for key in ('TERRAIN TYPES','CROSSER TYPES'):
        parts.append('['+key+']\n'+base[key])
        prefix='TERRAIN' if key=='TERRAIN TYPES' else 'CROSSER'
        parts.extend('['+k+']\n'+v for k,v in base.items() if re.fullmatch(prefix+r'\d+',k))
    parts += ['[PRIMARY RULES]\nCount=0','[SECONDARY RULES]\nCount=0','[TILES]\nCount='+str(len(identities))]
    for index,identity in enumerate(identities):
        row=original['TILE'+str(identity)]
        model=re.search(r'(?m)^Model=([^\r\n]+)',row)
        if not model or not re.fullmatch(r'[A-Za-z0-9_\-]{1,16}',model.group(1).strip()):raise ValueError('Valid original tile model required')
        tile=re.sub(r'(?m)^Model=[^\r\n]*','Model='+model.group(1).strip(),template)
        tile=re.sub(r'(?m)^AnimLoop[123]=[^\r\n]*',lambda m:m.group(0).split('=')[0]+'=0',tile)
        # The stock tile has no doors/groups and a flat display terrain.
        parts.append('[TILE'+str(index)+']\n'+tile)
    parts.append('[GROUPS]\nCount=0')
    # The installed EE client crashes on these LF-only SET payloads. Emit
    # explicit CRLF bytes through the caller, independent of host text mode.
    return ('\n\n'.join(parts)+'\n').replace('\n','\r\n')
