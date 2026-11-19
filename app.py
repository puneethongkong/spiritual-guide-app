import json
import os
import sqlite3
from datetime import date, datetime, timedelta, timezone

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
h1,h2,h3,h4 {color:#eae6df} p,li,.stMarkdown {color:#c9c4bb}
</style>
""", unsafe_allow_html=True)

SIGNS=["Aries","Taurus","Gemini","Cancer","Leo","Virgo","Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
NAKSHATRAS=["Ashwini","Bharani","Krittika","Rohini","Mrigashirsha","Ardra","Punarvasu","Pushya","Ashlesha","Magha","Purva Phalguni","Uttara Phalguni","Hasta","Chitra","Swati","Vishakha","Anuradha","Jyeshtha","Mula","Purvashadha","Uttarashadha","Shravana","Dhanishta","Shatabhisha","Purva Bhadrapada","Uttara Bhadrapada","Revati"]
NAKSHATRA_LORDS=["Ketu","Venus","Sun","Moon","Mars","Rahu","Jupiter","Saturn","Mercury"]
NAK_SIZE=360/27; PADA_SIZE=NAK_SIZE/4; FLAGS=swe.FLG_SWIEPH|swe.FLG_SIDEREAL
DASHA_SEQUENCE=["Ketu","Venus","Sun","Moon","Mars","Rahu","Jupiter","Saturn","Mercury"]
DASHA_YEARS={"Ketu":7,"Venus":20,"Sun":6,"Moon":10,"Mars":7,"Rahu":18,"Jupiter":16,"Saturn":19,"Mercury":17}
DAYS_PER_YEAR=365.2425
PLANET_MAP={
"Sun":{"chakra":"Manipura","dosha":"Pitta","theme":"Purpose & Vitality","nama":"Needs Verification"},
"Moon":{"chakra":"Anahata","dosha":"Kapha","theme":"Emotion & Nurturing","nama":"N494 Rakinyamba"},
"Mars":{"chakra":"Manipura","dosha":"Pitta","theme":"Courage & Action","nama":"N503 Lakinyamba"},
"Mercury":{"chakra":"Vishuddha","dosha":"Vata","theme":"Communication & Logic","nama":"N484 Dakinishvari"},
"Jupiter":{"chakra":"Ajna","dosha":"Kapha","theme":"Wisdom & Expansion","nama":"N523 Shadanana"},
"Venus":{"chakra":"Svadhisthana","dosha":"Kapha","theme":"Love & Creativity","nama":"N513 Kakini"},
"Saturn":{"chakra":"Muladhara","dosha":"Vata","theme":"Discipline & Grounding","nama":"N520 Sakinyamba"}}

def sign_info(lon):
    lon%=360; return {"longitude":lon,"sign":SIGNS[int(lon/30)],"degree":lon%30,"sign_index":int(lon/30)}
def nak_info(lon):
    lon%=360; idx=min(int(lon/NAK_SIZE),26); within=lon-idx*NAK_SIZE
    return {"nakshatra":NAKSHATRAS[idx],"pada":min(int(within/PADA_SIZE)+1,4),"lord":NAKSHATRA_LORDS[idx%9],"position_within":within}
def fmt_deg(v):
    d=int(v); mf=(v-d)*60; m=int(mf); s=round((mf-m)*60)
    if s==60:s=0;m+=1
    if m==60:m=0;d+=1
    return f"{d:02d}° {m:02d}′ {s:02d}″"
def calc_body(jd,pid):
    data,_=swe.calc_ut(jd,pid,FLAGS); out=sign_info(data[0]); out.update(nak_info(data[0])); out["retrograde"]=data[3]<0; return out
def add_years(dt,years): return dt+timedelta(days=float(years)*DAYS_PER_YEAR)
def whole_sign_house(asc_index,planet_index): return ((planet_index-asc_index)%12)+1

def calculate_vimshottari(moon_longitude,birth_utc,as_of_utc):
    n=nak_info(moon_longitude); lord=n["lord"]; elapsed=DASHA_YEARS[lord]*(n["position_within"]/NAK_SIZE); balance=DASHA_YEARS[lord]-elapsed
    idx=DASHA_SEQUENCE.index(lord); cursor=add_years(birth_utc,-elapsed); rows=[]
    for cycle in range(2):
        for offset in range(9):
            md=DASHA_SEQUENCE[(idx+offset)%9]; end=add_years(cursor,DASHA_YEARS[md]); rows.append({"lord":md,"start":cursor,"end":end}); cursor=end
    current=next(x for x in rows if x["start"]<=as_of_utc<x["end"])
    return {"birth_lord":lord,"balance_at_birth_years":balance,"current_lord":current["lord"],"current_start":current["start"].date().isoformat(),"current_end":current["end"].date().isoformat(),"year_basis":DAYS_PER_YEAR,"timeline":[{"Mahadasha":x["lord"],"Start":x["start"].date().isoformat(),"End":x["end"].date().isoformat(),"Current":"Yes" if x is current else ""} for x in rows[:9]]}

def calculate_chart(dob,tob,lat,lon,tz):
    swe.set_sid_mode(swe.SIDM_LAHIRI,0,0); local=tob.hour+tob.minute/60+tob.second/3600; jd=swe.julday(dob.year,dob.month,dob.day,local-tz,swe.GREG_CAL)
    _,ascmc=swe.houses_ex(jd,lat,lon,b"W",swe.FLG_SIDEREAL); asc=sign_info(ascmc[0]); asc.update(nak_info(ascmc[0]))
    ids={"Sun":swe.SUN,"Moon":swe.MOON,"Mars":swe.MARS,"Mercury":swe.MERCURY,"Jupiter":swe.JUPITER,"Venus":swe.VENUS,"Saturn":swe.SATURN,"Rahu":swe.MEAN_NODE}
    planets={n:calc_body(jd,p) for n,p in ids.items()}; ketu=sign_info(planets["Rahu"]["longitude"]+180); ketu.update(nak_info(ketu["longitude"])); ketu["retrograde"]=True; planets["Ketu"]=ketu
    for v in planets.values(): v["house"]=whole_sign_house(asc["sign_index"],v["sign_index"])
    ak=max(["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn"],key=lambda x:planets[x]["degree"])
    now=datetime.now(timezone.utc); jd_now=swe.julday(now.year,now.month,now.day,now.hour+now.minute/60+now.second/3600,swe.GREG_CAL)
    birth_utc=(datetime(dob.year,dob.month,dob.day,tob.hour,tob.minute,tob.second)-timedelta(hours=tz)).replace(tzinfo=timezone.utc)
    return {"system":"Lahiri / Chitrapaksha sidereal zodiac","house_system":"Whole Sign","ayanamsa":swe.get_ayanamsa_ut(jd),"ascendant":asc,"planets":planets,"moon_nakshatra":planets["Moon"]["nakshatra"],"moon_pada":planets["Moon"]["pada"],"moon_lord":planets["Moon"]["lord"],"atmakaraka":ak,"atmakaraka_degree":planets[ak]["degree"],"karaka_method":"Seven-karaka system; Rahu and Ketu excluded","dasha":calculate_vimshottari(planets["Moon"]["longitude"],birth_utc,now),"saturn_transit":calc_body(jd_now,swe.SATURN),"jupiter_transit":calc_body(jd_now,swe.JUPITER),"transit_date":now.date().isoformat(),**PLANET_MAP[ak]}

@st.cache_data(show_spinner=False)
def inspect_sqlite_database():
    candidates=[p for p in ["chroma.sqlite3",os.path.join("chroma_db","chroma.sqlite3")] if os.path.isfile(p)]
    if not candidates:return {"status":"missing","message":"chroma.sqlite3 was not found.","paths":[]}
    reports=[]
    for path in candidates:
        r={"path":path,"size_bytes":os.path.getsize(path),"sqlite_header":False,"tables":[],"row_counts":{},"collections":[],"segments":[],"error":""}
        try:
            with open(path,"rb") as f:r["sqlite_header"]=f.read(16)==b"SQLite format 3\x00"
            con=sqlite3.connect(f"file:{path}?mode=ro",uri=True); cur=con.cursor(); r["tables"]=[x[0] for x in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
            for table in r["tables"]:
                try:r["row_counts"][table]=cur.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                except Exception:r["row_counts"][table]="unavailable"
            if "collections" in r["tables"]:
                cols=[x[1] for x in cur.execute("PRAGMA table_info(collections)").fetchall()]; data=cur.execute("SELECT * FROM collections").fetchall(); r["collections"]=[dict(zip(cols,row)) for row in data]
            if "segments" in r["tables"]:
                cols=[x[1] for x in cur.execute("PRAGMA table_info(segments)").fetchall()]; data=cur.execute("SELECT * FROM segments").fetchall(); r["segments"]=[dict(zip(cols,row)) for row in data]
            con.close()
        except Exception as e:r["error"]=str(e)
        reports.append(r)
    return {"status":"ok","paths":candidates,"reports":reports}

@st.cache_resource(show_spinner=False)
def load_knowledge_base():
    candidates=[p for p in [".","chroma_db"] if os.path.isfile(os.path.join(p,"chroma.sqlite3"))]; diagnostics=[]; emb=HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    for path in candidates:
        try:client=chromadb.PersistentClient(path=path); collections=client.list_collections()
        except Exception as e:diagnostics.append(f"{path}: open failed ({e})");continue
        details=[]
        for item in collections:
            name=item.name if hasattr(item,"name") else str(item)
            try:count=client.get_collection(name=name).count()
            except Exception:count=0
            details.append((name,count))
        populated=[x for x in details if x[1]>0]
        if populated:
            name,count=max(populated,key=lambda x:x[1]); store=Chroma(client=client,collection_name=name,embedding_function=emb); return store.as_retriever(search_kwargs={"k":4}),name,count
        diagnostics.append(f"{path}: "+(", ".join(f"{n}={c}" for n,c in details) or "no collections"))
    raise RuntimeError("No populated Chroma collection was found. "+" | ".join(diagnostics))

def build_llm(key): return ChatOpenAI(model="glm-4.5-flash",openai_api_key=key,openai_api_base="https://api.z.ai/api/paas/v4",temperature=0.6,max_tokens=2000,extra_body={"thinking":{"type":"disabled"}})
def parse_json(raw):
    try:a=raw.find("{");b=raw.rfind("}")+1;return json.loads(raw[a:b]) if a>=0 and b>a else None
    except Exception:return None

def make_prompt(name,chart,scores,balance,context):
    facts={p:{"sign":v["sign"],"degree":round(v["degree"],4),"house":v["house"],"nakshatra":v["nakshatra"],"pada":v["pada"],"retrograde":v["retrograde"]} for p,v in chart["planets"].items()}
    return f'''Return ONLY valid JSON with keys executive_summary, vedic_interpretation, psychological_interpretation, ayurvedic_interpretation, convergence, practical_actions, vedic_practice, cautions. practical_actions is a list of objects with action, why, how, frequency. vedic_practice contains mantra, nama, practice, explanation.
Use the calculated Whole Sign house numbers exactly. Never calculate, infer or reassign houses. Do not diagnose illness, claim certainty or invent sources.
User: {name}. Presentation balance: {balance}/100. System: {chart['system']}; houses: {chart['house_system']}; Ascendant: {chart['ascendant']['sign']} {chart['ascendant']['degree']:.6f}. Moon: {chart['moon_nakshatra']} Pada {chart['moon_pada']}. Current Mahadasha: {chart['dasha']['current_lord']} {chart['dasha']['current_start']} to {chart['dasha']['current_end']}. Atmakaraka: {chart['atmakaraka']} in house {chart['planets'][chart['atmakaraka']]['house']}. Planets: {json.dumps(facts)}. Self-reflection: {json.dumps(scores)}. Retrieved context: {context}'''

def sidebar():
    with st.sidebar:
        st.markdown("### Configuration")
        try:secret=st.secrets.get("ZAI_API_KEY","")
        except Exception:secret=""
        key=secret or st.text_input("Z.ai API Key",type="password")
        with st.expander("Advanced settings"):balance=st.slider("Explanation balance",0,100,50)
        st.divider();st.markdown("### Profile");name=st.text_input("Name","Puneet");st.markdown("### Birth details")
        dob=st.date_input("Date of birth",date(1983,12,27),min_value=date(1900,1,1),max_value=date.today());tob=st.time_input("Time of birth",datetime.strptime("00:35","%H:%M").time());lat=st.number_input("Latitude",-90.0,90.0,31.64,format="%.4f");lon=st.number_input("Longitude",-180.0,180.0,76.13,format="%.4f");tz=st.number_input("Birthplace UTC offset",-12.0,14.0,5.5,0.25)
    return dict(key=key,balance=balance,name=name or "Seeker",dob=dob,tob=tob,lat=lat,lon=lon,tz=tz)

def assessment():
    st.markdown("## Personal Self-Reflection Profile");st.caption("Non-clinical reflective indicators. 0 = Never, 4 = Always.")
    groups={"Reflective Thinking":["I question the nature of reality and the self behind my thoughts.","I am comfortable holding uncertainty and paradox.","I reflect on purpose beyond material goals."],"Meaning & Direction":["I find meaning even in difficult experiences.","My life feels oriented towards a larger purpose.","I learn from my past rather than repeat it."],"Spiritual Perception":["I sense a connection with other living beings.","I experience the sacred in nature or everyday life.","I can observe my thoughts without being swept away."],"Inner Calm":["I can quiet my mind when I choose to.","I experience moments of mental stillness.","I remain steady during stressful situations."]}
    scores={};cols=st.columns(2)
    for i,(g,qs) in enumerate(groups.items()):
        with cols[i%2]:
            with st.container(border=True):
                st.markdown(f"#### {g}");vals=[st.slider(q,0,4,2,key=f"q_{i}_{j}") for j,q in enumerate(qs)];scores[g]=round(sum(vals)/(len(vals)*4)*100)
    return scores

def show_diagnostics():
    report=inspect_sqlite_database()
    with st.expander("Knowledge Base Diagnostics",expanded=True):
        st.caption("Read-only inspection. The database is not modified.")
        if report["status"]!="ok":st.error(report["message"]);return
        for item in report["reports"]:
            st.markdown(f"#### {item['path']}");c1,c2,c3=st.columns(3);c1.metric("File size",f"{item['size_bytes']/1024:.1f} KB");c2.metric("SQLite header","Valid" if item["sqlite_header"] else "Invalid");c3.metric("Tables",len(item["tables"]))
            if item["error"]:st.error(item["error"])
            st.markdown("**Table row counts**");st.dataframe([{"Table":k,"Rows":v} for k,v in item["row_counts"].items()],use_container_width=True,hide_index=True)
            st.markdown("**Collections table**");st.json(item["collections"] if item["collections"] else "No collection records")
            st.markdown("**Segments table**");st.json(item["segments"] if item["segments"] else "No segment records")

def show_chart(chart):
    st.markdown("## Calculated Vedic Profile");st.caption(f"{chart['system']} · {chart['house_system']} houses · Ayanamsa {chart['ayanamsa']:.4f}°")
    c1,c2,c3,c4=st.columns(4);c1.metric("Ascendant",chart["ascendant"]["sign"],fmt_deg(chart["ascendant"]["degree"]));c2.metric("Moon",f"{chart['moon_nakshatra']} · Pada {chart['moon_pada']}",chart["planets"]["Moon"]["sign"]);c3.metric("Current Mahadasha",chart["dasha"]["current_lord"],f"to {chart['dasha']['current_end']}");c4.metric("Atmakaraka",chart["atmakaraka"],f"House {chart['planets'][chart['atmakaraka']]['house']}")
    rows=[]
    for p in ["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn","Rahu","Ketu"]:
        v=chart["planets"][p];rows.append({"Body":p,"Sign":v["sign"],"Degree":fmt_deg(v["degree"]),"House":v["house"],"Nakshatra":v["nakshatra"],"Pada":v["pada"],"Motion":"Retrograde" if v["retrograde"] else "Direct"})
    with st.expander("Full sidereal planetary table",expanded=True):st.dataframe(rows,use_container_width=True,hide_index=True);st.caption(chart["karaka_method"])
    with st.expander("Vimshottari Mahadasha timeline",expanded=True):st.dataframe(chart["dasha"]["timeline"],use_container_width=True,hide_index=True)

def show_scores(scores):
    labels=list(scores);values=list(scores.values());labels+=labels[:1];values+=values[:1];fig=go.Figure(go.Scatterpolar(r=values,theta=labels,fill="toself",line=dict(color="#7c5cbf")));fig.update_layout(polar=dict(radialaxis=dict(visible=True,range=[0,100])),showlegend=False,paper_bgcolor="rgba(0,0,0,0)",height=330);st.plotly_chart(fig,use_container_width=True)

def show_result(result,raw):
    if not result:st.warning("Z.ai returned unstructured content.");st.markdown(raw);return
    for title,key in [("Executive Summary","executive_summary"),("Vedic Perspective","vedic_interpretation"),("Self-Reflection Perspective","psychological_interpretation"),("Ayurvedic Symbolic Perspective","ayurvedic_interpretation"),("Where the Systems Converge","convergence")]:
        with st.container(border=True):st.markdown(f"#### {title}");st.markdown(str(result.get(key,"No content returned.")))
    actions=result.get("practical_actions",[])
    if isinstance(actions,list):
        with st.container(border=True):
            st.markdown("#### Practical Actions")
            for i,a in enumerate(actions,1):
                if isinstance(a,dict):st.markdown(f"**{i}. {a.get('action','Action')}**  \n**Why:** {a.get('why','')}  \n**How:** {a.get('how','')}  \n**Frequency:** {a.get('frequency','')}")

def main():
    st.markdown("<h1 style='text-align:center'>Ancient Wisdom Synthesis</h1>",unsafe_allow_html=True);st.markdown("<p style='text-align:center;color:#9c9a93'>Lahiri sidereal astrology · deterministic Whole Sign houses · ancient texts</p>",unsafe_allow_html=True)
    cfg=sidebar();scores=assessment();show_diagnostics();st.divider()
    if st.button("Generate My Synthesis",type="primary",use_container_width=True):
        try:
            chart=calculate_chart(cfg["dob"],cfg["tob"],cfg["lat"],cfg["lon"],cfg["tz"]);st.session_state.chart=chart;st.session_state.scores=scores;docs=[];context=""
            try:
                retriever,cname,ccount=load_knowledge_base();docs=retriever.invoke(f"{chart['atmakaraka']} house {chart['planets'][chart['atmakaraka']]['house']} {chart['moon_nakshatra']} {chart['dasha']['current_lord']} Mahadasha");st.session_state.kb_status=f"Connected: {cname} ({ccount} records)";context="\n\n".join(f"[S{i}] {(d.metadata or {}).get('source','Unknown')}\n{d.page_content}" for i,d in enumerate(docs,1))
            except Exception as e:st.session_state.kb_status=f"Unavailable: {e}"
            if cfg["key"]:
                try:raw=build_llm(cfg["key"]).invoke(make_prompt(cfg["name"],chart,scores,cfg["balance"],context or "No knowledge-base context was available.")).content;st.session_state.raw=raw;st.session_state.result=parse_json(raw);st.session_state.zai_status="Connected"
                except Exception as e:st.session_state.raw="";st.session_state.result=None;st.session_state.zai_status=f"Unavailable: {e}"
            else:st.session_state.raw="";st.session_state.result=None;st.session_state.zai_status="API key missing"
            st.session_state.docs=docs
        except Exception as e:st.error(f"Astrology calculation failed: {e}")
    if "chart" in st.session_state:
        st.divider();show_chart(st.session_state.chart);a,b,c=st.columns(3);a.success("Astrology engine: Ready")
        (b.success if str(st.session_state.get("kb_status","")).startswith("Connected") else b.warning)(f"Knowledge base: {st.session_state.get('kb_status','Not tested')}")
        (c.success if st.session_state.get("zai_status")=="Connected" else c.warning)(f"Z.ai: {st.session_state.get('zai_status','Not tested')}")
        left,right=st.columns([2,1])
        with left:st.markdown("## Synthesis");show_result(st.session_state.get("result"),st.session_state.get("raw","")) if st.session_state.get("zai_status")=="Connected" else st.info("Calculated chart available; synthesis requires Z.ai.")
        with right:st.markdown("## Self-Reflection");show_scores(st.session_state.scores)

if __name__=="__main__":main()
