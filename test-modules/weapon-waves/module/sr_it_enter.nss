void ReportEquip(object actor) {
  if(!GetIsObjectValid(actor)) return;
  object item=GetItemInSlot(INVENTORY_SLOT_RIGHTHAND,actor);
  WriteTimestampedLogEntry("ITEMKIT_EQUIPPED actor="+GetTag(actor)+" valid="+IntToString(GetIsObjectValid(item))+" right="+GetResRef(item));
  if(GetIsPC(actor)) SendMessageToPC(actor,"Equipped: "+GetName(item)+" ["+GetResRef(item)+"]. Both Human reviewers are directly ahead.");
}
void GiveBlade(object actor) {
  object item=GetItemPossessedBy(actor,"sr_cl36_1");
  if(!GetIsObjectValid(item)) item=CreateItemOnObject("sr_cl36_1",actor);
  if(!GetIsObjectValid(item)) { WriteTimestampedLogEntry("ITEMKIT_ITEM_FAILED actor="+GetTag(actor)); return; }
  AssignCommand(actor,ActionEquipItem(item,INVENTORY_SLOT_RIGHTHAND));
  DelayCommand(1.0,ReportEquip(actor));
}
void StartReview(object pc,int retries) {
  if(!GetIsObjectValid(pc) || !GetIsPC(pc)) return;
  object male=GetObjectByTag("sr_it_male"); object female=GetObjectByTag("sr_it_female");
  object area=GetArea(pc);
  if(!GetIsObjectValid(area) || !GetIsObjectValid(male) || !GetIsObjectValid(female) || GetArea(male)!=area || GetArea(female)!=area) {
    if(retries>0) DelayCommand(0.5,StartReview(pc,retries-1));
    else { WriteTimestampedLogEntry("ITEMKIT_READY_FAILED area="+GetTag(area)+" male="+IntToString(GetIsObjectValid(male))+" female="+IntToString(GetIsObjectValid(female)));
      SendMessageToPC(pc,"Review fixture could not find both placed Human actors; inspect the client log."); }
    return;
  }
  GiveBlade(pc); GiveBlade(male); GiveBlade(female);
  if(!GetIsObjectValid(GetItemPossessedBy(pc,"sr_cl36_2"))) CreateItemOnObject("sr_cl36_2",pc);
  if(!GetIsObjectValid(GetItemPossessedBy(pc,"sr_cougar"))) CreateItemOnObject("sr_cougar",pc);
  if(!GetIsObjectValid(GetItemPossessedBy(pc,"sr_cfk"))) CreateItemOnObject("sr_cfk",pc);
  if(!GetIsObjectValid(GetItemPossessedBy(pc,"sr_cfs"))) CreateItemOnObject("sr_cfs",pc);
  WriteTimestampedLogEntry("ITEMKIT_READY area="+GetTag(area)+" male="+GetTag(male)+" female="+GetTag(female));
}
void main() {
  object pc=GetEnteringObject(); if(!GetIsPC(pc)) return;
  
  DelayCommand(0.5,StartReview(pc,20));
}