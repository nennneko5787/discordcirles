import os
import asyncpg

if os.path.isfile(".env"):
    from dotenv import load_dotenv

    load_dotenv(".env")


class DataBase:
    pool: asyncpg.Pool = None

    @classmethod
    async def connect(cls):
        dsn = os.getenv("dsn")
        if not dsn:
            raise ValueError("DSN is not set in the environment variables.")
        print(f"Connecting to database with DSN: {dsn}")
        cls.pool = await asyncpg.create_pool(dsn, statement_cache_size=0)

    @classmethod
    async def disconnect(cls):
        if cls.pool:
            await cls.pool.close()
