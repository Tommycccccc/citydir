import re
import pandas as pd
import streamlit as st

st.set_page_config(page_title="ELC - City Directory Search", layout="wide")
st.title("ELC - City Directory Search")

# ---------- Styling ----------
st.markdown(
    """
    <style>
      div.stButton > button {
        width: 100%;
        height: 52px;
        border-radius: 10px;
        font-weight: 700;
        letter-spacing: .5px;
      }

      .addr-card {
        border: 1px solid rgba(255,255,255,.10);
        border-radius: 12px;
        padding: 14px 16px 10px 16px;
        background: rgba(255,255,255,.03);
        margin: 10px 0 18px 0;
      }

      .addr-header {
        font-size: 16px;
        font-weight: 800;
        margin: 0 0 10px 0;
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 8px;
      }
      .addr-pill {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 999px;
        background: rgba(255, 75, 75, .16);
        border: 1px solid rgba(255, 75, 75, .45);
        color: #ff4b4b;
        font-weight: 900;
        letter-spacing: .4px;
      }

      .neat-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 6px;
        table-layout: fixed; /* helps wrapping behave */
      }
      .neat-table th, .neat-table td {
        padding: 10px 12px;
        border-bottom: 1px solid rgba(255,255,255,.08);
        vertical-align: top;
      }
      .neat-table th {
        text-align: left;
        font-size: 14px;
        opacity: .9;
      }
      .neat-table td:first-child, .neat-table th:first-child {
        width: 90px;
        text-align: center;
        font-variant-numeric: tabular-nums;
        white-space: nowrap;
      }
      .neat-table td:last-child, .neat-table th:last-child {
        word-break: break-word;
        overflow-wrap: anywhere;
      }

      .section-title {
        margin-top: 18px;
      }

      /* Optional: make the right scroll container feel like a panel */
      .scroll-panel {
        border: 1px solid rgba(255,255,255,.10);
        border-radius: 12px;
        background: rgba(255,255,255,.02);
        padding: 10px 10px 2px 10px;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- Helpers ----------
def normalize_addr(addr: str) -> str:
    if addr is None:
        return ""
    s = str(addr).strip()
    s = re.sub(r"\s+", " ", s)
    return s

def read_input(file) -> pd.DataFrame:
    name = file.name.lower()

    if name.endswith(".csv"):
        df = pd.read_csv(file)
        df.columns = [str(c).strip().upper() for c in df.columns]
        if "ADDRESS" in df.columns:
            df["ADDRESS"] = df["ADDRESS"].ffill().apply(normalize_addr)
        return df

    xls = pd.ExcelFile(file)
    raw = pd.read_excel(xls, sheet_name=0, header=None)

    header_row = None
    for i in range(min(50, len(raw))):
        row_vals = raw.iloc[i].astype(str).str.upper().tolist()
        if "ADDRESS" in row_vals and "YEAR" in row_vals:
            header_row = i
            break

    if header_row is None:
        df = pd.read_excel(xls, sheet_name=0)
        df.columns = [str(c).strip().upper() for c in df.columns]
        if "ADDRESS" in df.columns:
            df["ADDRESS"] = df["ADDRESS"].ffill().apply(normalize_addr)
        return df

    df = pd.read_excel(xls, sheet_name=0, header=header_row)
    df.columns = [str(c).strip().upper() for c in df.columns]

    if "YEAR" in df.columns:
        df = df[df["YEAR"].notna()]

    if "ADDRESS" in df.columns:
        df["ADDRESS"] = df["ADDRESS"].ffill().apply(normalize_addr)

    return df

def format_year_listing(df_addr: pd.DataFrame) -> pd.DataFrame:
    if "YEAR" not in df_addr.columns or "LISTING" not in df_addr.columns:
        return pd.DataFrame(columns=["Year(s)", "Occupant Listed"])

    t = df_addr[["YEAR", "LISTING"]].copy()
    t["YEAR"] = pd.to_numeric(t["YEAR"], errors="coerce")
    t = t.dropna(subset=["YEAR"])
    t["YEAR"] = t["YEAR"].astype(int)

    t["LISTING"] = t["LISTING"].astype(str).str.strip()
    t = t[t["LISTING"].str.len() > 0]

    def combine_listings(series: pd.Series) -> str:
        seen = set()
        out = []
        for item in series.tolist():
            if item not in seen:
                seen.add(item)
                out.append(item)
        return ", ".join(out)

    grouped = (
        t.sort_values(["YEAR", "LISTING"], ascending=[True, True])
         .groupby("YEAR", as_index=False)["LISTING"]
         .apply(combine_listings)
         .rename(columns={"YEAR": "Year(s)", "LISTING": "Occupant Listed"})
         .reset_index(drop=True)
    )
    return grouped

def render_block(addr: str, kind: str, out_df: pd.DataFrame):
    st.markdown('<div class="addr-card">', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="addr-header">
          City Directory Search for <span class="addr-pill">{addr}</span> ({kind})
        </div>
        """,
        unsafe_allow_html=True
    )

    rows_html = ""
    for _, r in out_df.iterrows():
        year = str(r.get("Year(s)", "")).strip()
        occ = str(r.get("Occupant Listed", "")).strip()
        rows_html += f"<tr><td>{year}</td><td>{occ}</td></tr>"

    table_html = f"""
      <table class="neat-table">
        <thead>
          <tr>
            <th>Year(s)</th>
            <th>Occupant Listed</th>
          </tr>
        </thead>
        <tbody>
          {rows_html if rows_html else "<tr><td colspan='2' style='opacity:.7;'>No results</td></tr>"}
        </tbody>
      </table>
    """
    st.markdown(table_html, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ---------- Upload ----------
uploaded = st.file_uploader("Upload City Directory export (CSV or XLSX)", type=["csv", "xlsx"])
if not uploaded:
    st.stop()

df = read_input(uploaded)
df.columns = [c.upper() for c in df.columns]

if "ADDRESS" not in df.columns:
    st.error("Could not find an ADDRESS column. If your file uses a different column name, tell me what it is.")
    st.stop()

df["ADDRESS"] = df["ADDRESS"].apply(normalize_addr)
all_addresses = sorted([a for a in df["ADDRESS"].dropna().unique() if a.strip()])
st.success(f"Loaded {len(df):,} rows • Found {len(all_addresses):,} unique addresses")

# ---------- Session state + callbacks ----------
if "subject_sel" not in st.session_state:
    st.session_state["subject_sel"] = []
if "adjoining_sel" not in st.session_state:
    st.session_state["adjoining_sel"] = []
if "run_subject" not in st.session_state:
    st.session_state["run_subject"] = False
if "run_adjoining" not in st.session_state:
    st.session_state["run_adjoining"] = False

def clear_all():
    st.session_state["subject_sel"] = []
    st.session_state["adjoining_sel"] = []
    st.session_state["run_subject"] = False
    st.session_state["run_adjoining"] = False

def set_run_subject():
    st.session_state["run_subject"] = True

def set_run_adjoining():
    st.session_state["run_adjoining"] = True

# ---------- TOP UI ----------
ui_left, ui_right = st.columns(2)

with ui_left:
    st.subheader("Pick Subject Property Addresses")
    subject_selected = st.multiselect("Subject addresses", all_addresses, key="subject_sel")
    st.button("CREATE SUBJECT PROPERTY TABLES", use_container_width=True, on_click=set_run_subject)

with ui_right:
    st.subheader("Pick Adjoining Property Addresses")
    adjoining_selected = st.multiselect("Adjoining addresses", all_addresses, key="adjoining_sel")
    st.button("CREATE ADJOINING PROPERTY TABLES", use_container_width=True, on_click=set_run_adjoining)

st.button("CLEAR ALL", use_container_width=True, on_click=clear_all)
st.divider()

# ---------- OUTPUT IN TWO COLUMNS ----------
out_left, out_right = st.columns(2)

with out_left:
    st.markdown('<h2 class="section-title">Subject Property Tables</h2>', unsafe_allow_html=True)
    if st.session_state["run_subject"] and subject_selected:
        for addr in subject_selected:
            block = df[df["ADDRESS"] == addr].copy()
            out = format_year_listing(block)
            render_block(addr, "Subject Property", out)
    else:
        st.caption("Select a subject address and click CREATE SUBJECT PROPERTY TABLES.")

with out_right:
    st.markdown('<h2 class="section-title">Adjoining Property Tables</h2>', unsafe_allow_html=True)

    if st.session_state["run_adjoining"] and adjoining_selected:
        # Panel wrapper (optional)

        # ✅ Native Streamlit scroll area (FULL WIDTH like left)
        scroll_box = st.container(height=720)
        with scroll_box:
            for addr in adjoining_selected:
                block = df[df["ADDRESS"] == addr].copy()
                out = format_year_listing(block)
                render_block(addr, "Adjoining Property", out)

    else:
        st.caption("Select adjoining addresses and click CREATE ADJOINING PROPERTY TABLES.")
