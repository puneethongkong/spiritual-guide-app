import json
import os
from datetime import date, datetime, timezone

import chromadb
import plotly.graph_objects as go
import streamlit as st
import swisseph as swe
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_openai import ChatOpenAI

st.set_page_config(page_title="Ancient Wisdom Synthesis", page_icon="🕉️", layout="wide")

st.markdown("""
<style>
.stApp {background:#0f1226;color:#eae6df}
[data-testid="stSidebar"] {background:#12142b;border-right:1px solid #2a2d4a}
[data-testid="stMetric"] {background:#171a33;border:1px solid #2a2d4a;border-radius:12px;padding:15px}
[data-testid="stMetricLabel"] {color:#aaa6a0!important}
[data-testid="stMetricValue"] {color:#d7b958!important}
.stButton>button {background:linear-gradient(135deg,#4a3f78,#7c5cbf);color:white;border:0;border-radius:26px;padding:10px 26px;font-weight:600}
[data-testid="stChatMessage"] {background:#171a33;border:1px solid #2a2d4a;border-radius:12px}
h1,h2,h3,h4 {color:#eae6df} p,li,.stMarkdown {color:#c9c4bb}
</style>
""", unsafe_allow_html=True)

SIGNS = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo","Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
NAKSHATRAS = ["Ashwini","Bharani","Krittika","Rohini","Mrigashirsha","Ardra","Punarvasu","Pushya","Ashlesha","Magha","Purva Phalguni","Uttara Phalguni","Hasta","Chitra","Swati","Vishakha","Anuradha","Jyeshtha","Mula","Purvashadha","Uttarashadha","Shravana","Dhanishta","Shatabhisha","Purva Bhadrapada","Uttara Bhadrapada","Revati"]
NAKSHATRA_LORDS = ["Ketu","Venus","Sun","Moon","Mars","Rahu","Jupiter","Saturn","Mercury"]
NAK_SIZE = 360/27
PADA_SIZE = NAK_SIZE/4
FLAGS = swe.FLG_SWIEPH | swe.FLG_SIDEREAL

PLANET_MAP = {
    "Sun":{"chakra":"Manipura","dosha":"Pitta","theme":"Purpose & Vitality","nama":"Needs Verification"},
    "Moon":{"chakra":"Anahata","dosha":"Kapha","theme":"Emotion & Nurturing","nama":"N494 Rakinyamba"},
    "Mars":{"chakra":"Manipura","dosha":"Pitta","theme":"Courage & Action","nama":"N503 Lakinyamba"},
    "Mercury":{"chakra":"Vishuddha","dosha":"Vata","theme":"Communication & Logic","nama":"N484 Dakinishvari"},
    "Jupiter":{"chakra":"Ajna","dosha":"Kapha","theme":"Wisdom & Expansion","nama":"N523 Shadanana"},
    "Venus":{"chakra":"Svadhisthana","dosha":"Kapha","theme":"Love & Creativity","nama":"N513 Kakini"},
    "Saturn":{"chakra":"Muladhara","dosha":"Vata","theme":"Discipline & Grounding","nama":"N520 Sakinyamba"},
}

def sign_info(lon):
    lon %= 360
    return {"longitude":lon,"sign":SIGNS[int(lon/30)],"degree":lon%30}

def nak_info(lon):
    lon %= 360
    idx = min(int(lon/NAK_SIZE),26)
    within = lon - idx*NAK_SIZE
    return {"nakshatra":NAKSHATRAS[idx],"pada":min(int(within/PADA_SIZE)+1,4),"lord":NAKSHATRA_LORDS[idx%9]}

def fmt_deg(v):
    d=int(v); mf=(v-d)*60; m=int(mf); s=round((mf-m)*60)
    if s==60: s=0; m+=1
    if m==60: m=0; d+=1
    return f"{d:02d}° {m:02d}′ {s:02d}″"

def calc_body(jd,pid):
    data,_=swe.calc_ut(jd,pid,FLAGS)
    out=sign_info(data[0]); out.update(nak_info(data[0])); out["retrograde"]=data[3]<0
    return out

def calculate_chart(dob,tob,lat,lon,tz):
    swe.set_sid_mode(swe.SIDM_LAHIRI,0,0)
    local_hour=tob.hour+tob.minute/60+tob.second/3600
    jd=swe.julday(dob.year,dob.month,dob.day,local_hour-tz,swe.GREG_CAL)
    _,ascmc=swe.houses_ex(jd,lat,lon,b"W",swe.FLG_SIDEREAL)
    asc=sign_info(ascmc[0]); asc.update(nak_info(ascmc[0]))
    ids={"Sun":swe.SUN,"Moon":swe.MOON,"Mars":swe.MARS,"Mercury":swe.MERCURY,"Jupiter":swe.JUPITER,"Venus":swe.VENUS,"Saturn":swe.SATURN,"Rahu":swe.MEAN_NODE}
    planets={name:calc_body(jd,pid) for name,pid in ids.items()}
    ketu=sign_info(planets["Rahu"]["longitude"]+180); ketu.update(nak_info(ketu["longitude"])); ketu["retrograde"]=True; planets["Ketu"]=ketu
    ak=max(["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn"],key=lambda x:planets[x]["degree"])
    now=datetime.now(timezone.utc); jd_now=swe.julday(now.year,now.month,now.day,now.hour+now.minute/60,swe.GREG_CAL)
    return {
        "system":"Lahiri / Chitrapaksha sidereal zodiac","house_system":"Whole Sign",
        "ayanamsa":swe.get_ayanamsa_ut(jd),"ascendant":asc,"planets":planets,
        "moon_nakshatra":planets["Moon"]["nakshatra"],"moon_pada":planets["Moon"]["pada"],"moon_lord":planets["Moon"]["lord"],
        "atmakaraka":ak,"atmakaraka_degree":planets[ak]["degree"],"karaka_method":"Seven-karaka system; Rahu and Ketu excluded",
        "saturn_transit":calc_body(jd_now,swe.SATURN),"jupiter_transit":calc_body(jd_now,swe.JUPITER),"transit_date":now.date().isoformat(),
        **PLANET_MAP[ak]
    }

@st.cache_resource(show_spinner=False)
def load_knowledge_base():
    db_dir = "." if os.path.isfile("chroma.sqlite3") else "chroma_db"
    db_file=os.path.join(db_dir,"chroma.sqlite3")
    if not os.path.isfile(db_file):
        raise FileNotFoundError("chroma.sqlite3 was not found in the GitHub repository.")
    client=chromadb.PersistentClient(path=db_dir)
    collections=client.list_collections()
    populated=[]
    for item in collections:
        name=item.name if hasattr(item,"name") else str(item)
        try:
            count=client.get_collection(name=name).count()
        except Exception:
            count=0
        if count>0: populated.append((name,count))
    if not populated:
        raise RuntimeError("No populated Chroma collection was found in chroma.sqlite3.")
    populated.sort(key=lambda x:x[1],reverse=True)
    collection_name=populated[0][0]
    embeddings=HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    store=Chroma(client=client,collection_name=collection_name,embedding_function=embeddings)
    return store.as_retriever(search_kwargs={"k":4}),collection_name,populated[0][1]

def build_llm(key):
    return ChatOpenAI(model="glm-4.5-flash",openai_api_key=key,openai_api_base="https://api.z.ai/api/paas/v4",temperature=0.6,max_tokens=2000,extra_body={"thinking":{"type":"disabled"}})

def parse_json(raw):
    try:
        a=raw.find("{"); b=raw.rfind("}")+1
        return json.loads(raw[a:b]) if a>=0 and b>a else None
    except Exception: return None

def make_prompt(name,chart,scores,balance,context):
    facts={p:{"sign":v["sign"],"degree":round(v["degree"],4),"nakshatra":v["nakshatra"],"pada":v["pada"],"retrograde":v["retrograde"]} for p,v in chart["planets"].items()}
    return f'''Return ONLY valid JSON with keys executive_summary, vedic_interpretation, psychological_interpretation, ayurvedic_interpretation, convergence, practical_actions, vedic_practice, cautions.
practical_actions must be a list of objects with action, why, how, frequency. vedic_practice must contain mantra, nama, practice, explanation.
Interpret but never alter the calculated facts. Do not diagnose illness, claim certainty, invent quotations, or call the Nakshatra lord the current Mahadasha.
User: {name}. Presentation balance 0=practical and 100=traditional: {balance}.
System: {chart['system']}; houses: {chart['house_system']}; ayanamsa: {chart['ayanamsa']:.6f}.
Ascendant: {chart['ascendant']['sign']} {chart['ascendant']['degree']:.6f}.
Moon Nakshatra: {chart['moon_nakshatra']}, Pada {chart['moon_pada']}, birth Nakshatra lord {chart['moon_lord']}.
Atmakaraka: {chart['atmakaraka']} {chart['atmakaraka_degree']:.6f}; method: {chart['karaka_method']}.
Planets: {json.dumps(facts)}. Self-reflection: {json.dumps(scores)}.
Symbolic mapping: theme {chart['theme']}; chakra {chart['chakra']}; dosha {chart['dosha']}; nama {chart['nama']}.
Retrieved context:\n{context}'''

def sidebar():
    with st.sidebar:
        st.markdown("### Configuration")
        try: secret=st.secrets.get("ZAI_API_KEY","")
        except Exception: secret=""
        key=secret or st.text_input("Z.ai API Key",type="password")
        with st.expander("Advanced settings"):
            balance=st.slider("Explanation balance",0,100,50,help="0 = practical; 100 = traditional")
        st.divider(); st.markdown("### Profile")
        name=st.text_input("Name","Puneet")
        st.markdown("### Birth details")
        dob=st.date_input("Date of birth",date(1983,12,27),min_value=date(1900,1,1),max_value=date.today())
        tob=st.time_input("Time of birth",datetime.strptime("00:35","%H:%M").time())
        lat=st.number_input("Latitude",-90.0,90.0,31.64,format="%.4f")
        lon=st.number_input("Longitude",-180.0,180.0,76.13,format="%.4f")
        tz=st.number_input("Birthplace UTC offset",-12.0,14.0,5.5,0.25)
    return dict(key=key,balance=balance,name=name or "Seeker",dob=dob,tob=tob,lat=lat,lon=lon,tz=tz)

def assessment():
    st.markdown("## Personal Self-Reflection Profile")
    st.caption("Non-clinical reflective indicators. 0 = Never, 4 = Always.")
    groups={
        "Reflective Thinking":["I question the nature of reality and the self behind my thoughts.","I am comfortable holding uncertainty and paradox.","I reflect on purpose beyond material goals."],
        "Meaning & Direction":["I find meaning even in difficult experiences.","My life feels oriented towards a larger purpose.","I learn from my past rather than repeat it."],
        "Spiritual Perception":["I sense a connection with other living beings.","I experience the sacred in nature or everyday life.","I can observe my thoughts without being swept away."],
        "Inner Calm":["I can quiet my mind when I choose to.","I experience moments of mental stillness.","I remain steady during stressful situations."]}
    scores={}; cols=st.columns(2)
    for i,(group,questions) in enumerate(groups.items()):
        with cols[i%2]:
            with st.container(border=True):
                st.markdown(f"#### {group}"); values=[]
                for j,q in enumerate(questions): values.append(st.slider(q,0,4,2,key=f"q_{i}_{j}"))
                scores[group]=round(sum(values)/(len(values)*4)*100)
    return scores

def show_chart(chart):
    st.markdown("## Calculated Vedic Profile")
    st.caption(f"{chart['system']} · {chart['house_system']} houses · Ayanamsa {chart['ayanamsa']:.4f}°")
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Ascendant",chart["ascendant"]["sign"],fmt_deg(chart["ascendant"]["degree"]))
    c2.metric("Moon",f"{chart['moon_nakshatra']} · Pada {chart['moon_pada']}",chart["planets"]["Moon"]["sign"])
    c3.metric("Nakshatra Lord",chart["moon_lord"],"Not current Mahadasha")
    c4.metric("Atmakaraka",chart["atmakaraka"],fmt_deg(chart["atmakaraka_degree"]))
    rows=[]
    for p in ["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn","Rahu","Ketu"]:
        v=chart["planets"][p]; rows.append({"Body":p,"Sidereal Sign":v["sign"],"Degree":fmt_deg(v["degree"]),"Nakshatra":v["nakshatra"],"Pada":v["pada"],"Motion":"Retrograde" if v["retrograde"] else "Direct"})
    with st.expander("Full sidereal planetary table",expanded=True): st.dataframe(rows,use_container_width=True,hide_index=True); st.caption(chart["karaka_method"])

def show_scores(scores):
    labels=list(scores); values=list(scores.values()); labels+=labels[:1]; values+=values[:1]
    fig=go.Figure(go.Scatterpolar(r=values,theta=labels,fill="toself",line=dict(color="#7c5cbf"),marker=dict(color="#c9a84c")))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True,range=[0,100])),showlegend=False,paper_bgcolor="rgba(0,0,0,0)",font=dict(color="#c9c4bb"),height=330,margin=dict(t=25,b=25,l=25,r=25))
    st.plotly_chart(fig,use_container_width=True)

def show_result(result,raw):
    if not result: st.warning("Z.ai returned unstructured content."); st.markdown(raw); return
    for title,key in [("Executive Summary","executive_summary"),("Vedic Perspective","vedic_interpretation"),("Self-Reflection Perspective","psychological_interpretation"),("Ayurvedic Symbolic Perspective","ayurvedic_interpretation"),("Where the Systems Converge","convergence")]:
        with st.container(border=True): st.markdown(f"#### {title}"); st.markdown(str(result.get(key,"No content returned.")))
    actions=result.get("practical_actions",[])
    if isinstance(actions,list):
        with st.container(border=True):
            st.markdown("#### Practical Actions")
            for i,a in enumerate(actions,1):
                if isinstance(a,dict): st.markdown(f"**{i}. {a.get('action','Action')}**\n\n**Why:** {a.get('why','')}  \n**How:** {a.get('how','')}  \n**Frequency:** {a.get('frequency','')}")
    vp=result.get("vedic_practice",{})
    if isinstance(vp,dict) and vp:
        with st.container(border=True): st.markdown("#### Recommended Vedic Practice"); st.markdown(f"**Mantra:** {vp.get('mantra','')}  \n**Nama:** {vp.get('nama','')}  \n**Practice:** {vp.get('practice','')}  \n{vp.get('explanation','')}")
    if result.get("cautions"): st.info(f"Framing note: {result['cautions']}")

def main():
    st.markdown("<h1 style='text-align:center'>Ancient Wisdom Synthesis</h1>",unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;color:#9c9a93'>Lahiri sidereal astrology · self-reflection · ancient texts · practical synthesis</p>",unsafe_allow_html=True)
    cfg=sidebar(); scores=assessment(); st.divider()
    if st.button("Generate My Synthesis",type="primary",use_container_width=True):
        try:
            chart=calculate_chart(cfg["dob"],cfg["tob"],cfg["lat"],cfg["lon"],cfg["tz"])
            st.session_state.chart=chart; st.session_state.scores=scores
            st.session_state.kb_status="Not tested"; st.session_state.zai_status="Not tested"
            docs=[]; context=""
            try:
                retriever,cname,ccount=load_knowledge_base(); docs=retriever.invoke(f"{chart['atmakaraka']} {chart['moon_nakshatra']} {chart['theme']} contemplation practice")
                st.session_state.kb_status=f"Connected: {cname} ({ccount} records)"
                blocks=[]
                for i,d in enumerate(docs,1):
                    md=d.metadata or {}; blocks.append(f"[S{i}] Source: {md.get('source') or md.get('book') or 'Unknown'}; Page: {md.get('page','Needs Verification')}\n{d.page_content}")
                context="\n\n".join(blocks)
            except Exception as e:
                st.session_state.kb_status=f"Unavailable: {e}"
            if cfg["key"]:
                try:
                    raw=build_llm(cfg["key"]).invoke(make_prompt(cfg["name"],chart,scores,cfg["balance"],context or "No knowledge-base context was available.")).content
                    st.session_state.raw=raw; st.session_state.result=parse_json(raw); st.session_state.zai_status="Connected"
                except Exception as e:
                    st.session_state.raw=""; st.session_state.result=None; st.session_state.zai_status=f"Unavailable: {e}"
            else:
                st.session_state.raw=""; st.session_state.result=None; st.session_state.zai_status="API key missing"
            st.session_state.docs=docs
        except Exception as e: st.error(f"Astrology calculation failed: {e}")
    if "chart" in st.session_state:
        st.divider(); show_chart(st.session_state.chart)
        a,b,c=st.columns(3); a.success("Astrology engine: Ready")
        if str(st.session_state.get("kb_status","")).startswith("Connected"): b.success(f"Knowledge base: {st.session_state.kb_status}")
        else: b.warning(f"Knowledge base: {st.session_state.get('kb_status','Not tested')}")
        if st.session_state.get("zai_status")=="Connected": c.success("Z.ai: Connected")
        else: c.warning(f"Z.ai: {st.session_state.get('zai_status','Not tested')}")
        left,right=st.columns([2,1])
        with left:
            st.markdown("## Synthesis")
            if st.session_state.get("zai_status")=="Connected": show_result(st.session_state.get("result"),st.session_state.get("raw",""))
            else: st.info("The calculated chart remains available. Synthesis will appear when Z.ai is connected.")
        with right: st.markdown("## Self-Reflection"); show_scores(st.session_state.scores); st.caption("Self-reported indicators, not clinical measures.")
        docs=st.session_state.get("docs",[])
        if docs:
            with st.expander("Retrieved source passages"):
                for i,d in enumerate(docs,1): st.markdown(f"**S{i} · {(d.metadata or {}).get('source','Source')}**\n\n{d.page_content[:800]}"); st.divider()

if __name__=="__main__": main()
