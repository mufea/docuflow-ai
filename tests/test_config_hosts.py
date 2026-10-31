from docuflow.config import Settings


def test_trusted_hosts_include_render_hostname(monkeypatch) -> None:
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", "docuflow-api.onrender.com")
    monkeypatch.setenv("DOCUFLOW_TRUSTED_HOSTS", "127.0.0.1,localhost")
    settings = Settings()
    assert "docuflow-api.onrender.com" in settings.trusted_host_list
    assert ".onrender.com" in settings.trusted_host_list


def test_cors_includes_public_web_url() -> None:
    settings = Settings(
        cors_origins="http://127.0.0.1:43123",
        public_web_url="https://docuflow-web.onrender.com",
    )
    assert "https://docuflow-web.onrender.com" in settings.cors_origin_list


def test_render_external_url_fills_localhost_public_api(monkeypatch) -> None:
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://docuflow-api.onrender.com")
    settings = Settings(public_api_url="http://127.0.0.1:43124")
    assert settings.public_api_url == "https://docuflow-api.onrender.com"
