#include "sr_g_api"
void main(){
  object pc=GetEnteringObject();if(!GetIsPC(pc))return;GGHelp(pc);
  object module=GetModule();
  if(!GetLocalInt(module,"GG_STARTED")){
    SetLocalInt(module,"GG_STARTED",1);GGPage(pc,GetLocalString(module,"gg_start_category"),0);
    int i;int count=GetLocalInt(module,"gg_prestaged_count");
    for(i=0;i<count;i++)GGFind(pc,GetLocalString(module,"gg_prestaged"+IntToString(i)),TRUE);
  }
}
