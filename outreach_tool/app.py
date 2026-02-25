from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from config import CampaignSettings, load_env
from run_campaign import CampaignStats, process_campaign


st.set_page_config(page_title="Cybernara Outreach Tool", layout="wide")
load_env()

if "stop_requested" not in st.session_state:
    st.session_state.stop_requested = False
if "last_log_path" not in st.session_state:
    st.session_state.last_log_path = None
if "live_lines" not in st.session_state:
    st.session_state.live_lines = []
if "stats" not in st.session_state:
    st.session_state.stats = CampaignStats()
if "fatal_error" not in st.session_state:
    st.session_state.fatal_error = None

st.title("Cybernara Internal Outreach Tool (Verify + Send)")
st.markdown(
    """
    ### Daily flow for Astha
    1. Upload leads file (CSV/Excel)
    2. Choose verification and pacing settings
    3. Click **Start** and monitor live logs
    4. Download the run log when complete
    """
)

uploader_col, controls_col = st.columns([2, 1])

with uploader_col:
    uploaded_file = st.file_uploader("Upload leads file", type=["csv", "xlsx", "xls"])
    st.caption("Supports CSV and Excel files so Astha can upload directly from a spreadsheet export.")

with controls_col:
    verification_enabled = st.toggle("Verification ON", value=True)
    verification_quality = "High"
    if verification_enabled:
        verification_quality = st.selectbox("Verification quality", ["Standard", "High", "Extreme"], index=1)

    max_emails = st.number_input("Max emails per run", min_value=1, max_value=50, value=50)
    delay_min = st.number_input("Delay min (seconds)", min_value=0, value=300)
    delay_max = st.number_input("Delay max (seconds)", min_value=0, value=720)
    defer_outside_hours = st.toggle("Defer outside business hours", value=True)
    stop_on_credits = st.toggle("Stop if Verifalia credits exhausted", value=True)

start_col, stop_col = st.columns(2)
start_clicked = start_col.button("Start", type="primary", use_container_width=True)
stop_clicked = stop_col.button("Stop", use_container_width=True)

if stop_clicked:
    st.session_state.stop_requested = True

stats_placeholder = st.empty()
status_placeholder = st.empty()
live_log_placeholder = st.empty()


def render_stats(stats: CampaignStats) -> None:
    stats_placeholder.info(
        f"Total rows: {stats.total_rows} | Current row: {stats.current_row} | Sent: {stats.sent_count} "
        f"| Skipped: {stats.skipped_count} | Deferred: {stats.deferred_count} | Failed: {stats.failed_count}"
    )


def on_progress(stats: CampaignStats, message: str) -> None:
    st.session_state.stats = stats
    st.session_state.live_lines.append(message)
    if len(st.session_state.live_lines) > 200:
        st.session_state.live_lines = st.session_state.live_lines[-200:]
    render_stats(stats)
    status_placeholder.write(message)
    live_log_placeholder.code("\n".join(st.session_state.live_lines[-30:]), language="text")


render_stats(st.session_state.stats)
live_log_placeholder.code("\n".join(st.session_state.live_lines[-30:]), language="text")

if start_clicked:
    if uploaded_file is None:
        st.error("Please upload a leads file before starting.")
    else:
        st.session_state.stop_requested = False
        st.session_state.live_lines = []
        st.session_state.fatal_error = None

        suffix = Path(uploaded_file.name).suffix.lower()
        if suffix in {".xlsx", ".xls"}:
            dataframe = pd.read_excel(uploaded_file)
        else:
            dataframe = pd.read_csv(uploaded_file)
        settings = CampaignSettings(
            verification_enabled=verification_enabled,
            verification_quality=verification_quality,
            max_emails_per_run=int(max_emails),
            delay_min_seconds=int(delay_min),
            delay_max_seconds=int(delay_max),
            defer_outside_business_hours=defer_outside_hours,
            stop_on_verifalia_credits_exhausted=stop_on_credits,
        )

        try:
            stats, _, log_path, fatal_error = process_campaign(
                dataframe=dataframe,
                settings=settings,
                progress_callback=on_progress,
                should_stop=lambda: st.session_state.stop_requested,
            )
            st.session_state.stats = stats
            st.session_state.last_log_path = str(log_path)
            st.session_state.fatal_error = fatal_error
            render_stats(stats)

            if fatal_error:
                st.error(fatal_error)
            elif st.session_state.stop_requested:
                st.warning("Processing stopped gracefully.")
            else:
                st.success("Campaign completed.")
        except Exception as exc:  # noqa: BLE001
            st.exception(exc)

if st.session_state.last_log_path:
    log_path = Path(st.session_state.last_log_path)
    if log_path.exists():
        st.download_button(
            "Download latest log",
            data=log_path.read_bytes(),
            file_name=log_path.name,
            mime="text/csv",
        )
