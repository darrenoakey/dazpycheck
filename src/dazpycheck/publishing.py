from __future__ import annotations

from daz_secrets import Client


def pypi_token(service: str = "pypi", account: str = "api_token") -> str:
    raw = Client().get(service, account).value
    if not raw:
        raise RuntimeError(f"credential {service}/{account} is empty")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeError(f"credential {service}/{account} is not UTF-8") from exc
