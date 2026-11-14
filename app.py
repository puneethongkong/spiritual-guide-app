import streamlit as st
import swisseph as swe
from datetime import datetime, date
from langchain_openai import ChatOpenAI
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
import os
import requests

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Ancient Wisdom Guide", page_icon="🕉️", layout="wide")
st.title("🕉️ Ancient Wisdom & Modern Science Guide")
st.markdown("*Deep analysis of your Vedic Chart, Mind, and Body.*")

# --- SIDEBAR: SETUP & SLIDER ---
with st.sidebar:
    st.header("1. Setup")
    api_key = st.text_input("Z.ai API Key", type="password")
    user_name = st.text_input("Your Name", value="Seeker")
    
    st.divider()
    slider_val = st.slider("How should we explain your results?", 0, 100, 50)
    if slider_val < 30:
        st.caption("**Current Bias:** Modern Science (Psychological).")
    elif slider_val > 70:
        st.caption("**Current Bias:** Ancient Philosophy (Vedic).")
    else:
        st.caption("**Current Bias:** Balanced Synthesis.")
    
    st.divider()
    st.header("2. Birth Details")
    st.markdown("**Date of Birth**")
    col_y, col_m, col_d = st.columns(3)
    with col_y:
        birth_year = st.selectbox("Year", options=list(range(2030, 1900, -1)), index=47)
    with col_m:
        birth_month = st.selectbox("Month", options=list(range(1, 13)), format_func=lambda x: datetime(2000, x, 1).strftime('%b'), index=11)
    with col_d:
        birth_day = st.selectbox("Day", options=list(range(1, 32)), index=26)
        
    tob = st.time_input("Time of Birth", datetime.strptime("00:35", "%H:%M").time())
    lat = st.number_input("Latitude", value=31.64, format="%.4f")
    lon = st.number_input("Longitude", value=76.13, format="%.4f")
    tz = st.number_input("Timezone (UTC offset)", value=5.5)

    st.divider()
    st.header("3. The 12 Scientific Questions (0=Never, 4=Always)")
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

# --- CORE ASTROLOGY ---
def calculate_vedic_profile(year, month, day, tob, lat, lon, tz):
    dt = datetime(year, month, day, tob.hour, tob.minute)
    ut_hour = dt.hour + dt.minute/60 - tz
    jd = swe.julday(dt.year, dt.month, dt.day, ut_hour)
    
    planets = {"Sun": swe.SUN, "Moon": swe.MOON, "Mars": swe.MARS, "Mercury": swe.MERCURY, "Jupiter": swe.JUPITER, "Venus": swe.VENUS, "Saturn": swe.SATURN, "Rahu": swe.MEAN_NODE}
    degrees = {}
    for name, pid in planets.items():
        pos, _ = swe.calc_ut(jd, pid)
        deg_in_sign = pos[0] % 30
        if name == "Rahu": deg_in_sign = 30.0 - deg_in_sign
        if name not in ["Sun", "Rahu"]: degrees[name] = deg_in_sign
        
    atmakaraka = max(degrees, key=degrees.get)
    
    mapping = {
        "Jupiter": {"chakra": "Ajna (Third Eye)", "dosha": "Kapha", "theme": "Wisdom & Expansion", "nama_range": "521-527", "sample_nama": "N523 Shadanana"},
        "Mars": {"chakra": "Manipura (Solar Plexus)", "dosha": "Pitta", "theme": "Courage & Action", "nama_range": "495-503", "sample_nama": "N503 Lakinyamba"},
        "Venus": {"chakra": "Svadhisthana (Sacral)", "dosha": "Kapha", "theme": "Love & Creativity", "nama_range": "504-513", "sample_nama": "N513 Kakini"},
        "Saturn": {"chakra": "Muladhara (Root)", "dosha": "Vata", "theme": "Discipline & Grounding", "nama_range": "514-520", "sample_nama": "N520 Sakinyamba"},
        "Moon": {"chakra": "Anahata (Heart)", "dosha": "Kapha", "theme": "Emotion & Nurturing", "nama_range": "485-494", "sample_nama": "N494 Rakinyamba"},
        "Mercury": {"chakra": "Vishuddha (Throat)", "dosha": "Vata", "theme": "Communication & Logic", "nama_range": "475-484", "sample_nama": "N484 Dakinishvari"},
        "Rahu": {"chakra": "Sahasrara (Crown)", "dosha": "Vata", "theme": "Liberation & Obsession", "nama_range": "528-534", "sample_nama": "N534 Yakinyamba"}
    }
    
    return {
        "atmakaraka": atmakaraka, 
        "chakra": mapping[atmakaraka]["chakra"],
        "dosha": mapping[atmakaraka]["dosha"],
        "theme": mapping[atmakaraka]["theme"],
        "nama_range": mapping[atmakaraka]["nama_range"],
        "sample_nama": mapping[atmakaraka]["sample_nama"]
    }

# --- KNOWLEDGE BASE ---
@st.cache_resource(show_spinner=False)
def load_knowledge_base():
    sqlite_url = "https://raw.githubusercontent.com/puneethongkong/spiritual-guide-app/main/chroma.sqlite3"
    os.makedirs("chroma_db", exist_ok=True)
    filepath = "chroma_db/chroma.sqlite3"
    
    if not os.path.exists(filepath):
        with st.spinner("Downloading 10-book database from GitHub..."):
            r = requests.get(sqlite_url)
            with open(filepath, 'wb') as f:
                f.write(r.content)
                
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vectorstore = Chroma(persist_directory="chroma_db", embedding_function=embeddings)
    return vectorstore.as_retriever(search_kwargs={"k": 5})

# --- MAIN APP ---
if st.button("Run Deep Diagnostic Analysis", type="primary"):
    if not api_key:
        st.error("Please enter your Z.ai API Key.")
    else:
        with st.spinner(f"Analyzing {user_name}'s Vedic Chart and Modern Psychology Profile..."):
            
            vedic = calculate_vedic_profile(birth_year, birth_month, birth_day, tob, lat, lon, tz)
            
            cet_score = int(((q1 + q2 + q3) / 12) * 100)
            pmp_score = int(((q4 + q5 + q6) / 12) * 100)
            ta_score = int(((q7 + q8 + q9) / 12) * 100)
            cse_score = int(((q10 + q11 + q12) / 12) * 100)
            
            # --- CALCULATE SPIRITUAL SCORE OUT OF 10 ---
            # Base score is the average of the 4 modern psychology scores
            base_avg = (cet_score + pmp_score + ta_score + cse_score) / 4
            
            # Vedic adjustment
            vedic_bonus = 0
            if vedic['atmakaraka'] in ["Jupiter", "Moon", "Rahu"]:
                vedic_bonus = 10  # Sattvic/Spiritual planets add a boost
            elif vedic['atmakaraka'] in ["Venus", "Mercury"]:
                vedic_bonus = 5   # Rajasic/Neutral planets
            elif vedic['atmakaraka'] in ["Mars", "Saturn"]:
                vedic_bonus = 0   # Tamasic/Intense karmic planets
            
            # Calculate final score out of 10
            final_raw_score = base_avg + vedic_bonus
            spiritual_score = round((final_raw_score / 110) * 10, 1) # Scale 0-110 to 0-10
            if spiritual_score > 10.0: spiritual_score = 10.0
            
            retriever = load_knowledge_base()
            docs = retriever.invoke(f"{vedic['atmakaraka']} remedies {vedic['dosha']} balancing {vedic['chakra']}")
            context = "\n\n".join([d.page_content for d in docs])
            
            llm = ChatOpenAI(model="glm-4.5-flash", openai_api_key=api_key, openai_api_base="https://api.z.ai/api/paas/v4", temperature=0.7, max_tokens=1500, extra_body={"thinking": {"type": "disabled"}})
            
            # UPDATED PROMPT WITH SCORE
            prompt = f"""
            You are an expert Vedic Astrologer, Ayurvedic Doctor, and Spiritual Guide. 
            The user's name is: {user_name}. Address them by name.
            Their calculated Spiritual Score is: {spiritual_score} out of 10.
            
            Patient's Ancient Data:
            - Atmakaraka (Core Theme): {vedic['theme']} ({vedic['atmakaraka']})
            - Active Chakra: {vedic['chakra']}
            - Ayurvedic Imbalance: {vedic['dosha']}
            - Lalita Nama Range: {vedic['nama_range']} (e.g., {vedic['sample_nama']})
            
            Patient's Modern SISRI-24 Scores:
            - Critical Thinking: {cet_score}/100
            - Meaning & Purpose: {pmp_score}/100
            - Transcendental Awareness: {ta_score}/100
            - Inner Calm (CSE): {cse_score}/100
            
            Context from ancient texts: {context}
            
            Write a DETAILED, deeply analytical prescription. 
            
            **1. The Vedic Diagnosis:** Address {user_name}. Explain the specific friction between their soul's desire ({vedic['atmakaraka']}) and their mind's modern psychological state. Mention their Spiritual Score of {spiritual_score}/10 and explain what it means for their current journey.
            **2. The Chakra Blockage (Detailed):** Focus on the {vedic['chakra']}. Explain what it governs, the symptoms of blockage, and why their SISRI scores indicate a block here.
            **3. The Ayurvedic Body Fix (Detailed):** Explain the {vedic['dosha']} imbalance. Prescribe 2 specific Ayurvedic actions (e.g., Pranayama, dietary change). Explain the mechanism of WHY this balances {vedic['dosha']}.
            **4. The Psychological Mind Fix (Detailed):** Prescribe a specific psychological reframe based on their lowest SISRI score.
            **5. The Lalita Sahasranama Spiritual Remedy:** Introduce Nama {vedic['nama_range']} (e.g., {vedic['sample_nama']}). Explain its meaning, prescribe how to chant it, and explain how it pierces the {vedic['chakra']}.
            """
            
            response = llm.invoke(prompt)
            content = response.content
            
            # DISPLAY METRICS
            st.success(f"✅ Synthesis Complete for {user_name}")
            
            # NEW LAYOUT WITH SPIRITUAL SCORE COLUMN
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Vedic Theme", vedic['theme'])
            col2.metric("Active Chakra", vedic['chakra'])
            col3.metric("Ayurvedic Type", vedic['dosha'])
            col4.metric("Spiritual Score", f"{spiritual_score}/10") # The new column!
            
            st.markdown(f"### {user_name}'s Modern Psychological Profile (SISRI-24)")
            st.progress(cet_score, text=f"Critical Thinking: {cet_score}%")
            st.progress(pmp_score, text=f"Meaning & Purpose: {pmp_score}%")
            st.progress(ta_score, text=f"Transcendental Awareness: {ta_score}%")
            st.progress(cse_score, text=f"Inner Calm (CSE): {cse_score}%")
            
            st.divider()
            
            try:
                diag = content.split("**1. The Vedic Diagnosis:**")[1].split("**2. The Chakra Blockage (Detailed):**")[0].strip()
                chakra = content.split("**2. The Chakra Blockage (Detailed):**")[1].split("**3. The Ayurvedic Body Fix (Detailed):**")[0].strip()
                body = content.split("**3. The Ayurvedic Body Fix (Detailed):**")[1].split("**4. The Psychological Mind Fix (Detailed):**")[0].strip()
                mind = content.split("**4. The Psychological Mind Fix (Detailed):**")[1].split("**5. The Lalita Sahasranama Spiritual Remedy:**")[0].strip()
                remedy = content.split("**5. The Lalita Sahasranama Spiritual Remedy:**")[1].strip()
                
                with st.expander(f"🔍 The Vedic Diagnosis for {user_name}", expanded=True):
                    st.write(diag)
                
                with st.expander(f"🌀 The Chakra Blockage: {vedic['chakra']}", expanded=True):
                    st.write(chakra)
                    
                col_a, col_b = st.columns(2)
                with col_a:
                    st.info(f"**🧘 Ayurvedic Body Fix ({vedic['dosha']})**\n\n{body}")
                with col_b:
                    st.warning(f"**🧠 Psychological Mind Fix**\n\n{mind}")
                    
                st.success(f"**🕉️ Lalita Sahasranama Spiritual Remedy**\n\n{remedy}")
                
            except Exception:
                st.info(content)
            
            st.session_state["user_name"] = user_name
            st.session_state["vedic"] = vedic
            st.session_state["reading"] = content

# --- CHAT ---
st.divider()
st.header(f"💬 Discuss {user_name}'s Corrective Actions")
if "messages" not in st.session_state: st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.markdown(msg["content"])

if user_query := st.chat_input("Ask about your remedies..."):
    if not api_key: st.error("API Key missing.")
    elif "vedic" not in st.session_state: st.error("Please run the diagnostic first.")
    else:
        st.session_state.messages.append({"role": "user", "content": user_query})
        with st.chat_message("user"): st.markdown(user_query)
        
        with st.chat_message("assistant"):
            with st.spinner("Reflecting..."):
                llm = ChatOpenAI(model="glm-4.5-flash", openai_api_key=api_key, openai_api_base="https://api.z.ai/api/paas/v4", temperature=0.7, extra_body={"thinking": {"type": "disabled"}})
                chat_prompt = f"You are speaking to {st.session_state['user_name']}. Chart: {st.session_state['vedic']}. Reading: {st.session_state['reading']}. Answer: {user_query}"
                response = llm.invoke(chat_prompt)
                st.markdown(response.content)
                st.session_state.messages.append({"role": "assistant", "content": response.content})
