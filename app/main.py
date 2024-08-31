from platform import version, system, architecture, release
from typing import Dict, List, Tuple
from pathlib import Path
import asyncio
import socket
import json
import time

from app.database import Session, Database
from app.types import Json
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
    async def handle_http_request(self, conn: socket.socket) -> None:
        request = await asyncio.get_event_loop().sock_recv(conn, 1024)
        request_text = request.decode("utf-8")

        route, method, headers, body = self.parse_http_request(request_text)
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
        route_data = route_data[1] if len(route_data) - 1 else ""
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
                return self.publish(json.dumps(response_data), content_type="application/json")
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
                return self.publish(json.dumps(response_data), content_type="application/json")
        return self.publish("404 Not Found", status_code=404)

    def publish(self, content: str, status_code: int = 200, content_type: str = "text/html") -> str:
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
            print(f'Connection from {"localhost" if addr[0] == "127.0.0.1" else addr[0]}:{addr[1]}')
            await self.handle_http_request(conn)

    # endregion
    # region GET funcs
    def main(self) -> str:
        """Возвращает главную HTML-страницу."""
        with open(Path(".", "static", "index.html"), "r") as f:
            return f.read()

    def status(self) -> Json:
        return {"status": "ok", "message_count": 50}

    async def get_messages(self, route: str) -> Dict[str, str | Json]:
        try:
            query = route.split("?")[1] if "?" in route else ""
            params = dict(qc.split("=") for qc in query.split("&") if "=" in qc)
            limit = float(params.get("limit", 50))
        except (ValueError, IndexError):
            return {"error": "Invalid or missing limit parameter"}

        with Database() as db:
            return db.get_messages(limit)

    async def get_chats(self, route: str) -> Json:
        try:
            query = route.split("?")[1] if "?" in route else ""
            params = dict(qc.split("=") for qc in query.split("&") if "=" in qc)
            limit = float(params.get("limit", 50))
        except (ValueError, IndexError):
            return {"error": "Invalid or missing limit parameter"}

        with Database() as db:
            return db.get_chats(limit)

    async def get_users(self, route: str) -> Json:
        try:
            query = route.split("?")[1] if "?" in route else ""
            params = dict(qc.split("=") for qc in query.split("&") if "=" in qc)
            limit = float(params.get("limit", 50))
        except (ValueError, IndexError):
            return {"error": "Invalid or missing limit parameter"}

        with Database() as db:
            return db.get_all_users(limit)

    # endregion
    # region POST funcs
    async def send_message(self, body: str) -> Json:
        """Добавляет сообщение в базу данных."""
        try:
            data: Json = json.loads(body)
            chat: Json = data["chat"]
            user_id: Json = data["id"]
            text: str = data["text"]

            if chat not in chat_list:
                return {"status": "error", "message": "Chat not found."}

            if not user_id or not text:
                return {"status": "error", "message": "ID and text are required."}

            with Database() as db:
                user = db.get_user_by_id(user_id)

            return {"status": "ok", "message": message}
        except json.JSONDecodeError:
            return {"status": "error", "message": "Invalid JSON"}

    async def create_chat(self, body: str) -> Json:
        return self.publish("404 Not Found", status_code=404)
        """Добавляет чат в базу данных."""
        try:
            data = json.loads(body)
            name = data["name"]
            description = data["description"]
            chat_type = data["chat_type"]

            if not name or not chat_type:
                return {"status": "error", "message": "Name and chat type are required."}

            if name in [i["name"] for i in chat_list]:
                return {"status": "error", "message": f"Name {name} is busy."}

            chat: Json = {"name": name, "description": description, "chat_type": chat_type}
            chat_list.append(chat)
            return {"status": "ok", "chat": chat}
        except json.JSONDecodeError:
            return {"status": "error", "message": "Invalid JSON"}

    async def register_user(self, body: str) -> Json:
        try:
            data: Json = json.loads(body)
            name: Json = data["name"]
            password: Json = data["password"]

            with Database() as db:
                if not db.check_name(name):
                    return {
                        "status": "error",
                        "code": "409",
                        "message": "This name is already taken.",
                    }

            success = User().sign_up(name, password)

            return {"status": "ok", "message": success}
        except json.JSONDecodeError:
            return {"status": "error", "message": "Invalid JSON"}

    async def login_user(self, body: str) -> Json:
        pass

    # endregion
