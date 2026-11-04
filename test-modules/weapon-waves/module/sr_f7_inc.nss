void SyncFirearm(object actor) {
 string item=GetResRef(GetItemInSlot(INVENTORY_SLOT_RIGHTHAND,actor));
 int human=GetAppearanceType(actor)==15100;
 int enabled=(item=="sre9a211be_3"||item=="sr_cl36_1"||item=="sr_cl36_2") && human;
 int previous=GetLocalInt(actor,"SR_F7_MAPPED");
 string fire="";string ready="";if(enabled){fire="srf7fire";ready="srf7ready";}
 ReplaceObjectAnimation(actor,"throwr",fire);ReplaceObjectAnimation(actor,"1hreadyr",ready);
 SetLocalInt(actor,"SR_F7_MAPPED",enabled);
 if(enabled!=previous)WriteTimestampedLogEntry("SR_F7_MAPPING tag="+GetTag(actor)+" enabled="+IntToString(enabled));
 fire="";ready="";
 if(human && (item=="sra84e4660_5"||item=="sra84e4660gl")){fire="srakfire";ready="srakready";}
 if(human && item=="sr6abe18c_6"){fire="srcbfire";ready="srcbready";}
 ReplaceObjectAnimation(actor,"xbowshot",fire);ReplaceObjectAnimation(actor,"xbowrdy",ready);
 ReplaceObjectAnimation(actor,"bowshot","");
}