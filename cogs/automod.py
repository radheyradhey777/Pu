from discord.ext import commands
import discord
import re
import time
import asyncio
import json
import os
from collections import defaultdict
from typing import Dict, List, Set, Optional
from datetime import datetime, timedelta

class AutoMod(commands.Cog):
    """
    Enhanced Professional Discord AutoMod System
    Features: Anti-Link, Anti-Spam, Bad Words Filter, Enhanced Moderation, Per-Guild Config
    """
    
    def __init__(self, bot):
        self.bot = bot
        
        # Default Configuration (per guild)
        self.default_config = {
            "bad_words": ["badword1", "badword2", "spam", "toxic", "inappropriate"],
            "spam_threshold": 5,
            "spam_time_window": 10,
            "max_mentions": 5,
            "max_caps_percentage": 70,
            "min_message_length_for_caps": 10,
            "mute_duration": 30,
            "whitelisted_roles": ["Moderator", "Admin", "Staff"],
            "whitelisted_channels": ["links-allowed", "media"],
            "allowed_domains": ["youtube.com", "youtu.be", "github.com", "discord.gg"],
            "log_channel": None,
            "enabled_features": {
                "anti_link": True,
                "bad_words": True,
                "anti_spam": True,
                "excessive_caps": True,
                "excessive_mentions": True
            }
        }
        
        # Tracking dictionaries (per guild)
        self.guild_configs: Dict[int, dict] = {}
        self.user_message_timestamps: Dict[int, Dict[int, List[float]]] = defaultdict(lambda: defaultdict(list))
        self.user_warnings: Dict[int, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
        self.muted_users: Dict[int, Set[int]] = defaultdict(set)
        self.user_violations: Dict[int, Dict[int, List[dict]]] = defaultdict(lambda: defaultdict(list))
        
        # Load configurations
        self.load_configs()
        
    def load_configs(self):
        """Load guild configurations from file"""
        try:
            if os.path.exists('automod_configs.json'):
                with open('automod_configs.json', 'r') as f:
                    self.guild_configs = {int(k): v for k, v in json.load(f).items()}
        except Exception as e:
            print(f"[AUTOMOD] Error loading configs: {e}")
    
    def save_configs(self):
        """Save guild configurations to file"""
        try:
            with open('automod_configs.json', 'w') as f:
                json.dump({str(k): v for k, v in self.guild_configs.items()}, f, indent=2)
        except Exception as e:
            print(f"[AUTOMOD] Error saving configs: {e}")
    
    def get_guild_config(self, guild_id: int) -> dict:
        """Get configuration for a specific guild"""
        if guild_id not in self.guild_configs:
            self.guild_configs[guild_id] = self.default_config.copy()
            self.save_configs()
        return self.guild_configs[guild_id]
    
    def is_whitelisted(self, member: discord.Member, channel: discord.TextChannel) -> bool:
        """Check if user or channel is whitelisted from automod"""
        config = self.get_guild_config(member.guild.id)
        
        # Check role whitelist
        user_roles = {role.name for role in member.roles}
        if set(config["whitelisted_roles"]).intersection(user_roles):
            return True
            
        # Check channel whitelist
        if channel.name in config["whitelisted_channels"]:
            return True
            
        return False
    
    def contains_bad_words(self, content: str, guild_id: int) -> List[str]:
        """Check if message contains bad words, return found words"""
        config = self.get_guild_config(guild_id)
        content_lower = re.sub(r'[^\w\s]', '', content.lower())
        found_words = []
        
        for word in config["bad_words"]:
            pattern = r'\b' + re.escape(word) + r'\b'
            if re.search(pattern, content_lower):
                found_words.append(word)
        
        return found_words
    
    def contains_unauthorized_links(self, content: str, guild_id: int) -> List[str]:
        """Check for links, excluding whitelisted domains"""
        config = self.get_guild_config(guild_id)
        url_pattern = r'https?://(?:[-\w.])+(?:\:[0-9]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:\#(?:[\w.])*)?)?'
        urls = re.findall(url_pattern, content)
        unauthorized_urls = []
        
        for url in urls:
            domain_match = re.search(r'https?://(?:www\.)?([^/]+)', url)
            if domain_match:
                domain = domain_match.group(1)
                if not any(allowed in domain for allowed in config["allowed_domains"]):
                    unauthorized_urls.append(url)
        
        return unauthorized_urls
    
    def is_spam(self, user_id: int, guild_id: int) -> bool:
        """Check if user is spamming based on time window"""
        config = self.get_guild_config(guild_id)
        current_time = time.time()
        
        # Add current message timestamp
        self.user_message_timestamps[guild_id][user_id].append(current_time)
        
        # Remove old timestamps outside the time window
        self.user_message_timestamps[guild_id][user_id] = [
            timestamp for timestamp in self.user_message_timestamps[guild_id][user_id]
            if current_time - timestamp <= config["spam_time_window"]
        ]
        
        return len(self.user_message_timestamps[guild_id][user_id]) > config["spam_threshold"]
    
    def is_excessive_caps(self, content: str, guild_id: int) -> bool:
        """Check if message has excessive capital letters"""
        config = self.get_guild_config(guild_id)
        
        if len(content) < config["min_message_length_for_caps"]:
            return False
            
        caps_count = sum(1 for char in content if char.isupper())
        caps_percentage = (caps_count / len(content)) * 100
        
        return caps_percentage > config["max_caps_percentage"]
    
    def has_excessive_mentions(self, message: discord.Message) -> bool:
        """Check if message has too many mentions"""
        config = self.get_guild_config(message.guild.id)
        total_mentions = len(message.mentions) + len(message.role_mentions)
        return total_mentions > config["max_mentions"]
    
    async def log_violation(self, message: discord.Message, violation_type: str, reason: str, details: str = ""):
        """Enhanced logging with embed and channel support"""
        guild_id = message.guild.id
        user_id = message.author.id
        
        # Record violation
        violation_data = {
            "type": violation_type,
            "reason": reason,
            "details": details,
            "timestamp": datetime.now().isoformat(),
            "channel": message.channel.name
        }
        
        self.user_violations[guild_id][user_id].append(violation_data)
        self.user_warnings[guild_id][user_id] += 1
        
        print(f"[AUTOMOD] {violation_type} | Guild: {message.guild.name} | User: {message.author} | Reason: {reason}")
        
        # Send to log channel if configured
        config = self.get_guild_config(guild_id)
        if config.get("log_channel"):
            log_channel = discord.utils.get(message.guild.channels, name=config["log_channel"])
            if log_channel:
                embed = discord.Embed(
                    title=f"🛡️ AutoMod: {violation_type}",
                    color=0xff6b6b,
                    timestamp=datetime.now()
                )
                embed.add_field(name="👤 User", value=f"{message.author.mention} ({message.author})", inline=True)
                embed.add_field(name="📍 Channel", value=message.channel.mention, inline=True)
                embed.add_field(name="⚠️ Warnings", value=self.user_warnings[guild_id][user_id], inline=True)
                embed.add_field(name="📝 Reason", value=reason, inline=False)
                
                if details:
                    embed.add_field(name="🔍 Details", value=details, inline=False)
                
                # Show original message content (truncated)
                content_preview = message.content[:100] + "..." if len(message.content) > 100 else message.content
                if content_preview:
                    embed.add_field(name="💬 Message", value=f"```{content_preview}```", inline=False)
                
                embed.set_footer(text=f"User ID: {message.author.id}")
                
                try:
                    await log_channel.send(embed=embed)
                except Exception as e:
                    print(f"[AUTOMOD] Error sending to log channel: {e}")
    
    async def safe_delete_message(self, message: discord.Message) -> bool:
        """Safely delete a message with error handling"""
        try:
            await message.delete()
            return True
        except discord.NotFound:
            return False
        except discord.Forbidden:
            print(f"[AUTOMOD] Missing permissions to delete message in {message.channel}")
            return False
        except Exception as e:
            print(f"[AUTOMOD] Error deleting message: {e}")
            return False
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Enhanced main automod message listener"""
        # Ignore bot messages and DMs
        if message.author.bot or not message.guild:
            return
            
        guild_id = message.guild.id
        config = self.get_guild_config(guild_id)
        
        # Check if user/channel is whitelisted
        if self.is_whitelisted(message.author, message.channel):
            return
        
        # Skip if user is muted
        if message.author.id in self.muted_users[guild_id]:
            await self.safe_delete_message(message)
            return
        
        # Anti-Link Detection
        if config["enabled_features"]["anti_link"]:
            unauthorized_links = self.contains_unauthorized_links(message.content, guild_id)
            if unauthorized_links:
                if await self.safe_delete_message(message):
                    await message.channel.send(
                        f"🚫 {message.author.mention}, unauthorized links are not allowed in this channel.",
                        delete_after=10
                    )
                    await self.log_violation(
                        message, "UNAUTHORIZED_LINK", 
                        "Posted unauthorized link", 
                        f"Links: {', '.join(unauthorized_links[:3])}"
                    )
                return
        
        # Bad Words Filter
        if config["enabled_features"]["bad_words"]:
            found_words = self.contains_bad_words(message.content, guild_id)
            if found_words:
                if await self.safe_delete_message(message):
                    await message.channel.send(
                        f"🤬 {message.author.mention}, please watch your language!",
                        delete_after=10
                    )
                    await self.log_violation(
                        message, "INAPPROPRIATE_LANGUAGE", 
                        "Used inappropriate language", 
                        f"Words: {', '.join(found_words)}"
                    )
                return
        
        # Excessive Mentions
        if config["enabled_features"]["excessive_mentions"] and self.has_excessive_mentions(message):
            if await self.safe_delete_message(message):
                total_mentions = len(message.mentions) + len(message.role_mentions)
                await message.channel.send(
                    f"📢 {message.author.mention}, please don't mention too many users at once.",
                    delete_after=10
                )
                await self.log_violation(
                    message, "EXCESSIVE_MENTIONS", 
                    f"Mentioned {total_mentions} users/roles", 
                    f"Limit: {config['max_mentions']}"
                )
            return
        
        # Excessive Caps
        if config["enabled_features"]["excessive_caps"] and self.is_excessive_caps(message.content, guild_id):
            if await self.safe_delete_message(message):
                await message.channel.send(
                    f"🔠 {message.author.mention}, please don't use excessive capital letters.",
                    delete_after=10
                )
                await self.log_violation(
                    message, "EXCESSIVE_CAPS", 
                    "Used excessive capital letters"
                )
            return
        
        # Anti-Spam Detection
        if config["enabled_features"]["anti_spam"] and self.is_spam(message.author.id, guild_id):
            if await self.safe_delete_message(message):
                # Temporary mute
                self.muted_users[guild_id].add(message.author.id)
                
                mute_duration = config["mute_duration"]
                await message.channel.send(
                    f"⚠️ {message.author.mention}, you're sending messages too quickly! "
                    f"You've been temporarily muted for {mute_duration} seconds.",
                    delete_after=15
                )
                
                await self.log_violation(
                    message, "SPAM", 
                    f"Exceeded {config['spam_threshold']} messages in {config['spam_time_window']} seconds"
                )
                
                # Remove mute after duration
                await asyncio.sleep(mute_duration)
                self.muted_users[guild_id].discard(message.author.id)
            return

    @commands.group(name="automod", invoke_without_command=True)
    @commands.has_permissions(manage_messages=True)
    async def automod(self, ctx):
        """Main automod command group"""
        embed = discord.Embed(
            title="🛡️ AutoMod System",
            description="Professional Discord moderation system",
            color=0x3498db
        )
        
        embed.add_field(
            name="📊 Commands",
            value=(
                "`!automod stats` - View moderation statistics\n"
                "`!automod config` - View current configuration\n"
                "`!automod toggle <feature>` - Toggle features on/off\n"
                "`!automod reset [user]` - Reset warnings\n"
                "`!automod unmute <user>` - Manually unmute user\n"
                "`!automod violations <user>` - View user violations"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔧 Configuration",
            value=(
                "`!automod set spam_threshold <number>`\n"
                "`!automod set max_mentions <number>`\n"
                "`!automod set log_channel <channel_name>`\n"
                "`!automod whitelist role <role_name>`\n"
                "`!automod whitelist channel <channel_name>`"
            ),
            inline=False
        )
        
        await ctx.send(embed=embed)

    @automod.command(name="stats")
    async def automod_stats(self, ctx):
        """Display detailed automod statistics"""
        guild_id = ctx.guild.id
        
        embed = discord.Embed(title="🛡️ AutoMod Statistics", color=0x3498db)
        
        total_warnings = sum(self.user_warnings[guild_id].values())
        active_mutes = len(self.muted_users[guild_id])
        tracked_users = len(self.user_message_timestamps[guild_id])
        total_violations = sum(len(violations) for violations in self.user_violations[guild_id].values())
        
        embed.add_field(name="📊 Total Warnings", value=total_warnings, inline=True)
        embed.add_field(name="🔇 Active Mutes", value=active_mutes, inline=True)
        embed.add_field(name="👥 Monitored Users", value=tracked_users, inline=True)
        embed.add_field(name="⚠️ Total Violations", value=total_violations, inline=True)
        
        # Violation breakdown
        violation_types = {}
        for user_violations in self.user_violations[guild_id].values():
            for violation in user_violations:
                v_type = violation["type"]
                violation_types[v_type] = violation_types.get(v_type, 0) + 1
        
        if violation_types:
            breakdown = "\n".join([f"{vtype}: {count}" for vtype, count in violation_types.items()])
            embed.add_field(name="📈 Violation Types", value=f"```{breakdown}```", inline=False)
        
        # Top violator
        if self.user_warnings[guild_id]:
            top_violator_id = max(self.user_warnings[guild_id], key=self.user_warnings[guild_id].get)
            top_violator = self.bot.get_user(top_violator_id)
            top_violations = self.user_warnings[guild_id][top_violator_id]
            
            embed.add_field(
                name="🏆 Most Warnings", 
                value=f"{top_violator.mention if top_violator else 'Unknown User'}: {top_violations}",
                inline=False
            )
        
        embed.set_footer(text="AutoMod is keeping your server clean! 🧹")
        await ctx.send(embed=embed)
    
    @automod.command(name="config")
    async def view_config(self, ctx):
        """View current automod configuration"""
        config = self.get_guild_config(ctx.guild.id)
        
        embed = discord.Embed(title="⚙️ AutoMod Configuration", color=0x95a5a6)
        
        # Feature status
        features = config["enabled_features"]
        feature_status = "\n".join([
            f"{'✅' if enabled else '❌'} {feature.replace('_', ' ').title()}"
            for feature, enabled in features.items()
        ])
        embed.add_field(name="🔧 Features", value=feature_status, inline=True)
        
        # Limits
        limits = (
            f"Spam Threshold: {config['spam_threshold']}\n"
            f"Spam Window: {config['spam_time_window']}s\n"
            f"Max Mentions: {config['max_mentions']}\n"
            f"Max Caps: {config['max_caps_percentage']}%\n"
            f"Mute Duration: {config['mute_duration']}s"
        )
        embed.add_field(name="📏 Limits", value=limits, inline=True)
        
        # Whitelists
        whitelist_info = (
            f"Roles: {', '.join(config['whitelisted_roles'])}\n"
            f"Channels: {', '.join(config['whitelisted_channels'])}\n"
            f"Log Channel: {config.get('log_channel', 'Not set')}"
        )
        embed.add_field(name="📝 Whitelists", value=whitelist_info, inline=False)
        
        await ctx.send(embed=embed)
    
    @automod.command(name="toggle")
    async def toggle_feature(self, ctx, feature: str):
        """Toggle automod features on/off"""
        config = self.get_guild_config(ctx.guild.id)
        
        if feature not in config["enabled_features"]:
            available = ", ".join(config["enabled_features"].keys())
            await ctx.send(f"❌ Invalid feature. Available: {available}")
            return
        
        config["enabled_features"][feature] = not config["enabled_features"][feature]
        self.save_configs()
        
        status = "enabled" if config["enabled_features"][feature] else "disabled"
        await ctx.send(f"✅ {feature.replace('_', ' ').title()} has been {status}.")
    
    @automod.command(name="violations")
    async def view_violations(self, ctx, member: discord.Member):
        """View detailed violation history for a user"""
        guild_id = ctx.guild.id
        user_id = member.id
        
        violations = self.user_violations[guild_id][user_id]
        
        if not violations:
            await ctx.send(f"{member.mention} has no recorded violations.")
            return
        
        embed = discord.Embed(
            title=f"📋 Violations for {member.display_name}",
            color=0xe74c3c
        )
        
        # Recent violations (last 10)
        recent_violations = violations[-10:]
        violation_text = ""
        
        for i, violation in enumerate(recent_violations, 1):
            timestamp = datetime.fromisoformat(violation["timestamp"]).strftime("%m/%d %H:%M")
            violation_text += f"`{i}.` **{violation['type']}** - {timestamp}\n"
            violation_text += f"   └ {violation['reason']}\n"
        
        embed.add_field(name="Recent Violations", value=violation_text, inline=False)
        embed.add_field(name="Total Warnings", value=self.user_warnings[guild_id][user_id], inline=True)
        embed.add_field(name="Total Violations", value=len(violations), inline=True)
        
        embed.set_footer(text=f"User ID: {member.id}")
        await ctx.send(embed=embed)
    
    @automod.command(name="reset")
    async def reset_warnings(self, ctx, member: discord.Member = None):
        """Reset warnings for a user or all users"""
        guild_id = ctx.guild.id
        
        if member:
            if member.id in self.user_warnings[guild_id]:
                old_count = self.user_warnings[guild_id][member.id]
                self.user_warnings[guild_id][member.id] = 0
                self.user_violations[guild_id][member.id] = []
                await ctx.send(f"✅ Reset {old_count} warnings for {member.mention}")
            else:
                await ctx.send(f"{member.mention} has no warnings to reset.")
        else:
            total_reset = sum(self.user_warnings[guild_id].values())
            self.user_warnings[guild_id].clear()
            self.user_violations[guild_id].clear()
            await ctx.send(f"✅ Reset all warnings ({total_reset} total warnings cleared)")
    
    @automod.command(name="unmute")
    async def unmute_user(self, ctx, member: discord.Member):
        """Manually unmute a user"""
        guild_id = ctx.guild.id
        
        if member.id in self.muted_users[guild_id]:
            self.muted_users[guild_id].remove(member.id)
            await ctx.send(f"✅ {member.mention} has been unmuted.")
        else:
            await ctx.send(f"{member.mention} is not currently muted by AutoMod.")

async def setup(bot):
    """Setup function to add the cog to the bot"""
    await bot.add_cog(AutoMod(bot))
