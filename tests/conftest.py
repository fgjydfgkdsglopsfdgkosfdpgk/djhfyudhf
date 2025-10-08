from __future__ import annotations

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app


@pytest.fixture()
def content_root(tmp_path: Path) -> Path:
    root = tmp_path

    main_site = root / "_"
    main_site.mkdir()
    (main_site / "index.html").write_text(
        """
        <html><head><title>Example Home</title><link rel=\"stylesheet\" href=\"index.css\"></head>
        <body><h1>Example.com</h1><p>Welcome to the main site.</p><script src=\"index.js\"></script></body>
        </html>
        """.strip(),
        encoding="utf-8",
    )
    (main_site / "index.css").write_text("body { color: #123456; }", encoding="utf-8")
    (main_site / "index.js").write_text(
        "window.__siteLoaded = 'root';",
        encoding="utf-8",
    )

    site1 = root / "site1"
    site1.mkdir()
    (site1 / "index.html").write_text(
        """
        <html><head><title>Site One</title><link rel=\"stylesheet\" href=\"index.css\"></head>
        <body><h1>Site 1</h1><p>Subsite available via path and subdomain.</p><script src=\"index.js\"></script></body>
        </html>
        """.strip(),
        encoding="utf-8",
    )
    (site1 / "index.css").write_text("body { color: #abcdef; }", encoding="utf-8")
    (site1 / "index.js").write_text(
        "document.body.innerHTML += '<span id=\\'site1-status\\'></span>';",
        encoding="utf-8",
    )

    return root


@pytest.fixture()
def app(content_root: Path):
    application = create_app(content_root)
    application.config.update(TESTING=True)
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()
