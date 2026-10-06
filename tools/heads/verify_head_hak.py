"""Verify the rebuilt head HAK payload exactly matches publication pins."""
import argparse
import hashlib
from pathlib import Path
import struct
from head_workflow import pin, read, require, write_fresh

TYPES={"tga":3,"plt":6,"mdl":2002,"txi":2022,"dds":2033,"mtr":2072}


def payload(path):
    data=Path(path).read_bytes()
    require(len(data)>=160 and data[:8]==b"HAK V1.0", "Expected native HAK archive")
    count=struct.unpack_from("<I",data,16)[0]
    keys,resources=struct.unpack_from("<II",data,24)
    require(keys>=160 and resources>=160 and keys+24*count<=len(data) and resources+8*count<=len(data),
            "Invalid HAK table bounds")
    rows={}
    for index in range(count):
        name,identity,kind=struct.unpack_from("<16sIH",data,keys+24*index)
        require(identity<count,"Invalid HAK resource ID")
        offset,size=struct.unpack_from("<II",data,resources+8*identity)
        require(offset>=160 and offset+size<=len(data),"Invalid HAK payload bounds")
        key=(name.split(b"\0",1)[0].decode("ascii"),kind)
        require(key not in rows,"Duplicate HAK resource")
        rows[key]=hashlib.sha256(data[offset:offset+size]).hexdigest()
    return rows


def write_hak(path, entries):
    count = len(entries)
    keys_offset = 160
    res_offset = 160 + 24 * count
    data_offset = res_offset + 8 * count
    total_len = data_offset + sum(len(d) for _, _, d in entries)
    buf = bytearray(total_len)
    buf[:8] = b"HAK V1.0"
    struct.pack_into("<I", buf, 16, count)
    struct.pack_into("<II", buf, 24, keys_offset, res_offset)
    cur_data = data_offset
    for i, (name, kind, data) in enumerate(entries):
        struct.pack_into("<16sIH", buf, keys_offset + 24 * i, name.encode("ascii"), i, kind)
        struct.pack_into("<II", buf, res_offset + 8 * i, cur_data, len(data))
        buf[cur_data:cur_data + len(data)] = data
        cur_data += len(data)
    Path(path).write_bytes(buf)


def verify(hak, manifest, output):
    document=read(manifest)
    require(document["kind"]=="srn-head-publication","Accepted publication manifest required")
    expected={(Path(p["path"]).stem,TYPES[Path(p["path"]).suffix[1:]]):p["sha256"] for p in document["resources"]}
    require(expected and len(expected)==len(document["resources"]) and payload(hak)==expected,
            "Head HAK differs from exact publication pins")
    write_fresh(output,{"kind":"srn-head-hak-verification","hak":pin(hak),"publication":pin(manifest),
                        "payloadHashesVerified":True,"resources":len(expected)})


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("hak","manifest","output"):parser.add_argument("--"+name,type=Path,required=True)
    args=parser.parse_args();verify(args.hak,args.manifest,args.output)
