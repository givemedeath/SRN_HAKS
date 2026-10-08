void HumanCameraItemObserve(string phase, object actor, string slotName, int slot) {
  object item=GetItemInSlot(slot,actor); int valid=GetIsObjectValid(item);
  string itemTag=""; string itemResRef=""; int baseItem=-1;
  if(valid) { itemTag=GetTag(item); itemResRef=GetResRef(item); baseItem=GetBaseItemType(item); }
  WriteTimestampedLogEntry("HUMAN_CAMERA_EQUIPMENT phase="+phase+" actor="+GetTag(actor)+" slot="+slotName+" slotIndex="+IntToString(slot)+" valid="+IntToString(valid)+" itemTag="+itemTag+" resref="+itemResRef+" baseItem="+IntToString(baseItem));
}
void HumanCameraObserve(string phase, object p) {
  int i; for(i=0;i<8;i++) {
    object actor=GetObjectByTag("tm_"+IntToString(i));
    if(!GetIsObjectValid(actor)) { WriteTimestampedLogEntry("HUMAN_CAMERA_ACTOR_MISSING phase="+phase+" index="+IntToString(i)); }
    else {
      vector v=GetPosition(actor);
      HumanCameraItemObserve(phase,actor,"chest",INVENTORY_SLOT_CHEST);
      HumanCameraItemObserve(phase,actor,"right-hand",INVENTORY_SLOT_RIGHTHAND);
      HumanCameraItemObserve(phase,actor,"left-hand",INVENTORY_SLOT_LEFTHAND);
      WriteTimestampedLogEntry("HUMAN_CAMERA_ACTOR phase="+phase+" tag="+GetTag(actor)+" pose="+IntToString(GetLocalInt(actor,"TM_POSE"))+" palette="+IntToString(GetLocalInt(actor,"TM_PALETTE"))+" action="+IntToString(GetCurrentAction(actor))+" facing="+FloatToString(GetFacing(actor))+" x="+FloatToString(v.x)+" y="+FloatToString(v.y)+" z="+FloatToString(v.z)+" seen="+IntToString(GetObjectSeen(actor,p))+" pcDistance="+FloatToString(GetDistanceBetween(p,actor)));
    }
  }
}
void HumanCameraView(string phase, string tag, float facing) {
  object p=OBJECT_SELF; object actor=GetObjectByTag(tag);
  WriteTimestampedLogEntry("HUMAN_CAMERA_PHASE phase="+phase+" pause="+IntToString(GetGamePauseState()));
  HumanCameraObserve(phase,p);
  if(!GetIsPC(p) || !GetIsObjectValid(actor) || GetArea(p)!=GetArea(actor) || !GetObjectSeen(actor,p)) {
    WriteTimestampedLogEntry("HUMAN_CAMERA_TARGET_UNAVAILABLE phase="+phase+" target="+tag); return;
  }
  LockCameraPitch(p,FALSE); LockCameraDistance(p,FALSE); LockCameraDirection(p,FALSE);
  SetCameraLimits(p,1.0,89.0,1.0,25.0);
  AttachCamera(p,p,FALSE); SetCameraMode(p,CAMERA_MODE_TOP_DOWN); SetCameraHeight(p,0.95);
  AttachCamera(p,actor,FALSE); SetCameraFacing(facing,4.5,75.0,CAMERA_TRANSITION_TYPE_SNAP);
  WriteTimestampedLogEntry("HUMAN_CAMERA_COMMAND phase="+phase+" target="+tag+" facing="+FloatToString(facing)+" distance=4.5 pitch=75 height=0.95 cameraUnlocked=1");
}
void HumanCameraRelease(object p) {
  if(GetIsObjectValid(p)) {
    LockCameraPitch(p,FALSE); LockCameraDistance(p,FALSE); LockCameraDirection(p,FALSE);
    AttachCamera(p,p,FALSE); SetCameraHeight(p,0.0); SetCameraLimits(p);
  }
  WriteTimestampedLogEntry("HUMAN_CAMERA_SEQUENCE_COMPLETE pause="+IntToString(GetGamePauseState()));
}
void StartHumanCameraInspection(object p) {
  if(GetLocalInt(GetModule(),"HUMAN_CAMERA_STARTED")) return;
  SetLocalInt(GetModule(),"HUMAN_CAMERA_STARTED",1);
  WriteTimestampedLogEntry("HUMAN_CAMERA_SEQUENCE_START pauseBefore="+IntToString(GetGamePauseState()));
  SetGameActivePause(FALSE);
  WriteTimestampedLogEntry("HUMAN_CAMERA_CLOCK pauseAfter="+IntToString(GetGamePauseState()));
  AssignCommand(p,HumanCameraView("entry-calibration-front","tm_0",90.0));
  AssignCommand(GetModule(),DelayCommand(10.0,AssignCommand(p,HumanCameraView("tm_0-front","tm_0",90.0))));
  AssignCommand(GetModule(),DelayCommand(22.0,AssignCommand(p,HumanCameraView("tm_0-rear","tm_0",270.0))));
  AssignCommand(GetModule(),DelayCommand(34.0,AssignCommand(p,HumanCameraView("tm_0-side","tm_0",180.0))));
  AssignCommand(GetModule(),DelayCommand(46.0,AssignCommand(p,HumanCameraView("tm_1-front","tm_1",90.0))));
  AssignCommand(GetModule(),DelayCommand(58.0,AssignCommand(p,HumanCameraView("tm_1-rear","tm_1",270.0))));
  AssignCommand(GetModule(),DelayCommand(70.0,AssignCommand(p,HumanCameraView("tm_1-side","tm_1",180.0))));
  AssignCommand(GetModule(),DelayCommand(82.0,AssignCommand(p,HumanCameraView("tm_2-front","tm_2",90.0))));
  AssignCommand(GetModule(),DelayCommand(94.0,AssignCommand(p,HumanCameraView("tm_2-rear","tm_2",270.0))));
  AssignCommand(GetModule(),DelayCommand(106.0,AssignCommand(p,HumanCameraView("tm_2-side","tm_2",180.0))));
  AssignCommand(GetModule(),DelayCommand(118.0,AssignCommand(p,HumanCameraView("tm_3-front","tm_3",90.0))));
  AssignCommand(GetModule(),DelayCommand(130.0,AssignCommand(p,HumanCameraView("tm_3-rear","tm_3",270.0))));
  AssignCommand(GetModule(),DelayCommand(142.0,AssignCommand(p,HumanCameraView("tm_3-side","tm_3",180.0))));
  AssignCommand(GetModule(),DelayCommand(154.0,AssignCommand(p,HumanCameraView("tm_4-front","tm_4",90.0))));
  AssignCommand(GetModule(),DelayCommand(166.0,AssignCommand(p,HumanCameraView("tm_4-rear","tm_4",270.0))));
  AssignCommand(GetModule(),DelayCommand(178.0,AssignCommand(p,HumanCameraView("tm_4-side","tm_4",180.0))));
  AssignCommand(GetModule(),DelayCommand(190.0,AssignCommand(p,HumanCameraView("tm_5-front","tm_5",90.0))));
  AssignCommand(GetModule(),DelayCommand(202.0,AssignCommand(p,HumanCameraView("tm_5-rear","tm_5",270.0))));
  AssignCommand(GetModule(),DelayCommand(214.0,AssignCommand(p,HumanCameraView("tm_5-side","tm_5",180.0))));
  AssignCommand(GetModule(),DelayCommand(226.0,AssignCommand(p,HumanCameraView("tm_6-front","tm_6",90.0))));
  AssignCommand(GetModule(),DelayCommand(238.0,AssignCommand(p,HumanCameraView("tm_6-rear","tm_6",270.0))));
  AssignCommand(GetModule(),DelayCommand(250.0,AssignCommand(p,HumanCameraView("tm_6-side","tm_6",180.0))));
  AssignCommand(GetModule(),DelayCommand(262.0,AssignCommand(p,HumanCameraView("tm_7-front","tm_7",90.0))));
  AssignCommand(GetModule(),DelayCommand(274.0,AssignCommand(p,HumanCameraView("tm_7-rear","tm_7",270.0))));
  AssignCommand(GetModule(),DelayCommand(286.0,AssignCommand(p,HumanCameraView("tm_7-side","tm_7",180.0))));
  AssignCommand(GetModule(),DelayCommand(298.0,HumanCameraRelease(p)));
}
void LegacyEntry() {
  object pc=GetEnteringObject(); if(!GetIsPC(pc)) return;
  LockCameraPitch(pc,FALSE); LockCameraDistance(pc,FALSE); SetCameraLimits(pc);
  WriteTimestampedLogEntry("HUMAN_FEMALE_FIXTURE_ENTER profile=stock-human-female-posture-poses pendingAcceptance=1");
  SendMessageToPC(pc,"Human female fixture: package selection and actual observation determine acceptance.");
  SetLocalInt(GetModule(),"TM_MATRIX",0);
  int i; for(i=0;i<8;i++) { object actor=GetObjectByTag("tm_"+IntToString(i));
    if(GetIsObjectValid(actor)) AssignCommand(actor,ExecuteScript("sr_tm_spawn",actor)); }
  StartHumanCameraInspection(pc);
}

// Mode 3 is a separate diagnostic. Original spawn/equipment and mode 2 stay intact.
// Literal schedule ID avoids a self-referential source/schedule hash.
void FemaleTransitionClock(int run) {
  object m=GetModule();
  if(GetLocalInt(m,"SF_RUN")!=run || GetLocalInt(m,"SF_COMPLETE")) return;
  SetLocalFloat(m,"SF_CLOCK",GetLocalFloat(m,"SF_CLOCK")+0.1);
  ExecuteScript("sr_tm_next",m);
  DelayCommand(0.1,FemaleTransitionClock(run));
}
void FemaleTransitionInitialize(object pc, int run) {
  object m=GetModule(); if(GetLocalInt(m,"SF_RUN")!=run) return;
  int firstAppearance=GetAppearanceType(GetObjectByTag("tm_0"));
  int batch=firstAppearance/2+1;
  if(firstAppearance!=0 && firstAppearance!=2 && firstAppearance!=4 && firstAppearance!=6) {
    WriteTimestampedLogEntry("SF_TRANSITION_ERROR reason=unexpected-batch"); return;
  }
  SetLocalInt(m,"SF_BATCH",batch); SetLocalInt(m,"SF_GROUP",0); SetLocalInt(m,"SF_PHASE",0);
  SetLocalObject(m,"SF_PC",pc); SetLocalFloat(m,"SF_CLOCK",0.0);
  int i; for(i=0;i<8;i++) {
    object a=GetObjectByTag("tm_"+IntToString(i));
    if(!GetIsObjectValid(a) || !GetLocalInt(a,"TM_INITIALIZED") || GetLocalInt(a,"TM_POSE")>1) {
      WriteTimestampedLogEntry("SF_TRANSITION_ERROR reason=actor-not-initialized tag=tm_"+IntToString(i)); return;
    }
    int group=i/4; if(batch==4 && i>=4) group=1+(i-4)/2;
    SetLocalInt(a,"SF_GROUP",group); SetLocalInt(a,"SF_LAST_PHASE",-1);
    SetLocalInt(a,"SF_READY",0); SetLocalInt(a,"TM_SCHEDULE_MODE",3);
    // This is the ONLY actor queue reset in mode 3, before any measured baseline.
    AssignCommand(a,ClearAllActions(TRUE));
  }
  WriteTimestampedLogEntry("SF_TRANSITION_START schedule=shared-female-transitions-v1 run="+IntToString(run)+" batch="+IntToString(batch)+" pause="+IntToString(GetGamePauseState()));
  AssignCommand(m,DelayCommand(0.25,FemaleTransitionClock(run)));
}
void main() {
  object pc=GetEnteringObject(); if(!GetIsPC(pc)) return;
  object m=GetModule(); if(GetLocalInt(m,"SF_RUN")) return;
  int run=1; SetLocalInt(m,"SF_RUN",run); SetLocalInt(m,"TM_MATRIX",0);
  SetGameActivePause(FALSE);
  LockCameraPitch(pc,FALSE); LockCameraDistance(pc,FALSE); LockCameraDirection(pc,FALSE);
  SetCameraLimits(pc,1.0,89.0,1.0,25.0);
  int i; for(i=0;i<8;i++) {
    object a=GetObjectByTag("tm_"+IntToString(i));
    if(GetIsObjectValid(a)) AssignCommand(a,ExecuteScript("sr_tm_spawn",a));
  }
  // Let the unchanged spawn finish before the single initialization reset.
  AssignCommand(m,DelayCommand(1.0,FemaleTransitionInitialize(pc,run)));
}
