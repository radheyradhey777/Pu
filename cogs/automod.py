import discord
from discord.ext import commands
from collections import defaultdict, deque
import time
import re
import logging
from datetime import timedelta

# Set up logging
log = logging.getLogger(__name__)

class AutoMod(commands.Cog):
    """
    A cog for automatically moderating server activity, including spam,
    invite links, and other external links.
    """

    # --- Configuration ---
    # You can easily change these values
    SPAM_MESSAGES = 5  # Number of messages to be considered spam
    SPAM_WINDOW = 5.0  # Time window in seconds for spam detection
    TIMEOUT_DURATION_SECONDS = 60  # Duration of timeout in seconds
    IMMUNE_ROLE_NAMES = ["Admin", "Moderator", "Bot Admin"] # Roles exempt from automod

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # The spam tracker now uses a (guild_id, user_id) tuple as the key
        self.spam_tracker = defaultdict(lambda: deque(maxlen=self.SPAM_MESSAGES))

        # Pre-compile regex for efficiency
        self.INVITE_REGEX = re.compile(r"(https?:\/\/)?(www\.)?(discord\.gg|discord\.com\/invite)\/[a-zA-Z0-9]+", re.IGNORECASE)
        self.URL_REGEX = re.compile(r"https?:\/\/[^\s/$.?#].[^\s]*", re.IGNORECASE)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Processes messages to detect and act on violations."""
        # Ignore DMs, messages from bots, and messages from immune users
        if not message.guild or message.author.bot:
            return

        # Check for immunity based on roles
        if any(role.name in self.IMMUNE_ROLE_NAMES for role in message.author.roles):
            return

        # --- Violation Checks ---
        # The order of these checks is important.
        # We check for spam first, then more specific violations like invite links.

        # 1. Spam Detection
        if await self.handle_spam(message):
            return # Stop processing if user was punished for spam

        # 2. Discord Invite Link Detection
        if await self.handle_invite_links(message):
            return # Stop processing if user was punished for sending an invite

        # 3. General External Link Detection (optional, can be noisy)
        # if await self.handle_general_links(message):
        #     return

    async def handle_spam(self, message: discord.Message) -> bool:
        """Checks for and handles message spam."""
        user_key = (message.guild.id, message.author.id)
        now = time.time()
        self.spam_tracker[user_key].append(now)

        if len(self.spam_tracker[user_key]) == self.SPAM_MESSAGES:
            if now - self.spam_tracker[user_key][0] <= self.SPAM_WINDOW:
                reason = f"Spamming {self.SPAM_MESSAGES} messages in {self.SPAM_WINDOW} seconds."
                try:
                    timeout_duration = timedelta(seconds=self.TIMEOUT_DURATION_SECONDS)
                    await message.author.timeout(timeout_duration, reason=reason)
                    await message.channel.send(f"🛑 {message.author.mention}, spamming detected. Timed out for {self.TIMEOUT_DURATION_SECONDS} seconds.", delete_after=10)
                    log.info(f"Timed out {message.author} in '{message.guild.name}' for spam.")
                    return True
                except discord.Forbidden:
                    log.warning(f"Missing permissions to time out {message.author} in '{message.guild.name}' for spam.")
                except Exception as e:
                    log.error(f"An unexpected error occurred while handling spam from {message.author}: {e}")
        return False

    async def handle_invite_links(self, message: discord.Message) -> bool:
        """Checks for and handles Discord invite links."""
        if self.INVITE_REGEX.search(message.content):
            reason = "Sending a Discord invite link."
            try:
                await message.delete()
                timeout_duration = timedelta(seconds=self.TIMEOUT_DURATION_SECONDS)
                await message.author.timeout(timeout_duration, reason=reason)
                await message.channel.send(f"❌ {message.author.mention}, Discord invites are not allowed. You have been timed out.", delete_after=10)
                log.info(f"Deleted invite link from {message.author} and timed them out in '{message.guild.name}'.")
                return True
            except discord.Forbidden:
                log.warning(f"Missing permissions to moderate invite link from {message.author} in '{message.guild.name}'.")
            except Exception as e:
                log.error(f"An unexpected error occurred while handling invite link from {message.author}: {e}")
        return False

    async def handle_general_links(self, message: discord.Message) -> bool:
        """Checks for and handles general external links."""
        # This check should not match Discord invite links again
        if not self.INVITE_REGEX.search(message.content) and self.URL_REGEX.search(message.content):
            reason = "Sending an external link."
            try:
                await message.delete()
                # Optional: Timeout for general links as well
                # timeout_duration = timedelta(seconds=self.TIMEOUT_DURATION_SECONDS)
                # await message.author.timeout(timeout_duration, reason=reason)
                await message.channel.send(f"🔗 {message.author.mention}, external links are not allowed here.", delete_after=10)
                log.info(f"Deleted external link from {message.author} in '{message.guild.name}'.")
                return True
            except discord.Forbidden:
                log.warning(f"Missing permissions to moderate external link from {message.author} in '{message.guild.name}'.")
            except Exception as e:
                log.error(f"An unexpected error occurred while handling a link from {message.author}: {e}")
        return False


async def setup(bot: commands.Bot):
    """Standard setup function to load the cog."""
    await bot.add_cog(AutoMod(bot))
