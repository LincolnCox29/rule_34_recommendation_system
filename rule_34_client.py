import aiohttp

class Rule_34_client:

    def __init__(self):
        self.session = None

    async def start(self):
        self.session = aiohttp.ClientSession(
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

    async def close(self):
        await self.session.close()

    async def search(self, params):
        async with self.session.get(
            "https://api.rule34.xxx/index.php",
            params=params
        ) as response:

            return await response.json()
        
R34_CLIENT: Rule_34_client = Rule_34_client()