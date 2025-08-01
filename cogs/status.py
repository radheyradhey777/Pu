import discord
from discord.ext import commands, tasks
import os

TICKET_CATEGORY_ID = 1393886882668220486
GUILD_ID = 1380792281048678441

class Status(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.message_count = self.load_count("message_count.txt")
        self.status_index = 0
        self.update_status.start()

    def load_count(self, filename):
        return int(open(filename).read()) if os.path.exists(filename) else 0

    def save_count(self, filename, count):
        with open(filename, "w") as f:
            f.write(str(count))

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        if message.guild.id != GUILD_ID:
            return

        self.message_count += 1
        self.save_count("message_count.txt", self.message_count)

    @tasks.loop(seconds=20)
    async def update_status(self):
        guild = self.bot.get_guild(GUILD_ID)
        if not guild:
            return

        total_members = guild.member_count

        # Count tickets under the specified category in the specific guild
        category = discord.utils.get(guild.categories, id=TICKET_CATEGORY_ID)
        total_tickets = 0
        if category:
            total_tickets = len([c for c in category.channels if isinstance(c, discord.TextChannel)])

        statuses = [
            f"Tickets: {total_tickets}",
            f"Members: {total_members}",
            f"Messages: {self.message_count}",
            "CoRamTix"
        ]

        current = statuses[self.status_index % len(statuses)]
        await self.bot.change_presence(activity=discord.Game(name=current))
        self.status_index += 1

    @commands.Cog.listener()
    async def on_ready(self):
        print("✅ Status Cog loaded.")

async def setup(bot):
    await bot.add_cog(Status(bot))
