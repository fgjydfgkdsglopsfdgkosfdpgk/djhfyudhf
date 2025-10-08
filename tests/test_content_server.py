from __future__ import annotations

from urllib.parse import urlparse


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


def test_unknown_site_returns_404(client):
    response = client.get("/unknown/", headers={"Host": "example.com"})
    assert response.status_code == 404


def test_traversal_blocked(client):
    response = client.get("/../run.py", headers={"Host": "example.com"})
    assert response.status_code == 404


def test_invalid_segment_blocked(client):
    response = client.get("/site1/../../etc/passwd", headers={"Host": "example.com"})
    assert response.status_code == 404
