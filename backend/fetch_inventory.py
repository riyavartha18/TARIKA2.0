import requests, json, sys
url = 'http://127.0.0.1:8000/api/demand-prediction/slow-inventory/'
resp = requests.get(url)
print('Status:', resp.status_code)
print(resp.text[:1000])

