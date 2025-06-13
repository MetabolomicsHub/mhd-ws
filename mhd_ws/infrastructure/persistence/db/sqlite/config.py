from pydantic import BaseModel


class SQLiteDatabaseConnection(BaseModel):
    file_path: str = ""
    url_scheme: str = "sqlite+aiosqlite"


class DatabaseConfiguration(BaseModel):
    connection: SQLiteDatabaseConnection = SQLiteDatabaseConnection()
