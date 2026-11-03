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

# `catalog`'s migrations only ALTER the pre-existing dataset tables `products`
# and `categories`, which exist on the live Neon database and nowhere else, so
# replaying them on the SQLite test database fails on a missing table before any
# test can run. Skipping that app's migrations lets Django create its tables
# straight from the models instead; every other app - including the managed
# `rfm_analysis` campaign tables - is still migrated, so a new migration is
# genuinely exercised by the test run.
MIGRATION_MODULES = {'catalog': None}
