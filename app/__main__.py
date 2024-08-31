import asyncio

from app.main import RenaleServer


if __name__ == "__main__":
    server = RenaleServer(host="127.0.0.1", port=9789)
    asyncio.run(server.start())
