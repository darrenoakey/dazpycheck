# dazpycheck: ignore-banned-words
from uuid import uuid4

import pytest
from daz_secrets import Client, DazSecretsError, ErrorCode

from dazpycheck.publishing import pypi_token


def test_pypi_token_round_trips_through_configured_provider() -> None:
    service = f"dazpycheck-publish-test-{uuid4()}"
    account = "api_token"
    client = Client()
    try:
        client.set(service, account, b"provider-only-token")
        assert pypi_token(service, account) == "provider-only-token"
    finally:
        try:
            client.delete(service, account)
        except DazSecretsError as exc:
            if exc.code is not ErrorCode.NOT_FOUND:
                raise


@pytest.mark.parametrize("value", [b"", b"\xff"])
def test_pypi_token_rejects_malformed_values(value: bytes) -> None:
    service = f"dazpycheck-publish-test-{uuid4()}"
    account = "api_token"
    client = Client()
    try:
        client.set(service, account, value)
        with pytest.raises(RuntimeError):
            pypi_token(service, account)
    finally:
        client.delete(service, account)
