from platform import version, system, architecture, release
from typing import Any, Dict, Tuple
from pathlib import Path
import asyncio
import socket
import json

from app.database import Session, app_database
from app.applib import Json
from app.user import User


class RenaleServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 9789):
        self.host = host
        self.port = port
        self.serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.serverSocket.bind((self.host, self.port))
        self.serverSocket.listen(2)
        self.serverSocket.setblocking(False)
        print(f"Server listening on {self.host}:{self.port}")
        session = Session(version(), system(), architecture(), release())
        print(session)

    # region server funcs
    async def handle_http_request(self, conn: socket.socket, addr: Tuple[str, int]) -> None:
        request = await asyncio.get_event_loop().sock_recv(conn, 1024)
        request_text = request.decode("utf-8")

        route, method, headers, body = self.parse_http_request(request_text)
        route_name = route.split("?", maxsplit=1)[0]
        print(f'Connection from {"localhost" if addr[0] == "127.0.0.1" else addr[0]}:{addr[1]}. Method: {method}, Route: {route_name}')
        response = await self.route_request(route, method, body)
        await asyncio.get_event_loop().sock_sendall(conn, response.encode("utf-8"))
        conn.close()

    def parse_http_request(self, request_text: str) -> Tuple[str, str, Json, str]:
        lines = request_text.split("\r\n")
        if not lines or not lines[0]:
            return ("/", "GET", {}, "")

        method, path, _ = lines[0].split(" ")
        headers: Json = {}
        body: str = ""
        i: int = 1

        while i < len(lines) and lines[i] != "":
            key, value = lines[i].split(": ", 1)
            headers[key] = value
            i += 1

        if i < len(lines) - 1:
            body = lines[i + 1]

        return (path, method, headers, body)

    async def route_request(self, route: str, method: str, body: str) -> str:
        response_data: str | Json = ""
        route_data = route.split("?", maxsplit=1)
        route_name = route_data[0]
        # TODO: unused...?
        # route_data = route_data[1] if len(route_data) - 1 else ""
        match method:
            case "GET":
                match route_name:
                    case "/":
                        return self.publish(self.main())
                    case "/status":
                        response_data = self.status()
                    case "/messages":
                        response_data = await self.get_messages(route)
                    case "/chats":
                        response_data = await self.get_chats(route)
                    case "/users":
                        response_data = await self.get_users(route)
                return self.publish(
                    json.dumps(response_data), content_type="application/json"
                )
            case "POST":
                match route_name:
                    case "/send":
                        response_data = await self.send_message(body)
                    case "/newChat":
                        response_data = await self.create_chat(body)
                    case "/register":
                        response_data = await self.register_user(body)
                    case "/login":
                        response_data = await self.login_user(body)
                return self.publish(
                    json.dumps(response_data), content_type="application/json",
                    status_code=200 if response_data["status"] else 400
                )
        return self.publish("404 Not Found", status_code=404)

    def publish(
        self, content: str, status_code: int = 200, content_type: str = "text/html"
    ) -> str:
        response = (
            f"HTTP/1.1 {status_code} OK\r\n"
            + f"Content-Type: {content_type}\r\n"
            + f"Content-Length: {len(content)}\r\n"
            + f"Connection: close\r\n\r\n{content}"
        )
        return response

    async def start(self) -> None:
        loop = asyncio.get_event_loop()
        while True:
            conn, addr = await loop.sock_accept(self.serverSocket)
            await self.handle_http_request(conn, addr)

    # endregion
    # region GET funcs
    def main(self) -> str:
        """
        `main()`

        Returns the main HTML page.
        """

        with open(Path(__file__).parent.parent/"static/index.html", "r") as f:
            return f.read()

    def status(self) -> Json:
        """
        `status()`

        Returns the server status.
        """

        return {"status": True,
                "message_count": app_database.count_messages,
                "user_count": app_database.count_users,
                "chat_count": app_database.count_chats}

    async def get_messages(self, route: str) -> Json:
        """
        `get_messages()`

        Returns last `limit` messages from the database.
        """

        try:
            query = route.split("?")[1] if "?" in route else ""
            params = dict(qc.split("=") for qc in query.split("&") if "=" in qc)
            limit = int(params.get("limit", 50))
        except (ValueError, IndexError):
            return {"error": "Invalid or missing limit parameter"}

        return app_database.get_messages(limit)

    async def get_chats(self, route: str) -> Json:
        """
        `get_chats()`

        Returns last `limit` chats from the database.
        """

        try:
            query = route.split("?")[1] if "?" in route else ""
            params = dict(qc.split("=") for qc in query.split("&") if "=" in qc)
            limit = int(params.get("limit", 50))
        except (ValueError, IndexError):
            return {"error": "Invalid or missing limit parameter"}

        return app_database.get_chats(limit)

    async def get_users(self, route: str) -> Json:
        try:
            query = route.split("?")[1] if "?" in route else ""
            params = dict(qc.split("=") for qc in query.split("&") if "=" in qc)
            limit = int(params.get("limit", 50))
        except (ValueError, IndexError):
            return {"error": "Invalid or missing limit parameter"}

        return app_database.get_users(limit)

    # endregion
    # region POST funcs
    async def register_user(self, body: str) -> Json:
        """Register new user and save to database.
        {
            "name": "John Doe",
            "password": "password123"
        }
        """
        try:
            data: Json = json.loads(body)
            name: str = data["name"]
            password: str = data["password"]

            if app_database.check_name(name):
                return {"status": False, "message": "This name is already taken."}

            success = User().sign_up(name, password)

            return {"status": True, "message": success}
        except json.JSONDecodeError:
            return {"status": False, "message": "Invalid JSON"}

    async def login_user(self, body: str) -> Json:
        """Log user in.
        {
            "name": "John Doe",
            "password": "password123"
        }
        """

        try:
            data: Json = json.loads(body)
            name: str = data["name"]
            password: str = data["password"]

            user: User = User()
            status: bool = user.sign_in(name, password)

            if user:
                return {"status": status, "message": "Logged in successfully.", "user": user.to_json() & {"token": user.token}}

        except Exception as e:
            return {"status": False, "message": "Not Implemented"}

    async def create_chat(self, body: str) -> Json:
        """Create chat in db.
        {
            "title": "Test Chat",
            "description": "This is a test chat.",
            "is_group": True,
            "creator": 1,
            "members": [1, 2, 3]
        }
        """
        try:
            data: Dict[str, Any] = json.loads(body)

            if (
                ("title" not in data) or
                ("description" not in data) or
                ("is_group" not in data) or
                ("creator" not in data) or
                ("members" not in data)
            ):
                return {"status": False, "message": "All fields are required."}

            title: str = data["title"]

            if not title:
                return {"status": False, "message": "Name is required."}

            if app_database.check_chat_title(title):
                return {"status": False, "message": f"Name {title} is busy."}

            app_database.create_chat(
                    data["creator"], data["is_group"], title, data["description"], data["members"]
                ),
            return {
                "status": True,
                "chat": title,
            }
        except json.JSONDecodeError:
            return {"status": False, "message": "Invalid JSON"}

    async def send_message(self, body: str) -> Json:
        """Store message in database.
        {
            "chat_id": -2,
            "id": 1,
            "text": "Hello, world!"
        }
        """
        try:
            data: Json = json.loads(body)
            chat_id: int = data["chat_id"]
            user_id: int = data["id"]
            text: str = data["text"]

            chat = app_database.get_chat_by_id(chat_id)

            if app_database.check_chat(chat_id):
                return {"status": False, "message": "Chat not found."}

            if user_id < 0 or not text:
                return {"status": False, "message": "Valid ID and text are required."}

            app_database.send_message(chat, user_id, text)

            return {"status": True,
                    "message": "Sent successfully."}
        except json.JSONDecodeError:
            return {"status": False, "message": "Invalid JSON"}

    # endregion
