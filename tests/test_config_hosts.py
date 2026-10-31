from docuflow.config import Settings
from docuflow.security.hosts import host_is_allowed


def test_host_matching_supports_onrender_suffix_and_ports() -> None:
    allowed = [".onrender.com", "pdf.example.com"]
    assert host_is_allowed("docuflow-api.onrender.com", allowed)
    assert host_is_allowed("docuflow-api.onrender.com:10000", allowed)
    assert host_is_allowed("pdf.example.com", allowed)
    assert not host_is_allowed("evil.example", allowed)


def test_production_always_trusts_onrender(monkeypatch) -> None:
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("RENDER_EXTERNAL_HOSTNAME", raising=False)
    monkeypatch.delenv("RENDER_EXTERNAL_URL", raising=False)
    settings = Settings(
        env="production",
        trusted_hosts="127.0.0.1,localhost",
        public_api_url="http://127.0.0.1:43124",
        public_web_url="http://127.0.0.1:43123",
        cors_origins="http://127.0.0.1:43123",
    )
    assert ".onrender.com" in settings.trusted_host_list


def test_trusted_hosts_include_cors_custom_domain() -> None:
    settings = Settings(
        trusted_hosts="127.0.0.1",
        cors_origins="https://pdf.example.com",
        public_web_url="http://127.0.0.1:43123",
    )
    assert "pdf.example.com" in settings.trusted_host_list


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
