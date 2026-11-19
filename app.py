import streamlit as st
import swisseph as swe
from datetime import datetime, date
from langchain_openai import ChatOpenAI
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
import os
import requests
import plotly.graph_objects as go

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Ancient Wisdom Guide", page_icon="🕉️", layout="wide")

# Custom CSS for a cleaner card look
st.markdown("""
<style>
    .stMetric { background-color: #1E1E2E; padding: 15px; border-radius: 10px; border: 1px solid #333; }
    .stProgress > div > div > div > div { background-color: #FFD700; }
</style>
""", unsafe_allow_html=True)

st.title("🕉️ Ancient Wisdom & Modern Science Guide")
st.markdown("*Deep analysis of your Vedic Chart, Mind, and Body.*")

# --- CONSTANTS ---
SIGNS = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashirsha", "Ardra", "Punarvasu", "Pushya", "Ashlesha",
    "Magha", "Purva Phalguni", "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purvashadha", "Uttarashadha", "Shravana", "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"
]
DASHA_LORDS = ["Ketu", "Venus", "Sun", "Moon", "Mars", "Rahu", "Jupiter", "Saturn", "Mercury"]

# --- ASTROLOGY ENGINE ---
def get_nakshatra(longitude):
    index = int(longitude / (13 + 20/60))
    return NAKSHATRAS[index % 27]

def calculate_vedic_profile(year, month, day, tob, lat, lon, tz):
    dt = datetime(year, month, day, tob.hour, tob.minute)
    ut_hour = dt.hour + dt.minute/60 - tz
    jd = swe.julday(dt.year, dt.month, dt.day, ut_hour)
    
    # Ascendant
    cusps, ascmc = swe.houses(jd, lat, lon, b'W')
    asc_deg = ascmc[0]
    asc_sign = SIGNS[int(asc_deg / 30)]
    
    # Moon Nakshatra
    moon_pos, _ = swe.calc_ut(jd, swe.MOON)
    moon_long = moon_pos[0]
    moon_nakshatra = get_nakshatra(moon_long)
    
    # Atmakaraka
    planets = {"Moon": swe.MOON, "Mars": swe.MARS, "Mercury": swe.MERCURY, "Jupiter": swe.JUPITER, "Venus": swe.VENUS, "Saturn": swe.SATURN}
    degrees = {}
    for name, pid in planets.items():
        pos, _ = swe.calc_ut(jd, pid)
        degrees[name] = pos[0] % 30
        
    atmakaraka = max(degrees, key=degrees.get)
    
    # Current Dasha (Simplified)
    nakshatra_index = int(moon_long / (13 + 20/60))
    start_dasha_index = nakshatra_index % 9
    current_dasha = DASHA_LORDS[start_dasha_index]
    
    # Transits
    today = datetime.now()
    jd_today = swe.julday(today.year, today.month, today.day, today.hour)
    saturn_today, _ = swe.calc_ut(jd_today, swe.SATURN)
    jupiter_today, _ = swe.calc_ut(jd_today, swe.JUPITER)
    saturn_sign = SIGNS[int(saturn_today[0] / 30)]
    jupiter_sign = SIGNS[int(jupiter_today[0] / 30)]

    mapping = {
        "Jupiter": {"chakra": "Ajna (Third Eye)", "dosha": "Kapha", "theme": "Wisdom & Expansion", "nama": "N523 Shadanana"},
        "Mars": {"chakra": "Manipura (Solar Plexus)", "dosha": "Pitta", "theme": "Courage & Action", "nama": "N503 Lakinyamba"},
        "Venus": {"chakra": "Svadhisthana (Sacral)", "dosha": "Kapha", "theme": "Love & Creativity", "nama": "N513 Kakini"},
        "Saturn": {"chakra": "Muladhara (Root)", "dosha": "Vata", "theme": "Discipline & Grounding", "nama": "N520 Sakinyamba"},
        "Moon": {"chakra": "Anahata (Heart)", "dosha": "Kapha", "theme": "Emotion & Nurturing", "nama": "N494 Rakinyamba"},
        "Mercury": {"chakra": "Vishuddha (Throat)", "dosha": "Vata", "theme": "Communication & Logic", "nama": "N484 Dakinishvari"}
    }
    
    return {
        "asc_sign": asc_sign,
        "moon_nakshatra": moon_nakshatra,
        "atmakaraka": atmakaraka,
        "current_dasha": current_dasha,
        "saturn_transit": saturn_sign,
        "jupiter_transit": jupiter_sign,
        "chakra": mapping[atmakaraka]["chakra"],
        "dosha": mapping[atmakaraka]["dosha"],
        "theme": mapping[atmakaraka]["theme"],
        "nama": mapping[atmakaraka]["nama"]
    }

# --- SIDEBAR ---
with st.sidebar:
    st.header("1. Setup")
    api_key = st.text_input("Z.ai API Key", type="password")
    user_name = st.text_input("Your Name", value="Seeker")
    
    st.header("2. Birth Details")
    col_y, col_m, col_d = st.columns(3)
    with col_y: birth_year = st.selectbox("Year", options=list(range(2030, 1900, -1)), index=47)
    with col_m: birth_month = st.selectbox("Month", options=list(range(1, 13)), format_func=lambda x: datetime(2000, x, 1).strftime('%b'), index=11)
    with col_d: birth_day = st.selectbox("Day", options=list(range(1, 32)), index=26)
    tob = st.time_input("Time", datetime.strptime("00:35", "%H:%M").time())
    lat = st.number_input("Latitude", value=31.64, format="%.4f")
    lon = st.number_input("Longitude", value=76.13, format="%.4f")
    tz = st.number_input("Timezone", value=5.5)

    st.header("3. The 12 Scientific Questions (0-4)")
    q1 = st.slider("I think deeply about life and death.", 0, 4, 2)
    q2 = st.slider("I question my core beliefs.", 0, 4, 2)
    q3 = st.slider("I handle uncertainty well.", 0, 4, 2)
    q4 = st.slider("I find meaning in hard times.", 0, 4, 2)
    q5 = st.slider("My life has a clear direction.", 0, 4, 2)
    q6 = st.slider("I learn from my past mistakes.", 0, 4, 2)
    q7 = st.slider("I feel a deep spiritual connection.", 0, 4, 2)
    q8 = st.slider("I feel deeply connected to nature.", 0, 4, 2)
    q9 = st.slider("I can watch my thoughts without getting swept away.", 0, 4, 2)
    q10 = st.slider("I can find inner peace on demand.", 0, 4, 2)
    q11 = st.slider("I experience moments of deep mental silence.", 0, 4, 2)
    q12 = st.slider("I stay calm in stressful situations.", 0, 4, 2)

# --- KNOWLEDGE BASE ---
@st.cache_resource(show_spinner=False)
def load_knowledge_base():
    sqlite_url = "https://raw.githubusercontent.com/puneethongkong/spiritual-guide-app/main/chroma.sqlite3"
    os.makedirs("chroma_db", exist_ok=True)
    filepath = "chroma_db/chroma.sqlite3"
    if not os.path.exists(filepath):
        with st.spinner("Downloading 10-book database..."):
            r = requests.get(sqlite_url)
            with open(filepath, 'wb') as f: f.write(r.content)
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vectorstore = Chroma(persist_directory="chroma_db", embedding_function=embeddings)
    return vectorstore.as_retriever(search_kwargs={"k": 3})

# --- MAIN APP ---
if st.button("Run Deterministic Vedic Analysis", type="primary"):
    if not api_key:
        st.error("Please enter your Z.ai API Key.")
    else:
        with st.spinner(f"Calculating {user_name}'s deterministic Vedic chart..."):
            
            chart = calculate_vedic_profile(birth_year, birth_month, birth_day, tob, lat, lon, tz)
            
            # SISRI
            cet = int(((q1 + q2 + q3) / 12) * 100)
            pmp = int(((q4 + q5 + q6) / 12) * 100)
            ta = int(((q7 + q8 + q9) / 12) * 100)
            cse = int(((q10 + q11 + q12) / 12) * 100)
            
            # Spiritual Score
            base_avg = (cet + pmp + ta + cse) / 4
            vedic_bonus = 10 if chart['atmakaraka'] in ["Jupiter", "Moon"] else 5
            spiritual_score = round(((base_avg + vedic_bonus) / 110) * 10, 1)
            if spiritual_score > 10.0: spiritual_score = 10.0
            
            retriever = load_knowledge_base()
            docs = retriever.invoke(f"{chart['atmakaraka']} {chart['moon_nakshatra']} remedies {chart['dosha']}")
            context = "\n\n".join([d.page_content for d in docs])
            
            llm = ChatOpenAI(model="glm-4.5-flash", openai_api_key=api_key, openai_api_base="https://api.z.ai/api/paas/v4", temperature=0.7, max_tokens=1200, extra_body={"thinking": {"type": "disabled"}})
            
            prompt = f"""
            You are an expert Vedic Astrologer. You are interpreting a chart calculated with 100% mathematical precision.
            User: {user_name}. Spiritual Score: {spiritual_score}/10.
            Chart: Ascendant {chart['asc_sign']}, Moon Nakshatra {chart['moon_nakshatra']}, Atmakaraka {chart['atmakaraka']}, Dasha {chart['current_dasha']}, Saturn in {chart['saturn_transit']}, Jupiter in {chart['jupiter_transit']}.
            SISRI: Thinking {cet}%, Meaning {pmp}%, Spiritual {ta}%, Calm {cse}%.
            Context: {context}
            
            Output strictly in this format:
            DIAGNOSIS: Address {user_name}. Synthesize Nakshatra, Atmakaraka, and Dasha. Explain core soul friction.
            CHAKRA_FIX: Focus on {chart['chakra']}. Explain the block and how to open it.
            AYURVEDA_FIX: 2 actions for {chart['dosha']} imbalance.
            PSYCHOLOGY_FIX: 1 reframe based on lowest SISRI score.
            VEDIC_REMEDY: Prescribe {chart['nama']} and explain how it pierces {chart['chakra']}.
            """
            
            response = llm.invoke(prompt)
            content = response.content
            
            # --- VISUAL DASHBOARD ---
            st.success(f"✅ Analysis Complete for {user_name}")
            
            # Astrological Fact Sheet in a nice box
            with st.expander("🔭 Your Calculated Vedic Chart", expanded=True):
                c1, c2, c3 = st.columns(3)
                c1.metric("Ascendant", chart['asc_sign'])
                c2.metric("Moon Nakshatra", chart['moon_nakshatra'])
                c3.metric("Current Dasha", chart['current_dasha'])
                st.caption(f"Transits Today: Saturn in {chart['saturn_transit']}, Jupiter in {chart['jupiter_transit']}")
            
            # Big Metrics
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Core Theme", chart['theme'])
            col2.metric("Active Chakra", chart['chakra'])
            col3.metric("Dosha", chart['dosha'])
            col4.metric("Spiritual Score", f"{spiritual_score}/10")
            
            # Radar Chart for Psychology
            st.markdown(f"### {user_name}'s Psychological Profile")
            fig = go.Figure(data=go.Scatterpolar(
                r=[cet, pmp, ta, cse],
                theta=['Critical Thinking', 'Meaning', 'Transcendental', 'Inner Calm'],
                fill='toself',
                marker=dict(color='#FFD700')
            ))
            fig.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                showlegend=False,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='white')
            )
            st.plotly_chart(fig, use_container_width=True)
            
            st.divider()
            
            try:
                diag = content.split("DIAGNOSIS:")[1].split("CHAKRA_FIX:")[0].strip()
                chakra = content.split("CHAKRA_FIX:")[1].split("AYURVEDA_FIX:")[0].strip()
                body = content.split("AYURVEDA_FIX:")[1].split("PSYCHOLOGY_FIX:")[0].strip()
                mind = content.split("PSYCHOLOGY_FIX:")[1].split("VEDIC_REMEDY:")[0].strip()
                remedy = content.split("VEDIC_REMEDY:")[1].strip()
                
                with st.expander(f"🔍 The Vedic Diagnosis for {user_name}", expanded=True):
                    st.write(diag)
                with st.expander(f"🌀 The Chakra Blockage: {chart['chakra']}", expanded=True):
                    st.write(chakra)
                col_a, col_b = st.columns(2)
                with col_a: st.info(f"**🧘 Ayurvedic Fix ({chart['dosha']})**\n\n{body}")
                with col_b: st.warning(f"**🧠 Psychological Fix**\n\n{mind}")
                st.success(f"**🕉️ Lalita Sahasranama Remedy**\n\n{remedy}")
            except Exception:
                st.info(content)

# --- CHAT ---
st.divider()
st.header("💬 Discuss Your Chart")
if "messages" not in st.session_state: st.session_state.messages = []
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.markdown(msg["content"])

if user_query := st.chat_input("Ask about your Nakshatra, Dasha, or remedies..."):
    if not api_key: st.error("API Key missing.")
    else:
        st.session_state.messages.append({"role": "user", "content": user_query})
        with st.chat_message("user"): st.markdown(user_query)
        with st.chat_message("assistant"):
            with st.spinner("Reflecting..."):
                llm = ChatOpenAI(model="glm-4.5-flash", openai_api_key=api_key, openai_api_base="https://api.z.ai/api/paas/v4", temperature=0.7, extra_body={"thinking": {"type": "disabled"}})
                chat_prompt = f"You are a Vedic Astrologer. Chart: {chart}. Answer: {user_query}"
                response = llm.invoke(chat_prompt)
                st.markdown(response.content)
                st.session_state.messages.append({"role": "assistant", "content": response.content})
