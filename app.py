import json
import os
import re
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone

import chromadb
import streamlit as st
import swisseph as swe
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_openai import ChatOpenAI

st.set_page_config(page_title="Ancient Wisdom Synthesis", page_icon="🕉️", layout="wide", initial_sidebar_state="expanded")

APP_VERSION = "AWS v1.30 Release Candidate"
EMBEDDING_MODEL = "paraphrase-MiniLM-L3-v2"
COLLECTION_NAME = "ancient_wisdom"
PAGES = ["Home", "Ask", "My Reading", "My Remedies", "Explore"]
KNOWLEDGE_MODES = ["Trusted Library", "Deep Research", "Offline"]
DEPTHS = ["Simple", "Detailed", "Advanced"]

st.markdown("""
<style>
.stApp{background:radial-gradient(circle at 15% 0%,#202653 0,#11152d 38%,#090b18 100%);color:#f5f0e8}
.block-container{max-width:1440px;padding-top:1rem;padding-bottom:4rem}
[data-testid="stSidebar"]{background:#11142b;border-right:1px solid #303558}
[data-testid="stMetric"]{background:linear-gradient(145deg,rgba(31,36,70,.97),rgba(19,22,45,.97));border:1px solid #3a3f68;border-radius:16px;padding:14px;box-shadow:0 10px 26px rgba(0,0,0,.2)}
[data-testid="stMetricLabel"]{color:#aaa6b6!important}[data-testid="stMetricValue"]{color:#e2c45f!important}
[data-testid="stExpander"]{background:rgba(18,22,45,.82);border:1px solid #343961;border-radius:14px}
.stButton>button{background:linear-gradient(135deg,#5d4ba0,#8d68d8);color:white;border:1px solid #9d83df;border-radius:22px;font-weight:650;min-height:2.65rem;box-shadow:0 7px 17px rgba(72,49,128,.26)}
.stButton>button:hover{border-color:#e2c45f;color:white;transform:translateY(-1px)}
h1,h2,h3,h4{color:#f6f0e7}.hero{padding:16px 22px;border:1px solid #41466f;border-radius:20px;background:linear-gradient(135deg,rgba(37,43,84,.97),rgba(17,20,43,.94));box-shadow:0 16px 42px rgba(0,0,0,.25);margin-bottom:14px}.hero h1{font-size:1.9rem!important;line-height:1.15!important;margin:.28rem 0 .45rem!important}.eyebrow{color:#e2c45f;font-size:.7rem;font-weight:760;letter-spacing:.16em;text-transform:uppercase}.subtitle{color:#bbb5c8;font-size:.96rem;margin:0}.choice{padding:17px;border:1px solid #3a3f67;border-radius:16px;background:linear-gradient(145deg,rgba(28,32,63,.95),rgba(17,20,42,.95));min-height:140px}.muted{color:#9c97aa}.mode-note{padding:10px 13px;border-left:3px solid #e2c45f;background:#171a36;border-radius:8px;color:#ccc6d3}
</style>
""", unsafe_allow_html=True)

SIGNS=["Aries","Taurus","Gemini","Cancer","Leo","Virgo","Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
NAKSHATRAS=["Ashwini","Bharani","Krittika","Rohini","Mrigashirsha","Ardra","Punarvasu","Pushya","Ashlesha","Magha","Purva Phalguni","Uttara Phalguni","Hasta","Chitra","Swati","Vishakha","Anuradha","Jyeshtha","Mula","Purvashadha","Uttarashadha","Shravana","Dhanishta","Shatabhisha","Purva Bhadrapada","Uttara Bhadrapada","Revati"]
NAK_LORDS=["Ketu","Venus","Sun","Moon","Mars","Rahu","Jupiter","Saturn","Mercury"]
NAK_SIZE=360/27; PADA_SIZE=NAK_SIZE/4; FLAGS=swe.FLG_SWIEPH|swe.FLG_SIDEREAL
DASHA_SEQ=["Ketu","Venus","Sun","Moon","Mars","Rahu","Jupiter","Saturn","Mercury"]
DASHA_YEARS={"Ketu":7,"Venus":20,"Sun":6,"Moon":10,"Mars":7,"Rahu":18,"Jupiter":16,"Saturn":19,"Mercury":17}
SIGN_LORDS={"Aries":"Mars","Taurus":"Venus","Gemini":"Mercury","Cancer":"Moon","Leo":"Sun","Virgo":"Mercury","Libra":"Venus","Scorpio":"Mars","Sagittarius":"Jupiter","Capricorn":"Saturn","Aquarius":"Saturn","Pisces":"Jupiter"}
OWN={"Sun":["Leo"],"Moon":["Cancer"],"Mars":["Aries","Scorpio"],"Mercury":["Gemini","Virgo"],"Jupiter":["Sagittarius","Pisces"],"Venus":["Taurus","Libra"],"Saturn":["Capricorn","Aquarius"]}
EXALT={"Sun":"Aries","Moon":"Taurus","Mars":"Capricorn","Mercury":"Virgo","Jupiter":"Cancer","Venus":"Pisces","Saturn":"Libra"}
DEBIL={"Sun":"Libra","Moon":"Scorpio","Mars":"Cancer","Mercury":"Pisces","Jupiter":"Capricorn","Venus":"Virgo","Saturn":"Aries"}
COMBUST={"Moon":12,"Mars":17,"Mercury":14,"Jupiter":11,"Venus":10,"Saturn":15}
ASPECTS={"Sun":[7],"Moon":[7],"Mercury":[7],"Venus":[7],"Mars":[4,7,8],"Jupiter":[5,7,9],"Saturn":[3,7,10]}
PLAIN={"Sun":"identity, vitality and leadership","Moon":"mind, emotions and inner security","Mars":"action, courage and directed energy","Mercury":"thinking, communication and adaptability","Jupiter":"growth, wisdom and judgement","Venus":"relationships, harmony and creativity","Saturn":"discipline, responsibility and endurance","Rahu":"intense desire and unfamiliar territory","Ketu":"detachment, insight and inward focus"}
LOCATION_PRESETS={"Hong Kong":(22.3193,114.1694,8.0),"Bharwain / Chintpurni, Himachal Pradesh":(31.64,76.13,5.5),"New Delhi":(28.6139,77.2090,5.5),"Mumbai":(19.0760,72.8777,5.5),"Singapore":(1.3521,103.8198,8.0),"Dubai":(25.2048,55.2708,4.0),"London":(51.5074,-0.1278,0.0),"New York":(40.7128,-74.0060,-5.0),"Los Angeles":(34.0522,-118.2437,-8.0),"Toronto":(43.6532,-79.3832,-5.0),"Sydney":(-33.8688,151.2093,10.0),"Melbourne":(-37.8136,144.9631,10.0),"Custom / other":(22.3193,114.1694,8.0)}

def sign_info(lon):
    lon%=360; i=int(lon/30); return {"longitude":lon,"sign":SIGNS[i],"degree":lon%30,"sign_index":i}
def nak_info(lon):
    lon%=360; i=min(int(lon/NAK_SIZE),26); within=lon-i*NAK_SIZE
    return {"nakshatra":NAKSHATRAS[i],"pada":min(int(within/PADA_SIZE)+1,4),"lord":NAK_LORDS[i%9],"within":within}
def fmt_deg(v):
    d=int(v); mf=(v-d)*60; m=int(mf); s=round((mf-m)*60)
    if s==60:s=0;m+=1
    if m==60:m=0;d+=1
    return f"{d:02d}° {m:02d}′ {s:02d}″"
def angle(a,b):
    d=abs((a-b)%360); return min(d,360-d)
def body(jd,pid):
    x,_=swe.calc_ut(jd,pid,FLAGS); out=sign_info(x[0]); out.update(nak_info(x[0])); out["retrograde"]=x[3]<0; return out
def add_years(dt,y): return dt+timedelta(days=y*365.2425)
def vimshottari(moon_lon,birth,analysis_dt):
    n=nak_info(moon_lon); lord=n["lord"]; elapsed=DASHA_YEARS[lord]*(n["within"]/NAK_SIZE); cursor=add_years(birth,-elapsed); idx=DASHA_SEQ.index(lord); mds=[]
    for _ in range(3):
        for off in range(9):
            l=DASHA_SEQ[(idx+off)%9]; end=add_years(cursor,DASHA_YEARS[l]); mds.append({"lord":l,"start":cursor,"end":end}); cursor=end
    target=max(analysis_dt,birth)
    md=next(x for x in mds if x["start"]<=target<x["end"])
    idx=DASHA_SEQ.index(md["lord"]); cursor=md["start"]; ads=[]
    for off in range(9):
        l=DASHA_SEQ[(idx+off)%9]; end=add_years(cursor,DASHA_YEARS[md["lord"]]*DASHA_YEARS[l]/120); ads.append({"lord":l,"start":cursor,"end":end}); cursor=end
    ad=next(x for x in ads if x["start"]<=target<x["end"])
    return {"analysis_date":target.date().isoformat(),"mahadasha":md["lord"],"md_start":md["start"].date().isoformat(),"md_end":md["end"].date().isoformat(),"antardasha":ad["lord"],"ad_start":ad["start"].date().isoformat(),"ad_end":ad["end"].date().isoformat(),"md_timeline":[{"Mahadasha":x["lord"],"Start":x["start"].date().isoformat(),"End":x["end"].date().isoformat(),"Current":"Yes" if x is md else ""} for x in mds[:9]],"ad_timeline":[{"Antardasha":x["lord"],"Start":x["start"].date().isoformat(),"End":x["end"].date().isoformat(),"Current":"Yes" if x is ad else ""} for x in ads]}
def calculate_chart(dob,tob,lat,lon,tz):
    swe.set_sid_mode(swe.SIDM_LAHIRI,0,0); hour=tob.hour+tob.minute/60+tob.second/3600; jd=swe.julday(dob.year,dob.month,dob.day,hour-tz,swe.GREG_CAL)
    _,ascmc=swe.houses_ex(jd,lat,lon,b"W",swe.FLG_SIDEREAL); asc=sign_info(ascmc[0]); asc.update(nak_info(ascmc[0]))
    ids={"Sun":swe.SUN,"Moon":swe.MOON,"Mars":swe.MARS,"Mercury":swe.MERCURY,"Jupiter":swe.JUPITER,"Venus":swe.VENUS,"Saturn":swe.SATURN,"Rahu":swe.MEAN_NODE}; ps={n:body(jd,i) for n,i in ids.items()}
    ketu=sign_info(ps["Rahu"]["longitude"]+180); ketu.update(nak_info(ketu["longitude"])); ketu["retrograde"]=True; ps["Ketu"]=ketu
    rules={n:[] for n in ["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn"]}
    for h in range(1,13): rules[SIGN_LORDS[SIGNS[(asc["sign_index"]+h-1)%12]]].append(h)
    for n,p in ps.items():
        p["house"]=((p["sign_index"]-asc["sign_index"])%12)+1; labels=[]
        if n in OWN and p["sign"] in OWN[n]:labels.append("Own sign")
        if n in EXALT and p["sign"]==EXALT[n]:labels.append("Exaltation sign")
        if n in DEBIL and p["sign"]==DEBIL[n]:labels.append("Debilitation sign")
        if p["retrograde"] and n not in ("Rahu","Ketu"):labels.append("Retrograde")
        if n in COMBUST and angle(p["longitude"],ps["Sun"]["longitude"])<=COMBUST[n]:labels.append("Combustion screening flag")
        p["condition"]=labels or ["No major condition flagged"]; p["rules_houses"]=rules.get(n,[])
    conjunctions=[]; names=list(ps)
    for i,a in enumerate(names):
        for b in names[i+1:]:
            if ps[a]["sign_index"]==ps[b]["sign_index"]:conjunctions.append({"Planets":f"{a} + {b}","Sign":ps[a]["sign"],"House":ps[a]["house"],"Separation":round(angle(ps[a]["longitude"],ps[b]["longitude"]),2)})
    aspects=[]
    for n,offs in ASPECTS.items():
        for off in offs:
            target=((ps[n]["house"]+off-2)%12)+1; targets=[x for x,p in ps.items() if p["house"]==target and x!=n]; aspects.append({"Planet":n,"Aspect":f"{off}th","From":ps[n]["house"],"To":target,"Target planets":", ".join(targets) or "—"})
    ak=max(["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn"],key=lambda n:ps[n]["degree"])
    birth=(datetime(dob.year,dob.month,dob.day,tob.hour,tob.minute,tob.second)-timedelta(hours=tz)).replace(tzinfo=timezone.utc); now=datetime.now(timezone.utc)
    return {"ascendant":asc,"planets":ps,"atmakaraka":ak,"timing":vimshottari(ps["Moon"]["longitude"],birth,now),"conjunctions":conjunctions,"aspects":aspects,"ayanamsa":swe.get_ayanamsa_ut(jd)}

@st.cache_resource(show_spinner=False)
def get_embeddings(): return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
@st.cache_resource(show_spinner=False)
def get_store():
    path="chroma_db"; db=os.path.join(path,"chroma.sqlite3")
    if not os.path.isfile(db):return None,0
    client=chromadb.PersistentClient(path=path); names=[c.name if hasattr(c,"name") else str(c) for c in client.list_collections()]; name=COLLECTION_NAME if COLLECTION_NAME in names else (names[0] if names else None)
    if not name:return None,0
    return Chroma(client=client,collection_name=name,embedding_function=get_embeddings()),client.get_collection(name).count()
@st.cache_data(show_spinner=False)
def get_practitioners():
    rows=[]
    for fn in ["integrative_practitioner_knowledge_v1_2.json","additional_practitioner_talks_v1.json"]:
        if not os.path.isfile(fn):continue
        with open(fn,encoding="utf-8") as f:data=json.load(f)
        rows.extend(data.get("records",[]))
        for speaker in data.get("speakers",[]):
            for record in speaker.get("records",[]):item=dict(record);item.setdefault("speaker",speaker.get("speaker"));rows.append(item)
    return list({r.get("id",str(i)):r for i,r in enumerate(rows)}.values())
def search_local(query,k=6):
    store,count=get_store()
    if not store:return [],count
    try:return store.as_retriever(search_kwargs={"k":k}).invoke(query),count
    except Exception:return [],count
def search_teachers(query,k=5):
    terms=[x.lower() for x in re.findall(r"[A-Za-zÀ-ÿ0-9]+",query) if len(x)>2]; scored=[]
    for r in get_practitioners():
        if r.get("rag_eligible") is False:continue
        text=json.dumps(r,ensure_ascii=False).lower();score=sum(1 for t in terms if t in text)+(2 if r.get("exact_answer_eligible") else 0)
        if score:scored.append((score,r))
    scored.sort(key=lambda x:x[0],reverse=True);return [r for _,r in scored[:k]]
def zai_key():
    try:return st.secrets.get("ZAI_API_KEY","")
    except Exception:return ""
def tavily_key():
    try:return st.secrets.get("TAVILY_API_KEY","")
    except Exception:return ""
def effective_mode(requested):
    if requested=="Offline":return "Offline"
    if requested=="Deep Research":return "Deep Research" if tavily_key() and zai_key() else ("Trusted Library" if zai_key() else "Offline")
    return "Trusted Library"
def sanitise_question(text):
    text=re.sub(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b","",text)
    text=re.sub(r"\b(?:19|20)\d{2}\b","",text)
    text=re.sub(r"\b\d{1,2}:\d{2}\b","",text)
    text=re.sub(r"\s+"," ",text).strip()
    return text[:320]
def safe_web_query(question,personal=None):
    q=sanitise_question(question)
    if personal:q+=" "+" ".join([personal["timing"]["mahadasha"]+" planetary period",personal["timing"]["antardasha"]+" sub-period",personal["atmakaraka"]+" Vedic astrology significator"])
    return q[:380]
def web_domains_for(question):
    q=question.lower()
    if any(x in q for x in ["health","medical","ayurveda","sleep","stress","anxiety","yoga","meditation","dosha","digestion"]):return ["who.int","nccih.nih.gov","ayush.gov.in","ccras.nic.in","pubmed.ncbi.nlm.nih.gov"]
    return []
def search_web(question,personal=None,max_results=5):
    if not tavily_key():return [],"Tavily key unavailable"
    payload={"query":safe_web_query(question,personal),"search_depth":"advanced","topic":"general","max_results":max_results,"chunks_per_source":2,"include_answer":False,"include_raw_content":False,"safe_search":True}
    domains=web_domains_for(question)
    if domains:payload["include_domains"]=domains
    req=urllib.request.Request("https://api.tavily.com/search",data=json.dumps(payload).encode(),headers={"Authorization":f"Bearer {tavily_key()}","Content-Type":"application/json"},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=35) as response:data=json.loads(response.read().decode())
    except Exception as e:return [],f"Web research failed: {type(e).__name__}"
    results=[{"title":x.get("title") or "Web source","url":x.get("url") or "","content":x.get("content") or "","score":x.get("score")} for x in data.get("results",[])[:max_results]]
    return results,None
def get_llm(max_tokens=2600):return ChatOpenAI(model="glm-4.5-flash",openai_api_key=zai_key(),openai_api_base="https://api.z.ai/api/paas/v4",temperature=.35,max_tokens=max_tokens,extra_body={"thinking":{"type":"disabled"}})
def _trim(text,words):
    a=(text or "").split();return " ".join(a[:words])+("…" if len(a)>words else "")
def dedupe_docs(docs,limit=5):
    out=[];seen=set()
    for d in docs:
        m=d.metadata or {};key=(m.get("book") or m.get("source"),m.get("pdf_page"),m.get("chunk_id"))
        if key in seen:continue
        seen.add(key);out.append(d)
        if len(out)>=limit:break
    return out
def dedupe_teachers(rows,limit=4):
    out=[];seen=set()
    for r in rows:
        key=(r.get("speaker"),r.get("topic") or r.get("title") or r.get("video_title"))
        if key in seen:continue
        seen.add(key);out.append(r)
        if len(out)>=limit:break
    return out
def evidence_context(docs,teachers):
    out=[]
    for i,d in enumerate(dedupe_docs(docs),1):
        m=d.metadata or {};out.append(f"[C{i}] {m.get('book') or m.get('source','Unknown')} | page {m.get('pdf_page','Needs Verification')}\n{_trim(d.page_content,260)}")
    for i,r in enumerate(dedupe_teachers(teachers),1):out.append(f"[P{i}] {r.get('speaker') or 'Needs Verification'} | {r.get('topic') or r.get('title') or r.get('video_title','Indexed teaching')}\n{_trim(r.get('summary') or r.get('explanation_text',''),180)}")
    return "\n\n".join(out)
def web_context(rows):return "\n\n".join(f"[W{i}] {x['title']} | {x['url']}\n{_trim(x['content'],180)}" for i,x in enumerate(rows,1))
def local_answer(question,docs,teachers,personal=None,depth="Simple"):
    docs=dedupe_docs(docs,3);teachers=dedupe_teachers(teachers,2);parts=[]
    if personal:parts.append(f"**Personal context:** {personal['timing']['mahadasha']} major period, {personal['timing']['antardasha']} sub-period and {personal['atmakaraka']} as a core developmental planet.")
    if teachers:
        text=teachers[0].get("summary") or teachers[0].get("explanation_text")
        if text:parts.append(_trim(text,100 if depth=="Simple" else 180))
    if docs:parts.append("**Trusted library:** "+_trim(" ".join(docs[0].page_content.split()),100 if depth=="Simple" else 180))
    if not parts:return "I could not find enough verified material for this question. **Needs Verification.**"
    parts.append("**Practical note:** use this as traditional or reflective guidance. Gemstones, herbs, advanced mantra, fasting and medical claims require separate verification.")
    return "\n\n".join(parts)
def synthesize(question,docs,teachers,personal=None,depth="Simple",history=None,requested_mode="Trusted Library"):
    used=effective_mode(requested_mode);web=[];web_error=None
    if used=="Deep Research":web,web_error=search_web(question,personal,5)
    if used=="Offline" or not zai_key():return local_answer(question,docs,teachers,personal,depth),web,used,web_error
    limits={"Simple":(180,"100-180 words"),"Detailed":(550,"300-550 words"),"Advanced":(1100,"700-1100 words")};tokens,rule=limits[depth]
    prompt=f"""Answer in plain language. Question: {question}\nKnowledge mode: {used}. Length: {rule}.\nPersonal chart: {json.dumps(personal,default=str) if personal else 'not supplied'}\nRecent conversation: {json.dumps((history or [])[-6:],ensure_ascii=False)}\nTrusted evidence:\n{evidence_context(docs,teachers)}\nWeb evidence:\n{web_context(web)}\nRules: calculated facts override prose; synthesise, do not dump passages; distinguish trusted/classical, practitioner, web and Needs Verification; explain Sanskrit; never invent remedies, gemstone suitability, universal chakra mappings or medical claims; end with a practical takeaway."""
    try:return get_llm(max(1000,tokens*2)).invoke(prompt).content,web,used,web_error
    except Exception:return local_answer(question,docs,teachers,personal,depth),web,"Offline fallback",web_error or "Z.ai synthesis failed"

def profile_signature(cfg):return (cfg["dob"].isoformat(),cfg["tob"].isoformat(),round(cfg["lat"],6),round(cfg["lon"],6),round(cfg["tz"],2))
def reset_personal_results():
    for key in ["chart","chart_signature","personal_report","personal_layers","personal_web","remedy_answer","remedy_sources"]:st.session_state.pop(key,None)
def _location_change():
    preset=st.session_state.location_preset
    if preset!="Custom / other":st.session_state.birth_lat,st.session_state.birth_lon,st.session_state.birth_tz=map(float,LOCATION_PRESETS[preset])
    st.session_state.profile_confirmed=False;reset_personal_results()
def build_date_inputs():
    default=st.session_state.get("profile_dob",date(1983,12,27));c1,c2,c3=st.columns([1,1.5,1.2])
    day=c1.number_input("Day",1,31,int(default.day),1,key="dob_day")
    month=c2.selectbox("Month",list(range(1,13)),index=int(default.month)-1,format_func=lambda x:datetime(2000,x,1).strftime("%B"),key="dob_month")
    year=c3.number_input("Year",1900,2050,int(default.year),1,key="dob_year")
    try:return date(int(year),int(month),int(day)),None
    except ValueError as e:return None,str(e)
def profile_panel():
    with st.sidebar:
        st.markdown("### Your Profile")
        name=st.text_input("Name",st.session_state.get("profile_name",""),placeholder="Your name")
        st.markdown("#### Date of birth")
        dob,date_error=build_date_inputs()
        if date_error:st.error("Invalid birth date. Check the day, month and leap year.")
        tob=st.time_input("Exact birth time",st.session_state.get("profile_tob",datetime.strptime("00:35","%H:%M").time()))
        if "location_preset" not in st.session_state:st.session_state.location_preset=st.session_state.get("profile_preset","Bharwain / Chintpurni, Himachal Pradesh")
        if "birth_lat" not in st.session_state:
            initial=LOCATION_PRESETS[st.session_state.location_preset];st.session_state.birth_lat=float(initial[0]);st.session_state.birth_lon=float(initial[1]);st.session_state.birth_tz=float(initial[2])
        preset=st.selectbox("Birthplace",list(LOCATION_PRESETS),key="location_preset",on_change=_location_change)
        with st.expander("Confirm birth location settings",expanded=preset=="Custom / other"):
            st.caption("Presets are approximate. Historical daylight-saving and timezone rules must be verified for the birth date.")
            lat=st.number_input("Latitude",-90.0,90.0,key="birth_lat",format="%.4f",on_change=lambda:reset_personal_results())
            lon=st.number_input("Longitude",-180.0,180.0,key="birth_lon",format="%.4f",on_change=lambda:reset_personal_results())
            tz=st.number_input("UTC offset at birth",-12.0,14.0,key="birth_tz",step=.25,on_change=lambda:reset_personal_results())
            confirmed=st.checkbox("I confirm the birth time, coordinates and UTC offset",key="profile_confirmed")
        requested=st.radio("Knowledge source",KNOWLEDGE_MODES,index=KNOWLEDGE_MODES.index(st.session_state.get("knowledge_mode","Deep Research")))
        st.caption({"Trusted Library":"Chart + 21-source library + selected teachers.","Deep Research":"Trusted Library + live web research + Z.ai synthesis.","Offline":"Local calculations and library only; no internet calls."}[requested])
        active=effective_mode(requested)
        if active!=requested:st.warning(f"{requested} is unavailable. Active mode: {active}.")
        depth=st.select_slider("Answer detail",DEPTHS,value=st.session_state.get("depth","Simple"));advanced=st.toggle("Show advanced Vedic details",value=st.session_state.get("advanced",False))
        cfg={"name":name or "Seeker","dob":dob,"tob":tob,"place":preset,"lat":lat,"lon":lon,"tz":tz,"confirmed":bool(confirmed and dob),"date_error":date_error,"knowledge_mode":requested,"effective_mode":active,"depth":depth,"advanced":advanced}
        current_sig=profile_signature(cfg) if dob else None
        if st.session_state.get("confirmed_signature")!=current_sig:cfg["confirmed"]=False
        if st.button("Save and confirm profile",use_container_width=True,disabled=bool(date_error)):
            st.session_state.update(profile_name=name,profile_dob=dob,profile_tob=tob,profile_preset=preset,profile_lat=lat,profile_lon=lon,profile_tz=tz,knowledge_mode=requested,depth=depth,advanced=advanced,profile_confirmed=True,confirmed_signature=current_sig)
            reset_personal_results();st.success("Profile confirmed for this session");st.rerun()
        return cfg
def ensure_chart(cfg,force=False):
    if not cfg.get("confirmed") or not cfg.get("dob"):return None
    sig=profile_signature(cfg)
    if force or st.session_state.get("chart_signature")!=sig:st.session_state.chart=calculate_chart(cfg["dob"],cfg["tob"],cfg["lat"],cfg["lon"],cfg["tz"]);st.session_state.chart_signature=sig
    return st.session_state.chart

def personal_fact_summary(c):
    return {"ascendant":c["ascendant"]["sign"],"ascendant_degree":round(c["ascendant"]["degree"],2),"atmakaraka":c["atmakaraka"],"timing":c["timing"],"planets":{n:{"sign":p["sign"],"degree":round(p["degree"],2),"house":p["house"],"nakshatra":p["nakshatra"],"pada":p["pada"],"condition":p["condition"],"rules_houses":p["rules_houses"]} for n,p in c["planets"].items()},"conjunctions":c["conjunctions"],"aspects":c["aspects"]}
def retrieve_layers(c):
    f=personal_fact_summary(c);t=c["timing"];ak=c["atmakaraka"]
    queries={"jyotish":f"{f['ascendant']} ascendant {ak} Atmakaraka {t['mahadasha']} Mahadasha {t['antardasha']} Antardasha lordship nakshatra","ayurveda":f"Ayurveda routine sleep digestion agni mental steadiness {ak}","mantra":f"{ak} {t['mahadasha']} {t['antardasha']} mantra japa stotra graha remedy","yoga":f"yoga meditation grounding focus balance {ak}","remedies":f"{ak} {t['mahadasha']} {t['antardasha']} upaya dana behaviour gemstone strengthen pacify","chakra":f"{ak} planet chakra subtle body correspondence"}
    return f,{k:(search_local(q,6)[0],search_teachers(q,5)) for k,q in queries.items()}
def deep_report(c,depth,requested_mode):
    facts,layers=retrieve_layers(c);used=effective_mode(requested_mode);web=[];web_errors=[]
    if used=="Deep Research":
        for q in ["current evidence yoga meditation stress sleep wellbeing","Ayurveda daily routine sleep digestion mental steadiness evidence safety","traditional medicine safety evidence person centred"]:
            rows,err=search_web(q,None,3);web.extend(rows)
            if err:web_errors.append(err)
    if used=="Offline" or not zai_key():return facts,layers,None,web,used,web_errors
    lengths={"Simple":"650-900 words","Detailed":"1100-1600 words","Advanced":"1700-2200 words"};tokens={"Simple":2400,"Detailed":3800,"Advanced":5200}[depth]
    contexts=[]
    for k,(docs,teachers) in layers.items():contexts.append(f"## {k.upper()}\n{evidence_context(docs,teachers)}")
    prompt=f"""Create an integrated personal Ancient Wisdom report of {lengths[depth]}.\nLOCKED FACTS:\n{json.dumps(facts,default=str)}\nTRUSTED RETRIEVAL:\n{chr(10).join(contexts)}\nWEB EVIDENCE:\n{web_context(web)}\nRequired sections: Executive synthesis; Personal Jyotish; Current timing; Ayurveda and mind-body without diagnosing Prakriti/Vikriti from astrology; Chakra perspectives showing disagreements; Mantra and spiritual practice; 3-5 ranked remedies with purpose, chart reason, source basis, application and guidance level; Gemstone assessment; Three priorities now; Evidence map. Calculated facts override prose. Never invent quotations, mantra counts, gemstone suitability, universal chakra mappings or medical outcomes."""
    try:return facts,layers,get_llm(tokens).invoke(prompt).content,web,used,web_errors
    except Exception:return facts,layers,None,web,"Offline fallback",web_errors+["Z.ai synthesis failed"]

def navigate(page,question=None):st.session_state.page=page;st.session_state.pending_question=question if question else st.session_state.get("pending_question");st.rerun()
def source_list(docs,teachers):
    with st.expander(f"Sources · {len(dedupe_docs(docs))} classical/official · {len(dedupe_teachers(teachers))} practitioner"):
        for d in dedupe_docs(docs):
            m=d.metadata or {};st.markdown(f"- **{m.get('book') or m.get('source','Unknown')}** · PDF page {m.get('pdf_page','Needs Verification')}")
        for r in dedupe_teachers(teachers):st.markdown(f"- **{r.get('speaker') or 'Needs Verification'}** · {r.get('topic') or r.get('title') or r.get('video_title','Indexed teaching')}")
def web_list(rows,error=None):
    if rows:
        with st.expander(f"Live web research · {len(rows)} sources"):
            for r in rows:st.markdown(f"- [{r['title']}]({r['url']})")
    if error:st.caption(error)

def home_page(cfg):
    st.markdown("## How can I help you today?")
    with st.form("home_question",clear_on_submit=True):
        q=st.text_input("Ask anything",placeholder="What should I focus on now? What does Saturn mean? Which mantra may help focus?",label_visibility="collapsed")
        submitted=st.form_submit_button("Ask Ancient Wisdom",type="primary",use_container_width=True)
    if submitted and q.strip():navigate("Ask",q.strip())
    st.caption("Ask in ordinary language. Once a personal chart is generated, the same question automatically uses the chart as context.")
    cols=st.columns(3);cards=[("🔮 My Personal Reading","Build a deep synthesis across Jyotish, timing, Ayurveda, yoga, mantra and remedies.","Build My Reading","My Reading"),("🪷 My Remedies","See practical priorities, low-risk practices and carefully qualified traditional options.","View My Remedies","My Remedies"),("📚 Explore Knowledge","Search the 21-source library, topics and indexed teachers.","Explore Knowledge","Explore")]
    for i,(title,desc,label,page) in enumerate(cards):
        with cols[i]:
            st.markdown(f"<div class='choice'><h3>{title}</h3><p>{desc}</p></div>",unsafe_allow_html=True)
            if st.button(label,key=f"home_{i}",use_container_width=True):navigate(page)
def ask_page(cfg):
    st.markdown("## Ask Ancient Wisdom");st.caption("Ask in ordinary language. Your confirmed chart is used automatically once generated.")
    if "chat" not in st.session_state:st.session_state.chat=[]
    for item in st.session_state.chat:
        with st.chat_message(item["role"]):st.markdown(item["content"])
    question=st.session_state.pop("pending_question",None) or st.chat_input("What's on your mind?")
    if question:
        st.session_state.chat.append({"role":"user","content":question});personal=st.session_state.get("chart");search_q=question
        if personal:search_q+=f" {personal['timing']['mahadasha']} Mahadasha {personal['timing']['antardasha']} Antardasha {personal['atmakaraka']} Atmakaraka"
        docs,_=search_local(search_q,7);teachers=search_teachers(search_q,6);ans,web,used,error=synthesize(question,docs,teachers,personal,cfg["depth"],st.session_state.chat,cfg["knowledge_mode"])
        st.session_state.chat.append({"role":"assistant","content":ans});st.session_state.last_sources=(docs,teachers);st.session_state.last_web=web;st.session_state.last_web_error=error;st.rerun()
    if st.session_state.get("last_sources"):source_list(*st.session_state.last_sources)
    web_list(st.session_state.get("last_web",[]),st.session_state.get("last_web_error"))
    if st.session_state.chat and st.button("Clear conversation"):
        for k in ["chat","last_sources","last_web","last_web_error"]:st.session_state.pop(k,None)
        st.rerun()
def reading_page(cfg):
    st.markdown("## My Personal Reading")
    if not cfg["confirmed"]:st.warning("Save and confirm the birth date, exact time, coordinates and UTC offset in Your Profile.")
    if st.button("Generate Full Personal Synthesis",type="primary",use_container_width=True,disabled=not cfg["confirmed"]):
        c=ensure_chart(cfg,True);facts,layers,report,web,used,errors=deep_report(c,cfg["depth"],cfg["knowledge_mode"]);st.session_state.update(personal_facts=facts,personal_layers=layers,personal_report=report,personal_web=web,personal_mode=used,personal_errors=errors)
    if "chart" not in st.session_state:return
    c=st.session_state.chart;t=c["timing"];a,b,d,e=st.columns(4);a.metric("How you approach life",c["ascendant"]["sign"],"Ascendant");b.metric("Emotional pattern",f"{c['planets']['Moon']['nakshatra']} · quarter {c['planets']['Moon']['pada']}","Nakshatra");d.metric("Major life period",t["mahadasha"],f"to {t['md_end']}");e.metric("Current sub-period",t["antardasha"],f"to {t['ad_end']}")
    st.markdown(f"### Core developmental theme: {c['atmakaraka']}");st.write(f"The chart gives special developmental importance to {PLAIN[c['atmakaraka']] }.")
    if st.session_state.get("personal_report"):st.markdown(st.session_state.personal_report)
    elif st.session_state.get("personal_layers"):
        st.info("Showing local retrieval layers because enhanced synthesis was unavailable.")
        for key,(docs,teachers) in st.session_state.personal_layers.items():
            with st.expander(key.title(),expanded=key in ("jyotish","remedies")):
                if teachers:st.write(_trim(teachers[0].get("summary") or teachers[0].get("explanation_text"),140))
                if docs:st.write(_trim(docs[0].page_content,160))
    web_list(st.session_state.get("personal_web",[]),"; ".join(st.session_state.get("personal_errors",[])) or None)
    if cfg["advanced"]:
        rows=[{"Planet":n,"Sign":p["sign"],"Degree":fmt_deg(p["degree"]),"House":p["house"],"Nakshatra":p["nakshatra"],"Pada":p["pada"],"Condition":"; ".join(p["condition"]),"Rules houses":", ".join(map(str,p["rules_houses"])) or "—"} for n,p in c["planets"].items()];st.dataframe(rows,use_container_width=True,hide_index=True)
def remedies_page(cfg):
    st.markdown("## My Remedies")
    if "chart" not in st.session_state:st.info("Generate My Personal Reading first.");return
    c=st.session_state.chart;t=c["timing"];q=f"personal remedies strengthen pacify {t['mahadasha']} Mahadasha {t['antardasha']} Antardasha {c['atmakaraka']} Atmakaraka mantra dana yoga Ayurveda gemstone";docs,_=search_local(q,10);teachers=search_teachers(q,10);web=[];error=None
    if st.button("Build Detailed Remedy Plan",type="primary",use_container_width=True):
        if effective_mode(cfg["knowledge_mode"])=="Deep Research":web,error=search_web("traditional remedies meditation yoga Ayurveda gemstone safety",c,5)
        prompt=f"Build a structured chart-specific remedy plan from {json.dumps(personal_fact_summary(c),default=str)} and {evidence_context(docs,teachers)} and web evidence {web_context(web)}. Rank 3-5 remedies; state purpose, chart reason, source basis, application and guidance level. Separate strengthen from pacify. Never invent mantra counts, medical effects or gemstone suitability."
        try:st.session_state.remedy_answer=get_llm(3000).invoke(prompt).content if zai_key() else local_answer(q,docs,teachers,c,"Detailed")
        except Exception:st.session_state.remedy_answer=local_answer(q,docs,teachers,c,"Detailed")
        st.session_state.remedy_sources=(docs,teachers);st.session_state.remedy_web=web;st.session_state.remedy_error=error
    if st.session_state.get("remedy_answer"):st.markdown(st.session_state.remedy_answer)
    if st.session_state.get("remedy_sources"):source_list(*st.session_state.remedy_sources)
    web_list(st.session_state.get("remedy_web",[]),st.session_state.get("remedy_error"))
    st.warning("Gemstones, herbs, fasting, advanced pranayama and Bija/Tantric practices require verification or qualified guidance.")
def explore_page(cfg):
    st.markdown("## Explore Ancient Wisdom");t1,t2,t3=st.tabs(["Topics","Wisdom Library","Teachers"])
    with t1:
        topic=st.selectbox("Choose a topic",["Planets","Life periods","Chakras","Meditation","Mantras","Ayurveda","Yoga","Gemstones","Remedies","Nakshatras"]);q=st.text_input("What would you like to know?")
        if st.button("Explore Topic",disabled=not q,use_container_width=True):
            docs,_=search_local(f"{topic} {q}",7);teachers=search_teachers(f"{topic} {q}",6);ans,web,used,error=synthesize(q,docs,teachers,None,cfg["depth"],None,cfg["knowledge_mode"]);st.session_state.update(explore_answer=ans,explore_sources=(docs,teachers),explore_web=web,explore_error=error)
        if st.session_state.get("explore_answer"):st.markdown(st.session_state.explore_answer);source_list(*st.session_state.explore_sources);web_list(st.session_state.get("explore_web",[]),st.session_state.get("explore_error"))
    with t2:
        _,count=get_store();st.metric("Indexed passages",f"{count:,}");q=st.text_input("Search the 21-source library",key="library_query")
        if q:
            for d in search_local(q,6)[0]:
                m=d.metadata or {}
                with st.expander(f"{m.get('book') or m.get('source','Unknown')} · page {m.get('pdf_page','Needs Verification')}"):st.write(_trim(d.page_content,260))
    with t3:
        rows=get_practitioners();teachers=sorted({r.get("speaker") for r in rows if r.get("speaker")});teacher=st.selectbox("Choose a teacher",teachers) if teachers else None
        if teacher:
            for r in [x for x in rows if x.get("speaker")==teacher][:30]:
                with st.expander(r.get("topic") or r.get("title") or r.get("video_title") or "Indexed teaching"):st.write(r.get("summary") or r.get("explanation_text") or "Needs Verification")

def main():
    cfg=profile_panel();_,count=get_store();teacher_count=len(get_practitioners())
    st.markdown("<div class='hero'><div class='eyebrow'>PERSONAL WISDOM & REMEDY ENGINE</div><h1>Ancient Wisdom Synthesis</h1><p class='subtitle'>Personal guidance from calculated Vedic astrology and a searchable library spanning Jyotish, Ayurveda, yoga, mantra, remedies and practitioner perspectives.</p></div>",unsafe_allow_html=True)
    if "page" not in st.session_state:st.session_state.page="Home"
    chosen=st.radio("Navigation",PAGES,horizontal=True,index=PAGES.index(st.session_state.page),label_visibility="collapsed")
    if chosen!=st.session_state.page:st.session_state.page=chosen;st.rerun()
    with st.expander("Library & system status"):
        st.write(f"Ancient Wisdom library: **{count:,} passages**");st.write(f"Practitioner knowledge: **{teacher_count} records**");st.write(f"Selected mode: **{cfg['knowledge_mode']}** · Active mode: **{cfg['effective_mode']}**")
    st.divider();{"Home":home_page,"Ask":ask_page,"My Reading":reading_page,"My Remedies":remedies_page,"Explore":explore_page}[st.session_state.page](cfg)

if __name__=="__main__":main()
