void main(){
  int i;for(i=0;i<18;i++)SetCreatureBodyPart(i,1);
  SetCreatureBodyPart(CREATURE_PART_BELT,0);SetCreatureBodyPart(CREATURE_PART_RIGHT_SHOULDER,0);SetCreatureBodyPart(CREATURE_PART_LEFT_SHOULDER,0);
  SetCreatureBodyPart(CREATURE_PART_HEAD,GetLocalInt(OBJECT_SELF,"HEAD_SLOT"));
  SetColor(OBJECT_SELF,COLOR_CHANNEL_SKIN,GetLocalInt(OBJECT_SELF,"SKIN_ROW"));SetColor(OBJECT_SELF,COLOR_CHANNEL_HAIR,GetLocalInt(OBJECT_SELF,"HAIR_ROW"));
  float scale=GetLocalFloat(OBJECT_SELF,"BODY_VISUAL_SCALE");if(scale>0.0)SetObjectVisualTransform(OBJECT_SELF,OBJECT_VISUAL_TRANSFORM_SCALE,scale);
  SetIsDestroyable(FALSE,TRUE,TRUE);
}
