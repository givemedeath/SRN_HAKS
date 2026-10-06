// Shared gallery controls. Content data lives in module locals generated at build time.
string GGPart(string text, int part) {
  int start=0; int i; int end;
  for(i=0;i<part;i++){end=FindSubString(text,"|",start);if(end<0)return "";start=end+1;}
  end=FindSubString(text,"|",start);if(end<0)end=GetStringLength(text);
  return GetSubString(text,start,end-start);
}
location GGHome(){return Location(GetObjectByTag("SR_G_START"),Vector(25.0,18.0,0.0),90.0);}
location GGSlot(int slot){return Location(GetObjectByTag("SR_G_START"),Vector(14.0+IntToFloat(slot%6)*12.0,46.0+IntToFloat(slot/6)*14.0,0.0),90.0);}
void GGClear(){
  object module=GetModule();int i;
  for(i=0;i<32;i++){object item=GetLocalObject(module,"gg_display"+IntToString(i));if(GetIsObjectValid(item))DestroyObject(item);DeleteLocalObject(module,"gg_display"+IntToString(i));}
}
void GGHelp(object pc){
  SendMessageToPC(pc,"SRN Gallery: use the labeled controls to browse. Chat: .gallery find <text>, .gallery stage <id>, .gallery home.");
  SendMessageToPC(pc,"More: .gallery category placeables|doors|items|creatures|sounds|music|skyboxes|tilesets; .gallery page <number>; .gallery area <resref>.");
}
void GGSelect(object pc,string category,int index){
  object module=GetModule();string row=GetLocalString(module,"gg_"+category+"_"+IntToString(index));
  if(row==""){SendMessageToPC(pc,"Gallery entry unavailable.");return;}
  string option=GGPart(row,3);int number=StringToInt(option);
  if(category=="sounds"){AssignCommand(pc,PlaySound(GGPart(row,1)));}
  else if(category=="music"){
    if(number<0){SendMessageToPC(pc,"This music resource has no production music-table row; see the saved catalog.");return;}
    MusicBackgroundChangeDay(GetArea(pc),number);MusicBackgroundChangeNight(GetArea(pc),number);MusicBackgroundPlay(GetArea(pc));
  }
  else if(category=="skyboxes"){SetSkyBox(number,GetArea(pc));}
  else if(category=="tilesets"){object area=GetObjectByTag(option);if(GetIsObjectValid(area))AssignCommand(pc,JumpToLocation(Location(area,Vector(5.0,5.0,0.0),90.0)));}
  SendMessageToPC(pc,GGPart(row,2)+" ["+GGPart(row,4)+"]");
}
object GGCreate(object pc,string category,int index,location where,int permanent=FALSE){
  string row=GetLocalString(GetModule(),"gg_"+category+"_"+IntToString(index));if(row=="")return OBJECT_INVALID;
  int kind=StringToInt(GGPart(row,0));object item;
  if(kind>0){item=CreateObject(kind,GGPart(row,1),where,FALSE,"GG_DISPLAY");}
  else {
    item=CreateObject(OBJECT_TYPE_PLACEABLE,"gg_button",where,FALSE,"GG_SELECTOR");
    SetLocalString(item,"GG_CATEGORY",category);SetLocalInt(item,"GG_INDEX",index);SetLocalString(item,"GG_ACTION","select");
  }
  if(GetIsObjectValid(item)){
    SetName(item,GGPart(row,2));SetLocalString(item,"GG_ID",GGPart(row,4));
    if(permanent)SetTag(item,"GG_STAGED");
  }else SendMessageToPC(pc,"Could not spawn "+GGPart(row,4)+"; record this client inspection failure.");
  return item;
}
void GGPage(object pc,string category,int page){
  object module=GetModule();int count=GetLocalInt(module,"gg_count_"+category);int size=GetLocalInt(module,"gg_page_size");
  if(count<1){SendMessageToPC(pc,"No entries in "+category+".");return;}
  int pages=(count+size-1)/size;if(page<0)page=pages-1;if(page>=pages)page=0;
  GGClear();SetLocalString(module,"gg_category",category);SetLocalInt(module,"gg_page",page);
  int i;for(i=0;i<size && page*size+i<count;i++)SetLocalObject(module,"gg_display"+IntToString(i),GGCreate(pc,category,page*size+i,GGSlot(i)));
  SendMessageToPC(pc,category+": page "+IntToString(page+1)+" / "+IntToString(pages)+"; "+IntToString(count)+" entries.");
}
// Yield between bounded batches so a large catalog cannot exhaust the VM
// instruction limit when searching for an absent entry.
void GGSearchChunk(object pc,string query,int c,int i,int found);
void GGSearchChunk(object pc,string query,int c,int i,int found){
  if(!GetIsObjectValid(pc))return;
  object module=GetModule();int budget=100;
  while(c<8 && budget>0){
    string category=GetLocalString(module,"gg_category"+IntToString(c));
    int count=GetLocalInt(module,"gg_count_"+category);
    if(i>=count){c++;i=0;continue;}
    string row=GetLocalString(module,"gg_"+category+"_"+IntToString(i));string id=GGPart(row,4);
    if(FindSubString(GetStringLowerCase(id+" "+GGPart(row,2)),query)>=0){
      SendMessageToPC(pc,id+" - "+GGPart(row,2));found++;
      if(found>=12){SendMessageToPC(pc,"First 12 matches shown; refine your search.");return;}
    }
    i++;budget--;
  }
  if(c<8)DelayCommand(0.05,GGSearchChunk(pc,query,c,i,found));
  else if(found==0)SendMessageToPC(pc,"No matching gallery entry.");
}
void GGFind(object pc,string query,int stage=FALSE){
  object module=GetModule();int c;int i;int found=0;query=GetStringLowerCase(query);
  if(stage){
    string selected=GetLocalString(module,"gg_id_"+query);
    if(selected==""){SendMessageToPC(pc,"Unknown gallery entry ID.");return;}
    int n=GetLocalInt(module,"gg_staged_count");
    if(n>=24){SendMessageToPC(pc,"Staging list is full. Rebuild your prestaged list or reload to clear temporary staging.");return;}
    location home=GGHome();vector v=GetPositionFromLocation(home);v.x=14.0+IntToFloat(n%6)*12.0;v.y=108.0+IntToFloat(n/6)*10.0;
    object item=GGCreate(pc,GGPart(selected,0),StringToInt(GGPart(selected,1)),Location(GetAreaFromLocation(home),v,90.0),TRUE);
    if(GetIsObjectValid(item))SetLocalInt(module,"gg_staged_count",n+1);return;
  }
  GGSearchChunk(pc,query,0,0,0);
}
void GGAction(object pc,string command,string argument=""){
  object module=GetModule();string category=GetLocalString(module,"gg_category");int page=GetLocalInt(module,"gg_page");
  if(command=="next")GGPage(pc,category,page+1);
  else if(command=="previous")GGPage(pc,category,page-1);
  else if(command=="category")GGPage(pc,argument,0);
  else if(command=="page")GGPage(pc,category,StringToInt(argument)-1);
  else if(command=="find")GGFind(pc,argument);
  else if(command=="stage")GGFind(pc,argument,TRUE);
  else if(command=="home")AssignCommand(pc,JumpToLocation(GGHome()));
  else if(command=="area"){
    object area=GetObjectByTag(argument);if(GetIsObjectValid(area) && GetLocalInt(module,"gg_area_"+argument)==1)AssignCommand(pc,JumpToLocation(Location(area,Vector(5.0,5.0,0.0),90.0)));
    else SendMessageToPC(pc,"Unknown gallery area; see the saved catalog.");
  }
  else GGHelp(pc);
}
