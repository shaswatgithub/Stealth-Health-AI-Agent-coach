import streamlit as st
import json
from pydantic import BaseModel, Field
import google.generativeai as genai
import PyPDF2

# ==========================================
# PAGE CONFIG
# ==========================================
st.set_page_config(
    page_title="Stealth Health AI Agent",
    page_icon="🧘",
    layout="centered"
)

# ==========================================
# GEMINI SETUP
# ==========================================
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash") # Stable production model supporting structural JSON schemas
except Exception:
    st.error("Missing GEMINI_API_KEY. Add it in Streamlit Secrets.")
    st.stop()

# ==========================================
# DEFAULT PROTOCOL
# ==========================================
DEFAULT_PROTOCOL = """
WELLNESS PROTOCOL
DAY 1:
- Introduction
- Establish hydration baseline
- Review sleep habits
DAY 2:
- Check hydration adherence
- Review meal logging
DAY 3:
- Focus on consistency
- Review sleep quality
- Check caffeine avoidance after 2 PM
DAY 4:
- Review progress
- Identify obstacles
DAY 5:
- Accountability check
- Focus on long-term consistency

RULES:
1. Hydration: Drink exactly 3 Liters daily.
2. Avoid caffeine after 2 PM.
3. Sleep: Maintain an 8-hour sleep window.
4. No screens 45 minutes before bed.
5. Activity: Minimum 8000 steps daily.
6. Stretch 10 minutes every morning.
7. Log meals within 30 minutes.
8. Never skip two days in a row.
9. Consistency beats perfection.
"""

# ==========================================
# PROFILE MODEL
# ==========================================
class PatientProfile(BaseModel):
    name: str = "Guest"
    age: int = 25
    primary_goal: str = "General Wellness"
    sleep_hours: float = 7.0
    current_day: int = 1

# ==========================================
# INITIALIZE SESSION STATE
# ==========================================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "profile" not in st.session_state:
    st.session_state.profile = PatientProfile()
if "extracted" not in st.session_state:
    st.session_state.extracted = False

# ==========================================
# URL EXTRACTION (Runs once on boot)
# ==========================================
query_params = st.query_params

if "raw_data" in query_params and not st.session_state.extracted:
    raw_text = query_params["raw_data"]
    
    extraction_prompt = f"""
    Extract patient information into the specified format.
    Text: {raw_text}
    """
    try:
        # Secure deterministic structured output from Gemini engine
        response = model.generate_content(
            extraction_prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
                response_schema=PatientProfile
            )
        )
        profile_data = json.loads(response.text)
        st.session_state.profile = PatientProfile(**profile_data)
        st.session_state.extracted = True
    except Exception:
        pass

# ==========================================
# HEADER
# ==========================================
st.title("🧘 Stealth Health AI Agent")
st.caption("Personalized wellness coaching with memory and protocol grounding")

# ==========================================
# PDF UPLOAD
# ==========================================
uploaded_pdf = st.file_uploader("Upload Wellness Protocol PDF", type=["pdf"])
pdf_text = ""

if uploaded_pdf is not None:
    try:
        reader = PyPDF2.PdfReader(uploaded_pdf)
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pdf_text += text + "\n"
        st.success("Protocol PDF loaded successfully")
    except Exception as e:
        st.warning(f"Could not read PDF: {e}")

REFERENCE_PROTOCOL = pdf_text if pdf_text.strip() else DEFAULT_PROTOCOL

# ==========================================
# SIDEBAR (Directly binds to state via keys)
# ==========================================
st.sidebar.title("📋 Patient State")

st.session_state.profile.name = st.sidebar.text_input("Name", st.session_state.profile.name)
st.session_state.profile.age = st.sidebar.number_input("Age", min_value=1, max_value=120, value=int(st.session_state.profile.age))
st.session_state.profile.primary_goal = st.sidebar.text_input("Primary Goal", st.session_state.profile.primary_goal)
st.session_state.profile.sleep_hours = st.sidebar.number_input("Sleep Hours", value=float(st.session_state.profile.sleep_hours))
st.session_state.profile.current_day = st.sidebar.number_input("Protocol Day", min_value=1, value=int(st.session_state.profile.current_day))

st.sidebar.json(st.session_state.profile.model_dump())

# ==========================================
# RESEARCH EXTRACTION RESULTS DISPLAY
# ==========================================
st.subheader("📋 Research Extraction Results")
st.json(st.session_state.profile.model_dump())

# ==========================================
# DAY CONTEXT SWITCHER
# ==========================================
day = st.session_state.profile.current_day

if day == 1:
    day_context = "Day 1 Introduction. Welcome the patient warmly. Review: hydration, sleep, and wellness goals."
elif day == 2:
    day_context = "Day 2. Review hydration adherence and explicitly discuss meal logging parameters."
elif day == 3:
    day_context = "Day 3. Focus intensely on consistency. Review sleep quality and check caffeine avoidance windows after 2 PM."
elif day == 4:
    day_context = "Day 4. Review programmatic progress and isolate behavioral obstacles."
else:
    day_context = f"Day {day} Follow Up. Maintain high accountability and long-term consistency metrics. Focus on their target: '{st.session_state.profile.primary_goal}'."

# ==========================================
# SYSTEM INSTRUCTIONS
# ==========================================
system_prompt = f"""
You are a warm, supportive personal health coach. 

PATIENT METRICS:
Name: {st.session_state.profile.name}
Age: {st.session_state.profile.age}
Goal: {st.session_state.profile.primary_goal}
Average Sleep: {st.session_state.profile.sleep_hours} hours

TIMELINE INTERACTION PROTOCOL:
{day_context}

KNOWLEDGE BOUNDARY GATES (ZERO HALLUCINATION):
Only answer wellness protocol questions using the facts provided below.
If user asks about topics or instructions not present in the protocol text, respond EXACTLY:
"I couldn't find that in the protocol document."

REFERENCE KNOWLEDGE DOCUMENT:
{REFERENCE_PROTOCOL}
"""

# ==========================================
# CHAT ARCHITECTURE
# ==========================================
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if user_input := st.chat_input("Ask your coach or log today's progress..."):
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Model architecture configuration
    orchestration_model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=system_prompt
    )

    # Convert native memory items to formal chat objects
    chat_history = []
    for msg in st.session_state.messages[-8:]:
        role = "user" if msg["role"] == "user" else "model"
        chat_history.append({"role": role, "parts": [msg["content"]]})

    with st.chat_message("assistant"):
        try:
            response = orchestration_model.generate_content(
                chat_history,
                generation_config={"temperature": 0.15}
            )
            response_text = response.text
        except Exception as e:
            response_text = f"Error generating response: {e}"
        
        st.markdown(response_text)
    st.session_state.messages.append({"role": "assistant", "content": response_text})