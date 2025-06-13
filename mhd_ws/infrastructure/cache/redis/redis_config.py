from pydantic import BaseModel


class RedisService(BaseModel):
    host: str = ""
    port: int = 6379


class RedisConnection(BaseModel):
    redis_service: RedisService = RedisService()
    db: int = 10
    password: str = ""
    socket_timeout: float = 0.5
