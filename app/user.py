from time import time as timestamp
from typing import List
import secrets
import string

from app.applib import Json, JsonD, random_id
from app.database import app_database


__all__ = ["User"]


class User:
    name: str
    token: str
    password: str
    _id: int
    sessions: List[Json]

    # region GET funcs
    def to_json(self) -> JsonD:
        return {"id": self._id,
                "name": self.name}

    # endregion
    # region POST funcs
    def sign_up(self, name: str, password: str) -> bool:
        self.token = self.random_token()
        self.id = self.free_id()
        session = {
            "version": version(),
            "system": system(),
            "architecture": architecture(),
            "release": release(),
        }  # TODO: why is this static...?
        # IDK, but now it dont

        app_database.create_user(self.id, name, password, self.token, {str(int(timestamp())): session})
        return True

    def sign_in(self, name: str, password: str) -> bool:
        self.id, self.token = app_database.login_user(name, password)
        return self.id >= 0

    def change_password(self, old_pass: str, new_pass: str) -> bool:
        if self.password == old_pass:
            app_database.change_password(self.id, new_pass)
            self.password = new_pass
            return True
        return False

    def sign_out(self) -> None:
        pass

    # endregion
    # region Other funcs
    def update_password(self, old_pass: str, new_pass: str) -> bool:
        if self.password == old_pass:
            self.password = new_pass
            # TODO: update_password doesnt exist
            # with Database() as db:
            #     db.update_password(self.id, new_pass)
            return True
        return False

    def random_token(self):
        return "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(128))

    def free_id(self) -> int:
        id = random_id()
        if app_database.check_id(id):
            return self.free_id()
        return id
    # endregion
