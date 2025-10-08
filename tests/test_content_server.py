from __future__ import annotations

from urllib.parse import urlparse


def _create_site(client, name="pending", owner_id="user-1"):
    response = client.post(
        "/api/sites",
        json={
            "name": name,
            "owner_id": owner_id,
            "html": "<html><head><title>{}</title><link rel=\"stylesheet\" href=\"index.css\"></head><body><h1>{}</h1><script src=\"index.js\"></script></body></html>".format(
                name, name
            ),
            "css": "body { background: #fff; }",
            "js": "window.__siteLoaded = '%s';" % name,
        },
        headers={"Host": "example.com"},
    )
    assert response.status_code == 201
    payload = response.get_json()
    return payload


def test_notifier_records_pending(client, notifier):
    payload = _create_site(client, name="notify")
    assert "notify" in notifier.pending
    assert payload["status"] == "pending"


def test_update_triggers_pending_notification(client, notifier):
    payload = _create_site(client, name="update-me")
    owner_token = payload["owner_token"]
    notifier.pending.clear()

    response = client.put(
        "/api/sites/update-me/content",
        headers={"Host": "example.com", "X-Owner-Token": owner_token},
        json={"html": "h", "css": "c", "js": "j"},
    )
    assert response.status_code == 200
    assert notifier.pending[-1] == "update-me"


def test_main_site_html(client):
    response = client.get("/", headers={"Host": "example.com"})
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Example.com" in body
    assert '<base href="/">' in body


def test_main_site_script(client):
    response = client.get("/index.js", headers={"Host": "example.com"})
    assert response.status_code == 200
    assert "__siteLoaded" in response.get_data(as_text=True)


def test_path_site_redirect(client):
    response = client.get("/site1", headers={"Host": "example.com"}, follow_redirects=False)
    assert response.status_code == 301
    parsed = urlparse(response.headers["Location"])
    assert parsed.path == "/site1/"


def test_path_site_html(client):
    response = client.get("/site1/", headers={"Host": "example.com"})
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Site 1" in body
    assert '<base href="/site1/">' in body


def test_path_site_script(client):
    response = client.get("/site1/index.js", headers={"Host": "example.com"})
    assert response.status_code == 200
    assert "site1-status" in response.get_data(as_text=True)


def test_subdomain_html(client):
    response = client.get("/", headers={"Host": "site1.example.com"})
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Site 1" in body
    assert '<base href="/">' in body


def test_subdomain_script(client):
    response = client.get("/index.js", headers={"Host": "site1.example.com"})
    assert response.status_code == 200
    assert "site1-status" in response.get_data(as_text=True)


def test_unknown_site_returns_invitation(client):
    response = client.get("/unknown/", headers={"Host": "example.com"})
    body = response.get_data(as_text=True)
    assert response.status_code == 404
    assert "этот поддомен может быть вашим" in body.lower()


def test_unknown_subdomain_returns_invitation(client):
    response = client.get("/", headers={"Host": "ghost.example.com"})
    body = response.get_data(as_text=True)
    assert response.status_code == 404
    assert "этот поддомен может быть вашим" in body.lower()


def test_missing_resource_in_registered_site_404(client):
    response = client.get("/site1/missing.js", headers={"Host": "example.com"})
    assert response.status_code == 404


def test_traversal_blocked(client):
    response = client.get("/../run.py", headers={"Host": "example.com"})
    assert response.status_code == 404


def test_invalid_segment_blocked(client):
    response = client.get("/site1/../../etc/passwd", headers={"Host": "example.com"})
    assert response.status_code == 404


def test_pending_site_requires_preview_token(client, notifier):
    payload = _create_site(client, name="beta")
    preview_token = payload["preview_token"]

    response = client.get("/beta/", headers={"Host": "example.com"})
    assert response.status_code == 403
    assert "ожидает модерации" in response.get_data(as_text=True)

    response = client.get(
        "/beta/",
        headers={"Host": "example.com", "X-Preview-Token": preview_token},
    )
    assert response.status_code == 200
    assert "beta" in response.get_data(as_text=True)

    approve = client.post(
        "/api/sites/beta/approve",
        headers={"Host": "example.com", "X-Admin-Token": "admintoken"},
    )
    assert approve.status_code == 200
    assert "beta" in notifier.approved

    response = client.get("/beta/", headers={"Host": "example.com"})
    assert response.status_code == 200
    assert "beta" in response.get_data(as_text=True)


def test_rejected_site_freezes_updates(client, notifier):
    payload = _create_site(client, name="gamma")
    owner_token = payload["owner_token"]

    reject = client.post(
        "/api/sites/gamma/reject",
        headers={"Host": "example.com", "X-Admin-Token": "admintoken"},
    )
    assert reject.status_code == 200
    assert "gamma" in notifier.rejected

    blocked = client.put(
        "/api/sites/gamma/content",
        headers={"Host": "example.com", "X-Owner-Token": owner_token},
        json={"html": "h", "css": "c", "js": "j"},
    )
    assert blocked.status_code == 403

    response = client.get("/gamma/", headers={"Host": "example.com"})
    assert response.status_code == 403
    assert "отклонён" in response.get_data(as_text=True)


def test_preview_token_rotates_on_update(client):
    payload = _create_site(client, name="delta")
    owner_token = payload["owner_token"]
    preview_token = payload["preview_token"]

    response = client.put(
        "/api/sites/delta/content",
        headers={"Host": "example.com", "X-Owner-Token": owner_token},
        json={
            "html": "<html><head><title>delta</title><link rel=\"stylesheet\" href=\"index.css\"></head><body><h1>delta</h1><script src=\"index.js\"></script></body></html>",
            "css": "body { color: red; }",
            "js": "window.__siteLoaded='delta2';",
        },
    )
    assert response.status_code == 200
    updated = response.get_json()
    assert updated["preview_token"] != preview_token
    new_preview = updated["preview_token"]

    response = client.get("/delta/", headers={"Host": "example.com"})
    assert response.status_code == 403

    response = client.get(
        "/delta/",
        headers={"Host": "example.com", "X-Preview-Token": preview_token},
    )
    assert response.status_code == 403

    response = client.get(
        "/delta/",
        headers={"Host": "example.com", "X-Preview-Token": new_preview},
    )
    assert response.status_code == 200
    assert "delta" in response.get_data(as_text=True)
