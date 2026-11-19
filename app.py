import json
import os
from datetime import date, datetime, timedelta, timezone

import chromadb
import streamlit as st
import swisseph as swe
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_openai import ChatOpenAI

st.set_page_config(page_title="Ancient Wisdom Synthesis", page_icon="🕉️", layout="wide", initial_sidebar_state="collapsed")

APP_VERSION = "AWS v1.14 Concise Conversational Search"
EMBEDDING_MODEL = "paraphrase-MiniLM-L3-v2"
COLLECTION_NAME = "ancient_wisdom"

st.markdown("""
<style>
.stApp{background:radial-gradient(circle at 16% 0%,#202653 0,#11152d 36%,#090b18 100%);color:#f5f0e8}
.block-container{max-width:1480px;padding-top:1.2rem;padding-bottom:4rem}
[data-testid="stSidebar"]{background:#11142b;border-right:1px solid #303558}
[data-testid="stMetric"]{background:linear-gradient(145deg,rgba(31,36,70,.97),rgba(19,22,45,.97));border:1px solid #3a3f68;border-radius:18px;padding:16px;box-shadow:0 12px 30px rgba(0,0,0,.22)}
[data-testid="stMetricLabel"]{color:#aaa6b6!important}[data-testid="stMetricValue"]{color:#e2c45f!important}
[data-testid="stExpander"]{background:rgba(18,22,45,.82);border:1px solid #343961;border-radius:14px}
[data-testid="stDataFrame"]{border:1px solid #343961;border-radius:14px;overflow:hidden}
.stButton>button{background:linear-gradient(135deg,#5d4ba0,#8d68d8);color:white;border:1px solid #9d83df;border-radius:25px;font-weight:650;min-height:2.75rem;box-shadow:0 8px 18px rgba(72,49,128,.28)}
.stButton>button:hover{border-color:#e2c45f;color:white;transform:translateY(-1px)}
.stTabs [data-baseweb="tab-list"]{gap:7px;flex-wrap:wrap}.stTabs [data-baseweb="tab"]{background:#171a36;border:1px solid #30355a;border-radius:14px;padding:10px 18px}
h1,h2,h3,h4{color:#f6f0e7;letter-spacing:.01em}p,li,.stMarkdown{color:#d6d0c8}
.hero{padding:26px 30px;border:1px solid #41466f;border-radius:24px;background:linear-gradient(135deg,rgba(37,43,84,.97),rgba(17,20,43,.94));box-shadow:0 20px 55px rgba(0,0,0,.28);margin-bottom:18px}
.eyebrow{color:#e2c45f;font-size:.8rem;font-weight:760;letter-spacing:.17em;text-transform:uppercase}
.subtitle{color:#bbb5c8;font-size:1.05rem;margin:0}.muted{color:#9c97aa}.badge{display:inline-block;padding:4px 9px;margin:2px;border-radius:999px;background:#242949;border:1px solid #41466f;color:#d9d3e1;font-size:.78rem}
.choice{padding:19px;border:1px solid #3a3f67;border-radius:18px;background:linear-gradient(145deg,rgba(28,32,63,.95),rgba(17,20,42,.95));min-height:155px}
</style>
""", unsafe_allow_html=True)

SIGNS=["Aries","Taurus","Gemini","Cancer","Leo","Virgo","Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
NAKSHATRAS=["Ashwini","Bharani","Krittika","Rohini","Mrigashirsha","Ardra","Punarvasu","Pushya","Ashlesha","Magha","Purva Phalguni","Uttara Phalguni","Hasta","Chitra","Swati","Vishakha","Anuradha","Jyeshtha","Mula","Purvashadha","Uttarashadha","Shravana","Dhanishta","Shatabhisha","Purva Bhadrapada","Uttara Bhadrapada","Revati"]
NAK_LORDS=["Ketu","Venus","Sun","Moon","Mars","Rahu","Jupiter","Saturn","Mercury"]
NAK_SIZE=360/27; PADA_SIZE=NAK_SIZE/4; FLAGS=swe.FLG_SWIEPH|swe.FLG_SIDEREAL
DASHA_SEQ=["Ketu","Venus","Sun","Moon","Mars","Rahu","Jupiter","Saturn","Mercury"]
DASHA_YEARS={"Ketu":7,"Venus":20,"Sun":6,"Moon":10,"Mars":7,"Rahu":18,"Jupiter":16,"Saturn":19,"Mercury":17}
DAYS_PER_YEAR=365.2425
SIGN_LORDS={"Aries":"Mars","Taurus":"Venus","Gemini":"Mercury","Cancer":"Moon","Leo":"Sun","Virgo":"Mercury","Libra":"Venus","Scorpio":"Mars","Sagittarius":"Jupiter","Capricorn":"Saturn","Aquarius":"Saturn","Pisces":"Jupiter"}
OWN={"Sun":["Leo"],"Moon":["Cancer"],"Mars":["Aries","Scorpio"],"Mercury":["Gemini","Virgo"],"Jupiter":["Sagittarius","Pisces"],"Venus":["Taurus","Libra"],"Saturn":["Capricorn","Aquarius"]}
EXALT={"Sun":"Aries","Moon":"Taurus","Mars":"Capricorn","Mercury":"Virgo","Jupiter":"Cancer","Venus":"Pisces","Saturn":"Libra"}
DEBIL={"Sun":"Libra","Moon":"Scorpio","Mars":"Cancer","Mercury":"Pisces","Jupiter":"Capricorn","Venus":"Virgo","Saturn":"Aries"}
COMBUST={"Moon":12,"Mars":17,"Mercury":14,"Jupiter":11,"Venus":10,"Saturn":15}
ASPECTS={"Sun":[7],"Moon":[7],"Mercury":[7],"Venus":[7],"Mars":[4,7,8],"Jupiter":[5,7,9],"Saturn":[3,7,10]}
GEMS={"Sun":"Ruby","Moon":"Pearl","Mars":"Red Coral","Mercury":"Emerald","Jupiter":"Yellow Sapphire","Venus":"Diamond / White Sapphire","Saturn":"Blue Sapphire","Rahu":"Hessonite (Gomed)","Ketu":"Cat's Eye"}
PLAIN={"Sun":"identity, vitality and leadership","Moon":"mind, emotions and inner security","Mars":"action, courage and directed energy","Mercury":"thinking, communication and adaptability","Jupiter":"growth, wisdom and judgement","Venus":"relationships, harmony and creativity","Saturn":"discipline, responsibility and endurance","Rahu":"intense desire, experimentation and unfamiliar territory","Ketu":"detachment, insight and inward focus"}
CORRESP={"Sun":{"dosha":"Pitta","chakra":"Solar plexus / Manipura"},"Moon":{"dosha":"Kapha, sometimes Vata context","chakra":"Heart / Anahata in some frameworks"},"Mars":{"dosha":"Pitta","chakra":"Root or solar plexus, depending on lineage"},"Mercury":{"dosha":"Vata or variable","chakra":"Throat / Vishuddha in some frameworks"},"Jupiter":{"dosha":"Kapha","chakra":"Ajna or higher centres in some frameworks"},"Venus":{"dosha":"Kapha","chakra":"Sacral / Svadhisthana in some frameworks"},"Saturn":{"dosha":"Vata","chakra":"Root / Muladhara in some frameworks"},"Rahu":{"dosha":"Vata or variable","chakra":"Lineage-dependent"},"Ketu":{"dosha":"Vata-Pitta or variable","chakra":"Ajna or crown in some frameworks"}}


def sign_info(lon):
    lon%=360; i=int(lon/30); return {"longitude":lon,"sign":SIGNS[i],"degree":lon%30,"sign_index":i}
def nak_info(lon):
    lon%=360; i=min(int(lon/NAK_SIZE),26); within=lon-i*NAK_SIZE
    return {"nakshatra":NAKSHATRAS[i],"pada":min(int(within/PADA_SIZE)+1,4),"lord":NAK_LORDS[i%9],"within":within}
def fmt_deg(v):
    d=int(v); m=int((v-d)*60); s=round((((v-d)*60)-m)*60)
    if s==60:s=0;m+=1
    if m==60:m=0;d+=1
    return f"{d:02d}° {m:02d}′ {s:02d}″"
def angle(a,b):
    d=abs((a-b)%360); return min(d,360-d)
def body(jd,pid):
    x,_=swe.calc_ut(jd,pid,FLAGS); o=sign_info(x[0]); o.update(nak_info(x[0])); o["retrograde"]=x[3]<0; return o
def add_years(dt,y): return dt+timedelta(days=y*DAYS_PER_YEAR)

def dasha(moon_lon,birth,now):
    n=nak_info(moon_lon); lord=n["lord"]; elapsed=DASHA_YEARS[lord]*(n["within"]/NAK_SIZE); cur=add_years(birth,-elapsed); idx=DASHA_SEQ.index(lord); mds=[]
    for _ in range(2):
        for off in range(9):
            l=DASHA_SEQ[(idx+off)%9]; end=add_years(cur,DASHA_YEARS[l]); mds.append({"lord":l,"start":cur,"end":end}); cur=end
    md=next(x for x in mds if x["start"]<=now<x["end"]); i=DASHA_SEQ.index(md["lord"]); cur=md["start"]; ads=[]
    for off in range(9):
        l=DASHA_SEQ[(i+off)%9]; end=add_years(cur,DASHA_YEARS[md["lord"]]*DASHA_YEARS[l]/120); ads.append({"lord":l,"start":cur,"end":end}); cur=end
    ad=next(x for x in ads if x["start"]<=now<x["end"])
    clean=lambda rows,key:[{key:x["lord"],"Start":x["start"].date().isoformat(),"End":x["end"].date().isoformat(),"Current":"Yes" if x in (md,ad) else ""} for x in rows]
    return {"mahadasha":md["lord"],"md_start":md["start"].date().isoformat(),"md_end":md["end"].date().isoformat(),"antardasha":ad["lord"],"ad_start":ad["start"].date().isoformat(),"ad_end":ad["end"].date().isoformat(),"md_timeline":clean(mds[:9],"Mahadasha"),"ad_timeline":clean(ads,"Antardasha")}

def chart(dob,tob,lat,lon,tz):
    swe.set_sid_mode(swe.SIDM_LAHIRI,0,0); hour=tob.hour+tob.minute/60+tob.second/3600; jd=swe.julday(dob.year,dob.month,dob.day,hour-tz,swe.GREG_CAL)
    _,ascmc=swe.houses_ex(jd,lat,lon,b"W",swe.FLG_SIDEREAL); asc=sign_info(ascmc[0]); asc.update(nak_info(ascmc[0]))
    ids={"Sun":swe.SUN,"Moon":swe.MOON,"Mars":swe.MARS,"Mercury":swe.MERCURY,"Jupiter":swe.JUPITER,"Venus":swe.VENUS,"Saturn":swe.SATURN,"Rahu":swe.MEAN_NODE}; ps={n:body(jd,i) for n,i in ids.items()}
    k=sign_info(ps["Rahu"]["longitude"]+180); k.update(nak_info(k["longitude"])); k["retrograde"]=True; ps["Ketu"]=k
    rules={n:[] for n in ["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn"]}
    for h in range(1,13): rules[SIGN_LORDS[SIGNS[(asc["sign_index"]+h-1)%12]]].append(h)
    for n,p in ps.items():
        p["house"]=((p["sign_index"]-asc["sign_index"])%12)+1; labels=[]
        if n in OWN and p["sign"] in OWN[n]: labels.append("Own sign")
        if n in EXALT and p["sign"]==EXALT[n]: labels.append("Exaltation sign")
        if n in DEBIL and p["sign"]==DEBIL[n]: labels.append("Debilitation sign")
        if p["retrograde"] and n not in ("Rahu","Ketu"): labels.append("Retrograde")
        if n in COMBUST and angle(p["longitude"],ps["Sun"]["longitude"])<=COMBUST[n]: labels.append("Combust")
        p["condition"]=labels or ["No major condition flagged"]; p["rules_houses"]=rules.get(n,[])
    conjunctions=[]; names=list(ps)
    for i,a in enumerate(names):
        for b in names[i+1:]:
            if ps[a]["sign_index"]==ps[b]["sign_index"]: conjunctions.append({"Planets":f"{a} + {b}","Sign":ps[a]["sign"],"House":ps[a]["house"],"Separation":round(angle(ps[a]["longitude"],ps[b]["longitude"]),2)})
    aspects=[]
    for n,offs in ASPECTS.items():
        for off in offs:
            target=((ps[n]["house"]+off-2)%12)+1; targets=[x for x,p in ps.items() if p["house"]==target and x!=n]
            aspects.append({"Planet":n,"Aspect":f"{off}th","From":ps[n]["house"],"To":target,"Target planets":", ".join(targets) or "—"})
    ak=max(["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn"],key=lambda n:ps[n]["degree"]); now=datetime.now(timezone.utc); birth=(datetime(dob.year,dob.month,dob.day,tob.hour,tob.minute,tob.second)-timedelta(hours=tz)).replace(tzinfo=timezone.utc); timing=dasha(ps["Moon"]["longitude"],birth,now)
    return {"ascendant":asc,"planets":ps,"atmakaraka":ak,"timing":timing,"conjunctions":conjunctions,"aspects":aspects,"ayanamsa":swe.get_ayanamsa_ut(jd)}

@st.cache_resource(show_spinner=False)
def embeddings(): return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
@st.cache_resource(show_spinner=False)
def ancient_store():
    path="chroma_db"; db=os.path.join(path,"chroma.sqlite3")
    if not os.path.isfile(db): return None,0
    client=chromadb.PersistentClient(path=path); names=[(c.name if hasattr(c,"name") else str(c)) for c in client.list_collections()]
    name=COLLECTION_NAME if COLLECTION_NAME in names else (names[0] if names else None)
    if not name:return None,0
    count=client.get_collection(name).count(); return Chroma(client=client,collection_name=name,embedding_function=embeddings()),count
@st.cache_data(show_spinner=False)
def practitioner_records():
    out=[]
    for fn in ["integrative_practitioner_knowledge_v1_2.json","additional_practitioner_talks_v1.json"]:
        if not os.path.isfile(fn):continue
        data=json.load(open(fn,encoding="utf-8"))
        out.extend(data.get("records",[]))
        for s in data.get("speakers",[]):
            for r in s.get("records",[]):
                x=dict(r); x.setdefault("speaker",s.get("speaker")); x.setdefault("tradition",s.get("tradition")); out.append(x)
    return list({r.get("id",str(i)):r for i,r in enumerate(out)}.values())

def search_classical(q,k=7):
    store,count=ancient_store()
    if not store:return [],count
    try:return store.as_retriever(search_kwargs={"k":k}).invoke(q),count
    except Exception:return [],count

def search_practitioners(q,k=8,teacher=None):
    terms=[x.lower() for x in q.replace("/"," ").split() if len(x)>2]; scored=[]
    for r in practitioner_records():
        if r.get("rag_eligible") is False:continue
        speaker=r.get("speaker") or "Needs Verification"; text=json.dumps(r,ensure_ascii=False).lower(); score=sum(1 for t in terms if t in text)
        if teacher and speaker.lower()==teacher.lower():score+=10
        if r.get("exact_answer_eligible"):score+=2
        if score: scored.append((score,r,speaker))
    scored.sort(key=lambda x:x[0],reverse=True)
    ans=[]
    for _,r,speaker in scored[:k]:
        x=dict(r); x["speaker"]=speaker; ans.append(x)
    return ans

def api_key():
    try:return st.secrets.get("ZAI_API_KEY","")
    except Exception:return ""
def llm(key):return ChatOpenAI(model="glm-4.5-flash",openai_api_key=key,openai_api_base="https://api.z.ai/api/paas/v4",temperature=.45,max_tokens=2400,extra_body={"thinking":{"type":"disabled"}})
def context(docs,prs):
    parts=[]
    for i,d in enumerate(docs,1):
        m=d.metadata or {}; parts.append(f"[C{i}] {m.get('book') or m.get('source','Unknown')} | PDF page {m.get('pdf_page','Needs Verification')}\n{d.page_content}")
    for i,r in enumerate(prs,1):parts.append(f"[P{i}] {r.get('speaker','Needs Verification')} | {r.get('topic') or r.get('title') or r.get('video_title','Indexed teaching')} | {r.get('verification_status','')}\n{r.get('summary') or r.get('explanation_text','')}")
    return "\n\n".join(parts)

def normalise_evidence(docs,prs,max_docs=5,max_prs=4):
    picked_docs=[]; seen=set()
    for d in docs:
        m=d.metadata or {}; key=(m.get("book") or m.get("source"),m.get("pdf_page"))
        if key in seen: continue
        seen.add(key); picked_docs.append(d)
        if len(picked_docs)>=max_docs: break
    picked_prs=[]; seen=set()
    for r in prs:
        speaker=r.get("speaker") or "Needs Verification"
        topic=r.get("topic") or r.get("title") or r.get("video_title") or "Indexed teaching"
        key=(speaker,topic)
        if key in seen: continue
        seen.add(key); x=dict(r); x["speaker"]=speaker; picked_prs.append(x)
        if len(picked_prs)>=max_prs: break
    return picked_docs,picked_prs

def local_short_answer(q,docs,prs,personal=None,depth="Simple"):
    docs,prs=normalise_evidence(docs,prs)
    if not docs and not prs:
        return "I could not find enough verified local material for that question. **Needs Verification.**"
    lines=[]
    if personal:
        t=personal["timing"]
        lines.append(f"**Personal context:** {t['mahadasha']} is your current major period and {t['antardasha']} the current sub-period.")
    if prs:
        summary=prs[0].get("summary") or prs[0].get("explanation_text") or ""
        if summary: lines.append(summary.strip())
    if docs:
        snippets=[]
        for d in docs[:2]:
            text=" ".join(d.page_content.split())
            if text: snippets.append(text[:260].rstrip()+("…" if len(text)>260 else ""))
        if snippets: lines.append("**From the local library:** "+" ".join(snippets))
    lines.append("**Bottom line:** use this as traditional or reflective guidance. Specific gemstones, herbs, fasting, medical claims or advanced mantra practices require verification.")
    return "\n\n".join(lines)

def answer(q,docs,prs,personal=None,level="Simple",history=None):
    docs,prs=normalise_evidence(docs,prs)
    key=api_key()
    if not key:
        return local_short_answer(q,docs,prs,personal,level)
    if level=="Simple":
        length_rule="80-140 words. Direct answer first. At most three short bullets. Do not name teachers unless asked or attribution is necessary. Do not quote passages."
    elif level=="Detailed":
        length_rule="180-300 words. Use Direct answer, Practical meaning and Caution. Mention traditions briefly; do not dump passages."
    else:
        length_rule="350-550 words. Include Vedic terminology, calculation logic where relevant, disagreements between traditions, and a compact source note."
    personal_text=json.dumps(personal,default=str) if personal else "No personal chart supplied."
    history_text=json.dumps((history or [])[-6:],ensure_ascii=False)
    ctx=context(docs,prs)
    prompt=(
        f"Answer this user question in plain language: {q}\n"
        f"Answer depth: {level}. {length_rule}\n"
        f"Personal chart context: {personal_text}\n"
        f"Recent conversation: {history_text}\n"
        f"Retrieved evidence:\n{ctx}\n\n"
        "Rules:\n"
        "- Synthesize; never dump raw retrieved passages.\n"
        "- Do not list practitioner names in Simple mode unless specifically asked or needed to distinguish a non-classical framework.\n"
        "- Translate every Vedic/Sanskrit term immediately into plain English.\n"
        "- Calculated chart facts are locked.\n"
        "- Separate traditional interpretation from modern evidence where relevant.\n"
        "- Do not invent remedies, universal chakra correspondences, mantra instructions, gemstone suitability, or medical claims.\n"
        "- If evidence is insufficient, say Needs Verification.\n"
        "- End Simple answers with one short practical takeaway, not a bibliography."
    )
    return llm(key).invoke(prompt).content

def profile_sidebar():
    with st.sidebar:
        st.markdown("### Your details")
        name=st.text_input("Name","Puneet"); dob=st.date_input("Date of birth",date(1983,12,27),min_value=date(1900,1,1),max_value=date.today()); tob=st.time_input("Time of birth",datetime.strptime("00:35","%H:%M").time()); lat=st.number_input("Birthplace latitude",-90.0,90.0,31.64,format="%.4f"); lon=st.number_input("Birthplace longitude",-180.0,180.0,76.13,format="%.4f"); tz=st.number_input("UTC offset",-12.0,14.0,5.5,.25)
        st.divider(); advanced=st.toggle("Show advanced Vedic detail",value=False)
        depth=st.select_slider("Answer detail",options=["Simple","Detailed","Advanced"],value="Simple",help="Simple gives a short direct answer. Detailed adds interpretation. Advanced includes technical Vedic logic and source distinctions.")
        with st.expander("Advanced settings"):
            ai=st.selectbox("AI assistance",["Automatic","Local only","Enhanced online"],index=0)
            st.caption("Automatic uses enhanced synthesis when configured and otherwise uses the local library.")
        return {"name":name or "Seeker","dob":dob,"tob":tob,"lat":lat,"lon":lon,"tz":tz,"advanced":advanced,"depth":depth,"ai":ai}

def source_panel(docs,prs):
    docs,prs=normalise_evidence(docs,prs)
    label=f"Sources · {len(docs)} classical/official · {len(prs)} practitioner"
    with st.expander(label,expanded=False):
        if docs:
            st.markdown("#### Classical / official")
            for d in docs:
                m=d.metadata or {}
                st.markdown(f"- **{m.get('book') or m.get('source','Unknown')}** · PDF page {m.get('pdf_page','Needs Verification')}")
        if prs:
            st.markdown("#### Practitioner interpretation")
            for r in prs:
                speaker=r.get("speaker") or "Needs Verification"
                topic=r.get("topic") or r.get("title") or r.get("video_title") or "Indexed teaching"
                st.markdown(f"- **{speaker}** · {topic}")
        st.caption("Use Explore if you want to read indexed passages or browse a teacher's records.")

def ensure_chart(cfg):
    if "chart" not in st.session_state:
        st.session_state.chart=chart(cfg["dob"],cfg["tob"],cfg["lat"],cfg["lon"],cfg["tz"])
    return st.session_state.chart

def home(cfg):
    st.markdown("## What would you like to do?")
    cols=st.columns(4)
    cards=[("🔮 Understand Me","See what is important in your chart and current life period."),("💬 Ask Anything","Ask ordinary questions about life, astrology, meditation, chakras or remedies."),("🪷 What Can I Do?","See source-grounded personal practices and cautions."),("📚 Explore","Browse planets, mantras, Ayurveda, books and teachers.")]
    for c,(title,desc) in zip(cols,cards):
        with c:st.markdown(f"<div class='choice'><h3>{title}</h3><p>{desc}</p></div>",unsafe_allow_html=True)
    st.markdown("### Try asking")
    st.markdown("<span class='badge'>Why am I restless?</span><span class='badge'>What is a mantra?</span><span class='badge'>Which gemstone suits me?</span><span class='badge'>What does Saturn mean?</span><span class='badge'>How can I improve focus?</span>",unsafe_allow_html=True)

def ask(cfg):
    st.markdown("## Ask Ancient Wisdom")
    st.caption("No Vedic knowledge required. Ask in normal language. Answers are short by default; open Sources only if you want the evidence.")
    st.markdown("<span class='badge'>Why am I feeling restless?</span><span class='badge'>What does Saturn mean?</span><span class='badge'>Can a mantra help focus?</span><span class='badge'>Is a gemstone suitable for me?</span>",unsafe_allow_html=True)
    if "chat" not in st.session_state:st.session_state.chat=[]
    for item in st.session_state.chat:
        with st.chat_message(item["role"]):st.markdown(item["content"])
    q=st.chat_input("What's on your mind?")
    if q:
        st.session_state.chat.append({"role":"user","content":q}); personal=st.session_state.get("chart"); search_q=q
        if personal:search_q+=f" {personal['timing']['mahadasha']} Mahadasha {personal['timing']['antardasha']} Antardasha {personal['atmakaraka']} Atmakaraka"
        docs,_=search_classical(search_q,7); prs=search_practitioners(search_q,8); level=cfg.get("depth","Simple"); result=answer(q,docs,prs,personal,level,st.session_state.chat)
        st.session_state.chat.append({"role":"assistant","content":result}); st.rerun()

def reading(cfg):
    st.markdown("## My Reading")
    if st.button("Generate my reading",type="primary",use_container_width=True):st.session_state.chart=chart(cfg["dob"],cfg["tob"],cfg["lat"],cfg["lon"],cfg["tz"])
    if "chart" not in st.session_state:return
    c=st.session_state.chart; t=c["timing"]; a,b,c1,d=st.columns(4); a.metric("Your rising pattern",c["ascendant"]["sign"],"Vedic term: Ascendant"); b.metric("Your Moon pattern",f"{c['planets']['Moon']['nakshatra']} · quarter {c['planets']['Moon']['pada']}","Vedic term: Nakshatra"); c1.metric("Major life period",t["mahadasha"],f"to {t['md_end']}"); d.metric("Current sub-period",t["antardasha"],f"to {t['ad_end']}")
    st.markdown(f"### Core developmental theme: {c['atmakaraka']}")
    st.write(f"In this chart, {c['atmakaraka']} carries particular developmental significance. In plain language, {PLAIN[c['atmakaraka']] } is a recurring area of growth.")
    q=f"Explain the current personal theme of {t['mahadasha']} major period, {t['antardasha']} sub-period and {c['atmakaraka']} core developmental planet for a beginner"
    docs,_=search_classical(q,8); prs=search_practitioners(q,8)
    if st.button("Explain what this means",use_container_width=True):st.session_state.reading_answer=answer(q,docs,prs,c,cfg.get("depth","Simple"))
    if st.session_state.get("reading_answer"):st.markdown(st.session_state.reading_answer);source_panel(docs,prs)
    if cfg["advanced"]:
        st.markdown("### Advanced Vedic detail")
        rows=[]
        for n,p in c["planets"].items():rows.append({"Planet":n,"Sign":p["sign"],"Degree":fmt_deg(p["degree"]),"House":p["house"],"Nakshatra":p["nakshatra"],"Pada":p["pada"],"Condition":"; ".join(p["condition"]),"Rules houses":", ".join(map(str,p["rules_houses"])) or "—"})
        st.dataframe(rows,use_container_width=True,hide_index=True)
        with st.expander("Mahadasha and Antardasha timelines"):st.dataframe(t["md_timeline"],use_container_width=True,hide_index=True);st.dataframe(t["ad_timeline"],use_container_width=True,hide_index=True)
        with st.expander("Conjunctions and classical aspects"):st.dataframe(c["conjunctions"],use_container_width=True,hide_index=True);st.dataframe(c["aspects"],use_container_width=True,hide_index=True)

def remedies(cfg):
    st.markdown("## What Can I Do?")
    st.caption("Personal practices are based on the calculated chart and retrieved sources, not generic planet-to-remedy tables.")
    c=ensure_chart(cfg); t=c["timing"]; st.markdown(f"### Current focus: {t['mahadasha']} major period · {t['antardasha']} sub-period · {c['atmakaraka']} developmental theme")
    q=f"safe low risk remedies and practical support for {t['mahadasha']} Mahadasha {t['antardasha']} Antardasha {c['atmakaraka']} Atmakaraka house {c['planets'][c['atmakaraka']]['house']}"
    docs,_=search_classical(q,6); prs=search_practitioners(q,10)
    if st.button("Build my personal action plan",type="primary",use_container_width=True):st.session_state.remedy_answer=answer(q,docs,prs,c,cfg.get("depth","Simple"))
    if st.session_state.get("remedy_answer"):st.markdown(st.session_state.remedy_answer);source_panel(docs,prs)
    st.warning("Gemstones, herbs, fasting, advanced pranayama and Bija/Tantric practices require verification or qualified guidance. A planet's traditional gemstone is not automatically suitable for a person.")

def explore(cfg):
    st.markdown("## Explore")
    t1,t2,t3=st.tabs(["Topics","Wisdom Library","Teachers"])
    with t1:
        topic=st.selectbox("Choose a topic",["Planets","Life periods","Chakras","Meditation","Mantras","Ayurveda","Yoga","Gemstones","Remedies","Nakshatras"])
        q=st.text_input("What would you like to know?",placeholder=f"Ask about {topic.lower()}")
        if st.button("Explore topic",use_container_width=True,disabled=not q):
            docs,_=search_classical(f"{topic} {q}",7);prs=search_practitioners(f"{topic} {q}",8);st.session_state.explore_answer=answer(q,docs,prs,None,cfg.get("depth","Simple"));st.session_state.explore_sources=(docs,prs)
        if st.session_state.get("explore_answer"):st.markdown(st.session_state.explore_answer);source_panel(*st.session_state.explore_sources)
    with t2:
        store,count=ancient_store();st.metric("Indexed classical and official passages",f"{count:,}")
        q=st.text_input("Search the 21-source library",key="libq",placeholder="e.g. mantra initiation, Jupiter remedies, Vata")
        if q:
            docs,_=search_classical(q,6)
            for d in docs:
                m=d.metadata or {}
                with st.expander(f"{m.get('book') or m.get('source','Unknown')} · page {m.get('pdf_page','Needs Verification')}"):st.write(d.page_content[:550]+("…" if len(d.page_content)>550 else ""));st.caption(f"Chunk {m.get('chunk_id','')}")
    with t3:
        records=practitioner_records();teachers=sorted({r.get("speaker") for r in records if r.get("speaker")})
        teacher=st.selectbox("Choose a teacher",teachers)
        rows=[r for r in records if r.get("speaker")==teacher]
        st.caption(f"{len(rows)} indexed records")
        for r in rows[:30]:
            with st.expander(r.get("topic") or r.get("title") or r.get("video_title") or "Indexed teaching"):st.write(r.get("summary") or r.get("explanation_text") or "Needs Verification");st.caption(r.get("verification_status",""))

def main():
    cfg=profile_sidebar(); store,count=ancient_store(); records=practitioner_records()
    st.markdown(f"<div class='hero'><div class='eyebrow'>Personal Wisdom & Remedy Engine</div><h1>Ancient Wisdom Synthesis</h1><p class='subtitle'>Ask a simple question and get a simple answer. Deeper Vedic detail and sources are available only when you want them.</p><div class='muted' style='margin-top:10px'>{APP_VERSION}</div></div>",unsafe_allow_html=True)
    a,b,c=st.columns(3);a.success(f"Wisdom library: {count:,} passages" if count else "Wisdom library unavailable");b.success(f"Teacher knowledge: {len(records)} records");c.success("Enhanced online available" if api_key() else "Local knowledge ready")
    tabs=st.tabs(["Home","Ask","My Reading","My Remedies","Explore"])
    with tabs[0]:home(cfg)
    with tabs[1]:ask(cfg)
    with tabs[2]:reading(cfg)
    with tabs[3]:remedies(cfg)
    with tabs[4]:explore(cfg)

if __name__=="__main__":main()
