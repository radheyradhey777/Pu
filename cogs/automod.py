import discord
from discord.ext import commands
from discord import app_commands
import re
import json
import asyncio
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG_FILE = "automod_config.json"
WARNINGS_FILE = "user_warnings.json"

# Enhanced default configuration
default_config = {
    "enabled": True,
    "filters": {
        "discord_invite": {"enabled": False, "action": "warn"},
        "external_link": {"enabled": False, "action": "warn"},
        "spam_mention": {"enabled": False, "action": "warn", "threshold": 5},
        "excessive_caps": {"enabled": False, "action": "warn", "threshold": 10},
        "repeated_messages": {"enabled": False, "action": "warn", "threshold": 3},
        "profanity": {"enabled": False, "action": "warn"},
        "excessive_emojis": {"enabled": False, "action": "warn", "threshold": 10}
    },
    "ignored_channels": [],
    "ignored_roles": [],
    "ignored_users": [],
    "warning_threshold": 3,
    "punishment_actions": {
        "first": {"type": "timeout", "duration": 5},  # 5 minutes
        "second": {"type": "timeout", "duration": 30},  # 30 minutes
        "third": {"type": "timeout", "duration": 1440}  # 24 hours
    },
    "auto_delete_violations": True,
    "log_channel_id": None,
    "whitelist_channels": [],  # Channels where automod is less strict
    "profanity_words": ["example_bad_word"]
}

def load_config() -> Dict:
    """Load configuration from file or return default."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                # Merge with default to ensure all keys exist
                return merge_configs(default_config, config)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Error loading config: {e}")
            return default_config.copy()
    return default_config.copy()

def save_config(config: Dict) -> None:
    """Save configuration to file."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving config: {e}")

def load_warnings() -> Dict:
    """Load user warnings from file."""
    if os.path.exists(WARNINGS_FILE):
        try:
            with open(WARNINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Error loading warnings: {e}")
    return {}

def save_warnings(warnings: Dict) -> None:
    """Save user warnings to file."""
    try:
        with open(WARNINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(warnings, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving warnings: {e}")

def merge_configs(default: Dict, user: Dict) -> Dict:
    """Recursively merge user config with default config."""
    result = default.copy()
    for key, value in user.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_configs(result[key], value)
        else:
            result[key] = value
    return result

class AutoModView(discord.ui.View):
    """Interactive view for AutoMod configuration."""
    
    def __init__(self, config: Dict, cog_instance):
        super().__init__(timeout=300)  # 5 minute timeout
        self.config = config
        self.cog = cog_instance

    @discord.ui.button(label="Toggle AutoMod", style=discord.ButtonStyle.primary, emoji="🛡️")
    async def toggle_automod(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.config["enabled"] = not self.config["enabled"]
        save_config(self.config)
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.select(
        placeholder="Configure Filters",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label="Discord Invites", emoji="🔗", value="discord_invite"),
            discord.SelectOption(label="External Links", emoji="🌐", value="external_link"),
            discord.SelectOption(label="Mass Mentions", emoji="📢", value="spam_mention"),
            discord.SelectOption(label="Excessive Caps", emoji="🔠", value="excessive_caps"),
            discord.SelectOption(label="Spam Messages", emoji="📨", value="repeated_messages"),
            discord.SelectOption(label="Profanity Filter", emoji="🤬", value="profanity"),
            discord.SelectOption(label="Excessive Emojis", emoji="😀", value="excessive_emojis")
        ]
    )
    async def filter_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        filter_key = select.values[0]
        current_state = self.config["filters"][filter_key]["enabled"]
        self.config["filters"][filter_key]["enabled"] = not current_state
        save_config(self.config)
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="Reset Warnings", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def reset_warnings(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.cog.user_warnings = {}
        save_warnings({})
        embed = discord.Embed(
            title="✅ Warnings Reset",
            description="All user warnings have been cleared.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    def create_embed(self) -> discord.Embed:
        """Create status embed for AutoMod."""
        embed = discord.Embed(
            title="🛡️ AutoMod Control Panel",
            description=f"Status: {'🟢 Enabled' if self.config['enabled'] else '🔴 Disabled'}",
            color=discord.Color.green() if self.config["enabled"] else discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        
        # Filter status
        filter_status = []
        for filter_name, filter_config in self.config["filters"].items():
            status = "✅" if filter_config["enabled"] else "❌"
            name = filter_name.replace("_", " ").title()
            filter_status.append(f"{status} {name}")
        
        embed.add_field(
            name="🔍 Active Filters",
            value="\n".join(filter_status) if filter_status else "No filters enabled",
            inline=True
        )
        
        # Configuration info
        config_info = [
            f"Warning Threshold: {self.config['warning_threshold']}",
            f"Ignored Channels: {len(self.config['ignored_channels'])}",
            f"Ignored Roles: {len(self.config['ignored_roles'])}",
            f"Ignored Users: {len(self.config['ignored_users'])}"
        ]
        
        embed.add_field(
            name="⚙️ Configuration",
            value="\n".join(config_info),
            inline=True
        )
        
        # Active warnings count
        warning_count = len(self.cog.user_warnings)
        embed.add_field(
            name="📊 Statistics",
            value=f"Users with warnings: {warning_count}",
            inline=False
        )
        
        embed.set_footer(text="Use the buttons and dropdown to configure AutoMod")
        return embed

class AutoModCog(commands.Cog):
    """Enhanced AutoMod cog with comprehensive moderation features."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = load_config()
        self.user_warnings = load_warnings()
        self.message_history = {}  # For spam detection
        self.recent_messages = {}  # For repeated message detection
        
    async def cog_load(self):
        """Called when the cog is loaded."""
        logger.info("AutoMod cog loaded successfully")
        
    async def cog_unload(self):
        """Called when the cog is unloaded."""
        save_warnings(self.user_warnings)
        logger.info("AutoMod cog unloaded, warnings saved")

    def is_ignored(self, message: discord.Message) -> bool:
        """Check if message should be ignored by automod."""
        # Check if user is ignored
        if str(message.author.id) in self.config["ignored_users"]:
            return True
            
        # Check if channel is ignored
        if str(message.channel.id) in self.config["ignored_channels"]:
            return True
            
        # Check if user has ignored role
        if hasattr(message.author, 'roles'):
            for role in message.author.roles:
                if str(role.id) in self.config["ignored_roles"]:
                    return True
                    
        return False

    async def check_discord_invite(self, message: discord.Message) -> bool:
        """Check for Discord invite links."""
        invite_patterns = [
            r"discord\.gg/\w+",
            r"discordapp\.com/invite/\w+",
            r"discord\.com/invite/\w+"
        ]
        
        for pattern in invite_patterns:
            if re.search(pattern, message.content, re.IGNORECASE):
                return True
        return False

    async def check_external_links(self, message: discord.Message) -> bool:
        """Check for external links."""
        url_pattern = r"https?://(?:[-\w.])+(?:\:[0-9]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?)?)"
        return bool(re.search(url_pattern, message.content))

    async def check_spam_mentions(self, message: discord.Message) -> bool:
        """Check for excessive mentions."""
        threshold = self.config["filters"]["spam_mention"].get("threshold", 5)
        total_mentions = len(message.mentions) + len(message.role_mentions)
        return total_mentions >= threshold

    async def check_excessive_caps(self, message: discord.Message) -> bool:
        """Check for excessive caps."""
        if len(message.content) < 10:
            return False
            
        caps_ratio = sum(1 for c in message.content if c.isupper()) / len(message.content)
        return caps_ratio > 0.7  # 70% caps

    async def check_repeated_messages(self, message: discord.Message) -> bool:
        """Check for repeated/spam messages."""
        user_id = message.author.id
        content = message.content.lower().strip()
        
        if user_id not in self.recent_messages:
            self.recent_messages[user_id] = []
            
        # Clean old messages (older than 1 minute)
        current_time = datetime.utcnow()
        self.recent_messages[user_id] = [
            (msg_content, timestamp) for msg_content, timestamp in self.recent_messages[user_id]
            if (current_time - timestamp).seconds < 60
        ]
        
        # Check for repeated content
        recent_content = [msg_content for msg_content, _ in self.recent_messages[user_id]]
        threshold = self.config["filters"]["repeated_messages"].get("threshold", 3)
        
        if recent_content.count(content) >= threshold - 1:  # -1 because current message isn't added yet
            return True
            
        # Add current message
        self.recent_messages[user_id].append((content, current_time))
        return False

    async def check_profanity(self, message: discord.Message) -> bool:
        """Check for profanity."""
        profanity_words = self.config.get("profanity_words", [])
        content_lower = message.content.lower()
        
        for word in profanity_words:
            if word.lower() in content_lower:
                return True
        return False

    async def check_excessive_emojis(self, message: discord.Message) -> bool:
        """Check for excessive emojis."""
        threshold = self.config["filters"]["excessive_emojis"].get("threshold", 10)
        
        # Count Unicode emojis and custom emojis
        emoji_count = len(re.findall(r'<:[^:]+:[0-9]+>', message.content))  # Custom emojis
        emoji_count += len(re.findall(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]', message.content))  # Unicode emojis
        
        return emoji_count >= threshold

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Main message processing listener."""
        # Ignore bots and disabled automod
        if message.author.bot or not self.config["enabled"]:
            return
            
        # Check if message should be ignored
        if self.is_ignored(message):
            return

        violations = []
        
        # Check all enabled filters
        filter_checks = {
            "discord_invite": self.check_discord_invite,
            "external_link": self.check_external_links,
            "spam_mention": self.check_spam_mentions,
            "excessive_caps": self.check_excessive_caps,
            "repeated_messages": self.check_repeated_messages,
            "profanity": self.check_profanity,
            "excessive_emojis": self.check_excessive_emojis
        }
        
        for filter_name, check_func in filter_checks.items():
            if self.config["filters"][filter_name]["enabled"]:
                try:
                    if await check_func(message):
                        violations.append(filter_name.replace("_", " ").title())
                except Exception as e:
                    logger.error(f"Error in {filter_name} check: {e}")

        # Process violations
        if violations:
            if self.config["auto_delete_violations"]:
                try:
                    await message.delete()
                except discord.NotFound:
                    pass  # Message already deleted
                except discord.Forbidden:
                    logger.warning("Missing permissions to delete message")
                    
            await self.handle_violation(message.author, message.channel, violations)

    async def handle_violation(self, member: discord.Member, channel: discord.TextChannel, violations: List[str]):
        """Handle user violations and apply punishments."""
        user_id = str(member.id)
        
        # Update warning count
        if user_id not in self.user_warnings:
            self.user_warnings[user_id] = {"count": 0, "last_violation": None}
            
        self.user_warnings[user_id]["count"] += 1
        self.user_warnings[user_id]["last_violation"] = datetime.utcnow().isoformat()
        
        violation_text = ", ".join(violations)
        warning_count = self.user_warnings[user_id]["count"]
        
        # Send warning message
        warning_embed = discord.Embed(
            title="⚠️ AutoMod Warning",
            description=f"{member.mention} violated: **{violation_text}**",
            color=discord.Color.orange()
        )
        warning_embed.add_field(name="Warning Count", value=f"{warning_count}/{self.config['warning_threshold']}", inline=True)
        
        try:
            warning_msg = await channel.send(embed=warning_embed)
            # Auto-delete warning after 15 seconds
            await warning_msg.delete(delay=15)
        except discord.Forbidden:
            logger.warning("Missing permissions to send warning message")

        # Apply punishment if threshold reached
        if warning_count >= self.config["warning_threshold"]:
            await self.apply_punishment(member, channel, warning_count)
            
        # Save warnings
        save_warnings(self.user_warnings)
        
        # Log to designated channel if configured
        await self.log_violation(member, channel, violations, warning_count)

    async def apply_punishment(self, member: discord.Member, channel: discord.TextChannel, warning_count: int):
        """Apply punishment based on warning count."""
        punishment_actions = self.config["punishment_actions"]
        
        # Determine punishment level
        if warning_count == self.config["warning_threshold"]:
            action = punishment_actions.get("first", {"type": "timeout", "duration": 5})
        elif warning_count == self.config["warning_threshold"] + 1:
            action = punishment_actions.get("second", {"type": "timeout", "duration": 30})
        else:
            action = punishment_actions.get("third", {"type": "timeout", "duration": 1440})
        
        try:
            if action["type"] == "timeout":
                duration = timedelta(minutes=action["duration"])
                await member.timeout(discord.utils.utcnow() + duration, reason="AutoMod: Warning threshold exceeded")
                
                punishment_embed = discord.Embed(
                    title="🚫 User Timed Out",
                    description=f"{member.mention} has been timed out for {action['duration']} minutes due to repeated violations.",
                    color=discord.Color.red()
                )
                await channel.send(embed=punishment_embed)
                
                # Reset warning count after punishment
                self.user_warnings[str(member.id)]["count"] = 0
                
        except discord.Forbidden:
            error_embed = discord.Embed(
                title="❌ Punishment Failed",
                description="Missing permissions to apply punishment to this user.",
                color=discord.Color.red()
            )
            await channel.send(embed=error_embed)

    async def log_violation(self, member: discord.Member, channel: discord.TextChannel, violations: List[str], warning_count: int):
        """Log violation to designated log channel."""
        log_channel_id = self.config.get("log_channel_id")
        if not log_channel_id:
            return
            
        log_channel = self.bot.get_channel(log_channel_id)
        if not log_channel:
            return
            
        log_embed = discord.Embed(
            title="📋 AutoMod Log",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        log_embed.add_field(name="User", value=f"{member} ({member.id})", inline=True)
        log_embed.add_field(name="Channel", value=channel.mention, inline=True)
        log_embed.add_field(name="Violations", value=", ".join(violations), inline=True)
        log_embed.add_field(name="Warning Count", value=warning_count, inline=True)
        log_embed.set_thumbnail(url=member.display_avatar.url)
        
        try:
            await log_channel.send(embed=log_embed)
        except discord.Forbidden:
            logger.warning("Missing permissions to send to log channel")

    # Slash Commands
    @app_commands.command(name="automod", description="Configure AutoMod settings")
    @app_commands.describe(action="Action to perform")
    @app_commands.choices(action=[
        app_commands.Choice(name="Configure", value="config"),
        app_commands.Choice(name="Status", value="status"),
        app_commands.Choice(name="Reset Warnings", value="reset")
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def automod_command(self, interaction: discord.Interaction, action: str = "config"):
        """Main AutoMod command."""
        if action == "config":
            view = AutoModView(self.config, self)
            await interaction.response.send_message(embed=view.create_embed(), view=view, ephemeral=True)
        elif action == "status":
            embed = AutoModView(self.config, self).create_embed()
            await interaction.response.send_message(embed=embed, ephemeral=True)
        elif action == "reset":
            self.user_warnings = {}
            save_warnings({})
            embed = discord.Embed(
                title="✅ Warnings Reset",
                description="All user warnings have been cleared.",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="automod-ignore", description="Add/remove channels, roles, or users from AutoMod ignore list")
    @app_commands.describe(
        target_type="Type of target to ignore",
        target="The channel, role, or user to ignore",
        action="Add or remove from ignore list"
    )
    @app_commands.choices(
        target_type=[
            app_commands.Choice(name="Channel", value="channel"),
            app_commands.Choice(name="Role", value="role"),
            app_commands.Choice(name="User", value="user")
        ],
        action=[
            app_commands.Choice(name="Add", value="add"),
            app_commands.Choice(name="Remove", value="remove")
        ]
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def automod_ignore(self, interaction: discord.Interaction, target_type: str, target: Union[discord.TextChannel, discord.Role, discord.Member], action: str):
        """Manage AutoMod ignore lists."""
        target_id = str(target.id)
        ignore_key = f"ignored_{target_type}s"
        
        if action == "add":
            if target_id not in self.config[ignore_key]:
                self.config[ignore_key].append(target_id)
                save_config(self.config)
                embed = discord.Embed(
                    title="✅ Added to Ignore List",
                    description=f"{target.mention} has been added to the AutoMod ignore list.",
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title="ℹ️ Already Ignored",
                    description=f"{target.mention} is already in the AutoMod ignore list.",
                    color=discord.Color.blue()
                )
        else:  # remove
            if target_id in self.config[ignore_key]:
                self.config[ignore_key].remove(target_id)
                save_config(self.config)
                embed = discord.Embed(
                    title="✅ Removed from Ignore List",
                    description=f"{target.mention} has been removed from the AutoMod ignore list.",
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title="ℹ️ Not in Ignore List",
                    description=f"{target.mention} is not in the AutoMod ignore list.",
                    color=discord.Color.blue()
                )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="warnings", description="Check warnings for a user")
    @app_commands.describe(user="User to check warnings for")
    async def check_warnings(self, interaction: discord.Interaction, user: discord.Member = None):
        """Check warning count for a user."""
        target_user = user or interaction.user
        user_id = str(target_user.id)
        
        if user_id in self.user_warnings:
            warning_data = self.user_warnings[user_id]
            warning_count = warning_data["count"]
            last_violation = warning_data.get("last_violation")
            
            embed = discord.Embed(
                title="⚠️ Warning Information",
                color=discord.Color.orange()
            )
            embed.add_field(name="User", value=target_user.mention, inline=True)
            embed.add_field(name="Warning Count", value=f"{warning_count}/{self.config['warning_threshold']}", inline=True)
            
            if last_violation:
                try:
                    last_date = datetime.fromisoformat(last_violation)
                    embed.add_field(name="Last Violation", value=last_date.strftime("%Y-%m-%d %H:%M UTC"), inline=True)
                except ValueError:
                    pass
                    
            embed.set_thumbnail(url=target_user.display_avatar.url)
        else:
            embed = discord.Embed(
                title="✅ Clean Record",
                description=f"{target_user.mention} has no warnings.",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=target_user.display_avatar.url)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # Error handling
    @automod_command.error
    @automod_ignore.error
    async def automod_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle AutoMod command errors."""
        if isinstance(error, app_commands.MissingPermissions):
            embed = discord.Embed(
                title="❌ Missing Permissions",
                description="You need Administrator permissions to use this command.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            logger.error(f"AutoMod command error: {error}")
            embed = discord.Embed(
                title="❌ Command Error",
                description="An error occurred while processing your command.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    """Setup function for the cog."""
    await bot.add_cog(AutoModCog(bot))
