from __future__ import annotations

from urllib.parse import urlparse

import pytest


@pytest.mark.parametrize(
    "path, expected_substring",
    [
        ("/", "<base href=\"/\">") ,
        ("/extra.html", "Extra"),
    ],
)
def test_global_html_served(client, path, expected_substring):
    response = client.get(path)
    assert response.status_code == 200
    assert expected_substring in response.get_data(as_text=True)


def test_global_static_served(client):
    response = client.get("/static/app.css")
    assert response.status_code == 200
    assert "color" in response.get_data(as_text=True)


def test_directory_redirect(client):
    response = client.get("/site", follow_redirects=False)
    assert response.status_code == 301
    location = response.headers["Location"]
    parsed = urlparse(location)
    assert parsed.path == "/site/"


def test_subdirectory_html(client):
    response = client.get("/site/page.html")
    assert response.status_code == 200
    assert "Site page" in response.get_data(as_text=True)
    assert '<base href="/site/">' in response.get_data(as_text=True)


def test_subdirectory_static(client):
    response = client.get("/site/static/site.css")
    assert response.status_code == 200
    assert "blue" in response.get_data(as_text=True)


def test_subdomain_html(client):
    response = client.get("/", headers={"Host": "blog.localhost"})
    assert response.status_code == 200
    assert "Blog" in response.get_data(as_text=True)


def test_subdomain_static(client):
    response = client.get("/static/blog.css", headers={"Host": "blog.localhost"})
    assert response.status_code == 200
    assert "red" in response.get_data(as_text=True)


def test_traversal_blocked(client):
    # ``safe_join`` should ensure that attempts to traverse outside are blocked.
    response = client.get("/../run.py")
    assert response.status_code == 404


def test_invalid_segment_blocked(client):
    response = client.get("/../../secret")
    assert response.status_code == 404
