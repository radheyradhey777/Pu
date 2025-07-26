from discord.ext import commands
import discord
import re

BAD_WORDS = ["badword1", "badword2"]
SPAM_THRESHOLD = 5
user_message_count = {}

class AutoMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        # Anti-link
        if re.search(r"https?://", message.content):
            await message.delete()
            await message.channel.send(f"{message.author.mention}, links are not allowed.")
            return

        # Bad words
        if any(word in message.content.lower() for word in BAD_WORDS):
            await message.delete()
            await message.channel.send(f"{message.author.mention}, watch your language!")
            return

        # Anti-spam
        author_id = message.author.id
        user_message_count[author_id] = user_message_count.get(author_id, 0) + 1
        if user_message_count[author_id] > SPAM_THRESHOLD:
            await message.delete()
            await message.channel.send(f"{message.author.mention}, please stop spamming!")

async def setup(bot):
    await bot.add_cog(AutoMod(bot))
