import discord
from discord.ext import commands
from collections import defaultdict, deque
import time
import re
import logging
import asyncio
from datetime import timedelta
from typing import Set, List, Dict, Optional

# Set up logging
log = logging.getLogger(__name__)

class AutoMod(commands.Cog):
    """
    A comprehensive cog for automatically moderating server activity, including spam,
    invite links, profanity, caps spam, repeated characters, and other violations.
    """

    # --- Configuration ---
    # Spam Detection
    SPAM_MESSAGES = 5
    SPAM_WINDOW = 5.0
    
    # Timeout Durations (in seconds)
    SPAM_TIMEOUT = 60
    INVITE_TIMEOUT = 120
    PROFANITY_TIMEOUT = 300
    CAPS_TIMEOUT = 30
    REPEATED_CHAR_TIMEOUT = 45
    MASS_MENTION_TIMEOUT = 180
    
    # Content Limits
    MAX_CAPS_PERCENTAGE = 70  # Maximum percentage of caps allowed
    MIN_MESSAGE_LENGTH_FOR_CAPS = 10  # Minimum message length to check caps
    MAX_REPEATED_CHARS = 8  # Maximum repeated characters in a row
    MAX_MENTIONS = 5  # Maximum mentions allowed in a single message
    MAX_EMOJIS = 10  # Maximum emojis allowed in a single message
    MAX_MESSAGE_LENGTH = 2000  # Maximum message length
    
    # Rate Limiting
    MESSAGE_RATE_LIMIT = 10  # Messages per time window
    MESSAGE_RATE_WINDOW = 30.0  # Time window for rate limiting
    
    # Immune roles
    IMMUNE_ROLE_NAMES = ["Admin", "Moderator", "Bot Admin", "VIP"]
    
    # Profanity filter (add more words as needed)
    PROFANITY_WORDS = {
        "mild": ["damn", "hell", "crap"],
        "moderate": ["shit", "bitch", "ass"],
        "severe": ["fuck", "nigger", "faggot", "retard"]
    }
    
    # Suspicious patterns
    ZALGO_REGEX = re.compile(r'[\u0300-\u036f\u1ab0-\u1aff\u1dc0-\u1dff\u20d0-\u20ff\ufe20-\ufe2f]')
    EXCESSIVE_NEWLINES = re.compile(r'\n{4,}')
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
        # Tracking dictionaries
        self.spam_tracker = defaultdict(lambda: deque(maxlen=self.SPAM_MESSAGES))
        self.rate_limit_tracker = defaultdict(lambda: deque(maxlen=self.MESSAGE_RATE_LIMIT))
        self.violation_tracker = defaultdict(int)  # Track violations per user
        self.muted_users = set()  # Track temporarily muted users
        
        # Pre-compile regex patterns for efficiency
        self.INVITE_REGEX = re.compile(
            r"(https?:\/\/)?(www\.)?(discord\.gg|discord\.com\/invite|discordapp\.com\/invite)\/[a-zA-Z0-9]+", 
            re.IGNORECASE
        )
        self.URL_REGEX = re.compile(r"https?:\/\/[^\s/$.?#].[^\s]*", re.IGNORECASE)
        self.REPEATED_CHAR_REGEX = re.compile(rf'(.)\1{{{self.MAX_REPEATED_CHARS},}}', re.IGNORECASE)
        
        # Compile profanity regex
        all_profanity = []
        for category in self.PROFANITY_WORDS.values():
            all_profanity.extend(category)
        self.PROFANITY_REGEX = re.compile(r'\b(' + '|'.join(re.escape(word) for word in all_profanity) + r')\b', re.IGNORECASE)

    def is_immune(self, member: discord.Member) -> bool:
        """Check if a member is immune to automod actions."""
        return any(role.name in self.IMMUNE_ROLE_NAMES for role in member.roles)

    async def log_violation(self, member: discord.Member, violation_type: str, reason: str):
        """Log violations and track repeat offenders."""
        user_key = (member.guild.id, member.id)
        self.violation_tracker[user_key] += 1
        
        violation_count = self.violation_tracker[user_key]
        log.info(f"Violation #{violation_count} for {member} in '{member.guild.name}': {violation_type} - {reason}")
        
        # Escalate punishment for repeat offenders
        if violation_count >= 5:
            try:
                # Longer timeout for repeat offenders
                timeout_duration = timedelta(minutes=30)
                await member.timeout(timeout_duration, reason=f"Repeat offender: {violation_count} violations")
                log.warning(f"Escalated punishment for repeat offender {member}: 30-minute timeout")
            except discord.Forbidden:
                log.warning(f"Cannot escalate punishment for {member} - missing permissions")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Main message processing function."""
        # Ignore DMs, messages from bots, and messages from immune users
        if not message.guild or message.author.bot or self.is_immune(message.author):
            return

        # Check if user is temporarily muted
        if message.author.id in self.muted_users:
            try:
                await message.delete()
                return
            except discord.Forbidden:
                pass

        # Process all violation checks
        violations = []
        
        # 1. Rate limiting check
        if await self.check_rate_limit(message):
            violations.append("rate_limit")
        
        # 2. Spam detection
        if await self.handle_spam(message):
            violations.append("spam")
            return  # Stop processing if spam detected
        
        # 3. Message length check
        if await self.check_message_length(message):
            violations.append("message_length")
        
        # 4. Caps spam detection
        if await self.handle_caps_spam(message):
            violations.append("caps_spam")
        
        # 5. Repeated characters
        if await self.handle_repeated_characters(message):
            violations.append("repeated_chars")
        
        # 6. Mass mentions
        if await self.handle_mass_mentions(message):
            violations.append("mass_mentions")
        
        # 7. Excessive emojis
        if await self.handle_excessive_emojis(message):
            violations.append("excessive_emojis")
        
        # 8. Zalgo text (corrupted text)
        if await self.handle_zalgo_text(message):
            violations.append("zalgo_text")
        
        # 9. Excessive newlines
        if await self.handle_excessive_newlines(message):
            violations.append("excessive_newlines")
        
        # 10. Profanity filter
        if await self.handle_profanity(message):
            violations.append("profanity")
        
        # 11. Discord invite links
        if await self.handle_invite_links(message):
            violations.append("invite_links")
        
        # 12. General external links (optional)
        # if await self.handle_general_links(message):
        #     violations.append("external_links")

    async def check_rate_limit(self, message: discord.Message) -> bool:
        """Check if user is sending messages too quickly."""
        user_key = (message.guild.id, message.author.id)
        now = time.time()
        self.rate_limit_tracker[user_key].append(now)
        
        if len(self.rate_limit_tracker[user_key]) == self.MESSAGE_RATE_LIMIT:
            if now - self.rate_limit_tracker[user_key][0] <= self.MESSAGE_RATE_WINDOW:
                try:
                    await message.delete()
                    timeout_duration = timedelta(seconds=30)
                    await message.author.timeout(timeout_duration, reason="Rate limit exceeded")
                    await message.channel.send(
                        f"⚠️ {message.author.mention}, you're sending messages too quickly. Slow down!",
                        delete_after=10
                    )
                    await self.log_violation(message.author, "Rate Limit", "Sending messages too quickly")
                    return True
                except (discord.Forbidden, discord.NotFound):
                    pass
        return False

    async def handle_spam(self, message: discord.Message) -> bool:
        """Enhanced spam detection."""
        user_key = (message.guild.id, message.author.id)
        now = time.time()
        self.spam_tracker[user_key].append(now)

        if len(self.spam_tracker[user_key]) == self.SPAM_MESSAGES:
            if now - self.spam_tracker[user_key][0] <= self.SPAM_WINDOW:
                reason = f"Spamming {self.SPAM_MESSAGES} messages in {self.SPAM_WINDOW} seconds"
                try:
                    timeout_duration = timedelta(seconds=self.SPAM_TIMEOUT)
                    await message.author.timeout(timeout_duration, reason=reason)
                    await message.channel.send(
                        f"🛑 {message.author.mention}, spam detected. Timed out for {self.SPAM_TIMEOUT} seconds.",
                        delete_after=10
                    )
                    await self.log_violation(message.author, "Spam", reason)
                    return True
                except (discord.Forbidden, discord.NotFound):
                    log.warning(f"Cannot timeout {message.author} for spam - missing permissions")
        return False

    async def check_message_length(self, message: discord.Message) -> bool:
        """Check for excessively long messages."""
        if len(message.content) > self.MAX_MESSAGE_LENGTH:
            try:
                await message.delete()
                await message.channel.send(
                    f"📏 {message.author.mention}, your message was too long and has been removed.",
                    delete_after=10
                )
                await self.log_violation(message.author, "Long Message", f"Message length: {len(message.content)}")
                return True
            except (discord.Forbidden, discord.NotFound):
                pass
        return False

    async def handle_caps_spam(self, message: discord.Message) -> bool:
        """Detect and handle excessive capital letters."""
        content = message.content
        if len(content) < self.MIN_MESSAGE_LENGTH_FOR_CAPS:
            return False
        
        caps_count = sum(1 for c in content if c.isupper())
        caps_percentage = (caps_count / len(content)) * 100
        
        if caps_percentage > self.MAX_CAPS_PERCENTAGE:
            try:
                await message.delete()
                timeout_duration = timedelta(seconds=self.CAPS_TIMEOUT)
                await message.author.timeout(timeout_duration, reason="Excessive caps usage")
                await message.channel.send(
                    f"🔠 {message.author.mention}, please don't use excessive capital letters.",
                    delete_after=10
                )
                await self.log_violation(message.author, "Caps Spam", f"Caps percentage: {caps_percentage:.1f}%")
                return True
            except (discord.Forbidden, discord.NotFound):
                pass
        return False

    async def handle_repeated_characters(self, message: discord.Message) -> bool:
        """Handle messages with too many repeated characters."""
        if self.REPEATED_CHAR_REGEX.search(message.content):
            try:
                await message.delete()
                timeout_duration = timedelta(seconds=self.REPEATED_CHAR_TIMEOUT)
                await message.author.timeout(timeout_duration, reason="Excessive repeated characters")
                await message.channel.send(
                    f"🔄 {message.author.mention}, please don't spam repeated characters.",
                    delete_after=10
                )
                await self.log_violation(message.author, "Repeated Characters", "Too many repeated characters")
                return True
            except (discord.Forbidden, discord.NotFound):
                pass
        return False

    async def handle_mass_mentions(self, message: discord.Message) -> bool:
        """Handle messages with too many mentions."""
        total_mentions = len(message.mentions) + len(message.role_mentions)
        
        if total_mentions > self.MAX_MENTIONS:
            try:
                await message.delete()
                timeout_duration = timedelta(seconds=self.MASS_MENTION_TIMEOUT)
                await message.author.timeout(timeout_duration, reason="Mass mentioning")
                await message.channel.send(
                    f"📢 {message.author.mention}, please don't mention too many users/roles at once.",
                    delete_after=10
                )
                await self.log_violation(message.author, "Mass Mentions", f"Mentioned {total_mentions} users/roles")
                return True
            except (discord.Forbidden, discord.NotFound):
                pass
        return False

    async def handle_excessive_emojis(self, message: discord.Message) -> bool:
        """Handle messages with too many emojis."""
        # Count Unicode emojis and custom emojis
        unicode_emoji_count = len(re.findall(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U0001F251]+', message.content))
        custom_emoji_count = len(re.findall(r'<a?:[a-zA-Z0-9_]+:[0-9]+>', message.content))
        total_emojis = unicode_emoji_count + custom_emoji_count
        
        if total_emojis > self.MAX_EMOJIS:
            try:
                await message.delete()
                await message.channel.send(
                    f"😵 {message.author.mention}, please don't use too many emojis in one message.",
                    delete_after=10
                )
                await self.log_violation(message.author, "Excessive Emojis", f"Used {total_emojis} emojis")
                return True
            except (discord.Forbidden, discord.NotFound):
                pass
        return False

    async def handle_zalgo_text(self, message: discord.Message) -> bool:
        """Handle zalgo/corrupted text."""
        if self.ZALGO_REGEX.search(message.content):
            try:
                await message.delete()
                await message.channel.send(
                    f"🌀 {message.author.mention}, please don't use corrupted text.",
                    delete_after=10
                )
                await self.log_violation(message.author, "Zalgo Text", "Used corrupted/zalgo text")
                return True
            except (discord.Forbidden, discord.NotFound):
                pass
        return False

    async def handle_excessive_newlines(self, message: discord.Message) -> bool:
        """Handle messages with too many newlines."""
        if self.EXCESSIVE_NEWLINES.search(message.content):
            try:
                await message.delete()
                await message.channel.send(
                    f"📄 {message.author.mention}, please don't use excessive line breaks.",
                    delete_after=10
                )
                await self.log_violation(message.author, "Excessive Newlines", "Too many line breaks")
                return True
            except (discord.Forbidden, discord.NotFound):
                pass
        return False

    async def handle_profanity(self, message: discord.Message) -> bool:
        """Handle profanity in messages."""
        if self.PROFANITY_REGEX.search(message.content):
            try:
                await message.delete()
                timeout_duration = timedelta(seconds=self.PROFANITY_TIMEOUT)
                await message.author.timeout(timeout_duration, reason="Using inappropriate language")
                await message.channel.send(
                    f"🤐 {message.author.mention}, inappropriate language is not allowed.",
                    delete_after=10
                )
                await self.log_violation(message.author, "Profanity", "Used inappropriate language")
                return True
            except (discord.Forbidden, discord.NotFound):
                pass
        return False

    async def handle_invite_links(self, message: discord.Message) -> bool:
        """Enhanced invite link detection."""
        if self.INVITE_REGEX.search(message.content):
            try:
                await message.delete()
                timeout_duration = timedelta(seconds=self.INVITE_TIMEOUT)
                await message.author.timeout(timeout_duration, reason="Sending Discord invite links")
                await message.channel.send(
                    f"❌ {message.author.mention}, Discord invites are not allowed. Timed out for {self.INVITE_TIMEOUT} seconds.",
                    delete_after=10
                )
                await self.log_violation(message.author, "Invite Link", "Sent Discord invite link")
                return True
            except (discord.Forbidden, discord.NotFound):
                pass
        return False

    async def handle_general_links(self, message: discord.Message) -> bool:
        """Handle general external links (optional)."""
        if not self.INVITE_REGEX.search(message.content) and self.URL_REGEX.search(message.content):
            try:
                await message.delete()
                await message.channel.send(
                    f"🔗 {message.author.mention}, external links are not allowed here.",
                    delete_after=10
                )
                await self.log_violation(message.author, "External Link", "Sent external link")
                return True
            except (discord.Forbidden, discord.NotFound):
                pass
        return False

    # --- Moderation Commands ---
    
    @commands.command(name="automod_stats")
    @commands.has_permissions(manage_messages=True)
    async def automod_stats(self, ctx):
        """Show automod statistics for the server."""
        guild_violations = {k: v for k, v in self.violation_tracker.items() if k[0] == ctx.guild.id}
        
        if not guild_violations:
            await ctx.send("No violations recorded for this server.")
            return
        
        total_violations = sum(guild_violations.values())
        top_offenders = sorted(guild_violations.items(), key=lambda x: x[1], reverse=True)[:5]
        
        embed = discord.Embed(title="AutoMod Statistics", color=discord.Color.red())
        embed.add_field(name="Total Violations", value=str(total_violations), inline=True)
        embed.add_field(name="Unique Users", value=str(len(guild_violations)), inline=True)
        
        if top_offenders:
            offenders_text = ""
            for (guild_id, user_id), violations in top_offenders:
                user = self.bot.get_user(user_id)
                user_name = user.name if user else f"Unknown User ({user_id})"
                offenders_text += f"{user_name}: {violations} violations\n"
            
            embed.add_field(name="Top Offenders", value=offenders_text, inline=False)
        
        await ctx.send(embed=embed)

    @commands.command(name="reset_violations")
    @commands.has_permissions(administrator=True)
    async def reset_violations(self, ctx, user: discord.Member = None):
        """Reset violation count for a user or all users."""
        if user:
            user_key = (ctx.guild.id, user.id)
            if user_key in self.violation_tracker:
                del self.violation_tracker[user_key]
                await ctx.send(f"✅ Reset violations for {user.mention}")
            else:
                await ctx.send(f"No violations found for {user.mention}")
        else:
            # Reset all violations for this guild
            guild_keys = [k for k in self.violation_tracker.keys() if k[0] == ctx.guild.id]
            for key in guild_keys:
                del self.violation_tracker[key]
            await ctx.send(f"✅ Reset all violations for this server ({len(guild_keys)} users)")

    @commands.command(name="temp_mute")
    @commands.has_permissions(manage_messages=True)
    async def temp_mute(self, ctx, user: discord.Member, duration: int = 300):
        """Temporarily mute a user (their messages will be auto-deleted)."""
        self.muted_users.add(user.id)
        await ctx.send(f"🔇 {user.mention} has been temporarily muted for {duration} seconds.")
        
        # Remove mute after duration
        await asyncio.sleep(duration)
        self.muted_users.discard(user.id)
        
        try:
            await ctx.send(f"🔊 {user.mention} has been unmuted.")
        except:
            pass  # Channel might be deleted

    @commands.command(name="unmute")
    @commands.has_permissions(manage_messages=True)
    async def unmute(self, ctx, user: discord.Member):
        """Unmute a temporarily muted user."""
        if user.id in self.muted_users:
            self.muted_users.remove(user.id)
            await ctx.send(f"🔊 {user.mention} has been unmuted.")
        else:
            await ctx.send(f"{user.mention} is not currently muted.")


async def setup(bot: commands.Bot):
    """Standard setup function to load the cog."""
    await bot.add_cog(AutoMod(bot))
