"""Test-only settings: run the suite on in-memory SQLite (no MySQL needed)."""
from studentdb.settings import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
