import asyncio
import os
from contextlib import asynccontextmanager

import aiofiles
import discord
from discord.ext import commands
from fastapi import FastAPI
from fastapi.responses import ORJSONResponse, HTMLResponse

from cogs.database import DataBase

if os.path.isfile(".env"):
    from dotenv import load_dotenv

    load_dotenv()

discord.utils.setup_logging()

intents = discord.Intents.default()
bot = commands.Bot("", intents=intents)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await DataBase.connect()
    asyncio.create_task(bot.start(os.getenv("discord")))
    yield
    await DataBase.disconnect()


app = FastAPI(lifespan=lifespan, default_response_class=ORJSONResponse)


@app.get("/")
async def index():
    async with aiofiles.open("./pages/index.html", encoding="utf8") as f:
        return HTMLResponse(await f.read())


@app.get("/api/getservers")
async def getservers():
    guilds = [
        {
            "name": guild.name,
            "icon": guild.icon.url,
            "memberCount": guild.member_count,
        }
        for guild in bot.guilds
    ]
    return guilds


@bot.event
async def setup_hook():
    await bot.load_extension("cogs.servers")
    await bot.tree.sync()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=10000)
