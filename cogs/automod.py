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

        # Track timestamps for spam detection
        self.spam_tracker[user_id].append(now)

        # 🛑 Spam Detection
        if len(self.spam_tracker[user_id]) == 4 and now - self.spam_tracker[user_id][0] <= self.SPAM_TIME_WINDOW:
            try:
                await message.channel.send(f"🛑 {message.author.mention}, spamming detected. Timeout for {self.TIMEOUT_DURATION} seconds.")
                await message.author.timeout(discord.utils.utcnow() + discord.timedelta(seconds=self.TIMEOUT_DURATION), reason="Spam")
            except Exception as e:
                print(f"[Spam Timeout Error]: {e}")

        # ❌ Discord Invite Links
        if re.search(self.invite_regex, message.content, re.IGNORECASE):
            await message.delete()
            try:
                await message.channel.send(f"❌ {message.author.mention}, Discord invites are not allowed.")
                await message.author.timeout(discord.utils.utcnow() + discord.timedelta(seconds=self.TIMEOUT_DURATION), reason="Invite Link")
            except:
                pass

        # 🔗 External Links
        elif re.search(self.url_regex, message.content, re.IGNORECASE):
            await message.delete()
            await message.channel.send(f"🔗 {message.author.mention}, external links are not allowed.")

async def setup(bot):
    await bot.add_cog(AutoMod(bot))
