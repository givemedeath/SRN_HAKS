void Equip(string tag,string name,int slot) {
 object actor=GetObjectByTag(tag); if(!GetIsObjectValid(actor)) return;
 if(GetLocalInt(actor,"SW1_EQUIPPED")) return;
 object item=CreateItemOnObject(name,actor); AssignCommand(actor,ActionEquipItem(item,slot));
 SetLocalInt(actor,"SW1_EQUIPPED",1);
}
void main() { object pc=GetEnteringObject(); if(!GetIsPC(pc)) return;
 if(!GetLocalInt(pc,"SW1_ITEMS")) {
  CreateItemOnObject("sre9a211be_3",pc);
  CreateItemOnObject("sr_stbaton",pc);
  CreateItemOnObject("sra84e4660_5",pc);
  CreateItemOnObject("sr6abe18c_6",pc);
  CreateItemOnObject("sr800e341u",pc);
  CreateItemOnObject("sra84e4660gl",pc);
  CreateItemOnObject("sr_cougar",pc);
  CreateItemOnObject("sr_cfk",pc);
  CreateItemOnObject("sr_cfs",pc);
  CreateItemOnObject("sr_cl36_1",pc);
  CreateItemOnObject("sr_cl36_2",pc);
  CreateItemOnObject("sr_cl36_1",pc); SetLocalInt(pc,"SW1_ITEMS",1);
 }
 Equip("sw1_m0","sre9a211be_3",INVENTORY_SLOT_RIGHTHAND);
 Equip("sw1_f0","sre9a211be_3",INVENTORY_SLOT_RIGHTHAND);
 Equip("sw1_m1","sr_stbaton",INVENTORY_SLOT_RIGHTHAND);
 Equip("sw1_f1","sr_stbaton",INVENTORY_SLOT_RIGHTHAND);
 Equip("sw1_m2","sra84e4660_5",INVENTORY_SLOT_RIGHTHAND);
 Equip("sw1_f2","sra84e4660_5",INVENTORY_SLOT_RIGHTHAND);
 Equip("sw1_m3","sr6abe18c_6",INVENTORY_SLOT_RIGHTHAND);
 Equip("sw1_f3","sr6abe18c_6",INVENTORY_SLOT_RIGHTHAND);
 Equip("sw1_m4","sr800e341u",INVENTORY_SLOT_LEFTHAND);
 Equip("sw1_f4","sr800e341u",INVENTORY_SLOT_LEFTHAND);
 SendMessageToPC(pc,"Wave1: all five candidates and all four approved weapons are in your inventory, including two base Colts and the alternate finish. Five male/female pairs stand ahead. Shield is in the left hand. Client checks remain pending.");
}
