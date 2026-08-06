import streamlit as st
import requests
import re
import json
import io
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
# SAP STANDARD TABLE DESCRIPTIONS + CATEGORY (ENRICHMENT LOOKUP)
# ============================================================
# Each table now maps to (description, category). Category drives
# node color and the "Active Data Toggles" filter checkboxes,
# mirroring the ProcessFx Enterprise Organizational Hierarchy view.

SAP_TABLE_INFO = {
    "EKKO": ("Purchasing Document Header", "Purchasing"),
    "EKPO": ("Purchasing Document Item", "Purchasing"),
    "EINA": ("Purchase Info Record General Data", "Purchasing"),
    "EINE": ("Purchase Info Record Purchasing Data", "Purchasing"),
    "EBAN": ("Purchase Requisition", "Purchasing"),
    "T024": ("Purchasing Groups", "Purchasing"),
    "T024E": ("Purchasing Organizations", "Purchasing"),

    "MARA": ("General Material Data", "Material"),
    "MARC": ("Plant Data for Material", "Material"),
    "MARD": ("Storage Location Data for Material", "Material"),
    "MAKT": ("Material Descriptions", "Material"),
    "MBEW": ("Material Valuation", "Material"),
    "RESB": ("Reservation / Dependent Requirements", "Material"),
    "MKPF": ("Header Material Document", "Material"),
    "MSEG": ("Document Segment Material", "Material"),

    "VBAK": ("Sales Document Header Data", "Sales"),
    "VBAP": ("Sales Document Item Data", "Sales"),
    "VBRK": ("Billing Document Header", "Sales"),
    "VBRP": ("Billing Document Item", "Sales"),
    "LIKP": ("SD Document Delivery Header", "Sales"),
    "LIPS": ("SD Document Delivery Item", "Sales"),
    "TVKO": ("Sales Organizations", "Sales"),

    "BKPF": ("Accounting Document Header", "Finance"),
    "BSEG": ("Accounting Document Segment", "Finance"),

    "KNA1": ("Customer Master General Data", "Master Data"),
    "LFA1": ("Vendor Master General Data", "Master Data"),

    "T001": ("Company Codes", "Organization"),
    "T001W": ("Plants / Branches", "Organization"),
    "T001L": ("Storage Locations", "Organization"),
}

# Fallback for any table present in the graph JSON but not in the lookup above.
DEFAULT_CATEGORY = "Other"

CATEGORY_COLORS = {
    "Purchasing": "#FF9800",
    "Material": "#4CAF50",
    "Sales": "#E91E63",
    "Finance": "#9C27B0",
    "Master Data": "#00BCD4",
    "Organization": "#3F51B5",
    "Other": "#9E9E9E",
}

ROOT_COLOR = "#212121"


def get_table_desc(table_id):
    info = SAP_TABLE_INFO.get(table_id.upper())
    return info[0] if info else ""


def get_table_category(table_id):
    info = SAP_TABLE_INFO.get(table_id.upper())
    return info[1] if info else DEFAULT_CATEGORY


def get_table_label(table_id):
    desc = get_table_desc(table_id)
    if desc:
        return f"{table_id} ({desc})"
    return table_id


# ============================================================
# PAGE CONFIG & ENTERPRISE STYLING
# ============================================================

st.set_page_config(
    page_title="SAP Structural Tree Explorer",
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
        /* Floating legend box, positioned like the bottom-left legend
           in the ProcessFx tree explorer screenshot. */
        .floating-legend {
            position: relative;
            margin-top: -80px;
            margin-left: 8px;
            width: fit-content;
            background: white;
            border: 1px solid rgba(0,0,0,0.12);
            border-radius: 10px;
            padding: 12px 16px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08);
            z-index: 999;
        }
        .floating-legend .legend-row {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 4px;
            font-size: 0.85rem;
        }
        .legend-swatch {
            width: 12px;
            height: 12px;
            border-radius: 3px;
            display: inline-block;
        }
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

if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

if "active_categories" not in st.session_state:
    # All categories start enabled except "Other", mirroring the
    # ProcessFx screenshot where only a couple of toggles are checked
    # by default (Warehouses, Sales Channels).
    st.session_state.active_categories = set(CATEGORY_COLORS.keys()) - {"Other"}

# ============================================================
# HEADER
# ============================================================

st.title("💬 SAP Data & Relationship Explorer")
st.caption("Intelligent Q&A Assistant and Interactive SAP Structural Tree Explorer.")

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

tab_chat, tab_graph = st.tabs(["💬 Chat Assistant", "🔗 Structural Tree Explorer"])

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
                                st.toast(f"Pivoted Graph to **{tbl}**! Switch to '🔗 Structural Tree Explorer' tab.", icon="🚀")

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
                st.caption("🔍 **Explore referenced SAP tables in Structural Tree Explorer:**")
                cols = st.columns(min(len(referenced_tables), 6))
                for idx, tbl in enumerate(referenced_tables[:6]):
                    with cols[idx]:
                        if st.button(f"🔗 {tbl}", key=f"new_btn_{tbl}_{idx}"):
                            st.session_state.selected_table = tbl
                            st.toast(f"Selected table set to **{tbl}**. Switch to '🔗 Structural Tree Explorer' tab!", icon="🚀")

# ============================================================
# TAB 2: STRUCTURAL TREE EXPLORER
# ============================================================

with tab_graph:
    st.subheader("🌳 SAP Structural Tree Explorer")
    st.caption("Search / Select SAP Table — auto-analyze structural relationships by data layer.")

    # --------------------------------------------------------
    # TOP BAR: search box + root dropdown + JSON/PNG export
    # --------------------------------------------------------
    top1, top2, top3, top4 = st.columns([3, 2, 1, 1])

    with top1:
        search_text = st.text_input(
            "Search node (ID / Name)",
            value="",
            placeholder="Search node (ID / Name)",
            label_visibility="collapsed",
        )

    with top2:
        # If the search box matches a table, jump the dropdown to it.
        default_index = table_ids.index(st.session_state.selected_table) if st.session_state.selected_table in table_ids else 0
        if search_text:
            matches = [t for t in table_ids if search_text.upper() in t.upper() or search_text.lower() in get_table_desc(t).lower()]
            if matches:
                default_index = table_ids.index(matches[0])

        selected = st.selectbox(
            "Root Table",
            options=table_ids,
            index=default_index,
            format_func=get_table_label,
            label_visibility="collapsed",
        )
        st.session_state.selected_table = selected

    with top3:
        json_bytes = json.dumps(graph_data, indent=2).encode("utf-8")
        st.download_button(
            "⬇ JSON",
            data=json_bytes,
            file_name="sap_graph_d3.json",
            mime="application/json",
            use_container_width=True,
        )

    with top4:
        export_png_clicked = st.button("⬇ PNG", use_container_width=True)

    st.markdown("---")

    # --------------------------------------------------------
    # ACTIVE DATA TOGGLES (category checkboxes, replaces
    # the old depth / max-nodes selectboxes)
    # --------------------------------------------------------
    st.markdown("**Active Data Toggles:**")
    toggle_cols = st.columns(len(CATEGORY_COLORS))
    for i, (cat, color) in enumerate(CATEGORY_COLORS.items()):
        with toggle_cols[i]:
            checked = st.checkbox(
                cat,
                value=cat in st.session_state.active_categories,
                key=f"toggle_{cat}",
            )
            if checked:
                st.session_state.active_categories.add(cat)
            else:
                st.session_state.active_categories.discard(cat)

    physics_on = st.toggle("Enable Physics (force layout instead of tree)", value=False)

    active_categories = st.session_state.active_categories

    # --------------------------------------------------------
    # TRAVERSAL — unlimited-depth BFS, then filtered by which
    # data-layer toggles are active (instead of a hop-depth cap)
    # --------------------------------------------------------
    def get_connected_tables(start, adj):
        visited = {start: 0}
        queue = deque([(start, 0)])
        while queue:
            current, d = queue.popleft()
            for neighbor in adj.get(current, set()):
                if neighbor not in visited:
                    nd = d + 1
                    visited[neighbor] = nd
                    queue.append((neighbor, nd))
        return visited

    table_depths = get_connected_tables(selected, adjacency)

    visible_tables = {
        t for t in table_depths
        if get_table_category(t) in active_categories
    }
    visible_tables.add(selected)  # root always visible regardless of its own category
    visible_depths = {t: table_depths.get(t, 0) for t in visible_tables}

    filtered_edges = [
        e for e in directed_edges
        if e["source"] in visible_tables and e["target"] in visible_tables
    ]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Selected Root Table", selected, delta=get_table_desc(selected))
    m2.metric("Visible Tables", len(visible_tables))
    m3.metric("Relationships Found", len(filtered_edges))
    m4.metric("Active Layers", f"{len(active_categories)} / {len(CATEGORY_COLORS)}")

    # --------------------------------------------------------
    # BUILD NODES — colored by category (not hop-distance),
    # rounded-rect "box" shape with a two-line label (ID + desc)
    # --------------------------------------------------------
    nodes = []
    for table in sorted(visible_tables):
        table_desc = get_table_desc(table)
        table_cat = get_table_category(table)
        node_label = f"{table}\n{table_desc}" if table_desc else table

        if table == selected:
            color = ROOT_COLOR
            size = 32
        else:
            color = CATEGORY_COLORS.get(table_cat, CATEGORY_COLORS["Other"])
            size = 22

        nodes.append(Node(
            id=table,
            label=node_label,
            size=size,
            color=color,
            shape="box",
        ))

    edges = []
    for edge in filtered_edges:
        edges.append(Edge(
            source=edge["source"],
            target=edge["target"],
            label=edge["via_field"],
        ))

    # --------------------------------------------------------
    # HIERARCHICAL TOP-DOWN TREE CONFIG (mirrors the
    # Controlling Area -> Company Code -> Plant/Sales Org tree)
    # --------------------------------------------------------
    config = Config(
        width="100%",
        height=650,
        directed=True,
        physics=physics_on,
        hierarchical=not physics_on,
        hierarchical_sort_method="directed",
        direction="UD",
        nodeHighlightBehavior=True,
        highlightColor="#FFD54F",
        collapsible=False,
        node={"labelProperty": "label", "font": {"multi": True, "align": "left"}},
    )

    st.markdown("💡 *Tip: Drag nodes to move them. **Click any node** to pivot the tree around that table! Use scroll / pinch to zoom.*")

    clicked_node = agraph(nodes=nodes, edges=edges, config=config)

    if clicked_node and clicked_node in table_ids and clicked_node != st.session_state.selected_table:
        st.session_state.selected_table = clicked_node
        st.toast(f"Pivoting tree to **{clicked_node}**...", icon="🔄")
        st.rerun()

    # --------------------------------------------------------
    # PNG EXPORT — client-side agraph has no native snapshot
    # API, so we render a static matplotlib snapshot of the
    # current filtered view as a downloadable PNG fallback.
    # --------------------------------------------------------
    if export_png_clicked:
        try:
            import matplotlib.pyplot as plt
            import networkx as nx

            G = nx.DiGraph()
            for t in visible_tables:
                G.add_node(t)
            for e in filtered_edges:
                G.add_edge(e["source"], e["target"], label=e["via_field"])

            pos = nx.spring_layout(G, seed=42, k=0.9)
            fig, ax = plt.subplots(figsize=(12, 8))
            node_colors = [
                ROOT_COLOR if n == selected else CATEGORY_COLORS.get(get_table_category(n), CATEGORY_COLORS["Other"])
                for n in G.nodes
            ]
            nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=900, ax=ax)
            nx.draw_networkx_labels(G, pos, font_size=8, font_color="white", ax=ax)
            nx.draw_networkx_edges(G, pos, arrows=True, ax=ax)
            edge_labels = nx.get_edge_attributes(G, "label")
            nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=7, ax=ax)
            ax.set_title(f"SAP Structural Tree — Root: {selected}")
            ax.axis("off")

            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
            plt.close(fig)
            buf.seek(0)

            st.download_button(
                "📥 Download tree_snapshot.png",
                data=buf,
                file_name="tree_snapshot.png",
                mime="image/png",
            )
        except Exception as e:
            st.error(f"Could not generate PNG snapshot: {e}")

    # --------------------------------------------------------
    # FLOATING LEGEND (bottom-left, like the ProcessFx screenshot)
    # --------------------------------------------------------
    legend_rows = "".join(
        f'<div class="legend-row"><span class="legend-swatch" style="background:{color};"></span>{cat}</div>'
        for cat, color in CATEGORY_COLORS.items()
    )
    st.markdown(
        f"""
        <div class="floating-legend">
            <div class="legend-row"><span class="legend-swatch" style="background:{ROOT_COLOR};"></span><b>Selected Root</b></div>
            {legend_rows}
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.subheader("📋 Relationship Summary")

    if filtered_edges:
        rel_data = []
        for e in filtered_edges:
            direction = "Outgoing ➡️" if e["source"] == selected else "Incoming ⬅️" if e["target"] == selected else "Indirect 🔗"
            rel_data.append({
                "From Table": e["source"],
                "From Description": get_table_desc(e["source"]),
                "To Table": e["target"],
                "To Description": get_table_desc(e["target"]),
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
        st.info("No relationship edges found for the selected view / active data toggles.")

    direct_neighbors = sorted(adjacency.get(selected, set()))
    with st.expander(f"📌 Direct Neighbors of {selected} ({len(direct_neighbors)} tables)"):
        if direct_neighbors:
            cols = st.columns(4)
            for idx, neighbor in enumerate(direct_neighbors):
                desc = get_table_desc(neighbor)
                with cols[idx % 4]:
                    if st.button(f"🔗 {neighbor}", key=f"nb_btn_{neighbor}"):
                        st.session_state.selected_table = neighbor
                        st.rerun()
                    if desc:
                        st.caption(desc)
        else:
            st.write("No direct neighbors recorded.")
