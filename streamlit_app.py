import streamlit as st
import requests
from streamlit_agraph import agraph, Node, Edge, Config


# ============================================================
# CONFIGURATION
# ============================================================

LAMBDA_URL = "https://nmpfj3dvfqhb4aqq3eoqy45ljm0gnyvh.lambda-url.us-east-1.on.aws/"

GRAPH_JSON_URL = (
    "https://graphdbarun.s3.us-east-1.amazonaws.com/sap_graph_d3.json"
)


# ============================================================
# STREAMLIT PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="SAP Q&A",
    page_icon="💬",
    layout="wide"
)

st.title("SAP Data Q&A - Chatbot")


# ============================================================
# CHAT HISTORY
# ============================================================

if "history" not in st.session_state:
    st.session_state.history = []


# Display previous messages
for role, msg in st.session_state.history:
    with st.chat_message(role):
        st.markdown(msg)


# ============================================================
# CHAT INPUT
# ============================================================

question = st.chat_input(
    "Ask a question about your SAP data..."
)


if question:

    # Store and display user question
    st.session_state.history.append(
        ("user", question)
    )

    with st.chat_message("user"):
        st.markdown(question)


    # Call Lambda
    with st.chat_message("assistant"):

        with st.spinner("Thinking..."):

            try:

                resp = requests.post(
                    LAMBDA_URL,
                    json={
                        "question": question
                    },
                    timeout=100,
                )

                # Raise error for 4xx / 5xx responses
                resp.raise_for_status()

                data = resp.json()

                answer = (
                    data.get("answer")
                    or data.get("error")
                    or "No response received."
                )

            except requests.exceptions.Timeout:

                answer = (
                    "The chatbot request timed out. "
                    "Please try again."
                )

            except requests.exceptions.RequestException as e:

                answer = (
                    f"Error reaching the chatbot: {e}"
                )

            except ValueError:

                answer = (
                    "The chatbot returned an invalid response."
                )

            except Exception as e:

                answer = (
                    f"Unexpected error: {e}"
                )


        st.markdown(answer)


    # Store assistant response
    st.session_state.history.append(
        ("assistant", answer)
    )


# ============================================================
# SAP RELATIONSHIP GRAPH
# ============================================================

st.divider()

st.subheader("SAP Table Relationship Graph")


# ============================================================
# LOAD GRAPH JSON
# ============================================================

@st.cache_data
def load_graph_data():

    try:

        resp = requests.get(
            GRAPH_JSON_URL,
            timeout=30
        )

        resp.raise_for_status()

        return resp.json()

    except Exception as e:

        st.error(
            f"Could not load graph data: {e}"
        )

        return None


graph_data = load_graph_data()


# ============================================================
# BUILD GRAPH
# ============================================================

if graph_data:

    nodes = [
        Node(
            id=n["id"],
            label=n["id"],
            size=15,
            color=(
                "#4CAF50"
                if n.get("group") == 1
                else "#CCCCCC"
            )
        )
        for n in graph_data.get("nodes", [])
    ]


    edges = [
        Edge(
            source=e["source"],
            target=e["target"],
            label=e.get(
                "via_field",
                ""
            )
        )
        for e in graph_data.get("links", [])
    ]


    # ========================================================
    # GRAPH CONFIGURATION
    # ========================================================

    config = Config(
        width=900,
        height=600,
        directed=True,
        physics=True,
        hierarchical=False
    )


    # ========================================================
    # DISPLAY GRAPH
    # ========================================================

    agraph(
        nodes=nodes,
        edges=edges,
        config=config
    )

else:

    st.warning(
        "Graph data is currently unavailable."
    )
