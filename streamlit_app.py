import streamlit as st
import requests
import re
from collections import deque
from streamlit_agraph import agraph, Node, Edge, Config

# ============================================================
# CONFIGURATION & SECRETS
# ============================================================

LAMBDA_URL = st.secrets.get(
    "LAMBDA_URL",
    "https://nmpfj3dvfqhb4aqq3eoqy45ljm0gnyvh.lambda-url.us-east-1.on.aws/"
)
GRAPH_JSON_URL = st.secrets.get(
    "GRAPH_JSON_URL",
    "https://graphdbarun.s3.us-east-1.amazonaws.com/sap_graph_d3.json"
)

# ============================================================
# SAP STANDARD TABLE DESCRIPTIONS (ENRICHMENT LOOKUP)
# ============================================================

SAP_TABLE_DESC = {
    "EKKO": "Purchasing Document Header",
    "EKPO": "Purchasing Document Item",
    "MARA": "General Material Data",
    "MARC": "Plant Data for Material",
    "MARD": "Storage Location Data for Material",
    "MAKT": "Material Descriptions",
    "MBEW": "Material Valuation",
    "VBAK": "Sales Document Header Data",
    "VBAP": "Sales Document Item Data",
    "VBRK": "Billing Document Header",
    "VBRP": "Billing Document Item",
    "LIKP": "SD Document Delivery Header",
    "LIPS": "SD Document Delivery Item",
    "BKPF": "Accounting Document Header",
    "BSEG": "Accounting Document Segment",
    "KNA1": "Customer Master General Data",
    "LFA1": "Vendor Master General Data",
    "T001": "Company Codes",
    "T001W": "Plants / Branches",
    "T001L": "Storage Locations",
    "T024": "Purchasing Groups",
    "T024E": "Purchasing Organizations",
    "TVKO": "Sales Organizations",
    "EINA": "Purchase Info Record General Data",
    "EINE": "Purchase Info Record Purchasing Data",
    "EBAN": "Purchase Requisition",
    "RESB": "Reservation / Dependent Requirements",
    "MKPF": "Header Material Document",
    "MSEG": "Document Segment Material",
}

def get_table_label(table_id):
    desc = SAP_TABLE_DESC.get(table_id.upper())
    if desc:
        return f"{table_id} ({desc})"
    return table_id

# ============================================================
# PAGE CONFIG & ENTERPRISE STYLING
# ============================================================

st.set_page_config(
    page_title="SAP Data & Relationship Explorer",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(
    """
    <style>
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
        }
        div[data-testid="stMetric"] {
            background-color: rgba(128, 128, 128, 0.05);
            border: 1px solid rgba(128, 128, 128, 0.15);
            border-radius: 8px;
            padding: 12px;
            text-align: center;
        }
        .sap-badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 0.85rem;
            margin-right: 6px;
        }
        .sap-badge-orange { background-color: #FF9800; color: white; }
        .sap-badge-green { background-color: #4CAF50; color: white; }
        .sap-badge-blue { background-color: #42A5F5; color: white; }
        .sap-badge-grey { background-color: #9E9E9E; color: white; }
    </style>
    """,
    unsafe_allow_html=True
)

# ============================================================
# SESSION STATE INITIALISATION
# ============================================================

if "history" not in st.session_state:
    st.session_state.history = []

if "selected_table" not in st.session_state:
    st.session_state.selected_table = None

if "depth" not in st.session_state:
    st.session_state.depth = 1

if "max_nodes" not in st.session_state:
    st.session_state.max_nodes = 50

if "physics_enabled" not in st.session_state:
    st.session_state.physics_enabled = True

if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

# ============================================================
# HEADER
# ============================================================

st.title("💬 SAP Data & Relationship Explorer")
st.caption("Intelligent Q&A Assistant and Interactive SAP Table Network Visualizer.")

# ============================================================
# DATA CACHING & LOAD
# ============================================================

@st.cache_data(ttl=3600)
def load_graph_data():
    try:
        response = requests.get(GRAPH_JSON_URL, timeout=30)
        response.raise_for_status()
        data = response.json()
        if "nodes" not in data or "links" not in data:
            st.error("Graph JSON format invalid: Must contain 'nodes' and 'links'.")
            return None
        return data
    except Exception as e:
        st.error(f"Could not load SAP graph dataset: {e}")
        return None

graph_data = load_graph_data()
if not graph_data:
    st.warning("⚠️ SAP relationship graph data is currently unavailable.")
    st.stop()

raw_nodes = graph_data.get("nodes", [])
raw_links = graph_data.get("links", [])

table_ids = sorted({node["id"] for node in raw_nodes if node.get("id")})

adjacency = {}
directed_edges = []
for edge in raw_links:
    src = edge.get("source")
    tgt = edge.get("target")
    if not src or not tgt:
        continue
    adjacency.setdefault(src, set()).add(tgt)
    adjacency.setdefault(tgt, set()).add(src)
    directed_edges.append({
        "source": src,
        "target": tgt,
        "via_field": edge.get("via_field", "")
    })

if st.session_state.selected_table not in table_ids:
    st.session_state.selected_table = table_ids[0] if table_ids else None

def extract_sap_tables(text, valid_tables):
    words = set(re.findall(r'\b[A-Z0-9_]{3,8}\b', text.upper()))
    found = [w for w in words if w in valid_tables]
    return sorted(found)

# ============================================================
# SIDEBAR CONTROLS & UTILITIES
# ============================================================

with st.sidebar:
    st.header("⚙️ Explorer Settings")
    st.markdown("---")
    
    st.subheader("System Status")
    st.success("🟢 Graph Data Connected")
    st.info(f"📊 Total Tables: **{len(table_ids)}**")
    st.info(f"🔗 Total Edges: **{len(directed_edges)}**")
    
    st.markdown("---")
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.history = []
        st.toast("Chat history cleared!", icon="🧹")
        st.rerun()

# ============================================================
# TABS
# ============================================================

tab_chat, tab_graph = st.tabs(["💬 Chat Assistant", "🔗 Relationship Explorer"])

# ============================================================
# TAB 1: CHAT ASSISTANT
# ============================================================

with tab_chat:
    st.subheader("🤖 Ask Questions About SAP Data & Schema")
    st.caption("Enter natural language questions to query SAP records or schema knowledge.")

    st.markdown("💡 **Quick Starter Prompts:**")
    prompt_cols = st.columns(4)
    starters = [
        ("🛒 Purchase Orders", "Which SAP tables link Purchase Order headers to items and vendor data?"),
        ("📦 Material Master", "Explain the relationship between MARA, MARC, and MARD tables in SAP."),
        ("💰 Sales Documents", "How are Sales Document headers (VBAK) connected to items (VBAP) and billing?"),
        ("🏦 Financial Accounting", "What are the main tables for Financial Accounting (FI) header and line items?")
    ]
    for idx, (label, prompt_text) in enumerate(starters):
        with prompt_cols[idx]:
            if st.button(label, key=f"starter_{idx}", use_container_width=True):
                st.session_state.pending_question = prompt_text

    st.markdown("---")

    for role, message in st.session_state.history:
        with st.chat_message(role):
            st.markdown(message)
            if role == "assistant":
                referenced = extract_sap_tables(message, set(table_ids))
                if referenced:
                    st.caption("🔍 **Referenced SAP Tables (Click to explore graph):**")
                    btn_cols = st.columns(min(len(referenced), 6))
                    for i, tbl in enumerate(referenced[:6]):
                        with btn_cols[i]:
                            if st.button(f"🔗 {tbl}", key=f"hist_btn_{tbl}_{i}_{hash(message)}"):
                                st.session_state.selected_table = tbl
                                st.toast(f"Pivoted Graph to **{tbl}**! Switch to '🔗 Relationship Explorer' tab.", icon="🚀")

    chat_input_val = st.chat_input("Ask a question about your SAP data...")
    question = chat_input_val or st.session_state.pending_question

    if question:
        st.session_state.pending_question = None
        st.session_state.history.append(("user", question))
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Analyzing SAP schema and querying data..."):
                try:
                    response = requests.post(
                        LAMBDA_URL,
                        json={"question": question},
                        timeout=100,
                    )
                    response.raise_for_status()
                    data = response.json()
                    answer = data.get("answer") or data.get("error") or "No response received."
                except requests.exceptions.Timeout:
                    answer = "⏳ Request timed out. Please try again."
                except requests.exceptions.RequestException as e:
                    answer = f"⚠️ Error reaching backend chatbot: {e}"
                except ValueError:
                    answer = "⚠️ Received invalid JSON response from server."
                except Exception as e:
                    answer = f"⚠️ Unexpected error occurred: {e}"

            st.markdown(answer)
            st.session_state.history.append(("assistant", answer))

            referenced_tables = extract_sap_tables(answer, set(table_ids))
            if referenced_tables:
                st.caption("🔍 **Explore referenced SAP tables in Graph Explorer:**")
                cols = st.columns(min(len(referenced_tables), 6))
                for idx, tbl in enumerate(referenced_tables[:6]):
                    with cols[idx]:
                        if st.button(f"🔗 {tbl}", key=f"new_btn_{tbl}_{idx}"):
                            st.session_state.selected_table = tbl
                            st.toast(f"Selected table set to **{tbl}**. Switch to '🔗 Relationship Explorer' tab!", icon="🚀")

# ============================================================
# TAB 2: RELATIONSHIP EXPLORER
# ============================================================

with tab_graph:
    st.subheader("🔗 SAP Table Relationship Network")
    st.caption("Interactive multi-hop network traversal for SAP data architecture.")

    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
    
    with col1:
        selected = st.selectbox(
            "Search / Select SAP Table",
            options=table_ids,
            format_func=get_table_label,
            key="selected_table"
        )

    with col2:
        depth = st.selectbox(
            "Relationship Depth",
            options=[1, 2, 3],
            format_func=lambda v: f"{v} Hop" if v == 1 else f"{v} Hops",
            key="depth"
        )

    with col3:
        max_nodes = st.selectbox(
            "Maximum Tables",
            options=[25, 50, 75, 100],
            key="max_nodes"
        )

    with col4:
        physics_on = st.toggle("Enable Physics", value=st.session_state.physics_enabled, key="physics_enabled")

    def get_connected_tables(start, adj, max_depth):
        visited = {start: 0}
        queue = deque([(start, 0)])
        while queue:
            current, d = queue.popleft()
            if d >= max_depth:
                continue
            for neighbor in adj.get(current, set()):
                if neighbor not in visited:
                    nd = d + 1
                    visited[neighbor] = nd
                    queue.append((neighbor, nd))
        return visited

    table_depths = get_connected_tables(selected, adjacency, depth)

    sorted_tables = sorted(table_depths.items(), key=lambda x: (x[1], x[0]))
    limited = len(sorted_tables) > max_nodes
    if limited:
        sorted_tables = sorted_tables[:max_nodes]

    visible_tables = {t for t, _ in sorted_tables}
    visible_tables.add(selected)
    visible_depths = {t: table_depths.get(t, 0) for t in visible_tables}

    filtered_edges = [
        e for e in directed_edges
        if e["source"] in visible_tables and e["target"] in visible_tables
    ]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Selected Root Table", selected, delta=SAP_TABLE_DESC.get(selected, ""))
    m2.metric("Connected Tables", len(visible_tables))
    m3.metric("Relationships Found", len(filtered_edges))
    m4.metric("Traversal Depth", f"{depth} Hop" if depth == 1 else f"{depth} Hops")

    if limited:
        st.warning(
            f"⚠️ **{selected}** has a large network ({len(table_depths)} total reachable tables). "
            f"Display limited to **{max_nodes}** tables. Increase 'Maximum Tables' setting to expand."
        )

    nodes = []
    for table in sorted(visible_tables):
        table_depth = visible_depths.get(table, 0)
        table_desc = SAP_TABLE_DESC.get(table, "")
        node_label = f"{table}\n({table_desc})" if table_desc else table
        
        if table == selected:
            color = "#FF9800"
            size = 35
        elif table_depth == 1:
            color = "#4CAF50"
            size = 26
        elif table_depth == 2:
            color = "#42A5F5"
            size = 20
        else:
            color = "#9E9E9E"
            size = 16

        nodes.append(Node(id=table, label=node_label, size=size, color=color))

    edges = []
    for edge in filtered_edges:
        edges.append(Edge(
            source=edge["source"],
            target=edge["target"],
            label=edge["via_field"]
        ))

    config = Config(
        width="100%",
        height=650,
        directed=True,
        physics=physics_on,
        hierarchical=False,
        nodeHighlightBehavior=True,
        highlightColor="#FFD54F",
        collapsible=False,
        physicsConfig={
            "enabled": physics_on,
            "solver": "forceAtlas2Based",
            "forceAtlas2Based": {
                "gravitationalConstant": -60,
                "centralGravity": 0.01,
                "springLength": 150,
                "springConstant": 0.08,
                "damping": 0.4,
                "avoidOverlap": 1,
            },
            "stabilization": {
                "enabled": True,
                "iterations": 120,
                "updateInterval": 25,
            },
        },
    )

    st.markdown("💡 *Tip: Drag nodes to move them. **Click any node** to pivot the graph around that table!*")

    clicked_node = agraph(nodes=nodes, edges=edges, config=config)

    if clicked_node and clicked_node in table_ids and clicked_node != st.session_state.selected_table:
        st.session_state.selected_table = clicked_node
        st.toast(f"Pivoting network graph to **{clicked_node}**...", icon="🔄")
        st.rerun()

    st.markdown("---")

    st.markdown(
        """
        **Graph Legend:** &nbsp;
        <span class="sap-badge sap-badge-orange">🟠 Selected Root</span>
        <span class="sap-badge sap-badge-green">🟢 1-Hop Direct</span>
        <span class="sap-badge sap-badge-blue">🔵 2-Hop Indirect</span>
        <span class="sap-badge sap-badge-grey">⚪ 3-Hop Extended</span>
        """,
        unsafe_allow_html=True
    )

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("📋 Relationship Summary")

    if filtered_edges:
        rel_data = []
        for e in filtered_edges:
            direction = "Outgoing ➡️" if e["source"] == selected else "Incoming ⬅️" if e["target"] == selected else "Indirect 🔗"
            rel_data.append({
                "From Table": e["source"],
                "From Description": SAP_TABLE_DESC.get(e["source"], ""),
                "To Table": e["target"],
                "To Description": SAP_TABLE_DESC.get(e["target"], ""),
                "Via Foreign Key Field": e["via_field"],
                "Relationship Type": direction
            })

        search_query = st.text_input("🔍 Search relationships by table or field name:", "")
        if search_query:
            q = search_query.strip().lower()
            rel_data = [
                row for row in rel_data
                if q in row["From Table"].lower() or
                   q in row["To Table"].lower() or
                   q in row["Via Foreign Key Field"].lower() or
                   q in row["From Description"].lower() or
                   q in row["To Description"].lower()
            ]

        st.dataframe(rel_data, use_container_width=True, hide_index=True)
    else:
        st.info("No relationship edges found for the selected view.")

    direct_neighbors = sorted(adjacency.get(selected, set()))
    with st.expander(f"📌 Direct Neighbors of {selected} ({len(direct_neighbors)} tables)"):
        if direct_neighbors:
            cols = st.columns(4)
            for idx, neighbor in enumerate(direct_neighbors):
                desc = SAP_TABLE_DESC.get(neighbor, "")
                with cols[idx % 4]:
                    if st.button(f"🔗 {neighbor}", key=f"nb_btn_{neighbor}"):
                        st.session_state.selected_table = neighbor
                        st.rerun()
                    if desc:
                        st.caption(desc)
        else:
            st.write("No direct neighbors recorded.")
