import json
import os
from datetime import date, datetime, timedelta, timezone

import chromadb
import plotly.graph_objects as go
import streamlit as st
import swisseph as swe
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_openai import ChatOpenAI

st.set_page_config(page_title="Ancient Wisdom Synthesis", page_icon="🕉️", layout="wide", initial_sidebar_state="expanded")
AI_MODE_OPTIONS=["Automatic","Offline","Z.ai Enhanced"]


st.markdown("""
<style>
.stApp{background:radial-gradient(circle at 15% 0%,#1d2147 0,#0f1226 38%,#090b18 100%);color:#f4efe6}.block-container{padding-top:1.4rem;max-width:1480px}
[data-testid="stSidebar"]{background:#12142b;border-right:1px solid #2a2d4a}
[data-testid="stMetric"]{background:linear-gradient(145deg,rgba(32,36,68,.96),rgba(20,23,48,.96));border:1px solid #373b63;border-radius:16px;padding:16px;box-shadow:0 10px 30px rgba(0,0,0,.20)}
[data-testid="stMetricLabel"]{color:#aaa6a0!important}[data-testid="stMetricValue"]{color:#d7b958!important}
.stButton>button{background:linear-gradient(135deg,#5d4b9d,#8c67d7);color:white;border:1px solid #9e83df;border-radius:24px;font-weight:650;min-height:2.7rem;box-shadow:0 8px 18px rgba(72,49,128,.28)}.stButton>button:hover{transform:translateY(-1px);border-color:#d7b958;color:white}
[data-testid="stChatMessage"]{background:#171a33;border:1px solid #2a2d4a;border-radius:12px}
h1,h2,h3,h4{color:#f4efe6;letter-spacing:.01em}p,li,.stMarkdown{color:#d6d0c7}[data-testid="stDataFrame"]{border:1px solid #34385f;border-radius:14px;overflow:hidden}[data-testid="stExpander"]{background:rgba(21,24,50,.78);border:1px solid #34385f;border-radius:14px}.stTabs [data-baseweb="tab-list"]{gap:8px}.stTabs [data-baseweb="tab"]{background:#181b38;border-radius:12px;padding:8px 16px}
.small-muted{color:#9c9a93;font-size:.9rem}.gold{color:#d7b958}
</style>
""", unsafe_allow_html=True)

# ------------------------------
# Astrology constants
# ------------------------------
SIGNS=["Aries","Taurus","Gemini","Cancer","Leo","Virgo","Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
NAKSHATRAS=["Ashwini","Bharani","Krittika","Rohini","Mrigashirsha","Ardra","Punarvasu","Pushya","Ashlesha","Magha","Purva Phalguni","Uttara Phalguni","Hasta","Chitra","Swati","Vishakha","Anuradha","Jyeshtha","Mula","Purvashadha","Uttarashadha","Shravana","Dhanishta","Shatabhisha","Purva Bhadrapada","Uttara Bhadrapada","Revati"]
NAKSHATRA_LORDS=["Ketu","Venus","Sun","Moon","Mars","Rahu","Jupiter","Saturn","Mercury"]
NAK_SIZE=360/27; PADA_SIZE=NAK_SIZE/4; FLAGS=swe.FLG_SWIEPH|swe.FLG_SIDEREAL
DASHA_SEQUENCE=["Ketu","Venus","Sun","Moon","Mars","Rahu","Jupiter","Saturn","Mercury"]
DASHA_YEARS={"Ketu":7,"Venus":20,"Sun":6,"Moon":10,"Mars":7,"Rahu":18,"Jupiter":16,"Saturn":19,"Mercury":17}
DAYS_PER_YEAR=365.2425
GEMSTONES={"Sun":"Ruby","Moon":"Pearl","Mars":"Red Coral","Mercury":"Emerald","Jupiter":"Yellow Sapphire","Venus":"Diamond / White Sapphire","Saturn":"Blue Sapphire","Rahu":"Hessonite (Gomed)","Ketu":"Cat's Eye"}

# Classical sign-condition rules used only for deterministic chart facts.
OWN_SIGNS={"Sun":["Leo"],"Moon":["Cancer"],"Mars":["Aries","Scorpio"],"Mercury":["Gemini","Virgo"],"Jupiter":["Sagittarius","Pisces"],"Venus":["Taurus","Libra"],"Saturn":["Capricorn","Aquarius"]}
EXALTATION={"Sun":("Aries",10.0),"Moon":("Taurus",3.0),"Mars":("Capricorn",28.0),"Mercury":("Virgo",15.0),"Jupiter":("Cancer",5.0),"Venus":("Pisces",27.0),"Saturn":("Libra",20.0)}
DEBILITATION={"Sun":("Libra",10.0),"Moon":("Scorpio",3.0),"Mars":("Cancer",28.0),"Mercury":("Pisces",15.0),"Jupiter":("Capricorn",5.0),"Venus":("Virgo",27.0),"Saturn":("Aries",20.0)}
# Conservative combustion orbs for application screening. This is not a strength score.
COMBUSTION_ORB={"Moon":12.0,"Mars":17.0,"Mercury":14.0,"Jupiter":11.0,"Venus":10.0,"Saturn":15.0}
SIGN_LORDS={"Aries":"Mars","Taurus":"Venus","Gemini":"Mercury","Cancer":"Moon","Leo":"Sun","Virgo":"Mercury","Libra":"Venus","Scorpio":"Mars","Sagittarius":"Jupiter","Capricorn":"Saturn","Aquarius":"Saturn","Pisces":"Jupiter"}

GRAHA_ASPECT_OFFSETS={"Sun":[7],"Moon":[7],"Mercury":[7],"Venus":[7],"Mars":[4,7,8],"Jupiter":[5,7,9],"Saturn":[3,7,10]}


# Framework-dependent correspondences. These are search/map aids, not medical facts.
CORRESPONDENCE_MAP={
 "Sun":{"dosha":"Pitta","chakra":"Manipura","element":"Fire"},
 "Moon":{"dosha":"Kapha / Vata context-dependent","chakra":"Anahata (framework-dependent)","element":"Water"},
 "Mars":{"dosha":"Pitta","chakra":"Muladhara / Manipura (framework-dependent)","element":"Fire"},
 "Mercury":{"dosha":"Vata / variable","chakra":"Vishuddha (framework-dependent)","element":"Earth / Air context-dependent"},
 "Jupiter":{"dosha":"Kapha","chakra":"Ajna / higher centres (framework-dependent)","element":"Ether"},
 "Venus":{"dosha":"Kapha","chakra":"Svadhisthana (framework-dependent)","element":"Water"},
 "Saturn":{"dosha":"Vata","chakra":"Muladhara (framework-dependent)","element":"Air"},
 "Rahu":{"dosha":"Vata / variable","chakra":"Framework-dependent","element":"Air / shadow principle"},
 "Ketu":{"dosha":"Vata-Pitta / variable","chakra":"Ajna / Sahasrara (framework-dependent)","element":"Fire / shadow principle"},
}

def sign_info(lon):
    lon%=360; idx=int(lon/30); return {"longitude":lon,"sign":SIGNS[idx],"degree":lon%30,"sign_index":idx}
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
def whole_sign_house(asc_idx,p_idx): return ((p_idx-asc_idx)%12)+1
def add_years(dt,years): return dt+timedelta(days=float(years)*DAYS_PER_YEAR)

def calculate_vimshottari(moon_longitude,birth_utc,as_of_utc):
    n=nak_info(moon_longitude)
    birth_lord=n["lord"]
    elapsed=DASHA_YEARS[birth_lord]*(n["position_within"]/NAK_SIZE)
    balance=DASHA_YEARS[birth_lord]-elapsed
    start_idx=DASHA_SEQUENCE.index(birth_lord)
    cursor=add_years(birth_utc,-elapsed)
    mahadashas=[]

    for _ in range(2):
        for offset in range(9):
            lord=DASHA_SEQUENCE[(start_idx+offset)%9]
            end=add_years(cursor,DASHA_YEARS[lord])
            mahadashas.append({"lord":lord,"start":cursor,"end":end})
            cursor=end

    current_md=next(x for x in mahadashas if x["start"]<=as_of_utc<x["end"])

    # Standard Vimshottari Antardasha sequence starts with the Mahadasha lord,
    # then follows the normal nine-lord Vimshottari order.
    md_lord=current_md["lord"]
    md_idx=DASHA_SEQUENCE.index(md_lord)
    ad_cursor=current_md["start"]
    antardashas=[]

    for offset in range(9):
        ad_lord=DASHA_SEQUENCE[(md_idx+offset)%9]
        ad_years=DASHA_YEARS[md_lord]*DASHA_YEARS[ad_lord]/120.0
        ad_end=add_years(ad_cursor,ad_years)
        antardashas.append({"lord":ad_lord,"start":ad_cursor,"end":ad_end})
        ad_cursor=ad_end

    current_ad=next(x for x in antardashas if x["start"]<=as_of_utc<x["end"])

    return {
        "birth_lord":birth_lord,
        "balance_at_birth_years":balance,
        "current_lord":current_md["lord"],
        "current_start":current_md["start"].date().isoformat(),
        "current_end":current_md["end"].date().isoformat(),
        "current_antardasha":current_ad["lord"],
        "antardasha_start":current_ad["start"].date().isoformat(),
        "antardasha_end":current_ad["end"].date().isoformat(),
        "timeline":[{"Mahadasha":x["lord"],"Start":x["start"].date().isoformat(),"End":x["end"].date().isoformat(),"Current":"Yes" if x is current_md else ""} for x in mahadashas[:9]],
        "antardasha_timeline":[{"Mahadasha":md_lord,"Antardasha":x["lord"],"Start":x["start"].date().isoformat(),"End":x["end"].date().isoformat(),"Current":"Yes" if x is current_ad else ""} for x in antardashas]
    }

def calculate_functional_lordship(asc_sign_index):
    rulership={planet:[] for planet in ["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn"]}
    house_signs={}
    for house in range(1,13):
        sign=SIGNS[(asc_sign_index+house-1)%12]
        lord=SIGN_LORDS[sign]
        house_signs[house]=sign
        rulership[lord].append(house)
    return rulership,house_signs

def functional_role_label(houses):
    # Descriptive only. It does not decide benefic/malefic or prescribe remedies.
    if not houses:return "No classical sign rulership"
    labels=[]
    if 1 in houses: labels.append("Lagna lord")
    if any(h in houses for h in (5,9)): labels.append("Trikona lord")
    if any(h in houses for h in (1,4,7,10)): labels.append("Kendra lord")
    if any(h in houses for h in (6,8,12)): labels.append("Dusthana lord")
    if any(h in houses for h in (2,11)): labels.append("Artha/wealth house lord")
    if 3 in houses: labels.append("3rd-house lord")
    return "; ".join(labels) if labels else "House lord"

def angular_distance(a,b):
    d=abs((a-b)%360.0)
    return min(d,360.0-d)

def planet_condition(name,planet,sun_longitude):
    sign=planet["sign"]
    degree=planet["degree"]
    condition=[]
    if name in OWN_SIGNS and sign in OWN_SIGNS[name]: condition.append("Own sign")
    if name in EXALTATION and sign==EXALTATION[name][0]:
        condition.append("Exaltation sign")
    if name in DEBILITATION and sign==DEBILITATION[name][0]:
        condition.append("Debilitation sign")
    if planet.get("retrograde") and name not in ("Rahu","Ketu"): condition.append("Retrograde")
    combust=False
    if name in COMBUSTION_ORB:
        separation=angular_distance(planet["longitude"],sun_longitude)
        combust=separation<=COMBUSTION_ORB[name]
        if combust: condition.append("Combust")
    else:
        separation=None
    return {
        "condition_labels":condition or ["No major condition flagged"],
        "own_sign":name in OWN_SIGNS and sign in OWN_SIGNS[name],
        "exaltation_sign":name in EXALTATION and sign==EXALTATION[name][0],
        "debilitation_sign":name in DEBILITATION and sign==DEBILITATION[name][0],
        "retrograde":bool(planet.get("retrograde")),
        "combust":combust,
        "sun_separation":round(separation,3) if separation is not None else None
    }

def detect_conjunctions(planets):
    names=["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn","Rahu","Ketu"]
    results=[]
    for i,name1 in enumerate(names):
        for name2 in names[i+1:]:
            p1,p2=planets[name1],planets[name2]
            if p1["sign_index"]==p2["sign_index"]:
                results.append({
                    "planet_1":name1,"planet_2":name2,"sign":p1["sign"],"house":p1["house"],
                    "separation_deg":round(angular_distance(p1["longitude"],p2["longitude"]),3)
                })
    return results

def graha_aspects(planets):
    results=[]
    classical=["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn"]
    for source in classical:
        occupied=planets[source]["house"]
        for count in GRAHA_ASPECT_OFFSETS[source]:
            target_house=((occupied+count-2)%12)+1
            targets=[name for name,p in planets.items() if p["house"]==target_house and name!=source]
            results.append({
                "source":source,"aspect_count":count,"source_house":occupied,
                "target_house":target_house,"target_planets":targets
            })
    return results

def planet_relationship_flags(name,chart_planets):
    received=[]
    for aspect in graha_aspects(chart_planets):
        if name in aspect["target_planets"]:
            received.append({"from":aspect["source"],"aspect":aspect["aspect_count"]})
    conjunct=[c for c in detect_conjunctions(chart_planets) if name in (c["planet_1"],c["planet_2"])]
    return received,conjunct

def remedy_decision_for_planet(name,planet,chart_planets,dasha,atmakaraka):
    """Conservative decision support, not a definitive Jyotish strength score."""
    reasons=[]
    cautions=[]
    score=0
    c=planet["condition"]
    houses=planet.get("rules_houses",[])

    if c.get("own_sign"):
        score+=2; reasons.append("placed in own sign")
    if c.get("exaltation_sign"):
        score+=3; reasons.append("placed in exaltation sign")
    if c.get("debilitation_sign"):
        score-=3; reasons.append("placed in debilitation sign")
    if c.get("combust"):
        score-=2; cautions.append("combustion screening flagged")
    if planet.get("retrograde") and name not in ("Rahu","Ketu"):
        cautions.append("retrograde; interpretation requires context")

    if 1 in houses: reasons.append("rules the Ascendant")
    if any(h in houses for h in (5,9)): reasons.append("rules a Trikona house")
    if any(h in houses for h in (6,8,12)): cautions.append("rules a Dusthana house; avoid simplistic strengthening")
    if name==atmakaraka: reasons.append("Atmakaraka; high personal relevance")
    if name==dasha.get("current_lord"): reasons.append("current Mahadasha lord")
    if name==dasha.get("current_antardasha"): reasons.append("current Antardasha lord")

    received,conjunct=planet_relationship_flags(name,chart_planets)
    if received: reasons.append(f"receives {len(received)} classical Graha aspect(s)")
    if conjunct: reasons.append(f"has {len(conjunct)} same-sign conjunction(s)")

    mixed_lordship=any(h in houses for h in (5,9,1)) and any(h in houses for h in (6,8,12))
    if mixed_lordship:
        action="Support carefully"
        cautions.append("mixed supportive/challenging house rulership")
    elif c.get("debilitation_sign") or c.get("combust"):
        action="Balance / pacify first"
    elif score>=2 and not any(h in houses for h in (6,8,12)):
        action="Support / strengthen cautiously"
    else:
        action="Support carefully"

    gemstone_status="Specialist Verification Required"
    low_risk=["simple devotional prayer", "ethical/behavioural upaya", "appropriate charity or service", "gentle meditation"]
    return {
        "planet":name,"decision":action,"reasons":reasons,"cautions":cautions,
        "traditional_gemstone":GEMSTONES.get(name,"Needs Verification"),
        "gemstone_status":gemstone_status,"low_risk_options":low_risk,
        "decision_basis":"Conservative screening only; not a Shadbala or complete functional-benefic determination."
    }

def build_remedy_decisions(planets,dasha,atmakaraka):
    return {name:remedy_decision_for_planet(name,p,planets,dasha,atmakaraka) for name,p in planets.items()}

def calculate_chart(dob,tob,lat,lon,tz):
    swe.set_sid_mode(swe.SIDM_LAHIRI,0,0); hour=tob.hour+tob.minute/60+tob.second/3600; jd=swe.julday(dob.year,dob.month,dob.day,hour-tz,swe.GREG_CAL)
    _,ascmc=swe.houses_ex(jd,lat,lon,b"W",swe.FLG_SIDEREAL); asc=sign_info(ascmc[0]); asc.update(nak_info(ascmc[0]))
    ids={"Sun":swe.SUN,"Moon":swe.MOON,"Mars":swe.MARS,"Mercury":swe.MERCURY,"Jupiter":swe.JUPITER,"Venus":swe.VENUS,"Saturn":swe.SATURN,"Rahu":swe.MEAN_NODE}
    planets={n:calc_body(jd,p) for n,p in ids.items()}; ketu=sign_info(planets["Rahu"]["longitude"]+180); ketu.update(nak_info(ketu["longitude"])); ketu["retrograde"]=True; planets["Ketu"]=ketu
    for v in planets.values(): v["house"]=whole_sign_house(asc["sign_index"],v["sign_index"])
    rulership,house_signs=calculate_functional_lordship(asc["sign_index"])
    sun_longitude=planets["Sun"]["longitude"]
    for name,v in planets.items():
        v["condition"]=planet_condition(name,v,sun_longitude)
        v["rules_houses"]=rulership.get(name,[])
        v["functional_role"]=functional_role_label(v["rules_houses"])
    conjunctions=detect_conjunctions(planets)
    aspects=graha_aspects(planets)
    ak=max(["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn"],key=lambda x:planets[x]["degree"])
    now=datetime.now(timezone.utc); birth_utc=(datetime(dob.year,dob.month,dob.day,tob.hour,tob.minute,tob.second)-timedelta(hours=tz)).replace(tzinfo=timezone.utc)
    dasha=calculate_vimshottari(planets["Moon"]["longitude"],birth_utc,now)
    remedy_decisions=build_remedy_decisions(planets,dasha,ak)
    return {"system":"Lahiri / Chitrapaksha sidereal zodiac","house_system":"Whole Sign","ayanamsa":swe.get_ayanamsa_ut(jd),"ascendant":asc,"planets":planets,"moon_nakshatra":planets["Moon"]["nakshatra"],"moon_pada":planets["Moon"]["pada"],"moon_lord":planets["Moon"]["lord"],"atmakaraka":ak,"atmakaraka_degree":planets[ak]["degree"],"karaka_method":"Seven-karaka system; Rahu and Ketu excluded","house_signs":house_signs,"conjunctions":conjunctions,"aspects":aspects,"dasha":dasha,"remedy_decisions":remedy_decisions,"analysis_date":now.date().isoformat()}

# ------------------------------
# Knowledge stores
# ------------------------------
@st.cache_resource(show_spinner=False)
def get_embeddings(): return HuggingFaceEmbeddings(model_name="paraphrase-MiniLM-L3-v2")

@st.cache_resource(show_spinner=False)
def load_ancient_wisdom():
    # Prefer the final directory build; fall back to older root DB while development continues.
    choices=["chroma_db","."]
    for path in choices:
        if not os.path.isfile(os.path.join(path,"chroma.sqlite3")): continue
        try:
            client=chromadb.PersistentClient(path=path)
            names=[]
            for c in client.list_collections():
                name=c.name if hasattr(c,"name") else str(c); count=client.get_collection(name).count(); names.append((name,count))
            populated=[x for x in names if x[1]>0]
            if not populated: continue
            preferred=next((x for x in populated if x[0]=="ancient_wisdom"),max(populated,key=lambda x:x[1]))
            store=Chroma(client=client,collection_name=preferred[0],embedding_function=get_embeddings())
            return store,preferred[0],preferred[1],path
        except Exception:
            continue
    return None,None,0,None

@st.cache_data(show_spinner=False)
def load_practitioner_records():
    candidates=["integrative_practitioner_knowledge_v1_2.json","additional_practitioner_talks_v1.json"]
    records=[]
    for fn in candidates:
        if not os.path.isfile(fn): continue
        try:
            data=json.load(open(fn,encoding="utf-8"))
            if isinstance(data,dict) and isinstance(data.get("records"),list): records.extend(data["records"])
            if isinstance(data,dict) and isinstance(data.get("speakers"),list):
                for s in data["speakers"]:
                    for r in s.get("records",[]):
                        item=dict(r); item.setdefault("speaker",s.get("speaker")); item.setdefault("tradition",s.get("tradition")); records.append(item)
        except Exception:
            pass
    dedup={r.get("id",f"row-{i}"):r for i,r in enumerate(records)}
    return list(dedup.values())

PLANET_ALIASES={
    "Sun":["sun","surya"],"Moon":["moon","chandra"],"Mars":["mars","mangal","kuja"],
    "Mercury":["mercury","budha"],"Jupiter":["jupiter","guru","brihaspati"],
    "Venus":["venus","shukra"],"Saturn":["saturn","shani"],"Rahu":["rahu","north node"],"Ketu":["ketu","south node"]
}
CHAKRA_ALIASES={
    "Muladhara":["muladhara","root chakra"],"Svadhisthana":["svadhisthana","sacral chakra"],
    "Manipura":["manipura","solar plexus"],"Anahata":["anahata","heart chakra"],
    "Vishuddha":["vishuddha","throat chakra"],"Ajna":["ajna","third eye"],
    "Sahasrara":["sahasrara","crown chakra"]
}
DOSHA_ALIASES={"Vata":["vata"],"Pitta":["pitta"],"Kapha":["kapha"]}
MANTRA_ALIASES={
    "Bija mantra":["bija","beej"],"Graha mantra":["graha mantra","planetary mantra","navagraha mantra"],
    "Gayatri":["gayatri"],"Japa":["japa","chanting","repetition"],"Diksha":["diksha","initiation"],
    "Stotra":["stotra","stotram"],"Siddha Kunjika":["siddha kunjika","kunjika"],
    "Shri Suktam":["shri suktam","sri suktam"],"Shri Yantra":["shri yantra","sri yantra"]
}
TOPIC_ALIASES={
    "gemstone":["gemstone","gem","sapphire","ruby","coral","emerald","pearl","gomed","hessonite","cat's eye"],
    "remedy":["remedy","remedies","upaya","upāya","pacify","pacification","strengthen","strengthening"],
    "Ayurveda":["ayurveda","ayurvedic"],"yoga":["yoga","asana","pranayama"],
    "Nakshatra":["nakshatra","lunar mansion"],"Atmakaraka":["atmakaraka","atma karaka"],
    "Mahadasha":["mahadasha","dasha"],"Antardasha":["antardasha","bhukti"]
}
TEACHER_NAMES=["Siddharth Banerjee","Harshdev Madhav","Vasant Lad","David Frawley","Robert Svoboda","Komilla Sutton","Sanjay Rath","Vic DiCara","Shubham Alock Singh","Dennis Harness","Ernst Wilhelm"]

def detect_entities(query):
    q=query.lower()
    def scan(mapping): return [name for name,aliases in mapping.items() if any(alias.lower() in q for alias in aliases)]
    return {
        "planets":scan(PLANET_ALIASES),"chakras":scan(CHAKRA_ALIASES),"doshas":scan(DOSHA_ALIASES),
        "mantra_types":scan(MANTRA_ALIASES),"topics":scan(TOPIC_ALIASES),
        "teachers":[name for name in TEACHER_NAMES if name.lower() in q]
    }

def record_search_text(record):
    fields=[record.get("speaker",""),record.get("topic",""),record.get("summary",""),record.get("explanation_text",""),record.get("video_title",""),record.get("title",""),record.get("tradition","")]
    fields.extend(record.get("tags",[]) if isinstance(record.get("tags"),list) else [])
    fields.extend(record.get("retrieval_terms",[]) if isinstance(record.get("retrieval_terms"),list) else [])
    return " ".join(map(str,fields)).lower()

def practitioner_search(query,limit=10,planet=None,topic=None):
    entities=detect_entities(query)
    terms=[x.lower() for x in query.replace("/"," ").replace("-"," ").split() if len(x)>2]
    scored=[]
    for r in load_practitioner_records():
        if r.get("rag_eligible") is False: continue
        text=record_search_text(r)
        score=0
        score+=sum(1 for t in terms if t in text)
        if query.lower() in text: score+=5
        for p in entities["planets"]:
            if any(a in text for a in PLANET_ALIASES[p]): score+=7
        for c in entities["chakras"]:
            if any(a in text for a in CHAKRA_ALIASES[c]): score+=7
        for d in entities["doshas"]:
            if d.lower() in text: score+=7
        for m in entities["mantra_types"]:
            if any(a in text for a in MANTRA_ALIASES[m]): score+=7
        for tpc in entities["topics"]:
            if any(a in text for a in TOPIC_ALIASES[tpc]): score+=5
        for teacher in entities["teachers"]:
            if r.get("speaker","").lower()==teacher.lower(): score+=12
        if planet and any(a in text for a in PLANET_ALIASES.get(planet,[planet.lower()])): score+=6
        if topic and topic.lower() in text: score+=3
        if r.get("exact_answer_eligible"): score+=2
        if score>0: scored.append((score,r))
    scored.sort(key=lambda x:(x[0],bool(x[1].get("exact_answer_eligible"))),reverse=True)
    return [r for _,r in scored[:limit]]


def expand_knowledge_query(query,focus="All"):
    e=detect_entities(query)
    parts=[query]
    for p in e["planets"]: parts.extend([p]+PLANET_ALIASES[p])
    for c in e["chakras"]: parts.extend([c]+CHAKRA_ALIASES[c])
    for d in e["doshas"]: parts.append(d)
    for m in e["mantra_types"]: parts.extend([m]+MANTRA_ALIASES[m])
    parts.extend(e["topics"])
    if focus!="All": parts.append(focus)
    return " ".join(dict.fromkeys(str(x) for x in parts if x))

def classical_search(query,k=6,source_type=None):
    store,name,count,path=load_ancient_wisdom()
    if store is None:return [],{"status":"unavailable","count":0}
    try:
        kwargs={"k":k}
        if source_type: kwargs["filter"]={"source_type":source_type}
        docs=store.as_retriever(search_kwargs=kwargs).invoke(query)
        return docs,{"status":"connected","count":count,"collection":name,"path":path}
    except Exception as e:
        return [],{"status":f"error: {e}","count":count}

# ------------------------------
# Source-grounded remedy retrieval
# ------------------------------
def build_personal_remedy_queries(chart):
    priority=[]
    for name,role in [
        (chart["dasha"]["current_lord"],"Mahadasha lord"),
        (chart["dasha"]["current_antardasha"],"Antardasha lord"),
        (chart["atmakaraka"],"Atmakaraka")
    ]:
        if name not in [x["planet"] for x in priority]:
            priority.append({"planet":name,"role":role})

    queries=[]
    for item in priority:
        name=item["planet"]
        p=chart["planets"][name]
        screen=chart["remedy_decisions"][name]
        queries.append({
            "planet":name,
            "role":item["role"],
            "query":(
                f"{name} {item['role']} house {p['house']} "
                f"rules houses {' '.join(map(str,p.get('rules_houses',[])))} "
                f"{p['sign']} {' '.join(p['condition']['condition_labels'])} "
                f"{screen['decision']} remedies mantra dana charity yoga meditation "
                f"Ayurveda gemstone strengthening pacification"
            )
        })
    return queries

def retrieve_personal_remedy_evidence(chart):
    queries=build_personal_remedy_queries(chart)
    classical=[]
    practitioner=[]
    seen_classical=set()
    seen_practitioner=set()

    for q in queries:
        docs,_=classical_search(q["query"],k=5)
        for d in docs:
            md=d.metadata or {}
            key=(md.get("book") or md.get("source"),md.get("chunk_id"),md.get("pdf_page"))
            if key not in seen_classical:
                seen_classical.add(key); classical.append(d)
        prs=practitioner_search(q["query"],limit=6,planet=q["planet"],topic="remedy")
        for r in prs:
            key=r.get("id") or json.dumps(r,sort_keys=True)
            if key not in seen_practitioner:
                seen_practitioner.add(key); practitioner.append(r)

    return queries,classical[:12],practitioner[:15]

def evidence_labels(docs,practitioners):
    return {
        "classical_count":len(docs),
        "practitioner_count":len(practitioners),
        "classical_books":sorted({(d.metadata or {}).get("book") or (d.metadata or {}).get("source") or "Unknown" for d in docs}),
        "practitioners":sorted({r.get("speaker","Unknown") for r in practitioners})
    }

# ------------------------------
# LLM and synthesis
# ------------------------------
def build_llm(key): return ChatOpenAI(model="glm-4.5-flash",openai_api_key=key,openai_api_base="https://api.z.ai/api/paas/v4",temperature=.45,max_tokens=2600,extra_body={"thinking":{"type":"disabled"}})
def get_api_key():
    try:
        return st.secrets.get("ZAI_API_KEY","")
    except Exception:
        return ""

def resolved_ai_mode(selected_mode):
    key=get_api_key()
    if selected_mode=="Offline":
        return "Offline",None
    if selected_mode=="Z.ai Enhanced":
        return ("Z.ai Enhanced",key) if key else ("Offline",None)
    return ("Z.ai Enhanced",key) if key else ("Offline",None)

def offline_knowledge_answer(query,docs,practitioners):
    lines=["### Offline Knowledge Result"]
    if not docs and not practitioners:
        return "No matching verified local knowledge was found. **Needs Verification.**"
    if docs:
        lines.append("\n#### Classical / official sources")
        for i,d in enumerate(docs[:5],1):
            md=d.metadata or {}
            title=md.get("book") or md.get("source","Unknown source")
            page=md.get("pdf_page","Needs Verification")
            text=" ".join(d.page_content.split())[:420]
            lines.append(f"**{i}. {title} · PDF page {page}**  ")
            lines.append(text+("…" if len(d.page_content)>420 else ""))
    if practitioners:
        lines.append("\n#### Practitioner perspectives")
        for i,r in enumerate(practitioners[:6],1):
            speaker=r.get("speaker","Unknown practitioner")
            topic=r.get("topic") or r.get("video_title") or r.get("title") or "Indexed teaching"
            summary=r.get("summary") or r.get("explanation_text") or "Needs Verification"
            lines.append(f"**{i}. {speaker} · {topic}**  ")
            lines.append(summary)
    lines.append("\n#### Offline note")
    lines.append("This answer is assembled directly from local indexed records without Z.ai synthesis. Source-specific interpretation remains separate from calculated chart facts.")
    return "\n".join(lines)

def offline_personal_remedy_report(chart,scores,docs,practitioners):
    d=chart["dasha"]
    priority=[]
    for name,role in [(d["current_lord"],"Mahadasha lord"),(d["current_antardasha"],"Antardasha lord"),(chart["atmakaraka"],"Atmakaraka")]:
        if name not in [x[0] for x in priority]:
            priority.append((name,role))
    lines=[
        "### Offline Personal Remedy Report",
        f"**Current timing:** {d['current_lord']} Mahadasha / {d['current_antardasha']} Antardasha",
        f"**Atmakaraka:** {chart['atmakaraka']} · House {chart['planets'][chart['atmakaraka']]['house']}",
        "\n#### Chart-based screening",
    ]
    for name,role in priority:
        r=chart.get("remedy_decisions",{}).get(name,{})
        planet=chart["planets"][name]
        houses=", ".join(map(str,planet.get("rules_houses",[]))) or "—"
        conditions="; ".join(planet["condition"]["condition_labels"])
        lines.append(f"**{name} · {role}: {r.get('decision','Support carefully')}**  ")
        lines.append(f"{planet['sign']} · House {planet['house']} · Rules houses {houses} · {conditions}")
        if r.get("cautions"):
            lines.append("Cautions: "+"; ".join(r["cautions"]))
        gem=r.get("traditional_gemstone",GEMSTONES.get(name,"Needs Verification"))
        lines.append(f"Traditional gemstone correspondence: **{gem}** · **Specialist Verification Required**")
    lines.append("\n#### Retrieved local evidence")
    lines.append(f"Classical/official passages: **{len(docs)}** · Practitioner records: **{len(practitioners)}**")
    if docs:
        for doc in docs[:5]:
            md=doc.metadata or {}
            lines.append(f"- {md.get('book') or md.get('source','Unknown')} · PDF page {md.get('pdf_page','Needs Verification')}")
    if practitioners:
        for r in practitioners[:6]:
            label=r.get("topic") or r.get("video_title") or r.get("title") or "Indexed teaching"
            lines.append(f"- {r.get('speaker','Unknown')} · {label}")
    lines.append("\n**Offline safety rule:** low-risk devotional, reflective and behavioural practices may be explored from retrieved sources. Gemstones, herbs, fasting, advanced pranayama, Bija/Tantric practices and medical claims remain subject to verification or specialist guidance.")
    return "\n".join(lines)

def source_context(docs,practitioners):
    parts=[]
    for i,d in enumerate(docs,1):
        md=d.metadata or {}; parts.append(f"[C{i}] Classical/official source: {md.get('book') or md.get('source','Unknown')} | PDF page: {md.get('pdf_page','Needs Verification')} | chunk: {md.get('chunk_id','')}\n{d.page_content}")
    for i,r in enumerate(practitioners,1):
        parts.append(f"[P{i}] Practitioner: {r.get('speaker','Unknown')} | Topic: {r.get('topic','')} | Source: {r.get('video_title') or r.get('title','')} | Timestamp: {r.get('timestamp_start','')}–{r.get('timestamp_end','')} | Verification: {r.get('verification_status','')} | Safety: {r.get('safety_level',r.get('safety',''))}\n{r.get('explanation_text') or r.get('summary','')}")
    return "\n\n".join(parts)

def answer_knowledge(query,key,docs,practitioners,ai_mode="Automatic"):
    resolved,key2=resolved_ai_mode(ai_mode)
    if resolved=="Offline": return offline_knowledge_answer(query,docs,practitioners)
    key=key2
    context=source_context(docs,practitioners)
    prompt=f'''You are the evidence-aware knowledge engine for Ancient Wisdom Synthesis. Answer: {query}\n\nUse ONLY the supplied context for source-specific claims. Clearly distinguish: Classical/official sources; Practitioner interpretation; Modern evidence/safety; and Needs Verification. If traditions disagree, say so. Do not turn symbolic correspondences into medical causation. Gemstones strengthen a planetary principle in traditional practice and must not be automatically prescribed. Advanced bija/tantric practices may require guidance or diksha.\n\nCONTEXT:\n{context}\n\nGive a concise but useful answer with headings: Direct answer; Classical / source perspective; Practitioner perspectives; Practical application; Safety and evidence; Sources used.'''
    return build_llm(key).invoke(prompt).content

def answer_personal_remedies(chart,scores,key,docs,practitioners,ai_mode="Automatic"):
    resolved,key2=resolved_ai_mode(ai_mode)
    if resolved=="Offline": return offline_personal_remedy_report(chart,scores,docs,practitioners)
    key=key2
    facts={p:{"sign":v["sign"],"degree":round(v["degree"],3),"house":v["house"],"nakshatra":v["nakshatra"],"pada":v["pada"],"retrograde":v["retrograde"],"condition":v["condition"],"rules_houses":v["rules_houses"],"functional_role":v["functional_role"]} for p,v in chart["planets"].items()}
    context=source_context(docs,practitioners)
    prompt=f'''Create a personalised, source-grounded remedy report. Calculated facts are locked and must not be recalculated.\nChart: Ascendant {chart['ascendant']['sign']}; Atmakaraka {chart['atmakaraka']} house {chart['planets'][chart['atmakaraka']]['house']}; Moon {chart['moon_nakshatra']} pada {chart['moon_pada']}; current Mahadasha {chart['dasha']['current_lord']} {chart['dasha']['current_start']} to {chart['dasha']['current_end']}; current Antardasha {chart['dasha']['current_antardasha']} {chart['dasha']['antardasha_start']} to {chart['dasha']['antardasha_end']}; planets {json.dumps(facts)}. Self-reflection: {json.dumps(scores)}.\n\nCONTEXT:\n{context}\n\nRules: separate strengthening from pacification/balancing. Never recommend a gemstone merely because its planet is active. Gemstones must be labelled Specialist Verification Required. Sign condition, retrogression, combustion and Antardasha are supplied, but functional house rulership is supplied descriptively, but conjunctions and classical Parashari aspects are supplied, but a conservative remedy-screening result is supplied. Treat it as a screening decision rather than a complete Shadbala or universal benefic/malefic verdict. Do not override it without source evidence. Do not prescribe herbs, bhasma, fasting, acupuncture or medical treatment. Advanced bija/tantric practices require guidance.\n\nEvidence rule: recommend a specific named remedy only when the supplied context supports it. If a specific mantra, donation, gemstone, fasting practice, herb, yantra, puja, pranayama or ritual is not supported in context, say Needs Verification rather than inventing it. Prefer source-supported low-risk remedies. For each recommended remedy explicitly state: Purpose (strengthen, balance/pacify, or supportive); Why it fits this chart; Source basis; How to practise only if source-supported; Risk level.

Return sections: Current priority; Why this matters; Recommended remedies ranked 1-5; Mantra/devotional options; Ayurveda/yoga supportive options; Gemstone information with verification warning; What to avoid; Classical sources; Practitioner perspectives; Modern evidence/safety; Needs Verification.'''
    return build_llm(key).invoke(prompt).content

# ------------------------------
# UI helpers
# ------------------------------
def sidebar_profile():
    with st.sidebar:
        st.markdown("### Personal Profile")
        name=st.text_input("Name","Puneet"); dob=st.date_input("Date of birth",date(1983,12,27),min_value=date(1900,1,1),max_value=date.today()); tob=st.time_input("Time of birth",datetime.strptime("00:35","%H:%M").time()); lat=st.number_input("Latitude",-90.0,90.0,31.64,format="%.4f"); lon=st.number_input("Longitude",-180.0,180.0,76.13,format="%.4f"); tz=st.number_input("Birthplace UTC offset",-12.0,14.0,5.5,0.25)
        st.divider()
        st.markdown("### AI Mode")
        ai_mode=st.selectbox("Mode",AI_MODE_OPTIONS,index=0,help="Automatic uses Z.ai when configured and otherwise falls back to Offline. Offline never calls Z.ai. Z.ai Enhanced requires a configured secret and falls back safely if unavailable.")
        resolved,_=resolved_ai_mode(ai_mode)
        if resolved=="Offline": st.info("Offline Knowledge Mode active")
        else: st.success("Z.ai Enhanced Mode active")
        st.caption("Lahiri/Chitrapaksha · Whole Sign houses")
    return dict(name=name or "Seeker",dob=dob,tob=tob,lat=lat,lon=lon,tz=tz,ai_mode=ai_mode)

def assessment():
    groups={"Reflective Thinking":["I question the nature of reality and the self behind my thoughts.","I am comfortable holding uncertainty and paradox.","I reflect on purpose beyond material goals."],"Meaning & Direction":["I find meaning even in difficult experiences.","My life feels oriented towards a larger purpose.","I learn from my past rather than repeat it."],"Spiritual Perception":["I sense a connection with other living beings.","I experience the sacred in nature or everyday life.","I can observe my thoughts without being swept away."],"Inner Calm":["I can quiet my mind when I choose to.","I experience moments of mental stillness.","I remain steady during stressful situations."]}
    scores={}; cols=st.columns(2)
    for i,(g,qs) in enumerate(groups.items()):
        with cols[i%2]:
            with st.container(border=True):
                st.markdown(f"#### {g}"); vals=[st.slider(q,0,4,2,key=f"q_{i}_{j}") for j,q in enumerate(qs)]; scores[g]=round(sum(vals)/(len(vals)*4)*100)
    return scores

def show_chart(chart):
    c1,c2,c3,c4=st.columns(4); c1.metric("Ascendant",chart["ascendant"]["sign"],fmt_deg(chart["ascendant"]["degree"])); c2.metric("Moon",f"{chart['moon_nakshatra']} · Pada {chart['moon_pada']}",chart["planets"]["Moon"]["sign"]); c3.metric("Mahadasha",chart["dasha"]["current_lord"],f"to {chart['dasha']['current_end']}"); c4.metric("Antardasha",chart["dasha"]["current_antardasha"],f"to {chart['dasha']['antardasha_end']}")
    c5,c6=st.columns(2); c5.metric("Atmakaraka",chart["atmakaraka"],f"House {chart['planets'][chart['atmakaraka']]['house']}"); c6.metric("Current Dasha",f"{chart['dasha']['current_lord']} / {chart['dasha']['current_antardasha']}",f"AD from {chart['dasha']['antardasha_start']}")
    rows=[]
    for p in ["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn","Rahu","Ketu"]:
        v=chart["planets"][p]; m=CORRESPONDENCE_MAP[p]; rows.append({"Body":p,"Sign":v["sign"],"Degree":fmt_deg(v["degree"]),"House":v["house"],"Nakshatra":v["nakshatra"],"Pada":v["pada"],"Condition":"; ".join(v["condition"]["condition_labels"]),"Rules houses":", ".join(map(str,v["rules_houses"])) or "—","Functional role":v["functional_role"],"Dosha map":m["dosha"],"Chakra map":m["chakra"],"Traditional gem":GEMSTONES[p]})
    with st.expander("Planet, house and correspondence map",expanded=True): st.dataframe(rows,use_container_width=True,hide_index=True); st.caption("Dosha/chakra mappings are framework-dependent correspondences, not medical diagnoses or universal classical consensus.")
    with st.expander("Conjunctions and Graha Drishti",expanded=False):
        st.markdown("#### Same-sign conjunctions")
        if chart["conjunctions"]:
            st.dataframe(chart["conjunctions"],use_container_width=True,hide_index=True)
        else:
            st.caption("No same-sign conjunctions detected.")
        st.markdown("#### Classical Graha aspects")
        aspect_rows=[]
        for a in chart["aspects"]:
            aspect_rows.append({
                "Planet":a["source"],"From house":a["source_house"],
                "Aspect":f"{a['aspect_count']}th","To house":a["target_house"],
                "Planets in target":", ".join(a["target_planets"]) or "—"
            })
        st.dataframe(aspect_rows,use_container_width=True,hide_index=True)
        st.caption("Classical Parashari Graha Drishti: all seven visible Grahas aspect the 7th; Mars additionally 4th/8th, Jupiter 5th/9th, Saturn 3rd/10th. Rahu/Ketu aspects are deliberately not assumed because lineage conventions differ.")

    with st.expander("Vimshottari Mahadasha timeline"):
        st.dataframe(chart["dasha"]["timeline"],use_container_width=True,hide_index=True)
    with st.expander(f"Antardasha timeline within {chart['dasha']['current_lord']} Mahadasha",expanded=True):
        st.dataframe(chart["dasha"]["antardasha_timeline"],use_container_width=True,hide_index=True)

def status_bar(ai_mode="Automatic"):
    store,name,count,path=load_ancient_wisdom(); prac=len(load_practitioner_records()); a,b,c=st.columns(3)
    if store:a.success(f"Ancient Wisdom: {count:,} records")
    else:a.warning("Ancient Wisdom: waiting for final Chroma DB")
    b.success(f"Practitioner index: {prac} records" if prac else "Practitioner JSON: add files to repository")
    resolved,_=resolved_ai_mode(ai_mode)
    c.success(f"AI Mode: {resolved}")

def render_sources(docs,practitioners):
    with st.expander("Sources used",expanded=False):
        if docs:
            st.markdown("#### Classical / official")
            for i,d in enumerate(docs,1):
                md=d.metadata or {}; st.markdown(f"**C{i}. {md.get('book') or md.get('source','Unknown')}** · PDF page {md.get('pdf_page','Needs Verification')} · `{md.get('chunk_id','')}`\n\n{d.page_content[:450]}…")
        if practitioners:
            st.markdown("#### Practitioner interpretation")
            for i,r in enumerate(practitioners,1): st.markdown(f"**P{i}. {r.get('speaker','Unknown')}** · {r.get('topic','')} · {r.get('timestamp_start','')} {r.get('verification_status','')}\n\n{r.get('summary','')}")

# ------------------------------
# App modes
# ------------------------------
def personal_mode(cfg):
    st.header("My Reading")
    st.caption("Calculated chart → source retrieval → personalised interpretation and remedies")
    scores=assessment()
    if st.button("Generate My Reading & Remedies",type="primary",use_container_width=True):
        chart=calculate_chart(cfg["dob"],cfg["tob"],cfg["lat"],cfg["lon"],cfg["tz"]); st.session_state.personal_chart=chart; st.session_state.personal_scores=scores
        remedy_queries,docs,practitioners=retrieve_personal_remedy_evidence(chart)
        st.session_state.personal_remedy_queries=remedy_queries
        st.session_state.personal_docs=docs
        st.session_state.personal_prac=practitioners
        st.session_state.personal_evidence=evidence_labels(docs,practitioners)
        st.session_state.personal_answer=answer_personal_remedies(chart,scores,get_api_key(),docs,practitioners,cfg.get("ai_mode","Automatic"))
    if "personal_chart" in st.session_state:
        show_chart(st.session_state.personal_chart)
        ev=st.session_state.get("personal_evidence",{})
        if ev:
            e1,e2,e3=st.columns(3)
            e1.metric("Classical evidence",ev.get("classical_count",0),"retrieved passages")
            e2.metric("Practitioner evidence",ev.get("practitioner_count",0),"structured records")
            e3.metric("Teachers represented",len(ev.get("practitioners",[])),", ".join(ev.get("practitioners",[])[:3]) or "—")
        st.markdown("## Personal Remedy Plan")
        if st.session_state.get("personal_answer"): st.markdown(st.session_state.personal_answer)
        else: st.info("Offline report generated from local calculations and indexed evidence. Select Z.ai Enhanced when a configured API is available for richer natural-language synthesis.")
        render_sources(st.session_state.get("personal_docs",[]),st.session_state.get("personal_prac",[]))

def search_mode(ai_mode="Automatic"):
    st.header("Search Wisdom")
    st.caption("Search exact concepts, classical texts and practitioner interpretations without entering birth data.")
    c1,c2=st.columns([1,1])
    with c1: category=st.selectbox("Focus",["All","Planets","Chakras","Ayurveda","Mantra","Remedies","Gemstones","Nakshatras","Yoga"])
    with c2: source_scope=st.selectbox("Sources",["All sources","Classical / official","Practitioner"])
    query=st.text_input("Ask or search",placeholder="e.g. Saturn Vata remedies, Siddha Kunjika Diksha, Mars chakra, Jupiter gemstone")
    if query.strip():
        entities=detect_entities(query)
        labels=[]
        for label,items in [("Planet",entities["planets"]),("Chakra",entities["chakras"]),("Dosha",entities["doshas"]),("Mantra",entities["mantra_types"]),("Topic",entities["topics"]),("Teacher",entities["teachers"])]:
            if items: labels.append(f"**{label}:** {', '.join(items)}")
        if labels: st.caption(" · ".join(labels))
    if st.button("Search Knowledge",type="primary",use_container_width=True,disabled=not query.strip()):
        expanded=expand_knowledge_query(query,category)
        docs=[]; practitioners=[]
        if source_scope in ("All sources","Classical / official"): docs,_=classical_search(expanded,8)
        if source_scope in ("All sources","Practitioner"): practitioners=practitioner_search(expanded,12)
        st.session_state.search_docs=docs; st.session_state.search_prac=practitioners
        if source_scope=="All sources": st.session_state.search_answer=answer_knowledge(query,get_api_key(),docs,practitioners,ai_mode)
        elif source_scope=="Classical / official": st.session_state.search_answer=answer_knowledge(query,get_api_key(),docs,[],ai_mode)
        else: st.session_state.search_answer=answer_knowledge(query,get_api_key(),[],practitioners,ai_mode)
    if st.session_state.get("search_answer"):
        st.markdown("## Answer"); st.markdown(st.session_state.search_answer)
        docs=st.session_state.get("search_docs",[]); prs=st.session_state.get("search_prac",[])
        s1,s2=st.columns(2); s1.metric("Classical passages",len(docs)); s2.metric("Practitioner records",len(prs))
        render_sources(docs,prs)

def map_mode(ai_mode="Automatic"):
    st.header("Explore Map")
    st.caption("Map a Graha to chart meaning, dosha/chakra frameworks, mantra, remedies and source evidence.")
    c1,c2=st.columns([1,1])
    with c1: planet=st.selectbox("Planet / Graha",list(CORRESPONDENCE_MAP.keys()))
    with c2: map_focus=st.selectbox("Explore",["Overview","Ayurveda","Chakra","Mantra","Remedies","Gemstone"])
    v=CORRESPONDENCE_MAP[planet]
    m1,m2,m3,m4=st.columns(4); m1.metric("Planet",planet); m2.metric("Ayurvedic tendency",v["dosha"]); m3.metric("Chakra",v["chakra"]); m4.metric("Traditional gemstone",GEMSTONES[planet])
    st.warning("Dosha/chakra correspondences vary by lineage. Gemstone correspondence is informational and does not establish suitability for an individual chart.")
    query=expand_knowledge_query(f"{planet} {v['dosha']} {v['chakra']} {map_focus} mantra remedies gemstone",map_focus)
    docs,_=classical_search(query,7); practitioners=practitioner_search(query,12,planet=planet)
    if st.button("Explain This Map",type="primary",use_container_width=True):
        st.session_state.map_answer=answer_knowledge(f"Explain {planet} with focus on {map_focus}, including relevant dosha/chakra/mantra/remedy correspondences and disagreements",get_api_key(),docs,practitioners,ai_mode)
    if st.session_state.get("map_answer"): st.markdown("### Mapped explanation"); st.markdown(st.session_state.map_answer)
    st.markdown("### Practitioner records")
    if practitioners:
        for r in practitioners[:8]:
            with st.container(border=True):
                st.markdown(f"**{r.get('speaker','Unknown')} · {r.get('topic','')}**")
                st.markdown(r.get('summary',''))
                st.caption(f"{r.get('verification_status','')} · {r.get('timestamp_start','')}")
    else: st.info("No practitioner records matched this map.")
    render_sources(docs,practitioners)

def sources_mode():
    st.header("Explore Sources")
    st.caption("Browse what the app knows before asking it to synthesise an answer.")
    store,name,count,path=load_ancient_wisdom()
    practitioner=load_practitioner_records()

    a,b,c=st.columns(3)
    a.metric("Classical / official records",f"{count:,}" if count else "0")
    b.metric("Practitioner records",len(practitioner))
    c.metric("Practitioners",len({r.get("speaker") for r in practitioner if r.get("speaker")}))

    tab1,tab2=st.tabs(["Classical & Official","Practitioner Teachers"])
    with tab1:
        if store is None:
            st.info("Final ancient_wisdom database is not installed yet.")
        else:
            st.markdown(f"**Collection:** `{name}`")
            st.markdown(f"**Database location:** `{path}`")
            st.caption("Use Search Wisdom for semantic searching. This panel confirms the active authoritative collection.")
            q=st.text_input("Preview classical source",placeholder="e.g. Jupiter remedies, Vata, mantra",key="source_preview")
            if q:
                docs,_=classical_search(q,6)
                for i,d in enumerate(docs,1):
                    md=d.metadata or {}
                    with st.container(border=True):
                        st.markdown(f"**{i}. {md.get('book') or md.get('source','Unknown')}**")
                        st.caption(f"PDF page {md.get('pdf_page','Needs Verification')} · {md.get('source_type','')} · {md.get('chunk_id','')}")
                        st.markdown(d.page_content[:700]+("…" if len(d.page_content)>700 else ""))
    with tab2:
        teachers=sorted({r.get("speaker") for r in practitioner if r.get("speaker")})
        if not teachers:
            st.info("Practitioner JSON files are not installed yet.")
        else:
            teacher=st.selectbox("Teacher",teachers)
            rows=[r for r in practitioner if r.get("speaker")==teacher]
            exact=[r for r in rows if r.get("exact_answer_eligible")]
            t1,t2,t3=st.columns(3)
            t1.metric("Indexed records",len(rows)); t2.metric("Exact-answer eligible",len(exact)); t3.metric("Needs deeper verification",len(rows)-len(exact))
            for r in rows[:30]:
                with st.expander(r.get("topic") or r.get("video_title") or r.get("title") or "Indexed teaching"):
                    st.markdown(r.get("summary") or r.get("explanation_text") or "No detailed summary available.")
                    meta=[]
                    if r.get("timestamp_start"): meta.append(f"Timestamp {r.get('timestamp_start')}–{r.get('timestamp_end','')}")
                    if r.get("verification_status"): meta.append(r.get("verification_status"))
                    if r.get("safety_level"): meta.append(f"Safety: {r.get('safety_level')}")
                    st.caption(" · ".join(meta))
                    if r.get("source_url"): st.markdown(f"Source URL: {r.get('source_url')}")

def remedies_mode(cfg):
    st.header("My Remedies")
    st.caption("Chart-derived traditional options with source hierarchy and safety controls.")
    if "personal_chart" not in st.session_state:
        st.info("Generate My Reading first. The remedy engine will use that calculated chart rather than generic planet-to-remedy rules.")
        return
    chart=st.session_state.personal_chart; show_chart(chart)
    st.markdown("### Chart-based remedy screening")
    focus=[]
    priority_names=[]
    for name in [chart["dasha"]["current_lord"],chart["dasha"]["current_antardasha"],chart["atmakaraka"]]:
        if name not in priority_names: priority_names.append(name)
    for name in priority_names:
        r=chart["remedy_decisions"][name]
        focus.append({"Planet":name,"Screening":r["decision"],"Why":"; ".join(r["reasons"]) or "No special factor","Cautions":"; ".join(r["cautions"]) or "—","Traditional gemstone":r["traditional_gemstone"],"Gemstone status":r["gemstone_status"]})
    st.dataframe(focus,use_container_width=True,hide_index=True)
    st.markdown("### Remedy policy")
    st.markdown("""
- Low-risk devotional, reflective and behavioural practices are prioritised.
- Ayurveda/yoga suggestions are supportive wellness practices, not medical treatment.
- Bija/Tantric practices may require lineage guidance or Diksha.
- Antardasha is now included in the timing context.
- Sign condition, retrogression and combustion screening are now included.
- Functional house rulership is now displayed descriptively.
- Same-sign conjunctions and classical Parashari Graha aspects are now included.
- A first conservative **support / balance / strengthen-cautiously** screening is now included for the Mahadasha lord, Antardasha lord and Atmakaraka.
- Gemstones remain **Specialist Verification Required** because this is not yet a complete Shadbala or full classical strength determination.
""")
    ev=st.session_state.get("personal_evidence",{})
    if ev:
        st.caption("Evidence base used: "+", ".join(ev.get("classical_books",[])[:5])+(" · Practitioners: "+", ".join(ev.get("practitioners",[])[:5]) if ev.get("practitioners") else ""))
    if st.session_state.get("personal_answer"): st.markdown(st.session_state.personal_answer)

# ------------------------------
# Main
# ------------------------------
def main():
    st.markdown("""
    <div style="padding:24px 28px;border:1px solid #3d416c;border-radius:22px;background:linear-gradient(135deg,rgba(35,39,78,.96),rgba(17,19,42,.92));box-shadow:0 18px 55px rgba(0,0,0,.28);margin-bottom:18px">
      <div style="color:#d7b958;font-size:.82rem;font-weight:700;letter-spacing:.16em;text-transform:uppercase">Personal Wisdom & Remedy Engine</div>
      <h1 style="margin:.3rem 0 .25rem 0;font-size:2.3rem">Ancient Wisdom Synthesis</h1>
      <p style="margin:0;color:#bdb7c9;font-size:1.04rem">Calculated Vedic astrology, classical sources, practitioner perspectives and modern safety context.</p>
    </div>
    """,unsafe_allow_html=True)
    cfg=sidebar_profile(); status_bar()
    st.caption("Source hierarchy: calculated chart facts → classical/official texts → practitioner interpretations → modern evidence/safety. Unsupported specifics are labelled Needs Verification.")
    st.divider()
    tabs=st.tabs(["My Reading","Search Wisdom","Explore Map","Explore Sources","My Remedies"])
    with tabs[0]: personal_mode(cfg)
    with tabs[1]: search_mode(cfg.get("ai_mode","Automatic"))
    with tabs[2]: map_mode(cfg.get("ai_mode","Automatic"))
    with tabs[3]: sources_mode()
    with tabs[4]: remedies_mode(cfg)

if __name__=="__main__": main()
