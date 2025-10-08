from __future__ import annotations

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app


@pytest.fixture()
def content_root(tmp_path: Path) -> Path:
    root = tmp_path

    html_dir = root / "html"
    html_dir.mkdir()
    (html_dir / "index.html").write_text("<html><head><title>Root</title></head><body>Root</body></html>", encoding="utf-8")
    (html_dir / "extra.html").write_text("<html><body>Extra</body></html>", encoding="utf-8")

    static_dir = root / "static"
    static_dir.mkdir()
    (static_dir / "app.css").write_text("body { color: #333; }", encoding="utf-8")

    site_dir = root / "site"
    (site_dir / "html").mkdir(parents=True)
    (site_dir / "html" / "index.html").write_text("<html><body>Site</body></html>", encoding="utf-8")
    (site_dir / "html" / "page.html").write_text("<html><body>Site page</body></html>", encoding="utf-8")
    (site_dir / "static").mkdir()
    (site_dir / "static" / "site.css").write_text("body { color: blue; }", encoding="utf-8")

    sub_dir = root / "blog"
    (sub_dir / "html").mkdir(parents=True)
    (sub_dir / "html" / "index.html").write_text("<html><body>Blog</body></html>", encoding="utf-8")
    (sub_dir / "static").mkdir()
    (sub_dir / "static" / "blog.css").write_text("body { color: red; }", encoding="utf-8")

    return root


@pytest.fixture()
def app(content_root: Path):
    application = create_app(content_root)
    application.config.update(TESTING=True)
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()
