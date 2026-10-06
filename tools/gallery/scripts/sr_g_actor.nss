void GGRecordOutfit(){
  object worn=GetItemInSlot(INVENTORY_SLOT_CHEST,OBJECT_SELF);
  WriteTimestampedLogEntry("GG_PILOT_SPAWN tag="+GetTag(OBJECT_SELF)+" head="+IntToString(GetCreatureBodyPart(CREATURE_PART_HEAD))+" outfit="+GetResRef(worn));
}
void main(){
  int i;for(i=0;i<18;i++)SetCreatureBodyPart(i,1);
  SetCreatureBodyPart(CREATURE_PART_BELT,0);SetCreatureBodyPart(CREATURE_PART_RIGHT_SHOULDER,0);SetCreatureBodyPart(CREATURE_PART_LEFT_SHOULDER,0);
  SetCreatureBodyPart(CREATURE_PART_HEAD,GetLocalInt(OBJECT_SELF,"HEAD_SLOT"));
  SetColor(OBJECT_SELF,COLOR_CHANNEL_SKIN,GetLocalInt(OBJECT_SELF,"SKIN_ROW"));SetColor(OBJECT_SELF,COLOR_CHANNEL_HAIR,GetLocalInt(OBJECT_SELF,"HAIR_ROW"));
  float scale=GetLocalFloat(OBJECT_SELF,"BODY_VISUAL_SCALE");if(scale>0.0)SetObjectVisualTransform(OBJECT_SELF,OBJECT_VISUAL_TRANSFORM_SCALE,scale);
  SetIsDestroyable(FALSE,TRUE,TRUE);
  string outfit=GetLocalString(OBJECT_SELF,"GG_EQUIPMENT");
  if(outfit!=""){
    object item=CreateItemOnObject(outfit,OBJECT_SELF);
    if(GetIsObjectValid(item))ActionEquipItem(item,INVENTORY_SLOT_CHEST);
    else WriteTimestampedLogEntry("GG_PILOT_OUTFIT_FAILED tag="+GetTag(OBJECT_SELF)+" item="+outfit);
  }
  DelayCommand(1.0,GGRecordOutfit());
}
