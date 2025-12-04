import streamlit as st
from openai import OpenAI

client = OpenAI(api_key="sk-proj-UrPPgeel0EU1Ylv4niIHFBJ49GeiXA-kC4H0rh2p3GTbwHxeLxJOU7MPzNOaCj9m6Dtq2IN6NxT3BlbkFJpxpHMK-_9hTCWbfp2eIhVFB2mLRFvt5oxEMU8DadMCFhkiR5MaEZ5Lpv1DhL1VCqxGLqeHuS8AY")

st.title("💬 Multilingual AI Loan Advisor")

system_prompt = """
You are a multilingual loan advisor for India.
If the user writes in Hindi, respond in Hindi.
Ask for monthly income, employment type, location, and loan type if missing.
Give eligibility and required documents in short points.
Be polite, helpful, and simple.
"""

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": system_prompt}]

for msg in st.session_state.messages:
    if msg["role"] != "system":
        st.chat_message(msg["role"]).write(msg["content"])

user_input = st.chat_input("Ask about loans...")

if user_input:
    st.chat_message("user").write(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=st.session_state.messages
    )

    reply = response.choices[0].message.content
    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.chat_message("assistant").write(reply)

