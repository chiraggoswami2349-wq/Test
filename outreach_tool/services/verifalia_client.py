from __future__ import annotations

from dataclasses import dataclass

import requests


@dataclass
class VerificationResult:
    classification: str
    is_sendable: bool
    error_message: str | None = None


class VerifaliaCreditsExhausted(Exception):
    pass


class VerifaliaClient:
    def __init__(self, username: str, password: str, timeout: int = 45):
        self.username = username
        self.password = password
        self.timeout = timeout

    def verify_email(self, email: str, quality: str = "High") -> VerificationResult:
        url = "https://api.verifalia.com/v2.6/email-validations"
        payload = {
            "entries": [{"inputData": email}],
            "quality": quality.title(),
        }
        response = requests.post(
            url,
            json=payload,
            auth=(self.username, self.password),
            timeout=self.timeout,
        )

        if response.status_code == 402:
            raise VerifaliaCreditsExhausted("Verifalia credits exhausted (HTTP 402).")

        if response.status_code >= 400:
            return VerificationResult("Error", False, f"Verifalia_HTTP_{response.status_code}")

        data = response.json()
        entries = data.get("entries", [])
        if not entries:
            return VerificationResult("Unknown", False, "No entries returned by Verifalia")

        classification = entries[0].get("classification", "Unknown")
        is_sendable = classification in {"Deliverable", "Risky"}
        return VerificationResult(classification, is_sendable)
