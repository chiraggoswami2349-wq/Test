from __future__ import annotations

import argparse
import random
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

import pandas as pd

from config import OPTIONAL_EMAIL_COLUMNS, OUTPUT_DIR, REQUIRED_COLUMNS, CampaignSettings, load_env, load_secrets
from services.graph_client import GraphClient
from services.logger import make_log_path, write_logs
from services.templating import render_template
from services.timezone_rules import check_business_hours
from services.verifalia_client import VerifaliaClient, VerifaliaCreditsExhausted

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class CampaignStats:
    total_rows: int = 0
    sent_count: int = 0
    skipped_count: int = 0
    deferred_count: int = 0
    failed_count: int = 0
    current_row: int = 0


def _empty_classifications() -> dict[str, str]:
    return {
        "classification_email1": "",
        "classification_email2": "",
        "classification_email3": "",
        "final_classification": "",
    }


def _base_log_row(row: dict, settings: CampaignSettings) -> dict:
    log_row = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        **row,
        "selected_email": "",
        "verification_enabled": settings.verification_enabled,
        "verification_quality": settings.verification_quality,
        **_empty_classifications(),
        "send_attempted": False,
        "send_status_code": "",
        "send_result": "",
        "error_message": "",
    }
    return log_row


def _interruptible_sleep(total_seconds: int, should_stop: Callable[[], bool] | None) -> bool:
    remaining = total_seconds
    while remaining > 0:
        if should_stop and should_stop():
            return True
        time.sleep(min(1, remaining))
        remaining -= 1
    return False


def _is_valid_email_format(email: str) -> bool:
    return bool(email and EMAIL_PATTERN.match(email.strip()))


def process_campaign(
    dataframe: pd.DataFrame,
    settings: CampaignSettings,
    progress_callback: Callable[[CampaignStats, str], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> tuple[CampaignStats, list[dict], Path, str | None]:
    settings.normalize()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    missing = REQUIRED_COLUMNS - set(dataframe.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")

    for optional_col in OPTIONAL_EMAIL_COLUMNS:
        if optional_col not in dataframe.columns:
            dataframe[optional_col] = ""

    secrets = load_secrets()
    graph_client = GraphClient(secrets.tenant_id, secrets.client_id, secrets.client_secret)
    verifalia_client = None
    if settings.verification_enabled:
        if not secrets.verifalia_username or not secrets.verifalia_password:
            raise ValueError("Verification enabled but VERIFALIA credentials are missing.")
        verifalia_client = VerifaliaClient(secrets.verifalia_username, secrets.verifalia_password)

    prepared_rows = []
    for idx, row in dataframe.iterrows():
        row_data = {k: ("" if pd.isna(v) else str(v)) for k, v in row.to_dict().items()}
        prepared_rows.append((idx + 1, row_data))

    stats = CampaignStats(total_rows=len(prepared_rows))
    log_rows: list[dict] = []
    fatal_error: str | None = None
    verification_enabled_runtime = settings.verification_enabled

    pending_positions = list(range(len(prepared_rows)))
    sender_next_available_epoch: dict[str, float] = {}

    while pending_positions and stats.sent_count < settings.max_emails_per_run:
        if should_stop and should_stop():
            break

        now_epoch = time.time()
        selected_pending_slot: int | None = None
        earliest_ready_epoch: float | None = None

        for slot, row_position in enumerate(pending_positions):
            row_number, row_data = prepared_rows[row_position]
            sender = row_data.get("sender", "").strip().lower()
            ready_epoch = sender_next_available_epoch.get(sender, 0.0)
            if sender in settings.sender_allow_list and ready_epoch > now_epoch:
                if earliest_ready_epoch is None or ready_epoch < earliest_ready_epoch:
                    earliest_ready_epoch = ready_epoch
                continue

            selected_pending_slot = slot
            break

        if selected_pending_slot is None:
            if earliest_ready_epoch is None:
                break
            sleep_seconds = max(1, int(earliest_ready_epoch - now_epoch))
            if progress_callback:
                progress_callback(
                    stats,
                    f"All ready senders are cooling down. Waiting {sleep_seconds} seconds for the next mailbox window.",
                )
            was_stopped = _interruptible_sleep(sleep_seconds, should_stop)
            if was_stopped:
                break
            continue

        selected_row_position = pending_positions.pop(selected_pending_slot)
        row_number, row_data = prepared_rows[selected_row_position]

        stats.current_row = row_number
        log_row = _base_log_row(row_data, settings)
        log_row["verification_enabled"] = verification_enabled_runtime

        if progress_callback:
            progress_callback(stats, f"Processing row {stats.current_row}/{stats.total_rows}")

        sender = row_data.get("sender", "").strip().lower()
        if progress_callback:
            progress_callback(stats, f"Validating sender mailbox: {sender or '[missing]'}")
        if sender not in settings.sender_allow_list:
            log_row["send_result"] = "Skipped"
            log_row["error_message"] = "Invalid_Sender_Not_Allowed"
            stats.skipped_count += 1
            log_rows.append(log_row)
            continue

        ready_epoch = sender_next_available_epoch.get(sender, 0.0)
        if ready_epoch > time.time():
            wait_seconds = max(1, int(ready_epoch - time.time()))
            if progress_callback:
                progress_callback(stats, f"Mailbox {sender} is cooling down for {wait_seconds} more seconds; row re-queued.")
            pending_positions.append(selected_row_position)
            continue

        if progress_callback:
            progress_callback(stats, f"Checking business hours for country: {row_data.get('country', '')}")
        business_hours = check_business_hours(row_data.get("country", ""))
        if not business_hours.valid_country:
            log_row["send_result"] = "Skipped"
            log_row["error_message"] = "Invalid_Country"
            stats.skipped_count += 1
            log_rows.append(log_row)
            continue
        if not business_hours.within_business_hours and settings.defer_outside_business_hours:
            log_row["send_result"] = "Deferred"
            log_row["error_message"] = "Deferred_Outside_Business_Hours"
            stats.deferred_count += 1
            log_rows.append(log_row)
            continue

        selected_email = ""
        selected_classification = ""
        classification_keys = ["classification_email1", "classification_email2", "classification_email3"]

        for email_col_index, email_col in enumerate(["email1", "email2", "email3"]):
            candidate = row_data.get(email_col, "").strip()
            if progress_callback:
                progress_callback(stats, f"Evaluating {email_col} for {row_data.get('name', 'prospect')}: {candidate or '[empty]'}")
            if not candidate:
                continue

            if not _is_valid_email_format(candidate):
                log_row[classification_keys[email_col_index]] = "InvalidFormat"
                continue

            if verification_enabled_runtime and verifalia_client:
                if progress_callback:
                    progress_callback(stats, f"Fetching information from Verifalia for {candidate} ({settings.verification_quality})")
                try:
                    verification = verifalia_client.verify_email(candidate, settings.verification_quality)
                    log_row[classification_keys[email_col_index]] = verification.classification
                except VerifaliaCreditsExhausted as credit_error:
                    if settings.stop_on_verifalia_credits_exhausted:
                        fatal_error = str(credit_error)
                        log_row["send_result"] = "Failed"
                        log_row["error_message"] = str(credit_error)
                        stats.failed_count += 1
                        log_rows.append(log_row)
                        break
                    verification_enabled_runtime = False
                    log_row["verification_enabled"] = False
                    verification = None

                if fatal_error:
                    break

                if verification and verification.is_sendable:
                    if progress_callback:
                        progress_callback(stats, f"Verifalia accepted {candidate} as {verification.classification}")
                    selected_email = candidate
                    selected_classification = verification.classification
                    break
                continue

            log_row[classification_keys[email_col_index]] = "BasicFormatValid"
            if progress_callback:
                progress_callback(stats, f"Verification OFF, using basic-format email: {candidate}")
            selected_email = candidate
            selected_classification = "BasicFormatValid"
            break

        if fatal_error:
            break

        if not selected_email:
            log_row["send_result"] = "Skipped"
            log_row["error_message"] = "No_Valid_Email_Found"
            log_row["final_classification"] = "No_Valid_Email_Found"
            stats.skipped_count += 1
            log_rows.append(log_row)
            continue

        rendered_subject = render_template(row_data.get("subject", ""), row_data)
        rendered_body = render_template(row_data.get("body", ""), row_data)

        if progress_callback:
            progress_callback(stats, f"Sending email to {selected_email} from {sender}")
        send_response = graph_client.send_mail(
            sender=sender,
            recipient_email=selected_email,
            subject=rendered_subject,
            body=rendered_body,
            content_type="HTML" if settings.send_as_html else "Text",
        )
        log_row["send_attempted"] = True
        log_row["selected_email"] = selected_email
        log_row["send_status_code"] = send_response.status_code
        log_row["final_classification"] = selected_classification

        if send_response.ok:
            if progress_callback:
                progress_callback(stats, f"Sent email successfully to {selected_email}")
            log_row["send_result"] = "Sent"
            stats.sent_count += 1
        else:
            if progress_callback:
                progress_callback(stats, f"Send failed for {selected_email} with status {send_response.status_code}")
            log_row["send_result"] = "Failed"
            log_row["error_message"] = send_response.error_message or "Send_Failed"
            stats.failed_count += 1

        log_rows.append(log_row)

        delay = random.randint(settings.delay_min_seconds, settings.delay_max_seconds)
        sender_next_available_epoch[sender] = time.time() + delay
        if progress_callback:
            progress_callback(stats, f"Mailbox {sender} delay started for {delay} seconds")

    log_path = make_log_path(OUTPUT_DIR)
    write_logs(log_path, log_rows)

    if progress_callback:
        progress_callback(stats, "Completed")
    return stats, log_rows, log_path, fatal_error


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Cybernara outreach campaign")
    parser.add_argument("--input", required=True, help="Path to leads CSV")
    parser.add_argument("--verify", action="store_true", help="Enable Verifalia verification")
    parser.add_argument("--quality", default="High", choices=["Standard", "High", "Extreme"])
    parser.add_argument("--max", type=int, default=50, dest="max_emails")
    parser.add_argument("--delay-min", type=int, default=300)
    parser.add_argument("--delay-max", type=int, default=720)
    parser.add_argument("--no-defer", action="store_true", help="Send even outside business hours")
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> int:
    load_env()
    args = parse_args(argv or sys.argv[1:])
    leads_path = Path(args.input)
    if not leads_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {leads_path}")

    settings = CampaignSettings(
        verification_enabled=args.verify,
        verification_quality=args.quality,
        max_emails_per_run=args.max_emails,
        delay_min_seconds=args.delay_min,
        delay_max_seconds=args.delay_max,
        defer_outside_business_hours=not args.no_defer,
    )
    dataframe = pd.read_csv(leads_path)
    stats, _, log_path, fatal_error = process_campaign(dataframe, settings)

    print(f"Sent: {stats.sent_count}")
    print(f"Skipped: {stats.skipped_count}")
    print(f"Deferred: {stats.deferred_count}")
    print(f"Failed: {stats.failed_count}")
    print(f"Log: {log_path}")
    if fatal_error:
        print(f"Error: {fatal_error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
