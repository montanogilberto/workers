import requests

url = "https://api.mercadolibre.com/sites/MLM/search"
params = {"q": "smartphones", "offset": 0, "limit": 10}

headers = {
    "Accept": "application/json",
    "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.mercadolibre.com.mx/",
    "Origin": "https://www.mercadolibre.com.mx",
}

s = requests.Session()
s.headers.update(headers)

r = s.get(url, params=params, timeout=30)

print("STATUS:", r.status_code)
print("x-request-id:", r.headers.get("x-request-id"))
print("x-cache:", r.headers.get("x-cache"))
print("via:", r.headers.get("via"))
print("BODY:", r.text[:500])
