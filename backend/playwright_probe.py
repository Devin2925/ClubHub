import asyncio
import json
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        categories = []
        class_data = []

        async def handle_response(response):
            if "GetCategoriesDataV2" in response.url:
                try:
                    text = await response.text()
                    data = json.loads(text)
                    for cat in data:
                        for cal in cat.get("Calendars", []):
                            link = cal.get("BookingLink")
                            if link:
                                categories.append(link)
                except Exception:
                    pass
            elif "Classes" in response.url or "Calendar" in response.url or "Event" in response.url:
                try:
                    text = await response.text()
                    if text.startswith('{') or text.startswith('['):
                        if len(text) > 500:
                            data = json.loads(text)
                            if 'classes' in data and len(data['classes']) > 0:
                                class_data.append(data['classes'][0])
                except Exception:
                    pass

        page.on("response", handle_response)
        
        URL = "https://cityofvictoria.perfectmind.com/23902/Clients/BookMe4?widgetId=15f6af07-39c5-473e-b053-96653f77a406"
        print("Navigating to start page...")
        await page.goto(URL, wait_until="networkidle")
        await page.wait_for_timeout(2000)
        
        print(f"Found {len(categories)} calendars. Visiting first one...")
        if categories:
            test_link = "https://cityofvictoria.perfectmind.com" + categories[0]
            print(f"Navigating to {test_link}")
            await page.goto(test_link, wait_until="networkidle")
            await page.wait_for_timeout(3000)
            
            if class_data:
                print("Extracted Class Data sample!")
                print(json.dumps(class_data[-1], indent=2))


        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
