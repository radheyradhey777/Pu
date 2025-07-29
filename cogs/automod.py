import discord
from discord.ext import commands
from collections import defaultdict, deque
import time
import re

class AutoMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.spam_tracker = defaultdict(lambda: deque(maxlen=4))
        self.SPAM_TIME_WINDOW = 5  # seconds
        self.TIMEOUT_DURATION = 60  # seconds

        self.invite_regex = r"(https?:\/\/)?(www\.)?(discord\.gg|discord\.com\/invite)\/\w+"
        self.url_regex = r"https?:\/\/[^\s]+"

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        user_id = message.author.id
        now = time.time()

        # Track message timestamps
        self.spam_tracker[user_id].append(now)

        # Spam Detection
        if len(self.spam_tracker[user_id]) == 4 and now - self.spam_tracker[user_id][0] <= self.SPAM_TIME_WINDOW:
            await message.channel.send(f"🚨 {message.author.mention}, slow down or you'll get a timeout like a bot in T-side rush B.")
            try:
                await message.author.timeout(discord.utils.utcnow() + discord.timedelta(seconds=self.TIMEOUT_DURATION), reason="Spam")
            except Exception as e:
                print(f"Spam Timeout Failed: {e}")

        # Anti-Invite
        if re.search(self.invite_regex, message.content):
            await message.delete()
            await message.channel.send(f"🛑 {message.author.mention}, Discord invites are not allowed!")
            try:
                await message.author.timeout(discord.utils.utcnow() + discord.timedelta(seconds=self.TIMEOUT_DURATION), reason="Discord Invite")
            except:
                pass

        # Anti-Link
        elif re.search(self.url_regex, message.content):
            await message.delete()
            await message.channel.send(f"🔗 {message.author.mention}, no links allowed in this server.")

def setup(bot):
    bot.add_cog(AutoMod(bot))
