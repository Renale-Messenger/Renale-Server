from typing import Any, Dict, Tuple
from pathlib import Path
import asyncio
import socket
import json

from app.database import app_database
from app.applib import Json, JsonD, JsonResp
from app.user import User


class RenaleServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 9789, local: bool = False):
        if local:
            self.host = host
            self.port = port
            self.serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.serverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.serverSocket.bind((self.host, self.port))
            self.serverSocket.listen(2)
            self.serverSocket.setblocking(False)
            print(f"Server listening on {self.host}:{self.port}")

    # region server funcs
    async def handle_http_request(self, conn: socket.socket, addr: Tuple[str, int]) -> None:
        request = await asyncio.get_event_loop().sock_recv(conn, 1024)
        request_text = request.decode("utf-8")

        route, method, headers, body = self.parse_http_request(request_text)  # type: ignore
        route_name = route.split("?", maxsplit=1)[0]
        print(f'Connection from {"localhost" if addr[0] == "127.0.0.1" else addr[0]}:{addr[1]}. Method: {method}, Route: {route_name}')
        response = await self.route_request(route, method, body, headers)
        await asyncio.get_event_loop().sock_sendall(conn, response.encode("utf-8"))
        conn.close()

    def parse_http_request(self, request_text: str) -> Tuple[str, str, JsonD, str]:
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

    async def route_request(self, route: str, method: str, body: str, headers: JsonD) -> str:
        response_data: JsonResp = {}
        route_data = route.split("?", maxsplit=1)
        route_name = route_data[0]
        user_agent = headers.get("User-Agent", "")
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
                    case _:
                        return self.publish("404 Not Found", status_code=404)
                return self.publish(
                    json.dumps(response_data['data']), content_type="application/json"
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
                    case "/changePassword":
                        response_data = await self.change_password(body)
                    case _:
                        return self.publish("404 Not Found", status_code=404)
                return self.publish(
                    json.dumps(response_data['data']), content_type="application/json",
                    status_code=200 if response_data["status"] else 400  # type: ignore
                )
            case "DELETE":
                match route_name:
                    case "/deleteUser":
                        response_data = await self.delete_user(body)
                    case _:
                        return self.E404
                return self.publish(
                    json.dumps(response_data['data']), content_type="application/json",
                    status_code=200 if response_data["status"] else 400  # type: ignore
                )
            case _:
                return self.publish("405 Method Not Allowed", status_code=405)

    def publish(self, content: str, status_code: int = 200, content_type: str = "text/html") -> str:
        response = (
            f"HTTP/1.1 {status_code} OK\n"
            f"Content-Type: {content_type}\n"
            f"Content-Length: {len(content)}\n"
            f"Connection: close\n\n{content}"
        )
        return response

    @property
    def E404(self) -> str:
        return self.publish("404 Not Found", status_code=404)

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

    def status(self) -> JsonResp:
        """
        `status()`

        Returns the server status.
        """

        return {"status": True,
                "data": {"message_count": app_database.count_messages,
                         "user_count": app_database.count_users,
                         "chat_count": app_database.count_chats}}

    async def get_messages(self, route: str) -> JsonResp:
        """
        `get_messages()`

        Returns last `limit` messages from the database.
        """

        try:
            query: str = route.split("?")[1] if "?" in route else ""
            params: JsonD = dict(qc.split("=") for qc in query.split("&") if "=" in qc)
            limit: int = int(params.get("limit", 50))

            return {"status": True, "data": {"messages": app_database.get_messages(limit)}}
        except (ValueError, IndexError):
            return {"status": False, "data": {"error": "Invalid or missing limit parameter"}}

    async def get_chats(self, route: str) -> JsonResp:
        """
        `get_chats()`

        Returns last `limit` chats from the database.
        """

        try:
            query = route.split("?")[1] if "?" in route else ""
            params = dict(qc.split("=") for qc in query.split("&") if "=" in qc)
            limit = int(params.get("limit", 50))

            return {"status": True, "data": {"chats": app_database.get_chats(limit)}}
        except (ValueError, IndexError):
            return {"status": False, "data": {"error": "Invalid or missing limit parameter"}}

    async def get_users(self, route: str) -> JsonResp:
        try:
            query = route.split("?")[1] if "?" in route else ""
            params = dict(qc.split("=") for qc in query.split("&") if "=" in qc)
            limit = int(params.get("limit", 50))

            return {"status": True, "data": {"users": app_database.get_users(limit)}}
        except (ValueError, IndexError):
            return {"status": False, "data": {"error": "Invalid or missing limit parameter"}}

    # endregion
    # region POST funcs
    async def register_user(self, body: str) -> JsonResp:
        """Register new user and save to database.
        {
            "name": "John Doe",
            "password": "password123"
        }
        """

        try:
            data: JsonD = json.loads(body)
            name: str = data["name"]
            password: str = data["password"]

            if app_database.name_exist(name):
                return {"status": False, "data": {"message": "This name is already taken."}}

            success = User().sign_up(name, password)

            if not success:
                return {"status": False, "data": {"message": "Error."}}

            return {"status": True, "data": {"message": success}}
        except json.JSONDecodeError:
            return {"status": False, "data": {"message": "Invalid JSON"}}

    async def login_user(self, body: str) -> JsonResp:
        """Log user in.
        {
            "name": "John Doe",
            "password": "password123"
        }
        """

        try:
            data: JsonD = json.loads(body)
            name: str = data["name"]
            password: str = data["password"]

            user: User = User()
            status: bool = user.sign_in(name, password)

            if not status:
                return {"status": False, "data": {"message": "Invalid credentials or user not found."}}

            if user:
                userdata: JsonD = user.to_json()
                userdata.update({"token": user.token})
                return {"status": status, "data": {"message": "Logged in successfully.", "user": userdata}}  # type: ignore

        except json.JSONDecodeError:
            return {"status": False, "data": {"message": "Invalid JSON"}}

    async def create_chat(self, body: str) -> JsonResp:
        """Create chat in db.
        {
            "title": "Test Chat",
            "description": "This is a test chat.",
            "is_group": true,
            "creator_id": 1,
            "creator_token": "token123",
            "members": [1, 2, 3]
        }
        """

        try:
            data: Dict[str, Any] = json.loads(body)

            if any((
                ("title" not in data),
                ("description" not in data),
                ("is_group" not in data),
                ("creator_id" not in data),
                ("creator_token" not in data),
                ("members" not in data),
            )):
                return {"status": False, "data": {"message": "All fields are required."}}

            title: str = data["title"]

            if not title:
                return {"status": False, "data": {"message": "Name is required."}}

            if app_database.chat_title_exist(title):
                return {"status": False, "data": {"message": f"Name {title} is busy."}}

            app_database.create_chat(
                data["creator_id"], data["creator_token"], data["is_group"], title, data["description"], data["members"]
            )
            return {"status": True, "data": {"message": title}}
        except json.JSONDecodeError:
            return {"status": False, "data": {"message": "Invalid JSON"}}

    async def send_message(self, body: str) -> JsonResp:
        """Store message in database.
        {
            "chat_id": -1,
            "user_id": 1,
            "token": "token123",
            "text": "Hello, World!"
        """

        try:
            data: JsonD = json.loads(body)
            chat_id: int = data["chat_id"]
            user_id: int = data["user_id"]
            user_token: str = data["token"]
            text: str = data["text"]

            if not app_database.chat_exist(chat_id):
                return {"status": False, "data": {"message": "Chat not found."}}

            if user_id < 0 or not text:
                return {"status": False, "data": {"message": "Valid ID and text are required."}}

            app_database.send_message(user_id, user_token, chat_id, text)

            return {"status": True, "data": {"message": "Sent successfully."}}
        except json.JSONDecodeError:
            return {"status": False, "data": {"message": "Invalid JSON"}}

    async def change_password(self, body: str) -> JsonResp:
        """Update user password.
        {
            "id": 1,
            "old_pass": "old_password",
            "new_pass": "new_password"
        }
        """

        try:
            data: JsonD = json.loads(body)
            user_id: int = int(data["id"])
            old_pass: str = str(data["old_pass"])
            new_pass: str = str(data["new_pass"])

            if user_id < 0 or not old_pass:
                return {"status": False, "data": {"message": "Valid ID and password are required."}}

            user_json: JsonD = app_database.get_user_by_id(user_id)

            if not user_json:
                return {"status": False, "data": {"message": "User not found."}}

            user: User = User()
            user.sign_in(user_json["name"], old_pass)

            user.change_password(old_pass, new_pass)

            return {"status": True, "data": {"message": "Password updated successfully."}}
        except json.JSONDecodeError:
            return {"status": False, "data": {"message": "Invalid JSON"}}

    # endregion
    # region DELETE funcs
    async def delete_user(self, body: str) -> JsonResp:
        """Delete user from db.
        {
            "id": 1,
            "token": "user_token"
        }
        """

        try:
            data: JsonD = json.loads(body)
            user_id: int = int(data["id"])
            user_token: str = str(data["token"])

            if user_id < 0:
                return {"status": False, "data": {"message": "Valid ID is required."}}

            user_json: JsonD = app_database.get_user_by_id(user_id)

            if not user_json:
                return {"status": False, "data": {"message": "User not found."}}

            user: User = User()
            user.sign_in(user_json["name"], user_json["password"])

            app_database.delete_user(user_id, user_token)

            return {"status": True, "data": {"message": "User deleted successfully."}}
        except json.JSONDecodeError:
            return {"status": False, "data": {"message": "Invalid JSON"}}

    # endregion
