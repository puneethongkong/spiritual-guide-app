import streamlit as st
import swisseph as swe
from datetime import datetime
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
    
    slider_val = st.slider(
        "How should we explain your results?", 
        0, 100, 50, 
        help="0 = Modern Science (Psychology), 100 = Ancient Philosophy (Vedic/Kashmir Shaivism)"
    )
    
    st.header("2. Birth Details")
    dob = st.date_input("Date of Birth", datetime(1983, 12, 27))
    tob = st.time_input("Time of Birth", datetime.strptime("00:35", "%H:%M").time())
    lat = st.number_input("Latitude", value=31.64, format="%.4f")
    lon = st.number_input("Longitude", value=76.13, format="%.4f")
    tz = st.number_input("Timezone (UTC offset)", value=5.5)

    st.header("3. The 12 Scientific Questions (0=Never, 4=Always)")
    # CET (Critical Existential Thinking)
    q1 = st.slider("I think deeply about life and death.", 0, 4, 2)
    q2 = st.slider("I question my core beliefs.", 0, 4, 2)
    q3 = st.slider("I handle uncertainty well.", 0, 4, 2)
    # PMP (Personal Meaning Production)
    q4 = st.slider("I find meaning in hard times.", 0, 4, 2)
    q5 = st.slider("My life has a clear direction.", 0, 4, 2)
    q6 = st.slider("I learn from my past mistakes.", 0, 4, 2)
    # TA (Transcendental Awareness)
    q7 = st.slider("I feel a deep spiritual connection.", 0, 4, 2)
    q8 = st.slider("I feel deeply connected to nature.", 0, 4, 2)
    q9 = st.slider("I can watch my thoughts without getting swept away.", 0, 4, 2)
    # CSE (Conscious State Expansion)
    q10 = st.slider("I can find inner peace on demand.", 0, 4, 2)
    q11 = st.slider("I experience moments of deep mental silence.", 0, 4, 2)
    q12 = st.slider("I stay calm in stressful situations.", 0, 4, 2)

# --- CORE ASTROLOGY ---
def calculate_vedic_profile(dob, tob, lat, lon, tz):
    dt = datetime.combine(dob, tob)
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
        with st.spinner("Analyzing your Vedic Chart, Psychological State, and 10 books..."):
            
            vedic = calculate_vedic_profile(dob, tob, lat, lon, tz)
            
            # --- CALCULATE THE SCIENTIFIC SISRI SCORES ---
            cet_score = int(((q1 + q2 + q3) / 12) * 100)
            pmp_score = int(((q4 + q5 + q6) / 12) * 100)
            ta_score = int(((q7 + q8 + q9) / 12) * 100)
            cse_score = int(((q10 + q11 + q12) / 12) * 100)
            
            retriever = load_knowledge_base()
            docs = retriever.invoke(f"{vedic['atmakaraka']} remedies {vedic['dosha']} balancing {vedic['chakra']}")
            context = "\n\n".join([d.page_content for d in docs])
            
            llm = ChatOpenAI(model="glm-4.5-flash", openai_api_key=api_key, openai_api_base="https://api.z.ai/api/paas/v4", temperature=0.7, extra_body={"thinking": {"type": "disabled"}})
            
            # THE SYNTHESIS PROMPT
            prompt = f"""
            You are a Spiritual Guide blending Ancient Vedic Wisdom with Modern Psychology (SISRI-24).
            User Slider Preference (0=Science, 100=Philosophy): {slider_val}
            
            Ancient Data:
            - Core Theme: {vedic['theme']} ({vedic['atmakaraka']})
            - Active Chakra: {vedic['chakra']}
            - Ayurvedic Imbalance: {vedic['dosha']}
            
            Modern Scientific SISRI-24 Scores:
            - Critical Existential Thinking: {cet_score}/100
            - Personal Meaning Production: {pmp_score}/100
            - Transcendental Awareness: {ta_score}/100
            - Conscious State Expansion (Inner Calm): {cse_score}/100
            
            Context from the 10 ancient books: {context}
            
            Task: Write a 3-part prescription.
            1. The Diagnosis: Blend the Vedic theme ({vedic['atmakaraka']}) with the modern psychological scores (e.g., high CET but low CSE). If the slider is closer to 100, use Vedic terms. If closer to 0, use modern psychological terms.
            2. The Body & Mind Fix: Give one Ayurvedic action for {vedic['dosha']} AND one psychological reframe for their specific SISRI scores.
            3. The Vedic Remedy: Recommend Lalita Namas {vedic['nama_range']} (e.g., {vedic['sample_nama']}) and explain how it pierces the {vedic['chakra']}.
            
            Keep it under 250 words.
            """
            
            response = llm.invoke(prompt)
            
            st.success("✅ Synthesis Complete")
            
            # DISPLAY THE METRICS
            col1, col2, col3 = st.columns(3)
            col1.metric("Vedic Theme", vedic['theme'])
            col2.metric("Chakra", vedic['chakra'])
            col3.metric("Dosha", vedic['dosha'])
            
            st.markdown("### Modern Scientific Scores (SISRI-24)")
            st.write(f"**Critical Thinking:** {cet_score}% | **Meaning:** {pmp_score}% | **Transcendental Awareness:** {ta_score}% | **Inner Calm:** {cse_score}%")
            
            st.info(response.content)
            
            st.session_state["vedic"] = vedic
            st.session_state["reading"] = response.content

# --- CHAT ---
st.divider()
st.header("💬 Discuss Your Corrective Actions")
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
                chat_prompt = f"User Chart: {st.session_state['vedic']}. Reading: {st.session_state['reading']}. Answer: {user_query}"
                response = llm.invoke(chat_prompt)
                st.markdown(response.content)
                st.session_state.messages.append({"role": "assistant", "content": response.content})
