import streamlit as st
import requests

# ============================================================
# PASTE your real Lambda Function URL here
# ============================================================
LAMBDA_URL = "https://nmpfj3dvfqhb4aqq3eoqy45ljm0gnyvh.lambda-url.us-east-1.on.aws/"

st.set_page_config(page_title="SAP Q&A", page_icon="💬")
st.title("SAP Data Q&A - Chatbot")

if "history" not in st.session_state:
    st.session_state.history = []

for role, msg in st.session_state.history:
    with st.chat_message(role):
        st.markdown(msg)

question = st.chat_input("Ask a question about your SAP data...")

if question:
    st.session_state.history.append(("user", question))
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                resp = requests.post(
                    LAMBDA_URL,
                    json={"question": question},
                    timeout=100,
                )
                data = resp.json()
                answer = data.get("answer") or data.get("error") or "No response received."
            except Exception as e:
                answer = f"Error reaching the chatbot: {e}"
        st.markdown(answer)

    st.session_state.history.append(("assistant", answer))
