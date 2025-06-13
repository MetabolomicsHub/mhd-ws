from pydantic import BaseModel


class DatabaseConnection(BaseModel):
    host: str = ""
    port: int = 5432
    user: str = ""
    password: str = ""
    database: str = ""
    url_scheme: str = ""


class DatabaseConfiguration(BaseModel):
    connection: DatabaseConnection = DatabaseConnection()
