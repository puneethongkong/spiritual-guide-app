import html
import json
import os
from datetime import date, datetime, timezone

import plotly.graph_objects as go
import streamlit as st
import swisseph as swe
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_openai import ChatOpenAI

# ============================================================
# 1. PAGE CONFIGURATION
# ============================================================
st.set_page_config(
    page_title="Ancient Wisdom Synthesis",
    page_icon="🕉️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        .stApp {
            background-color: #0F1226;
            color: #EAE6DF;
        }
        h1, h2, h3, h4 {
            color: #EAE6DF;
        }
        p, li, .stMarkdown {
            color: #C9C4BB;
        }
        hr {
            border-color: #2A2D4A;
        }
        [data-testid="stMetric"] {
            background: #171A33;
            border: 1px solid #2A2D4A;
            border-radius: 12px;
            padding: 16px;
        }
        [data-testid="stMetricLabel"] {
            color: #9C9A93 !important;
        }
        [data-testid="stMetricValue"] {
            color: #C9A84C !important;
        }
        .stButton > button {
            background: linear-gradient(135deg, #4A3F78, #7C5CBF);
            color: white;
            border: none;
            border-radius: 28px;
            padding: 10px 28px;
            font-weight: 600;
        }
        [data-testid="stSidebar"] {
            background-color: #12142B;
            border-right: 1px solid #2A2D4A;
        }
        [data-testid="stChatMessage"] {
            background: #171A33;
            border: 1px solid #2A2D4A;
            border-radius: 12px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# 2. CONSTANTS
# ============================================================
SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashirsha", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni",
    "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha",
    "Jyeshtha", "Mula", "Purvashadha", "Uttarashadha", "Shravana",
    "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada",
    "Revati",
]

NAKSHATRA_LORDS = [
    "Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu",
    "Jupiter", "Saturn", "Mercury",
]

NAKSHATRA_SIZE = 360.0 / 27.0
PADA_SIZE = NAKSHATRA_SIZE / 4.0
SIDEREAL_FLAGS = swe.FLG_SWIEPH | swe.FLG_SIDEREAL

PLANET_MAPPING = {
    "Jupiter": {
        "chakra": "Ajna (Third Eye)",
        "dosha": "Kapha",
        "theme": "Wisdom & Expansion",
        "nama": "N523 Shadanana",
    },
    "Mars": {
        "chakra": "Manipura (Solar Plexus)",
        "dosha": "Pitta",
        "theme": "Courage & Action",
        "nama": "N503 Lakinyamba",
    },
    "Venus": {
        "chakra": "Svadhisthana (Sacral)",
        "dosha": "Kapha",
        "theme": "Love & Creativity",
        "nama": "N513 Kakini",
    },
    "Saturn": {
        "chakra": "Muladhara (Root)",
        "dosha": "Vata",
        "theme": "Discipline & Grounding",
        "nama": "N520 Sakinyamba",
    },
    "Moon": {
        "chakra": "Anahata (Heart)",
        "dosha": "Kapha",
        "theme": "Emotion & Nurturing",
        "nama": "N494 Rakinyamba",
    },
    "Mercury": {
        "chakra": "Vishuddha (Throat)",
        "dosha": "Vata",
        "theme": "Communication & Logic",
        "nama": "N484 Dakinishvari",
    },
}

# ============================================================
# 3. SIDEREAL ASTROLOGY ENGINE - PHASE 1A
# ============================================================
def normalise_longitude(value: float) -> float:
    return value % 360.0


def format_degree(value: float) -> str:
    value = value % 30.0
    degrees = int(value)
    minutes_float = (value - degrees) * 60.0
    minutes = int(minutes_float)
    seconds = int(round((minutes_float - minutes) * 60.0))

    if seconds == 60:
        seconds = 0
        minutes += 1
    if minutes == 60:
        minutes = 0
        degrees += 1

    return f"{degrees:02d}° {minutes:02d}′ {seconds:02d}″"


def get_sign_details(longitude: float) -> dict:
    longitude = normalise_longitude(longitude)
    sign_index = int(longitude / 30.0)
    return {
        "sign": SIGNS[sign_index],
        "sign_index": sign_index,
        "degree_in_sign": longitude % 30.0,
        "longitude": longitude,
    }


def get_nakshatra_details(longitude: float) -> dict:
    longitude = normalise_longitude(longitude)
    nakshatra_index = min(int(longitude / NAKSHATRA_SIZE), 26)
    position_in_nakshatra = longitude - (nakshatra_index * NAKSHATRA_SIZE)
    pada = min(int(position_in_nakshatra / PADA_SIZE) + 1, 4)

    return {
        "nakshatra": NAKSHATRAS[nakshatra_index],
        "nakshatra_index": nakshatra_index,
        "nakshatra_lord": NAKSHATRA_LORDS[nakshatra_index % 9],
        "pada": pada,
        "position_in_nakshatra": position_in_nakshatra,
    }


def local_birth_to_julian_day(dob: date, tob, utc_offset: float) -> float:
    local_hour = tob.hour + tob.minute / 60.0 + tob.second / 3600.0
    universal_hour = local_hour - float(utc_offset)
    return swe.julday(dob.year, dob.month, dob.day, universal_hour, swe.GREG_CAL)


def sidereal_planet_position(jd_ut: float, planet_id: int) -> dict:
    data, return_flags = swe.calc_ut(jd_ut, planet_id, SIDEREAL_FLAGS)
    longitude = normalise_longitude(data[0])
    speed = data[3]
    details = get_sign_details(longitude)
    details.update(
        {
            "speed": speed,
            "retrograde": speed < 0,
            "return_flags": return_flags,
        }
    )
    return details


def calculate_vedic_profile(dob, tob, lat, lon, utc_offset):
    if not -90.0 <= lat <= 90.0:
        raise ValueError("Latitude must be between -90 and +90 degrees.")
    if not -180.0 <= lon <= 180.0:
        raise ValueError("Longitude must be between -180 and +180 degrees.")
    if not -12.0 <= utc_offset <= 14.0:
        raise ValueError("UTC offset must be between -12 and +14 hours.")

    jd_ut = local_birth_to_julian_day(dob, tob, utc_offset)

    # Explicit Vedic sidereal mode: Lahiri / Chitrapaksha.
    swe.set_sid_mode(swe.SIDM_LAHIRI, 0, 0)

    # houses_ex accepts the sidereal flag. Whole Sign houses are used.
    _, ascmc = swe.houses_ex(jd_ut, lat, lon, b"W", swe.FLG_SIDEREAL)
    ascendant_longitude = normalise_longitude(ascmc[0])
    ascendant = get_sign_details(ascendant_longitude)
    ascendant.update(get_nakshatra_details(ascendant_longitude))

    planet_ids = {
        "Sun": swe.SUN,
        "Moon": swe.MOON,
        "Mars": swe.MARS,
        "Mercury": swe.MERCURY,
        "Jupiter": swe.JUPITER,
        "Venus": swe.VENUS,
        "Saturn": swe.SATURN,
        "Rahu": swe.MEAN_NODE,
    }

    planets = {}
    for planet_name, planet_id in planet_ids.items():
        planet = sidereal_planet_position(jd_ut, planet_id)
        planet.update(get_nakshatra_details(planet["longitude"]))
        planets[planet_name] = planet

    # Ketu is exactly opposite Rahu.
    ketu_longitude = normalise_longitude(planets["Rahu"]["longitude"] + 180.0)
    ketu = get_sign_details(ketu_longitude)
    ketu.update(get_nakshatra_details(ketu_longitude))
    ketu.update({"speed": planets["Rahu"]["speed"], "retrograde": True})
    planets["Ketu"] = ketu

    # Jaimini seven-karaka convention: Sun through Saturn, excluding Rahu/Ketu.
    chara_karaka_planets = [
        "Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"
    ]
    atmakaraka = max(
        chara_karaka_planets,
        key=lambda name: planets[name]["degree_in_sign"],
    )

    moon_nakshatra = get_nakshatra_details(planets["Moon"]["longitude"])
    ayanamsa_value = swe.get_ayanamsa_ut(jd_ut)

    mapping = PLANET_MAPPING.get(
        atmakaraka,
        {
            "chakra": "Needs Verification",
            "dosha": "Needs Verification",
            "theme": "Needs Verification",
            "nama": "Needs Verification",
        },
    )

    now_utc = datetime.now(timezone.utc)
    transit_jd = swe.julday(
        now_utc.year,
        now_utc.month,
        now_utc.day,
        now_utc.hour + now_utc.minute / 60.0 + now_utc.second / 3600.0,
        swe.GREG_CAL,
    )
    saturn_transit = sidereal_planet_position(transit_jd, swe.SATURN)
    jupiter_transit = sidereal_planet_position(transit_jd, swe.JUPITER)

    return {
        "calculation_system": "Lahiri / Chitrapaksha sidereal zodiac",
        "house_system": "Whole Sign",
        "chara_karaka_system": "Seven-karaka system; Rahu and Ketu excluded",
        "julian_day_ut": jd_ut,
        "ayanamsa_value": ayanamsa_value,
        "ascendant": ascendant,
        "planets": planets,
        "moon_nakshatra": moon_nakshatra["nakshatra"],
        "moon_pada": moon_nakshatra["pada"],
        "moon_nakshatra_lord": moon_nakshatra["nakshatra_lord"],
        "atmakaraka": atmakaraka,
        "atmakaraka_degree": planets[atmakaraka]["degree_in_sign"],
        "saturn_transit": saturn_transit,
        "jupiter_transit": jupiter_transit,
        "transit_date_utc": now_utc.date().isoformat(),
        **mapping,
    }

# ============================================================
# 4. KNOWLEDGE BASE AND Z.AI
# ============================================================
@st.cache_resource(show_spinner=False)
def load_knowledge_base():
    # The GitHub screenshot shows chroma.sqlite3 in the repository root.
    # Chroma expects the directory containing that file as persist_directory.
    candidate_directories = [".", "chroma_db"]
    persist_directory = None

    for directory in candidate_directories:
        database_path = os.path.join(directory, "chroma.sqlite3")
        if os.path.isfile(database_path):
            persist_directory = directory
            break

    if persist_directory is None:
        raise FileNotFoundError(
            "chroma.sqlite3 was not found in the repository root or chroma_db folder."
        )

    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vectorstore = Chroma(
        persist_directory=persist_directory,
        embedding_function=embeddings,
    )

    try:
        collection_count = vectorstore._collection.count()
    except Exception:
        collection_count = 0

    if collection_count == 0:
        raise RuntimeError(
            "The Chroma database opened but contains no retrievable documents."
        )

    return vectorstore.as_retriever(search_kwargs={"k": 4})


def build_llm(api_key: str):
    return ChatOpenAI(
        model="glm-4.5-flash",
        openai_api_key=api_key,
        openai_api_base="https://api.z.ai/api/paas/v4",
        temperature=0.6,
        max_tokens=2000,
        extra_body={"thinking": {"type": "disabled"}},
    )


def build_prompt(user_name, chart, scores, balance, source_context):
    planet_summary = {
        name: {
            "sign": value["sign"],
            "degree": round(value["degree_in_sign"], 4),
            "nakshatra": value["nakshatra"],
            "pada": value["pada"],
            "retrograde": value.get("retrograde", False),
        }
        for name, value in chart["planets"].items()
    }

    return f"""
Return ONLY valid JSON, without markdown or code fences.

You are interpreting calculated Vedic astrology data, a non-clinical self-reflection
profile, and retrieved classical-source passages. Do not recalculate or alter any
astronomical fact supplied below. Do not present symbolic correspondences as medical
diagnoses. Do not claim certainty, prediction, or supernatural proof.

Use exactly this JSON structure:
{{
  "executive_summary": "3 to 5 concise sentences",
  "vedic_interpretation": "Interpret the supplied sidereal facts",
  "psychological_interpretation": "Interpret the self-reported indicators cautiously",
  "ayurvedic_interpretation": "Describe the symbolic correspondence, not constitution or diagnosis",
  "convergence": "Explain possible converging themes without claiming causation",
  "practical_actions": [
    {{"action": "", "why": "", "how": "", "frequency": ""}}
  ],
  "vedic_practice": {{
    "mantra": "",
    "nama": "{chart['nama']}",
    "practice": "",
    "explanation": ""
  }},
  "cautions": ""
}}

USER
Name: {user_name}
Presentation balance: {balance}/100, where 0 is practical/modern language and 100 is traditional/Vedic language.

CALCULATED FACTS
Calculation system: {chart['calculation_system']}
House system: {chart['house_system']}
Ayanamsa at birth: {chart['ayanamsa_value']:.6f} degrees
Ascendant: {chart['ascendant']['sign']} {chart['ascendant']['degree_in_sign']:.6f} degrees
Moon Nakshatra: {chart['moon_nakshatra']}, Pada {chart['moon_pada']}
Birth Nakshatra Lord: {chart['moon_nakshatra_lord']}
Atmakaraka: {chart['atmakaraka']} {chart['atmakaraka_degree']:.6f} degrees
Chara Karaka method: {chart['chara_karaka_system']}
Planets: {json.dumps(planet_summary, ensure_ascii=False)}
Current Saturn transit: {chart['saturn_transit']['sign']}
Current Jupiter transit: {chart['jupiter_transit']['sign']}
Transit date UTC: {chart['transit_date_utc']}

SELF-REFLECTION INDICATORS
{json.dumps(scores, ensure_ascii=False)}

RETRIEVED SOURCE CONTEXT
{source_context}

RULES
- Do not call the Nakshatra lord the current Mahadasha.
- Proper Vimshottari Mahadasha is not implemented in Phase 1A.
- Do not invent Sanskrit quotations, book titles, page numbers, or citations.
- Use the retrieved context only as supporting material.
- Keep each section concise and practical.
"""


def parse_json_safe(raw: str):
    try:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end <= start:
            return None
        parsed = json.loads(raw[start:end])
        return parsed if isinstance(parsed, dict) else None
    except (json.JSONDecodeError, TypeError):
        return None

# ============================================================
# 5. USER INTERFACE
# ============================================================
def render_sidebar():
    with st.sidebar:
        st.markdown("### Configuration")
        configured_key = ""
        try:
            configured_key = st.secrets.get("ZAI_API_KEY", "")
        except Exception:
            configured_key = ""

        if configured_key:
            st.success("Z.ai API key loaded from Streamlit Secrets.")
            api_key = configured_key
        else:
            api_key = st.text_input("Z.ai API Key", type="password", help="The key is not displayed.")

        with st.expander("Advanced settings", expanded=False):
            balance = st.slider(
                "Explanation balance",
                0,
                100,
                50,
                help="0 = practical/modern language; 100 = traditional/Vedic language",
            )
            st.caption(
                "Practical" if balance < 30 else
                "Traditional" if balance > 70 else
                "Balanced"
            )

        st.divider()
        st.markdown("### Profile")
        name = st.text_input("Name", value="Puneet")

        st.markdown("### Birth details")
        dob = st.date_input(
            "Date of birth",
            value=date(1983, 12, 27),
            min_value=date(1900, 1, 1),
            max_value=date.today(),
        )
        tob = st.time_input("Time of birth", value=datetime.strptime("00:35", "%H:%M").time())
        lat = st.number_input(
            "Latitude",
            min_value=-90.0,
            max_value=90.0,
            value=31.6400,
            format="%.4f",
        )
        lon = st.number_input(
            "Longitude",
            min_value=-180.0,
            max_value=180.0,
            value=76.1300,
            format="%.4f",
        )
        utc_offset = st.number_input(
            "Birthplace UTC offset",
            min_value=-12.0,
            max_value=14.0,
            value=5.5,
            step=0.25,
            help="For the birth date and place. India is UTC+5.5.",
        )

        return {
            "api_key": api_key,
            "balance": balance,
            "name": name.strip() or "Seeker",
            "dob": dob,
            "tob": tob,
            "lat": float(lat),
            "lon": float(lon),
            "utc_offset": float(utc_offset),
        }


def render_assessment():
    st.markdown("## Personal Self-Reflection Profile")
    st.caption(
        "A non-clinical reflective exercise. Scale: 0 = Never, 1 = Rarely, "
        "2 = Sometimes, 3 = Often, 4 = Always."
    )

    groups = {
        "Reflective Thinking": [
            "I question the nature of reality and the self behind my thoughts.",
            "I am comfortable holding uncertainty and paradox.",
            "I reflect on purpose beyond material goals.",
        ],
        "Meaning & Direction": [
            "I find meaning even in difficult experiences.",
            "My life feels oriented towards a larger purpose.",
            "I learn from my past rather than repeat it.",
        ],
        "Spiritual Perception": [
            "I sense a connection with other living beings.",
            "I experience a sense of the sacred in nature or everyday life.",
            "I can observe my thoughts without being swept away by them.",
        ],
        "Inner Calm": [
            "I can quiet my mind when I choose to.",
            "I experience moments of mental stillness.",
            "I remain steady during stressful situations.",
        ],
    }

    answers = {}
    columns = st.columns(2)
    for group_index, (group_name, questions) in enumerate(groups.items()):
        with columns[group_index % 2]:
            with st.container(border=True):
                st.markdown(f"#### {group_name}")
                values = []
                for question_index, question in enumerate(questions):
                    key = f"assessment_{group_index}_{question_index}"
                    values.append(st.slider(question, 0, 4, 2, key=key))
                answers[group_name] = values

    scores = {
        group_name: round(sum(values) / (len(values) * 4) * 100)
        for group_name, values in answers.items()
    }
    return scores


def render_planet_table(chart):
    rows = []
    for name in ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]:
        item = chart["planets"][name]
        rows.append(
            {
                "Body": name,
                "Sidereal Sign": item["sign"],
                "Degree": format_degree(item["degree_in_sign"]),
                "Nakshatra": item["nakshatra"],
                "Pada": item["pada"],
                "Motion": "Retrograde" if item.get("retrograde") else "Direct",
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_profile_chart(scores):
    labels = list(scores.keys())
    values = list(scores.values())
    if labels:
        labels_closed = labels + [labels[0]]
        values_closed = values + [values[0]]
    else:
        labels_closed = []
        values_closed = []

    figure = go.Figure(
        data=go.Scatterpolar(
            r=values_closed,
            theta=labels_closed,
            fill="toself",
            line=dict(color="#7C5CBF"),
            marker=dict(color="#C9A84C"),
        )
    )
    figure.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100], gridcolor="#2A2D4A"),
            angularaxis=dict(gridcolor="#2A2D4A"),
        ),
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#C9C4BB"),
        height=330,
        margin=dict(t=30, b=30, l=30, r=30),
    )
    st.plotly_chart(figure, use_container_width=True)


def render_calculated_profile(chart):
    st.markdown("## Calculated Vedic Profile")
    st.caption(
        f"{chart['calculation_system']} · {chart['house_system']} houses · "
        f"Ayanamsa at birth {chart['ayanamsa_value']:.4f}°"
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(
        "Ascendant",
        chart["ascendant"]["sign"],
        format_degree(chart["ascendant"]["degree_in_sign"]),
    )
    col2.metric(
        "Moon",
        f"{chart['moon_nakshatra']} · Pada {chart['moon_pada']}",
        chart["planets"]["Moon"]["sign"],
    )
    col3.metric(
        "Nakshatra Lord",
        chart["moon_nakshatra_lord"],
        "Not current Mahadasha",
    )
    col4.metric(
        "Atmakaraka",
        chart["atmakaraka"],
        format_degree(chart["atmakaraka_degree"]),
    )

    with st.expander("Full sidereal planetary table", expanded=True):
        render_planet_table(chart)
        st.caption(chart["chara_karaka_system"])


def render_synthesis(result, raw):
    if not result:
        st.warning("Z.ai returned an unstructured response. The raw response is shown below.")
        with st.container(border=True):
            st.markdown(raw)
        return

    section_map = [
        ("Executive Summary", "executive_summary"),
        ("Vedic Perspective", "vedic_interpretation"),
        ("Self-Reflection Perspective", "psychological_interpretation"),
        ("Ayurvedic Symbolic Perspective", "ayurvedic_interpretation"),
        ("Where the Systems Converge", "convergence"),
    ]

    for title, key in section_map:
        with st.container(border=True):
            st.markdown(f"#### {title}")
            st.markdown(str(result.get(key, "No content returned.")))

    actions = result.get("practical_actions", [])
    if isinstance(actions, list) and actions:
        with st.container(border=True):
            st.markdown("#### Practical Actions")
            for index, action in enumerate(actions, 1):
                if not isinstance(action, dict):
                    continue
                st.markdown(f"**{index}. {action.get('action', 'Action')}**")
                st.markdown(f"**Why:** {action.get('why', 'Needs Verification')}")
                st.markdown(f"**How:** {action.get('how', 'Needs Verification')}")
                st.markdown(f"**Frequency:** {action.get('frequency', 'Needs Verification')}")

    practice = result.get("vedic_practice", {})
    if isinstance(practice, dict) and practice:
        with st.container(border=True):
            st.markdown("#### Recommended Vedic Practice")
            st.markdown(f"**Mantra:** {practice.get('mantra', 'Needs Verification')}")
            st.markdown(f"**Nama:** {practice.get('nama', 'Needs Verification')}")
            st.markdown(f"**Practice:** {practice.get('practice', 'Needs Verification')}")
            st.markdown(str(practice.get("explanation", "")))

    if result.get("cautions"):
        st.info(f"Framing note: {result['cautions']}")


def render_sources(docs):
    with st.expander("Sources retrieved from the knowledge base", expanded=False):
        for index, document in enumerate(docs, 1):
            metadata = document.metadata or {}
            source_name = metadata.get("source") or metadata.get("book") or f"Source {index}"
            page = metadata.get("page", "Needs Verification")
            st.markdown(f"**S{index} · {source_name} · Page {page}**")
            st.markdown(document.page_content[:800])
            st.divider()


def answer_chat_question(question, api_key, chart, synthesis_text):
    llm = build_llm(api_key)
    safe_chart = {
        "system": chart["calculation_system"],
        "ascendant": chart["ascendant"]["sign"],
        "moon_nakshatra": chart["moon_nakshatra"],
        "moon_pada": chart["moon_pada"],
        "nakshatra_lord": chart["moon_nakshatra_lord"],
        "atmakaraka": chart["atmakaraka"],
    }
    prompt = f"""
Answer the user's question using the supplied chart facts and previous synthesis.
Do not recalculate the chart. Do not call the Nakshatra lord the current Mahadasha.
Do not diagnose illness or claim certainty. If evidence is missing, say Needs Verification.

Chart facts: {json.dumps(safe_chart)}
Previous synthesis: {synthesis_text}
Question: {question}
"""
    return llm.invoke(prompt).content


def render_chat(api_key, chart, synthesis_text):
    st.markdown("## Explore Your Reading")
    st.caption("Ask about the calculated chart, interpretation, or suggested practices.")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    question = st.chat_input("Ask a follow-up question")
    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("Reflecting..."):
                response_text = answer_chat_question(
                    question,
                    api_key,
                    chart,
                    synthesis_text,
                )
                st.markdown(response_text)
        st.session_state.messages.append({"role": "assistant", "content": response_text})

# ============================================================
# 6. MAIN APPLICATION
# ============================================================
def main():
    st.markdown(
        "<h1 style='text-align:center;'>Ancient Wisdom Synthesis</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align:center;color:#9C9A93;'>"
        "Lahiri sidereal astrology · self-reflection · ancient texts · practical synthesis"
        "</p>",
        unsafe_allow_html=True,
    )
    st.divider()

    config = render_sidebar()
    scores = render_assessment()

    st.divider()
    generate = st.button("Generate My Synthesis", type="primary", use_container_width=True)

    if generate:
        if not config["api_key"]:
            st.error("Add the Z.ai API key in Streamlit Secrets or the sidebar.")
        else:
            progress = st.progress(5, text="Validating birth data")
            try:
                chart = calculate_vedic_profile(
                    config["dob"],
                    config["tob"],
                    config["lat"],
                    config["lon"],
                    config["utc_offset"],
                )

                progress.progress(30, text="Calculating Lahiri sidereal chart")
                retriever = load_knowledge_base()

                progress.progress(55, text="Retrieving passages from the knowledge base")
                query = (
                    f"{chart['atmakaraka']} {chart['moon_nakshatra']} "
                    f"{chart['theme']} {chart['chakra']} contemplation practice"
                )
                documents = retriever.invoke(query)

                source_blocks = []
                for index, document in enumerate(documents, 1):
                    metadata = document.metadata or {}
                    source_name = metadata.get("source") or metadata.get("book") or "Unknown source"
                    page = metadata.get("page", "Needs Verification")
                    source_blocks.append(
                        f"[S{index}]\nSource: {source_name}\nPage: {page}\nText: {document.page_content}"
                    )
                source_context = "\n\n".join(source_blocks)

                progress.progress(75, text="Preparing the Z.ai synthesis")
                llm = build_llm(config["api_key"])
                prompt = build_prompt(
                    config["name"],
                    chart,
                    scores,
                    config["balance"],
                    source_context,
                )
                raw_response = llm.invoke(prompt).content
                result = parse_json_safe(raw_response)

                progress.progress(100, text="Synthesis complete")

                st.session_state["chart"] = chart
                st.session_state["scores"] = scores
                st.session_state["documents"] = documents
                st.session_state["raw_response"] = raw_response
                st.session_state["result"] = result
                st.session_state["api_key"] = config["api_key"]
                st.session_state["synthesis_text"] = (
                    result.get("executive_summary", raw_response)
                    if result else raw_response
                )
                st.session_state["messages"] = []

            except Exception as error:
                progress.empty()
                st.error(f"The synthesis could not be completed: {error}")

    if "chart" in st.session_state:
        st.divider()
        render_calculated_profile(st.session_state["chart"])

        left, right = st.columns([2, 1])
        with left:
            st.markdown("## Synthesis")
            render_synthesis(
                st.session_state.get("result"),
                st.session_state.get("raw_response", ""),
            )
        with right:
            st.markdown("## Self-Reflection")
            render_profile_chart(st.session_state.get("scores", {}))
            st.caption("Self-reported indicators, not clinical measures.")

        render_sources(st.session_state.get("documents", []))

        st.divider()
        render_chat(
            st.session_state.get("api_key", config["api_key"]),
            st.session_state["chart"],
            st.session_state.get("synthesis_text", ""),
        )
    else:
        st.divider()
        st.markdown("## Explore Your Reading")
        st.caption("Generate the synthesis first to unlock follow-up questions.")


if __name__ == "__main__":
    main()
