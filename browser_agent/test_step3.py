"""
Step 3 verification script — tests BrowserRecorder.
Run from: c:\Projects\Antigravity Browsing agent\browser_agent\
Usage: python test_step3.py

A browser will open at https://the-internet.herokuapp.com/login
Fill in the login form (username: tomsmith, password: SuperSecretPassword!)
The browser auto-closes after 20 seconds.
"""
import asyncio
import sys
from core.recorder import BrowserRecorder

sys.stdout.reconfigure(encoding='utf-8')


async def test():
    r = BrowserRecorder(
        "https://the-internet.herokuapp.com/login",
        "test_app",
        "./screenshots"
    )
    print("=" * 55)
    print("Browser will open. Fill the login form.")
    print("Credentials: tomsmith / SuperSecretPassword!")
    print("Auto-closes in 20 seconds.")
    print("=" * 55)

    try:
        await asyncio.wait_for(r.start_session(), timeout=20)
    except (asyncio.TimeoutError, KeyboardInterrupt):
        pass

    session = await r.stop_session()
    events = session.get("events", [])
    navigations = session.get("navigations", [])

    print(f"\nEvents captured  : {len(events)}")
    print(f"Navigations      : {len(navigations)}")

    if len(events) > 0:
        print("\nSample events:")
        for ev in events[:5]:
            print(f"  [{ev.get('event_type','?')}] "
                  f"<{ev.get('tag','?')}> "
                  f"id={ev.get('id','—')} "
                  f"name={ev.get('name','—')} "
                  f"value={str(ev.get('value','—'))[:20]}")
        print("\nRecorder OK")
    else:
        print("\nFAIL - No events captured!")


asyncio.run(test())
