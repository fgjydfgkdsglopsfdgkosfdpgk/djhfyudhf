def test_ui_account_and_site_flow(app, client, notifier):
    response = client.post(
        "/ui/register",
        data={"display_name": "Alice", "email": "alice@example.com"},
        follow_redirects=True,
    )
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Аккаунт создан" in body

    accounts = app.config["ACCOUNT_STORE"]
    registry = app.config["SITE_REGISTRY"]

    account = next(iter(accounts.list_accounts().values()))

    response = client.post(
        "/ui/sites/new",
        data={
            "name": "mysite",
            "html": "<html><body><h1>My Site</h1></body></html>",
            "css": "body { background: #fff; }",
            "js": "console.log('mysite');",
        },
        follow_redirects=True,
    )
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Сайт mysite создан" in body
    assert notifier.pending[-1] == "mysite"

    record = registry.get("mysite")
    registry.approve("mysite")
    assert registry.get("mysite").active_version is not None

    response = client.get("/ui/sites/mysite")
    assert "Состояние:" in response.get_data(as_text=True)

    response = client.post(
        "/ui/sites/mysite",
        data={
            "action": "update",
            "html": "<html><body><h1>Updated</h1></body></html>",
            "css": "body { color: red; }",
            "js": "console.log('updated');",
        },
        follow_redirects=True,
    )
    body = response.get_data(as_text=True)
    assert "Контент обновлён" in body
    assert notifier.pending[-1] == "mysite"

    registry.approve("mysite")
    record = registry.get("mysite")
    latest_version = record.active_version
    versions = list(record.versions.keys())
    assert len(versions) >= 2
    first_version = versions[0]

    response = client.post(
        "/ui/sites/mysite",
        data={"action": "set_active", "version_id": first_version},
        follow_redirects=True,
    )
    body = response.get_data(as_text=True)
    assert "Версия активирована" in body
    assert registry.get("mysite").active_version == first_version

    response = client.post(
        "/ui/sites/mysite",
        data={"action": "delete_version", "version_id": latest_version},
        follow_redirects=True,
    )
    body = response.get_data(as_text=True)
    assert "Версия удалена" in body

    response = client.post(
        "/ui/support",
        data={"subject": "Help", "message": "Need assistance"},
        follow_redirects=True,
    )
    body = response.get_data(as_text=True)
    assert "Сообщение отправлено" in body
    support = app.config["SUPPORT_STORE"]
    assert any(msg.account_id == account.id for msg in support.list_messages())

    response = client.post(
        "/ui/settings",
        data={"display_name": "Alice Updated", "email": "new@example.com"},
        follow_redirects=True,
    )
    body = response.get_data(as_text=True)
    assert "Настройки обновлены" in body
    assert accounts.get(account.id).display_name == "Alice Updated"

    response = client.post(
        "/ui/sites/mysite",
        data={"action": "delete_site"},
        follow_redirects=True,
    )
    body = response.get_data(as_text=True)
    assert "Сайт удалён" in body
    assert registry.get("mysite") is None
