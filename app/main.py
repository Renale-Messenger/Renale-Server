__version__ = "0.0.1.dev1"

from app.user import User

from flask_socketio import SocketIO, send, emit, join_room, leave_room  # type: ignore
from flask import Flask, request, render_template
from json import loads, dumps, JSONDecodeError
from app.applib import JsonD
from uuid import uuid4


import app.database as app_database


# connect
# welcome
# disconnect
# MessageSent
# MessageSend
# roomJoin
# roomLeave


app: Flask = Flask(__name__)
app.config['SECRET_KEY'] = uuid4().hex
socketio = SocketIO(app, logger=True, engineio_logger=True)


@socketio.on('connect')
def handle_connect():
    emit('welcome', {
        'protocol_version': __version__,
    })


@socketio.on('register')
def register_user(json: JsonD):
    """Register new user and save to database.
    {
        "name": "John Doe",
        "password": "qwerty123"
    }
    """

    try:
        name: str = json["name"]
        password: str = json["password"]

        if app_database.name_exist(name):
            emit('error', 'This name is already taken.')

        success = User().sign_up(name, password)

        if not success:
            emit('error', 'Error.')

        emit('registered', success)
    except JSONDecodeError:
        emit('error', 'Invalid JSON')


@socketio.on('auth')
def login_user(json: JsonD):
    """Log user in.
    {
        "name": "John Doe",
        "password": "qwerty123"
    }
    """

    try:
        name: str = json["name"]
        password: str = json["password"]

        user: User = User()
        status: bool = user.sign_in(name, password)

        if not status:
            emit('error', 'Invalid credentials or user not found.')

        if user:
            userdata: JsonD = user.to_json()
            userdata.update({"token": user.token})
            emit('success_auth', {
                'user_id': user._id,  # type: ignore
                'user_token': user.token,
            })

    except JSONDecodeError:
        emit('error', 'Invalid JSON')


@socketio.on('disconnect')
def test_disconnect():
    print('Client disconnected')


@socketio.on('message')
def handle_message(json: str):
    print(f'received json: {loads(json)}')


@socketio.on('get_chats_list')
def handle_get_chats_list(json: JsonD):
    emit('chats_list', app_database.get_chats(json['start'], json['count']))


@socketio.on('roomJoin')
def on_join(json: JsonD):
    room = json['chat_id']
    join_room(room)
    emit('success_join', {})


@socketio.on('roomLeave')
def on_leave(json: JsonD):
    username = json['username']
    room = json['room']
    leave_room(room)
    send(f'{username} has left the room.', to=room)


@socketio.on('create_chat')
def create_chat(json: JsonD):
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
        if any((
            ("title" not in json),
            ("description" not in json),
            ("is_group" not in json),
            ("creator_id" not in json),
            ("creator_token" not in json),
            ("members" not in json),
        )):
            emit('error', "All fields are required.")

        title: str = json["title"]

        if not title:
            emit('error', 'Name is required.')

        if app_database.chat_title_exist(title):
            emit('error', f'Name {title} is busy.')

        app_database.create_chat(
            json["creator_id"], json["creator_token"], json["is_group"], title, json["description"], json["members"]
        )
        emit('chat_created', title)
    except JSONDecodeError:
        emit('error', 'Invalid JSON')


@socketio.on('message_send')
def send_message(json: JsonD):
    """Store message in database.
    {
        "chat_id": -1,
        "user_id": 1,
        "token": "token123",
        "text": "Hello, World!"
    """

    try:
        chat_id: int = json["chat_id"]
        user_id: int = json["user_id"]
        user_token: str = json["token"]
        text: str = json["text"]

        if not app_database.chat_exist(chat_id):
            emit('error', 'Chat not found.')

        if user_id < 0 or not text:
            emit('error', 'Valid ID and text are required.')

        message: str | JsonD = app_database.send_message(user_id, user_token, chat_id, text)

        if isinstance(message, str):
            emit('error', message)
        else:
            send(dumps(message), to=chat_id)
    except JSONDecodeError:
        emit('error', 'Invalid JSON')


# region WEB INTERFACE
@app.route('/', methods=['GET'])
def admin_page():
    return render_template('index.html')


@app.route('/signin', methods=['GET'])
def signin_page():
    return render_template('login.html')


@app.route('/api/v1', methods=['GET'])
def status():
    return {"message_count": app_database.count_messages(),
            "user_count": app_database.count_users(),
            "chat_count": app_database.count_chats()}


@app.route('/api/messages', methods=['GET'])
def get_messages():
    try:
        return {"messages": app_database.get_messages(int(request.args["start"]), int(request.args["count"]))}
    except (ValueError, IndexError):
        return {"error": "Invalid or missing start/count parameter"}


@app.route('/api/chats', methods=['GET'])
def get_chats():
    try:
        return {"chats": app_database.get_chats(int(request.args["start"]), int(request.args["count"]))}
    except (ValueError, IndexError):
        return {"error": "Invalid or missing start/count parameter"}


@app.route('/api/users', methods=['GET'])
def get_users():
    try:
        return {"users": app_database.get_users(int(request.args["start"]), int(request.args["count"]))}
    except (ValueError, IndexError):
        return {"error": "Invalid or missing start/count parameter"}
# endregion


"""
async def route_request(route: str, method: str, body: str, headers: JsonD) -> str:
    response_data: JsonResp = {}
    route_data = route.split("?", maxsplit=1)
    route_name = route_data[0]
    # TODO: unused...?
    # route_data = route_data[1] if len(route_data) - 1 else ""
    match method:
        case "GET":
            match route_name:
                case "/":
                    return publish(main())
                case "/status":
                    response_data = status()
                case "/messages":
                    response_data = await get_messages(route)
                case "/chats":
                    response_data = await get_chats(route)
                case "/users":
                    response_data = await get_users(route)
                case _:
                    return publish("404 Not Found", status_code=404)
            return publish(
                json.dumps(response_data['data']), content_type="application/json"
            )
        case "POST":
            match route_name:
                case "/send":
                    response_data = await send_message(body)
                case "/newChat":
                    response_data = await create_chat(body)
                case "/register":
                    response_data = await register_user(body)
                case "/login":
                    response_data = await login_user(body)
                case "/changePassword":
                    response_data = await change_password(body)
                case _:
                    return publish("404 Not Found", status_code=404)
            return publish(
                json.dumps(response_data['data']), content_type="application/json",
                status_code=200 if response_data["status"] else 400  # type: ignore
            )
        case "DELETE":
            match route_name:
                case "/deleteUser":
                    response_data = await delete_user(body)
                case _:
                    return E404
            return publish(
                json.dumps(response_data['data']), content_type="application/json",
                status_code=200 if response_data["status"] else 400  # type: ignore
            )
        case _:
            return publish("405 Method Not Allowed", status_code=405)
"""

"""
# region POST funcs
async def change_password(body: str) -> JsonResp:
    \"""Update user password.
    {
        "id": 1,
        "old_pass": "old_password",
        "new_pass": "new_password"
    }
    \"""

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
async def delete_user(body: str) -> JsonResp:
    \"""Delete user from db.
    {
        "id": 1,
        "token": "user_token"
    }
    \"""

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
"""
