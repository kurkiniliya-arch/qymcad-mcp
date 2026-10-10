"""Open or reconnect to the desktop, leaving it open when this launcher exits."""
import asyncio
import json
from bridge import BASE
from live import LiveBridge

async def main():
    bridge = LiveBridge(BASE / "models")
    try:
        print(json.dumps(await bridge.status(), indent=2))
    finally:
        bridge.close()

if __name__ == "__main__":
    asyncio.run(main())
