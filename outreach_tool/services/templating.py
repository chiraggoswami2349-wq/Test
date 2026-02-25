from __future__ import annotations

from typing import Mapping


def render_template(template: str, values: Mapping[str, str]) -> str:
    rendered = template or ""
    for key in ("name", "company", "sender", "country"):
        rendered = rendered.replace(f"{{{{{key}}}}}", str(values.get(key, "")))
    return rendered
