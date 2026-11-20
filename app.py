import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import chromadb
import streamlit as st
import swisseph as swe
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_openai import ChatOpenAI

st.set_page_config(
    page_title="Ancient Wisdom Synthesis",
    page_icon="🕉️",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_VERSION = "AWS v1.32 Automatic Place and Historical UTC"
EMBEDDING_MODEL = "paraphrase-MiniLM-L3-v2"
COLLECTION_NAME = "ancient_wisdom"
PAGES = ["Home", "Ask", "My Reading", "My Remedies", "Explore"]
KNOWLEDGE_MODES = ["Trusted Library", "Deep Research", "Offline"]
ANSWER_DEPTHS = ["Simple", "Detailed", "Advanced"]

st.markdown(
    """
<style>
.stApp{background:radial-gradient(circle at 15% 0%,#202653 0,#11152d 38%,#090b18 100%);color:#f5f0e8}
.block-container{max-width:1480px;padding-top:1rem;padding-bottom:4rem}
[data-testid="stSidebar"]{background:#11142b;border-right:1px solid #303558}
[data-testid="stMetric"]{background:linear-gradient(145deg,rgba(31,36,70,.97),rgba(19,22,45,.97));border:1px solid #3a3f68;border-radius:16px;padding:14px}
[data-testid="stMetricLabel"]{color:#aaa6b6!important}[data-testid="stMetricValue"]{color:#e2c45f!important}
[data-testid="stExpander"]{background:rgba(18,22,45,.82);border:1px solid #343961;border-radius:14px}
.stButton>button{background:linear-gradient(135deg,#5d4ba0,#8d68d8);color:white;border:1px solid #9d83df;border-radius:24px;font-weight:650;min-height:2.7rem}
.stButton>button:hover{border-color:#e2c45f;color:white;transform:translateY(-1px)}
h1,h2,h3,h4{color:#f6f0e7}
.hero{padding:15px 21px;border:1px solid #41466f;border-radius:20px;background:linear-gradient(135deg,rgba(37,43,84,.97),rgba(17,20,43,.94));margin-bottom:14px}
.hero h1{font-size:1.8rem!important;line-height:1.15!important;margin:.25rem 0 .4rem!important}
.eyebrow{color:#e2c45f;font-size:.7rem;font-weight:760;letter-spacing:.16em;text-transform:uppercase}
.subtitle{color:#bbb5c8;font-size:.95rem;margin:0;line-height:1.45}
.choice{padding:17px;border:1px solid #3a3f67;border-radius:17px;background:linear-gradient(145deg,rgba(28,32,63,.95),rgba(17,20,42,.95));min-height:135px}
.small{color:#aaa6b6;font-size:.86rem}
</style>
""",
    unsafe_allow_html=True,
)

SIGNS = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo","Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
NAKSHATRAS = ["Ashwini","Bharani","Krittika","Rohini","Mrigashirsha","Ardra","Punarvasu","Pushya","Ashlesha","Magha","Purva Phalguni","Uttara Phalguni","Hasta","Chitra","Swati","Vishakha","Anuradha","Jyeshtha","Mula","Purvashadha","Uttarashadha","Shravana","Dhanishta","Shatabhisha","Purva Bhadrapada","Uttara Bhadrapada","Revati"]
NAK_LORDS = ["Ketu","Venus","Sun","Moon","Mars","Rahu","Jupiter","Saturn","Mercury"]
DASHA_SEQ = ["Ketu","Venus","Sun","Moon","Mars","Rahu","Jupiter","Saturn","Mercury"]
DASHA_YEARS = {"Ketu":7,"Venus":20,"Sun":6,"Moon":10,"Mars":7,"Rahu":18,"Jupiter":16,"Saturn":19,"Mercury":17}
SIGN_LORDS = {"Aries":"Mars","Taurus":"Venus","Gemini":"Mercury","Cancer":"Moon","Leo":"Sun","Virgo":"Mercury","Libra":"Venus","Scorpio":"Mars","Sagittarius":"Jupiter","Capricorn":"Saturn","Aquarius":"Saturn","Pisces":"Jupiter"}
OWN = {"Sun":["Leo"],"Moon":["Cancer"],"Mars":["Aries","Scorpio"],"Mercury":["Gemini","Virgo"],"Jupiter":["Sagittarius","Pisces"],"Venus":["Taurus","Libra"],"Saturn":["Capricorn","Aquarius"]}
EXALT = {"Sun":"Aries","Moon":"Taurus","Mars":"Capricorn","Mercury":"Virgo","Jupiter":"Cancer","Venus":"Pisces","Saturn":"Libra"}
DEBIL = {"Sun":"Libra","Moon":"Scorpio","Mars":"Cancer","Mercury":"Pisces","Jupiter":"Capricorn","Venus":"Virgo","Saturn":"Aries"}
COMBUST = {"Moon":12,"Mars":17,"Mercury":14,"Jupiter":11,"Venus":10,"Saturn":15}
ASPECTS = {"Sun":[7],"Moon":[7],"Mercury":[7],"Venus":[7],"Mars":[4,7,8],"Jupiter":[5,7,9],"Saturn":[3,7,10]}
GEMS = {"Sun":"Ruby","Moon":"Pearl","Mars":"Red Coral","Mercury":"Emerald","Jupiter":"Yellow Sapphire","Venus":"Diamond / White Sapphire","Saturn":"Blue Sapphire","Rahu":"Hessonite (Gomed)","Ketu":"Cat's Eye"}
PLAIN = {"Sun":"identity, vitality and leadership","Moon":"mind, emotions and inner security","Mars":"action, courage and directed energy","Mercury":"thinking, communication and adaptability","Jupiter":"growth, wisdom and judgement","Venus":"relationships, harmony and creativity","Saturn":"discipline, responsibility and endurance","Rahu":"intense desire and unfamiliar territory","Ketu":"detachment, insight and inward focus"}
NAK_SIZE = 360 / 27
PADA_SIZE = NAK_SIZE / 4
FLAGS = swe.FLG_SWIEPH | swe.FLG_SIDEREAL


def sign_info(lon):
    lon %= 360
    i = int(lon / 30)
    return {"longitude": lon, "sign": SIGNS[i], "degree": lon % 30, "sign_index": i}


def nak_info(lon):
    lon %= 360
    i = min(int(lon / NAK_SIZE), 26)
    within = lon - i * NAK_SIZE
    return {"nakshatra": NAKSHATRAS[i], "pada": min(int(within / PADA_SIZE) + 1, 4), "lord": NAK_LORDS[i % 9], "within": within}


def fmt_deg(v):
    d = int(v); mf = (v - d) * 60; m = int(mf); s = round((mf - m) * 60)
    if s == 60: s = 0; m += 1
    if m == 60: m = 0; d += 1
    return f"{d:02d}° {m:02d}′ {s:02d}″"


def angle(a, b):
    d = abs((a - b) % 360)
    return min(d, 360 - d)


def body(jd, pid):
    x, _ = swe.calc_ut(jd, pid, FLAGS)
    out = sign_info(x[0]); out.update(nak_info(x[0])); out["retrograde"] = x[3] < 0
    return out


def add_years(dt, years):
    return dt + timedelta(days=years * 365.2425)


def vimshottari(moon_lon, birth, analysis_time):
    n = nak_info(moon_lon)
    lord = n["lord"]
    elapsed = DASHA_YEARS[lord] * (n["within"] / NAK_SIZE)
    cursor = add_years(birth, -elapsed)
    idx = DASHA_SEQ.index(lord)
    mds = []
    for _ in range(2):
        for off in range(9):
            current_lord = DASHA_SEQ[(idx + off) % 9]
            end = add_years(cursor, DASHA_YEARS[current_lord])
            mds.append({"lord": current_lord, "start": cursor, "end": end})
            cursor = end
    target_time = max(analysis_time, birth)
    md = next((x for x in mds if x["start"] <= target_time < x["end"]), mds[0])
    idx = DASHA_SEQ.index(md["lord"])
    cursor = md["start"]
    ads = []
    for off in range(9):
        current_lord = DASHA_SEQ[(idx + off) % 9]
        end = add_years(cursor, DASHA_YEARS[md["lord"]] * DASHA_YEARS[current_lord] / 120)
        ads.append({"lord": current_lord, "start": cursor, "end": end})
        cursor = end
    ad = next((x for x in ads if x["start"] <= target_time < x["end"]), ads[0])
    return {
        "mahadasha": md["lord"], "md_start": md["start"].date().isoformat(), "md_end": md["end"].date().isoformat(),
        "antardasha": ad["lord"], "ad_start": ad["start"].date().isoformat(), "ad_end": ad["end"].date().isoformat(),
        "analysis_date": target_time.date().isoformat(),
        "md_timeline": [{"Mahadasha":x["lord"],"Start":x["start"].date().isoformat(),"End":x["end"].date().isoformat(),"Current":"Yes" if x is md else ""} for x in mds[:9]],
        "ad_timeline": [{"Antardasha":x["lord"],"Start":x["start"].date().isoformat(),"End":x["end"].date().isoformat(),"Current":"Yes" if x is ad else ""} for x in ads],
    }


def calculate_chart(profile):
    dob, tob, lat, lon, tz = profile["dob"], profile["tob"], profile["lat"], profile["lon"], profile["tz"]
    swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)
    hour = tob.hour + tob.minute / 60 + tob.second / 3600
    jd = swe.julday(dob.year, dob.month, dob.day, hour - tz, swe.GREG_CAL)
    _, ascmc = swe.houses_ex(jd, lat, lon, b"W", swe.FLG_SIDEREAL)
    asc = sign_info(ascmc[0]); asc.update(nak_info(ascmc[0]))
    ids = {"Sun":swe.SUN,"Moon":swe.MOON,"Mars":swe.MARS,"Mercury":swe.MERCURY,"Jupiter":swe.JUPITER,"Venus":swe.VENUS,"Saturn":swe.SATURN,"Rahu":swe.MEAN_NODE}
    ps = {name: body(jd, pid) for name, pid in ids.items()}
    ketu = sign_info(ps["Rahu"]["longitude"] + 180); ketu.update(nak_info(ketu["longitude"])); ketu["retrograde"] = True; ps["Ketu"] = ketu
    rules = {n: [] for n in ["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn"]}
    for h in range(1, 13):
        rules[SIGN_LORDS[SIGNS[(asc["sign_index"] + h - 1) % 12]]].append(h)
    for name, p in ps.items():
        p["house"] = ((p["sign_index"] - asc["sign_index"]) % 12) + 1
        labels = []
        if name in OWN and p["sign"] in OWN[name]: labels.append("Own sign")
        if name in EXALT and p["sign"] == EXALT[name]: labels.append("Exaltation sign")
        if name in DEBIL and p["sign"] == DEBIL[name]: labels.append("Debilitation sign")
        if p["retrograde"] and name not in ("Rahu", "Ketu"): labels.append("Retrograde")
        if name in COMBUST and angle(p["longitude"], ps["Sun"]["longitude"]) <= COMBUST[name]: labels.append("Combustion screening flag")
        p["condition"] = labels or ["No major screening flag"]
        p["rules_houses"] = rules.get(name, [])
    conjunctions = []
    names = list(ps)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if ps[a]["sign_index"] == ps[b]["sign_index"]:
                conjunctions.append({"Planets":f"{a} + {b}","Sign":ps[a]["sign"],"House":ps[a]["house"],"Separation":round(angle(ps[a]["longitude"],ps[b]["longitude"]),2)})
    aspects = []
    for name, offsets in ASPECTS.items():
        for off in offsets:
            target = ((ps[name]["house"] + off - 2) % 12) + 1
            targets = [x for x, p in ps.items() if p["house"] == target and x != name]
            aspects.append({"Planet":name,"Aspect":f"{off}th","From":ps[name]["house"],"To":target,"Target planets":", ".join(targets) or "—"})
    ak = max(["Sun","Moon","Mars","Mercury","Jupiter","Venus","Saturn"], key=lambda n: ps[n]["degree"])
    birth = (datetime(dob.year,dob.month,dob.day,tob.hour,tob.minute,tob.second) - timedelta(hours=tz)).replace(tzinfo=timezone.utc)
    timing = vimshottari(ps["Moon"]["longitude"], birth, datetime.now(timezone.utc))
    return {"ascendant":asc,"planets":ps,"atmakaraka":ak,"timing":timing,"conjunctions":conjunctions,"aspects":aspects,"ayanamsa":swe.get_ayanamsa_ut(jd)}


@st.cache_resource(show_spinner=False)
def get_embeddings():
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)


@st.cache_resource(show_spinner=False)
def get_store():
    path = "chroma_db"
    db = os.path.join(path, "chroma.sqlite3")
    if not os.path.isfile(db): return None, 0
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
        with open(fn, encoding="utf-8") as handle:
            data = json.load(handle)
        rows.extend(data.get("records", []))
        for speaker in data.get("speakers", []):
            for record in speaker.get("records", []):
                item = dict(record); item.setdefault("speaker", speaker.get("speaker")); rows.append(item)
    return list({r.get("id", str(i)): r for i, r in enumerate(rows)}.values())


def search_local(query, k=6):
    store, count = get_store()
    if not store: return [], count
    try: return store.as_retriever(search_kwargs={"k": k}).invoke(query), count
    except Exception: return [], count


def search_teachers(query, k=5):
    terms = [x.lower() for x in re.findall(r"[A-Za-zÀ-ÿ]+", query) if len(x) > 2]
    scored = []
    for record in get_practitioners():
        if record.get("rag_eligible") is False: continue
        text = json.dumps(record, ensure_ascii=False).lower()
        score = sum(1 for term in terms if term in text) + (2 if record.get("exact_answer_eligible") else 0)
        if score: scored.append((score, record))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:k]]


def secret(name):
    try: return st.secrets.get(name, "")
    except Exception: return ""


def effective_mode(requested):
    if requested == "Offline": return "Offline"
    if requested == "Deep Research" and secret("TAVILY_API_KEY") and secret("ZAI_API_KEY"): return "Deep Research"
    return "Trusted Library"


def get_llm(max_tokens=2600):
    return ChatOpenAI(model="glm-4.5-flash", openai_api_key=secret("ZAI_API_KEY"), openai_api_base="https://api.z.ai/api/paas/v4", temperature=.35, max_tokens=max_tokens, extra_body={"thinking":{"type":"disabled"}})


def geocode_place(place):
    query = urllib.parse.urlencode({"q": place, "format":"jsonv2", "limit":5, "addressdetails":1})
    request = urllib.request.Request(
        "https://nominatim.openstreetmap.org/search?" + query,
        headers={
            "User-Agent":"AncientWisdomSynthesis/1.32 birthplace lookup",
            "Accept-Language":"en",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8"))
    return [{
        "label": item.get("display_name", "Result"),
        "lat": float(item["lat"]),
        "lon": float(item["lon"]),
    } for item in data]


def timezone_for_coordinates(lat, lon, dob, tob):
    """Resolve IANA zone by coordinates, then compute the historic offset locally."""
    query = urllib.parse.urlencode({"latitude": lat, "longitude": lon})
    urls = [
        "https://timeapi.io/api/Time/current/coordinate?" + query,
        "https://timeapi.io/api/TimeZone/coordinate?" + query,
    ]
    payload = None
    last_error = None
    for url in urls:
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent":"AncientWisdomSynthesis/1.32 timezone lookup"},
            )
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if payload:
                break
        except Exception as exc:
            last_error = exc
    if not payload:
        raise RuntimeError(f"Timezone lookup unavailable: {last_error}")
    zone_name = (
        payload.get("timeZone")
        or payload.get("timezone")
        or payload.get("timeZoneId")
        or payload.get("iana")
    )
    if not zone_name and isinstance(payload.get("data"), dict):
        data = payload["data"]
        zone_name = data.get("timeZone") or data.get("timezone") or data.get("iana")
    if not zone_name:
        raise RuntimeError("Timezone service did not return an IANA timezone.")
    try:
        local_dt = datetime(dob.year, dob.month, dob.day, tob.hour, tob.minute, tob.second, tzinfo=ZoneInfo(zone_name))
    except ZoneInfoNotFoundError as exc:
        raise RuntimeError(f"Timezone data unavailable for {zone_name}") from exc
    offset = local_dt.utcoffset()
    if offset is None:
        raise RuntimeError("Historical UTC offset could not be calculated.")
    return zone_name, offset.total_seconds() / 3600.0, local_dt.tzname() or ""


def _init_profile_widgets():
    saved = st.session_state.get("saved_profile", default_profile())
    defaults = {
        "w_name": saved["name"],
        "w_day": int(saved["dob"].day),
        "w_month": int(saved["dob"].month),
        "w_year": int(saved["dob"].year),
        "w_tob": saved["tob"],
        "w_place_query": saved["place"],
        "w_lat": float(saved["lat"]),
        "w_lon": float(saved["lon"]),
        "w_tz": float(saved["tz"]),
        "w_zone_name": saved.get("zone_name", ""),
        "w_zone_abbr": saved.get("zone_abbr", ""),
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _apply_selected_location():
    results = st.session_state.get("location_results", [])
    index = st.session_state.get("w_location_index", 0)
    if not results or not (0 <= index < len(results)):
        return
    selected = results[index]
    st.session_state.w_place_query = selected["label"]
    st.session_state.w_lat = float(selected["lat"])
    st.session_state.w_lon = float(selected["lon"])
    st.session_state.w_zone_name = ""
    st.session_state.w_zone_abbr = ""
    try:
        dob = date(int(st.session_state.w_year), int(st.session_state.w_month), int(st.session_state.w_day))
        zone_name, utc_offset, zone_abbr = timezone_for_coordinates(
            selected["lat"], selected["lon"], dob, st.session_state.w_tob
        )
        st.session_state.w_tz = float(utc_offset)
        st.session_state.w_zone_name = zone_name
        st.session_state.w_zone_abbr = zone_abbr
        st.session_state.location_lookup_message = (
            f"Location and birth-date timezone resolved: {zone_name} "
            f"({zone_abbr}), UTC {utc_offset:+.2f}."
        )
    except Exception as exc:
        st.session_state.location_lookup_message = (
            "Coordinates were filled, but the historical timezone could not be resolved. "
            f"Verify the UTC offset manually. Details: {exc}"
        )


def profile_signature(profile):
    return (profile["name"], profile["dob"].isoformat(), profile["tob"].isoformat(), profile["place"], round(profile["lat"],6), round(profile["lon"],6), round(profile["tz"],2))


def default_profile():
    return {"name":"","dob":date(1990,1,1),"tob":datetime.strptime("12:00","%H:%M").time(),"place":"","lat":22.3193,"lon":114.1694,"tz":8.0}


def profile_panel():
    _init_profile_widgets()
    with st.sidebar:
        st.markdown("### Your Profile")
        st.text_input("Name", key="w_name", placeholder="Your name")
        c1, c2, c3 = st.columns([1, 1.5, 1.2])
        with c1:
            st.number_input("Day", 1, 31, 1, key="w_day")
        with c2:
            st.selectbox(
                "Month", list(range(1, 13)), key="w_month",
                format_func=lambda x: datetime(2000, x, 1).strftime("%B"),
            )
        with c3:
            st.number_input("Year", 1900, 2050, 1, key="w_year")
        st.time_input("Exact birth time", key="w_tob")

        st.markdown("#### Birthplace")
        st.text_input(
            "City, state/province, country",
            key="w_place_query",
            placeholder="e.g. Bharwain, Himachal Pradesh, India",
        )
        if st.button("Find birthplace and timezone", use_container_width=True):
            query = st.session_state.w_place_query.strip()
            if not query:
                st.warning("Enter a birthplace first.")
            else:
                try:
                    results = geocode_place(query)
                    st.session_state.location_results = results
                    st.session_state.w_location_index = 0
                    if results:
                        _apply_selected_location()
                    else:
                        st.warning("No matching birthplace was found. Try adding the country or region.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Birthplace lookup failed: {exc}")

        results = st.session_state.get("location_results", [])
        if results:
            labels = [r["label"] for r in results]
            st.selectbox(
                "Choose the correct result",
                options=list(range(len(results))),
                format_func=lambda i: labels[i],
                key="w_location_index",
                on_change=_apply_selected_location,
            )

        message = st.session_state.get("location_lookup_message")
        if message:
            if "could not" in message.lower():
                st.warning(message)
            else:
                st.success(message)

        with st.expander("Location details and manual correction", expanded=False):
            st.number_input("Latitude", -90.0, 90.0, key="w_lat", format="%.6f")
            st.number_input("Longitude", -180.0, 180.0, key="w_lon", format="%.6f")
            st.number_input("UTC offset at birth", -12.0, 14.0, step=.25, key="w_tz")
            if st.session_state.w_zone_name:
                st.caption(
                    f"Timezone: {st.session_state.w_zone_name} "
                    f"({st.session_state.w_zone_abbr or 'historical abbreviation unavailable'})"
                )
            st.caption(
                "Coordinates come from OpenStreetMap search. The UTC offset is calculated "
                "for the entered birth date/time when timezone resolution succeeds. Verify "
                "ambiguous or historically unusual times before generating the chart."
            )

        confirmed = st.checkbox(
            "I confirm the birth time, selected birthplace and calculated/manual UTC offset",
            key="w_confirmed",
        )

        st.markdown("### Knowledge source")
        mode = st.radio(
            "Knowledge source", KNOWLEDGE_MODES,
            index=KNOWLEDGE_MODES.index(st.session_state.get("knowledge_mode", "Deep Research")),
            label_visibility="collapsed",
        )
        depth = st.select_slider(
            "Answer detail", ANSWER_DEPTHS,
            value=st.session_state.get("depth", "Detailed"),
        )
        advanced = st.toggle(
            "Show advanced Vedic details",
            value=st.session_state.get("advanced", False),
        )

        if st.button("Save and confirm profile", type="primary", use_container_width=True):
            try:
                dob = date(int(st.session_state.w_year), int(st.session_state.w_month), int(st.session_state.w_day))
            except ValueError as exc:
                st.error(f"Invalid date of birth: {exc}")
                dob = None
            if not st.session_state.w_name.strip():
                st.error("Enter a name.")
            elif not st.session_state.w_place_query.strip():
                st.error("Find and select a birthplace, or enter the coordinates manually.")
            elif not confirmed:
                st.error("Confirm the birth details before saving.")
            elif dob:
                new_profile = {
                    "name": st.session_state.w_name.strip(),
                    "dob": dob,
                    "tob": st.session_state.w_tob,
                    "place": st.session_state.w_place_query.strip(),
                    "lat": float(st.session_state.w_lat),
                    "lon": float(st.session_state.w_lon),
                    "tz": float(st.session_state.w_tz),
                    "zone_name": st.session_state.w_zone_name,
                    "zone_abbr": st.session_state.w_zone_abbr,
                }
                old_signature = st.session_state.get("saved_profile_signature")
                new_signature = profile_signature(new_profile)
                st.session_state.saved_profile = new_profile
                st.session_state.saved_profile_signature = new_signature
                st.session_state.knowledge_mode = mode
                st.session_state.depth = depth
                st.session_state.advanced = advanced
                if old_signature != new_signature:
                    for key in [
                        "chart", "chart_signature", "personal_report", "personal_layers",
                        "remedy_answer", "remedy_sources", "last_sources",
                    ]:
                        st.session_state.pop(key, None)
                st.success("Profile saved and confirmed.")
                st.rerun()

        saved_now = st.session_state.get("saved_profile")
        if saved_now:
            st.success(
                f"Confirmed: {saved_now['place']} · "
                f"{saved_now['lat']:.4f}, {saved_now['lon']:.4f} · "
                f"UTC {saved_now['tz']:+.2f}"
            )
        effective = effective_mode(mode)
        if effective != mode:
            st.info(f"{mode} is unavailable; using {effective}.")
        return {
            "saved_profile": saved_now,
            "knowledge_mode": mode,
            "effective_mode": effective,
            "depth": depth,
            "advanced": advanced,
        }


def ensure_chart(cfg, force=False):
    profile = cfg.get("saved_profile")
    if not profile: return None
    signature = profile_signature(profile)
    if force or st.session_state.get("chart_signature") != signature:
        st.session_state.chart = calculate_chart(profile)
        st.session_state.chart_signature = signature
    return st.session_state.chart


def local_answer(question, docs, teachers, personal=None):
    parts = []
    if personal: parts.append(f"**Personal context:** {personal['timing']['mahadasha']} major period, {personal['timing']['antardasha']} sub-period and {personal['atmakaraka']} core significator.")
    if teachers:
        text = teachers[0].get("summary") or teachers[0].get("explanation_text") or ""
        if text: parts.append(" ".join(text.split()[:120]))
    if docs:
        text = " ".join(docs[0].page_content.split())
        if text: parts.append("**Trusted library:** " + " ".join(text.split()[:130]))
    if not parts: return "I could not find enough verified material. **Needs Verification.**"
    parts.append("**Practical note:** gemstones, herbs, fasting, advanced mantra and medical claims require verification or qualified guidance.")
    return "\n\n".join(parts)


def synthesize(question, docs, teachers, personal, cfg):
    mode = effective_mode(cfg["knowledge_mode"])
    if mode == "Offline" or not secret("ZAI_API_KEY"):
        return local_answer(question, docs, teachers, personal)
    evidence = []
    for i, d in enumerate(docs[:5], 1):
        m = d.metadata or {}; evidence.append(f"[C{i}] {m.get('book') or m.get('source','Unknown')} page {m.get('pdf_page','Needs Verification')}\n{' '.join(d.page_content.split())[:1200]}")
    for i, r in enumerate(teachers[:4], 1):
        evidence.append(f"[P{i}] {r.get('speaker') or 'Needs Verification'} | {r.get('topic') or r.get('title') or 'Indexed teaching'}\n{(r.get('summary') or r.get('explanation_text') or '')[:900]}")
    lengths = {"Simple":"180-300 words","Detailed":"700-1100 words","Advanced":"1300-1900 words"}
    prompt = f"""Answer the user's question using the locked calculated facts and retrieved evidence.\nQuestion: {question}\nDepth: {cfg['depth']} ({lengths[cfg['depth']]}).\nPersonal chart: {json.dumps(personal,default=str) if personal else 'not supplied'}\nEvidence:\n{chr(10).join(evidence)}\nRules: explain Sanskrit immediately; calculate nothing yourself; distinguish calculated fact, classical source, practitioner view and Needs Verification; do not invent remedies, medical claims, universal chakra mappings, mantra counts or gemstone suitability; provide a useful synthesis and practical takeaway."""
    try: return get_llm(3000 if cfg["depth"] != "Advanced" else 5200).invoke(prompt).content
    except Exception: return local_answer(question, docs, teachers, personal)


def navigate(page, question=None):
    st.session_state.page = page
    if question: st.session_state.pending_question = question
    st.rerun()


def home_page(cfg):
    st.markdown("## How can I help you today?")
    with st.form("home_question_form", clear_on_submit=True):
        question = st.text_input("Ask anything", placeholder="What should I focus on now? What does Saturn mean? Which mantra may help focus?", label_visibility="collapsed")
        submit = st.form_submit_button("Ask Ancient Wisdom", type="primary", use_container_width=True)
    if submit and question.strip(): navigate("Ask", question.strip())
    cols = st.columns(3)
    cards = [
        ("🔮 My Personal Reading","Deep synthesis from your confirmed birth details.","Build My Reading","My Reading"),
        ("🪷 My Remedies","Chart-specific practical actions and qualified traditional options.","View My Remedies","My Remedies"),
        ("📚 Explore Knowledge","Search the 21-source library, topics and teachers.","Explore Knowledge","Explore"),
    ]
    for i, (title, desc, label, page) in enumerate(cards):
        with cols[i]:
            st.markdown(f"<div class='choice'><h3>{title}</h3><p>{desc}</p></div>", unsafe_allow_html=True)
            if st.button(label, key=f"home_{i}", use_container_width=True): navigate(page)


def ask_page(cfg):
    st.markdown("## Ask Ancient Wisdom")
    if "chat" not in st.session_state: st.session_state.chat = []
    for item in st.session_state.chat:
        with st.chat_message(item["role"]): st.markdown(item["content"])
    question = st.session_state.pop("pending_question", None) or st.chat_input("What's on your mind?")
    if question:
        personal = st.session_state.get("chart")
        query = question
        if personal: query += f" {personal['timing']['mahadasha']} Mahadasha {personal['timing']['antardasha']} Antardasha {personal['atmakaraka']} Atmakaraka"
        docs, _ = search_local(query, 7); teachers = search_teachers(query, 6)
        response = synthesize(question, docs, teachers, personal, cfg)
        st.session_state.chat.extend([{"role":"user","content":question},{"role":"assistant","content":response}])
        st.session_state.last_sources = (docs, teachers)
        st.rerun()
    if st.session_state.get("last_sources"):
        docs, teachers = st.session_state.last_sources
        with st.expander(f"Sources · {len(docs[:5])} classical/official · {len(teachers[:4])} practitioner"):
            for d in docs[:5]:
                m = d.metadata or {}; st.markdown(f"- **{m.get('book') or m.get('source','Unknown')}** · page {m.get('pdf_page','Needs Verification')}")
            for r in teachers[:4]: st.markdown(f"- **{r.get('speaker') or 'Needs Verification'}** · {r.get('topic') or r.get('title') or 'Indexed teaching'}")


def reading_page(cfg):
    st.markdown("## My Personal Reading")
    if not cfg.get("saved_profile"):
        st.warning("Save and confirm your profile first.")
        return
    if st.button("Generate Full Personal Synthesis", type="primary", use_container_width=True):
        c = ensure_chart(cfg, True)
        t = c["timing"]
        query = f"{c['ascendant']['sign']} Ascendant {c['atmakaraka']} Atmakaraka {t['mahadasha']} Mahadasha {t['antardasha']} Antardasha personal Jyotish Ayurveda yoga mantra remedies"
        docs, _ = search_local(query, 12); teachers = search_teachers(query, 10)
        st.session_state.personal_report = synthesize("Create a full integrated personal report with astrology, current timing, Ayurveda support, yoga/meditation, mantra, chakra perspectives, remedies, gemstone caution and three priorities now.", docs, teachers, c, cfg)
        st.session_state.personal_sources = (docs, teachers)
    c = st.session_state.get("chart")
    if not c: return
    t = c["timing"]
    a,b,d,e = st.columns(4)
    a.metric("How you approach life", c["ascendant"]["sign"], "Ascendant")
    b.metric("Emotional pattern", f"{c['planets']['Moon']['nakshatra']} · quarter {c['planets']['Moon']['pada']}", "Moon Nakshatra")
    d.metric("Major life period", t["mahadasha"], f"to {t['md_end']}")
    e.metric("Current sub-period", t["antardasha"], f"to {t['ad_end']}")
    st.markdown(f"### Core developmental planet: {c['atmakaraka']}")
    st.write(f"This chart gives special developmental importance to {PLAIN[c['atmakaraka']] }.")
    if st.session_state.get("personal_report"): st.markdown(st.session_state.personal_report)
    if cfg["advanced"]:
        rows = [{"Planet":n,"Sign":p["sign"],"Degree":fmt_deg(p["degree"]),"House":p["house"],"Nakshatra":p["nakshatra"],"Pada":p["pada"],"Condition":"; ".join(p["condition"]),"Rules houses":", ".join(map(str,p["rules_houses"])) or "—"} for n,p in c["planets"].items()]
        st.dataframe(rows, use_container_width=True, hide_index=True)


def remedies_page(cfg):
    st.markdown("## My Remedies")
    c = ensure_chart(cfg)
    if not c:
        st.info("Save your profile and generate My Personal Reading first.")
        return
    t = c["timing"]
    st.markdown(f"### Current focus: {t['mahadasha']} major period · {t['antardasha']} sub-period · {c['atmakaraka']} core planet")
    query = f"{t['mahadasha']} {t['antardasha']} {c['atmakaraka']} remedies mantra dana behaviour yoga Ayurveda gemstone strengthen pacify"
    docs, _ = search_local(query, 10); teachers = search_teachers(query, 10)
    if st.button("Build Detailed Remedy Plan", type="primary", use_container_width=True):
        st.session_state.remedy_answer = synthesize("Build a ranked personal remedy plan. For every action state purpose, chart reason, source basis, practical application and guidance level. Separate low-risk options from specialist verification.", docs, teachers, c, cfg)
    if st.session_state.get("remedy_answer"): st.markdown(st.session_state.remedy_answer)
    st.warning("Gemstones, herbs, fasting, advanced pranayama and Bija/Tantric practices require verification or qualified guidance.")


def explore_page(cfg):
    st.markdown("## Explore Ancient Wisdom")
    t1, t2 = st.tabs(["Search Library", "Teachers"])
    with t1:
        query = st.text_input("Search the 21-source library", placeholder="e.g. Saturn and Vata, mantra initiation, Jupiter remedies")
        if query:
            docs, _ = search_local(query, 8)
            answer = synthesize(query, docs, search_teachers(query, 5), None, cfg)
            st.markdown(answer)
            with st.expander("View retrieved passages"):
                for d in docs:
                    m = d.metadata or {}; st.markdown(f"**{m.get('book') or m.get('source','Unknown')} · page {m.get('pdf_page','Needs Verification')}**"); st.write(" ".join(d.page_content.split())[:550] + "…")
    with t2:
        records = get_practitioners(); teachers = sorted({r.get("speaker") for r in records if r.get("speaker")})
        if teachers:
            teacher = st.selectbox("Choose a teacher", teachers)
            for r in [x for x in records if x.get("speaker") == teacher][:30]:
                with st.expander(r.get("topic") or r.get("title") or r.get("video_title") or "Indexed teaching"):
                    st.write(r.get("summary") or r.get("explanation_text") or "Needs Verification")


def main():
    cfg = profile_panel()
    st.markdown("<div class='hero'><div class='eyebrow'>PERSONAL WISDOM & REMEDY ENGINE</div><h1>Ancient Wisdom Synthesis</h1><p class='subtitle'>Personal guidance from calculated Vedic astrology and a searchable library spanning Jyotish, Ayurveda, yoga, mantra, remedies and practitioner perspectives.</p></div>", unsafe_allow_html=True)
    if "page" not in st.session_state: st.session_state.page = "Home"
    chosen = st.radio("Navigation", PAGES, horizontal=True, index=PAGES.index(st.session_state.page), label_visibility="collapsed")
    if chosen != st.session_state.page: st.session_state.page = chosen; st.rerun()
    with st.expander("Library & system status", expanded=False):
        _, count = get_store()
        st.write(f"Ancient Wisdom library: **{count:,} indexed passages**")
        st.write(f"Practitioner knowledge: **{len(get_practitioners())} structured records**")
        st.write(f"Knowledge mode: **{cfg['effective_mode']}**")
    st.divider()
    if st.session_state.page == "Home": home_page(cfg)
    elif st.session_state.page == "Ask": ask_page(cfg)
    elif st.session_state.page == "My Reading": reading_page(cfg)
    elif st.session_state.page == "My Remedies": remedies_page(cfg)
    else: explore_page(cfg)


if __name__ == "__main__":
    main()
