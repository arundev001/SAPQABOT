import streamlit as st
import requests
import re
from collections import deque
from streamlit_agraph import agraph, Node, Edge, Config

# ============================================================
# CONFIGURATION
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
# CUSTOM CSS FOR ENTERPRISE STYLE
# ============================================================

st.markdown("""
<style>
    /* Global reset & typography */
    .main {
        padding: 0rem 1rem;
    }
    .block-container {
        padding-top: 0.5rem;
        padding-bottom: 0rem;
    }
    
    /* Enterprise header */
    .app-header {
        background: linear-gradient(135deg, #1a2332 0%, #2c3e50 100%);
        padding: 1.5rem 2rem;
        border-radius: 8px;
        margin-bottom: 1.5rem;
        color: white;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    }
    .app-header h1 {
        margin: 0;
        font-size: 1.8rem;
        font-weight: 600;
        letter-spacing: -0.5px;
    }
    .app-header p {
        margin: 0.3rem 0 0 0;
        opacity: 0.85;
        font-size: 0.95rem;
    }
    
    /* Sidebar styling - enterprise dark */
    section[data-testid="stSidebar"] {
        background-color: #1a2332 !important;
        padding-top: 1rem;
    }
    section[data-testid="stSidebar"] .stMarkdown {
        color: #e8edf2;
    }
    section[data-testid="stSidebar"] h1, 
    section[data-testid="stSidebar"] h2, 
    section[data-testid="stSidebar"] h3 {
        color: #ffffff !important;
        font-weight: 500;
        letter-spacing: 0.3px;
    }
    section[data-testid="stSidebar"] hr {
        border-color: #3d4c5e;
        margin: 1rem 0;
    }
    section[data-testid="stSidebar"] .stSelectbox label,
    section[data-testid="stSidebar"] .stSlider label {
        color: #a0b4c7 !important;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    /* Cards for metrics */
    .metric-card {
        background: white;
        border-radius: 8px;
        padding: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        border: 1px solid #e8ecf0;
        text-align: center;
        transition: all 0.2s;
    }
    .metric-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.12);
        transform: translateY(-2px);
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #1a2332;
        margin: 0.2rem 0;
    }
    .metric-label {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: #6b7a8b;
    }
    
    /* Tab styling - enterprise */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
        background-color: #f5f7fa;
        padding: 0.4rem 0.4rem 0 0.4rem;
        border-radius: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 6px;
        padding: 0.5rem 1.2rem;
        font-weight: 500;
        color: #5a6a7a;
    }
    .stTabs [aria-selected="true"] {
        background-color: #ffffff !important;
        color: #1a2332 !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    }
    
    /* Search box styling */
    .search-box {
        background: white;
        border: 1px solid #e0e5ea;
        border-radius: 6px;
        padding: 0.4rem 0.8rem;
        margin-bottom: 0.5rem;
    }
    .search-box input {
        border: none;
        outline: none;
        width: 100%;
        font-size: 0.9rem;
        padding: 0.3rem 0;
    }
    
    /* Quick starter chips */
    .starter-chip {
        background: #f0f3f7;
        border: 1px solid #e0e5ea;
        border-radius: 20px;
        padding: 0.4rem 1rem;
        font-size: 0.8rem;
        color: #1a2332;
        cursor: pointer;
        transition: all 0.2s;
        display: inline-block;
        margin: 0.2rem 0.2rem;
    }
    .starter-chip:hover {
        background: #e0e8f0;
        border-color: #4a90d9;
        transform: translateY(-1px);
    }
    
    /* Graph container */
    .graph-container {
        background: white;
        border-radius: 8px;
        border: 1px solid #e8ecf0;
        padding: 1rem;
        margin-top: 1rem;
    }
    
    /* Legend with badges */
    .badge {
        display: inline-block;
        padding: 0.2rem 0.7rem;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 500;
        margin: 0.1rem 0.2rem;
    }
    .badge-orange { background: #FF9800; color: white; }
    .badge-green { background: #4CAF50; color: white; }
    .badge-blue { background: #42A5F5; color: white; }
    .badge-grey { background: #9E9E9E; color: white; }
    
    /* Info panel styling */
    .info-panel {
        background: #f8fafc;
        border-radius: 6px;
        padding: 0.8rem 1rem;
        border-left: 3px solid #4a90d9;
        margin: 0.5rem 0;
    }
    
    /* Relationship table container */
    .table-container {
        background: white;
        border-radius: 8px;
        border: 1px solid #e8ecf0;
        padding: 0.5rem;
        overflow: auto;
        max-height: 400px;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# HEADER
# ============================================================

st.markdown("""
<div class="app-header">
    <h1>🏢 SAP Data & Relationship Explorer</h1>
    <p>Intelligent Q&A Assistant & Interactive Table Network Visualizer for SAP S/4HANA</p>
</div>
""", unsafe_allow_html=True)

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
if "pending_table_pivot" not in st.session_state:
    st.session_state.pending_table_pivot = None
if "search_query" not in st.session_state:
    st.session_state.search_query = ""

# ============================================================
# LOAD DATA
# ============================================================

@st.cache_data(ttl=3600)
def load_table_descriptions():
    descriptions = {}
    try:
        resp = requests.get(TABLE_DESC_URL, timeout=10)
        if resp.status_code == 200:
            remote_desc = resp.json()
            if isinstance(remote_desc, dict):
                descriptions.update(remote_desc)
    except Exception:
        pass
    return descriptions

@st.cache_data(ttl=3600)
def load_graph_data():
    try:
        response = requests.get(GRAPH_JSON_URL, timeout=30)
        response.raise_for_status()
        data = response.json()
        if "nodes" not in data or "links" not in data:
            return None
        return data
    except Exception as e:
        st.error(f"Failed to load graph data: {e}")
        return None

SAP_TABLE_DESC = load_table_descriptions()
graph_data = load_graph_data()

if not graph_data:
    st.warning("⚠️ Graph data unavailable. Please check your connection.")
    st.stop()

# ============================================================
# DATA PROCESSING
# ============================================================

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

def extract_sap_tables(text, valid_tables):
    words = set(re.findall(r'\b[A-Z0-9_]{3,8}\b', text.upper()))
    found = [w for w in words if w in valid_tables]
    return sorted(found)

def get_table_label(table_id):
    desc = SAP_TABLE_DESC.get(table_id.upper())
    if desc:
        return f"{table_id} ({desc})"
    return table_id

# ============================================================
# SIDEBAR - ENTERPRISE NAVIGATION
# ============================================================

with st.sidebar:
    st.markdown("### ⚙️ Navigation")
    st.markdown("---")
    
    # System status as cards in sidebar
    st.markdown("#### System Status")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Tables", len(table_ids))
    with col2:
        st.metric("Relationships", len(directed_edges))
    
    st.markdown("---")
    
    # Graph controls
    st.markdown("#### Graph Settings")
    
    # Quick search for tables
    st.session_state.search_query = st.text_input(
        "🔍 Quick Table Search",
        placeholder="Type table name...",
        value=st.session_state.search_query
    )
    
    if st.session_state.search_query:
        filtered_tables = [t for t in table_ids if st.session_state.search_query.upper() in t.upper()]
        if filtered_tables:
            with st.expander(f"Results ({len(filtered_tables)})"):
                for t in filtered_tables[:10]:
                    desc = SAP_TABLE_DESC.get(t, "")
                    display = f"{t} - {desc}" if desc else t
                    if st.button(display, key=f"quick_{t}"):
                        st.session_state.selected_table = t
                        st.rerun()
    
    st.markdown("---")
    
    # Depth and limit controls
    st.session_state.depth = st.selectbox(
        "🔄 Relationship Depth",
        options=[1, 2, 3],
        format_func=lambda v: f"{v} Hop{'s' if v > 1 else ''}",
        key="depth_sidebar"
    )
    
    st.session_state.max_nodes = st.slider(
        "📊 Max Nodes",
        min_value=25,
        max_value=150,
        value=st.session_state.max_nodes,
        step=25,
        key="max_nodes_sidebar"
    )
    
    st.session_state.physics_enabled = st.toggle(
        "🎯 Enable Physics",
        value=st.session_state.physics_enabled,
        key="physics_sidebar"
    )
    
    st.markdown("---")
    
    # Quick actions
    st.markdown("#### Actions")
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.history = []
        st.toast("Chat cleared!")
        st.rerun()
    
    st.markdown("---")
    
    # Legend
    st.markdown("#### Legend")
    st.markdown("""
    <span class="badge badge-orange">Selected</span>
    <span class="badge badge-green">1-Hop</span>
    <span class="badge badge-blue">2-Hop</span>
    <span class="badge badge-grey">3-Hop</span>
    """, unsafe_allow_html=True)

# ============================================================
# MAIN CONTENT - TABS
# ============================================================

tab_chat, tab_graph, tab_browse = st.tabs([
    "💬 Chat Assistant", 
    "🔗 Relationship Explorer",
    "📋 Table Browser"
])

# ============================================================
# TAB 1: CHAT ASSISTANT
# ============================================================

with tab_chat:
    st.markdown("### 🤖 Ask Questions About SAP Data")
    
    # Quick starter prompts as chips
    st.markdown("#### Quick Start Prompts")
    starters = [
        ("🛒 Purchase Orders", "Which SAP tables link Purchase Order headers to line items?"),
        ("📦 Material Master", "Explain how MARA, MARC, and MARD are linked."),
        ("💰 Sales & Billing", "How are Sales Documents and Billing Documents connected?"),
        ("🏦 Finance", "What are the core tables for Accounting documents?"),
        ("🏭 Plant & Valuation", "How does Plant relate to Valuation Areas?"),
        ("🚚 Logistics", "Which tables store Delivery Headers and Items?")
    ]
    
    cols = st.columns(3)
    for idx, (label, prompt_text) in enumerate(starters):
        with cols[idx % 3]:
            if st.button(label, key=f"start_{idx}", use_container_width=True):
                st.session_state.pending_question = prompt_text
    
    st.markdown("---")
    
    # Chat history
    for role, message in st.session_state.history:
        with st.chat_message(role):
            st.markdown(message)
            if role == "assistant":
                referenced = extract_sap_tables(message, set(table_ids))
                if referenced:
                    st.caption("🔍 **Referenced Tables:**")
                    btn_cols = st.columns(min(len(referenced), 4))
                    for i, tbl in enumerate(referenced[:4]):
                        with btn_cols[i]:
                            if st.button(f"🔗 {tbl}", key=f"hist_{tbl}_{i}"):
                                st.session_state.selected_table = tbl
                                st.toast(f"Switched to {tbl} in Graph Explorer")
                                st.rerun()
    
    # Chat input
    chat_input = st.chat_input("Ask a question about your SAP data...")
    question = chat_input or st.session_state.pending_question
    
    if question:
        st.session_state.pending_question = None
        st.session_state.history.append(("user", question))
        
        with st.chat_message("user"):
            st.markdown(question)
        
        with st.chat_message("assistant"):
            with st.spinner("Analyzing SAP schema..."):
                try:
                    response = requests.post(
                        LAMBDA_URL,
                        json={"question": question},
                        timeout=100,
                    )
                    response.raise_for_status()
                    data = response.json()
                    answer = data.get("answer") or "No response received."
                except Exception as e:
                    answer = f"⚠️ Error: {e}"
            
            st.markdown(answer)
            st.session_state.history.append(("assistant", answer))
            
            referenced_tables = extract_sap_tables(answer, set(table_ids))
            if referenced_tables:
                st.caption("🔍 **Explore these tables:**")
                btn_cols = st.columns(min(len(referenced_tables), 4))
                for i, tbl in enumerate(referenced_tables[:4]):
                    with btn_cols[i]:
                        if st.button(f"🔗 {tbl}", key=f"new_{tbl}_{i}"):
                            st.session_state.selected_table = tbl
                            st.toast(f"Switched to {tbl}")
                            st.rerun()

# ============================================================
# TAB 2: RELATIONSHIP EXPLORER
# ============================================================

with tab_graph:
    st.markdown("### 🔗 SAP Table Relationship Network")
    
    # Table selector
    selected = st.selectbox(
        "**Select a Table**",
        options=table_ids,
        format_func=get_table_label,
        key="selected_table"
    )
    
    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Selected Table</div>
            <div class="metric-value">{selected}</div>
            <div style="font-size:0.8rem;color:#6b7a8b;">{SAP_TABLE_DESC.get(selected, '')}</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Get connected tables
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
    
    table_depths = get_connected_tables(selected, adjacency, st.session_state.depth)
    sorted_tables = sorted(table_depths.items(), key=lambda x: (x[1], x[0]))
    
    limited = len(sorted_tables) > st.session_state.max_nodes
    if limited:
        sorted_tables = sorted_tables[:st.session_state.max_nodes]
    
    visible_tables = {t for t, _ in sorted_tables}
    visible_tables.add(selected)
    visible_depths = {t: table_depths.get(t, 0) for t in visible_tables}
    
    filtered_edges = [
        e for e in directed_edges
        if e["source"] in visible_tables and e["target"] in visible_tables
    ]
    
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Connected Tables</div>
            <div class="metric-value">{len(visible_tables)}</div>
            <div style="font-size:0.8rem;color:#6b7a8b;">Depth: {st.session_state.depth} hop{'s' if st.session_state.depth > 1 else ''}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Relationships</div>
            <div class="metric-value">{len(filtered_edges)}</div>
            <div style="font-size:0.8rem;color:#6b7a8b;">Direct & Indirect</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Max Nodes</div>
            <div class="metric-value">{st.session_state.max_nodes}</div>
            <div style="font-size:0.8rem;color:#6b7a8b;">
                {'⚠️ Limited' if limited else '✓ All displayed'}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    if limited:
        st.warning(f"⚠️ Display limited to {st.session_state.max_nodes} nodes. Increase 'Max Nodes' in sidebar.")
    
    # Graph
    st.markdown('<div class="graph-container">', unsafe_allow_html=True)
    
    nodes = []
    for table in sorted(visible_tables):
        table_depth = visible_depths.get(table, 0)
        table_desc = SAP_TABLE_DESC.get(table, "")
        node_label = f"{table}\n({table_desc})" if table_desc else table
        
        if table == selected:
            color = "#FF9800"
            size = 38
        elif table_depth == 1:
            color = "#4CAF50"
            size = 28
        elif table_depth == 2:
            color = "#42A5F5"
            size = 22
        else:
            color = "#9E9E9E"
            size = 18
        
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
        height=600,
        directed=True,
        physics=st.session_state.physics_enabled,
        hierarchical=False,
        nodeHighlightBehavior=True,
        highlightColor="#FFD54F",
        collapsible=False,
    )
    
    st.markdown("💡 **Tip:** Click any node to pivot the graph around that table. Drag nodes to rearrange.")
    
    clicked_node = agraph(nodes=nodes, edges=edges, config=config)
    
    if clicked_node and clicked_node in table_ids and clicked_node != st.session_state.selected_table:
        st.session_state.pending_table_pivot = clicked_node
        st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Relationship summary
    st.markdown("---")
    st.markdown("### 📋 Relationship Details")
    
    if filtered_edges:
        rel_data = []
        for e in filtered_edges:
            direction = "Outgoing" if e["source"] == selected else "Incoming" if e["target"] == selected else "Indirect"
            rel_data.append({
                "From": e["source"],
                "From Desc": SAP_TABLE_DESC.get(e["source"], ""),
                "To": e["target"],
                "To Desc": SAP_TABLE_DESC.get(e["target"], ""),
                "Via Field": e["via_field"],
                "Direction": direction
            })
        
        search = st.text_input("🔍 Search relationships", placeholder="Filter by table or field...")
        if search:
            search_lower = search.lower()
            rel_data = [r for r in rel_data if 
                       search_lower in r["From"].lower() or 
                       search_lower in r["To"].lower() or 
                       search_lower in r["Via Field"].lower() or
                       search_lower in r["From Desc"].lower() or
                       search_lower in r["To Desc"].lower()]
        
        st.dataframe(rel_data, use_container_width=True, hide_index=True)
    else:
        st.info("No relationships found in the filtered view.")

# ============================================================
# TAB 3: TABLE BROWSER
# ============================================================

with tab_browse:
    st.markdown("### 📋 SAP Table Browser")
    st.caption("Browse all SAP tables with descriptions and search functionality")
    
    # Search
    browse_search = st.text_input("🔍 Search tables by ID or description", placeholder="Type table name...")
    
    # Get all tables with descriptions
    table_list = []
    for tid in table_ids:
        desc = SAP_TABLE_DESC.get(tid, "")
        table_list.append({
            "Table ID": tid,
            "Description": desc,
            "Module": "Unknown"  # You could add module detection based on prefix
        })
    
    # Filter
    if browse_search:
        search_lower = browse_search.lower()
        table_list = [t for t in table_list if 
                     search_lower in t["Table ID"].lower() or 
                     search_lower in t["Description"].lower()]
    
    # Display
    st.dataframe(table_list, use_container_width=True, hide_index=True)
    
    # Quick explore
    st.markdown("#### Quick Explore")
    if table_list:
        selected_browse = st.selectbox(
            "Select a table to explore in graph",
            options=[t["Table ID"] for t in table_list[:50]]
        )
        if st.button("Explore in Graph", use_container_width=True):
            st.session_state.selected_table = selected_browse
            st.toast(f"Switched to {selected_browse} in Graph Explorer")
            st.rerun()
