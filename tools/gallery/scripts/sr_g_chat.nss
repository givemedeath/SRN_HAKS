#include "sr_g_api"
void main(){
  object pc=GetPCChatSpeaker();string message=GetPCChatMessage();if(message!=".gallery" && GetStringLeft(message,9)!=".gallery ")return;
  SetPCChatMessage("");if(GetStringLength(message)<=9){GGHelp(pc);return;}
  string rest=GetStringRight(message,GetStringLength(message)-9);int space=FindSubString(rest," ");
  string command=rest;string argument="";if(space>=0){command=GetStringLeft(rest,space);argument=GetStringRight(rest,GetStringLength(rest)-space-1);}
  GGAction(pc,GetStringLowerCase(command),GetStringLowerCase(argument));
}
