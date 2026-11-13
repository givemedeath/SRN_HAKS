#include "sw_pairs"
void main(){
object m=GetModule();int current=GetLocalInt(m,"SW_PAIR");int pairs=SwPairCount();
if(GetLocalInt(GetLocalObject(m,"SW_MALE"),"SW2_TEST_ACTIVE"))return;
int stage=current+pairs;
if(OBJECT_SELF==GetLocalObject(m,"SW_MALE"))stage=current%pairs+1;
else if(OBJECT_SELF!=GetLocalObject(m,"SW_FEMALE")) {
 string tag=GetTag(OBJECT_SELF);stage=StringToInt(GetStringRight(tag,1))+1+SwGroupStart(GetStringLeft(tag,4));
}
SetLocalInt(m,"SW2_FIXED_STAGE",stage);ExecuteScript("c",m);
SendMessageToPC(GetFirstPC(),"Click MALE for next weapon; FEMALE for this pair's 60-second visual action. Shield is visual-only here.");
}
