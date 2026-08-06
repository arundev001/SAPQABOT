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
TABLE_DESC_URL = st.secrets.get(
    "TABLE_DESC_URL",
    "https://graphdbarun.s3.us-east-1.amazonaws.com/table_descriptions.json"
)

# ============================================================
# FALLBACK SAP STANDARD TABLE DESCRIPTIONS & MODULE MAPPINGS
# ============================================================

FALLBACK_SAP_TABLE_DESC = {
    "EKKO": ("Purchasing Document Header", "Procurement"),
    "EKPO": ("Purchasing Document Item", "Procurement"),
    "EBAN": ("Purchase Requisition", "Procurement"),
    "EINA": ("Purchase Info Record General", "Procurement"),
    "EINE": ("Purchase Info Record Purchasing", "Procurement"),
    "MARA": ("General Material Data", "Material Master"),
    "MARC": ("Plant Data for Material", "Material Master"),
    "MARD": ("Storage Location Data for Material", "Material Master"),
    "MAKT": ("Material Descriptions", "Material Master"),
    "MBEW": ("Material Valuation", "Material Master"),
    "VBAK": ("Sales Document Header Data", "Sales & Distribution"),
    "VBAP": ("Sales Document Item Data", "Sales & Distribution"),
    "VBRK": ("Billing Document Header", "Sales & Distribution"),
    "VBRP": ("Billing Document Item", "Sales & Distribution"),
    "LIKP": ("SD Document Delivery Header", "Sales & Distribution"),
    "LIPS": ("SD Document Delivery Item", "Sales & Distribution"),
    "BKPF": ("Accounting Document Header", "Finance & Accounting"),
    "BSEG": ("Accounting Document Segment", "Finance & Accounting"),
    "KNA1": ("Customer Master General Data", "Sales & Distribution"),
    "LFA1": ("Vendor Master General Data", "Procurement"),
    "T001": ("Company Codes", "Enterprise Structure"),
    "T001W": ("Plants / Branches", "Enterprise Structure"),
    "T001K": ("Valuation Areas", "Enterprise Structure"),
    "T001L": ("Storage Locations", "Enterprise Structure"),
    "T024": ("Purchasing Groups", "Procurement"),
    "T024E": ("Purchasing Organizations", "Procurement"),
    "TVKO": ("Sales Organizations", "Sales & Distribution"),
    "RESB": ("Reservation / Dependent Requirements", "Material Master"),
    "MKPF": ("Header Material Document", "Material Master"),
    "MSEG": ("Document Segment Material", "Material Master"),
}

# Normalize description dict
SAP_TABLE_DESC = {}
SAP_TABLE_MODULE = {}
for k, v in FALLBACK_SAP_TABLE_DESC.items():
    if isinstance(v, tuple):
        SAP_TABLE_DESC[k] = v[0]
        SAP_TABLE_MODULE[k] = v[1]
    else:
        SAP_TABLE_DESC[k] = v
        SAP_TABLE_MODULE[k] = "General SAP"

# ============================================================
# PAGE CONFIG & SAP SIGNAVIO / PROCESSFX THEME STYLING
# ============================================================

st.set_page_config(
    page_title="SAP Signavio | ProcessFx Explorer",
    page_icon="🔷",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Signavio / ProcessFx CSS
st.markdown(
    """
    <style>
        .block-container {
            padding-top: 1rem;
            padding-bottom: 2rem;
            max-width: 98%;
        }
        .signavio-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: #FFFFFF;
            border-bottom: 1px solid #E2E8F0;
            padding: 10px 20px;
            border-radius: 8px;
            margin-bottom: 15px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }
        .signavio-logo {
            font-size: 1.3rem;
            font-weight: 700;
            color: #0B192C;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .signavio-badge {
            background-color: #EBF5FF;
            color: #0070F2;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 600;
            border: 1px solid #BEE3F8;
        }
        section[data-testid="stSidebar"] {
            background-color: #F8FAFC;
            border-right: 1px solid #E2E8F0;
        }
        .inspector-box {
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 10px;
            padding: 16px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.04);
        }
        .inspector-title {
            font-size: 1.15rem;
            font-weight: 700;
            color: #1E293B;
            margin-bottom: 4px;
        }
        .inspector-subtitle {
            font-size: 0.85rem;
            color: #64748B;
            margin-bottom: 12px;
        }
        .legend-card {
            background: rgba(255, 255, 255, 0.9);
            border: 1px solid #E2E8F0;
            backdrop-filter: blur(8px);
            border-radius: 8px;
            padding: 10px;
            font-size: 0.8rem;
        }
        .sap-badge {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 0.78rem;
            margin-right: 4px;
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
# DYNAMIC METADATA LOADING
# ============================================================

@st.cache_data(ttl=3600)
def load_table_descriptions():
    descriptions = dict(SAP_TABLE_DESC)
    if TABLE_DESC_URL:
        try:
            resp = requests.get(TABLE_DESC_URL, timeout=10)
            if resp.status_code == 200:
                remote_desc = resp.json()
                if isinstance(remote_desc, dict):
                    descriptions.update(remote_desc)
        except Exception:
            pass
    return descriptions

SAP_TABLE_DESC = load_table_descriptions()

def get_table_label(table_id):
    desc = SAP_TABLE_DESC.get(table_id.upper())
    if desc:
        return f"{table_id} ({desc})"
    return table_id

# ============================================================
# SESSION STATE INITIALISATION
# ============================================================

if "history" not in st.session_state:
    st.session_state.history = []

if "selected_table" not in st.session_state:
    st.session_state.selected_table = None

if "pending_table_pivot" not in st.session_state:
    st.session_state.pending_table_pivot = None

if "depth" not in st.session_state:
    st.session_state.depth = 1

if "max_nodes" not in st.session_state:
    st.session_state.max_nodes = 50

if "layout_mode" not in st.session_state:
    st.session_state.layout_mode = "Force Cluster Network"

if "physics_enabled" not in st.session_state:
    st.session_state.physics_enabled = True

if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

# Process deferred pivot updates before widgets are instantiated
if st.session_state.pending_table_pivot:
    st.session_state.selected_table = st.session_state.pending_table_pivot
    st.session_state.pending_table_pivot = None

# ============================================================
# SAP SIGNAVIO TOP BRANDING HEADER
# ============================================================

st.markdown(
    """
    <div class="signavio-header">
        <div class="signavio-logo">
            <span>🔷 SAP Signavio</span>
            <span style="color:#64748B; font-weight:400;">|</span>
            <span style="color:#0070F2;">ProcessFx Explorer</span>
            <span class="signavio-badge">v2.5 Enterprise</span>
        </div>
        <div style="font-size: 0.85rem; color: #64748B;">
            🔍 Structural Architecture & Process Atom Inspector
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

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

for node in raw_nodes:
    n_id = node.get("id")
    n_desc = node.get("description") or node.get("label")
    if n_id and n_desc and n_id.upper() not in SAP_TABLE_DESC:
        SAP_TABLE_DESC[n_id.upper()] = n_desc

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
# PROCESSFX SIDEBAR NAVIGATION & CONTROLS
# ============================================================

with st.sidebar:
    st.markdown("### 📂 ProcessFx Menu")
    
    st.markdown("**ENTERPRISE STRUCTURE**")
    st.caption("🏢 Controlling Area, Company Codes, Orgs")
    
    st.markdown("**BUSINESS PROCESS**")
    st.caption("🔄 End-to-end Functional Workflow")

    st.markdown("---")
    st.subheader("⚙️ Visualizer Settings")
    
    layout_selection = st.radio(
        "Graph Layout Mode",
        options=["Force Cluster Network", "Hierarchical Mind-Map"],
        index=0 if st.session_state.layout_mode == "Force Cluster Network" else 1,
        key="layout_mode"
    )
    
    st.markdown("---")
    st.subheader("System Connectivity")
    st.success("🟢 Signavio Data Connected")
    st.info(f"📊 Total Tables: **{len(table_ids)}**")
    st.info(f"🔗 Total Edges: **{len(directed_edges)}**")

    st.markdown("---")
    if st.button("🗑️ Clear Conversation", use_container_width=True):
        st.session_state.history = []
        st.toast("Conversation cleared!", icon="🧹")
        st.rerun()

# ============================================================
# TABS
# ============================================================

tab_graph, tab_chat = st.tabs(["🌐 Signavio Process Atom Explorer", "💬 AI Assistant"])

# ============================================================
# TAB 1: SIGNAVIO / PROCESSFX EXPLORER
# ============================================================

with tab_graph:
    st.markdown("💡 **Filter by Domain Module:**")
    m_cols = st.columns(5)
    domain_filters = [
        ("🛒 Procurement", "EKKO"),
        ("📦 Material Master", "MARA"),
        ("💰 Sales & Distribution", "VBAK"),
        ("🏦 Financial Accounting", "BKPF"),
        ("🏭 Plant & Storage", "T001W")
    ]
    for idx, (label, table_code) in enumerate(domain_filters):
        with m_cols[idx]:
            if st.button(label, key=f"dom_filter_{idx}", use_container_width=True):
                if table_code in table_ids:
                    st.session_state.pending_table_pivot = table_code
                    st.rerun()

    st.markdown("---")

    canvas_col, inspector_col = st.columns([8, 4])

    with canvas_col:
        col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
        with col1:
            selected = st.selectbox(
                "Search Node (ID / Name)",
                options=table_ids,
                format_func=get_table_label,
                key="selected_table"
            )
        with col2:
            depth = st.selectbox(
                "Depth",
                options=[1, 2, 3],
                format_func=lambda v: f"{v} Hop" if v == 1 else f"{v} Hops",
                key="depth"
            )
        with col3:
            max_nodes = st.selectbox(
                "Max Tables",
                options=[25, 50, 75, 100],
                key="max_nodes"
            )
        with col4:
            physics_on = st.toggle("Physics", value=st.session_state.physics_enabled, key="physics_enabled")

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

        nodes = []
        for table in sorted(visible_tables):
            table_depth = visible_depths.get(table, 0)
            table_desc = SAP_TABLE_DESC.get(table, "")
            node_label = f"{table}\n({table_desc})" if table_desc else table
            
            if table == selected:
                color = "#0070F2" if st.session_state.layout_mode == "Hierarchical Mind-Map" else "#FF9800"
                size = 36
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

        is_hierarchical = (st.session_state.layout_mode == "Hierarchical Mind-Map")
        config = Config(
            width="100%",
            height=620,
            directed=True,
            physics=physics_on if not is_hierarchical else False,
            hierarchical=is_hierarchical,
            nodeHighlightBehavior=True,
            highlightColor="#FFD54F",
            collapsible=False
        )

        st.caption("💡 Drag nodes to re-position. **Click any node** to inspect details in the right drawer.")

        clicked_node = agraph(nodes=nodes, edges=edges, config=config)

        if clicked_node and clicked_node in table_ids and clicked_node != st.session_state.selected_table:
            st.session_state.pending_table_pivot = clicked_node
            st.toast(f"Inspecting **{clicked_node}**...", icon="🔄")
            st.rerun()

        st.markdown(
            """
            <div class="legend-card">
                <b>Legend:</b> &nbsp;
                <span class="sap-badge sap-badge-orange">🟠 Selected Root</span>
                <span class="sap-badge sap-badge-green">🟢 1-Hop Direct</span>
                <span class="sap-badge sap-badge-blue">🔵 2-Hop Indirect</span>
                <span class="sap-badge sap-badge-grey">⚪ 3-Hop Extended</span>
            </div>
            """,
            unsafe_allow_html=True
        )

    # RIGHT DRAWER: PROCESS ATOM INSPECTOR
    with inspector_col:
        st.markdown("### ⚛️ Process Atom Inspector")
        sel_desc = SAP_TABLE_DESC.get(selected, "SAP Business Table")
        sel_module = SAP_TABLE_MODULE.get(selected, "Enterprise Data")

        st.markdown(
            f"""
            <div class="inspector-box">
                <div class="inspector-title">{selected}</div>
                <div class="inspector-subtitle">{sel_desc}</div>
                <div><span class="signavio-badge">{sel_module}</span></div>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown("---")
        st.subheader("General Information")
        st.write(f"**Table Name:** `{selected}`")
        st.write(f"**Functional Description:** {sel_desc}")
        st.write(f"**SAP Sub-Module:** {sel_module}")
        st.write(f"**Network Hop Distance:** Root Selected")

        st.markdown("---")
        st.subheader("Technical Reference")
        st.code(f"doc-table-{selected.lower()}", language="text")

        st.markdown("---")
        st.subheader("Actions")
        act_col1, act_col2 = st.columns(2)
        with act_col1:
            if st.button("💬 Ask AI", use_container_width=True):
                st.session_state.pending_question = f"Explain the structure, fields, and business purpose of SAP table {selected} ({sel_desc})."
                st.toast(f"Switched to AI Assistant to analyze {selected}!", icon="🤖")
        with act_col2:
            if st.button("🔗 Re-Center", use_container_width=True):
                st.session_state.pending_table_pivot = selected
                st.rerun()

        st.markdown("---")
        st.subheader("Connected Neighbors")
        neighbors = sorted(adjacency.get(selected, set()))
        if neighbors:
            for nb in neighbors[:8]:
                nb_desc = SAP_TABLE_DESC.get(nb, "")
                btn_label = f"🔗 {nb} - {nb_desc}" if nb_desc else f"🔗 {nb}"
                if st.button(btn_label, key=f"insp_nb_{nb}"):
                    st.session_state.pending_table_pivot = nb
                    st.rerun()
        else:
            st.info("No direct neighbors recorded.")

    st.markdown("---")
    st.subheader("📋 Structural Relationship Summary")

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

# ============================================================
# TAB 2: AI ASSISTANT
# ============================================================

with tab_chat:
    st.subheader("🤖 Ask Questions About SAP Data & Schema")
    st.caption("Natural language Q&A interface linked to Signavio Process Atom Inspector.")

    for msg_idx, (role, message) in enumerate(st.session_state.history):
        with st.chat_message(role):
            st.markdown(message)
            if role == "assistant":
                referenced = extract_sap_tables(message, set(table_ids))
                if referenced:
                    st.caption("🔍 **Referenced SAP Tables (Click to inspect in Signavio):**")
                    btn_cols = st.columns(min(len(referenced), 6))
                    for i, tbl in enumerate(referenced[:6]):
                        with btn_cols[i]:
                            if st.button(f"🔗 {tbl}", key=f"hist_btn_{tbl}_{i}_{msg_idx}"):
                                st.session_state.pending_table_pivot = tbl
                                st.toast(f"Inspecting **{tbl}** in Signavio Explorer!", icon="🚀")

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
                st.caption("🔍 **Explore referenced SAP tables in Signavio Explorer:**")
                cols = st.columns(min(len(referenced_tables), 6))
                for idx, tbl in enumerate(referenced_tables[:6]):
                    with cols[idx]:
                        if st.button(f"🔗 {tbl}", key=f"new_btn_{tbl}_{idx}"):
                            st.session_state.pending_table_pivot = tbl
                            st.toast(f"Selected table set to **{tbl}**. Switch to 'Signavio Explorer' tab!", icon="🚀")
