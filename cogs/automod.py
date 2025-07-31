import discord
from discord.ext import commands
import re

class AutoMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.invite_regex = re.compile(r"(?:https?://)?(?:www\.)?(?:discord\.gg|discord\.com/invite)/\S+")
        self.url_regex = re.compile(r"https?://\S+|www\.\S+")
        with open("badwords.txt", "r", encoding="utf-8") as f:
            self.bad_words = set(line.strip().lower() for line in f if line.strip())

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or isinstance(message.channel, discord.DMChannel):
            return

        content = message.content.lower()

        # Check for invite links
        if self.invite_regex.search(content):
            await message.delete()
            await message.channel.send(f"{message.author.mention}, Discord invite links are not allowed.", delete_after=5)
            return

        # Check for general links
        if self.url_regex.search(content):
            await message.delete()
            await message.channel.send(f"{message.author.mention}, Links are not allowed.", delete_after=5)
            return

        # Check for bad words
        for word in self.bad_words:
            if word in content:
                await message.delete()
                await message.channel.send(f"{message.author.mention}, Watch your language!", delete_after=5)
                return

def setup(bot):
    bot.add_cog(AutoMod(bot))
