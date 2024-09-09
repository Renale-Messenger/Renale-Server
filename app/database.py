from sqlite3 import connect, OperationalError, Row, Cursor, Connection
from typing import Any, Dict, List, Optional, Tuple, Callable
from json import dumps, loads
from time import time as unixtime
from pathlib import Path

from app.applib import Json, JsonD, random_id, logf


__all__: List[str] = ["app_database", "Session"]


def db_link(default: Any = None) -> Callable[..., Any]:
    "db_link() used not right number of arguments"

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: List[Any], **kwargs: Dict[str, Any]) -> Any:
            sql: Cursor = app_database.cursor()
            try:
                return func(sql, *args, **kwargs)
            except Exception as e:
                logf(f"Error in {func.__name__}({', '.join((f'{i!r}' for i in args))}): {str(e)}")
                return default
            finally:
                sql.close()
        return wrapper

    return decorator


class Session:
    def __init__(self, version, system, architecture, release):  # type: ignore
        self.version = version
        self.system = system
        self.architecture = architecture
        self.release = release

    def __str__(self) -> str:
        version = self.version
        system = self.system
        architecture = self.architecture
        release = self.release

        return f"""
Session info:
{version = !r}
{system = !r}
{architecture = !r}
{release = !r}
""".strip()


# region GET USER
@db_link({})
def get_users(sql: Cursor, start: Optional[int] = 50, count: Optional[int] = 50) -> List[JsonD]:
    if isinstance(count, int) and isinstance(start, int):
        sql.execute("SELECT id, name, sessions FROM users ORDER BY id DESC LIMIT ? OFFSET ?", (count, start))
    else:
        sql.execute("SELECT is_group, chat_id, title, members FROM chats ORDER BY chat_id DESC")
    rows = sql.fetchall()

    return [{"id": row["id"],
             "name": row["name"],
             "sessions": loads(row["sessions"])}
            for row in rows
            ]


@db_link({})
def get_user_by_id(sql: Cursor, id: int) -> JsonD:
    sql.execute("SELECT id, name, sessions FROM users WHERE id =?", (id,))
    row = sql.fetchone()

    return {"id": row["id"],
            "name": row["name"],
            "sessions": row["sessions"]}


@db_link({})
def get_user_by_name(sql: Cursor, name: str) -> JsonD:
    sql.execute("SELECT id, name, sessions FROM users WHERE name =?", (name,))
    row = sql.fetchone()

    return {"id": row["id"],
            "name": row["name"],
            "sessions": loads(row["sessions"])}


@db_link(-1)
def get_id_by_name(sql: Cursor, name: str) -> int:
    sql.execute("SELECT id FROM users WHERE name =?", (name,))
    row = sql.fetchone()
    return row["id"]


@db_link(False)
def id_exist(sql: Cursor, id: int) -> bool:
    "Returns True if user with given id does exist in the database."

    sql.execute("SELECT * FROM users WHERE id =?", (id,))
    return sql.fetchone() is not None


@db_link(False)
def name_exist(sql: Cursor, name: str) -> bool:
    "Returns True if user with given name does exist in the database."

    sql.execute("SELECT * FROM users WHERE name =?", (name,))
    return sql.fetchone() is not None


@db_link(-1)
def count_users(sql: Cursor) -> int:
    sql.execute("SELECT COUNT(*) FROM users")
    return int(sql.fetchone()['COUNT(*)'])


# endregion
# region POST USER
@db_link((-1, "Error creating user"))
def create_user(sql: Cursor, id: int, name: str, password: str, token: str, session: Json) -> Tuple[int, str]:
    "Register user in database and return user's id and token."

    sql.execute(
        "INSERT INTO users (id, name, password, token, sessions, chats) VALUES (?, ?, ?, ?, ?, ?)",
        (id, name, password, token, dumps([session]), "[]"),
    )
    app_database.commit()
    return (id, token)


@db_link((-1, "User not found"))
def login_user(sql: Cursor, name: str, password: str) -> Tuple[int, str]:
    """Authenticate user by name and password and return user's id and token. If credentials are invalid, return id -1(invalid) and an error message."""

    sql.execute("SELECT id, name, password, token, sessions FROM users WHERE name =?", (name,))
    user = sql.fetchone()

    if user and user["password"] == password:
        return (user["id"], user["token"])
    else:
        return (-1, "Invalid credentials")


@db_link()
def update_sessions(sql: Cursor, id: int, token: str, new_session: Json) -> None:
    sql.execute("SELECT token FROM users WHERE id =?", (id,))
    user_token = sql.fetchone()["token"]
    if user_token == token:
        sql.execute(
            "SELECT id, name, sessions FROM users WHERE id =?", (id,)
        )
        sessions: List[Json] = sql.fetchall()
        sessions.append(new_session)
        sql.execute("UPDATE users SET sessions =? WHERE id =?", (sessions, id))


@db_link()
def change_password(sql: Cursor, id: int, new_password: str) -> None:
    sql.execute("UPDATE users SET password =? WHERE id =?", (new_password, id))
    app_database.commit()


# endregion
# region GET MESSAGE
@db_link([])
def get_messages(sql: Cursor, start: Optional[int] = 50, count: Optional[int] = 50) -> List[Dict[str, Any]]:
    if isinstance(count, int) and isinstance(start, int):
        sql.execute("SELECT * FROM messages ORDER BY time DESC LIMIT ? OFFSET ?", (count, start))
    else:
        sql.execute("SELECT is_group, chat_id, title, members FROM chats ORDER BY chat_id DESC")
    rows = sql.fetchall()

    return [{"chat": row["chat"],
             "user": row["user"],
             "text": row["text"],
             "time": row["time"],
             } for row in rows]


@db_link(-1)
def count_messages(sql: Cursor) -> int:
    sql.execute("SELECT COUNT(*) FROM messages")
    count = int(sql.fetchone()['COUNT(*)'])

    return count


# endregion
# region POST MESSAGE
@db_link(False)
def send_message(sql: Cursor, user_id: int, user_token: str, chat_id: int, text: str) -> str | JsonD:
    """Send a message to a chat."""

    sql.execute("SELECT token FROM users WHERE id =?", (user_id,))
    user_token_ = sql.fetchone()["token"]
    if user_token == user_token_:
        sql.execute("INSERT INTO messages (user, chat, text, time) VALUES (?, ?, ?, ?)",
                    (user_id, chat_id, text, unixtime()))
        app_database.commit()
        return {"user_id": user_id, "chat_id": chat_id, "text": text, "time": unixtime()}
    else:
        return "Invalid token"


# endregion
# region GET CHATS
@db_link([])
def get_chats(sql: Cursor, start: Optional[int] = 50, count: Optional[int] = 50) -> JsonD:
    if isinstance(count, int) and isinstance(start, int):
        sql.execute("SELECT is_group, chat_id, title, members FROM chats ORDER BY chat_id DESC LIMIT ? OFFSET ?", (count, start))
    else:
        sql.execute("SELECT is_group, chat_id, title, members FROM chats ORDER BY chat_id DESC")
    rows = sql.fetchall()

    return {"chats": [{"is_group": not not row["is_group"],
                       "chat_id": row["chat_id"],
                       "chat_name": row["title"],
                       "members": [{"id": i["id"], "name": i["name"], "sessions": loads(i["sessions"])}
                      for i in loads(row["members"])]}
            for row in rows]
            }


@db_link(False)
def chat_title_exist(sql: Cursor, title: str) -> bool:
    "Returns True if chat with given title already exists in the database."

    sql.execute("SELECT * FROM chats WHERE title =?", (title,))
    return sql.fetchone() is not None


@db_link(False)
def chat_exist(sql: Cursor, chat_id: int) -> bool:
    "Returns True if chat with given id already exists in the database."

    sql.execute("SELECT * FROM chats WHERE chat_id =?", (chat_id,))
    return sql.fetchone() is not None


@db_link({})
def get_chat_by_id(sql: Cursor, chat_id: int) -> Dict[str, Any]:
    sql.execute("SELECT is_group, chat_id, title, description, members, admins FROM chats WHERE chat_id =?", (chat_id,))
    row = sql.fetchone()

    return {
        "id": row["chat_id"],
        "title": row["title"],
        "description": row["description"],
        "is_group": row["is_group"],
        "members": loads(row["members"]),
        "admins": loads(row["admins"]),
    }


@db_link(-1)
def count_chats(sql: Cursor) -> int:
    sql.execute("SELECT COUNT(*) FROM chats")
    return int(sql.fetchone()['COUNT(*)'])


# endregion
# region POST CHATS
@db_link()
def create_chat(sql: Cursor, creator_id: int, creator_token: str, is_group: bool, title: str, description: str, member_ids: List[int]) -> None:
    sql.execute("SELECT token FROM users WHERE id =?", (creator_id,))
    user_token = sql.fetchone()["token"]
    if user_token != creator_token:
        return

    creator = get_user_by_id(creator_id)
    admins: List[JsonD] = []
    members: List[JsonD] = []
    chat_id: int = -1

    if is_group:
        for i in member_ids:
            members.append(get_user_by_id(i))

        admins.append(creator)
        while True:
            chat_id = -random_id()
            if not chat_exist(chat_id) and chat_id != -1:
                break
    else:
        title = ""
        description = ""

    sql.execute("INSERT INTO chats (is_group, chat_id, title, description, members, admins) VALUES (?,?,?,?,?,?)",
                (is_group, chat_id, title, description, dumps(members), dumps(admins)))
    app_database.commit()


@db_link()
def add_members(sql: Cursor, user_id: int, user_token: str, member_ids: List[int], chat_id: int) -> None:
    sql.execute("SELECT token FROM users WHERE id =?", (user_id,))
    user_token_ = sql.fetchone()["token"]
    if user_token != user_token_:
        return

    members: List[JsonD] = []

    for member in member_ids:
        members.append(get_user_by_id(member))
    sql.execute("SELECT members FROM chats WHERE chat_id = ?", (chat_id,))
    updated_members = loads(sql.fetchone()["members"]) + members
    sql.execute("UPDATE chats SET members = ? WHERE chat_id = ?", (dumps(updated_members), chat_id))
    app_database.commit()


# endregion
# region DELETE
@db_link(False)
def delete_user(sql: Cursor, user_id: int, token: str) -> bool:
    sql.execute("SELECT token FROM users WHERE id =?", (user_id,))
    user_token = sql.fetchone()["token"]

    if user_token == token:
        sql.execute("DELETE FROM users WHERE id =?", (user_id,))
        app_database.commit()
        return True
    else:
        return False
# endregion


try:
    app_database: Connection = connect(Path(__file__).parent.parent/"server.sqlite", check_same_thread=False)
    app_database.row_factory = Row
    print('Connected successfully to the SQLite database.')
except OperationalError as e:
    logf(e, 2)
    raise Exception(f"Error connecting to database:\n{e}")
