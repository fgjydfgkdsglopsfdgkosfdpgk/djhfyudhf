from urllib.parse import urlparse

import pytest

from app.registry import SiteLifecycle, SiteVersionStatus


@pytest.fixture()
def registry(app):
    return app.config["SITE_REGISTRY"]


@pytest.fixture()
def accounts(app):
    return app.config["ACCOUNT_STORE"]


def test_main_site_html(client):
    response = client.get("/", headers={"Host": "example.com"})
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Example.com" in body
    assert '<base href="/">' in body


def test_path_site_html(client):
    response = client.get("/site1/", headers={"Host": "example.com"})
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Site 1" in body
    assert '<base href="/site1/">' in body


def test_subdomain_html(client):
    response = client.get("/", headers={"Host": "site1.example.com"})
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Site 1" in body


def test_path_redirect(client):
    response = client.get("/site1", headers={"Host": "example.com"}, follow_redirects=False)
    assert response.status_code == 301
    parsed = urlparse(response.headers["Location"])
    assert parsed.path == "/site1/"


def test_unknown_site_invitation(client):
    response = client.get("/ghost/", headers={"Host": "example.com"})
    assert response.status_code == 404
    assert "поддомен" in response.get_data(as_text=True).lower()


def test_pending_preview_requires_token(app, client, registry, notifier):
    record = registry.create_site(
        "beta",
        owner_id="user1",
        html="<html><body><h1>beta</h1></body></html>",
        css="body{color:red;}",
        js="console.log('beta')",
    )
    app.config["MODERATION_NOTIFIER"].site_pending(record)
    pending = record.pending_version()
    assert pending is not None
    assert notifier.pending[-1] == "beta"

    response = client.get("/beta/", headers={"Host": "example.com"})
    assert response.status_code == 403
    assert "ожидает" in response.get_data(as_text=True).lower()

    response = client.get(
        "/beta/",
        headers={"Host": "example.com", "X-Preview-Token": pending.preview_token},
    )
    assert response.status_code == 200
    assert "beta" in response.get_data(as_text=True)

    record = registry.approve("beta")
    app.config["MODERATION_NOTIFIER"].site_approved(record)
    response = client.get("/beta/", headers={"Host": "example.com"})
    assert response.status_code == 200
    assert "beta" in response.get_data(as_text=True)
    assert notifier.approved[-1] == "beta"


def test_reject_blocks_and_freezes_account(app, client, registry, accounts, notifier):
    account = accounts.create("Owner", "owner@example.com")
    record = registry.create_site(
        "gamma",
        owner_id=account.id,
        html="<html><body><h1>gamma</h1></body></html>",
        css="body{color:blue;}",
        js="console.log('gamma')",
    )
    registry.approve("gamma")
    assert registry.get("gamma").lifecycle == SiteLifecycle.ACTIVE

    registry.update_content(
        "gamma",
        owner_token=record.owner_token,
        html="<html><body><h1>gamma2</h1></body></html>",
        css="body{color:green;}",
        js="console.log('gamma2')",
    )
    assert registry.get("gamma").pending_version() is not None

    record = registry.reject("gamma")
    app.config["MODERATION_NOTIFIER"].site_rejected(record)
    assert notifier.rejected[-1] == "gamma"
    assert registry.get("gamma").lifecycle == SiteLifecycle.BLOCKED
    assert accounts.get(account.id).frozen is True

    response = client.get("/gamma/", headers={"Host": "example.com"})
    assert response.status_code == 403
    assert "заблокирован" in response.get_data(as_text=True).lower()


def test_version_history_allows_revert(client, registry, accounts):
    account = accounts.create("Owner", "owner2@example.com")
    record = registry.create_site(
        "delta",
        owner_id=account.id,
        html="<html><body><h1>v1</h1></body></html>",
        css="body{color:black;}",
        js="console.log('v1')",
    )
    registry.approve("delta")
    first_version = registry.get("delta").active_version
    assert first_version

    registry.update_content(
        "delta",
        owner_token=record.owner_token,
        html="<html><body><h1>v2</h1></body></html>",
        css="body{color:orange;}",
        js="console.log('v2')",
    )
    registry.approve("delta")
    record = registry.get("delta")
    assert record.active_version != first_version

    registry.set_active_version(
        "delta",
        owner_token=record.owner_token,
        version_id=first_version,
    )
    response = client.get("/delta/", headers={"Host": "example.com"})
    body = response.get_data(as_text=True)
    assert "v1" in body

    versions = record.versions
    assert all(v.status != SiteVersionStatus.PENDING for v in versions.values())
