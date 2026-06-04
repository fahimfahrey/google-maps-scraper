"""Streamlit UI: sidebar control panel, live status, data table, export."""

from __future__ import annotations

import hashlib
import io
import queue
import threading
from datetime import datetime

import pandas as pd
import streamlit as st

import database
import scraper

# ---------------------------------------------------------------------------
# Pure helpers (no Streamlit — unit-testable)
# ---------------------------------------------------------------------------

def _adapt_lead(record: dict) -> dict:
    """Map scraper result keys to database.save_lead expected keys."""
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
        "scraped_at":    datetime.utcnow().isoformat(),
    }


def _df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def _df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


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

# ---------------------------------------------------------------------------
# DB bootstrap
# ---------------------------------------------------------------------------

database.initialize_db()

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Google Maps Scraper",
    page_icon=":material/travel_explore:",
    layout="wide",
)

st.title(":material/travel_explore: Google Maps Scraper")

# ---------------------------------------------------------------------------
# Sidebar — control panel
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header(":material/settings: Control Panel")

    queries_raw = st.text_area(
        "Search queries",
        placeholder="coffee shops london\nplumbers new york\nrestaurants berlin",
        height=180,
        help="One query per line. Each runs as a separate Google Maps search.",
        key="queries_input",
    )

    speed_label = st.selectbox(
        "Execution speed",
        options=["Normal", "Slow (cautious)", "Fast"],
        index=0,
        help="Controls inter-query delay. Slow = 15–30 s, Normal = 5–15 s, Fast = 1.5–5 s.",
        key="speed_select",
    )

    _SPEED_MAP = {
        "Normal":          "normal",
        "Slow (cautious)": "slow",
        "Fast":            "fast",
    }

# ---------------------------------------------------------------------------
# Status metrics — auto-refreshes every 2 s while scraping
# ---------------------------------------------------------------------------

@st.fragment(run_every=2 if st.session_state.scraping_active else None)
def _status_panel() -> None:
    # Drain any new messages from the background thread.
    out_q: queue.Queue | None = st.session_state.scrape_queue
    if out_q is not None:
        _drain_queue(out_q, st.session_state)

    total_in_db = database.count_leads()

    with st.container(horizontal=True):
        st.metric(
            "Total leads in DB",
            value=total_in_db,
            border=True,
        )
        st.metric(
            "Leads this session",
            value=st.session_state.leads_collected,
            border=True,
        )
        status_text = (
            ":material/sync: Scraping…"
            if st.session_state.scraping_active
            else ":material/check_circle: Idle"
        )
        st.metric("Status", value=status_text, border=True)

    if st.session_state.scraping_active:
        st.caption(f"Current query: **{st.session_state.current_query}**")

    if st.session_state.scrape_error:
        st.error(f"Scrape error: {st.session_state.scrape_error}")

    # Live log panel — shown only when there are log entries.
    log_lines: list[str] = st.session_state.get("log_lines", [])
    if log_lines:
        with st.expander(
            ":material/terminal: Live log",
            expanded=st.session_state.scraping_active,
        ):
            log_slot = st.empty()
            log_slot.code("\n".join(log_lines[-50:]), language=None)


_status_panel()

# ---------------------------------------------------------------------------
# Live data table
# ---------------------------------------------------------------------------

with st.container(border=True):
    st.subheader(":material/table: Collected Leads")
    _df = database.fetch_all_leads_as_dataframe()
    if _df.empty:
        st.info("No leads yet. Enter queries in the sidebar and click **Start Scraping**.")
    else:
        st.dataframe(
            _df,
            hide_index=True,
            column_config={
                "id":            None,
                "google_id":     None,
                "scraped_at":    st.column_config.DatetimeColumn("Scraped at", format="MMM DD, YYYY HH:mm"),
                "rating":        st.column_config.NumberColumn("Rating", format="%.1f ⭐"),
                "reviews_count": st.column_config.NumberColumn("Reviews"),
                "website":       st.column_config.LinkColumn("Website"),
            },
        )

# ---------------------------------------------------------------------------
# Background scraper thread
# ---------------------------------------------------------------------------

def _run_scrape(queries: list[str], preset: str, out_q: queue.Queue) -> None:
    """Background thread. Feeds out_q; row_callback handles DB write + counter."""
    def on_row(record: dict) -> None:
        adapted = _adapt_lead(record)
        database.save_lead(adapted)
        out_q.put({"type": "row", "data": adapted})

    def on_log(text: str) -> None:
        st.session_state.current_query = text
        out_q.put({"type": "log", "text": text})

    try:
        scraper.scrape_multi(
            queries,
            delay_preset=preset,
            row_callback=on_row,
            log_callback=on_log,
        )
    except Exception as exc:  # noqa: BLE001
        out_q.put({"type": "error", "text": str(exc)})
    finally:
        out_q.put({"type": "done"})
        st.session_state.scraping_active = False
        st.session_state.current_query = "—"


# ---------------------------------------------------------------------------
# Start Scraping button
# ---------------------------------------------------------------------------

parsed_queries = [q.strip() for q in queries_raw.splitlines() if q.strip()]

with st.container(horizontal=True):
    start_disabled = st.session_state.scraping_active or not parsed_queries
    if st.button(
        ":material/play_arrow: Start Scraping",
        type="primary",
        disabled=start_disabled,
        help="Disabled when no queries entered or scrape already running.",
    ):
        preset = _SPEED_MAP.get(speed_label, "normal")
        out_q: queue.Queue = queue.Queue()
        st.session_state.scraping_active = True
        st.session_state.leads_collected = 0
        st.session_state.scrape_error = None
        st.session_state.log_lines = []
        st.session_state.scrape_queue = out_q
        t = threading.Thread(
            target=_run_scrape,
            args=(parsed_queries, preset, out_q),
            daemon=True,
        )
        t.start()
        st.rerun()

# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

st.subheader(":material/download: Export Leads")

_export_df = database.fetch_all_leads_as_dataframe()

if _export_df.empty:
    st.caption("Nothing to export yet.")
else:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    with st.container(horizontal=True):
        st.download_button(
            label=":material/download: Download CSV",
            data=_df_to_csv_bytes(_export_df),
            file_name=f"leads_{ts}.csv",
            mime="text/csv",
        )
        st.download_button(
            label=":material/table_chart: Download Excel",
            data=_df_to_excel_bytes(_export_df),
            file_name=f"leads_{ts}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
