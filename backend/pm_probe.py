import requests
import re

url = "https://cityofvictoria.perfectmind.com/23902/Clients/BookMe4?widgetId=15f6af07-39c5-473e-b053-96653f77a406"
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)"
}
try:
    r = requests.get(url, headers=headers)
    print("Status:", r.status_code)
    
    api_urls = set(re.findall(r'/[\w\d]+/Clients/BookMe[^"\']+', r.text))
    print("Found endpoints:")
    for url in api_urls:
        print(url)

            
except Exception as e:
    print(e)
