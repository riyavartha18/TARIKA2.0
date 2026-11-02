import os
import sys
import io
import time

print("Step 1: Setting up paths", flush=True)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(BASE_DIR, 'backend')
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, BASE_DIR)
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'

print("Step 2: Configuring SQLite", flush=True)
import django
from django.conf import settings
settings.DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

print("Step 3: Calling django.setup()", flush=True)
t0 = time.time()
django.setup()
print(f"django.setup() took {time.time()-t0:.2f}s", flush=True)

print("Step 4: Importing models", flush=True)
from catalog.models import Product
from orders.models import Order
from digital_wardrobe.models import WardrobeItem

print("Step 5: Testing cutout", flush=True)
from digital_wardrobe.cutout import CutoutProcessor
print("Step 5 done", flush=True)

print("ALL DIAGNOSTIC STEPS COMPLETED!", flush=True)
