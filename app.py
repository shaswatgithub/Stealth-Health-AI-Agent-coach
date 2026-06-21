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
    st.error(
        "Missing GEMINI_API_KEY. Add it in Streamlit Secrets."
    )
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
    name: str = Field(default="Guest")
    age: int = 25
    primary_goal: str = "General Wellness"
    sleep_hours: float = 7.0
    current_day: int = 1

# ==========================================
# HEADER
# ==========================================

st.title("🧘 Stealth Health AI Agent")

st.caption(
    "Personalized wellness coaching with memory and protocol grounding"
)

# ==========================================
# PDF UPLOAD
# ==========================================

uploaded_pdf = st.file_uploader(
    "Upload Wellness Protocol PDF",
    type=["pdf"]
)

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

REFERENCE_PROTOCOL = (
    pdf_text
    if pdf_text.strip()
    else DEFAULT_PROTOCOL
)

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

if (
    "raw_data" in query_params
    and st.session_state.profile is None
):

    raw_text = query_params["raw_data"]

    extraction_prompt = f"""
Extract patient information.

Return ONLY valid JSON.

Schema:

{{
  "name": "",
  "age": 0,
  "primary_goal": "",
  "sleep_hours": 0,
  "current_day": 1
}}

Rules:
- age must be integer
- sleep_hours must be number
- current_day must be integer
- no markdown
- no explanation

Text:

{raw_text}
"""

    try:

        response = model.generate_content(
            extraction_prompt
        )

        json_text = response.text

        json_text = (
            json_text
            .replace("```json", "")
            .replace("```", "")
            .strip()
        )

        profile_data = json.loads(json_text)

        st.session_state.profile = PatientProfile(
            **profile_data
        )

    except Exception:

        st.session_state.profile = PatientProfile()

# ==========================================
# DEFAULT PROFILE
# ==========================================

if st.session_state.profile is None:

    st.session_state.profile = PatientProfile()

profile = st.session_state.profile

# ==========================================
# SIDEBAR
# ==========================================

st.sidebar.title("📋 Patient State")

profile.name = st.sidebar.text_input(
    "Name",
    profile.name
)

profile.age = st.sidebar.number_input(
    "Age",
    min_value=1,
    max_value=120,
    value=int(profile.age)
)

profile.primary_goal = st.sidebar.text_input(
    "Primary Goal",
    profile.primary_goal
)

profile.sleep_hours = st.sidebar.number_input(
    "Sleep Hours",
    value=float(profile.sleep_hours)
)

profile.current_day = st.sidebar.number_input(
    "Protocol Day",
    min_value=1,
    value=int(profile.current_day)
)

st.sidebar.json(profile.model_dump())

# ==========================================
# RESEARCH EXTRACTION RESULTS
# ==========================================

st.subheader("📋 Research Extraction Results")

st.json(profile.model_dump())

# ==========================================
# DAY CONTEXT
# ==========================================

day = profile.current_day

if day == 1:

    day_context = """
Day 1 Introduction.

Welcome the patient.

Review:
- hydration
- sleep
- wellness goals
"""

elif day == 2:

    day_context = """
Day 2.

Review hydration adherence.

Discuss meal logging.
"""

elif day == 3:

    day_context = """
Day 3.

Focus on consistency.

Review:
- sleep quality
- caffeine avoidance
"""

elif day == 4:

    day_context = """
Day 4.

Review progress.

Identify obstacles.
"""

else:

    day_context = f"""
Day {day} Follow Up.

Focus on:

- consistency
- accountability
- progress

Goal:
{profile.primary_goal}
"""

# ==========================================
# SYSTEM PROMPT
# ==========================================

system_prompt = f"""
You are a warm, supportive health coach.

PATIENT:

Name: {profile.name}

Age: {profile.age}

Goal: {profile.primary_goal}

Average Sleep:
{profile.sleep_hours} hours

TIMELINE:

{day_context}

MEMORY:
Use previous conversation history.

PROTOCOL RULE:

Only answer protocol questions
using the protocol below.

If information is not found
inside the protocol document,
respond exactly:

"I couldn't find that in the protocol document."

PROTOCOL:

{REFERENCE_PROTOCOL}
"""

# ==========================================
# CHAT HISTORY
# ==========================================

for msg in st.session_state.messages:

    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ==========================================
# CHAT INPUT
# ==========================================

user_input = st.chat_input(
    "Ask your coach or log today's progress..."
)

if user_input:

    with st.chat_message("user"):
        st.markdown(user_input)

    st.session_state.messages.append(
        {
            "role": "user",
            "content": user_input
        }
    )

    conversation = system_prompt + "\n\n"

    for msg in st.session_state.messages[-8:]:

        conversation += (
            f"{msg['role']}: "
            f"{msg['content']}\n"
        )

    try:

        response = model.generate_content(
            conversation,
            generation_config={
                "temperature": 0.2
            }
        )

        response_text = response.text

    except Exception as e:

        response_text = (
            f"Error generating response: {e}"
        )

    with st.chat_message("assistant"):
        st.markdown(response_text)

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": response_text
        }
    )