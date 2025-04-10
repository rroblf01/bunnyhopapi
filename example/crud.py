from pydantic import BaseModel
from bunnyhopapi.server import Server, Router
from bunnyhopapi.models import Endpoint, PathParam
import sqlite3
from contextlib import contextmanager
import uuid
import logging

logger = logging.getLogger(__name__)


class UserInput(BaseModel):
    name: str
    age: int


class UserOutput(BaseModel):
    id: str
    name: str
    age: int


class Message(BaseModel):
    message: str


class UserList(BaseModel):
    users: list[UserOutput]


class Database:
    def __init__(self, db_name="users.db"):
        self.db_name = db_name
        self.create_table()

    def create_table(self):
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    age INTEGER NOT NULL
                )
            """)

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_name)
        try:
            yield conn
        finally:
            conn.close()

    def add_user(self, user: UserInput) -> UserOutput:
        user_id = str(uuid.uuid4())
        new_user = UserOutput(id=user_id, **user.model_dump())
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO users (id, name, age)
                VALUES (?, ?, ?)
            """,
                (new_user.id, new_user.name, new_user.age),
            )
            conn.commit()
        return new_user

    def get_users(self) -> list[UserOutput]:
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT id, name, age FROM users")
            users = [UserOutput(id=row[0], name=row[1], age=row[2]) for row in cursor]
        return users

    def get_user(self, user_id: str) -> UserOutput | None:
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT id, name, age FROM users WHERE id = ?", (user_id,)
            )
            row = cursor.fetchone()
        if row:
            return UserOutput(id=row[0], name=row[1], age=row[2])
        return None

    def update_user(self, user_id: str, user: UserInput) -> UserOutput | None:
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE users
                SET name = ?, age = ?
                WHERE id = ?
            """,
                (user.name, user.age, user_id),
            )
            conn.commit()
            if cursor.rowcount == 0:
                return None
            return self.get_user(user_id)

    def delete_user(self, user_id: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            return cursor.rowcount > 0


class UserEndpoint(Endpoint):
    path: str = "/users"

    @Endpoint.MIDDLEWARE()
    def db_middleware(self, endpoint, headers, *args, **kwargs):
        logger.info("db_middleware: Before to call the endpoint")
        db = Database()
        return endpoint(headers=headers, db=db, *args, **kwargs)

    @Endpoint.GET()
    def get(self, headers, db: Database, *args, **kwargs) -> {200: UserList}:
        users = db.get_users()
        return 200, {"users": users}

    @Endpoint.GET()
    def get_with_params(
        self, db, user_id: PathParam[str], headers, *args, **kwargs
    ) -> {200: UserOutput, 404: Message}:
        users = db.get_user(user_id)

        if users is None:
            return 404, {"message": "User not found"}

        return 200, users

    @Endpoint.POST()
    def post(self, user: UserInput, headers, db, *args, **kwargs) -> {201: UserOutput}:
        new_user = db.add_user(user)
        return 201, new_user

    @Endpoint.PUT()
    def put(
        self, db, user_id: PathParam[str], user: UserInput, headers, *args, **kwargs
    ) -> {200: UserOutput, 404: Message}:
        updated_user = db.update_user(user_id, user)

        if updated_user is None:
            return 404, {"message": "User not found"}

        return 200, updated_user

    @Endpoint.DELETE()
    def delete(
        self, db, user_id: PathParam[str], headers, *args, **kwargs
    ) -> {200: Message, 404: Message}:
        if db.delete_user(user_id):
            return 200, {"message": "User deleted"}
        else:
            return 404, {"message": "User not found"}


if __name__ == "__main__":
    server = Server()
    auth_router = Router()
    auth_router.include_endpoint_class(UserEndpoint)
    server.include_router(auth_router)
    server.run(workers=1)
