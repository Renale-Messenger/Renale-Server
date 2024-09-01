from pymysql import Connection, connect as conn, cursors, OperationalError
from time import time as timestamp
from typing import Any, Dict, List, Optional, Literal, Tuple, Union
from json import dumps, loads

from app.applib import Json, random_id
from app.config import config


__all__: List[str] = ["app_database", "Database", "Session"]

class Session:
    def __init__(self, version, system, architecture, release):
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


class Database:
    def __init__(self) -> None:
        try:
            self.connection: Connection = conn(
                host=config.mysql_host,
                port=config.mysql_port,
                user=config.mysql_user.get_secret_value(),
                password=config.mysql_password.get_secret_value(),
                db=config.mysql_db,
                cursorclass=cursors.DictCursor,
            )
        except OperationalError as e:
            raise (Exception(f"Error connecting to database: {e}"))

        print("Database connection established successfully.")

    def __del__(self) -> None:
        if self.connection:
            self.connection.close()
            print("Database connection closed.")

    # region GET USER
    def get_users(self, limit: int = 50) -> Json:
        limit = int(limit)
        with self.connection.cursor() as sql:
            sql.execute("SELECT id, name, sessions FROM users ORDER BY id DESC LIMIT %s", (limit,))
            rows = sql.fetchall()

        return [{"id": row["id"],
                 "name": row["name"],
                 "sessions": loads(row["sessions"])}
                for row in rows
        ]

    def get_user_by_id(self, id: int) -> Json:
        with self.connection.cursor() as sql:
            sql.execute("SELECT id, name, sessions FROM users WHERE id = %s", (id,))
            row = sql.fetchone()

        return {"id": row["id"],
                "name": row["name"],
                "sessions": row["sessions"]}

    def get_user_by_name(self, name: str) -> Json:
        with self.connection.cursor() as sql:
            sql.execute("SELECT id, name, sessions FROM users WHERE name = %s", (name,))
            row = sql.fetchone()

        return {"id": row["id"],
                "name": row["name"],
                "sessions": loads(row["sessions"])}

    def get_id_by_name(self, name: str) -> int:
        with self.connection.cursor() as sql:
            sql.execute("SELECT id FROM users WHERE name = %s", (name,))
            row = sql.fetchone()
        return row["id"]

    def check_id(self, id: int) -> bool:
        """Returns True if user with given id does exist in the database."""
        with self.connection.cursor() as sql:
            sql.execute("SELECT * FROM users WHERE id = %s", (id,))
            return sql.fetchone() is not None

    def check_name(self, name: str) -> bool:
        """Returns True if user with given name does exist in the database."""
        with self.connection.cursor() as sql:
            sql.execute("SELECT * FROM users WHERE name = %s", (name,))
            return sql.fetchone() is not None

    @property
    def count_users(self) -> int:
        with self.connection.cursor() as sql:
            sql.execute("SELECT COUNT(*) FROM users")
            return int(sql.fetchone()["COUNT(*)"])

    # endregion
    # region POST USER
    def create_user(self, id: int, name: str, password: str, token: str, session: Json) -> Tuple[int, str]:
        """Register user in database and return user's id and token."""

        with self.connection.cursor() as sql:
            sql.execute(
                "INSERT INTO users (id, name, password, token, sessions, chats) VALUES (%s, %s, %s, %s, %s, %s)",
                (id, name, password, token, dumps([session]), "[]"),
            )
            self.connection.commit()
        return (id, token)

    def login_user(self, name: str, password: str) -> Tuple[int, str]:
        """Authenticate user by name and password and return user's id and token. If credentials are invalid, return id -1(invalid) and an error message."""

        with self.connection.cursor() as sql:
            sql.execute("SELECT id, name, password, token, sessions FROM users WHERE name = %s", (name,))
            user = sql.fetchone()

        if user and user["password"] == password:
            return (user["id"], user["token"])
        else:
            return (-1, "Invalid credentials")

    def update_sessions(self, id: int, new_session: Json) -> None:
        with self.connection.cursor() as sql:
            sessions: List[Json] = sql.execute(
                "SELECT id, name, sessions FROM users WHERE id = %s", (id,)
            )
            sessions.append(new_session)
            sql.execute("UPDATE users SET sessions = %s WHERE id = %s", (sessions, id))
            self.connection.commit()

    def change_password(self, id: int, new_password: str) -> None:
        with self.connection.cursor() as sql:
            sql.execute("UPDATE users SET password = %s WHERE id = %s", (new_password, id))
            self.connection.commit()

    # endregion
    # region GET MESSAGE
    def get_messages(self, limit: int = 50) -> Dict[Literal["messages"], List[Dict[str, Any]]]:
        limit = int(limit)
        with self.connection.cursor() as sql:
            sql.execute("SELECT * FROM messages ORDER BY time DESC LIMIT %s", (limit,))
            rows = sql.fetchall()

        return {
            "messages": [
                {
                    "id": row["id"],
                    "chat": row["chat"],
                    "user": row["user"],
                    "text": row["text"],
                    "time": row["time"],
                }
                for row in rows
            ]
        }

    @property
    def count_messages(self) -> int:
        with self.connection.cursor() as sql:
            sql.execute("SELECT COUNT(*) FROM messages")
            return int(sql.fetchone()["COUNT(*)"])

    # endregion
    # region POST MESSAGE
    def send_message(self, chat: Json, user: Json, text: str) -> None:
        with self.connection.cursor() as sql:
            sql.execute(
                "INSERT INTO messages (chat, user, text, time) VALUES (%s, %s, %s, %s)",
                (chat, user, text, timestamp()),
            )
            self.connection.commit()

    # endregion
    # region GET CHATS
    def get_chats(self, limit: Optional[int] = 50) -> Json:
        with self.connection.cursor() as sql:
            if isinstance(limit, int):
                sql.execute("SELECT is_group, chat_id, title, members FROM chats ORDER BY chat_id DESC LIMIT %s", (limit,))
            else:
                sql.execute("SELECT is_group, chat_id, title, members FROM chats ORDER BY chat_id DESC")
            rows = sql.fetchall()

        return {"chats": [{"is_group": not not row["is_group"],
                           "id": row["chat_id"],
                           "title": row["title"],
                           "members": [{"id": i["id"], "name": i["name"], "sessions": loads(i["sessions"])}
                                       for i in loads(row["members"])]}
                          for row in rows]}

    def check_chat_title(self, title: str) -> bool:
        """Returns True if chat with given title already exists in the database."""
        with self.connection.cursor() as sql:
            sql.execute("SELECT * FROM chats WHERE title = %s", (title,))
            return sql.fetchone() is not None

    def check_chat(self, chat_id: str) -> bool:
        """Returns True if chat with given id already exists in the database."""
        with self.connection.cursor() as sql:
            sql.execute("SELECT * FROM chats WHERE chat_id = %s", (chat_id,))
            return sql.fetchone() is not None

    def get_chat_by_id(self, chat_id) -> Dict[str, Any]:
        with self.connection.cursor() as sql:
            sql.execute("SELECT is_group, chat_id, title, description, members, admins FROM chats WHERE chat_id = %s", (chat_id,))
            row = sql.fetchone()

        return {
            "id": row["chat_id"],
            "title": row["title"],
            "description": row["description"],
            "is_group": row["is_group"],
            "members": loads(row["members"]),
            "admins": loads(row["admins"]),
        }

    @property
    def count_chats(self) -> int:
        with self.connection.cursor() as sql:
            sql.execute("SELECT COUNT(*) FROM chats")
            return int(sql.fetchone()["COUNT(*)"])

    # endregion
    # region POST CHATS
    def create_chat(self, creator_id: int, is_group: bool, title: str, description: str, member_ids: List[int]) -> None:
        creator = self.get_user_by_id(creator_id)
        admins: List = []
        members: List = []
        chat_id: int = 0

        if is_group:
            for i in member_ids:
                members.append(self.get_user_by_id(i))

            admins.append(creator)
            while True:
                chat_id = f"-{random_id()}"
                if not self.check_chat(chat_id):
                    break
        else:
            title = ""
            description = ""

        with self.connection.cursor() as sql:
            sql.execute("INSERT INTO chats (is_group, chat_id, title, description, members, admins) VALUES (%s, %s, %s, %s, %s, %s)",
            (is_group, chat_id, title, description, dumps(members), dumps(admins)))
            self.connection.commit()

    def add_members(self, member_ids: List[int], chat_id: int) -> None:
        members: List = []

        for member in member_ids:
            members.append(self.get_user_by_id(member))


        with self.connection.cursor() as sql:
            sql.execute("UPDATE chats SET members = array_append(members, %s) WHERE chat_id = %s", (user_id, chat_id))
            self.connection.commit()

    # endregion


try:
    app_database: Database = Database()
except OperationalError:
    print("Error connecting to database.")
    print("Reconnect...")
    app_database: Database = Database()
