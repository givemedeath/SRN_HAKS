#include "sr_f7_inc"
void Report(object o) {
 object r=GetItemInSlot(INVENTORY_SLOT_RIGHTHAND,o);object l=GetItemInSlot(INVENTORY_SLOT_LEFTHAND,o);object a=GetItemInSlot(INVENTORY_SLOT_ARROWS,o);
 WriteTimestampedLogEntry("SW2_FIXED_EQUIP tag="+GetTag(o)+" gender="+IntToString(GetGender(o))+" torso="+IntToString(GetCreatureBodyPart(CREATURE_PART_TORSO,o))+" head="+IntToString(GetCreatureBodyPart(CREATURE_PART_HEAD,o))+" exotic="+IntToString(GetHasFeat(FEAT_WEAPON_PROFICIENCY_EXOTIC,o))+" right="+GetResRef(r)+" base="+IntToString(GetBaseItemType(r))+" left="+GetResRef(l)+" arrows="+IntToString(GetItemStackSize(a))+" heldStack="+IntToString(GetItemStackSize(r)));
}
void RestoreFirearm(object actor) {
 AssignCommand(actor,ClearAllActions(TRUE));
 AssignCommand(actor,ActionEquipItem(GetLocalObject(actor,"SR_F7_ORIGINAL"),INVENTORY_SLOT_RIGHTHAND));
 DelayCommand(0.5,SyncFirearm(actor));
 location home=GetLocalLocation(actor,"SW2_START");vector walk=GetPositionFromLocation(home);walk.y-=3.0;
 DelayCommand(1.0,AssignCommand(actor,ActionMoveToLocation(Location(GetArea(actor),walk,270.0),TRUE)));
 DelayCommand(1.1,AssignCommand(actor,ActionMoveToLocation(home,TRUE)));
}
void SwapToThrow(object actor) {
 SetLocalObject(actor,"SR_F7_ORIGINAL",GetItemInSlot(INVENTORY_SLOT_RIGHTHAND,actor));
 object knife=CreateItemOnObject("sr2273b8c",actor,20);
 AssignCommand(actor,ActionEquipItem(knife,INVENTORY_SLOT_RIGHTHAND));
 DelayCommand(0.5,SyncFirearm(actor));
 DelayCommand(1.0,AssignCommand(actor,ActionPlayAnimation(ANIMATION_LOOPING_PAUSE,1.0,3.0)));
 DelayCommand(5.0,RestoreFirearm(actor));
 if(GetGender(actor)==GENDER_MALE)DelayCommand(7.0,DoSinglePlayerAutoSave());
}
void Finish(object actor) {
 AssignCommand(actor,ClearAllActions(TRUE));object held=GetItemInSlot(INVENTORY_SLOT_RIGHTHAND,actor);object ammo=GetItemInSlot(INVENTORY_SLOT_ARROWS,actor);int base=GetBaseItemType(held);int after=GetItemStackSize(held);if(base==61)ammo=GetItemInSlot(INVENTORY_SLOT_BULLETS,actor);if(base==6)ammo=GetItemInSlot(INVENTORY_SLOT_BOLTS,actor);if(base==8||base==61||base==6)after=GetItemStackSize(ammo);
 WriteTimestampedLogEntry("SW2_ATTACK_RESULT tag="+GetTag(actor)+" weapon="+GetResRef(held)+" base="+IntToString(base)+" before="+IntToString(GetLocalInt(actor,"SW2_AMMO_BEFORE"))+" after="+IntToString(after)+" attackEvents="+IntToString(GetLocalInt(actor,"SW2_ATTACK_EVENTS"))+" lastWeapon="+GetResRef(GetLastWeaponUsed(actor)));
 if(base==61 && !GetLocalInt(actor,"SR_F7_SWAP_TEST")){SetLocalInt(actor,"SR_F7_SWAP_TEST",1);DelayCommand(2.0,SwapToThrow(actor));}SetLocalInt(actor,"SW2_TEST_ACTIVE",0);DestroyObject(GetLocalObject(actor,"SW2_TEST_TARGET"));AssignCommand(actor,JumpToLocation(GetLocalLocation(actor,"SW2_START")));
}
void Attack(object actor) {
 SyncFirearm(actor);
 SetLocalLocation(actor,"SW2_START",GetLocation(actor));object area=GetArea(actor);vector p=GetPosition(actor);int carrier=GetBaseItemType(GetItemInSlot(INVENTORY_SLOT_RIGHTHAND,actor));if(carrier==61||carrier==6||carrier==8||carrier==63)p.y-=6.0;else p.x+=2.0;object target=CreateObject(OBJECT_TYPE_CREATURE,"sw2_target",Location(area,p,180.0));ChangeToStandardFaction(target,STANDARD_FACTION_HOSTILE);SetPlotFlag(target,TRUE);SetImmortal(target,TRUE);SetLocalObject(actor,"SW2_TEST_TARGET",target);SetIsTemporaryEnemy(target,actor);SetIsTemporaryEnemy(actor,target);AssignCommand(actor,ClearAllActions(TRUE));object held=GetItemInSlot(INVENTORY_SLOT_RIGHTHAND,actor);int before=GetItemStackSize(held);if(GetBaseItemType(held)==8)before=GetItemStackSize(GetItemInSlot(INVENTORY_SLOT_ARROWS,actor));if(GetBaseItemType(held)==61)before=GetItemStackSize(GetItemInSlot(INVENTORY_SLOT_BULLETS,actor));if(GetBaseItemType(held)==6)before=GetItemStackSize(GetItemInSlot(INVENTORY_SLOT_BOLTS,actor));SetLocalInt(actor,"SW2_AMMO_BEFORE",before);SetLocalInt(actor,"SW2_ATTACK_EVENTS",0);SetLocalInt(actor,"SW2_TEST_ACTIVE",1);AssignCommand(actor,ActionAttack(target));DelayCommand(60.0,Finish(actor));
}
void ShieldRun(object actor) {
 object target=GetLocalObject(actor,"SW2_TEST_TARGET");DestroyObject(target);
 AssignCommand(actor,ClearAllActions(TRUE));location home=GetLocalLocation(actor,"SW2_START");
 vector p=GetPositionFromLocation(home);p.y-=4.0;
 AssignCommand(actor,ActionMoveToLocation(Location(GetArea(actor),p,270.0),TRUE));
 AssignCommand(actor,ActionMoveToLocation(home,TRUE));
}
void ShieldProbe(object actor) {
 SetLocalLocation(actor,"SW2_START",GetLocation(actor));SetLocalInt(actor,"SW2_TEST_ACTIVE",1);
 SetPlotFlag(actor,TRUE);vector p=GetPosition(actor);p.y-=1.5;
 object target=CreateObject(OBJECT_TYPE_CREATURE,"sw2_target",Location(GetArea(actor),p,90.0));
 SetLocalObject(actor,"SW2_TEST_TARGET",target);SetPlotFlag(target,TRUE);SetImmortal(target,TRUE);
 ChangeToStandardFaction(target,STANDARD_FACTION_HOSTILE);SetIsTemporaryEnemy(target,actor);SetIsTemporaryEnemy(actor,target);
 AssignCommand(target,SetCommandable(TRUE));AssignCommand(actor,SetCommandable(TRUE));
 AssignCommand(target,ActionAttack(actor));AssignCommand(actor,ActionAttack(target));DelayCommand(20.0,ShieldRun(actor));
 DelayCommand(35.0,ShieldRun(actor));DelayCommand(60.0,Finish(actor));
 WriteTimestampedLogEntry("SW2_SHIELD_PROBE tag="+GetTag(actor)+" defense_then_run");
}
void Arrange(object male,object female,object pc,int pair) {
 object m=GetModule();object area=GetArea(male);
 WriteTimestampedLogEntry("SW_STAGE_AREA pc="+GetTag(pc)+" pcArea="+GetTag(GetArea(pc))+" actorArea="+GetTag(area));
 AssignCommand(male,ClearAllActions(TRUE));AssignCommand(female,ClearAllActions(TRUE));
 if(GetLocalInt(m,"SW_PAIR")!=pair+1) {
  object old=GetLocalObject(m,"SW_MALE");if(GetIsObjectValid(old))AssignCommand(old,JumpToLocation(GetLocalLocation(old,"SW_HOME")));
  old=GetLocalObject(m,"SW_FEMALE");if(GetIsObjectValid(old))AssignCommand(old,JumpToLocation(GetLocalLocation(old,"SW_HOME")));
  if(!GetLocalInt(male,"SW_HOME_SET")){SetLocalLocation(male,"SW_HOME",GetLocation(male));SetLocalInt(male,"SW_HOME_SET",1);}
  if(!GetLocalInt(female,"SW_HOME_SET")){SetLocalLocation(female,"SW_HOME",GetLocation(female));SetLocalInt(female,"SW_HOME_SET",1);}
  AssignCommand(male,JumpToLocation(Location(area,Vector(10.8,39.0,0.0),270.0)));
  AssignCommand(female,JumpToLocation(Location(area,Vector(13.2,39.0,0.0),270.0)));
  SetLocalObject(m,"SW_MALE",male);SetLocalObject(m,"SW_FEMALE",female);SetLocalInt(m,"SW_PAIR",pair+1);
 }
 AssignCommand(pc,ClearAllActions(TRUE));AssignCommand(pc,JumpToLocation(Location(area,Vector(12.0,37.0,0.0),90.0)));
 AssignCommand(pc,SetCameraFacing(90.0,5.5,65.0));
}
void main() {
 object m=GetModule();object pc=GetFirstPC();object area=GetArea(pc);int stage=GetLocalInt(m,"SW2_FIXED_STAGE");SetTime(12,0,0,0);SetPlotFlag(pc,TRUE);
 if(!GetIsObjectValid(area)){DelayCommand(1.0,ExecuteScript("c",m));return;}
 if(stage==0) {
  int count=0;object o=GetFirstObjectInArea(area,OBJECT_TYPE_CREATURE);
  while(GetIsObjectValid(o)){string t=GetTag(o);if(GetStringLeft(t,4)=="sw1_"||GetStringLeft(t,4)=="sw2_"||GetStringLeft(t,4)=="sw3_"||GetStringLeft(t,4)=="sw4_"){Report(o);count++;}o=GetNextObjectInArea(area,OBJECT_TYPE_CREATURE);}
  WriteTimestampedLogEntry("SW2_FIXED_START reviewers="+IntToString(count)+" thrown="+IntToString(GetItemStackSize(GetItemPossessedBy(pc,"sr2273b8c")))+" arrows="+IntToString(GetItemStackSize(GetItemPossessedBy(pc,"sw2_arrow"))));stage=11;
 }
 if(stage>=1&&stage<=34) {
  int pair=(stage-1)%17;int index=pair%5;float y=17.0;string prefix="sw1_";if(pair>=5){y=29.0;prefix="sw2_";}if(pair>=10){y=7.0;prefix="sw3_";}if(pair>=15){y=7.0;prefix="sw4_";}
  object male=GetObjectByTag(prefix+"m"+IntToString(index));object female=GetObjectByTag(prefix+"f"+IntToString(index));Arrange(male,female,pc,pair);Report(male);Report(female);
  if(stage>17 && pair==4){DelayCommand(0.5,ShieldProbe(male));DelayCommand(0.5,ShieldProbe(female));}
  if(stage>17) {
 if(pair==3){}

   DelayCommand(15.0,AssignCommand(pc,SetCameraFacing(45.0,7.0,65.0)));
   DelayCommand(35.0,AssignCommand(pc,SetCameraFacing(135.0,7.0,65.0)));
   DelayCommand(61.0,AssignCommand(pc,SetCameraFacing(90.0,5.5,65.0)));
  }
  if(stage<=17){SendMessageToPC(pc,"Static inspection "+IntToString(pair+1)+"/17");WriteTimestampedLogEntry("SW2_FIXED_VIEW pair="+IntToString(pair+1));}
  else if(pair!=4) {DelayCommand(0.5,Attack(male));DelayCommand(0.5,Attack(female));SendMessageToPC(pc,"Actual engine attack test "+IntToString(pair+1)+"/17;60second bounded visual action.");}
 }
 if(stage>34){SendMessageToPC(pc,"Inspection sequence complete. Client visual and attack outcomes remain individually recorded.");}
 SetLocalInt(m,"SW2_FIXED_STAGE",stage+1);
}
