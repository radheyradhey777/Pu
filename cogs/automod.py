import discord
from discord.ext import commands
import re
import requests

class AutoMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bad_words = self.fetch_bad_words()

        # Regex for invites and links
        self.invite_regex = re.compile(r"(?:https?://)?(?:www\.)?(?:discord\.gg|discord\.com/invite)/\S+")
        self.url_regex = re.compile(r"https?://\S+|www\.\S+")

    def fetch_bad_words(self):
        try:
            url = "https://gist.githubusercontent.com/realyashnag/104864931418cccdc9ace12975d4029d/raw/0cbafb97824b875f0556ad2e337d8c3334078553/AbusiveWords.json"
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                
                # Handle if it's a list directly
                if isinstance(data, list):
                    return set(word.lower() for word in data)
                
                # Handle if JSON is like {"bad_words": [...]}
                elif isinstance(data, dict) and "bad_words" in data:
                    return set(word.lower() for word in data["bad_words"])

            print(f"[AutoMod] Error: Status {response.status_code}")
        except Exception as e:
            print(f"[AutoMod] Failed to fetch bad words: {e}")
        return set()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        content = message.content.lower()

        # Check for abusive words
        if any(bad_word in content for bad_word in self.bad_words):
            await message.delete()
            await message.channel.send(f"{message.author.mention}, watch your language!", delete_after=5)
            return

        # Check for Discord invites
        if self.invite_regex.search(content):
            await message.delete()
            await message.channel.send(f"{message.author.mention}, Discord invites are not allowed!", delete_after=5)
            return

        # Check for URLs
        if self.url_regex.search(content):
            await message.delete()
            await message.channel.send(f"{message.author.mention}, posting links is not allowed!", delete_after=5)
            return

async def setup(bot):
    await bot.add_cog(AutoMod(bot))
