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

# Custom CSS for a premium "Temple" look
st.markdown("""
<style>
    .stMetric { background-color: #1E1E2E; padding: 20px; border-radius: 12px; border: 1px solid #D4AF37; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
    .stProgress > div > div > div > div { background-color: #D4AF37; }
    h1 { color: #D4AF37; font-family: 'Georgia', serif; text-align: center; padding-bottom: 20px; }
    h2, h3 { color: #EAEAEA; font-family: 'Georgia', serif; }
    p { font-size: 16px; line-height: 1.6; color: #CCCCCC; }
    .stSlider label { font-size: 15px; color: #EAEAEA; }
</style>
""", unsafe_allow_html=True)

st.title("🕉️ The Ancient Wisdom Synthesis")
st.markdown("<p style='text-align: center;'><i>Where Vedic Astrology, Ayurveda, and Modern Psychology converge.</i></p>", unsafe_allow_html=True)

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
    
    # Current Dasha
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
        "asc_sign": asc_sign, "moon_nakshatra": moon_nakshatra, "atmakaraka": atmakaraka,
        "current_dasha": current_dasha, "saturn_transit": saturn_sign, "jupiter_transit": jupiter_sign,
        "chakra": mapping[atmakaraka]["chakra"], "dosha": mapping[atmakaraka]["dosha"],
        "theme": mapping[atmakaraka]["theme"], "nama": mapping[atmakaraka]["nama"]
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

    st.divider()
    st.header("3. The 15 Spiritual Questions")
    st.info("**How to use:** Answer based on your current reality, not your ideal self. There are no 'right' answers here. The Sage will combine these answers with your Vedic chart to find the root cause.")
    
    # Group 1: Existential Thinking (CET)
    q1 = st.slider("I question the nature of reality and the 'I' behind my thoughts.", 0, 4, 2)
    q2 = st.slider("I am comfortable with paradox and uncertainty in spiritual matters.", 0, 4, 2)
    q3 = st.slider("I seek to understand my soul's purpose, not just worldly success.", 0, 4, 2)
    
    # Group 2: Meaning Production (PMP)
    q4 = st.slider("I see life's challenges as a necessary curriculum for my soul.", 0, 4, 2)
    q5 = st.slider("I can find a sense of sacred meaning even in painful experiences.", 0, 4, 2)
    q6 = st.slider("My daily actions are guided by a higher purpose.", 0, 4, 2)
    
    # Group 3: Transcendental Awareness (TA)
    q7 = st.slider("I sense a unified consciousness (Brahman/Shakti) flowing through all beings.", 0, 4, 2)
    q8 = st.slider("I can perceive the Divine presence in nature and ordinary life.", 0, 4, 2)
    q9 = st.slider("I am aware of a silent witness (Sakshi) behind my thoughts.", 0, 4, 2)
    
    # Group 4: Conscious State Expansion (CSE)
    q10 = st.slider("I can quiet my mind (Vritti Nirodha) and rest in inner silence.", 0, 4, 2)
    q11 = st.slider("I experience moments of profound meditative absorption.", 0, 4, 2)
    q12 = st.slider("I can remain centered and calm during intense stress.", 0, 4, 2)
    
    # Group 5: Spiritual Compassion (New)
    q13 = st.slider("I feel deep, unconditional compassion for those who cause harm.", 0, 4, 2)
    q14 = st.slider("I recognize myself in the struggles of others.", 0, 4, 2)
    q15 = st.slider("I actively practice non-harm (Ahimsa) in thought, word, and deed.", 0, 4, 2)

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
if st.button("Consult the Vedic Sage", type="primary"):
    if not api_key:
        st.error("Please enter your Z.ai API Key.")
    else:
        with st.spinner(f"The Sage is synthesizing {user_name}'s chart with 10 ancient books..."):
            
            chart = calculate_vedic_profile(birth_year, birth_month, birth_day, tob, lat, lon, tz)
            
            # Calculate 5 dimensions
            cet = int(((q1 + q2 + q3) / 12) * 100)
            pmp = int(((q4 + q5 + q6) / 12) * 100)
            ta = int(((q7 + q8 + q9) / 12) * 100)
            cse = int(((q10 + q11 + q12) / 12) * 100)
            comp = int(((q13 + q14 + q15) / 12) * 100)
            
            # Spiritual Score
            base_avg = (cet + pmp + ta + cse + comp) / 5
            vedic_bonus = 10 if chart['atmakaraka'] in ["Jupiter", "Moon"] else 5
            spiritual_score = round(((base_avg + vedic_bonus) / 110) * 10, 1)
            if spiritual_score > 10.0: spiritual_score = 10.0
            
            retriever = load_knowledge_base()
            docs = retriever.invoke(f"{chart['atmakaraka']} {chart['moon_nakshatra']} remedies {chart['dosha']}")
            context = "\n\n".join([d.page_content for d in docs])
            
            llm = ChatOpenAI(model="glm-4.5-flash", openai_api_key=api_key, openai_api_base="https://api.z.ai/api/paas/v4", temperature=0.7, max_tokens=1500, extra_body={"thinking": {"type": "disabled"}})
            
            # THE WEIGHTED PROMPT
            prompt = f"""
            You are a wise, compassionate Vedic Sage. Write with elegance, depth, and authority.
            User: {user_name}. Spiritual Score: {spiritual_score}/10.
            
            ASTROLOGICAL ROOT CAUSE (This is the absolute truth, prioritize this):
            - Ascendant: {chart['asc_sign']}
            - Moon Nakshatra: {chart['moon_nakshatra']}
            - Atmakaraka: {chart['atmakaraka']}
            - Current Dasha: {chart['current_dasha']}
            - Transits: Saturn in {chart['saturn_transit']}, Jupiter in {chart['jupiter_transit']}
            
            MODERN PSYCHOLOGICAL SYMPTOMS (How the user feels):
            - Critical Thinking: {cet}% | Meaning: {pmp}% | Transcendental: {ta}% | Inner Calm: {cse}% | Compassion: {comp}%
            
            Context from ancient texts: {context}
            
            Output strictly in this format (use Markdown):
            
            **The Vedic Diagnosis**
            [Address {user_name}. Synthesize Nakshatra, Atmakaraka, and Dasha. Explain their current soul friction. Note: If their psychological scores are high but their chart shows a difficult Dasha (like Saturn), gently explain that they may be spiritually bypassing their current karmic lessons.]
            
            **The Chakra Blockage**
            [Focus on {chart['chakra']}. Explain the subtle energy block and how it manifests based on their lowest psychological score.]
            
            **Ayurvedic Restoration**
            [2 specific Ayurvedic actions for {chart['dosha']} imbalance. Explain the ancient logic.]
            
            **Psychological Shift**
            [1 reframe based on their lowest SISRI score, using modern psychology.]
            
            **The Lalita Sahasranama Remedy**
            [Prescribe {chart['nama']}. Explain its meaning and how it pierces {chart['chakra']}.]
            """
            
            response = llm.invoke(prompt)
            content = response.content
            
            # --- DASHBOARD ---
            st.success(f"✨ The Sage has spoken for {user_name}")
            
            st.markdown("### 🔭 Your Celestial Blueprint")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Ascendant", chart['asc_sign'])
            c2.metric("Nakshatra", chart['moon_nakshatra'])
            c3.metric("Dasha", chart['current_dasha'])
            c4.metric("Score", f"{spiritual_score}/10")
            
            st.caption(f"Transits: Saturn in {chart['saturn_transit']} | Jupiter in {chart['jupiter_transit']}")
            st.divider()

            # CHARTS
            col_chart1, col_chart2 = st.columns(2)
            with col_chart1:
                st.markdown("#### Psychological Balance (SISRI)")
                fig_radar = go.Figure(data=go.Scatterpolar(
                    r=[cet, pmp, ta, cse, comp],
                    theta=['Thinking', 'Meaning', 'Transcendental', 'Inner Calm', 'Compassion'],
                    fill='toself', marker=dict(color='#D4AF37')
                ))
                fig_radar.update_layout(
                    polar=dict(radialaxis=dict(visible=True, range=[0, 100], color="white")),
                    showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='white'), margin=dict(t=30, b=30, l=30, r=30), height=300
                )
                st.plotly_chart(fig_radar, use_container_width=True)
                
            with col_chart2:
                st.markdown("#### Spiritual Alignment")
                fig_donut = go.Figure(data=[go.Pie(
                    values=[spiritual_score, 10 - spiritual_score],
                    labels=["Aligned", "Unrealized"], hole=.7, marker_colors=['#D4AF37', '#1E1E2E'], textinfo='none'
                )])
                fig_donut.update_layout(
                    showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='white'), margin=dict(t=30, b=30, l=30, r=30), height=300
                )
                st.plotly_chart(fig_donut, use_container_width=True)

            st.divider()

            # TEXT
            try:
                diag = content.split("**The Vedic Diagnosis**")[1].split("**The Chakra Blockage**")[0].strip()
                chakra = content.split("**The Chakra Blockage**")[1].split("**Ayurvedic Restoration**")[0].strip()
                body = content.split("**Ayurvedic Restoration**")[1].split("**Psychological Shift**")[0].strip()
                mind = content.split("**Psychological Shift**")[1].split("**The Lalita Sahasranama Remedy**")[0].strip()
                remedy = content.split("**The Lalita Sahasranama Remedy**")[1].strip()
                
                st.markdown(f"### 📜 The Synthesis for {user_name}")
                st.markdown(f"#### The Vedic Diagnosis\n{diag}")
                st.markdown(f"#### The Chakra Blockage: {chart['chakra']}\n{chakra}")
                
                col_a, col_b = st.columns(2)
                with col_a: st.info(f"**🌿 Ayurvedic Restoration ({chart['dosha']})**\n\n{body}")
                with col_b: st.warning(f"**🧠 Psychological Shift**\n\n{mind}")
                st.success(f"**🕉️ The Lalita Sahasranama Remedy**\n\n{remedy}")
            except Exception:
                st.info(content)

# --- CHAT ---
st.divider()
st.header("💬 Seek Further Guidance")
st.markdown("*Ask the Sage about your chart, your remedies, or your spiritual path.*")
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
                chat_prompt = f"You are a compassionate Vedic Sage. User Chart: {chart}. Answer elegantly: {user_query}"
                response = llm.invoke(chat_prompt)
                st.markdown(response.content)
                st.session_state.messages.append({"role": "assistant", "content": response.content})
