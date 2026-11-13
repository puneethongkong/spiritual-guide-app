import streamlit as st
import swisseph as swe
from datetime import datetime
from langchain_openai import ChatOpenAI
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
import pymupdf
import os
import requests

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Spiritual Diagnostic Engine", page_icon="🩺", layout="wide")
st.title("🩺 Ancient Wisdom Diagnostic Engine")
st.markdown("*Deep analysis of your Vedic Chart, Mind, and Body to find the friction and prescribe corrective action.*")

# --- SIDEBAR: SETUP & QUESTIONS ---
with st.sidebar:
    st.header("1. Setup")
    api_key = st.text_input("Z.ai API Key", type="password")
    
    st.header("2. Birth Details")
    dob = st.date_input("Date of Birth", datetime(1983, 12, 27))
    tob = st.time_input("Time of Birth", datetime.strptime("00:35", "%H:%M").time())
    lat = st.number_input("Latitude", value=31.64, format="%.4f")
    lon = st.number_input("Longitude", value=76.13, format="%.4f")
    tz = st.number_input("Timezone (UTC offset)", value=5.5)

    st.header("3. The 12 Questions (0=Never, 4=Always)")
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

# --- CORE ASTROLOGY & MAPPING ---
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
        "Jupiter": {"chakra": "Ajna (Third Eye)", "dosha": "Kapha", "theme": "Wisdom & Expansion", "nama_range": "521-527", "sample_nama": "N523 Shadanana (Six-faced)"},
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

# --- KNOWLEDGE BASE (Downloading from TmpFiles) ---
@st.cache_resource(show_spinner=False)
def load_knowledge_base():
    folder_path = "knowledge"
    os.makedirs(folder_path, exist_ok=True)
    
    # The direct link to the LSN text file
    file_url = "https://tmpfiles.org/dl/wQAp0NxHXK6I/srilalitasahasranamawithsaubhagyabhaskarabhaskaravilasakavyam-wlspansikar1935nsp_text.pdf"
    filename = "LSN_Text.pdf"
    filepath = os.path.join(folder_path, filename)
    
    # Download the file if it doesn't exist
    if not os.path.exists(filepath):
        with st.spinner("Downloading the Lalita Sahasranama text..."):
            r = requests.get(file_url)
            with open(filepath, 'wb') as f:
                f.write(r.content)
    
    texts = []
    try:
        # Since it's a PDF, we use pymupdf
        doc = pymupdf.open(filepath)
        for page in doc: 
            texts.append(page.get_text())
        doc.close()
    except Exception as e:
        st.error(f"Error reading the PDF: {e}")
        texts.append("Knowledge base loading failed.")
                
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    chunks = splitter.create_documents(texts)
    embeddings = HuggingFaceEmbeddings(model_name="paraphrase-MiniLM-L3-v2")
    vectorstore = Chroma.from_documents(chunks, embeddings)
    return vectorstore.as_retriever(search_kwargs={"k": 3})

# --- MAIN APP ---
if st.button("Run Deep Diagnostic Analysis", type="primary"):
    if not api_key:
        st.error("Please enter your Z.ai API Key.")
    else:
        with st.spinner("Analyzing your Vedic Chart, Psychological State, and Energetic Blockages..."):
            vedic = calculate_vedic_profile(dob, tob, lat, lon, tz)
            
            calm_score = ((q10 + q11 + q12) / 12) * 100
            thinking_score = ((q1 + q2 + q3) / 12) * 100
            
            friction = "You have high mental activity (overthinking) but low inner calm. Your soul wants wisdom, but your mind is too busy to hear it."
            if calm_score > 70:
                friction = "You have good inner peace, but you may be using it to avoid the real world. Your soul wants action, but your mind is hiding in the silence."
                
            retriever = load_knowledge_base()
            docs = retriever.invoke(f"{vedic['atmakaraka']} remedies {vedic['dosha']} balancing {vedic['chakra']}")
            context = "\n\n".join([d.page_content for d in docs])
            
            llm = ChatOpenAI(model="glm-4.5-flash", openai_api_key=api_key, openai_api_base="https://api.z.ai/api/paas/v4", temperature=0.7, extra_body={"thinking": {"type": "disabled"}})
            
            prompt = f"""
            You are a Spiritual Doctor. 
            Patient Data:
            - Core Theme: {vedic['theme']} ({vedic['atmakaraka']})
            - Active Chakra: {vedic['chakra']}
            - Ayurvedic Imbalance: {vedic['dosha']}
            - Mind State: Calm Score {calm_score}/100, Thinking Score {thinking_score}/100.
            
            Friction Diagnosis: {friction}
            
            Context from ancient texts: {context}
            
            Write a Prescription with 4 short, clear sections:
            1. The Diagnosis: Explain their friction in plain English.
            2. Somatic Fix (Body): A specific Ayurvedic action to balance {vedic['dosha']}.
            3. Psychological Fix (Mind): A mental reframe based on their scores.
            4. Vedic Fix (Soul): Recommend the specific Lalita Namas {vedic['nama_range']} (e.g., {vedic['sample_nama']}) and a simple mantra for {vedic['atmakaraka']}.
            
            Keep it under 250 words.
            """
            
            response = llm.invoke(prompt)
            
            st.success("✅ Diagnostic Complete")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Core Theme", vedic['theme'])
            col2.metric("Active Chakra", vedic['chakra'])
            col3.metric("Ayurvedic Type", vedic['dosha'])
            
            st.info(response.content)
            
            st.session_state["vedic"] = vedic
            st.session_state["reading"] = response.content
            st.session_state["friction"] = friction

# --- CHAT INTERFACE ---
st.divider()
st.header("💬 Discuss Your Corrective Actions")
if "messages" not in st.session_state: st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.markdown(msg["content"])

if user_query := st.chat_input("Ask about your remedies, dosha, or chakra..."):
    if not api_key: st.error("API Key missing.")
    elif "vedic" not in st.session_state: st.error("Please run the diagnostic first.")
    else:
        st.session_state.messages.append({"role": "user", "content": user_query})
        with st.chat_message("user"): st.markdown(user_query)
        
        with st.chat_message("assistant"):
            with st.spinner("Reflecting..."):
                llm = ChatOpenAI(model="glm-4.5-flash", openai_api_key=api_key, openai_api_base="https://api.z.ai/api/paas/v4", temperature=0.7, extra_body={"thinking": {"type": "disabled"}})
                chat_prompt = f"User Chart: {st.session_state['vedic']}. Friction: {st.session_state['friction']}. Context: {st.session_state['reading']}. Answer: {user_query}"
                response = llm.invoke(chat_prompt)
                st.markdown(response.content)
                st.session_state.messages.append({"role": "assistant", "content": response.content})
