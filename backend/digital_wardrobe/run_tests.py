import os
import sys
import io

# Setup stdout utf-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(BASE_DIR, 'backend')
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, BASE_DIR)

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
os.environ['DISABLE_REMBG'] = 'true'

import django
from django.conf import settings

# Override to SQLite in-memory for lightning-fast, isolated testing without remote Neon pooler locks
settings.DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

django.setup()

from django.db import connection
from django.core.management import call_command
from catalog.models import Product, Category
from accounts.models import Customer
from orders.models import Order
from recommendations.models import ProductRecommendation
from digital_wardrobe.models import (
    WardrobeItem,
    WardrobeMatch,
    WardrobeOutfit,
    WardrobeCollection,
    WardrobeNotificationLog
)

if __name__ == '__main__':
    print("=====================================================================", flush=True)
    print("RUNNING DIGITAL WARDROBE COMPREHENSIVE TEST SUITE", flush=True)
    print("=====================================================================", flush=True)
    
    # Create required test tables
    models_to_create = [
        Customer,
        Product,
        ProductRecommendation,
        Order,
        WardrobeItem,
        WardrobeMatch,
        WardrobeOutfit,
        WardrobeCollection,
        WardrobeNotificationLog
    ]
    with connection.schema_editor() as editor:
        for m in models_to_create:
            try:
                editor.create_model(m)
            except Exception as e:
                # Table might already exist
                pass

    import unittest
    suite = unittest.defaultTestLoader.loadTestsFromName('digital_wardrobe.tests')
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        print(f"FAILED: {len(result.failures)} failure(s), {len(result.errors)} error(s).", flush=True)
        sys.exit(1)
    else:
        print(f"\nALL {result.testsRun} DIGITAL WARDROBE TESTS PASSED SUCCESSFULLY!", flush=True)
        sys.exit(0)
