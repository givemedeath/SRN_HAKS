#include "sr_f7_inc"
void main(){object a=GetPCItemLastUnequippedBy();DelayCommand(0.1,SyncFirearm(a));}