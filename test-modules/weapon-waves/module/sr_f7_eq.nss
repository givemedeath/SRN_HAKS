#include "sr_f7_inc"
void main(){object a=GetPCItemLastEquippedBy();DelayCommand(0.1,SyncFirearm(a));}