import json
import os
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import chromadb
import streamlit as st
import swisseph as swe
from timezonefinder import TimezoneFinder
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_openai import ChatOpenAI

st.set_page_config(
    page_title="Ancient Wisdom Synthesis",
    page_icon="🕉️",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_VERSION = "AWS v1.42 Locked Rulership and Chart Validation"
EMBEDDING_MODEL = "paraphrase-MiniLM-L3-v2"
COLLECTION_NAME = "ancient_wisdom"
PAGES = ["Home", "Ask", "My Reading", "My Remedies", "Explore"]
MODES = ["Trusted Library", "Deep Research", "Offline"]
DEPTHS = ["Simple", "Detailed", "Advanced"]

st.markdown(
    """
<style>
.stApp{background:radial-gradient(circle at 15% 0%,#202653 0,#11152d 38%,#090b18 100%);color:#f5f0e8}
.block-container{max-width:1480px;padding-top:1rem;padding-bottom:4rem}
[data-testid='stSidebar']{background:#11142b;border-right:1px solid #303558}
.stButton>button{background:linear-gradient(135deg,#5d4ba0,#8d68d8);color:white;border:1px solid #9d83df;border-radius:22px;font-weight:650}
.hero{padding:14px 20px;border:1px solid #41466f;border-radius:18px;background:linear-gradient(135deg,rgba(37,43,84,.97),rgba(17,20,43,.94));margin-bottom:12px}
.hero h1{font-size:1.75rem!important;margin:.2rem 0}.eyebrow{color:#e2c45f;font-size:.7rem;font-weight:760;letter-spacing:.14em}
.subtitle{color:#bbb5c8;font-size:.94rem}.choice{padding:16px;border:1px solid #3a3f67;border-radius:16px;background:#171a36;min-height:125px}
h1,h2,h3,h4{color:#f6f0e7}
</style>
""",
    unsafe_allow_html=True,
)

SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
NAKS = ["Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashirsha", "Ardra", "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha", "Mula", "Purvashadha", "Uttarashadha", "Shravana", "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"]
NAK_LORDS = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
NAK_SIZE = 360 / 27
PADA_SIZE = NAK_SIZE / 4
DSEQ = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]
DYEARS = {"Ketu": 7, "Venus": 20, "Sun": 6, "Moon": 10, "Mars": 7, "Rahu": 18, "Jupiter": 16, "Saturn": 19, "Mercury": 17}
LORDS = {"Aries": "Mars", "Taurus": "Venus", "Gemini": "Mercury", "Cancer": "Moon", "Leo": "Sun", "Virgo": "Mercury", "Libra": "Venus", "Scorpio": "Mars", "Sagittarius": "Jupiter", "Capricorn": "Saturn", "Aquarius": "Saturn", "Pisces": "Jupiter"}
OWN = {"Sun": ["Leo"], "Moon": ["Cancer"], "Mars": ["Aries", "Scorpio"], "Mercury": ["Gemini", "Virgo"], "Jupiter": ["Sagittarius", "Pisces"], "Venus": ["Taurus", "Libra"], "Saturn": ["Capricorn", "Aquarius"]}
EXALT = {"Sun": "Aries", "Moon": "Taurus", "Mars": "Capricorn", "Mercury": "Virgo", "Jupiter": "Cancer", "Venus": "Pisces", "Saturn": "Libra"}
DEBIL = {"Sun": "Libra", "Moon": "Scorpio", "Mars": "Cancer", "Mercury": "Pisces", "Jupiter": "Capricorn", "Venus": "Virgo", "Saturn": "Aries"}
COMBUST = {"Moon": 12, "Mars": 17, "Mercury": 14, "Jupiter": 11, "Venus": 10, "Saturn": 15}
ASPECTS = {"Sun": [7], "Moon": [7], "Mercury": [7], "Venus": [7], "Mars": [4, 7, 8], "Jupiter": [5, 7, 9], "Saturn": [3, 7, 10]}
FLAGS = swe.FLG_SWIEPH | swe.FLG_SIDEREAL


def sign_info(lon):
    lon %= 360
    i = int(lon / 30)
    return {"longitude": lon, "sign": SIGNS[i], "degree": lon % 30, "sign_index": i, "sign_lord": LORDS[SIGNS[i]]}


def nak_info(lon):
    lon %= 360
    i = min(int(lon / NAK_SIZE), 26)
    within = lon - i * NAK_SIZE
    lord = NAK_LORDS[i % 9]
    return {"nakshatra": NAKS[i], "pada": min(int(within / PADA_SIZE) + 1, 4), "lord": lord, "nakshatra_lord": lord, "within": within}


def angle(a, b):
    d = abs((a - b) % 360)
    return min(d, 360 - d)


def body(jd, pid):
    x, _ = swe.calc_ut(jd, pid, FLAGS)
    out = sign_info(x[0])
    out.update(nak_info(x[0]))
    out["retrograde"] = x[3] < 0
    return out


def add_years(dt, years):
    return dt + timedelta(days=years * 365.2425)


def fmt_deg(value):
    d = int(value)
    mf = (value - d) * 60
    m = int(mf)
    s = round((mf - m) * 60)
    if s == 60:
        s = 0
        m += 1
    if m == 60:
        m = 0
        d += 1
    return f"{d:02d}° {m:02d}′ {s:02d}″"


def vimshottari(moon_lon, birth, analysis):
    n = nak_info(moon_lon)
    lord = n["lord"]
    cur = add_years(birth, -DYEARS[lord] * (n["within"] / NAK_SIZE))
    idx = DSEQ.index(lord)
    mds = []
    for _ in range(2):
        for off in range(9):
            item_lord = DSEQ[(idx + off) % 9]
            end = add_years(cur, DYEARS[item_lord])
            mds.append({"lord": item_lord, "start": cur, "end": end})
            cur = end
    target = max(analysis, birth)
    md = next((x for x in mds if x["start"] <= target < x["end"]), mds[0])
    idx = DSEQ.index(md["lord"])
    cur = md["start"]
    ads = []
    for off in range(9):
        item_lord = DSEQ[(idx + off) % 9]
        end = add_years(cur, DYEARS[md["lord"]] * DYEARS[item_lord] / 120)
        ads.append({"lord": item_lord, "start": cur, "end": end})
        cur = end
    ad = next((x for x in ads if x["start"] <= target < x["end"]), ads[0])
    return {
        "mahadasha": md["lord"], "md_start": md["start"].date().isoformat(), "md_end": md["end"].date().isoformat(),
        "antardasha": ad["lord"], "ad_start": ad["start"].date().isoformat(), "ad_end": ad["end"].date().isoformat(),
        "analysis_date": target.date().isoformat(),
        "md_timeline": [{"Mahadasha": x["lord"], "Start": x["start"].date().isoformat(), "End": x["end"].date().isoformat(), "Current": "Yes" if x is md else ""} for x in mds[:9]],
        "ad_timeline": [{"Antardasha": x["lord"], "Start": x["start"].date().isoformat(), "End": x["end"].date().isoformat(), "Current": "Yes" if x is ad else ""} for x in ads],
    }


def calculate_chart(profile, analysis_dt=None):
    dob, tob, lat, lon, tz = profile["dob"], profile["tob"], profile["lat"], profile["lon"], profile["tz"]
    swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
    hour = tob.hour + tob.minute / 60 + tob.second / 3600
    jd = swe.julday(dob.year, dob.month, dob.day, hour - tz, swe.GREG_CAL)
    _, ascmc = swe.houses_ex(jd, lat, lon, b"W", swe.FLG_SIDEREAL)
    asc = sign_info(ascmc[0])
    asc.update(nak_info(ascmc[0]))
    ids = {"Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS, "Mercury": swe.MERCURY, "Jupiter": swe.JUPITER, "Venus": swe.VENUS, "Saturn": swe.SATURN, "Rahu": swe.MEAN_NODE}
    planets = {name: body(jd, pid) for name, pid in ids.items()}
    ketu = sign_info(planets["Rahu"]["longitude"] + 180)
    ketu.update(nak_info(ketu["longitude"]))
    ketu["retrograde"] = True
    planets["Ketu"] = ketu
    rules = {n: [] for n in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]}
    for house in range(1, 13):
        rules[LORDS[SIGNS[(asc["sign_index"] + house - 1) % 12]]].append(house)
    for name, item in planets.items():
        item["house"] = ((item["sign_index"] - asc["sign_index"]) % 12) + 1
        labels = []
        if name in OWN and item["sign"] in OWN[name]: labels.append("Own sign")
        if name in EXALT and item["sign"] == EXALT[name]: labels.append("Exaltation sign")
        if name in DEBIL and item["sign"] == DEBIL[name]: labels.append("Debilitation sign")
        if item["retrograde"] and name not in ("Rahu", "Ketu"): labels.append("Retrograde")
        if name in COMBUST and angle(item["longitude"], planets["Sun"]["longitude"]) <= COMBUST[name]: labels.append("Combustion screening flag")
        item["condition"] = labels or ["No major screening flag"]
        item["rules_houses"] = rules.get(name, [])
    conjunctions = []
    names = list(planets)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if planets[a]["sign_index"] == planets[b]["sign_index"]:
                conjunctions.append({"Planets": f"{a} + {b}", "Sign": planets[a]["sign"], "House": planets[a]["house"], "Separation": round(angle(planets[a]["longitude"], planets[b]["longitude"]), 2)})
    aspects = []
    for name, offsets in ASPECTS.items():
        for off in offsets:
            target = ((planets[name]["house"] + off - 2) % 12) + 1
            targets = [x for x, p in planets.items() if p["house"] == target and x != name]
            aspects.append({"Planet": name, "Aspect": f"{off}th", "From": planets[name]["house"], "To": target, "Target planets": ", ".join(targets) or "—"})
    ak = max(["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"], key=lambda n: planets[n]["degree"])
    birth = (datetime(dob.year, dob.month, dob.day, tob.hour, tob.minute, tob.second) - timedelta(hours=tz)).replace(tzinfo=timezone.utc)
    timing = vimshottari(planets["Moon"]["longitude"], birth, analysis_dt or datetime.now(timezone.utc))
    chart = {"ascendant": asc, "planets": planets, "atmakaraka": ak, "timing": timing, "conjunctions": conjunctions, "aspects": aspects, "ayanamsa": swe.get_ayanamsa_ut(jd)}
    chart["validation_errors"] = validate_chart(chart)
    return chart


def validate_chart(chart):
    errors = []
    asc = chart["ascendant"]
    if asc.get("sign_lord") != LORDS.get(asc.get("sign")): errors.append("Ascendant sign lord mismatch")
    if asc.get("nakshatra_lord") != asc.get("lord"): errors.append("Ascendant Nakshatra lord mismatch")
    for name, p in chart["planets"].items():
        if p.get("sign_lord") != LORDS.get(p.get("sign")): errors.append(f"{name} sign lord mismatch")
        if p.get("nakshatra_lord") != p.get("lord"): errors.append(f"{name} Nakshatra lord mismatch")
        expected_house = ((p["sign_index"] - asc["sign_index"]) % 12) + 1
        if p.get("house") != expected_house: errors.append(f"{name} house mismatch")
    if abs(angle(chart["planets"]["Rahu"]["longitude"], chart["planets"]["Ketu"]["longitude"]) - 180) > 0.001: errors.append("Rahu/Ketu opposition mismatch")
    eligible = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
    expected_ak = max(eligible, key=lambda n: chart["planets"][n]["degree"])
    if chart.get("atmakaraka") != expected_ak: errors.append("Atmakaraka mismatch")
    return errors


def locked_chart_facts(chart):
    return {
        "ascendant": {
            "sign": chart["ascendant"]["sign"], "sign_lord": chart["ascendant"]["sign_lord"],
            "degree": round(chart["ascendant"]["degree"], 4), "nakshatra": chart["ascendant"]["nakshatra"],
            "nakshatra_lord": chart["ascendant"]["nakshatra_lord"], "pada": chart["ascendant"]["pada"],
        },
        "atmakaraka": chart["atmakaraka"], "timing": chart["timing"],
        "planets": {name: {"sign": p["sign"], "sign_lord": p["sign_lord"], "degree": round(p["degree"], 4), "house": p["house"], "nakshatra": p["nakshatra"], "nakshatra_lord": p["nakshatra_lord"], "pada": p["pada"], "condition": p["condition"], "rules_houses": p["rules_houses"], "retrograde": p["retrograde"]} for name, p in chart["planets"].items()},
        "conjunctions": chart["conjunctions"], "aspects": chart["aspects"]
    }


@st.cache_resource(show_spinner=False)
def get_embeddings(): return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)


@st.cache_resource(show_spinner=False)
def get_store():
    path = "chroma_db"
    if not os.path.isfile(os.path.join(path, "chroma.sqlite3")): return None, 0
    client = chromadb.PersistentClient(path=path)
    names = [c.name if hasattr(c, "name") else str(c) for c in client.list_collections()]
    name = COLLECTION_NAME if COLLECTION_NAME in names else (names[0] if names else None)
    if not name: return None, 0
    return Chroma(client=client, collection_name=name, embedding_function=get_embeddings()), client.get_collection(name).count()


@st.cache_data(show_spinner=False)
def get_practitioners():
    rows = []
    for fn in ["integrative_practitioner_knowledge_v1_2.json", "additional_practitioner_talks_v1.json"]:
        if not os.path.isfile(fn): continue
        with open(fn, encoding="utf-8") as handle: data = json.load(handle)
        rows.extend(data.get("records", []))
        for speaker in data.get("speakers", []):
            for record in speaker.get("records", []):
                item = dict(record)
                item.setdefault("speaker", speaker.get("speaker"))
                rows.append(item)
    return list({r.get("id", str(i)): r for i, r in enumerate(rows)}.values())


def search_local(q, k=7):
    store, count = get_store()
    if not store: return [], count
    try: return store.as_retriever(search_kwargs={"k": k}).invoke(q), count
    except Exception: return [], count


def search_teachers(q, k=6):
    terms = [x.lower() for x in re.findall(r"[A-Za-zÀ-ÿ]+", q) if len(x) > 2]
    scored = []
    for r in get_practitioners():
        if r.get("rag_eligible") is False: continue
        text = json.dumps(r, ensure_ascii=False).lower()
        score = sum(1 for t in terms if t in text) + (2 if r.get("exact_answer_eligible") else 0)
        if score: scored.append((score, r))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:k]]


def secret(name):
    try: return st.secrets.get(name, "")
    except Exception: return ""


def effective_mode(mode):
    if mode == "Offline": return "Offline"
    if mode == "Deep Research" and secret("TAVILY_API_KEY") and secret("ZAI_API_KEY"): return "Deep Research"
    return "Trusted Library"


def get_llm(tokens=3200):
    return ChatOpenAI(model="glm-4.5-flash", openai_api_key=secret("ZAI_API_KEY"), openai_api_base="https://api.z.ai/api/paas/v4", temperature=.35, max_tokens=tokens, extra_body={"thinking": {"type": "disabled"}})


PII_PATTERNS = [r"\b(?:19|20)\d{2}\b", r"\b\d{1,2}[:.]\d{2}\b", r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", r"\b(?:dob|date of birth|born|birth time|birthplace)\b[^,.]*"]


def sanitise_web_query(q, concepts=None):
    text = q or ""
    for pattern in PII_PATTERNS: text = re.sub(pattern, " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    return (text + " " + " ".join(str(x) for x in (concepts or []) if x)).strip()[:380]


def web_domains(q):
    if any(x in q.lower() for x in ["health", "medical", "ayurveda", "sleep", "stress", "anxiety", "yoga", "meditation", "dosha", "digestion"]):
        return ["who.int", "nccih.nih.gov", "ayush.gov.in", "ccras.nic.in", "pubmed.ncbi.nlm.nih.gov"]
    return []


def tavily_search(q, personal=None, max_results=5, opener=None):
    key = secret("TAVILY_API_KEY")
    if not key: return {"ok": False, "status": "not_configured", "results": [], "error": "Tavily key missing"}
    concepts = []
    if personal: concepts = [f"{personal['timing']['mahadasha']} planetary period", f"{personal['timing']['antardasha']} sub-period", f"{personal['atmakaraka']} Vedic astrology significator"]
    payload = {"query": sanitise_web_query(q, concepts), "search_depth": "advanced", "topic": "general", "max_results": max_results, "chunks_per_source": 2, "include_answer": False, "include_raw_content": False, "safe_search": True}
    domains = web_domains(q)
    if domains: payload["include_domains"] = domains
    req = urllib.request.Request("https://api.tavily.com/search", data=json.dumps(payload).encode(), headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, method="POST")
    opener = opener or urllib.request.urlopen
    try:
        with opener(req, timeout=35) as response: data = json.loads(response.read().decode())
    except Exception as exc:
        return {"ok": False, "status": "failed", "results": [], "error": str(exc)}
    results = [{"title": x.get("title") or "Web source", "url": x.get("url") or "", "content": x.get("content") or "", "score": x.get("score")} for x in data.get("results", [])[:max_results] if x.get("url") and x.get("content")]
    return {"ok": bool(results), "status": "ok" if results else "empty", "results": results, "error": ""}


def dedupe_evidence(docs, teachers):
    seen, clean_docs = set(), []
    for d in docs:
        m = d.metadata or {}
        key = (m.get("book") or m.get("source"), m.get("pdf_page"), m.get("chunk_id"))
        if key not in seen: seen.add(key); clean_docs.append(d)
    seen, clean_teachers = set(), []
    for r in teachers:
        key = r.get("id") or (r.get("speaker"), r.get("topic") or r.get("title") or r.get("video_title"))
        if key not in seen: seen.add(key); clean_teachers.append(r)
    return clean_docs, clean_teachers


def personal_evidence(chart):
    t, ak = chart["timing"], chart["atmakaraka"]
    a = chart["ascendant"]
    base = f"{a['sign']} Ascendant lord {a['sign_lord']} {a['nakshatra']} Nakshatra lord {a['nakshatra_lord']} {ak} Atmakaraka {t['mahadasha']} Mahadasha {t['antardasha']} Antardasha"
    queries = [base + " Jyotish houses lordship dignity conjunction aspects current life themes", base + " Ayurveda mind body routine sleep digestion Agni dosha supportive lifestyle", base + " mantra devotional practice japa stotra graha remedy", base + " yoga meditation grounding focus balance", base + " remedies upaya dana charity behaviour gemstone strengthen pacify", base + " chakra subtle body correspondence framework differences"]
    docs, teachers = [], []
    for q in queries:
        d, _ = search_local(q, 5)
        docs.extend(d)
        teachers.extend(search_teachers(q, 4))
    return dedupe_evidence(docs, teachers)


def evidence_context(docs, teachers, web):
    out = []
    for i, d in enumerate(docs[:5], 1):
        m = d.metadata or {}
        out.append(f"[C{i}] {m.get('book') or m.get('source', 'Unknown')} page {m.get('pdf_page', 'Needs Verification')}\n{' '.join(d.page_content.split())[:1200]}")
    for i, r in enumerate(teachers[:4], 1): out.append(f"[P{i}] {r.get('speaker') or 'Needs Verification'} | {r.get('topic') or r.get('title') or 'Indexed teaching'}\n{(r.get('summary') or r.get('explanation_text') or '')[:900]}")
    for i, r in enumerate(web[:5], 1): out.append(f"[W{i}] {r['title']} | {r['url']}\n{r['content'][:1000]}")
    return "\n\n".join(out)


def local_answer(q, docs, teachers, personal=None):
    parts = []
    if personal: parts.append(f"**Personal context:** {personal['timing']['mahadasha']} major period, {personal['timing']['antardasha']} sub-period and {personal['atmakaraka']} core significator.")
    for r in teachers[:2]:
        text = r.get("summary") or r.get("explanation_text") or ""
        if text: parts.append(" ".join(text.split()[:100]))
    for d in docs[:2]:
        text = " ".join(d.page_content.split())
        if text: parts.append("**Trusted library:** " + " ".join(text.split()[:100]))
    if not parts: return "I could not find enough verified material. **Needs Verification.**"
    parts.append("**Practical note:** gemstones, herbs, fasting, advanced mantra and medical claims require verification or qualified guidance.")
    return "\n\n".join(parts)


def synthesize(q, docs, teachers, personal, cfg):
    mode = effective_mode(cfg["knowledge_mode"])
    web = {"ok": False, "status": "not_used", "results": [], "error": ""}
    if personal and personal.get("validation_errors"):
        return "Chart validation failed. Personal interpretation has been withheld.\n\n" + "\n".join(f"- {x}" for x in personal["validation_errors"]), web, mode
    if mode == "Deep Research": web = tavily_search(q, personal)
    if mode == "Offline" or not secret("ZAI_API_KEY"): return local_answer(q, docs, teachers, personal), web, mode
    limits = {"Simple": "180-300 words", "Detailed": "700-1100 words", "Advanced": "1300-1900 words"}
    facts = locked_chart_facts(personal) if personal else "not supplied"
    prompt = f"""Answer using LOCKED CALCULATED FACTS and retrieved evidence.
Question: {q}
Depth: {cfg['depth']} ({limits[cfg['depth']]}). Mode: {mode}.
LOCKED CALCULATED FACTS: {json.dumps(facts, default=str)}
Evidence:\n{evidence_context(docs, teachers, web['results'])}
Rules:
- Never recalculate or override LOCKED CALCULATED FACTS.
- A zodiac SIGN LORD and a NAKSHATRA LORD are different facts. Never describe a Nakshatra lord as the ruler of a sign.
- State the Ascendant sign and its sign lord first, then separately state the Ascendant Nakshatra, Nakshatra lord and Pada.
- For Scorpio Ascendant, the sign lord is Mars. Jyestha's Nakshatra lord is Mercury. Never merge these.
- Explain Sanskrit terms and distinguish Calculated Fact, Classical Source, Practitioner View, Web Research and Needs Verification.
- Do not infer a definite personality trait from one condition. Use qualified language and evaluate sign, house, lordship, conjunctions, aspects and exact combustion distance together.
- Never invent remedies, medical claims, universal chakra mappings, mantra counts or gemstone suitability.
- Never transfer a remedy from one planet to another without direct evidence.
- If web research failed, say the answer uses Trusted Library only."""
    try: return get_llm(5200 if cfg["depth"] == "Advanced" else 3400).invoke(prompt).content, web, mode
    except Exception: return local_answer(q, docs, teachers, personal), web, "Trusted Library"


@st.cache_resource(show_spinner=False)
def timezone_finder(): return TimezoneFinder(in_memory=True)


def geocode(place):
    q = urllib.parse.urlencode({"q": place, "format": "jsonv2", "limit": 5, "addressdetails": 1})
    req = urllib.request.Request("https://nominatim.openstreetmap.org/search?" + q, headers={"User-Agent": "AncientWisdomSynthesis/1.42 birthplace lookup", "Accept-Language": "en"})
    with urllib.request.urlopen(req, timeout=20) as response: data = json.loads(response.read().decode())
    return [{"label": x.get("display_name", "Result"), "lat": float(x["lat"]), "lon": float(x["lon"])} for x in data]


def historic_zone(lat, lon, dob, tob):
    finder = timezone_finder()
    zone = finder.timezone_at(lat=lat, lng=lon) or finder.closest_timezone_at(lat=lat, lng=lon)
    if not zone: raise RuntimeError("Timezone boundary not found")
    local = datetime(dob.year, dob.month, dob.day, tob.hour, tob.minute, tob.second, tzinfo=ZoneInfo(zone))
    offset = local.utcoffset()
    if offset is None: raise RuntimeError("UTC offset unavailable")
    return zone, offset.total_seconds() / 3600, local.tzname() or ""


def default_profile(): return {"name": "", "dob": date(1990, 1, 1), "tob": datetime.strptime("12:00", "%H:%M").time(), "place": "", "lat": 22.3193, "lon": 114.1694, "tz": 8.0, "zone_name": "", "zone_abbr": ""}
def signature(p): return (p["name"], p["dob"].isoformat(), p["tob"].isoformat(), p["place"], round(p["lat"], 6), round(p["lon"], 6), round(p["tz"], 2))


def init_widgets():
    p = st.session_state.get("saved_profile", default_profile())
    values = {"w_name": p["name"], "w_day": p["dob"].day, "w_month": p["dob"].month, "w_year": p["dob"].year, "w_time": p["tob"], "w_place": p["place"], "w_lat": p["lat"], "w_lon": p["lon"], "w_tz": p["tz"], "w_zone": p.get("zone_name", ""), "w_abbr": p.get("zone_abbr", "")}
    for key, value in values.items(): st.session_state.setdefault(key, value)


def apply_location():
    results = st.session_state.get("location_results", [])
    index = st.session_state.get("location_index", 0)
    if not results: raise RuntimeError("No location selected")
    item = results[index]
    dob = date(int(st.session_state.w_year), int(st.session_state.w_month), int(st.session_state.w_day))
    zone, offset, abbr = historic_zone(item["lat"], item["lon"], dob, st.session_state.w_time)
    st.session_state.w_place = item["label"]
    st.session_state.w_lat = item["lat"]
    st.session_state.w_lon = item["lon"]
    st.session_state.w_tz = offset
    st.session_state.w_zone = zone
    st.session_state.w_abbr = abbr
    st.session_state.location_message = f"{item['label']} · {zone} ({abbr}) · UTC {offset:+.2f}"


def safe_apply_location():
    try:
        apply_location()
        st.session_state.location_error = ""
    except Exception as exc:
        st.session_state.location_error = f"Location/timezone resolution failed: {exc}"


def profile_panel():
    init_widgets()
    with st.sidebar:
        st.markdown("### Your Profile")
        st.text_input("Name", key="w_name")
        a, b, c = st.columns([1, 1.4, 1.2])
        with a: st.number_input("Day", min_value=1, max_value=31, step=1, key="w_day")
        with b: st.selectbox("Month", range(1, 13), format_func=lambda x: datetime(2000, x, 1).strftime("%B"), key="w_month")
        with c: st.number_input("Year", min_value=1900, max_value=2050, step=1, key="w_year")
        st.time_input("Exact birth time", key="w_time")
        st.text_input("Birthplace", key="w_place", placeholder="City, region, country")
        if st.button("Search birthplace", use_container_width=True):
            try:
                st.session_state.location_results = geocode(st.session_state.w_place)
                st.session_state.location_index = 0
                st.rerun()
            except Exception as exc: st.error(f"Birthplace lookup failed: {exc}")
        results = st.session_state.get("location_results", [])
        if results:
            st.selectbox("Choose the correct birthplace", range(len(results)), format_func=lambda i: results[i]["label"], key="location_index")
            st.button("Use selected birthplace", use_container_width=True, on_click=safe_apply_location)
        if st.session_state.get("location_message"): st.success(st.session_state.location_message)
        if st.session_state.get("location_error"): st.error(st.session_state.location_error)
        with st.expander("Location details and manual correction"):
            st.number_input("Latitude", -90.0, 90.0, key="w_lat", format="%.6f")
            st.number_input("Longitude", -180.0, 180.0, key="w_lon", format="%.6f")
            st.number_input("UTC offset at birth", -12.0, 14.0, step=.25, key="w_tz")
            st.caption(f"Timezone: {st.session_state.w_zone or 'manual'} {st.session_state.w_abbr}")
        confirmed = st.checkbox("I confirm the birth time, birthplace, coordinates and UTC offset", key="w_confirm")
        mode = st.radio("Knowledge source", MODES, index=MODES.index(st.session_state.get("knowledge_mode", "Deep Research")))
        depth = st.select_slider("Answer detail", DEPTHS, value=st.session_state.get("depth", "Detailed"))
        advanced = st.toggle("Show advanced Vedic details", value=st.session_state.get("advanced", False))
        if st.button("Save and confirm profile", type="primary", use_container_width=True):
            try: dob = date(int(st.session_state.w_year), int(st.session_state.w_month), int(st.session_state.w_day))
            except ValueError as exc: st.error(f"Invalid date: {exc}"); dob = None
            if not st.session_state.w_name.strip(): st.error("Enter a name.")
            elif not st.session_state.w_place.strip(): st.error("Search or enter a birthplace.")
            elif not confirmed: st.error("Confirm the birth details.")
            elif dob:
                p = {"name": st.session_state.w_name.strip(), "dob": dob, "tob": st.session_state.w_time, "place": st.session_state.w_place, "lat": float(st.session_state.w_lat), "lon": float(st.session_state.w_lon), "tz": float(st.session_state.w_tz), "zone_name": st.session_state.w_zone, "zone_abbr": st.session_state.w_abbr}
                old, new = st.session_state.get("profile_signature"), signature(p)
                st.session_state.saved_profile = p
                st.session_state.profile_signature = new
                st.session_state.knowledge_mode = mode
                st.session_state.depth = depth
                st.session_state.advanced = advanced
                st.session_state.profile_saved_notice = f"Profile saved and confirmed: {p['dob'].strftime('%d %b %Y')} · {p['tob'].strftime('%H:%M')} · {p['place']} · UTC {p['tz']:+.2f}"
                if old != new:
                    for key in ["chart", "chart_signature", "personal_report", "remedy_answer", "last_sources", "last_web"]: st.session_state.pop(key, None)
                st.rerun()
        if st.session_state.get("profile_saved_notice"): st.success(st.session_state.profile_saved_notice)
        p = st.session_state.get("saved_profile")
        if p: st.caption(f"Saved profile: {p['place']} · UTC {p['tz']:+.2f}")
        return {"saved_profile": p, "knowledge_mode": mode, "effective_mode": effective_mode(mode), "depth": depth, "advanced": advanced}


def ensure_chart(cfg, force=False):
    profile = cfg.get("saved_profile")
    if not profile: return None
    sig = signature(profile)
    if force or st.session_state.get("chart_signature") != sig:
        st.session_state.chart = calculate_chart(profile)
        st.session_state.chart_signature = sig
    return st.session_state.chart


def source_panel(docs, teachers):
    with st.expander(f"Sources · {len(docs[:12])} classical/official · {len(teachers[:10])} practitioner"):
        for d in docs[:12]:
            m = d.metadata or {}
            st.markdown(f"- **{m.get('book') or m.get('source', 'Unknown')}** · page {m.get('pdf_page', 'Needs Verification')}")
        for r in teachers[:10]: st.markdown(f"- **{r.get('speaker') or 'Needs Verification'}** · {r.get('topic') or r.get('title') or r.get('video_title') or 'Indexed teaching'}")


def web_panel(web):
    if web and web.get("status") in ("failed", "empty"): st.warning("Live web research was unavailable; this answer uses the Trusted Library.")
    if web and web.get("results"):
        with st.expander(f"Live web research · {len(web['results'])} sources"):
            for r in web["results"]: st.markdown(f"- [{r['title']}]({r['url']})")


def set_page(page): st.session_state.page = page
def nav(page, q=None): st.session_state.page = page; st.session_state.pending_question = q if q else st.session_state.get("pending_question"); st.rerun()


def home(cfg):
    st.markdown("## How can I help you today?")
    with st.form("homeask", clear_on_submit=True):
        q = st.text_input("Ask anything", placeholder="What should I focus on now? What does Saturn mean?", label_visibility="collapsed")
        go = st.form_submit_button("Ask Ancient Wisdom", type="primary", use_container_width=True)
    if go and q.strip(): nav("Ask", q.strip())
    columns = st.columns(3)
    cards = [("🔮 My Personal Reading", "Deep synthesis from confirmed birth details.", "Build My Reading", "My Reading"), ("🪷 My Remedies", "Practical, chart-specific guidance.", "View My Remedies", "My Remedies"), ("📚 Explore Knowledge", "Search books, topics and teachers.", "Explore Knowledge", "Explore")]
    for i, (title, desc, label, page) in enumerate(cards):
        with columns[i]:
            st.markdown(f"<div class='choice'><h3>{title}</h3><p>{desc}</p></div>", unsafe_allow_html=True)
            st.button(label, key=f"h{i}", use_container_width=True, on_click=set_page, args=(page,))


def ask(cfg):
    st.markdown("## Ask Ancient Wisdom")
    st.session_state.setdefault("chat", [])
    for item in st.session_state.chat:
        with st.chat_message(item["role"]): st.markdown(item["content"])
    q = st.session_state.pop("pending_question", None) or st.chat_input("What's on your mind?")
    if q:
        chart = st.session_state.get("chart")
        query = q + (f" {chart['timing']['mahadasha']} Mahadasha {chart['timing']['antardasha']} Antardasha {chart['atmakaraka']} Atmakaraka" if chart else "")
        docs, _ = search_local(query)
        teachers = search_teachers(query)
        ans, web, _ = synthesize(q, docs, teachers, chart, cfg)
        st.session_state.chat.extend([{"role": "user", "content": q}, {"role": "assistant", "content": ans}])
        st.session_state.last_sources = (docs, teachers)
        st.session_state.last_web = web
        st.rerun()
    if st.session_state.get("last_sources"): source_panel(*st.session_state.last_sources)
    if st.session_state.get("last_web"): web_panel(st.session_state.last_web)
    if st.session_state.chat and st.button("Clear conversation"):
        st.session_state.chat = []
        for key in ["last_sources", "last_web"]: st.session_state.pop(key, None)
        st.rerun()


def reading(cfg):
    st.markdown("## My Personal Reading")
    if not cfg.get("saved_profile"): st.warning("Save and confirm your profile first."); return
    if st.button("Generate Full Personal Synthesis", type="primary", use_container_width=True):
        chart = ensure_chart(cfg, True)
        if chart["validation_errors"]:
            st.session_state.personal_report = "Chart validation failed. Personal interpretation has been withheld."
            st.session_state.personal_sources = ([], [])
            st.session_state.personal_web = None
        else:
            docs, teachers = personal_evidence(chart)
            request = "Create a full integrated personal report with Jyotish, timing, Ayurveda support, yoga, mantra, chakra perspectives, remedies, gemstone caution and three priorities. Begin with the Ascendant sign and its sign lord, then separately state the Ascendant Nakshatra, Nakshatra lord and Pada. Never merge sign lordship with Nakshatra lordship. Explain why every major conclusion applies to this chart."
            ans, web, _ = synthesize(request, docs, teachers, chart, cfg)
            st.session_state.personal_report = ans
            st.session_state.personal_web = web
            st.session_state.personal_sources = (docs, teachers)
    chart = st.session_state.get("chart")
    if not chart: return
    t = chart["timing"]
    a, b, d, e = st.columns(4)
    a.metric("Ascendant", chart["ascendant"]["sign"], f"Lord: {chart['ascendant']['sign_lord']}")
    b.metric("Moon pattern", f"{chart['planets']['Moon']['nakshatra']} · Pada {chart['planets']['Moon']['pada']}", f"Lord: {chart['planets']['Moon']['nakshatra_lord']}")
    d.metric("Major period", t["mahadasha"], f"to {t['md_end']}")
    e.metric("Sub-period", t["antardasha"], f"to {t['ad_end']}")
    if st.session_state.get("personal_report"):
        st.markdown(st.session_state.personal_report)
        source_panel(*st.session_state.get("personal_sources", ([], [])))
        web_panel(st.session_state.get("personal_web"))
    if cfg["advanced"]:
        st.markdown("### Locked Ascendant facts")
        st.dataframe([{"Ascendant sign": chart["ascendant"]["sign"], "Sign lord": chart["ascendant"]["sign_lord"], "Ascendant Nakshatra": chart["ascendant"]["nakshatra"], "Nakshatra lord": chart["ascendant"]["nakshatra_lord"], "Pada": chart["ascendant"]["pada"]}], use_container_width=True, hide_index=True)
        rows = [{"Planet": name, "Sign": p["sign"], "Sign lord": p["sign_lord"], "Degree": fmt_deg(p["degree"]), "House": p["house"], "Nakshatra": p["nakshatra"], "Nakshatra lord": p["nakshatra_lord"], "Pada": p["pada"], "Condition": "; ".join(p["condition"]), "Rules houses": ", ".join(map(str, p["rules_houses"])) or "—"} for name, p in chart["planets"].items()]
        st.dataframe(rows, use_container_width=True, hide_index=True)


def remedies(cfg):
    st.markdown("## My Remedies")
    chart = ensure_chart(cfg)
    if not chart: st.info("Generate My Personal Reading first."); return
    if chart["validation_errors"]: st.error("Chart validation failed. Remedy generation has been withheld."); return
    t = chart["timing"]
    q = f"{t['mahadasha']} {t['antardasha']} {chart['atmakaraka']} remedies mantra dana yoga Ayurveda gemstone strengthen pacify"
    docs, _ = search_local(q, 10)
    teachers = search_teachers(q, 10)
    if st.button("Build Detailed Remedy Plan", type="primary", use_container_width=True):
        ans, web, _ = synthesize("Build a ranked personal remedy plan with purpose, chart reason, source basis, practical application and guidance level. Use only validated sign lordship and Nakshatra lordship facts. Never transfer a remedy between planets without direct support.", docs, teachers, chart, cfg)
        st.session_state.remedy_answer = ans
        st.session_state.remedy_web = web
        st.session_state.remedy_sources = (docs, teachers)
    if st.session_state.get("remedy_answer"):
        st.markdown(st.session_state.remedy_answer)
        source_panel(*st.session_state.get("remedy_sources", ([], [])))
        web_panel(st.session_state.get("remedy_web"))
    st.warning("Gemstones, herbs, fasting, advanced pranayama and Bija/Tantric practices require verification or qualified guidance.")


def explore(cfg):
    st.markdown("## Explore Ancient Wisdom")
    library, teacher_tab = st.tabs(["Search Library", "Teachers"])
    with library:
        q = st.text_input("Search the 21-source library", placeholder="e.g. Saturn and Vata, mantra initiation, Jupiter remedies")
        if q:
            docs, _ = search_local(q, 8)
            teachers = search_teachers(q)
            ans, web, _ = synthesize(q, docs, teachers, None, cfg)
            st.markdown(ans)
            source_panel(docs, teachers)
            web_panel(web)
    with teacher_tab:
        rows = get_practitioners()
        names = sorted({r.get("speaker") for r in rows if r.get("speaker")})
        if not names: st.info("Teacher library unavailable.")
        else:
            name = st.selectbox("Choose a teacher", names)
            for r in [x for x in rows if x.get("speaker") == name][:30]:
                with st.expander(r.get("topic") or r.get("title") or r.get("video_title") or "Indexed teaching"):
                    st.write(r.get("summary") or r.get("explanation_text") or "Needs Verification")
                    st.caption(r.get("verification_status", ""))


def run_regression_checks():
    checks = []
    y_profile = {"dob": date(2016, 7, 4), "tob": datetime.strptime("17:21", "%H:%M").time(), "lat": 31.532, "lon": 75.917, "tz": 5.5}
    y = calculate_chart(y_profile, datetime(2026, 11, 20, tzinfo=timezone.utc))
    checks.extend([
        ("Yuvaan Scorpio Ascendant", y["ascendant"]["sign"] == "Scorpio"),
        ("Yuvaan Ascendant lord Mars", y["ascendant"]["sign_lord"] == "Mars"),
        ("Yuvaan Jyestha", y["ascendant"]["nakshatra"] == "Jyeshtha"),
        ("Yuvaan Jyestha lord Mercury", y["ascendant"]["nakshatra_lord"] == "Mercury"),
        ("Yuvaan Moon Ardra 4", y["planets"]["Moon"]["nakshatra"] == "Ardra" and y["planets"]["Moon"]["pada"] == 4),
        ("Yuvaan Mars Atmakaraka", y["atmakaraka"] == "Mars"),
        ("Yuvaan Jupiter/Venus", y["timing"]["mahadasha"] == "Jupiter" and y["timing"]["antardasha"] == "Venus"),
        ("Yuvaan validation", not y["validation_errors"]),
    ])
    p_profile = {"dob": date(1983, 12, 27), "tob": datetime.strptime("00:35", "%H:%M").time(), "lat": 31.64, "lon": 76.13, "tz": 5.5}
    p = calculate_chart(p_profile, datetime(2026, 11, 20, tzinfo=timezone.utc))
    checks.extend([
        ("Puneet Virgo Ascendant", p["ascendant"]["sign"] == "Virgo"),
        ("Puneet Ascendant lord Mercury", p["ascendant"]["sign_lord"] == "Mercury"),
        ("Puneet Hasta Moon", p["planets"]["Moon"]["nakshatra"] == "Hasta"),
        ("Puneet Mars Atmakaraka", p["atmakaraka"] == "Mars"),
        ("Puneet Jupiter/Venus", p["timing"]["mahadasha"] == "Jupiter" and p["timing"]["antardasha"] == "Venus"),
        ("Puneet validation", not p["validation_errors"]),
    ])
    return checks


def main():
    cfg = profile_panel()
    st.markdown(f"<div class='hero'><div class='eyebrow'>PERSONAL WISDOM & REMEDY ENGINE</div><h1>Ancient Wisdom Synthesis</h1><p class='subtitle'>{APP_VERSION}</p></div>", unsafe_allow_html=True)
    st.session_state.setdefault("page", "Home")
    choice = st.radio("Navigation", PAGES, horizontal=True, index=PAGES.index(st.session_state.page), label_visibility="collapsed")
    if choice != st.session_state.page: st.session_state.page = choice; st.rerun()
    with st.expander("Release status", expanded=False):
        _, count = get_store()
        st.write(f"Ancient Wisdom records: **{count:,}**")
        st.write(f"Practitioner records: **{len(get_practitioners())}**")
        st.write(f"Selected mode: **{cfg['knowledge_mode']}** · Active mode: **{cfg['effective_mode']}**")
        st.write("Z.ai: **Ready**" if secret("ZAI_API_KEY") else "Z.ai: **Not configured**")
        st.write("Tavily: **Ready**" if secret("TAVILY_API_KEY") else "Tavily: **Not configured**")
        checks = run_regression_checks()
        failed = [name for name, ok in checks if not ok]
        st.write("Chart regression: **PASS**" if not failed else "Chart regression: **FAIL**")
        if failed: st.error("; ".join(failed))
    {"Home": home, "Ask": ask, "My Reading": reading, "My Remedies": remedies, "Explore": explore}[st.session_state.page](cfg)


if __name__ == "__main__":
    main()
