"""Build the isolated robe trial HAK, parts_robe rows, test items and comparison module.

Everything is written into a fresh staging folder and an isolated client user
directory; nothing touches repository packs, srn_2da or hakbuilder. Actors wear
stock, control and candidate robes side by side and cycle the motion matrix.
The receipt records exact resource hashes; it is not client evidence.
"""
import argparse
import copy
import json
import re
import shutil
import subprocess
from pathlib import Path

from robe_common import FLAGS, fresh_directory, pin, read, require, sha, utc, verify_pins, write_fresh
from tool_runtime import tool as resolved_tool

HIDE = ("HIDEFOOTR", "HIDEFOOTL", "HIDESHINR", "HIDESHINL", "HIDELEGR", "HIDELEGL", "HIDEPELVIS", "HIDECHEST",
        "HIDEBELT", "HIDENECK", "HIDEFORER", "HIDEFOREL", "HIDEBICEPR", "HIDEBICEPL", "HIDESHOR", "HIDESHOL",
        "HIDEHANDR", "HIDEHANDL", "HIDEHEAD")
MOTION = [("idle", "ActionPlayAnimation(ANIMATION_LOOPING_PAUSE2,1.0,5.5);"),
          ("walk", "WALK"), ("run", "RUN"), ("melee", "ATTACK"), ("melee", "ATTACK"),
          ("cast", "ActionPlayAnimation(ANIMATION_LOOPING_CONJURE1,1.0,5.5);"),
          ("raised-arms", "ActionPlayAnimation(ANIMATION_LOOPING_CONJURE2,1.0,5.5);"),
          ("bent-arms", "ActionPlayAnimation(ANIMATION_FIREFORGET_DRINK,1.0);"),
          ("crouch", "ActionPlayAnimation(ANIMATION_LOOPING_GET_LOW,1.0,5.5);"),
          ("sit", "ActionPlayAnimation(ANIMATION_LOOPING_SIT_CROSS,1.0,5.5);"),
          ("kneel", "ActionPlayAnimation(ANIMATION_LOOPING_MEDITATE,1.0,5.5);"),
          ("knockdown", "ActionPlayAnimation(ANIMATION_LOOPING_DEAD_FRONT,1.0,5.5);"),
          ("unequip", "UNEQUIP"), ("re-equip", "REEQUIP"),
          ("death-back", "ActionPlayAnimation(ANIMATION_LOOPING_DEAD_BACK,1.0,5.5);")]


def field(kind, value):
    return {"type": kind, "value": value}


def structure(kind, **values):
    return {"__data_type": kind, **values}


def write_2da(path, columns, rows):
    widths = [max(len(c), 4) + 2 for c in columns]
    lines = ["2DA V2.0", "", "    " + "".join(c.ljust(w) for c, w in zip(columns, widths))]
    # The engine indexes 2DA rows by position, not label: gaps are padded with empty rows so labels stay true.
    for index in range(max(rows) + 1):
        values = [str(rows.get(index, {}).get(c, "****")) for c in columns]
        lines.append(str(index).ljust(4) + "".join(v.ljust(w) for v, w in zip(values, widths)))
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def read_2da(path):
    lines = [line for line in Path(path).read_text(encoding="cp1252").splitlines() if line.strip()]
    columns = lines[1].split()
    return columns, {int(v[0]): dict(zip(columns, v[1:])) for v in (line.split() for line in lines[2:])}


def renamed_model(source, old, new):
    text = Path(source).read_text(encoding="cp1252")
    lines = []
    for line in text.splitlines():
        if line.strip().lower().startswith("bitmap"):
            lines.append(line)
        else:
            lines.append(re.sub(r"\b" + re.escape(old) + r"\b", new, line, flags=re.IGNORECASE))
    return "\n".join(lines) + "\n"


def scripts(actors, rows):
    steps = len(MOTION)
    cases = []
    for number, (family, command) in enumerate(MOTION):
        if command == "WALK" or command == "RUN":
            run = "TRUE" if command == "RUN" else "FALSE"
            body = ('vector h=GetPositionFromLocation(GetLocalLocation(OBJECT_SELF,"HOME"));'
                    'location far=Location(GetArea(OBJECT_SELF),Vector(h.x,h.y+6.0,h.z),180.0);'
                    'ActionMoveToLocation(far,' + run + ');'
                    'ActionMoveToLocation(GetLocalLocation(OBJECT_SELF,"HOME"),' + run + ');')
        elif command == "ATTACK":
            body = 'ActionAttack(GetObjectByTag("sr_rt_d"+GetStringRight(GetTag(OBJECT_SELF),GetStringLength(GetTag(OBJECT_SELF))-7)));'
        elif command == "UNEQUIP":
            body = 'ActionUnequipItem(GetItemInSlot(INVENTORY_SLOT_CHEST,OBJECT_SELF));'
        elif command == "REEQUIP":
            body = 'ActionEquipItem(GetItemPossessedBy(OBJECT_SELF,GetLocalString(OBJECT_SELF,"ROBE")),INVENTORY_SLOT_CHEST);'
        else:
            body = command
        cases.append(f'  if(step=={number}) {{ ClearAllActions(TRUE); ActionJumpToLocation(GetLocalLocation(OBJECT_SELF,"HOME")); {body} '
                     f'WriteTimestampedLogEntry("ROBE_STEP actor="+GetTag(OBJECT_SELF)+" step={number} family={family}"); }}')
    heartbeat = ("void main() {\n  if(!GetLocalInt(OBJECT_SELF,\"READY\")) return;\n"
                 "  int step=GetLocalInt(OBJECT_SELF,\"STEP\") % " + str(steps) + ";\n"
                 "  SetLocalInt(OBJECT_SELF,\"STEP\",step+1);\n" + "\n".join(cases) + "\n}\n")
    spawn = """void main() {
  int i; for(i=0;i<18;i++) SetCreatureBodyPart(i,1);
  SetCreatureBodyPart(CREATURE_PART_BELT,0);
  SetCreatureBodyPart(CREATURE_PART_RIGHT_SHOULDER,0);
  SetCreatureBodyPart(CREATURE_PART_LEFT_SHOULDER,0);
  SetColor(OBJECT_SELF,COLOR_CHANNEL_SKIN,GetLocalInt(OBJECT_SELF,"SKIN"));
  object robe=CreateItemOnObject(GetLocalString(OBJECT_SELF,"ROBE"),OBJECT_SELF);
  ActionEquipItem(robe,INVENTORY_SLOT_CHEST);
  string right=GetLocalString(OBJECT_SELF,"RIGHT"); string left=GetLocalString(OBJECT_SELF,"LEFT");
  if(right!="") ActionEquipItem(CreateItemOnObject(right,OBJECT_SELF),INVENTORY_SLOT_RIGHTHAND);
  if(left!="") ActionEquipItem(CreateItemOnObject(left,OBJECT_SELF),INVENTORY_SLOT_LEFTHAND);
  SetLocalLocation(OBJECT_SELF,"HOME",GetLocation(OBJECT_SELF));
  SetLocalInt(OBJECT_SELF,"READY",1);
  DelayCommand(2.0,ExecuteScript("sr_rt_report",OBJECT_SELF));
}
"""
    report = """void main() {
  object chest=GetItemInSlot(INVENTORY_SLOT_CHEST,OBJECT_SELF);
  WriteTimestampedLogEntry("ROBE_ACTOR tag="+GetTag(OBJECT_SELF)+" name="+GetName(OBJECT_SELF)
    +" chest="+GetResRef(chest)+" robeRow="+IntToString(GetItemAppearance(chest,ITEM_APPR_TYPE_ARMOR_MODEL,ITEM_APPR_ARMOR_MODEL_ROBE))
    +" phenotype="+IntToString(GetPhenoType(OBJECT_SELF))+" skin="+IntToString(GetColor(OBJECT_SELF,COLOR_CHANNEL_SKIN))
    +" right="+GetResRef(GetItemInSlot(INVENTORY_SLOT_RIGHTHAND,OBJECT_SELF))+" left="+GetResRef(GetItemInSlot(INVENTORY_SLOT_LEFTHAND,OBJECT_SELF)));
}
"""
    items = "".join(f'  CreateItemOnObject("sr_rt_r{row}",p);\n' for row in rows)
    enter = ("void main() {\n  object p=GetEnteringObject();\n  if(!GetIsPC(p)) return;\n" + items +
             '  CreateItemOnObject("nw_wswls001",p); CreateItemOnObject("nw_ashlw001",p); CreateItemOnObject("nw_wswgs001",p);\n'
             '  WriteTimestampedLogEntry("ROBE_MODULE_ENTER pc="+GetName(p));\n}\n')
    equip = """void main() {
  object item=GetPCItemLastEquipped(); object who=GetPCItemLastEquippedBy();
  if(GetBaseItemType(item)==BASE_ITEM_ARMOR)
    WriteTimestampedLogEntry("ROBE_EQUIP who="+GetName(who)+" item="+GetResRef(item)+" robeRow="+IntToString(GetItemAppearance(item,ITEM_APPR_TYPE_ARMOR_MODEL,ITEM_APPR_ARMOR_MODEL_ROBE)));
}
"""
    unequip = """void main() {
  object item=GetPCItemLastUnequipped();
  if(GetBaseItemType(item)==BASE_ITEM_ARMOR)
    WriteTimestampedLogEntry("ROBE_UNEQUIP item="+GetResRef(item)+" robeRow="+IntToString(GetItemAppearance(item,ITEM_APPR_TYPE_ARMOR_MODEL,ITEM_APPR_ARMOR_MODEL_ROBE)));
}
"""
    return {"sr_rt_spawn": spawn, "sr_rt_hb": heartbeat, "sr_rt_report": report, "sr_rt_enter": enter,
            "sr_rt_equip": equip, "sr_rt_unequip": unequip}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--game-root", type=Path, required=True)
    parser.add_argument("--user-directory", type=Path, required=True, help="Isolated client test userdir")
    parser.add_argument("--staging", type=Path, required=True)
    args = parser.parse_args()
    fixture = read(args.fixture)
    require(fixture["kind"] == "srn-robe-fixture", "Robe fixture configuration required")
    run_root, userdir = args.run_root.resolve(), args.user_directory.resolve()
    staging = fresh_directory(args.staging)
    json_dir, binary, resources = staging / "json", staging / "binary", staging / "hak-resources"
    for directory in (json_dir, binary, resources, userdir / "hak", userdir / "modules", userdir / "override"):
        directory.mkdir(parents=True, exist_ok=True)
    require(not any((userdir / "override").iterdir()), "Isolated userdir override must be empty")
    common = ["--root", str(args.game_root), "--userdirectory", str(userdir), "--no-ovr"]
    inputs, executables = [], {}

    def tool(name, arguments):
        if name not in executables:  # every invoked executable is pinned and re-verified with the inputs
            executables[name] = resolved_tool(name)
            inputs.append(pin(executables[name]))
        result = subprocess.run([str(executables[name]), *map(str, arguments)], capture_output=True)
        require(result.returncode == 0, name + " failed: " + result.stderr.decode(errors="replace")[-600:])
        return result.stdout

    def installed(name):
        """Installed game resource, staged under installed/ and pinned so the receipt names the bytes used."""
        data = tool("nwn_resman_cat", [*common, name])
        require(bool(data), "Installed resource missing: " + name)
        path = staging / "installed" / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(data)
        inputs.append(pin(path))
        return data

    def gff_json(name):
        installed(name)
        path = staging / "installed" / name
        out = staging / "installed" / (name + ".json")
        tool("nwn_gff", ["-i", path, "-o", out])
        return json.loads(out.read_text(encoding="utf-8"))

    inputs.append(pin(args.fixture))
    columns, table = read_2da(run_root / fixture["partsRobe"])
    inputs.append(pin(run_root / fixture["partsRobe"]))
    for row, spec in fixture["rows"].items():
        hide = spec["hide"] if isinstance(spec["hide"], dict) else \
            {c: table[int(spec["hide"].split(":")[1])][c] for c in HIDE}
        stock = table.get(int(row), {})  # an overridden stock row keeps its cost and AC; new rows get none
        kept = {c: stock[c] if stock.get(c, "****") != "****" else default
                for c, default in (("COSTMODIFIER", 0), ("ACBONUS", "0.00"))}
        table[int(row)] = {**kept, **{c: int(hide[c]) for c in HIDE}}
        source = run_root / spec["model"]
        inputs.append(pin(source))
        target = resources / (spec["resref"] + ".mdl")
        if source.read_bytes()[:4] == b"\0\0\0\0":  # client-compiled binary: names are baked in
            require(spec["sourceName"].lower() == spec["resref"].lower(), "Binary models cannot be renamed: " + row)
            shutil.copyfile(source, target)
            continue
        text = renamed_model(source, spec["sourceName"], spec["resref"])
        target.write_text(text, encoding="cp1252", newline="\n")
    write_2da(resources / "parts_robe.2da", columns, table)
    for item in fixture["resources"]:
        source = run_root / item
        inputs.append(pin(source))
        shutil.copyfile(source, resources / source.name)
    for path in resources.iterdir():
        require(len(path.stem) <= 16 and path.name == path.name.lower(), "Invalid resref: " + path.name)
    tileset = installed("ttr01.set").decode("cp1252")
    tileset = re.sub(r"(?m)^Name=TTR01$", "Name=SR_RT", tileset)
    tileset = re.sub(r"(?m)^Density=[^\n]+", "Density=0.000", tileset)
    (resources / "sr_rt.set").write_text(tileset, encoding="cp1252")
    (resources / "sr_rt_edge.2da").write_bytes(installed("ttr01_edge.2da"))
    hak = userdir / "hak" / (fixture["hak"] + ".hak")
    if hak.exists():
        hak.unlink()
    tool("nwn_erf", ["-c", "-f", hak, "-e", "HAK", resources])
    inventory = tool("nwn_erf", ["-t", "-f", hak]).decode().split()
    require(len(inventory) == len(list(resources.iterdir())), "HAK inventory mismatch")
    template = gff_json(fixture["templates"]["creature"] + ".utc")
    armor = gff_json(fixture["templates"]["armor"] + ".uti")
    rows = sorted({actor["row"] for actor in fixture["actors"]})
    for row in rows:
        item = copy.deepcopy(armor)
        for key in list(item):
            if key.startswith("ArmorPart_"):
                item[key] = field("byte", 0 if key in ("ArmorPart_Belt", "ArmorPart_LShoul", "ArmorPart_RShoul") else 1)
        item["ArmorPart_Robe"] = field("byte", row)
        name = f"sr_rt_r{row}"
        item.update(TemplateResRef=field("resref", name), Tag=field("cexostring", name),
                    LocalizedName=field("cexolocstring", {"0": fixture["rowLabels"].get(str(row), f"Robe row {row}")}),
                    Identified=field("byte", 1), PropertiesList=field("list", []), Plot=field("byte", 0))
        path = json_dir / (name + ".uti.json")
        path.write_text(json.dumps(item), encoding="utf-8")
        tool("nwn_gff", ["-i", path, "-o", binary / (name + ".uti")])
    creatures = []
    for index, actor in enumerate(fixture["actors"]):
        creature = copy.deepcopy(template)
        creature.pop("__data_type", None)
        creature["__struct_id"] = 4
        for key in list(creature):
            if key.startswith("Script"):
                creature[key] = field("resref", "")
        weapons = actor.get("weapons", [])
        creature.update({"Appearance_Type": field("word", 6), "Race": field("byte", 6), "Gender": field("byte", 0),
                         "Phenotype": field("int", 0), "FirstName": field("cexolocstring", {"0": actor["label"]}),
                         # The static-appearance template has no head; dynamic appearance 6 needs one.
                         "Appearance_Head": field("byte", actor.get("head", 1)),
                         "LastName": field("cexolocstring", {}), "Tag": field("cexostring", f"sr_rt_a{index}"),
                         "TemplateResRef": field("resref", f"sr_rt_a{index}"), "FactionID": field("word", 2),
                         "Plot": field("byte", 1), "Conversation": field("resref", ""),
                         "Equip_ItemList": field("list", []), "ItemList": field("list", []),
                         "ScriptSpawn": field("resref", "sr_rt_spawn"), "ScriptHeartbeat": field("resref", "sr_rt_hb"),
                         "XPosition": field("float", 6.0 + index * 3.5), "YPosition": field("float", 14.0),
                         "ZPosition": field("float", 0.0), "XOrientation": field("float", 0.0),
                         "YOrientation": field("float", 1.0),
                         "VarTable": field("list", [
                             {"__struct_id": 0, "Name": field("cexostring", "ROBE"), "Type": field("dword", 3),
                              "Value": field("cexostring", f"sr_rt_r{actor['row']}")},
                             {"__struct_id": 0, "Name": field("cexostring", "SKIN"), "Type": field("dword", 1),
                              "Value": field("int", actor.get("skin", 3))},
                             {"__struct_id": 0, "Name": field("cexostring", "RIGHT"), "Type": field("dword", 3),
                              "Value": field("cexostring", weapons[0] if weapons else "")},
                             {"__struct_id": 0, "Name": field("cexostring", "LEFT"), "Type": field("dword", 3),
                              "Value": field("cexostring", weapons[1] if len(weapons) > 1 else "")}])})
        feats = creature.setdefault("FeatList", field("list", []))["value"]
        existing = {f["Feat"]["value"] for f in feats}
        for feat in (2, 3, 4, 32, 44, 45, 46):  # armour, shield and exotic/martial/simple weapon proficiencies
            if feat not in existing:
                feats.append({"__struct_id": 1, "Feat": field("word", feat)})
        creatures.append(creature)
    for index in range(len(fixture["actors"])):
        dummy = copy.deepcopy(template)
        dummy.pop("__data_type", None)
        dummy["__struct_id"] = 4
        for key in list(dummy):
            if key.startswith("Script"):
                dummy[key] = field("resref", "")
        dummy.update({"FirstName": field("cexolocstring", {"0": "Training dummy"}), "LastName": field("cexolocstring", {}),
                      "Tag": field("cexostring", f"sr_rt_d{index}"), "TemplateResRef": field("resref", "sr_rt_dummy"),
                      "FactionID": field("word", 1), "Plot": field("byte", 1), "Equip_ItemList": field("list", []),
                      "ItemList": field("list", []), "XPosition": field("float", 7.3 + index * 3.5),
                      "YPosition": field("float", 14.0), "ZPosition": field("float", 0.0),
                      "XOrientation": field("float", -1.0), "YOrientation": field("float", 0.0)})
        creatures.append(dummy)
    tiles = [{"__struct_id": 1, "Tile_ID": field("int", 120), "Tile_Height": field("int", 0),
              "Tile_Orientation": field("int", 0), **{k: field("byte", v) for k, v in
              {"Tile_AnimLoop1": 1, "Tile_AnimLoop2": 1, "Tile_AnimLoop3": 1, "Tile_MainLight1": 0,
               "Tile_MainLight2": 0, "Tile_SrcLight1": 0, "Tile_SrcLight2": 0}.items()}} for _ in range(64)]
    area = fixture["area"]
    entry = fixture.get("entry", [18.0, 20.0])  # player start; faces the actor row (-Y)
    are = structure("ARE ", Tileset=field("resref", "sr_rt"), Width=field("int", 8), Height=field("int", 8),
                    Name=field("cexolocstring", {"0": "Robe trial floor"}), Tag=field("cexostring", area),
                    ResRef=field("resref", area), Tile_List=field("list", tiles), Version=field("dword", 2),
                    Flags=field("dword", 4), DayNightCycle=field("byte", 0), IsNight=field("byte", 0),
                    SunAmbientColor=field("dword", 11579568), SunDiffuseColor=field("dword", 15658734),
                    MoonAmbientColor=field("dword", 11579568), MoonDiffuseColor=field("dword", 15658734),
                    FogClipDist=field("float", 80), SunShadows=field("byte", 1), ShadowOpacity=field("byte", 20),
                    SkyBox=field("byte", 0))
    git = structure("GIT ", **{"Creature List": field("list", creatures), "Door List": field("list", []),
                    "Placeable List": field("list", []), "TriggerList": field("list", []),
                    "WaypointList": field("list", []), "StoreList": field("list", [])})
    ifo = structure("IFO ", Mod_Name=field("cexolocstring", {"0": fixture["title"]}),
                    Mod_Description=field("cexolocstring", {"0": "Meshy robe trial comparison fixture."}),
                    Mod_Tag=field("cexostring", fixture["module"].upper()), Mod_Version=field("dword", 3),
                    Mod_MinGameVer=field("cexostring", "1.69"), Mod_IsSaveGame=field("byte", 0),
                    Mod_Entry_Area=field("resref", area), Mod_Entry_X=field("float", entry[0]),
                    Mod_Entry_Y=field("float", entry[1]), Mod_Entry_Z=field("float", 0.0),
                    Mod_Entry_Dir_X=field("float", 0.0), Mod_Entry_Dir_Y=field("float", -1.0),
                    Mod_Area_list=field("list", [{"__struct_id": 6, "Area_Name": field("resref", area)}]),
                    Mod_HakList=field("list", [{"__struct_id": 8, "Mod_Hak": field("cexostring", fixture["hak"])}]),
                    Mod_CustomTlk=field("cexostring", ""), Mod_OnClientEntr=field("resref", "sr_rt_enter"),
                    Mod_OnPlrEqItm=field("resref", "sr_rt_equip"), Mod_OnPlrUnEqItm=field("resref", "sr_rt_unequip"),
                    Mod_StartYear=field("dword", 1372), Mod_StartMonth=field("byte", 1), Mod_StartDay=field("byte", 1),
                    Mod_StartHour=field("byte", 12), Mod_DawnHour=field("byte", 6), Mod_DuskHour=field("byte", 18),
                    Mod_MinPerHour=field("byte", 2), Mod_XPScale=field("byte", 10))
    factions = [{"__struct_id": i, "FactionName": field("cexostring", name), "FactionGlobal": field("word", 1),
                 "FactionParentID": field("dword", 4294967295)}
                for i, name in enumerate(("PC", "Hostile", "Commoner", "Merchant", "Defender"))]
    reps = [{"__struct_id": i * 5 + j, "FactionID1": field("dword", i), "FactionID2": field("dword", j),
             "FactionRep": field("dword", 0 if {i, j} == {1, 2} else 50)} for i in range(5) for j in range(5) if i != j]
    fac = structure("FAC ", FactionList=field("list", factions), RepList=field("list", reps))
    for filename, document in (("module.ifo", ifo), (area + ".are", are), (area + ".git", git), ("repute.fac", fac)):
        path = json_dir / (filename + ".json")
        path.write_text(json.dumps(document), encoding="utf-8")
        tool("nwn_gff", ["-i", path, "-o", binary / filename])
    for name, text in scripts(fixture["actors"], rows).items():
        path = binary / (name + ".nss")
        path.write_text(text, encoding="ascii")
        tool("nwn_script_comp", [*common, path])
        require(path.with_suffix(".ncs").exists(), "Script compiler produced no output: " + name)
    module = userdir / "modules" / (fixture["module"] + ".mod")
    if module.exists():
        module.unlink()
    tool("nwn_erf", ["-c", "-f", module, "-e", "MOD", binary])
    verify_pins(inputs)
    receipt = {"schemaVersion": 1, "kind": "srn-robe-fixture-build", "createdUtc": utc(), "inputs": inputs,
               "hak": pin(hak), "module": pin(module), "userDirectory": str(userdir),
               "hakResources": {p.name: sha(p) for p in sorted(resources.iterdir())},
               "items": {p.name: sha(p) for p in sorted(binary.glob("*.uti"))},
               "partsRobeRows": {row: table[int(row)] for row in fixture["rows"]},
               "actors": [{"tag": f"sr_rt_a{i}", **a} for i, a in enumerate(fixture["actors"])],
               "motion": [family for family, _ in MOTION], "engineObserved": False, **FLAGS}
    print(json.dumps(write_fresh(staging / "fixture.json", receipt)))


if __name__ == "__main__":
    main()
