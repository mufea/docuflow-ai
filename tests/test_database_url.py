from docuflow.dsn import normalize_database_url


def test_render_postgres_url_uses_psycopg3() -> None:
    raw = "postgres://docuflow:secret@dpg-host:5432/docuflow"
    assert normalize_database_url(raw) == "postgresql+psycopg://docuflow:secret@dpg-host:5432/docuflow"


def test_postgresql_url_uses_psycopg3() -> None:
    raw = "postgresql://docuflow:secret@localhost/docuflow?sslmode=require"
    assert (
        normalize_database_url(raw) == "postgresql+psycopg://docuflow:secret@localhost/docuflow?sslmode=require"
    )


def test_explicit_psycopg_and_sqlite_urls_are_unchanged() -> None:
    psycopg = "postgresql+psycopg://docuflow:dev@127.0.0.1:5432/docuflow"
    sqlite = "sqlite+pysqlite:///./data/docuflow.db"
    assert normalize_database_url(psycopg) == psycopg
    assert normalize_database_url(sqlite) == sqlite
