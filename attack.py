import asyncio, httpx, time

URL = "http://localhost:8000/limited"
HEADERS = {"x-api-key": "refill-test"}

async def burst(client, n=20):
    results = await asyncio.gather(*[client.get(URL, headers=HEADERS) for _ in range(n)])
    return [r.status_code for r in results].count(200)

async def main():
    async with httpx.AsyncClient() as client:
        print("First burst:", await burst(client), "allowed (expect ~10)")
        print("Waiting 3 seconds for refill...")
        time.sleep(3)
        print("Second burst:", await burst(client), "allowed (expect ~3)")

asyncio.run(main())