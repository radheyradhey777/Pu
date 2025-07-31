import discord
from discord.ext import commands
import re

class AutoMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.invite_regex = re.compile(r"(?:https?://)?(?:www\.)?(?:discord\.gg|discord\.com/invite)/\S+")
        self.url_regex = re.compile(r"https?://\S+|www\.\S+")

        self.bad_words = {
            "fuck", "bitch", "shit", "asshole", "nude", "porn",
            "chutiya", "madarchod", "bhosdike", "gaand", "randi", "gandu", "suar",
            "bc", "mc", "tera baap", "chod diya", "gand mara", "ullu ka pattha", "kutte"
        }

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not isinstance(message.channel, discord.abc.GuildChannel):
            return

        # Skip users with Manage Server permission
        if isinstance(message.author, discord.Member):
            if message.author.guild_permissions.manage_guild:
                return

        content = message.content.lower()

        try:
            # Check for Discord invite links
            if self.invite_regex.search(content):
                await message.delete()
                await message.channel.send(
                    f"{message.author.mention}, Discord invite links are not allowed!",
                    delete_after=5
                )
                return

            # Check for general links
            if self.url_regex.search(content):
                await message.delete()
                await message.channel.send(
                    f"{message.author.mention}, Posting links is not allowed!",
                    delete_after=5
                )
                return

            # Check for bad words
            if any(bad_word in content for bad_word in self.bad_words):
                await message.delete()
                await message.channel.send(
                    f"{message.author.mention}, Please avoid using bad language!",
                    delete_after=5
                )
        except discord.Forbidden:
            print(f"❌ Missing permissions to delete message in: {message.channel}")
        except discord.HTTPException as e:
            print(f"⚠️ Error deleting message: {e}")

async def setup(bot):
    await bot.add_cog(AutoMod(bot))
