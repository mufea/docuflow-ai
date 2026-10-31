"""Database URL helpers. Keep this module free of Settings/engine imports."""


def normalize_database_url(url: str) -> str:
    """Use psycopg3 for Render/libpq URLs. postgres:// defaults to missing psycopg2."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url
