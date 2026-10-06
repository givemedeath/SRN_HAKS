"""Encode typed GFF JSON for gallery resources; validated against native nwn_gff."""
import struct


TYPES={'byte':0,'char':1,'word':2,'short':3,'dword':4,'int':5,'dword64':6,'int64':7,'float':8,'double':9,
       'cexostring':10,'resref':11,'cexolocstring':12,'void':13,'struct':14,'list':15}


def encode(document):
    structs=[];fields=[];labels=[];label_ids={};data=bytearray();indices=bytearray();lists=bytearray()
    def append(buffer,payload):
        offset=len(buffer);buffer.extend(payload);return offset
    # NWN's English GFF strings use Windows-1252; UTF-8 produces mojibake
    # in the native decoder and the client. Reject unrepresentable input.
    def text(value):return str(value).encode('cp1252')
    def node(doc):
        identity=len(structs);structs.append(None);owned=[]
        for name,field in doc.items():
            if name.startswith('__'):continue
            if len(name.encode('ascii'))>16:raise ValueError('GFF label exceeds 16 bytes: '+name)
            if name not in label_ids:label_ids[name]=len(labels);labels.append(name.encode('ascii').ljust(16,b'\0'))
            kind=field['type'];value=field['value'];code=TYPES[kind]
            if kind in ('byte','char','word','short','dword','int','float'):
                fmt={'byte':'B','char':'b','word':'H','short':'h','dword':'I','int':'i','float':'f'}[kind]
                payload=struct.pack('<'+fmt,value).ljust(4,b'\0');index=struct.unpack('<I',payload)[0]
            elif kind in ('dword64','int64','double'):
                index=append(data,struct.pack('<'+{'dword64':'Q','int64':'q','double':'d'}[kind],value))
            elif kind=='cexostring':
                raw=text(value);index=append(data,struct.pack('<I',len(raw))+raw)
            elif kind=='resref':
                raw=text(value)
                if len(raw)>16:raise ValueError('GFF resref exceeds 16 bytes')
                index=append(data,bytes([len(raw)])+raw)
            elif kind=='cexolocstring':
                strings=[];strref=4294967295
                for language,string in value.items():
                    if language in ('id','strref','__strref'):
                        strref=int(string);continue
                    raw=text(string);strings.append(struct.pack('<II',int(language),len(raw))+raw)
                content=struct.pack('<II',strref,len(strings))+b''.join(strings);index=append(data,struct.pack('<I',len(content))+content)
            elif kind=='void':
                import base64
                raw=base64.b64decode(value);index=append(data,struct.pack('<I',len(raw))+raw)
            elif kind=='struct':index=node(value)
            elif kind=='list':
                children=[node(child) for child in value];index=append(lists,struct.pack('<I',len(children))+b''.join(struct.pack('<I',child) for child in children))
            else:raise ValueError('Unsupported GFF type: '+kind)
            owned.append(len(fields));fields.append(struct.pack('<III',code,label_ids[name],index))
        offset=owned[0] if len(owned)==1 else append(indices,b''.join(struct.pack('<I',i) for i in owned)) if owned else 0
        structs[identity]=struct.pack('<III',doc.get('__struct_id',-1)&0xffffffff,offset,len(owned));return identity
    node(document);parts=[b''.join(structs),b''.join(fields),b''.join(labels),bytes(data),bytes(indices),bytes(lists)]
    offsets=[];offset=56
    for i,part in enumerate(parts):offsets.extend([offset,len(structs) if i==0 else len(fields) if i==1 else len(labels) if i==2 else len(part)]);offset+=len(part)
    return document['__data_type'].encode('ascii')+b'V3.2'+struct.pack('<12I',*offsets)+b''.join(parts)
