void main(){
  int i; for(i=0;i<18;i++) SetCreatureBodyPart(i,1);
  SetCreatureBodyPart(CREATURE_PART_BELT,0); SetCreatureBodyPart(CREATURE_PART_RIGHT_SHOULDER,0); SetCreatureBodyPart(CREATURE_PART_LEFT_SHOULDER,0);
  SetCreatureBodyPart(CREATURE_PART_HEAD,1); SetColor(OBJECT_SELF,COLOR_CHANNEL_SKIN,3); SetColor(OBJECT_SELF,COLOR_CHANNEL_HAIR,5);
  SetImmortal(OBJECT_SELF,TRUE); SetLocalLocation(OBJECT_SELF,"HOME",GetLocation(OBJECT_SELF)); SetLocalInt(OBJECT_SELF,"STEP",0);
  location h=GetLocation(OBJECT_SELF); vector v=GetPosition(OBJECT_SELF); v.y+=2.2;
  object t=CreateObject(OBJECT_TYPE_CREATURE,"sr_it_target",Location(GetArea(OBJECT_SELF),v,270.0)); SetLocalObject(OBJECT_SELF,"TARGET",t);
  WriteTimestampedLogEntry("ITEMKIT_ACTOR_READY actor="+GetTag(OBJECT_SELF));
}