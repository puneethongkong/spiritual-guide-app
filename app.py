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

APP_VERSION = "AWS v1.23 User-Centred Home"
EMBEDDING_MODEL = "paraphrase-MiniLM-L3-v2"
COLLECTION_NAME = "ancient_wisdom"
PAGES = ["Home", "Ask", "My Reading", "My Remedies", "Explore"]

st.markdown("""
<style>
.stApp{background:radial-gradient(circle at 15% 0%,#202653 0,#11152d 38%,#090b18 100%);color:#f5f0e8}
.block-container{max-width:1480px;padding-top:1.2rem;padding-bottom:4rem}
[data-testid="stSidebar"]{background:#11142b;border-right:1px solid #303558}
[data-testid="stMetric"]{background:linear-gradient(145deg,rgba(31,36,70,.97),rgba(19,22,45,.97));border:1px solid #3a3f68;border-radius:18px;padding:16px;box-shadow:0 12px 30px rgba(0,0,0,.22)}
[data-testid="stMetricLabel"]{color:#aaa6b6!important}[data-testid="stMetricValue"]{color:#e2c45f!important}
[data-testid="stExpander"]{background:rgba(18,22,45,.82);border:1px solid #343961;border-radius:14px}
[data-testid="stDataFrame"]{border:1px solid #343961;border-radius:14px;overflow:hidden}
.stButton>button{background:linear-gradient(135deg,#5d4ba0,#8d68d8);color:white;border:1px solid #9d83df;border-radius:24px;font-weight:650;min-height:2.75rem;box-shadow:0 8px 18px rgba(72,49,128,.28)}
.stButton>button:hover{border-color:#e2c45f;color:white;transform:translateY(-1px)}
h1,h2,h3,h4{color:#f6f0e7}.hero h1{font-size:2.05rem!important;line-height:1.15!important;margin:.35rem 0 .55rem 0!important}.hero{padding:18px 24px!important}.hero .subtitle{font-size:.98rem!important;line-height:1.45!important}.hero .eyebrow{font-size:.72rem!important}.hero{padding:25px 29px;border:1px solid #41466f;border-radius:24px;background:linear-gradient(135deg,rgba(37,43,84,.97),rgba(17,20,43,.94));box-shadow:0 20px 55px rgba(0,0,0,.28);margin-bottom:18px}.eyebrow{color:#e2c45f;font-size:.8rem;font-weight:760;letter-spacing:.17em;text-transform:uppercase}.subtitle{color:#bbb5c8;font-size:1.05rem;margin:0}.muted{color:#9c97aa}.choice{padding:18px;border:1px solid #3a3f67;border-radius:17px;background:linear-gradient(145deg,rgba(28,32,63,.95),rgba(17,20,42,.95));min-height:145px}.small{color:#aaa6b6;font-size:.88rem}
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
GEMS={"Sun":"Ruby","Moon":"Pearl","Mars":"Red Coral","Mercury":"Emerald","Jupiter":"Yellow Sapphire","Venus":"Diamond / White Sapphire","Saturn":"Blue Sapphire","Rahu":"Hessonite (Gomed)","Ketu":"Cat's Eye"}
PLAIN={"Sun":"identity, vitality and leadership","Moon":"mind, emotions and inner security","Mars":"action, courage and directed energy","Mercury":"thinking, communication and adaptability","Jupiter":"growth, wisdom and judgement","Venus":"relationships, harmony and creativity","Saturn":"discipline, responsibility and endurance","Rahu":"intense desire and unfamiliar territory","Ketu":"detachment, insight and inward focus"}
LOCATION_PRESETS={
    "Hong Kong":(22.3193,114.1694,8.0),
    "Bharwain / Chintpurni, Himachal Pradesh":(31.64,76.13,5.5),
    "New Delhi":(28.6139,77.2090,5.5),
    "Mumbai":(19.0760,72.8777,5.5),
    "Singapore":(1.3521,103.8198,8.0),
    "Dubai":(25.2048,55.2708,4.0),
    "London":(51.5074,-0.1278,0.0),
    "New York":(40.7128,-74.0060,-5.0),
    "Los Angeles":(34.0522,-118.2437,-8.0),
    "Toronto":(43.6532,-79.3832,-5.0),
    "Sydney":(-33.8688,151.2093,10.0),
    "Melbourne":(-37.8136,144.9631,10.0),
    "Custom / other":(22.3193,114.1694,8.0),
}

# ---------- Calculation engine ----------
def sign_info(lon):
    lon%=360; i=int(lon/30); return {"longitude":lon,"sign":SIGNS[i],"degree":lon%30,"sign_index":i}
def nak_info(lon):
    lon%=360; i=min(int(lon/NAK_SIZE),26); within=lon-i*NAK_SIZE
    return {"nakshatra":NAKSHATRAS[i],"pada":min(int(within/PADA_SIZE)+1,4),"lord":NAK_LORDS[i%9],"within":within}
def fmt_deg(v):
    d=int(v); m=int((v-d)*60); s=round((((v-d)*60)-m)*60)
    return f"{d:02d}° {m:02d}′ {s:02d}″"
def angle(a,b):
    d=abs((a-b)%360); return min(d,360-d)
def body(jd,pid):
    x,_=swe.calc_ut(jd,pid,FLAGS); out=sign_info(x[0]); out.update(nak_info(x[0])); out["retrograde"]=x[3]<0; return out
def add_years(dt,y): return dt+timedelta(days=y*365.2425)
def vimshottari(moon_lon,birth,now):
    n=nak_info(moon_lon); lord=n["lord"]; elapsed=DASHA_YEARS[lord]*(n["within"]/NAK_SIZE); cursor=add_years(birth,-elapsed); idx=DASHA_SEQ.index(lord); mds=[]
    for _ in range(2):
        for off in range(9):
            l=DASHA_SEQ[(idx+off)%9]; end=add_years(cursor,DASHA_YEARS[l]); mds.append({"lord":l,"start":cursor,"end":end}); cursor=end
    md=next(x for x in mds if x["start"]<=now<x["end"]); idx=DASHA_SEQ.index(md["lord"]); cursor=md["start"]; ads=[]
    for off in range(9):
        l=DASHA_SEQ[(idx+off)%9]; end=add_years(cursor,DASHA_YEARS[md["lord"]]*DASHA_YEARS[l]/120); ads.append({"lord":l,"start":cursor,"end":end}); cursor=end
    ad=next(x for x in ads if x["start"]<=now<x["end"])
    return {"mahadasha":md["lord"],"md_start":md["start"].date().isoformat(),"md_end":md["end"].date().isoformat(),"antardasha":ad["lord"],"ad_start":ad["start"].date().isoformat(),"ad_end":ad["end"].date().isoformat(),"md_timeline":[{"Mahadasha":x["lord"],"Start":x["start"].date().isoformat(),"End":x["end"].date().isoformat(),"Current":"Yes" if x is md else ""} for x in mds[:9]],"ad_timeline":[{"Antardasha":x["lord"],"Start":x["start"].date().isoformat(),"End":x["end"].date().isoformat(),"Current":"Yes" if x is ad else ""} for x in ads]}
def calculate_chart(dob,tob,lat,lon,tz):
    swe.set_sid_mode(swe.SIDM_LAHIRI,0,0); hour=tob.hour+tob.minute/60+tob.second/3600; jd=swe.julday(dob.year,dob.month,dob.day,hour-tz,swe.GREG_CAL)
    _,ascmc=swe.houses_ex(jd,lat,lon,b"W",swe.FLG_SIDEREAL); asc=sign_info(ascmc[0]); asc.update(nak_info(ascmc[0]))
    ids={"Sun":swe.SUN,"Moon":swe.MOON,"Mars":swe.MARS,"Mercury":swe.MERCURY,"Jupiter":swe.JUPITER,"Venus":swe.VENUS,"Saturn":swe.SATURN,"Rahu":swe.MEAN_NODE}; ps={n:body(jd,i) for n,i in ids.items()}
    ketu=sign_info(ps["Rahu"]["longitude"]+180); ketu.update(nak_info(ketu["longitude"])); ketu["retrograde"]=True; ps["Ketu"]=ketu
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
            target=((ps[n]["house"]+off-2)%12)+1; targets=[x for x,p in ps.items() if p["house"]==target and x!=n]; aspects.append({"Planet":n,"Aspect":f"{off}th","From":ps[n]["house"],"To":target,"Target planets":", ".join(targets) or "—"})
    ak=max(["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn"],key=lambda n:ps[n]["degree"]); now=datetime.now(timezone.utc); birth=(datetime(dob.year,dob.month,dob.day,tob.hour,tob.minute,tob.second)-timedelta(hours=tz)).replace(tzinfo=timezone.utc)
    return {"ascendant":asc,"planets":ps,"atmakaraka":ak,"timing":vimshottari(ps["Moon"]["longitude"],birth,now),"conjunctions":conjunctions,"aspects":aspects,"ayanamsa":swe.get_ayanamsa_ut(jd)}

# ---------- Knowledge engine ----------
@st.cache_resource(show_spinner=False)
def get_embeddings(): return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
@st.cache_resource(show_spinner=False)
def get_store():
    path="chroma_db"; db=os.path.join(path,"chroma.sqlite3")
    if not os.path.isfile(db): return None,0
    client=chromadb.PersistentClient(path=path); names=[c.name if hasattr(c,"name") else str(c) for c in client.list_collections()]; name=COLLECTION_NAME if COLLECTION_NAME in names else (names[0] if names else None)
    if not name:return None,0
    return Chroma(client=client,collection_name=name,embedding_function=get_embeddings()),client.get_collection(name).count()
@st.cache_data(show_spinner=False)
def get_practitioners():
    rows=[]
    for fn in ["integrative_practitioner_knowledge_v1_2.json","additional_practitioner_talks_v1.json"]:
        if not os.path.isfile(fn): continue
        data=json.load(open(fn,encoding="utf-8")); rows.extend(data.get("records",[]))
        for speaker in data.get("speakers",[]):
            for record in speaker.get("records",[]):
                item=dict(record); item.setdefault("speaker",speaker.get("speaker")); rows.append(item)
    return list({r.get("id",str(i)):r for i,r in enumerate(rows)}.values())
def search_local(query,k=6):
    store,count=get_store()
    if not store:return [],count
    try:return store.as_retriever(search_kwargs={"k":k}).invoke(query),count
    except Exception:return [],count
def search_teachers(query,k=5):
    terms=[x.lower() for x in query.replace("/"," ").split() if len(x)>2]; scored=[]
    for r in get_practitioners():
        if r.get("rag_eligible") is False:continue
        text=json.dumps(r,ensure_ascii=False).lower(); score=sum(1 for term in terms if term in text)+(2 if r.get("exact_answer_eligible") else 0)
        if score:scored.append((score,r))
    scored.sort(key=lambda x:x[0],reverse=True); return [r for _,r in scored[:k]]
def zai_key():
    try:return st.secrets.get("ZAI_API_KEY","")
    except Exception:return ""
def get_llm():return ChatOpenAI(model="glm-4.5-flash",openai_api_key=zai_key(),openai_api_base="https://api.z.ai/api/paas/v4",temperature=.35,max_tokens=1800,extra_body={"thinking":{"type":"disabled"}})
def evidence_context(docs,teachers):
    out=[]
    for i,d in enumerate(docs,1):
        m=d.metadata or {}; out.append(f"[C{i}] {m.get('book') or m.get('source','Unknown')} | page {m.get('pdf_page','Needs Verification')}\n{d.page_content}")
    for i,r in enumerate(teachers,1):out.append(f"[P{i}] {r.get('speaker') or 'Needs Verification'} | {r.get('topic') or r.get('title') or r.get('video_title','Indexed teaching')}\n{r.get('summary') or r.get('explanation_text','')}")
    return "\n\n".join(out)
def _trim_words(text,limit):
    words=(text or "").split()
    return " ".join(words[:limit])+("…" if len(words)>limit else "")

def synthesize(question,docs,teachers,personal=None,depth="Simple",history=None):
    docs=docs[:5]; teachers=teachers[:4]
    if not zai_key():
        if not docs and not teachers:
            return "I could not find enough verified local material. **Needs Verification.**"
        parts=[]
        if personal:
            parts.append(f"**Personal context:** {personal['timing']['mahadasha']} major period, {personal['timing']['antardasha']} sub-period.")
        if teachers:
            summary=teachers[0].get("summary") or teachers[0].get("explanation_text")
            if summary: parts.append(_trim_words(summary,70 if depth=="Simple" else 130))
        elif docs:
            parts.append(_trim_words(" ".join(docs[0].page_content.split()),80 if depth=="Simple" else 150))
        parts.append("**Practical note:** treat this as traditional or reflective guidance. Specific gemstones, herbs, fasting, medical claims and advanced practices require verification.")
        return "\n\n".join(parts)
    limits={"Simple":"80-140 words, direct answer first, no raw quotations and no teacher names unless necessary","Detailed":"180-300 words with direct answer, practical meaning and caution","Advanced":"350-550 words with technical Vedic logic, disagreements and concise source notes"}
    prompt=f"""Answer in plain language. Question: {question}\nDepth: {depth}; {limits[depth]}.\nPersonal chart: {json.dumps(personal,default=str) if personal else 'not supplied'}\nRecent conversation: {json.dumps((history or [])[-6:],ensure_ascii=False)}\nEvidence:\n{evidence_context(docs,teachers)}\nRules: synthesise, do not dump passages; explain Sanskrit terms; never invent remedies, gemstone suitability, universal chakra mappings or medical claims; say Needs Verification when evidence is weak; end Simple answers with one practical takeaway."""
    try:
        return get_llm().invoke(prompt).content
    except Exception:
        return synthesize(question,docs,teachers,personal,depth,[]) if not zai_key() else "Enhanced synthesis is temporarily unavailable. Please use the local library view or try again. **Needs Verification for any specific remedy.**"

# ---------- Deep personal synthesis ----------
def personal_fact_summary(c):
    t=c["timing"]
    planets={}
    for n,p in c["planets"].items():
        planets[n]={
            "sign":p["sign"],"degree":round(p["degree"],2),"house":p["house"],
            "nakshatra":p["nakshatra"],"pada":p["pada"],
            "condition":p["condition"],"rules_houses":p["rules_houses"],
            "retrograde":p["retrograde"]
        }
    return {
        "ascendant":c["ascendant"]["sign"],
        "ascendant_degree":round(c["ascendant"]["degree"],2),
        "moon_nakshatra":c["planets"]["Moon"]["nakshatra"],
        "moon_pada":c["planets"]["Moon"]["pada"],
        "atmakaraka":c["atmakaraka"],
        "mahadasha":t["mahadasha"],"antardasha":t["antardasha"],
        "md_end":t["md_end"],"ad_end":t["ad_end"],
        "planets":planets,"conjunctions":c["conjunctions"],"aspects":c["aspects"]
    }

def retrieve_personal_layers(c):
    facts=personal_fact_summary(c); t=c["timing"]; ak=c["atmakaraka"]
    queries={
        "jyotish":f"{facts['ascendant']} ascendant {ak} Atmakaraka {t['mahadasha']} Mahadasha {t['antardasha']} Antardasha houses lordship nakshatra current life themes",
        "ayurveda":f"Ayurveda mind body routine sleep digestion agni dosha balance {ak} {t['mahadasha']} supportive lifestyle",
        "mantra":f"{ak} {t['mahadasha']} {t['antardasha']} mantra devotional practice japa stotra graha remedy",
        "yoga":f"yoga meditation pranayama grounding focus balance {ak} {t['mahadasha']}",
        "remedies":f"{ak} {t['mahadasha']} {t['antardasha']} upaya remedies dana charity behaviour gemstone strengthen pacify",
        "chakra":f"{ak} planet chakra subtle body correspondence balance"
    }
    layers={}
    for key,q in queries.items():
        docs,_=search_local(q,6); teachers=search_teachers(q,5)
        layers[key]=(docs,teachers)
    return facts,layers

def combined_layer_context(layers):
    blocks=[]
    for layer,(docs,teachers) in layers.items():
        blocks.append(f"\n## RETRIEVAL LAYER: {layer.upper()}\n"+evidence_context(docs[:5],teachers[:4]))
    return "\n".join(blocks)

def deep_personal_report(c,depth="Detailed"):
    facts,layers=retrieve_personal_layers(c)
    if not zai_key():
        return facts,layers,None
    lengths={"Simple":"650-900 words","Detailed":"1100-1600 words","Advanced":"1800-2600 words"}
    prompt=f"""Create a rigorous integrated personal Ancient Wisdom report. Length {lengths.get(depth,'1100-1600 words')}.

LOCKED CALCULATED FACTS:
{json.dumps(facts,ensure_ascii=False,default=str)}

RETRIEVED KNOWLEDGE:
{combined_layer_context(layers)}

Required structure:
1. Executive synthesis: 5-8 lines on the central personal pattern and current phase.
2. Personal Jyotish: Ascendant, Ascendant lord, Moon/Nakshatra, Atmakaraka, important planets/houses, dignity/retrogression/combustion, conjunctions and major classical aspects. Explain why each matters.
3. Current timing: integrate Mahadasha and Antardasha with their actual placements, lordships and condition in this chart. Give opportunities, pressures and decision themes.
4. Ayurveda and mind-body: use retrieved Ayurveda material for supportive themes such as routine, sleep, digestion/Agni, steadiness and lifestyle. Do NOT diagnose Prakriti or Vikriti from astrology alone. State what additional assessment would be needed.
5. Chakra/subtle-body: show mappings only where retrieved; identify framework differences rather than creating a universal mapping.
6. Mantra and spiritual practice: distinguish simple devotional practice, Graha mantra, stotra, bija/tantric or diksha-sensitive practices. Recommend only what retrieved evidence supports.
7. Personal remedies: rank 3-5 actions. For every action state PURPOSE, WHY THIS PERSON, SOURCE BASIS, HOW TO APPLY if supported, and GUIDANCE LEVEL. Distinguish strengthen from balance/pacify.
8. Gemstones: list relevant traditional correspondence only if useful, and explain why chart suitability needs stronger verification than Mahadasha alone.
9. Three priorities now: three concise actionable priorities.
10. Evidence map: briefly say which conclusions come from calculated facts, classical/official sources, practitioner frameworks, and which remain Needs Verification.

Rules: Calculated facts override retrieved prose. Never invent placements, classical quotations, mantra counts, gemstone suitability, medical outcomes or universal chakra correspondences. Practitioner material must not be promoted to classical consensus. Keep Simple language accessible even though the underlying analysis is deep."""
    try:
        report=get_llm().invoke(prompt).content
    except Exception as exc:
        report=None
    return facts,layers,report

def render_local_personal_layers(c,layers):
    st.markdown("### Deep local knowledge view")
    labels={"jyotish":"Personal Jyotish","ayurveda":"Ayurveda & mind-body","mantra":"Mantra & spiritual practice","yoga":"Yoga & meditation","remedies":"Traditional remedies","chakra":"Chakra / subtle-body perspectives"}
    for key in ["jyotish","ayurveda","mantra","yoga","remedies","chakra"]:
        docs,teachers=layers[key]
        with st.expander(labels[key],expanded=(key in ("jyotish","remedies"))):
            if teachers:
                for r in teachers[:2]:
                    text=r.get("summary") or r.get("explanation_text") or ""
                    if text: st.write(_trim_words(text,120))
            if docs:
                for d in docs[:2]:
                    m=d.metadata or {}; st.caption(f"{m.get('book') or m.get('source','Unknown')} · PDF page {m.get('pdf_page','Needs Verification')}")
                    st.write(_trim_words(" ".join(d.page_content.split()),120))

# ---------- UI state and profile ----------
def navigate(page,question=None):
    st.session_state.page=page
    if question:st.session_state.pending_question=question
    st.rerun()
def _apply_location_preset():
    preset=st.session_state.get("location_preset","Hong Kong")
    if preset!="Custom / other":
        lat,lon,tz=LOCATION_PRESETS[preset]
        st.session_state.birth_lat=float(lat)
        st.session_state.birth_lon=float(lon)
        st.session_state.birth_tz=float(tz)
    st.session_state.profile_confirmed=False

def profile_panel():
    with st.sidebar:
        st.markdown("### Your Profile")
        name=st.text_input("Name",st.session_state.get("profile_name",""),placeholder="Your name")
        dob=st.date_input("Date of birth",st.session_state.get("profile_dob",date(1990,1,1)),min_value=date(1900,1,1),max_value=date.today())
        tob=st.time_input("Exact birth time",st.session_state.get("profile_tob",datetime.strptime("12:00","%H:%M").time()))

        if "location_preset" not in st.session_state:
            st.session_state.location_preset=st.session_state.get("profile_preset","Hong Kong")
        if "birth_lat" not in st.session_state:
            initial=LOCATION_PRESETS.get(st.session_state.location_preset,LOCATION_PRESETS["Hong Kong"])
            st.session_state.birth_lat=float(st.session_state.get("profile_lat",initial[0]))
            st.session_state.birth_lon=float(st.session_state.get("profile_lon",initial[1]))
            st.session_state.birth_tz=float(st.session_state.get("profile_tz",initial[2]))

        preset=st.selectbox("Birthplace",list(LOCATION_PRESETS),key="location_preset",on_change=_apply_location_preset)
        with st.expander("Confirm birth location settings",expanded=(preset=="Custom / other")):
            st.caption("Coordinates and historical UTC offset must match the birthplace and birth date. Daylight-saving or historical timezone differences need verification.")
            lat=st.number_input("Latitude",-90.0,90.0,key="birth_lat",format="%.4f")
            lon=st.number_input("Longitude",-180.0,180.0,key="birth_lon",format="%.4f")
            tz=st.number_input("UTC offset at birth",-12.0,14.0,key="birth_tz",step=.25)
            confirmed=st.checkbox("I confirm the birth time, coordinates and UTC offset",key="profile_confirmed")

        depth=st.select_slider("Answer detail",["Simple","Detailed","Advanced"],value=st.session_state.get("depth","Simple"))
        advanced=st.toggle("Show advanced Vedic details",value=st.session_state.get("advanced",False))
        if st.button("Save profile",use_container_width=True):
            st.session_state.update(profile_name=name,profile_dob=dob,profile_tob=tob,profile_preset=preset,profile_lat=lat,profile_lon=lon,profile_tz=tz,depth=depth,advanced=advanced)
            st.success("Profile saved for this session")
        return {"name":name or "Seeker","dob":dob,"tob":tob,"place":preset,"lat":lat,"lon":lon,"tz":tz,"confirmed":confirmed,"depth":depth,"advanced":advanced}

def ensure_chart(cfg,force=False):
    if not cfg.get("confirmed"):
        return None
    signature=(cfg["dob"],cfg["tob"],cfg["lat"],cfg["lon"],cfg["tz"])
    if force or st.session_state.get("chart_signature")!=signature:
        st.session_state.chart=calculate_chart(cfg["dob"],cfg["tob"],cfg["lat"],cfg["lon"],cfg["tz"]); st.session_state.chart_signature=signature
    return st.session_state.chart

def sources_expander(docs,teachers):
    with st.expander(f"Sources · {len(docs[:5])} classical/official · {len(teachers[:4])} practitioner"):
        for d in docs[:5]:
            m=d.metadata or {}; st.markdown(f"- **{m.get('book') or m.get('source','Unknown')}** · PDF page {m.get('pdf_page','Needs Verification')}")
        for r in teachers[:4]:st.markdown(f"- **{r.get('speaker') or 'Needs Verification'}** · {r.get('topic') or r.get('title') or r.get('video_title','Indexed teaching')}")

# ---------- Pages ----------
def home_page(cfg):
    st.markdown("## How can I help you today?")

    # The most useful action is available immediately, without navigating first.
    with st.form("home_ask_form",clear_on_submit=True):
        home_question=st.text_input(
            "Ask anything",
            placeholder="e.g. What should I focus on now? What does Saturn mean? Which mantra may help focus?",
            label_visibility="collapsed"
        )
        ask_now=st.form_submit_button("Ask Ancient Wisdom",type="primary",use_container_width=True)
    if ask_now and home_question.strip():
        navigate("Ask",home_question.strip())

    st.caption("Ask in ordinary language. Once a personal chart is generated, the same question automatically uses the chart as context.")

    st.markdown("### Or choose a path")
    cols=st.columns(3)
    cards=[
        ("🔮 My Personal Reading","Enter or confirm birth details and build a deep personal synthesis across Jyotish, current timing, Ayurveda, yoga, mantra and remedies.","Build My Reading","My Reading"),
        ("🪷 My Remedies","Turn the calculated chart and retrieved knowledge into practical priorities, low-risk practices and carefully qualified traditional options.","View My Remedies","My Remedies"),
        ("📚 Explore Knowledge","Search the 21-source library, inspect topics and browse indexed teachers when you want to research rather than personalise.","Explore Knowledge","Explore")
    ]
    for i,(title,desc,label,page) in enumerate(cards):
        with cols[i]:
            st.markdown(f"<div class='choice'><h3>{title}</h3><p>{desc}</p></div>",unsafe_allow_html=True)
            if st.button(label,key=f"home_{i}",use_container_width=True):navigate(page)

    st.markdown("### Common questions")
    prompts=[
        ("What should I focus on now?","What should I focus on right now, and why?"),
        ("Why am I restless?","Why am I feeling restless lately?"),
        ("What is a mantra?","What is a mantra and how is it used?"),
        ("Could a gemstone suit me?","Is any gemstone traditionally relevant to my chart, and what must be verified first?")
    ]
    pcs=st.columns(4)
    for i,(label,q) in enumerate(prompts):
        with pcs[i]:
            if st.button(label,key=f"prompt_{i}",use_container_width=True):navigate("Ask",q)

def ask_page(cfg):
    st.markdown("## Ask Ancient Wisdom"); st.caption("Ask in ordinary language. The app uses your personal chart automatically once generated.")
    if "chat" not in st.session_state:st.session_state.chat=[]
    for item in st.session_state.chat:
        with st.chat_message(item["role"]):st.markdown(item["content"])
    question=st.session_state.pop("pending_question",None) or st.chat_input("What's on your mind?")
    if question:
        st.session_state.chat.append({"role":"user","content":question}); personal=st.session_state.get("chart"); search_q=question
        if personal:search_q+=f" {personal['timing']['mahadasha']} Mahadasha {personal['timing']['antardasha']} Antardasha {personal['atmakaraka']} Atmakaraka"
        docs,_=search_local(search_q,7); teachers=search_teachers(search_q,6); response=synthesize(question,docs,teachers,personal,cfg["depth"],st.session_state.chat)
        st.session_state.chat.append({"role":"assistant","content":response}); st.session_state.last_sources=(docs,teachers); st.rerun()
    if st.session_state.get("last_sources"):sources_expander(*st.session_state.last_sources)
    if st.session_state.chat and st.button("Clear conversation"):st.session_state.chat=[];st.session_state.pop("last_sources",None);st.rerun()
def reading_page(cfg):
    st.markdown("## My Personal Reading")
    st.caption("The engine analyses the full calculated chart first, then retrieves Jyotish, Ayurveda, yoga, mantra, chakra and remedy knowledge around that chart.")
    if not cfg.get("confirmed"):
        st.warning("Confirm birth time, coordinates and UTC offset in Your Profile before generating the chart.")
    if st.button("Generate Full Personal Synthesis",type="primary",use_container_width=True,disabled=not cfg.get("confirmed")):
        c=ensure_chart(cfg,True)
        facts,layers,report=deep_personal_report(c,cfg["depth"])
        st.session_state.personal_facts=facts
        st.session_state.personal_layers=layers
        st.session_state.personal_report=report

    if "chart" not in st.session_state:return
    c=st.session_state.chart;t=c["timing"]
    a,b,d,e=st.columns(4)
    a.metric("How you approach life",c["ascendant"]["sign"],"Vedic term: Ascendant")
    b.metric("Your emotional pattern",f"{c['planets']['Moon']['nakshatra']} · quarter {c['planets']['Moon']['pada']}","Vedic term: Nakshatra")
    d.metric("Major life period",t["mahadasha"],f"to {t['md_end']}")
    e.metric("Current sub-period",t["antardasha"],f"to {t['ad_end']}")
    st.markdown(f"### Core developmental theme: {c['atmakaraka']}")
    st.write(f"The chart gives special developmental importance to {PLAIN[c['atmakaraka']] }. This is only one layer; the report below integrates the rest of the chart and knowledge base.")

    if st.session_state.get("personal_report"):
        st.markdown(st.session_state.personal_report)
    elif st.session_state.get("personal_layers"):
        st.info("Enhanced synthesis is not connected, so the app is showing the deep local retrieval layers instead of collapsing the reading to one short paragraph.")
        render_local_personal_layers(c,st.session_state.personal_layers)
    else:
        st.info("Click Generate Full Personal Synthesis to build the multi-layer report.")

    if cfg["advanced"]:
        st.markdown("### Advanced calculated chart")
        rows=[{"Planet":n,"Sign":p["sign"],"Degree":fmt_deg(p["degree"]),"House":p["house"],"Nakshatra":p["nakshatra"],"Pada":p["pada"],"Condition":"; ".join(p["condition"]),"Rules houses":", ".join(map(str,p["rules_houses"])) or "—"} for n,p in c["planets"].items()]
        st.dataframe(rows,use_container_width=True,hide_index=True)
        with st.expander("Mahadasha and Antardasha timelines"):st.dataframe(t["md_timeline"],use_container_width=True,hide_index=True);st.dataframe(t["ad_timeline"],use_container_width=True,hide_index=True)
        with st.expander("Conjunctions and classical aspects"):st.dataframe(c["conjunctions"],use_container_width=True,hide_index=True);st.dataframe(c["aspects"],use_container_width=True,hide_index=True)

def remedies_page(cfg):
    st.markdown("## My Remedies")
    if "chart" not in st.session_state:
        st.info("Generate My Personal Reading first. The remedy plan must come from the calculated personal chart, not default or generic planet rules.")
        if st.button("Go to My Reading",use_container_width=True):navigate("My Reading")
        return
    c=st.session_state.chart;t=c["timing"]
    st.markdown(f"### Current focus: {t['mahadasha']} major period · {t['antardasha']} sub-period · {c['atmakaraka']} developmental theme")
    st.caption("The engine ranks low-risk actions first and keeps gemstones, advanced mantra and stronger interventions behind verification.")
    q=f"personal remedies strengthen pacify balance {t['mahadasha']} Mahadasha {t['antardasha']} Antardasha {c['atmakaraka']} Atmakaraka house {c['planets'][c['atmakaraka']]['house']} mantra dana behaviour yoga Ayurveda gemstone"
    docs,_=search_local(q,10);teachers=search_teachers(q,10)
    if st.button("Build Detailed Remedy Plan",type="primary",use_container_width=True):
        if zai_key():
            prompt=f"""Build a structured remedy plan from this locked chart {json.dumps(personal_fact_summary(c),default=str)} and this evidence {evidence_context(docs,teachers)}. Rank 3-5 remedies. For each give purpose, exact chart reason, source basis, application only if source-supported, expected traditional objective, and guidance level. Separate low-risk behavioural/devotional/yoga/Ayurveda support from guidance-required advanced mantra/fasting/yantra and specialist gemstone questions. Distinguish strengthen versus pacify. Never invent mantra counts, medical effects or gemstone suitability."""
            try:st.session_state.remedy_answer=get_llm().invoke(prompt).content
            except Exception:st.session_state.remedy_answer=None
        else:st.session_state.remedy_answer=None
        st.session_state.remedy_sources=(docs,teachers)
    if st.session_state.get("remedy_answer"):st.markdown(st.session_state.remedy_answer)
    elif st.session_state.get("remedy_sources"):
        st.markdown("### Retrieved remedy evidence")
        sources_expander(*st.session_state.remedy_sources)
        st.info("Enhanced synthesis is unavailable. Use the source evidence above rather than a generic remedy generated without support.")
    st.warning("Gemstones, herbs, fasting, advanced pranayama and Bija/Tantric practices require verification or qualified guidance.")

def explore_page(cfg):
    st.markdown("## Explore Ancient Wisdom");t1,t2,t3=st.tabs(["Topics","Wisdom Library","Teachers"])
    with t1:
        topic=st.selectbox("Choose a topic",["Planets","Life periods","Chakras","Meditation","Mantras","Ayurveda","Yoga","Gemstones","Remedies","Nakshatras"]);q=st.text_input("What would you like to know?",placeholder=f"Ask about {topic.lower()}")
        if st.button("Explore Topic",disabled=not q,use_container_width=True):
            docs,_=search_local(f"{topic} {q}",7);teachers=search_teachers(f"{topic} {q}",6);st.session_state.explore_answer=synthesize(q,docs,teachers,None,cfg["depth"]);st.session_state.explore_sources=(docs,teachers)
        if st.session_state.get("explore_answer"):st.markdown(st.session_state.explore_answer);sources_expander(*st.session_state.explore_sources)
    with t2:
        _,count=get_store();st.metric("Indexed classical and official passages",f"{count:,}");q=st.text_input("Search the 21-source library",key="library_query")
        if q:
            docs,_=search_local(q,6)
            for d in docs:
                m=d.metadata or {}
                with st.expander(f"{m.get('book') or m.get('source','Unknown')} · page {m.get('pdf_page','Needs Verification')}"):st.write(d.page_content[:600]+("…" if len(d.page_content)>600 else ""));st.caption(f"Chunk {m.get('chunk_id','')}")
    with t3:
        records=get_practitioners();teachers=sorted({r.get("speaker") for r in records if r.get("speaker")})
        if not teachers:st.info("Practitioner library unavailable")
        else:
            teacher=st.selectbox("Choose a teacher",teachers);rows=[r for r in records if r.get("speaker")==teacher];st.caption(f"{len(rows)} indexed records")
            for r in rows[:30]:
                with st.expander(r.get("topic") or r.get("title") or r.get("video_title") or "Indexed teaching"):st.write(r.get("summary") or r.get("explanation_text") or "Needs Verification");st.caption(r.get("verification_status",""))

# ---------- Main ----------
def main():
    cfg=profile_panel();_,count=get_store();teacher_count=len(get_practitioners())
    st.markdown("<div class='hero'><div class='eyebrow'>PERSONAL WISDOM & REMEDY ENGINE</div><h1>Ancient Wisdom Synthesis</h1><p class='subtitle'>Personal guidance from calculated Vedic astrology and a searchable library spanning Jyotish, Ayurveda, yoga, mantra, remedies and practitioner perspectives.</p></div>",unsafe_allow_html=True)

    if "page" not in st.session_state:st.session_state.page="Home"
    chosen=st.radio("Navigation",PAGES,horizontal=True,index=PAGES.index(st.session_state.page),label_visibility="collapsed")
    if chosen!=st.session_state.page:st.session_state.page=chosen;st.rerun()

    with st.expander("Library & system status",expanded=False):
        st.write(f"Ancient Wisdom library: **{count:,} indexed passages**")
        st.write(f"Practitioner knowledge: **{teacher_count} structured records**")
        st.write("Answer engine: **Enhanced online**" if zai_key() else "Answer engine: **Local knowledge**")
        st.caption("These figures are system diagnostics, not part of your reading.")

    st.divider();page=st.session_state.page
    if page=="Home":home_page(cfg)
    elif page=="Ask":ask_page(cfg)
    elif page=="My Reading":reading_page(cfg)
    elif page=="My Remedies":remedies_page(cfg)
    else:explore_page(cfg)

if __name__=="__main__":main()
