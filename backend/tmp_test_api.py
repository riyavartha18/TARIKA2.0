import os, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE','backend.settings')
import django
django.setup()
from django.test import Client
c=Client()
resp=c.get('/api/demand-prediction/slow-inventory/')
print('status', resp.status_code)
print('keys', resp.json().keys())
print('items count', len(resp.json().get('items',[])))
if resp.json().get('items'):
    print('first item', json.dumps(resp.json()['items'][0], indent=2)[:500])

