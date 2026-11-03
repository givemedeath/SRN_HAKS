object Gear(string key,string res){ object x=GetLocalObject(OBJECT_SELF,key);
  if(!GetIsObjectValid(x)){ x=CreateItemOnObject(res,OBJECT_SELF); SetLocalObject(OBJECT_SELF,key,x); } return x; }
void Observe(int n){ WriteTimestampedLogEntry("ITEMKIT_OBSERVED actor="+GetTag(OBJECT_SELF)+" step="+IntToString(n)+" action="+IntToString(GetCurrentAction())+" right="+GetResRef(GetItemInSlot(INVENTORY_SLOT_RIGHTHAND))+" left="+GetResRef(GetItemInSlot(INVENTORY_SLOT_LEFTHAND))+" armor="+GetResRef(GetItemInSlot(INVENTORY_SLOT_CHEST))+" gloves="+GetResRef(GetItemInSlot(INVENTORY_SLOT_ARMS))); }
void main(){
  int n=GetLocalInt(OBJECT_SELF,"STEP"); SetLocalInt(OBJECT_SELF,"STEP",n+1);
  object blade=GetItemPossessedBy(OBJECT_SELF,"sr_cl36_1"); object target=GetLocalObject(OBJECT_SELF,"TARGET");
  location h=GetLocalLocation(OBJECT_SELF,"HOME"); vector v=GetPositionFromLocation(h);
  if(n==0 && GetIsObjectValid(blade)){ ClearAllActions(TRUE); ActionEquipItem(blade,INVENTORY_SLOT_RIGHTHAND); SetFacing(90.0); }
  if(n==5){ ClearAllActions(TRUE); ActionUnequipItem(GetItemInSlot(INVENTORY_SLOT_RIGHTHAND)); }
  if(n==6){ ActionEquipItem(blade,INVENTORY_SLOT_RIGHTHAND); }
  if(n==7){ ClearAllActions(TRUE); v.y+=4.0; ActionMoveToLocation(Location(GetArea(OBJECT_SELF),v,90.0),FALSE); ActionMoveToLocation(h,FALSE); }
  if(n==9){ ClearAllActions(TRUE); v.y+=6.0; ActionMoveToLocation(Location(GetArea(OBJECT_SELF),v,90.0),TRUE); ActionMoveToLocation(h,TRUE); }
  if(n==11){ ClearAllActions(TRUE); ActionAttack(target); }
  if(n==15){ ClearAllActions(TRUE); ActionMoveToLocation(h,FALSE); ActionEquipItem(Gear("SHIELD","nw_ashlw001"),INVENTORY_SLOT_LEFTHAND); ActionAttack(target); }
  if(n==19){ ClearAllActions(TRUE); ActionUnequipItem(GetItemInSlot(INVENTORY_SLOT_LEFTHAND)); ActionEquipItem(Gear("OFFHAND","nw_wswss001"),INVENTORY_SLOT_LEFTHAND); ActionAttack(target); }
  if(n==23){ ClearAllActions(TRUE); ActionUnequipItem(GetItemInSlot(INVENTORY_SLOT_LEFTHAND)); ActionEquipItem(Gear("ARMOR","nw_aarcl001"),INVENTORY_SLOT_CHEST); ActionEquipItem(Gear("GLOVES","nw_it_mglove001"),INVENTORY_SLOT_ARMS); ActionAttack(target); }
  if(n==27){ ClearAllActions(TRUE); ActionUnequipItem(GetItemInSlot(INVENTORY_SLOT_CHEST)); ActionUnequipItem(GetItemInSlot(INVENTORY_SLOT_ARMS)); ActionMoveToLocation(h,FALSE); }
  if(n==28) WriteTimestampedLogEntry("ITEMKIT_SEQUENCE_COMPLETE actor="+GetTag(OBJECT_SELF));
  if(n>=39) SetLocalInt(OBJECT_SELF,"STEP",0);
  DelayCommand(1.0,Observe(n));
}