#include "sr_f7_inc"
void Equip(string tag,string name,int slot,int bow) {
 object actor=GetObjectByTag(tag);if(!GetIsObjectValid(actor)||GetLocalInt(actor,"SW2_EQUIPPED"))return;
 if(bow) {object ammo=CreateItemOnObject("sw2_arrow",actor,99);AssignCommand(actor,ActionEquipItem(ammo,INVENTORY_SLOT_ARROWS));}
 int count=1;if(name=="sr2273b8c")count=20;if(name=="sre9a211be_3"||name=="sr_cl36_1"||name=="sr_cl36_2"||name=="sr3ab64906_5") {object bullets=CreateItemOnObject("nw_wambu001",actor,99);AssignCommand(actor,ActionEquipItem(bullets,INVENTORY_SLOT_BULLETS));}
 if(name=="sra84e4660_5"||name=="sr6abe18c_6") {object bolts=CreateItemOnObject("nw_wambo001",actor,99);AssignCommand(actor,ActionEquipItem(bolts,INVENTORY_SLOT_BOLTS));}
 object item=CreateItemOnObject(name,actor,count);AssignCommand(actor,ActionEquipItem(item,slot));SetLocalInt(actor,"SW2_EQUIPPED",1);DelayCommand(0.5,SyncFirearm(actor));
}
void ReviewBody(object pc) {
 SetCreatureAppearanceType(pc,15100);SetPhenoType(0,pc);
 int part;for(part=0;part<18;part++)SetCreatureBodyPart(part,1,pc);
 SetCreatureBodyPart(CREATURE_PART_BELT,0,pc);
 SetCreatureBodyPart(CREATURE_PART_RIGHT_SHOULDER,0,pc);
 SetCreatureBodyPart(CREATURE_PART_LEFT_SHOULDER,0,pc);
}
void main(){object pc=GetEnteringObject();if(!GetIsPC(pc))return;
 if(!GetLocalInt(pc,"SW_REVIEW_BODY")) {
  int slot;for(slot=0;slot<4;slot++) {
   object clothing=GetItemInSlot(slot,pc);if(GetIsObjectValid(clothing))AssignCommand(pc,ActionUnequipItem(clothing));
  }
  object cloak=GetItemInSlot(INVENTORY_SLOT_CLOAK,pc);if(GetIsObjectValid(cloak))AssignCommand(pc,ActionUnequipItem(cloak));
  DelayCommand(0.5,ReviewBody(pc));SetLocalInt(pc,"SW_REVIEW_BODY",1);
 }

 if(!GetLocalInt(pc,"SW2_ITEMS")) {ApplyEffectToObject(DURATION_TYPE_PERMANENT,EffectAbilityIncrease(ABILITY_STRENGTH,50),pc);
CreateItemOnObject("sr6abe18c_6",pc);
CreateItemOnObject("sr800e341u",pc);
CreateItemOnObject("sr_cfk",pc);
CreateItemOnObject("sr_cfs",pc);
CreateItemOnObject("sr_cl36_1",pc);
CreateItemOnObject("sr_cl36_2",pc);
CreateItemOnObject("sr_cougar",pc);
CreateItemOnObject("sr_stbaton",pc);
CreateItemOnObject("sra84e4660_5",pc);
CreateItemOnObject("sra84e4660gl",pc);
CreateItemOnObject("sre9a211be_3",pc);
CreateItemOnObject("srf7ac8ec",pc);
CreateItemOnObject("srdc4c1668",pc);
CreateItemOnObject("sr2273b8c",pc,20);
CreateItemOnObject("srdd7dc09",pc);
CreateItemOnObject("sreab35fc",pc);
CreateItemOnObject("sw2_arrow",pc,99);
CreateItemOnObject("sr421b34c6",pc);
CreateItemOnObject("sr3ab64906_5",pc);
CreateItemOnObject("srd6342080",pc);
CreateItemOnObject("srd1aaa8cd",pc);
CreateItemOnObject("sre99544ae",pc);
CreateItemOnObject("sr1d8f6e60",pc);
CreateItemOnObject("sr05afd23e",pc);
CreateItemOnObject("sr_cl36_1",pc);SetLocalInt(pc,"SW2_ITEMS",1);}
Equip("sw1_m0","sre9a211be_3",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw1_f0","sre9a211be_3",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw1_m1","sr_stbaton",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw1_f1","sr_stbaton",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw1_m2","sra84e4660_5",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw1_f2","sra84e4660_5",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw1_m3","sr6abe18c_6",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw1_f3","sr6abe18c_6",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw1_m4","sr800e341u",INVENTORY_SLOT_LEFTHAND,0);
Equip("sw1_f4","sr800e341u",INVENTORY_SLOT_LEFTHAND,0);
Equip("sw2_m0","srf7ac8ec",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw2_f0","srf7ac8ec",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw2_m1","srdc4c1668",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw2_f1","srdc4c1668",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw2_m2","sr2273b8c",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw2_f2","sr2273b8c",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw2_m3","srdd7dc09",INVENTORY_SLOT_RIGHTHAND,1);
Equip("sw2_f3","srdd7dc09",INVENTORY_SLOT_RIGHTHAND,1);
Equip("sw2_m4","sreab35fc",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw2_f4","sreab35fc",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw3_m0","sr_cfk",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw3_f0","sr_cfk",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw3_m1","sr_cougar",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw3_f1","sr_cougar",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw3_m2","sr_cfs",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw3_f2","sr_cfs",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw3_m3","sr_cl36_1",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw3_f3","sr_cl36_1",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw3_m4","sr_cl36_2",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw3_f4","sr_cl36_2",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw4_m0","sr421b34c6",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw4_f0","sr421b34c6",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw4_m1","sr3ab64906_5",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw4_f1","sr3ab64906_5",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw5_m0","srd6342080",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw5_f0","srd6342080",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw5_m1","srd1aaa8cd",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw5_f1","srd1aaa8cd",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw5_m2","sre99544ae",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw5_f2","sre99544ae",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw5_m3","sr1d8f6e60",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw5_f3","sr1d8f6e60",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw5_m4","sr05afd23e",INVENTORY_SLOT_RIGHTHAND,0);
Equip("sw5_f4","sr05afd23e",INVENTORY_SLOT_RIGHTHAND,0);
SendMessageToPC(pc,"Twenty-two weapon/finish NPC pairs and inventory controls supplied. Cougar/Colt reviewers stand in the southern row; all pairs are in the selector. Bow arrows use native consumption only. Client/gameplay acceptance remains pending.");if(!GetLocalInt(GetModule(),"SW_REVIEW_STARTED")){SetLocalInt(GetModule(),"SW_REVIEW_STARTED",1);DelayCommand(3.0,ExecuteScript("c",GetModule()));}
}
