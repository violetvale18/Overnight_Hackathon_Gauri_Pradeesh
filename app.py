# app.py - Final working version for Streamlit + Google Gemini (robust)
import os
import uuid
import traceback
import streamlit as st
from streamlit_mic_recorder import mic_recorder



def calculate_loan_approval(income, loan_amount, credit_score):
    # Basic rule logic:
    # 1. Income must be ≥ 2x EMI
    # 2. EMI formula simplified: EMI ≈ loan_amount / 60 (5-year loan)
    # 3. Credit score thresholds decide approval level
    
    emi = loan_amount / 60
    
    if credit_score >= 750 and income >= emi * 2:
        return "Approved ✅ (Excellent eligibility — low risk)"
    elif 650 <= credit_score < 750 and income >= emi * 2.5:
        return "Conditionally Approved ⚠ (Need stable income proof)"
    elif 550 <= credit_score < 650 and income >= emi * 3:
        return "High-Risk ❌ (Need guarantor or collateral)"
    else:
        return "Rejected ❌ (Income or credit score too low)"


# Install-time deps: google-genai, streamlit, gtts
try:
    from google import genai
except Exception as e:
    st.stop()  # If imports fail, stop and show instruction below

from gtts import gTTS

# -----------------------
# CONFIG: Paste your key:
# -----------------------
API_KEY = ""  # <-- PUT KEY HERE (AIza...); do NOT commit to public repo

# Default model preference (will auto-fallback if unavailable)
PREFERRED_MODELS = [
    "gemini-1.5-mini",
    "gemini-1.5-small",
    "gemini-1.5",
    "gemini-1.0",
]

# Utility: extract text from response for different SDK shapes
def extract_text_from_response(resp):
    # Try common attributes used by different SDK versions
    if resp is None:
        return ""
    # If response has .text or .output_text
    for attr in ("text", "output_text"):
        if hasattr(resp, attr):
            val = getattr(resp, attr)
            if isinstance(val, str) and val.strip():
                return val.strip()
    # If response has 'outputs' list (newer formats)
    try:
        outputs = getattr(resp, "outputs", None)
        if outputs:
            parts = []
            for out in outputs:
                # each out may have 'content' or 'text'
                if isinstance(out, dict):
                    # dict format
                    for key in ("content", "text"):
                        if key in out:
                            parts.append(str(out[key]))
                    # nested 'text' in 'parts'
                    if "parts" in out and isinstance(out["parts"], list):
                        parts.extend([str(p) for p in out["parts"] if isinstance(p, str)])
                else:
                    # object with attributes
                    if hasattr(out, "content"):
                        parts.append(str(getattr(out, "content")))
                    elif hasattr(out, "text"):
                        parts.append(str(getattr(out, "text")))
            if parts:
                return "\n".join([p.strip() for p in parts if p])
    except Exception:
        pass
    # Last resort, stringify response
    try:
        return str(resp)
    except Exception:
        return ""

# Create client
def create_client(key):
    return genai.Client(api_key=key)

# Try to generate using a model name and return (success, text or error)
def try_generate(client, model_name, prompt):
    try:
        # Two common calling styles: client.models.generate_content(...) OR client.responses.generate(...)
        # Try models.generate_content first (newer)
        try:
            resp = client.models.generate_content(
                model=model_name,
                contents=[{"role": "user", "parts": [{"text": prompt}]}]
            )
            text = extract_text_from_response(resp)
            return True, text
        except TypeError:
            # some SDKs expect different keyword names - try alternative form
            resp = client.models.generate_content(model=model_name, input=prompt)
            text = extract_text_from_response(resp)
            return True, text
        except Exception as e_inner:
            # If models.generate_content failed, try responses.generate (older versions)
            try:
                resp = client.responses.generate(model=model_name, input=prompt)
                text = extract_text_from_response(resp)
                return True, text
            except Exception as e2:
                # bubble up last error message
                return False, f"Model call failed: {e2}"
    except Exception as e:
        return False, f"Call failed: {e}"

# Find a workable model from preference or by listing available models
def choose_working_model(client, prompt):
    # Try preferred models first
    for m in PREFERRED_MODELS:
        ok, txt = try_generate(client, m, "Say: testing model availability")
        if ok and txt:
            return m, None
    # If none of preferred models worked, list available models and try them
    try:
        models = client.models.list()
        # models may be generator/iterable - build list of names
        names = []
        for m in models:
            try:
                nm = getattr(m, "name", None) or (m if isinstance(m, str) else None)
            except Exception:
                nm = None
            if nm:
                names.append(nm)
        # Filter names that contain 'gemini' first
        candidate_names = [n for n in names if "gemini" in n.lower()]
        # add rest as fallback
        candidate_names += [n for n in names if n not in candidate_names]
        for nm in candidate_names:
            ok, txt = try_generate(client, nm, "Say: testing model availability")
            if ok and txt:
                return nm, None
        return None, "No usable model found from the available model list."
    except Exception as e:
        return None, f"Failed to list models: {e}"

# -------------------
# Streamlit UI start
# -------------------
st.set_page_config(page_title="AI Loan Assistant", layout="centered")

st.markdown("""
<div style="text-align:center; font-size:32px; font-weight:700;">
💰 AI Loan Assistant
</div>
""", unsafe_allow_html=True)

st.markdown("<hr style='border:1px solid #ccc;'>", unsafe_allow_html=True)

# Validate API key present
if not API_KEY or API_KEY.startswith("PASTE_YOUR"):
    st.error("API key missing. Open the file and set API_KEY to your Gemini key (from https://aistudio.google.com/app/apikey).")
    st.stop()

# Initialize client
try:
    client = create_client(API_KEY)
except Exception as e:
    st.error(f"Failed to create client: {e}")
    st.stop()

# Determine or reuse model
if "model_name" not in st.session_state:
    st.session_state.model_name = None
    st.session_state.model_error = None
    st.session_state.auto_checked = False

if not st.session_state.get("auto_checked", False):
    with st.spinner("Checking available models..."):
        model_name, model_err = choose_working_model(client, "Say: model check")
        if model_name:
            st.session_state.model_name = model_name
            st.session_state.model_error = None
        else:
            st.session_state.model_name = None
            st.session_state.model_error = model_err
    st.session_state.auto_checked = True

if st.session_state.model_error:
    st.error(f"Model detection error: {st.session_state.model_error}")
    st.stop()

if not st.session_state.model_name:
    st.error("No working model detected.")
    st.stop()

st.caption(f"Using model: **{st.session_state.model_name}**")

# init chat history
if "messages" not in st.session_state:
    st.session_state.messages = [("assistant", "Hi — I'm your loan assistant. Ask about eligibility, documents, or loan types.")]

# display messages
with st.container():
    for role, text in st.session_state.messages:
        if role == "user":
            st.chat_message("user").write(f"🧑‍💼 {text}")
        else:
            st.chat_message("assistant").write(f"🤖 {text}")


# --- Speech to Text Input ---
st.markdown("<br><b>🎙 Voice Input</b><br>", unsafe_allow_html=True)
audio = mic_recorder(start_prompt="🎤 Speak", stop_prompt="🛑 Stop", key="voice")
st.markdown("<br>", unsafe_allow_html=True)

spoken_text = None
if audio:
    try:
        # Gemini can transcribe audio input directly
        st.audio(audio["bytes"])
        transcription = client.models.generate_content(
            model=st.session_state.model_name, 
            contents=[{"role": "user", "parts": [{"mime_type": "audio/wav", "data": audio["bytes"]}]}]
        )
        spoken_text = transcription.text.strip()
        st.success(f"🗣 Transcribed: {spoken_text}")
    except:
        st.warning("⚠ Voice failed to transcribe. Try again.")


# user input
typed_input = st.chat_input("Ask about loans...")
user_input = spoken_text if spoken_text else typed_input


if user_input:
    st.chat_message("user").write(user_input)
    st.session_state.messages.append(("user", user_input))

    prompt = f"""
You are a loan advisor. First answer normally.

Then check if the user provided numbers like:
- Monthly income
- Loan amount
- Credit score

If these values exist, calculate eligibility using rules:

- EMI = loan_amount / 60
- If credit score ≥ 750 and income ≥ EMI × 2 → Approved
- If credit score 650–749 and income ≥ EMI × 2.5 → Conditional approval
- If credit score 550–649 and income ≥ EMI × 3 → High risk
- Otherwise → Rejected

Then output a final decision line starting with: 
➡ FINAL DECISION: <result>

User: {user_input}
"""


    # Attempt the generation with robust handling
    try:
        with st.spinner("Contacting Gemini..."):
            ok, result = try_generate(client, st.session_state.model_name, prompt)
        if not ok:
            # If failed, show error (first line)
            first_line = str(result).splitlines()[0]
            st.error(f"Model call failed: {first_line}")
            # Attempt to re-detect a working model once
            if not st.session_state.get("tried_reselect", False):
                st.session_state.tried_reselect = True
                with st.spinner("Attempting to find alternative model..."):
                    new_model, err = choose_working_model(client, "Say: model check")
                    if new_model and new_model != st.session_state.model_name:
                        st.session_state.model_name = new_model
                        st.success(f"Switched to model: {new_model}. Retry your query.")
                    else:
                        st.warning("No alternative model available. See sidebar for debug.")
            st.stop()
        reply = result or ""
        reply = reply.strip()
        if not reply:
            st.warning("Model replied with empty text.")
        else:
            st.chat_message("assistant").write(reply)
            st.session_state.messages.append(("assistant", reply))

            # Text-to-speech: create unique filename to avoid permission issues
            try:
                mp3_name = f"reply_{uuid.uuid4().hex}.mp3"
                tts = gTTS(reply, lang="en")
                tts.save(mp3_name)
                st.audio(mp3_name)
                # optional: delete file later to keep folder clean (attempt)
                try:
                    os.remove(mp3_name)
                except Exception:
                    pass
            except Exception as e_audio:
                st.warning(f"Audio failed: {str(e_audio).splitlines()[0]}")
    except Exception as e_main:
        # Show the first line of the traceback for brevity
        tb = traceback.format_exc().splitlines()
        first = tb[-1] if tb else str(e_main)
        st.error(f"Unexpected error: {first}")
        # For debugging in sidebar, show more if needed
        with st.expander("Full debug trace (click to expand)"):
            st.text("\n".join(tb))

st.markdown("""
<br><br>
<div style='text-align:center; color:gray; font-size:14px;'>
🔹 Prototype: AI Loan Assistant • Team Titans 🔹
</div>
""", unsafe_allow_html=True)

