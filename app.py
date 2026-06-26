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
    model = genai.GenerativeModel("gemini-2.5-flash")
except Exception:
    st.error("Missing GEMINI_API_KEY in Streamlit Secrets.")
    st.stop()

# ==========================================
# DEFAULT PROTOCOL
# ==========================================
DEFAULT_PROTOCOL = """
WELLNESS PROTOCOL

DAILY RULES:
1. Hydration: Drink exactly 3 Liters of water daily.
2. Avoid caffeine after 2 PM.
3. Sleep: Maintain an 8-hour sleep window.
4. No screens 45 minutes before bed.
5. Activity: Minimum 8000 steps daily.
6. Stretch 10 minutes every morning.
7. Log meals within 30 minutes of eating.
8. Never skip two days in a row.
9. Consistency beats perfection.

DAY 1:
- Welcome and introduction
- Establish hydration baseline
- Review current sleep habits

DAY 2:
- Check hydration adherence
- Review meal logging habits

DAY 3:
- Focus on consistency
- Review sleep quality
- Check caffeine avoidance

DAY 4:
- Review overall progress
- Identify any obstacles

DAY 5+:
- Accountability check-in
- Long-term habit building
"""

# ==========================================
# PROFILE MODEL
# ==========================================
class PatientProfile(BaseModel):
    name: str = Field(default="Guest")
    age: int = Field(default=25)
    primary_goal: str = Field(default="General Wellness")
    sleep_hours: float = Field(default=7.0)
    current_day: int = Field(default=1)

# ==========================================
# HEADER
# ==========================================
st.title("🧘 Stealth Health AI Agent")
st.caption("Your personal wellness coach • Protocol-grounded • Adaptive daily guidance")

# ==========================================
# PDF UPLOAD
# ==========================================
uploaded_pdf = st.file_uploader("Upload Wellness Protocol PDF (optional)", type=["pdf"])
pdf_text = ""
if uploaded_pdf is not None:
    try:
        reader = PyPDF2.PdfReader(uploaded_pdf)
        for page in reader.pages:
            text = page.extract_text() or ""
            pdf_text += text + "\n"
        st.success("✅ Protocol PDF loaded")
    except Exception as e:
        st.warning(f"Could not read PDF: {e}")

REFERENCE_PROTOCOL = pdf_text.strip() if pdf_text.strip() else DEFAULT_PROTOCOL

# ==========================================
# SESSION STATE
# ==========================================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "profile" not in st.session_state:
    st.session_state.profile = None

# ==========================================
# URL EXTRACTION
# ==========================================
query_params = st.query_params
if "raw_data" in query_params and st.session_state.profile is None:
    raw_text = query_params["raw_data"]
    extraction_prompt = f"""
Extract patient information. Return ONLY valid JSON.
Schema: {{"name": "", "age": 0, "primary_goal": "", "sleep_hours": 0, "current_day": 1}}
Text: {raw_text}
"""
    try:
        resp = model.generate_content(extraction_prompt)
        json_text = resp.text.replace("```json", "").replace("```", "").strip()
        profile_data = json.loads(json_text)
        st.session_state.profile = PatientProfile(**profile_data)
    except:
        st.session_state.profile = PatientProfile()

if st.session_state.profile is None:
    st.session_state.profile = PatientProfile()

profile = st.session_state.profile

# ==========================================
# SIDEBAR
# ==========================================
with st.sidebar:
    st.title("📋 Patient Profile")
    profile.name = st.text_input("Name", profile.name)
    profile.age = st.number_input("Age", 1, 120, int(profile.age))
    profile.primary_goal = st.text_input("Primary Goal", profile.primary_goal)
    profile.sleep_hours = st.number_input("Sleep Hours", value=float(profile.sleep_hours), step=0.5)
    profile.current_day = st.number_input("Current Day", 1, 30, int(profile.current_day))
    st.json(profile.model_dump())

st.subheader("📋 Parsed Patient Profile")
st.json(profile.model_dump())

# ==========================================
# DAY CONTEXT
# ==========================================
day_contexts = {
    1: "Welcome warmly. Review hydration, sleep, and goals.",
    2: "Review hydration adherence and meal logging.",
    3: "Focus on consistency, sleep quality, and caffeine rules.",
    4: "Review progress and identify obstacles.",
    5: "Accountability and long-term consistency.",
}
day_context = day_contexts.get(profile.current_day, f"Day {profile.current_day} follow-up focused on consistency.")

# ==========================================
# IMPROVED SYSTEM PROMPT
# ==========================================
system_prompt = f"""
You are Stealth, a warm, practical, and encouraging health coach.

PATIENT:
- Name: {profile.name}
- Age: {profile.age}
- Goal: {profile.primary_goal}
- Sleep: {profile.sleep_hours} hours
- Day: {profile.current_day}

TODAY'S FOCUS: {day_context}

PROTOCOL GROUNDING:
You have access to the official wellness protocol below.
- Answer questions about rules, habits, or recommendations **directly from the protocol**.
- Quote or clearly reference the protocol when answering.
- If the exact information is not in the protocol, say: "I couldn't find that specific information in the wellness protocol document."

Full Protocol:
{REFERENCE_PROTOCOL}

Keep responses helpful, concise, and supportive. Use conversation history for context.
"""

# ==========================================
# CHAT
# ==========================================
st.subheader("💬 Chat with Stealth")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if user_input := st.chat_input("Ask about the protocol or log your progress..."):
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    history = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages[-10:]])
    full_prompt = f"{system_prompt}\n\nConversation so far:\n{history}\n\nStealth:"

    try:
        response = model.generate_content(full_prompt, generation_config={"temperature": 0.3})
        response_text = response.text
    except Exception as e:
        response_text = f"Error: {str(e)[:100]}"

    with st.chat_message("assistant"):
        st.markdown(response_text)
    st.session_state.messages.append({"role": "assistant", "content": response_text})

st.caption("Try: \"How much water should I drink daily?\"")
