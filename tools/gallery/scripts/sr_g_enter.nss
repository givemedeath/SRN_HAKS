#include "sr_g_api"
void main(){
  object pc=GetEnteringObject();if(!GetIsPC(pc))return;GGHelp(pc);
  object module=GetModule();
  int pilots=GetLocalInt(module,"gg_pilot_count");int visible=0;int p;
  for(p=0;p<pilots;p++)if(GetIsObjectValid(GetObjectByTag(GetLocalString(module,"gg_pilot_"+IntToString(p)))))visible++;
  WriteTimestampedLogEntry("GG_PILOT_INSTANCES count="+IntToString(visible)+" expected="+IntToString(pilots));
  SendMessageToPC(pc,"Gallery controls: floor levers ahead of spawn. Use Male race rows or .gallery pilots for the separate eastern bay: bodies first, Clothing 1 second.");
  if(!GetLocalInt(module,"GG_STARTED")){
    SetLocalInt(module,"GG_STARTED",1);GGPage(pc,GetLocalString(module,"gg_start_category"),0);
    int i;int count=GetLocalInt(module,"gg_prestaged_count");
    for(i=0;i<count;i++)GGFind(pc,GetLocalString(module,"gg_prestaged"+IntToString(i)),TRUE);
  }
}
