from websockets import serve as start_ws
import asyncio


async def handler(websocket):
    async for message in websocket:
        await websocket.send(message)


async def main():
    async with start_ws(handler, "127.0.0.1", 8765):
        await asyncio.Future()


asyncio.run(main())
