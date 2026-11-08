void Camera(object p){
  object a=GetObjectByTag("sr_it_male"); if(!GetIsObjectValid(a)) return;
  SetCameraMode(p,CAMERA_MODE_TOP_DOWN); SetCameraHeight(p,1.1); AttachCamera(p,a,FALSE); SetCameraFacing(90.0,7.0,25.0);
}
void main(){ object p=GetEnteringObject(); if(!GetIsPC(p)) p=GetFirstPC(); if(!GetIsObjectValid(p)) return;
  DelayCommand(3.0,Camera(p)); SendMessageToPC(p,"Private Cougar fixture: both actors cycle equip, walk/run, attacks, shield/offhand and armor/gloves. Visual review remains required."); }