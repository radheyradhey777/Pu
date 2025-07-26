from discord.ext import commands
import discord
import re
import time
import asyncio
from collections import defaultdict
from typing import Dict, List, Set

class AutoMod(commands.Cog):
    """
    Professional Discord AutoMod System
    Features: Anti-Link, Anti-Spam, Bad Words Filter, Enhanced Moderation
    """
    
    def __init__(self, bot):
        self.bot = bot
        
        # Configuration
        self.BAD_WORDS = {
            "badword1", "badword2", "spam", "toxic", "inappropriate"
        }
        self.SPAM_THRESHOLD = 5
        self.SPAM_TIME_WINDOW = 10  # seconds
        self.MAX_MENTIONS = 5
        self.MAX_CAPS_PERCENTAGE = 70
        self.MIN_MESSAGE_LENGTH_FOR_CAPS = 10
        
        # Tracking dictionaries
        self.user_message_timestamps: Dict[int, List[float]] = defaultdict(list)
        self.user_warnings: Dict[int, int] = defaultdict(int)
        self.muted_users: Set[int] = set()
        
        # Whitelist (can be configured per server)
        self.whitelisted_roles = {"Moderator", "Admin", "Staff"}
        self.whitelisted_channels = {"links-allowed", "media"}
        
    def is_whitelisted(self, member: discord.Member, channel: discord.TextChannel) -> bool:
        """Check if user or channel is whitelisted from automod"""
        # Check role whitelist
        user_roles = {role.name for role in member.roles}
        if self.whitelisted_roles.intersection(user_roles):
            return True
            
        # Check channel whitelist
        if channel.name in self.whitelisted_channels:
            return True
            
        return False
    
    def contains_bad_words(self, content: str) -> bool:
        """Check if message contains bad words"""
        content_lower = content.lower()
        return any(word in content_lower for word in self.BAD_WORDS)
    
    def is_spam(self, user_id: int) -> bool:
        """Check if user is spamming based on time window"""
        current_time = time.time()
        
        # Add current message timestamp
        self.user_message_timestamps[user_id].append(current_time)
        
        # Remove old timestamps outside the time window
        self.user_message_timestamps[user_id] = [
            timestamp for timestamp in self.user_message_timestamps[user_id]
            if current_time - timestamp <= self.SPAM_TIME_WINDOW
        ]
        
        return len(self.user_message_timestamps[user_id]) > self.SPAM_THRESHOLD
    
    def is_excessive_caps(self, content: str) -> bool:
        """Check if message has excessive capital letters"""
        if len(content) < self.MIN_MESSAGE_LENGTH_FOR_CAPS:
            return False
            
        caps_count = sum(1 for char in content if char.isupper())
        caps_percentage = (caps_count / len(content)) * 100
        
        return caps_percentage > self.MAX_CAPS_PERCENTAGE
    
    def has_excessive_mentions(self, message: discord.Message) -> bool:
        """Check if message has too many mentions"""
        total_mentions = len(message.mentions) + len(message.role_mentions)
        return total_mentions > self.MAX_MENTIONS
    
    async def log_violation(self, message: discord.Message, violation_type: str, reason: str):
        """Log moderation actions (can be expanded to send to log channel)"""
        print(f"[AUTOMOD] {violation_type} | User: {message.author} | Reason: {reason}")
        
        # Increment user warnings
        self.user_warnings[message.author.id] += 1
        
        # You can expand this to send to a log channel:
        # log_channel = discord.utils.get(message.guild.channels, name="mod-logs")
        # if log_channel:
        #     embed = discord.Embed(title=f"AutoMod: {violation_type}", color=0xff0000)
        #     embed.add_field(name="User", value=message.author.mention)
        #     embed.add_field(name="Reason", value=reason)
        #     embed.add_field(name="Channel", value=message.channel.mention)
        #     await log_channel.send(embed=embed)
    
    async def safe_delete_message(self, message: discord.Message) -> bool:
        """Safely delete a message with error handling"""
        try:
            await message.delete()
            return True
        except discord.NotFound:
            # Message already deleted
            return False
        except discord.Forbidden:
            # Bot lacks permissions
            print(f"[AUTOMOD] Missing permissions to delete message in {message.channel}")
            return False
        except Exception as e:
            print(f"[AUTOMOD] Error deleting message: {e}")
            return False
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Main automod message listener"""
        # Ignore bot messages
        if message.author.bot:
            return
            
        # Ignore DMs
        if not message.guild:
            return
            
        # Check if user/channel is whitelisted
        if self.is_whitelisted(message.author, message.channel):
            return
        
        # Skip if user is muted (prevents spam of mod messages)
        if message.author.id in self.muted_users:
            await self.safe_delete_message(message)
            return
        
        # Anti-Link Detection
        if re.search(r"https?://(?:[-\w.])+(?:\:[0-9]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:\#(?:[\w.])*)?)?", message.content):
            if await self.safe_delete_message(message):
                await message.channel.send(
                    f"🚫 {message.author.mention}, links are not allowed in this channel.",
                    delete_after=10
                )
                await self.log_violation(message, "LINK_FILTER", "Posted unauthorized link")
            return
        
        # Bad Words Filter
        if self.contains_bad_words(message.content):
            if await self.safe_delete_message(message):
                await message.channel.send(
                    f"🤬 {message.author.mention}, please watch your language!",
                    delete_after=10
                )
                await self.log_violation(message, "BAD_WORDS", "Used inappropriate language")
            return
        
        # Excessive Mentions
        if self.has_excessive_mentions(message):
            if await self.safe_delete_message(message):
                await message.channel.send(
                    f"📢 {message.author.mention}, please don't mention too many users at once.",
                    delete_after=10
                )
                await self.log_violation(message, "EXCESSIVE_MENTIONS", f"Mentioned {len(message.mentions) + len(message.role_mentions)} users/roles")
            return
        
        # Excessive Caps
        if self.is_excessive_caps(message.content):
            if await self.safe_delete_message(message):
                await message.channel.send(
                    f"🔠 {message.author.mention}, please don't use excessive capital letters.",
                    delete_after=10
                )
                await self.log_violation(message, "EXCESSIVE_CAPS", "Used excessive capital letters")
            return
        
        # Anti-Spam Detection
        if self.is_spam(message.author.id):
            if await self.safe_delete_message(message):
                # Temporary mute for repeated spam
                self.muted_users.add(message.author.id)
                
                warning_msg = await message.channel.send(
                    f"⚠️ {message.author.mention}, you're sending messages too quickly! You've been temporarily muted for 30 seconds.",
                    delete_after=15
                )
                
                await self.log_violation(message, "SPAM", f"Exceeded {self.SPAM_THRESHOLD} messages in {self.SPAM_TIME_WINDOW} seconds")
                
                # Remove mute after 30 seconds
                await asyncio.sleep(30)
                self.muted_users.discard(message.author.id)
            return

    @commands.command(name="automod_stats")
    @commands.has_permissions(manage_messages=True)
    async def automod_stats(self, ctx):
        """Display automod statistics"""
        embed = discord.Embed(title="🛡️ AutoMod Statistics", color=0x3498db)
        
        total_warnings = sum(self.user_warnings.values())
        active_mutes = len(self.muted_users)
        tracked_users = len(self.user_message_timestamps)
        
        embed.add_field(name="Total Warnings Issued", value=total_warnings, inline=True)
        embed.add_field(name="Currently Muted Users", value=active_mutes, inline=True)
        embed.add_field(name="Users Being Monitored", value=tracked_users, inline=True)
        
        # Top violators
        if self.user_warnings:
            top_violator_id = max(self.user_warnings, key=self.user_warnings.get)
            top_violator = self.bot.get_user(top_violator_id)
            top_violations = self.user_warnings[top_violator_id]
            
            embed.add_field(
                name="Most Warnings", 
                value=f"{top_violator.mention if top_violator else 'Unknown User'}: {top_violations}",
                inline=False
            )
        
        embed.set_footer(text="AutoMod is keeping your server clean! 🧹")
        await ctx.send(embed=embed)
    
    @commands.command(name="reset_warnings")
    @commands.has_permissions(manage_messages=True)
    async def reset_warnings(self, ctx, member: discord.Member = None):
        """Reset warnings for a specific user or all users"""
        if member:
            if member.id in self.user_warnings:
                old_count = self.user_warnings[member.id]
                self.user_warnings[member.id] = 0
                await ctx.send(f"✅ Reset {old_count} warnings for {member.mention}")
            else:
                await ctx.send(f"{member.mention} has no warnings to reset.")
        else:
            # Reset all warnings
            total_reset = sum(self.user_warnings.values())
            self.user_warnings.clear()
            await ctx.send(f"✅ Reset all warnings ({total_reset} total warnings cleared)")
    
    @commands.command(name="unmute")
    @commands.has_permissions(manage_messages=True)
    async def unmute_user(self, ctx, member: discord.Member):
        """Manually unmute a user"""
        if member.id in self.muted_users:
            self.muted_users.remove(member.id)
            await ctx.send(f"✅ {member.mention} has been unmuted.")
        else:
            await ctx.send(f"{member.mention} is not currently muted by AutoMod.")

async def setup(bot):
    """Setup function to add the cog to the bot"""
    await bot.add_cog(AutoMod(bot))
