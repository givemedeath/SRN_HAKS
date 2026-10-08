void Mark(string state) {
  vector v=GetPosition(OBJECT_SELF);
  WriteTimestampedLogEntry("HUMAN_FEMALE_FIXTURE_ACTION actor="+GetTag(OBJECT_SELF)+" state="+state+" phase="+IntToString(GetLocalInt(OBJECT_SELF,"TM_PHASE"))+" action="+IntToString(GetCurrentAction())+" x="+FloatToString(v.x)+" y="+FloatToString(v.y)+" z="+FloatToString(v.z));
}
void Continue(int phase) {
  if(GetLocalInt(OBJECT_SELF,"TM_PHASE")!=phase || GetLocalInt(OBJECT_SELF,"TM_SCHEDULE_MODE")!=2) return;
  ClearAllActions(TRUE); ExecuteScript("sr_tm_next",OBJECT_SELF);
}
void Recover(int phase) {
  if(GetLocalInt(OBJECT_SELF,"TM_PHASE")!=phase || GetLocalInt(OBJECT_SELF,"TM_SCHEDULE_MODE")!=2) return;
  ApplyEffectToObject(DURATION_TYPE_INSTANT,EffectResurrection(),OBJECT_SELF);
  ApplyEffectToObject(DURATION_TYPE_INSTANT,EffectHeal(1000),OBJECT_SELF);
  SetImmortal(OBJECT_SELF,TRUE); JumpToLocation(GetLocalLocation(OBJECT_SELF,"HOME"));
  Mark("resurrected"); Continue(phase);
}
void LegacyNext() {
  if(GetLocalInt(OBJECT_SELF,"TM_SCHEDULE_MODE")!=2) return;
  int phase=GetLocalInt(OBJECT_SELF,"TM_PHASE")+1;
  SetLocalInt(OBJECT_SELF,"TM_PHASE",phase); int step=(phase-1)%13;
  ClearAllActions(TRUE); Mark("phase-start");
  if(step==2 || step==3) {
    location home=GetLocalLocation(OBJECT_SELF,"HOME"); vector out=GetPositionFromLocation(home); out.y+=24.0;
    ActionMoveToLocation(Location(GetArea(OBJECT_SELF),out,90.0),step==3);
    ActionDoCommand(Mark("outward-arrived")); ActionMoveToLocation(home,step==3);
    ActionDoCommand(Mark("home-arrived")); ActionWait(12.0);
    ActionDoCommand(ExecuteScript("sr_tm_next",OBJECT_SELF)); return;
  }
  if(step==4 || step==5) {
    object target=GetLocalObject(OBJECT_SELF,"TARGET");
    if(!GetIsObjectValid(target)) {
      vector v=GetPosition(OBJECT_SELF); v.y+=2.0;
      target=CreateObject(OBJECT_TYPE_CREATURE,"sr_tm_target",Location(GetArea(OBJECT_SELF),v,270.0));
      SetLocalObject(OBJECT_SELF,"TARGET",target); SetImmortal(target,TRUE);
      AssignCommand(target,ClearAllActions(TRUE)); SetCommandable(FALSE,target);
    }
    SetIsTemporaryEnemy(target,OBJECT_SELF);
    if(step==4) { ActionCastSpellAtObject(SPELL_MAGIC_MISSILE,target,METAMAGIC_NONE,TRUE); ActionWait(1.0);
      ActionCastSpellAtObject(SPELL_MAGIC_MISSILE,target,METAMAGIC_NONE,TRUE); ActionWait(12.0);
      ActionDoCommand(ExecuteScript("sr_tm_next",OBJECT_SELF)); }
    else { ActionAttack(target); DelayCommand(24.0,Continue(phase)); }
    return;
  }
  if(step==10) {
    SetImmortal(OBJECT_SELF,FALSE); SetPlotFlag(OBJECT_SELF,FALSE);
    ApplyEffectToObject(DURATION_TYPE_INSTANT,EffectDeath(FALSE,FALSE),OBJECT_SELF);
    object corpse=OBJECT_SELF;
    AssignCommand(GetModule(),DelayCommand(18.0,AssignCommand(corpse,Recover(phase)))); return;
  }
  if(step==11) ApplyEffectToObject(DURATION_TYPE_INSTANT,EffectDamage(3,DAMAGE_TYPE_MAGICAL),OBJECT_SELF);
  int animation=ANIMATION_LOOPING_PAUSE;
  if(step==1) animation=ANIMATION_LOOPING_PAUSE2;
  if(step==6) animation=ANIMATION_LOOPING_GET_LOW;
  if(step==7) animation=ANIMATION_LOOPING_WORSHIP;
  if(step==8) animation=ANIMATION_LOOPING_DEAD_FRONT;
  if(step==9) animation=ANIMATION_LOOPING_DEAD_BACK;
  if(step==11) animation=ANIMATION_LOOPING_TALK_NORMAL;
  if(step==12) animation=ANIMATION_FIREFORGET_BOW;
  ActionPlayAnimation(animation,1.0,18.0); ActionWait(2.0);
  ActionDoCommand(ExecuteScript("sr_tm_next",OBJECT_SELF));
}

// Arrival callbacks follow the actual movement action; no timer substitutes for arrival.
string FemaleGroupID() {
  object m=GetModule(); int group=GetLocalInt(m,"SF_GROUP"); int batch=GetLocalInt(m,"SF_BATCH");
  int start=group*4; if(batch==4 && group>0) start=4+(group-1)*2;
  object first=GetObjectByTag("tm_"+IntToString(start));
  string purpose="required-case"; if(batch==4 && group>0) purpose="equipment-control";
  return "batch-"+IntToString(batch)+"-"+purpose+"-race-"+IntToString(GetAppearanceType(first));
}
void FemaleEvent(string state, int requested) {
  object m=GetModule(); vector p=GetPosition(OBJECT_SELF);
  WriteTimestampedLogEntry("SF_TRANSITION_EVENT schedule=shared-female-transitions-v1 group="+FemaleGroupID()+" actor="+GetTag(OBJECT_SELF)+" run="+IntToString(GetLocalInt(m,"SF_RUN"))+" phase="+IntToString(GetLocalInt(m,"SF_PHASE"))+" state="+state+" elapsed="+FloatToString(GetLocalFloat(m,"SF_CLOCK"),9,3)+" requested="+IntToString(requested)+" action="+IntToString(GetCurrentAction())+" x="+FloatToString(p.x,9,4)+" y="+FloatToString(p.y,9,4)+" z="+FloatToString(p.z,9,4)+" facing="+FloatToString(GetFacing(OBJECT_SELF),9,4)+" pause="+IntToString(GetGamePauseState()));
}
void FemaleIdleComplete(int baseline) {
  string state="idle-complete"; if(baseline) state="baseline-complete";
  FemaleEvent(state,GetLocalInt(OBJECT_SELF,"TM_POSE"));
  SetLocalInt(OBJECT_SELF,"SF_READY",1);
}
void FemaleQueueIdle(int baseline) {
  int pose=GetLocalInt(OBJECT_SELF,"TM_POSE");
  string state="idle-request"; if(baseline) state="baseline-request";
  FemaleEvent(state,pose);
  int animation=ANIMATION_LOOPING_PAUSE; if(pose==1) animation=ANIMATION_LOOPING_PAUSE2;
  // Native blend, at least two complete cycles, plus seven seconds for close visual sampling.
  // No clear, wait, jump, facing reset or hold is inserted between active motion and idle.
  float duration=12.50; int appearance=GetAppearanceType(OBJECT_SELF);
  if(appearance==0 || appearance==5) duration=12.20;
  ActionPlayAnimation(animation,1.0,duration);
  ActionDoCommand(FemaleIdleComplete(baseline));
}
void FemaleHomeArrived(int run) {
  string state="walk-home-arrived"; if(run) state="run-home-arrived"; FemaleEvent(state,run);
  FemaleQueueIdle(FALSE);
}
void FemalePostureComplete(int kneel) {
  string state="crouch-complete"; int requested=ANIMATION_LOOPING_GET_LOW;
  if(kneel) {state="kneel-complete";requested=ANIMATION_LOOPING_WORSHIP;}
  FemaleEvent(state,requested); FemaleQueueIdle(FALSE);
}
void FemaleGroupCamera(object pc, object anchor, int phase) {
  if(!GetIsPC(pc) || !GetIsObjectValid(anchor) || GetIsPC(anchor)) {
    WriteTimestampedLogEntry("SF_REVIEW_CAMERA_ERROR reason=invalid-actor-anchor"); return;
  }
  WriteTimestampedLogEntry("SF_REVIEW_CAMERA actor="+GetTag(anchor)+" phase="+IntToString(phase)+" distance=4.5 pitch=75");
  float facing=90.0; if(phase==2 || phase==3) facing=135.0; if(phase==4) facing=270.0;
  LockCameraPitch(pc,FALSE); LockCameraDistance(pc,FALSE); LockCameraDirection(pc,FALSE);
  SetCameraLimits(pc,1.0,89.0,1.0,25.0); SetCameraHeight(pc,0.95);
  AttachCamera(pc,anchor,FALSE); SetCameraFacing(facing,4.5,75.0,CAMERA_TRANSITION_TYPE_SNAP);
}
void FemaleBarrier() {
  object m=GetModule(); if(GetLocalInt(m,"SF_COMPLETE")) return;
  int group=GetLocalInt(m,"SF_GROUP"); int ready=1; int count=0; int i;
  for(i=0;i<8;i++) {object a=GetObjectByTag("tm_"+IntToString(i));
    if(GetLocalInt(a,"SF_GROUP")==group) {count++; if(!GetLocalInt(a,"SF_READY")) ready=0;}}
  if(count==0) {WriteTimestampedLogEntry("SF_TRANSITION_ERROR reason=empty-group");SetLocalInt(m,"SF_COMPLETE",1);return;}
  if(ready) {
    int phase=GetLocalInt(m,"SF_PHASE")+1;
    if(phase==5) {phase=0;group++;}
    int groupCount=2; if(GetLocalInt(m,"SF_BATCH")==4) groupCount=3;
    if(group==groupCount) {
      SetLocalInt(m,"SF_COMPLETE",1);
      object pc=GetLocalObject(m,"SF_PC"); AssignCommand(pc,AttachCamera(pc,pc,FALSE));
      WriteTimestampedLogEntry("SF_TRANSITION_COMPLETE run="+IntToString(GetLocalInt(m,"SF_RUN"))+" elapsed="+FloatToString(GetLocalFloat(m,"SF_CLOCK"),9,3));return;
    }
    SetLocalInt(m,"SF_GROUP",group); SetLocalInt(m,"SF_PHASE",phase);
    for(i=0;i<8;i++) {object a=GetObjectByTag("tm_"+IntToString(i));
      if(GetLocalInt(a,"SF_GROUP")==group) SetLocalInt(a,"SF_READY",0);}
  }
  // Review one actor at a time. An in-flight actor owns the camera until its
  // actual action callback completes; no queue reset interrupts a measured blend.
  for(i=0;i<8;i++) {object a=GetObjectByTag("tm_"+IntToString(i));
    if(GetLocalInt(a,"SF_GROUP")==group && !GetLocalInt(a,"SF_READY")) {
      if(GetLocalInt(a,"SF_LAST_PHASE")!=GetLocalInt(m,"SF_PHASE"))
        AssignCommand(a,ExecuteScript("sr_tm_next",a));
      return;
    }
  }
}
void FemaleActorPhase() {
  object m=GetModule(); int phase=GetLocalInt(m,"SF_PHASE");
  if(GetLocalInt(OBJECT_SELF,"SF_GROUP")!=GetLocalInt(m,"SF_GROUP") ||
      GetLocalInt(OBJECT_SELF,"SF_LAST_PHASE")==phase) return;
  SetLocalInt(OBJECT_SELF,"SF_LAST_PHASE",phase);
  int first=GetLocalInt(m,"SF_GROUP")*4;
  if(GetLocalInt(m,"SF_BATCH")==4 && GetLocalInt(m,"SF_GROUP")>0) first=4+(GetLocalInt(m,"SF_GROUP")-1)*2;
  // AssignCommand changes OBJECT_SELF to the command receiver. Capture the actor first.
  object reviewActor=OBJECT_SELF;
  object reviewPC=GetLocalObject(m,"SF_PC");
  AssignCommand(reviewPC,FemaleGroupCamera(reviewPC,reviewActor,phase));
  if(phase==0) {FemaleQueueIdle(TRUE);return;}
  if(phase==1 || phase==2) {
    int run=phase==2; string state="walk-request"; if(run) state="run-request";
    FemaleEvent(state,run);
    location home=GetLocalLocation(OBJECT_SELF,"HOME"); vector out=GetPositionFromLocation(home);
    if(out.y<20.0) out.y-=12.0; else out.y+=12.0;
    ActionMoveToLocation(Location(GetArea(OBJECT_SELF),out,GetFacing(OBJECT_SELF)),run);
    string arrived="walk-out-arrived"; if(run) arrived="run-out-arrived";
    ActionDoCommand(FemaleEvent(arrived,run));
    ActionMoveToLocation(home,run);
    ActionDoCommand(FemaleHomeArrived(run));return;
  }
  int animation=ANIMATION_LOOPING_GET_LOW; string state="crouch-request";
  if(phase==4) {animation=ANIMATION_LOOPING_WORSHIP;state="kneel-request";}
  FemaleEvent(state,animation);
  // Extra real dwell covers delayed clock callbacks; the eight-second check stays strict.
  ActionPlayAnimation(animation,1.0,9.50);
  ActionDoCommand(FemalePostureComplete(phase==4));
}
void main() {
  if(OBJECT_SELF==GetModule()) {FemaleBarrier();return;}
  if(GetLocalInt(OBJECT_SELF,"TM_SCHEDULE_MODE")!=3) {LegacyNext();return;}
  FemaleActorPhase();
}
