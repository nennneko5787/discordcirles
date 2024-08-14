import asyncio
import random
import traceback
import enum
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks
from discord import app_commands

from .database import DataBase


class RankingTypes(enum.Enum):
    Point = "Point"
    Rank = "Rank"


class ServersCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot
        self.cooldown: set[int] = set()
        self.serversPoint: dict[int, int] = {}

    @tasks.loop(seconds=1)
    async def serverReset(self):
        now = datetime.now(tz=ZoneInfo("Asia/Tokyo"))
        if now.hour == 0 and now.minute == 0:
            users = await DataBase.pool.fetch("SELECT * FROM users")
            for user in users:
                user = dict(user)
                user["rank"] = round(user["point"] / 10)
                user["point"] = 0
                await DataBase.pool.execute(
                    """
                    INSERT INTO users (id, username, displayname, icon, point, rank)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (id)
                    DO UPDATE SET
                        username = EXCLUDED.username,
                        displayname = EXCLUDED.displayname,
                        icon = EXCLUDED.icon,
                        point = EXCLUDED.point,
                        rank = EXCLUDED.rank;
                    """,
                    user["id"],
                    user["username"],
                    user["displayname"],
                    user["icon"],
                    user["point"],
                    user["rank"],
                )
        if (now.minute == 0 and now.hour >= 6) or len(self.serversPoint.keys()) <= 0:
            for guild in self.bot.guilds:
                self.serversPoint[guild.id] = random.randint(30, 100)

    @tasks.loop(seconds=20)
    async def presenceLoop(self):
        await self.bot.change_presence(
            activity=discord.Game(f"{len(self.bot.guilds)} サーバーが参加中")
        )

    @app_commands.command(
        name="ranking", description="ポイントとランクのランキングを表示します"
    )
    async def rankingCommand(
        self, interaction: discord.Interaction, type: RankingTypes
    ):
        await interaction.response.defer()
        if not bool(
            await DataBase.pool.fetchval(
                "SELECT value FROM metadata WHERE key = $1", "isevent"
            )
        ):
            await interaction.followup.send("現在はイベント期間中ではありません")
            return
        if type == RankingTypes.Point:
            users = await DataBase.pool.fetch(
                "SELECT * FROM users ORDER by point DESC LIMIT 10 OFFSET 0;"
            )
            rankingString = "\n".join(
                f"#{count} {user['displayname']} (@{user['username']}) **{user['point']}**pt."
                for count, user in enumerate(users, start=1)
            )
        else:
            users = await DataBase.pool.fetch(
                "SELECT * FROM users ORDER by rank DESC LIMIT 10 OFFSET 0;"
            )
            rankingString = "\n".join(
                f"#{count} {user['displayname']} (@{user['username']}) **{user['rank']}**pt."
                for count, user in enumerate(users, start=1)
            )
        embed = discord.Embed(
            title="TOP 10", description=rankingString, color=discord.Color.og_blurple()
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="status", description="あなたのステータスをチェックします"
    )
    async def statusCommand(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not bool(
            await DataBase.pool.fetchval(
                "SELECT value FROM metadata WHERE key = $1", "isevent"
            )
        ):
            await interaction.followup.send(
                "現在はイベント期間中ではありません", ephemeral=True
            )
            return
        user = await DataBase.pool.fetchrow(
            "SELECT * FROM users WHERE id = $1", interaction.user.id
        )
        pointRanking = await DataBase.pool.fetchval(
            """
                SELECT
                    ranking
                FROM
                    (
                        SELECT
                            id,
                            point,
                            RANK() OVER (ORDER BY point DESC) AS ranking
                        FROM
                            users
                    ) AS ranked_table
                WHERE
                    id = $1;
            """,
            interaction.user.id,
        )
        rankRanking = await DataBase.pool.fetchval(
            """
                SELECT
                    ranking
                FROM
                    (
                        SELECT
                            id,
                            rank,
                            RANK() OVER (ORDER BY rank DESC) AS ranking
                        FROM
                            users
                    ) AS ranked_table
                WHERE
                    id = $1;
            """,
            interaction.user.id,
        )
        embed = discord.Embed(
            title="Your Status",
            description=f"""
                ポイント: **{user['point']}**pt. (#{pointRanking})
                ランク: **{user['rank']}**pt. (#{rankRanking})
            """,
            color=discord.Color.og_blurple(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        self.serversPoint[guild.id] = random.randint(30, 100)

    @commands.Cog.listener()
    async def on_ready(self):
        self.presenceLoop.start()
        self.serverReset.start()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if (
            message.author.bot
            or message.author.id in self.cooldown
            or message.guild.id not in self.serversPoint
        ):
            return
        if not bool(
            await DataBase.pool.fetchval(
                "SELECT value FROM metadata WHERE key = $1", "isevent"
            )
        ):
            return

        self.cooldown.add(message.author.id)
        try:
            row = await DataBase.pool.fetchrow(
                "SELECT * FROM users WHERE id = $1", message.author.id
            )
            if not row:
                row = {
                    "id": message.author.id,
                    "username": message.author.name,
                    "displayname": message.author.display_name,
                    "icon": message.author.display_avatar.url,
                    "point": self.serversPoint[message.guild.id],
                    "rank": 0,
                }
            else:
                row = dict(row)
                row["username"] = message.author.name
                row["displayname"] = message.author.display_name
                row["icon"] = message.author.display_avatar.url
                row["point"] += self.serversPoint[message.guild.id]

            await DataBase.pool.execute(
                """
                INSERT INTO users (id, username, displayname, icon, point, rank)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (id)
                DO UPDATE SET
                    username = EXCLUDED.username,
                    displayname = EXCLUDED.displayname,
                    icon = EXCLUDED.icon,
                    point = EXCLUDED.point,
                    rank = EXCLUDED.rank;
                """,
                row["id"],
                row["username"],
                row["displayname"],
                row["icon"],
                row["point"],
                row["rank"],
            )
        except Exception:
            traceback.print_exc()
        finally:
            await asyncio.sleep(5)
            self.cooldown.remove(message.author.id)


async def setup(bot: commands.Bot):
    await bot.add_cog(ServersCog(bot))
