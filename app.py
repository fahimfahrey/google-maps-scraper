"""Streamlit UI: an 'operations console' for Google Maps scraping.

Sidebar control panel, live status, per-query result tabs, export.
"""

from __future__ import annotations

import hashlib
import io
import queue
import re
import threading
from datetime import datetime

import pandas as pd
import streamlit as st

import database
import scraper

# ---------------------------------------------------------------------------
# Pure helpers (no Streamlit — unit-testable)
# ---------------------------------------------------------------------------

def _adapt_lead(record: dict, search_query: str = "") -> dict:
    """Map scraper result keys to database.save_lead expected keys.

    `search_query` tags the lead with the query that produced it so the UI
    can group leads into per-query tabs.
    """
    key = f"{record.get('name', '')}|{record.get('phone', '')}"
    return {
        "google_id":     hashlib.md5(key.encode()).hexdigest(),
        "name":          record.get("name", ""),
        "rating":        record.get("rating", ""),
        "reviews_count": record.get("reviews", ""),
        "phone":         record.get("phone", ""),
        "website":       record.get("website", ""),
        "address":       "",
        "category":      "",
        "search_query":  search_query,
        "scraped_at":    datetime.utcnow().isoformat(),
    }


def _df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def _df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


def _slug(text: str) -> str:
    """Filesystem/key-safe slug from arbitrary query text."""
    return re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_") or "query"


def _query_of(log_text: str) -> str:
    """Extract the query from a '[i/n] query' progress log line."""
    return log_text.split("] ", 1)[-1] if "] " in log_text else log_text


def _drain_queue(out_q: queue.Queue, state: dict) -> None:
    """Drain all available messages from out_q into state. Non-blocking.

    Message schema:
        {"type": "row",   "data": dict}   — increment leads_collected
        {"type": "log",   "text": str}    — append to log_lines
        {"type": "error", "text": str}    — set scrape_error
        {"type": "done"}                  — mark scraping finished, clear queue ref
    """
    try:
        while True:
            msg = out_q.get_nowait()
            mtype = msg.get("type")
            if mtype == "row":
                state["leads_collected"] = state.get("leads_collected", 0) + 1
            elif mtype == "log":
                logs: list = state.get("log_lines", [])
                logs.append(msg["text"])
                state["log_lines"] = logs
                # Current-query indicator is driven by the queue (the background
                # thread has no ScriptRunContext and cannot write session_state).
                state["current_query"] = _query_of(msg["text"])
            elif mtype == "error":
                state["scrape_error"] = msg["text"]
            elif mtype == "done":
                state["scraping_active"] = False
                state["scrape_queue"] = None
    except queue.Empty:
        pass


# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------

st.session_state.setdefault("scraping_active", False)
st.session_state.setdefault("leads_collected", 0)
st.session_state.setdefault("current_query", "—")
st.session_state.setdefault("scrape_error", None)
st.session_state.setdefault("scrape_queue", None)
st.session_state.setdefault("log_lines", [])
st.session_state.setdefault("max_results_cap", None)

# ---------------------------------------------------------------------------
# DB bootstrap
# ---------------------------------------------------------------------------

database.initialize_db()

# ---------------------------------------------------------------------------
# Page config + theme
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="GMAPS // Lead Console",
    page_icon=":material/radar:",
    layout="wide",
)

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700;800&family=Sora:wght@300;400;500;600&display=swap');

:root {
    --amber:    #FFB000;
    --amber-dim:#7a5500;
    --ink:      #0B0E11;
    --panel:    #14181D;
    --line:     #232A31;
    --text:     #E6E1D6;
    --muted:    #8A8F98;
    --green:    #4ADE80;
}

/* Canvas: deep ink with a faint amber horizon glow + scanlines */
.stApp {
    background:
        radial-gradient(1200px 480px at 78% -8%, rgba(255,176,0,0.07), transparent 60%),
        repeating-linear-gradient(0deg, rgba(255,255,255,0.012) 0 1px, transparent 1px 3px),
        var(--ink);
    color: var(--text);
    font-family: 'Sora', sans-serif;
}

/* Typography */
h1, h2, h3, h4,
[data-testid="stMetricValue"],
.stTabs [data-baseweb="tab"] {
    font-family: 'JetBrains Mono', monospace !important;
    letter-spacing: -0.01em;
}

/* ---- Hero banner ---- */
.console-hero {
    border: 1px solid var(--line);
    border-left: 3px solid var(--amber);
    background: linear-gradient(180deg, rgba(255,176,0,0.05), transparent 70%), var(--panel);
    border-radius: 10px;
    padding: 20px 24px;
    margin-bottom: 18px;
    box-shadow: 0 18px 50px -28px rgba(0,0,0,0.9);
}
.console-hero .eyebrow {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px; letter-spacing: 0.32em; text-transform: uppercase;
    color: var(--amber);
}
.console-hero h1 {
    font-size: 30px; font-weight: 800; margin: 6px 0 4px;
    color: var(--text);
}
.console-hero .sub { color: var(--muted); font-size: 13px; }
.led {
    display: inline-block; width: 8px; height: 8px; border-radius: 50%;
    margin-right: 7px; vertical-align: middle;
}
.led.on  { background: var(--green); box-shadow: 0 0 10px var(--green); animation: pulse 1.2s infinite; }
.led.off { background: var(--amber-dim); }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.35; } }

/* Metrics as instrument readouts */
[data-testid="stMetric"] {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 9px;
    padding: 14px 16px;
}
[data-testid="stMetricLabel"] {
    text-transform: uppercase; letter-spacing: 0.16em; font-size: 10px !important;
    color: var(--muted);
}
[data-testid="stMetricValue"] { color: var(--amber); font-weight: 700; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0E1216, #0B0E11);
    border-right: 1px solid var(--line);
}
[data-testid="stSidebar"] h2 { font-size: 15px; color: var(--text); }

/* Buttons */
.stButton button, [data-testid="stBaseButton-primary"] {
    font-family: 'JetBrains Mono', monospace; font-weight: 700;
    letter-spacing: 0.04em; border-radius: 8px;
}
[data-testid="stBaseButton-primary"] {
    background: var(--amber) !important; color: #1a1300 !important;
    border: 1px solid var(--amber) !important;
    box-shadow: 0 0 24px -6px rgba(255,176,0,0.5);
}
[data-testid="stBaseButton-primary"]:hover { filter: brightness(1.08); }

/* Tabs: terminal channel selector */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px; border-bottom: 1px solid var(--line);
}
.stTabs [data-baseweb="tab"] {
    background: transparent; color: var(--muted);
    font-size: 13px; padding: 8px 14px; border-radius: 6px 6px 0 0;
}
.stTabs [aria-selected="true"] {
    color: var(--amber) !important;
    border-bottom: 2px solid var(--amber) !important;
    background: rgba(255,176,0,0.06);
}

/* Progress bar */
.stProgress > div > div > div { background-image: linear-gradient(90deg, var(--amber-dim), var(--amber)) !important; }

/* Dataframe container */
[data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 8px; }

/* Hide Streamlit chrome for a cleaner console */
#MainMenu, [data-testid="stToolbar"] { visibility: hidden; }
</style>
"""
st.html(_CSS)


def _hero() -> None:
    active = st.session_state.scraping_active
    led = "on" if active else "off"
    state_word = "SCANNING" if active else "STANDBY"
    st.html(
        f"""
        <div class="console-hero">
          <div class="eyebrow">Google Maps · Lead Acquisition</div>
          <h1>Lead Console</h1>
          <div class="sub"><span class="led {led}"></span>{state_word} —
          extract businesses by query, stream them live, group by search.</div>
        </div>
        """
    )


_hero()

# ---------------------------------------------------------------------------
# Sidebar — control panel
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header(":material/tune: Control Panel")

    queries_raw = st.text_area(
        "Search queries",
        placeholder="coffee shops london\nplumbers new york\nrestaurants berlin",
        height=170,
        help="One query per line. Each becomes its own result tab.",
        key="queries_input",
    )

    speed_label = st.selectbox(
        "Execution speed",
        options=["Normal", "Slow (cautious)", "Fast"],
        index=0,
        help="Inter-query delay. Slow = 15–30 s, Normal = 5–15 s, Fast = 1.5–5 s.",
        key="speed_select",
    )

    _SPEED_MAP = {
        "Normal":          "normal",
        "Slow (cautious)": "slow",
        "Fast":            "fast",
    }

    max_results_input = st.number_input(
        "Max results (0 = unlimited)",
        min_value=0,
        max_value=1000,
        value=50,
        step=10,
        help="Stop once this many unique leads are collected across all queries.",
        key="max_results_input",
    )

    st.divider()
    st.caption(":material/info: Phone & website appear only for listings that publish them.")


# ---------------------------------------------------------------------------
# Result rendering
# ---------------------------------------------------------------------------

_BASE_COLS = {
    "id":            None,
    "google_id":     None,
    "address":       None,
    "category":      None,
    "scraped_at":    st.column_config.DatetimeColumn("Scraped", format="MMM DD, HH:mm"),
    "name":          st.column_config.TextColumn("Name", width="medium"),
    "rating":        st.column_config.NumberColumn("Rating", format="%.1f ⭐"),
    "reviews_count": st.column_config.NumberColumn("Reviews"),
    "phone":         st.column_config.TextColumn("Phone"),
    "website":       st.column_config.LinkColumn("Website"),
}


def _apply_editor_changes(df: pd.DataFrame, state: dict, query_label: str | None) -> bool:
    """Persist a data_editor's edits / row-deletions / additions to the DB.

    `df` is the exact frame handed to the editor (positional index = editor
    index); `state` is the editor's session_state diff dict. Returns True if
    anything changed.
    """
    changed = False

    for idx, changes in state.get("edited_rows", {}).items():
        gid = df.iloc[int(idx)]["google_id"]
        database.update_lead(gid, changes)
        changed = True

    for idx in state.get("deleted_rows", []):
        gid = df.iloc[int(idx)]["google_id"]
        database.delete_lead(gid)
        changed = True

    for row in state.get("added_rows", []):
        if not row.get("name"):
            continue
        record = {
            "name":    row.get("name", ""),
            "phone":   row.get("phone", ""),
            "rating":  row.get("rating", ""),
            "reviews": row.get("reviews_count", ""),
            "website": row.get("website", ""),
        }
        q = row.get("search_query") or query_label or ""
        database.save_lead(_adapt_lead(record, q))
        changed = True

    return changed


def _leads_table(df: pd.DataFrame, key: str, show_query: bool, query_label: str | None) -> None:
    """Editable leads table: inline edit, row delete (trash), CSV, danger zone.

    Editing is disabled while a scrape is active (the 2 s refresh would discard
    in-progress edits)."""
    active = st.session_state.scraping_active
    df = df.reset_index(drop=True)  # positional index for editor diffing
    editor_key = f"editor_{key}"

    cols = dict(_BASE_COLS)
    cols["search_query"] = (
        st.column_config.TextColumn("Query") if show_query else None
    )

    # Toolbar
    c_info, c_apply, c_csv, c_del = st.columns([3, 1.1, 1, 1], vertical_alignment="center")
    with c_info:
        avg = pd.to_numeric(df["rating"], errors="coerce").mean()
        avg_txt = f" · avg {avg:.1f}★" if pd.notna(avg) else ""
        st.caption(f":material/database: {len(df)} leads{avg_txt}")
    with c_apply:
        if st.button(
            ":material/save: Apply", key=f"apply_{key}", width="stretch",
            disabled=active, help="Save inline edits, deletions and new rows.",
        ):
            if _apply_editor_changes(df, st.session_state.get(editor_key, {}), query_label):
                st.toast("Changes saved", icon=":material/check_circle:")
            st.session_state.pop(editor_key, None)
            st.rerun(scope="app")
    with c_csv:
        st.download_button(
            ":material/download: CSV",
            data=_df_to_csv_bytes(df.drop(columns=["id"], errors="ignore")),
            file_name=f"leads_{key}.csv",
            mime="text/csv",
            key=f"dl_{key}",
            width="stretch",
        )
    with c_del:
        with st.popover(":material/delete: Delete", width="stretch", disabled=active):
            st.caption("Danger zone — cannot be undone.")
            if query_label is not None and st.button(
                f":material/delete_sweep: Delete query “{query_label}”",
                key=f"delq_{key}", width="stretch",
            ):
                n = database.delete_by_query(query_label)
                st.session_state.pop(editor_key, None)
                st.toast(f"Deleted {n} leads", icon=":material/delete:")
                st.rerun(scope="app")
            if st.button(
                ":material/delete_forever: Clear ALL leads",
                key=f"delall_{key}", width="stretch",
            ):
                database.delete_all()
                st.session_state.pop(editor_key, None)
                st.toast("All leads cleared", icon=":material/delete:")
                st.rerun(scope="app")

    if active:
        st.caption(":material/lock: Editing locked while scraping.")
        st.dataframe(df, hide_index=True, width="stretch", column_config=cols)
        return

    st.data_editor(
        df,
        key=editor_key,
        hide_index=True,
        width="stretch",
        num_rows="dynamic",
        disabled=["id", "google_id", "scraped_at"],
        column_config=cols,
    )
    st.caption(
        ":material/edit: Edit cells inline · select rows + trash icon to delete · "
        "then click **Apply**."
    )


def _render_results(df: pd.DataFrame) -> None:
    """Per-query tabs (+ an All tab). Tab labels are stable (no counts) so the
    selected tab survives the 2 s live refresh."""
    if df.empty:
        st.info(
            ":material/radar: No leads yet. Enter queries in the sidebar and "
            "hit **Start Scraping** — results stream in here, one tab per query."
        )
        return

    df = df.copy()
    df["search_query"] = df["search_query"].fillna("").replace("", "Unlabeled")
    # Preserve first-seen order of queries.
    queries = list(dict.fromkeys(df["search_query"].tolist()))

    labels = ["◆ All"] + [f"› {q}" for q in queries]
    tabs = st.tabs(labels)

    with tabs[0]:
        _leads_table(df, "all", show_query=True, query_label=None)

    for i, q in enumerate(queries, start=1):
        with tabs[i]:
            _leads_table(
                df[df["search_query"] == q], _slug(q),
                show_query=False, query_label=q,
            )


# ---------------------------------------------------------------------------
# Status console — auto-refreshes every 2 s while scraping
# ---------------------------------------------------------------------------

@st.fragment(run_every=2 if st.session_state.scraping_active else None)
def _status_panel() -> None:
    # Drain any new messages from the background thread.
    out_q: queue.Queue | None = st.session_state.scrape_queue
    if out_q is not None:
        _drain_queue(out_q, st.session_state)
        if not st.session_state.scraping_active:
            # Scrape just finished ('done' drained). A full app rerun
            # re-evaluates run_every → None, stopping the 2 s loop.
            st.rerun(scope="app")

    total_in_db = database.count_leads()
    active = st.session_state.scraping_active

    c1, c2, c3 = st.columns(3)
    c1.metric("Total in DB", value=total_in_db, border=True)
    c2.metric("This session", value=st.session_state.leads_collected, border=True)
    c3.metric(
        "Status",
        value="SCANNING" if active else "IDLE",
        delta=st.session_state.current_query if active else None,
        delta_color="off",
        border=True,
    )

    cap = st.session_state.get("max_results_cap")
    if active and cap:
        collected = min(st.session_state.leads_collected, cap)
        st.progress(collected / cap, text=f"{collected} / {cap} leads")

    if st.session_state.scrape_error:
        st.error(f":material/error: {st.session_state.scrape_error}")

    log_lines: list[str] = st.session_state.get("log_lines", [])
    if log_lines:
        with st.expander(":material/terminal: Live log", expanded=active):
            st.code("\n".join(log_lines[-50:]), language=None)

    st.html("<div style='height:6px'></div>")
    _render_results(database.fetch_all_leads_as_dataframe())


_status_panel()

# ---------------------------------------------------------------------------
# Background scraper thread
# ---------------------------------------------------------------------------

def _run_scrape(
    queries: list[str],
    preset: str,
    out_q: queue.Queue,
    max_results: int | None = None,
) -> None:
    """Background thread. Feeds out_q; row_callback handles DB write + counter.

    Runs without a Streamlit ScriptRunContext, so it MUST NOT touch
    st.session_state directly — all state flows back through out_q and is
    applied by _drain_queue on the main thread.
    """
    # Track which query is currently producing rows (set by the log callback,
    # which fires just before each query's rows stream in).
    cursor = {"query": ""}

    def on_row(record: dict) -> None:
        adapted = _adapt_lead(record, cursor["query"])
        database.save_lead(adapted)
        out_q.put({"type": "row", "data": adapted})

    def on_log(text: str) -> None:
        cursor["query"] = _query_of(text)
        out_q.put({"type": "log", "text": text})

    try:
        scraper.scrape_multi(
            queries,
            delay_preset=preset,
            row_callback=on_row,
            log_callback=on_log,
            max_results=max_results,
        )
    except Exception as exc:  # noqa: BLE001
        out_q.put({"type": "error", "text": str(exc)})
    finally:
        out_q.put({"type": "done"})


# ---------------------------------------------------------------------------
# Start / control row
# ---------------------------------------------------------------------------

parsed_queries = [q.strip() for q in queries_raw.splitlines() if q.strip()]

start_col, info_col = st.columns([1, 2], vertical_alignment="center")
with start_col:
    start_disabled = st.session_state.scraping_active or not parsed_queries
    if st.button(
        ":material/play_arrow: Start Scraping",
        type="primary",
        disabled=start_disabled,
        width="stretch",
        help="Disabled when no queries entered or a scrape is already running.",
    ):
        preset = _SPEED_MAP.get(speed_label, "normal")
        cap = int(max_results_input) or None  # 0 → unlimited
        out_q: queue.Queue = queue.Queue()
        st.session_state.scraping_active = True
        st.session_state.leads_collected = 0
        st.session_state.scrape_error = None
        st.session_state.log_lines = []
        st.session_state.scrape_queue = out_q
        st.session_state.max_results_cap = cap
        t = threading.Thread(
            target=_run_scrape,
            args=(parsed_queries, preset, out_q, cap),
            daemon=True,
        )
        t.start()
        st.rerun()
with info_col:
    if parsed_queries and not st.session_state.scraping_active:
        st.caption(
            f":material/playlist_add_check: {len(parsed_queries)} "
            f"quer{'y' if len(parsed_queries) == 1 else 'ies'} queued."
        )

# ---------------------------------------------------------------------------
# Export (all leads)
# ---------------------------------------------------------------------------

st.divider()
_export_df = database.fetch_all_leads_as_dataframe()

if _export_df.empty:
    st.caption("Nothing to export yet.")
else:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    e1, e2, _ = st.columns([1, 1, 3])
    with e1:
        st.download_button(
            ":material/download: All as CSV",
            data=_df_to_csv_bytes(_export_df.drop(columns=["id"], errors="ignore")),
            file_name=f"leads_all_{ts}.csv",
            mime="text/csv",
            width="stretch",
        )
    with e2:
        st.download_button(
            ":material/table_chart: All as Excel",
            data=_df_to_excel_bytes(_export_df.drop(columns=["id"], errors="ignore")),
            file_name=f"leads_all_{ts}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
