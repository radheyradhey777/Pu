import discord
from discord.ext import commands
import re
import requests

class AutoMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bad_words = self.fetch_bad_words()

        # Regex patterns
        self.invite_regex = re.compile(r"(?:https?://)?(?:www\.)?(?:discord\.gg|discord\.com/invite)/\S+")
        self.url_regex = re.compile(r"https?://\S+|www\.\S+")

    def fetch_bad_words(self):
        try:
            url = "https://raw.githubusercontent.com/radheyradhey777/Pu/main/bad_words.json"
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                return set(word.lower() for word in data.get("bad_words", []))
            else:
                print(f"[AutoMod] Failed to fetch bad words (Status {response.status_code})")
        except Exception as e:
            print(f"[AutoMod] Error fetching bad words: {e}")
        return set()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        content = message.content.lower()

        # Bad words
        if any(bad_word in content for bad_word in self.bad_words):
            await message.delete()
            await message.channel.send(f"{message.author.mention}, watch your language!", delete_after=5)
            return

        # Discord invites
        if self.invite_regex.search(content):
            await message.delete()
            await message.channel.send(f"{message.author.mention}, Discord invites are not allowed!", delete_after=5)
            return

        # URLs
        if self.url_regex.search(content):
            await message.delete()
            await message.channel.send(f"{message.author.mention}, posting links is not allowed!", delete_after=5)
            return

async def setup(bot):
    await bot.add_cog(AutoMod(bot))
