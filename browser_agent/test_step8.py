import asyncio
from storage.db import Database
from schema import ApplicationModel

async def test():
    db = Database('./browser_agent.db')
    apps = await db.list_applications()
    print(f'Apps in DB: {len(apps)}')
    for app in apps:
        print(f'  - {app["name"]} | {app["base_url"]}')
    print('Storage OK')

asyncio.run(test())
