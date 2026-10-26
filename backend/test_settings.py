"""Test settings: unit tests run on local SQLite.

The project's database is a remote Neon instance, and letting Django create a
test database there is slow enough to hang a test run. The suites under these
settings are SimpleTestCase-based (no database) plus mocked service tests, so a
local in-memory database is all that is needed:

    python manage.py test accounts cart orders --settings=test_settings

Live, end-to-end verification against the real database is done separately
against the running application, never through these settings.
"""
from config.settings import *  # noqa: F401,F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}
