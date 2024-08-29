from typing import Any, Dict, List, Tuple
import asyncio
import socket
import json
import time


messages: List[Dict[str, Any]] = []
chat_list: List = []


class RenaleServer:
    def __init__(self, host: str = '127.0.0.1', port: int = 9789):
        self.host = host
        self.port = port
        self.serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.serverSocket.bind((self.host, self.port))
        self.serverSocket.listen(2)
        self.serverSocket.setblocking(False)
        print(f'Server listening on {self.host}:{self.port}')

    async def handle_http_request(self, conn: socket.socket) -> None:
        request = await asyncio.get_event_loop().sock_recv(conn, 1024)
        request_text = request.decode('utf-8', errors='ignore')

        route, method, headers, body = self.parse_http_request(request_text)
        response = await self.route_request(route, method, body)
        await asyncio.get_event_loop().sock_sendall(conn, response.encode('utf-8'))
        conn.close()

    def parse_http_request(self, request_text: str) -> Tuple[str, str, Dict, str]:
        lines = request_text.split('\r\n')
        if not lines or not lines[0]:
            return ("/", "GET", {}, "")

        method, path, _ = lines[0].split(' ')
        headers = {}
        body = ""
        i = 1

        while i < len(lines) and lines[i] != "":
            key, value = lines[i].split(': ', 1)
            headers[key] = value
            i += 1

        if i < len(lines) - 1:
            body = lines[i + 1]

        return (path, method, headers, body)

    async def route_request(self, route: str, method: str, body: str) -> str:
        if route == '/':
            content = await self.main()
            return self.publish(content)
        elif route == '/status':
            content = await self.status()
            return self.publish(content)
        elif route == '/send' and method == 'POST':
            response_data = await self.send_message(body)
            return self.publish(json.dumps(response_data), content_type='application/json')
        elif route.startswith('/messages'):
            response_data = await self.get_messages(route)
            return self.publish(json.dumps(response_data), content_type='application/json')
        elif route.startswith('/chats'):
            response_data = await self.get_chats(route)
            return self.publish(json.dumps(response_data), content_type='application/json')
        else:
            return self.publish('404 Not Found', status_code=404)

    def publish(self, content: str, status_code: int = 200, content_type: str = 'text/html') -> str:
        response = f"HTTP/1.1 {status_code} OK\r\n" + \
        f"Content-Type: {content_type}\r\n" + \
        f"Content-Length: {len(content)}\r\n" + \
        f"Connection: close\r\n\r\n{content}"
        return response

    def main(self) -> str:
        """Возвращает главную HTML-страницу."""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Simple Socket Server</title>
</head>
<body>
    <h1>Hello, User!</h1>
    <a href="/send">Send</a>
    <a href="/messages?after=0">Messages</a>
    <a href="/status">Status</a>
</body>
</html>
"""

    async def status(self) -> str:
        return f'{{"status": "ok", "message_count": {len(messages)}}}'

    async def send_message(self, body: str) -> Dict[str, Any]:
        """Добавляет сообщение в базу данных."""
        try:
            data = json.loads(body)
            chat = data.get('chat')
            name = data.get('name')
            text = data.get('text')

            if not name or not text:
                return {"status": "error", "message": "Name and text are required"}

            message = {
                'chat': chat,
                'name': name,
                'text': text,
                'time': time.time()
            }
            messages.append(message)
            return {
                "status": "ok", 
                "message": {
                    "user": {
                        "name": name
                    },
                    "text": text,
                    "time": message['time']
                }
            }
        except json.JSONDecodeError:
            return {"status": "error", "message": "Invalid JSON"}

    async def get_messages(self, route: str) -> Dict[str, str | Dict[str, Any]]:
        try:
            query = route.split('?')[1] if '?' in route else ''
            params = dict(qc.split('=') for qc in query.split('&') if '=' in qc)
            after = float(params.get('after', 0))
        except (ValueError, IndexError):
            return {'error': 'Invalid or missing after parameter'}

        msgs = [msg for msg in messages if msg['time'] > after]
        return {'messages': msgs[:50]}

    async def get_chats(self, route: str) -> str:
        try:
            query = route.split('?')[1] if '?' in route else ''
            params = dict(qc.split('=') for qc in query.split('&') if '=' in qc)
            after = float(params.get('after', 0))
        except (ValueError, IndexError):
            return self.publish('{"error": "Invalid or missing after parameter"}', status_code=400)

        chats = [chat for chat in chat_list if chat['time'] > after]
        return self.publish(json.dumps({'chats': chats[:50]}))

    async def start(self) -> None:
        loop = asyncio.get_event_loop()
        while True:
            conn, addr = await loop.sock_accept(self.serverSocket)
            print(f'Connection from {"localhost" if addr[0] == "127.0.0.1" else addr[0]}:{addr[1]}')
            await self.handle_http_request(conn)


if __name__ == "__main__":
    server = RenaleServer(host='127.0.0.1', port=9789)
    asyncio.run(server.start())
