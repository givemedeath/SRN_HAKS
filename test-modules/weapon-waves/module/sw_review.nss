void main(){
object m=GetModule();int current=GetLocalInt(m,"SW_PAIR");
if(GetLocalInt(GetLocalObject(m,"SW_MALE"),"SW2_TEST_ACTIVE"))return;
int stage=current+26;
if(OBJECT_SELF==GetLocalObject(m,"SW_MALE"))stage=current%26+1;
else if(OBJECT_SELF!=GetLocalObject(m,"SW_FEMALE")) {
 string tag=GetTag(OBJECT_SELF);stage=StringToInt(GetStringRight(tag,1))+1;
 if(GetStringLeft(tag,4)=="sw2_")stage+=5;
 if(GetStringLeft(tag,4)=="sw3_")stage+=10;
 if(GetStringLeft(tag,4)=="sw4_")stage+=15;
 if(GetStringLeft(tag,4)=="sw5_")stage+=17;
 if(GetStringLeft(tag,4)=="sw6_")stage+=22;
}
SetLocalInt(m,"SW2_FIXED_STAGE",stage);ExecuteScript("c",m);
SendMessageToPC(GetFirstPC(),"Click MALE for next weapon; FEMALE for this pair's 60-second visual action. Shield is visual-only here.");
}