#include "sr_g_api"
void main(){
  object pc=GetLastUsedBy();string command=GetLocalString(OBJECT_SELF,"GG_ACTION");
  if(command=="select")GGSelect(pc,GetLocalString(OBJECT_SELF,"GG_CATEGORY"),GetLocalInt(OBJECT_SELF,"GG_INDEX"));
  else GGAction(pc,command,GetLocalString(OBJECT_SELF,"GG_ARGUMENT"));
}
