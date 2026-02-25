from __future__ import annotations

import time
from dataclasses import dataclass

import requests


TOKEN_URL_TEMPLATE = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
GRAPH_SEND_URL_TEMPLATE = "https://graph.microsoft.com/v1.0/users/{sender}/sendMail"


@dataclass
class SendResponse:
    status_code: int
    ok: bool
    error_message: str | None = None


class GraphClient:
    def __init__(self, tenant_id: str, client_id: str, client_secret: str, timeout: int = 30):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout = timeout
        self._access_token: str | None = None
        self._expires_at_epoch: float = 0

    def _token_expired(self) -> bool:
        return not self._access_token or time.time() >= self._expires_at_epoch - 60

    def _fetch_token(self) -> None:
        token_url = TOKEN_URL_TEMPLATE.format(tenant_id=self.tenant_id)
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        }
        response = requests.post(token_url, data=payload, timeout=self.timeout)
        response.raise_for_status()
        token_payload = response.json()

        self._access_token = token_payload["access_token"]
        self._expires_at_epoch = time.time() + int(token_payload.get("expires_in", 3599))

    def _get_token(self) -> str:
        if self._token_expired():
            self._fetch_token()
        return self._access_token  # type: ignore[return-value]

    def send_mail(
        self,
        sender: str,
        recipient_email: str,
        subject: str,
        body: str,
        content_type: str = "Text",
    ) -> SendResponse:
        body_payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": content_type, "content": body},
                "toRecipients": [{"emailAddress": {"address": recipient_email}}],
            },
            "saveToSentItems": "true",
        }

        def do_send() -> requests.Response:
            token = self._get_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            url = GRAPH_SEND_URL_TEMPLATE.format(sender=sender)
            return requests.post(url, json=body_payload, headers=headers, timeout=self.timeout)

        response = do_send()

        if response.status_code == 401:
            self._fetch_token()
            retry = do_send()
            if retry.status_code == 202:
                return SendResponse(202, True)
            if retry.status_code == 401:
                return SendResponse(401, False, "Send_Failed_401")
            return SendResponse(retry.status_code, False, retry.text[:300])

        if response.status_code == 429:
            time.sleep(120)
            retry = do_send()
            if retry.status_code == 202:
                return SendResponse(202, True)
            return SendResponse(retry.status_code, False, retry.text[:300])

        if 500 <= response.status_code <= 599:
            time.sleep(30)
            retry = do_send()
            if retry.status_code == 202:
                return SendResponse(202, True)
            return SendResponse(retry.status_code, False, retry.text[:300])

        if response.status_code == 202:
            return SendResponse(202, True)

        return SendResponse(response.status_code, False, response.text[:300])
