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
    LINK_TIMEOUT = 90  # Timeout for unauthorized links
    
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
    
    # Link filtering configuration
    LINK_WHITELIST_DOMAINS = [
        "youtube.com", "youtu.be", "imgur.com", "giphy.com", "tenor.com",
        "github.com", "stackoverflow.com", "wikipedia.org", "reddit.com",
        "twitter.com", "x.com", "instagram.com", "facebook.com", "tiktok.com"
    ]
    
    # Suspicious/malicious domains (add known bad domains)
    BLACKLISTED_DOMAINS = [
        # Add more suspicious shorteners and known malicious domains
        "scam-site.com", "phishing-example.com"
    ]
    
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
        
        # Link filtering settings per guild
        self.guild_link_settings = defaultdict(lambda: {
            "block_all_links": False,
            "allow_whitelisted_only": True,
            "block_shorteners": True,
            "block_ip_links": True,
            "block_file_uploads": False,
            "custom_whitelist": set(),
            "custom_blacklist": set()
        })
        
        # Pre-compile regex patterns for efficiency
        self.INVITE_REGEX = re.compile(
            r"(https?:\/\/)?(www\.)?(discord\.gg|discord\.com\/invite|discordapp\.com\/invite)\/[a-zA-Z0-9]+", 
            re.IGNORECASE
        )
        
        # Enhanced URL regex patterns
        self.URL_REGEX = re.compile(
            r"https?:\/\/(?:[-\w.])+(?:\:[0-9]+)?(?:\/(?:[\w\/_.])*(?:\?(?:[\w&=%.])*)?(?:\#(?:[\w.])*)?)?",
            re.IGNORECASE
        )
        
        # IP address regex (IPv4 and IPv6)
        self.IP_REGEX = re.compile(
            r"https?:\/\/(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)"
            r"|https?:\/\/(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}",
            re.IGNORECASE
        )
        
        # File upload links
        self.FILE_UPLOAD_REGEX = re.compile(
            r"https?:\/\/(?:www\.)?(?:mediafire|mega|dropbox|drive\.google|onedrive|wetransfer|sendspace|zippyshare)\.(?:com|co\.nz|live\.com)\/[^\s]+",
            re.IGNORECASE
        )
        
        # URL shorteners
        self.SHORTENER_REGEX = re.compile(
            r"https?:\/\/(?:www\.)?(?:bit\.ly|tinyurl\.com|t\.co|goo\.gl|ow\.ly|short\.link|is\.gd|v\.gd|tiny\.cc|buff\.ly)\/[^\s]+",
            re.IGNORECASE
        )
        
        self.REPEATED_CHAR_REGEX = re.compile(rf'(.)\1{{{self.MAX_REPEATED_CHARS},}}', re.IGNORECASE)
        
        # Compile profanity regex
        all_profanity = []
        for category in self.PROFANITY_WORDS.values():
            all_profanity.extend(category)
        self.PROFANITY_REGEX = re.compile(r'\b(' + '|'.join(re.escape(word) for word in all_profanity) + r')\b', re.IGNORECASE)

    def is_immune(self, member: discord.Member) -> bool:
        """Check if a member is immune to automod actions."""
        return any(role.name in self.IMMUNE_ROLE_NAMES for role in member.roles)

    def extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        # Remove protocol
        url = re.sub(r'^https?://', '', url)
        # Remove www.
        url = re.sub(r'^www\.', '', url)
        # Get domain part
        domain = url.split('/')[0].split('?')[0].split('#')[0]
        return domain.lower()

    def is_link_allowed(self, guild_id: int, url: str) -> tuple[bool, str]:
        """Check if a link is allowed based on guild settings."""
        settings = self.guild_link_settings[guild_id]
        domain = self.extract_domain(url)
        
        # Check if all links are blocked
        if settings["block_all_links"]:
            return False, "All links are blocked in this server"
        
        # Check custom blacklist first
        if domain in settings["custom_blacklist"]:
            return False, f"Domain '{domain}' is blacklisted"
        
        # Check global blacklist
        if domain in self.BLACKLISTED_DOMAINS:
            return False, f"Domain '{domain}' is globally blacklisted"
        
        # Check for IP addresses
        if settings["block_ip_links"] and self.IP_REGEX.match(url):
            return False, "IP address links are not allowed"
        
        # Check for URL shorteners
        if settings["block_shorteners"] and self.SHORTENER_REGEX.match(url):
            return False, "URL shorteners are not allowed"
        
        # Check for file upload sites
        if settings["block_file_uploads"] and self.FILE_UPLOAD_REGEX.match(url):
            return False, "File upload links are not allowed"
        
        # Check custom whitelist
        if domain in settings["custom_whitelist"]:
            return True, "Domain is whitelisted"
        
        # Check global whitelist
        if settings["allow_whitelisted_only"]:
            if domain in self.LINK_WHITELIST_DOMAINS:
                return True, "Domain is globally whitelisted"
            else:
                return False, f"Only whitelisted domains are allowed. '{domain}' is not whitelisted"
        
        # If not whitelist-only mode, allow by default
        return True, "Link is allowed"

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
        
        # 12. General external links (ENHANCED)
        if await self.handle_general_links(message):
            violations.append("external_links")

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
        """Enhanced general external link handling with whitelist/blacklist support."""
        # Skip if it's a Discord invite (handled separately)
        if self.INVITE_REGEX.search(message.content):
            return False
        
        # Find all URLs in the message
        urls = self.URL_REGEX.findall(message.content)
        if not urls:
            return False
        
        for url in urls:
            allowed, reason = self.is_link_allowed(message.guild.id, url)
            if not allowed:
                try:
                    await message.delete()
                    timeout_duration = timedelta(seconds=self.LINK_TIMEOUT)
                    await message.author.timeout(timeout_duration, reason=f"Unauthorized link: {reason}")
                    await message.channel.send(
                        f"🔗 {message.author.mention}, your link was blocked: {reason}",
                        delete_after=10
                    )
                    await self.log_violation(message.author, "Unauthorized Link", f"{url} - {reason}")
                    return True
                except (discord.Forbidden, discord.NotFound):
                    pass
        return False

    # --- Link Management Commands ---
    
    @commands.group(name="linkfilter", aliases=["lf"])
    @commands.has_permissions(manage_messages=True)
    async def link_filter(self, ctx):
        """Link filtering management commands."""
        if ctx.invoked_subcommand is None:
            settings = self.guild_link_settings[ctx.guild.id]
            embed = discord.Embed(title="🔗 Link Filter Settings", color=discord.Color.blue())
            embed.add_field(name="Block All Links", value=settings["block_all_links"], inline=True)
            embed.add_field(name="Whitelist Only", value=settings["allow_whitelisted_only"], inline=True)
            embed.add_field(name="Block Shorteners", value=settings["block_shorteners"], inline=True)
            embed.add_field(name="Block IP Links", value=settings["block_ip_links"], inline=True)
            embed.add_field(name="Block File Uploads", value=settings["block_file_uploads"], inline=True)
            embed.add_field(name="Custom Whitelist", value=len(settings["custom_whitelist"]), inline=True)
            embed.add_field(name="Custom Blacklist", value=len(settings["custom_blacklist"]), inline=True)
            await ctx.send(embed=embed)

    @link_filter.command(name="toggle")
    async def lf_toggle(self, ctx, setting: str):
        """Toggle link filter settings. Available: block_all, whitelist_only, shorteners, ip_links, file_uploads"""
        settings = self.guild_link_settings[ctx.guild.id]
        setting_map = {
            "block_all": "block_all_links",
            "whitelist_only": "allow_whitelisted_only", 
            "shorteners": "block_shorteners",
            "ip_links": "block_ip_links",
            "file_uploads": "block_file_uploads"
        }
        
        if setting not in setting_map:
            await ctx.send(f"❌ Invalid setting. Available: {', '.join(setting_map.keys())}")
            return
        
        key = setting_map[setting]
        settings[key] = not settings[key]
        status = "enabled" if settings[key] else "disabled"
        await ctx.send(f"✅ {setting.replace('_', ' ').title()} has been **{status}**")

    @link_filter.command(name="whitelist")
    async def lf_whitelist(self, ctx, action: str, domain: str = None):
        """Manage custom whitelist. Actions: add, remove, list"""
        settings = self.guild_link_settings[ctx.guild.id]
        
        if action == "list":
            if not settings["custom_whitelist"]:
                await ctx.send("📝 Custom whitelist is empty.")
            else:
                domains = "\n".join(settings["custom_whitelist"])
                embed = discord.Embed(title="📝 Custom Whitelist", description=domains, color=discord.Color.green())
                await ctx.send(embed=embed)
        
        elif action == "add" and domain:
            domain = domain.lower().replace("http://", "").replace("https://", "").replace("www.", "")
            settings["custom_whitelist"].add(domain)
            await ctx.send(f"✅ Added `{domain}` to whitelist")
        
        elif action == "remove" and domain:
            domain = domain.lower().replace("http://", "").replace("https://", "").replace("www.", "")
            if domain in settings["custom_whitelist"]:
                settings["custom_whitelist"].remove(domain)
                await ctx.send(f"✅ Removed `{domain}` from whitelist")
            else:
                await ctx.send(f"❌ `{domain}` not found in whitelist")
        
        else:
            await ctx.send("Usage: `linkfilter whitelist <add/remove/list> [domain]`")

    @link_filter.command(name="blacklist")
    async def lf_blacklist(self, ctx, action: str, domain: str = None):
        """Manage custom blacklist. Actions: add, remove, list"""
        settings = self.guild_link_settings[ctx.guild.id]
        
        if action == "list":
            if not settings["custom_blacklist"]:
                await ctx.send("📝 Custom blacklist is empty.")
            else:
                domains = "\n".join(settings["custom_blacklist"])
                embed = discord.Embed(title="📝 Custom Blacklist", description=domains, color=discord.Color.red())
                await ctx.send(embed=embed)
        
        elif action == "add" and domain:
            domain = domain.lower().replace("http://", "").replace("https://", "").replace("www.", "")
            settings["custom_blacklist"].add(domain)
            await ctx.send(f"✅ Added `{domain}` to blacklist")
        
        elif action == "remove" and domain:
            domain = domain.lower().replace("http://", "").replace("https://", "").replace("www.", "")
            if domain in settings["custom_blacklist"]:
                settings["custom_blacklist"].remove(domain)
                await ctx.send(f"✅ Removed `{domain}` from blacklist")
            else:
                await ctx.send(f"❌ `{domain}` not found in blacklist")
        
        else:
            await ctx.send("Usage: `linkfilter blacklist <add/remove/list> [domain]`")

    @link_filter.command(name="test")
    async def lf_test(self, ctx, url: str):
        """Test if a URL would be allowed or blocked."""
        allowed, reason = self.is_link_allowed(ctx.guild.id, url)
        color = discord.Color.green() if allowed else discord.Color.red()
        status = "✅ ALLOWED" if allowed else "❌ BLOCKED"
        
        embed = discord.Embed(title=f"🔍 Link Test: {status}", color=color)
        embed.add_field(name="URL", value=f"`{url}`", inline=False)
        embed.add_field(name="Domain", value=f"`{self.extract_domain(url)}`", inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        await ctx.send(embed=embed)

    # --- Original Moderation Commands ---
    
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
        
        embed = discord.Embed(title="📊 AutoMod Statistics", color=discord.Color.orange())
        embed.add_field(name="Total Violations", value=str(total_violations), inline=True)
        embed.add_field(name="Unique Offenders", value=str(len(guild_violations)), inline=True)
        
        if top_offenders:
            offenders_text = ""
            for (guild_id, user_id), violations in top_offenders:
                try:
                    user = await self.bot.fetch_user(user_id)
                    offenders_text += f"{user.mention}: **{violations}** violations\n"
                except discord.NotFound:
                    offenders_text += f"User ID `{user_id}`: **{violations}** violations (user not found)\n"
            
            embed.add_field(name="🏆 Top Offenders", value=offenders_text, inline=False)
        
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    """Loads the cog into the bot."""
    await bot.add_cog(AutoMod(bot))
    log.info("AutoMod cog has been loaded successfully.")
