import discord
from discord.ext import commands
from discord import app_commands
import json
import re
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict, deque
import time
import os

# Default configuration
default_config = {
    "enabled": True,
    "discord_invite": False,
    "link": False,
    "spam_mention": False,
    "spam_emoji": False,
    "sticker": False,
    "ban_words": False,
    "wall_text": False,
    "caps": False,
    "spoiler": False,
    "ignored_channels": [],
    "ignored_roles": [],
    "ignored_users": [],
    "warning_threshold": 5,
    "punishment_timeout": 5,
    "ban_word_list": ["badword1", "badword2"],
    "spam_message_count": 5,
    "spam_time_window": 10,
    "max_mentions": 5,
    "max_emojis": 10,
    "wall_text_limit": 500,
    "caps_percentage": 70,
    "log_channel": None,
    "auto_delete_violations": True,
    "warning_message_duration": 10
}

class AutoModView(discord.ui.View):
    def __init__(self, config, cog):
        super().__init__(timeout=300)
        self.config = config
        self.cog = cog

    @discord.ui.select(
        placeholder="Toggle AutoMod Filters",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(
                label="Discord Invite Filter",
                description="Block Discord server invites",
                emoji="🚫"
            ),
            discord.SelectOption(
                label="Link Filter",
                description="Block external links",
                emoji="🔗"
            ),
            discord.SelectOption(
                label="Spam Mention Filter",
                description="Block excessive mentions",
                emoji="📢"
            ),
            discord.SelectOption(
                label="Spam Emoji Filter",
                description="Block emoji spam",
                emoji="😀"
            ),
            discord.SelectOption(
                label="Sticker Filter",
                description="Block sticker messages",
                emoji="🎭"
            ),
            discord.SelectOption(
                label="Ban Words Filter",
                description="Block custom banned words",
                emoji="🔤"
            ),
            discord.SelectOption(
                label="Wall Text Filter",
                description="Block overly long messages",
                emoji="📜"
            ),
            discord.SelectOption(
                label="Capital Letters Filter",
                description="Block excessive caps",
                emoji="🔠"
            ),
            discord.SelectOption(
                label="Spoiler Filter",
                description="Block spoiler abuse",
                emoji="👁️"
            ),
        ]
    )
    async def filter_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        key_mapping = {
            "Discord Invite Filter": "discord_invite",
            "Link Filter": "link",
            "Spam Mention Filter": "spam_mention",
            "Spam Emoji Filter": "spam_emoji",
            "Sticker Filter": "sticker",
            "Ban Words Filter": "ban_words",
            "Wall Text Filter": "wall_text",
            "Capital Letters Filter": "caps",
            "Spoiler Filter": "spoiler"
        }

        key = key_mapping[select.values[0]]

        # Toggle selected filter
        self.config[key] = not self.config.get(key, False)
        self.cog.save_config()

        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Toggle AutoMod", style=discord.ButtonStyle.primary, emoji="🔄")
    async def toggle_automod(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.config["enabled"] = not self.config["enabled"]
        self.cog.save_config()

        embed = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Settings", style=discord.ButtonStyle.secondary, emoji="⚙️")
    async def open_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = SettingsModal(self.config, self.cog)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Reset Warnings", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def reset_warnings(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.cog.user_warnings.clear()

        embed = discord.Embed(
            title="✅ Warnings Reset",
            description="All user warnings have been cleared.",
            color=discord.Color.green()
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    def get_embed(self):
        cfg = self.config
        embed = discord.Embed(
            title="🛡️ AutoMod Configuration",
            description="Configure your server's automatic moderation",
            color=discord.Color.green() if cfg["enabled"] else discord.Color.red()
        )

        # Status field
        status_emoji = "🟢" if cfg["enabled"] else "🔴"
        embed.add_field(
            name=f"{status_emoji} AutoMod Status",
            value="**Enabled**" if cfg["enabled"] else "**Disabled**",
            inline=False
        )

        # Filter status
        filters = [
            ("🚫 Discord Invites", cfg["discord_invite"]),
            ("🔗 Links", cfg["link"]),
            ("📢 Spam Mentions", cfg["spam_mention"]),
            ("😀 Spam Emojis", cfg["spam_emoji"]),
            ("🎭 Stickers", cfg["sticker"]),
            ("🔤 Banned Words", cfg["ban_words"]),
            ("📜 Wall Text", cfg["wall_text"]),
            ("🔠 Caps Filter", cfg["caps"]),
            ("👁️ Spoilers", cfg["spoiler"])
        ]

        for name, status in filters:
            embed.add_field(
                name=name,
                value="🟢 On" if status else "🔴 Off",
                inline=True
            )

        # Settings info
        embed.add_field(
            name="⚙️ Current Settings",
            value=f"**Warning Threshold:** {cfg['warning_threshold']}\n"
                  f"**Timeout Duration:** {cfg['punishment_timeout']} min\n"
                  f"**Active Warnings:** {len(self.cog.user_warnings)}",
            inline=False
        )

        embed.set_footer(text="Use the dropdown to toggle filters • Click Settings for advanced options")
        return embed

class SettingsModal(discord.ui.Modal, title="AutoMod Settings"):
    def __init__(self, config, cog):
        super().__init__()
        self.config = config
        self.cog = cog

    warning_threshold = discord.ui.TextInput(
        label='Warning Threshold',
        placeholder='Number of warnings before timeout...',
        default=str(default_config['warning_threshold']),
        max_length=2
    )

    timeout_duration = discord.ui.TextInput(
        label='Timeout Duration (minutes)',
        placeholder='Duration for timeout punishment...',
        default=str(default_config['punishment_timeout']),
        max_length=3
    )

    banned_words = discord.ui.TextInput(
        label='Banned Words (comma separated)',
        placeholder='word1, word2, word3...',
        style=discord.TextStyle.paragraph,
        required=False,
        default=", ".join(default_config['ban_word_list']),
        max_length=1000
    )

    spam_limits = discord.ui.TextInput(
        label='Spam Limits (mentions,emojis,messages)',
        placeholder='5,10,5 (max mentions, max emojis, max messages)',
        default=f"{default_config['max_mentions']},{default_config['max_emojis']},{default_config['spam_message_count']}",
        max_length=20
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Update warning threshold
            self.config['warning_threshold'] = int(self.warning_threshold.value)

            # Update timeout duration
            self.config['punishment_timeout'] = int(self.timeout_duration.value)

            # Update banned words
            if self.banned_words.value.strip():
                words = [word.strip() for word in self.banned_words.value.split(',') if word.strip()]
                self.config['ban_word_list'] = words
            else:
                self.config['ban_word_list'] = [] # Allow clearing banned words

            # Update spam limits
            limits = self.spam_limits.value.split(',')
            if len(limits) == 3:
                self.config['max_mentions'] = int(limits[0].strip())
                self.config['max_emojis'] = int(limits[1].strip())
                self.config['spam_message_count'] = int(limits[2].strip())
            else:
                raise ValueError("Invalid spam limits format.")

            self.cog.save_config()

            embed = discord.Embed(
                title="✅ Settings Updated",
                description="AutoMod settings have been successfully updated!",
                color=discord.Color.green()
            )

        except ValueError:
            embed = discord.Embed(
                title="❌ Invalid Input",
                description="Please ensure all numerical inputs are valid numbers and spam limits are in the format `mentions,emojis,messages`.",
                color=discord.Color.red()
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

class AutoMod(commands.Cog):
    """Advanced automatic moderation system for Discord servers."""

    def __init__(self, bot):
        self.bot = bot
        self.config_file = "data/automod/config.json"
        self.config = self.load_config()

        # In-memory storage
        self.user_warnings = defaultdict(int)
        self.user_messages = defaultdict(lambda: deque(maxlen=self.config.get("spam_message_count", 5) + 5)) # Add a buffer to maxlen
        self.user_timeouts = {} # Stores {user_id: datetime_when_timeout_ends}

        # Ensure data directory exists
        os.makedirs("data/automod", exist_ok=True)

    def load_config(self):
        """Load configuration from file."""
        try:
            with open(self.config_file, "r") as f:
                config = json.load(f)
                # Ensure all default keys exist and merge with loaded config
                merged_config = default_config.copy()
                merged_config.update(config)
                return merged_config
        except FileNotFoundError:
            return default_config.copy()

    def save_config(self):
        """Save configuration to file."""
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, "w") as f:
            json.dump(self.config, f, indent=4)

    # Slash Commands
    automod_group = app_commands.Group(name="automod", description="AutoMod management commands")

    @automod_group.command(name="config", description="Configure AutoMod settings")
    async def automod_config(self, interaction: discord.Interaction):
        """Open the AutoMod configuration panel."""
        if not interaction.user.guild_permissions.manage_messages:
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You need the `Manage Messages` permission to use this command.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        view = AutoModView(self.config, self)
        embed = view.get_embed()
        await interaction.response.send_message(embed=embed, view=view)

    @automod_group.command(name="warnings", description="View user warnings")
    @app_commands.describe(user="View warnings for a specific user")
    async def view_warnings(self(self, interaction: discord.Interaction, user: discord.Member = None):
        """View warnings for all users or a specific user."""
        if not interaction.user.guild_permissions.manage_messages:
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You need the `Manage Messages` permission to use this command.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = discord.Embed(title="⚠️ User Warnings", color=discord.Color.orange())

        if user:
            # Show warnings for specific user
            warnings = self.user_warnings.get(user.id, 0)
            embed.description = f"**{user.display_name}** has {warnings} warning(s)"
            embed.set_thumbnail(url=user.display_avatar.url)
        else:
            # Show all warnings
            if not self.user_warnings:
                embed.description = "No users currently have warnings."
            else:
                warning_list = []
                # Sort by warning count, descending
                sorted_warnings = sorted(self.user_warnings.items(), key=lambda x: x[1], reverse=True)
                for user_id, count in sorted_warnings:
                    try:
                        # Attempt to get user object from cache first, then fetch
                        discord_user = interaction.guild.get_member(user_id) or await self.bot.fetch_user(user_id)
                        warning_list.append(f"**{discord_user.display_name}** ({discord_user.mention}): {count} warning(s)")
                    except discord.NotFound:
                        warning_list.append(f"**Unknown User** (ID: {user_id}): {count} warning(s)")
                    except Exception: # Catch other potential errors during user fetching
                        warning_list.append(f"**Unknown User** (ID: {user_id}): {count} warning(s)")


                embed.description = "\n".join(warning_list[:15])
                if len(self.user_warnings) > 15:
                    embed.set_footer(text=f"Showing top 15 of {len(self.user_warnings)} users")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @automod_group.command(name="clear", description="Clear warnings for a user")
    @app_commands.describe(user="User to clear warnings for")
    async def clear_warnings(self, interaction: discord.Interaction, user: discord.Member):
        """Clear all warnings for a specific user."""
        if not interaction.user.guild_permissions.manage_messages:
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You need the `Manage Messages` permission to use this command.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if user.id in self.user_warnings:
            old_warnings = self.user_warnings[user.id]
            del self.user_warnings[user.id]
            embed = discord.Embed(
                title="✅ Warnings Cleared",
                description=f"Cleared {old_warnings} warning(s) for {user.mention}",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="ℹ️ No Warnings",
                description=f"{user.mention} has no warnings to clear.",
                color=discord.Color.blue()
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @automod_group.command(name="ignore", description="Add/remove channels, roles, or users from AutoMod")
    @app_commands.describe(
        action="Add or remove from ignore list",
        target_type="What to ignore",
        target="The channel, role, or user to ignore (mention or ID)"
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Add", value="add"),
            app_commands.Choice(name="Remove", value="remove"),
            app_commands.Choice(name="List", value="list")
        ],
        target_type=[
            app_commands.Choice(name="Channel", value="channel"),
            app_commands.Choice(name="Role", value="role"),
            app_commands.Choice(name="User", value="user")
        ]
    )
    async def ignore_management(
        self,
        interaction: discord.Interaction,
        action: str,
        target_type: str = None,
        target: str = None
    ):
        """Manage AutoMod ignore lists."""
        if not interaction.user.guild_permissions.manage_guild:
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You need the `Manage Server` permission to use this command.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if action == "list":
            embed = discord.Embed(title="🔕 AutoMod Ignore Lists", color=discord.Color.blue())

            # Channels
            ignored_channels = []
            for channel_id in self.config.get("ignored_channels", []):
                channel = self.bot.get_channel(channel_id)
                if channel:
                    ignored_channels.append(channel.mention)
                else:
                    ignored_channels.append(f"<#{channel_id}> (Deleted Channel)") # Show if channel is gone

            embed.add_field(
                name="📝 Ignored Channels",
                value="\n".join(ignored_channels) if ignored_channels else "None",
                inline=False
            )

            # Roles
            ignored_roles = []
            for role_id in self.config.get("ignored_roles", []):
                role = interaction.guild.get_role(role_id)
                if role:
                    ignored_roles.append(role.mention)
                else:
                    ignored_roles.append(f"<@&{role_id}> (Deleted Role)") # Show if role is gone

            embed.add_field(
                name="👥 Ignored Roles",
                value="\n".join(ignored_roles) if ignored_roles else "None",
                inline=False
            )

            # Users
            ignored_users = []
            for user_id in self.config.get("ignored_users", []):
                user = self.bot.get_user(user_id)
                if user:
                    ignored_users.append(user.mention)
                else:
                    ignored_users.append(f"<@{user_id}> (Left Server/Unknown User)") # Show if user is gone

            embed.add_field(
                name="👤 Ignored Users",
                value="\n".join(ignored_users) if ignored_users else "None",
                inline=False
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # For add/remove actions, we need target_type and target
        if not target_type or not target:
            embed = discord.Embed(
                title="❌ Missing Information",
                description="Please specify both target type and target for add/remove actions.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Parse the target based on type
        target_id = None
        target_name = ""

        try:
            # Attempt to parse target as an ID
            if target.isdigit():
                target_id = int(target)
            else:
                # Attempt to parse target as a mention
                match = re.match(r'<[#@&!]+(\d+)>', target)
                if match:
                    target_id = int(match.group(1))

            if target_id is None:
                raise ValueError("Invalid target format. Please use a mention or ID.")

            if target_type == "channel":
                channel = self.bot.get_channel(target_id)
                if channel:
                    target_name = channel.name
                else:
                    raise ValueError("Channel not found.")
            elif target_type == "role":
                role = interaction.guild.get_role(target_id)
                if role:
                    target_name = role.name
                else:
                    raise ValueError("Role not found.")
            elif target_type == "user":
                user = self.bot.get_user(target_id) or await self.bot.fetch_user(target_id)
                if user:
                    target_name = user.display_name
                else:
                    raise ValueError("User not found.")

        except (ValueError, discord.NotFound):
            embed = discord.Embed(
                title="❌ Invalid Target",
                description="Could not find the specified channel, role, or user. Please provide a valid mention or ID.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Perform add/remove action
        ignore_key = f"ignored_{target_type}s"
        ignore_list = self.config.get(ignore_key, [])

        if action == "add":
            if target_id not in ignore_list:
                ignore_list.append(target_id)
                self.config[ignore_key] = ignore_list
                self.save_config()

                embed = discord.Embed(
                    title="✅ Added to Ignore List",
                    description=f"Added **{target_name}** to ignored {target_type}s.",
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title="ℹ️ Already Ignored",
                    description=f"**{target_name}** is already in the ignore list.",
                    color=discord.Color.blue()
                )

        elif action == "remove":
            if target_id in ignore_list:
                ignore_list.remove(target_id)
                self.config[ignore_key] = ignore_list
                self.save_config()

                embed = discord.Embed(
                    title="✅ Removed from Ignore List",
                    description=f"Removed **{target_name}** from ignored {target_type}s.",
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title="ℹ️ Not in List",
                    description=f"**{target_name}** is not in the ignore list.",
                    color=discord.Color.blue()
                )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @automod_group.command(name="logchannel", description="Set the log channel for AutoMod")
    @app_commands.describe(channel="Channel to send AutoMod logs to (leave empty to disable)")
    async def set_log_channel(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        """Set or disable the AutoMod log channel."""
        if not interaction.user.guild_permissions.manage_guild:
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You need the `Manage Server` permission to use this command.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        if channel:
            self.config["log_channel"] = channel.id
            self.save_config()

            embed = discord.Embed(
                title="✅ Log Channel Set",
                description=f"AutoMod logs will now be sent to {channel.mention}",
                color=discord.Color.green()
            )
        else:
            self.config["log_channel"] = None
            self.save_config()

            embed = discord.Embed(
                title="✅ Log Channel Disabled",
                description="AutoMod logging has been disabled.",
                color=discord.Color.green()
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # Event Listeners
    @commands.Cog.listener()
    async def on_message(self, message):
        """Main message processing for AutoMod."""
        # Skip if conditions not met
        if (message.author.bot or
            not message.guild or
            not self.config.get("enabled", True) or
            message.author.guild_permissions.manage_messages): # Bots and users with manage messages permission are ignored
            return

        # Check if the user is currently in timeout by AutoMod
        if message.author.id in self.user_timeouts:
            timeout_end_time = self.user_timeouts[message.author.id]
            if datetime.utcnow() < timeout_end_time:
                # If user is still in timeout, delete their message without warning
                try:
                    await message.delete()
                    return # Stop processing further
                except discord.NotFound:
                    pass # Message might have already been deleted
            else:
                # Timeout has expired, remove from user_timeouts
                del self.user_timeouts[message.author.id]


        # Check ignore lists
        if (message.channel.id in self.config.get("ignored_channels", []) or
            any(role.id in self.config.get("ignored_roles", []) for role in message.author.roles) or
            message.author.id in self.config.get("ignored_users", [])):
            return

        # Check for violations
        violations = await self.check_message_violations(message)

        if violations:
            await self.handle_violation(message, violations)

    async def check_message_violations(self, message):
        """Check message for various rule violations."""
        violations = []
        content = message.content.lower() # Convert to lowercase for case-insensitive checks where appropriate

        # Check each filter type
        if self.config.get("discord_invite") and self.check_discord_invite(content):
            violations.append("Discord invite link")

        if self.config.get("link") and self.check_link(content):
            violations.append("External link")

        if self.config.get("spam_mention") and self.check_spam_mentions(message):
            violations.append("Spam mentions")

        if self.config.get("spam_emoji") and self.check_spam_emojis(message.content): # Original content for emoji check
            violations.append("Spam emojis")

        if self.config.get("sticker") and message.stickers:
            violations.append("Sticker usage")

        if self.config.get("ban_words") and self.check_banned_words(content):
            violations.append("Banned words")

        if self.config.get("wall_text") and self.check_wall_text(message.content): # Original content for length check
            violations.append("Wall text")

        if self.config.get("caps") and self.check_caps(message.content): # Original content for caps check
            violations.append("Excessive capitals")

        if self.config.get("spoiler") and self.check_spoiler(message.content): # Original content for spoiler check
            violations.append("Spoiler abuse")

        # Check message spam (always check this, regardless of other filters)
        if self.check_message_spam(message):
            # Only add if not already marked as spam by other means, or if it's a distinct "message spam" type
            if "Message spam" not in violations:
                violations.append("Message spam")

        return violations

    # Violation Check Methods
    def check_discord_invite(self, content):
        """Check for Discord invite links."""
        # This pattern also catches variations like "discord.gg/invitecode"
        pattern = r'(discord\.gg/|discordapp\.com/invite/|discord\.com/invite/)([a-zA-Z0-9]+)'
        return bool(re.search(pattern, content))

    def check_link(self, content):
        """Check for external links."""
        # More robust link detection, excluding common Discord-internal links
        # This will still catch discord.gg, but that's fine if the invite filter is also on
        # Excludes attachments.discordapp.com
        pattern = r'https?://(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,6}(?:/[^\s]*)?'
        # Refine to exclude known Discord domains if the intent is only *external* links
        discord_domains = ['discord.com', 'discordapp.com', 'discord.gg', 'cdn.discordapp.com']
        found_links = re.findall(pattern, content)
        for link in found_links:
            # Check if the domain of the link is NOT in our discord_domains list
            try:
                domain = re.search(r'https?://([^/]+)/', link).group(1)
                if not any(d in domain for d in discord_domains):
                    return True
            except AttributeError:
                continue # Malformed link, skip
        return False

    def check_spam_mentions(self, message):
        """Check for spam mentions."""
        # This counts actual user mentions, not just roles or everyone/here
        return len(message.mentions) > self.config.get("max_mentions", 5)

    def check_spam_emojis(self, content):
        """Check for spam emojis."""
        # Custom emojis and Unicode emojis.
        # This pattern is good, just ensure it's applied to original message.content
        emoji_pattern = r'<a?:\w+:\d+>|[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U0001F251]'
        emojis = re.findall(emoji_pattern, content)
        return len(emojis) > self.config.get("max_emojis", 10)

    def check_banned_words(self, content):
        """Check for banned words."""
        banned_words = self.config.get("ban_word_list", [])
        if not banned_words: # No banned words configured
            return False
        content_lower = content.lower()
        # Use word boundaries (\b) to match whole words only
        return any(re.search(r'\b' + re.escape(word.lower()) + r'\b', content_lower) for word in banned_words if word)

    def check_wall_text(self, content):
        """Check for wall text (overly long messages)."""
        # Consider character count after removing whitespace for a more accurate check, or just raw length
        return len(content) > self.config.get("wall_text_limit", 500)

    def check_caps(self, content):
        """Check for excessive capital letters."""
        # Ignore messages that are too short to meaningfully check for caps
        if len(content) < 15: # Increased minimum length
            return False

        caps_count = sum(1 for c in content if c.isupper())
        total_letters = sum(1 for c in content if c.isalpha())

        if total_letters == 0: # Avoid division by zero
            return False

        caps_percentage = (caps_count / total_letters) * 100
        return caps_percentage > self.config.get("caps_percentage", 70)

    def check_spoiler(self, content):
        """Check for spoiler abuse."""
        # Check for multiple || || blocks, not just total count of ||
        # A simple check for unmatched or excessive pairs might be better
        spoiler_matches = re.findall(r'\|\|.*?\|\|', content)
        # Assuming "spoiler abuse" means many separate spoiler tags or very long spoiler content
        # For simplicity, let's keep the existing logic but clarify its intent:
        # It's checking total occurrences of '||', not valid spoiler blocks.
        spoiler_count = content.count('||')
        return spoiler_count > self.config.get("spoiler_character_limit", 20) # Made this configurable for clarity


    def check_message_spam(self, message):
        """Check for message spam."""
        user_id = message.author.id
        current_time = time.time()

        # Add current message to user's history
        self.user_messages[user_id].append(current_time)

        # Count recent messages within the time window
        time_window = self.config.get("spam_time_window", 10)
        spam_message_count = self.config.get("spam_message_count", 5)

        # Filter messages that are within the time window
        # The deque.maxlen will handle older messages automatically, but this ensures we only count recent ones.
        recent_messages_count = 0
        for msg_time in reversed(self.user_messages[user_id]): # Check from most recent
            if current_time - msg_time <= time_window:
                recent_messages_count += 1
            else:
                break # Messages are ordered, so if one is too old, all subsequent are too.

        return recent_messages_count >= spam_message_count


    async def handle_violation(self, message, violations):
        """Handle detected violations."""
        try:
            # Delete the message if enabled
            if self.config.get("auto_delete_violations", True):
                try:
                    await message.delete()
                except discord.NotFound:
                    pass # Message already deleted by another bot/user or self

            # Add warning
            self.user_warnings[message.author.id] += 1
            current_warnings = self.user_warnings[message.author.id]

            # Create violation embed
            embed = discord.Embed(
                title="🚨 AutoMod Violation Detected",
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )

            embed.add_field(name="👤 User", value=message.author.mention, inline=True)
            embed.add_field(name="📍 Channel", value=message.channel.mention, inline=True)
            embed.add_field(name="⚠️ Warnings", value=f"{current_warnings}/{self.config['warning_threshold']}", inline=True)

            violation_text = "\n".join(f"• {violation}" for violation in violations)
            embed.add_field(name="🔍 Violations", value=violation_text, inline=False)
            embed.add_field(name="Original Message", value=f"```\n{message.content[:1000]}\n```" if message.content else "*(No text content)*", inline=False)


            # Send warning message
            try:
                warning_msg = await message.channel.send(embed=embed)

                # Auto-delete warning message
                warning_duration = self.config.get("warning_message_duration", 10)
                if warning_duration > 0:
                    await asyncio.sleep(warning_duration)
                    try:
                        await warning_msg.delete()
                    except discord.NotFound:
                        pass # Warning message already deleted
            except discord.Forbidden:
                # Bot doesn't have permissions to send messages in that channel
                print(f"AutoMod: Missing permissions to send warning message in {message.channel.name}")
                pass


            # Log to log channel if configured
            await self.log_violation(message, violations, current_warnings)

            # Check for punishment
            if current_warnings >= self.config.get("warning_threshold", 5):
                await self.apply_punishment(message.author, message.guild)
                self.user_warnings[message.author.id] = 0  # Reset after punishment
                # Also clear their message history to prevent immediate re-trigger
                if message.author.id in self.user_messages:
                    self.user_messages[message.author.id].clear()

        except discord.errors.NotFound:
            pass # Message or channel not found, likely already deleted or inaccessible
        except Exception as e:
            print(f"AutoMod Error in handle_violation: {e}")

    async def log_violation(self, message, violations, warning_count):
        """Log violation to designated channel."""
        log_channel_id = self.config.get("log_channel")
        if not log_channel_id:
            return # No log channel configured

        log_channel = self.bot.get_channel(log_channel_id)
        if not log_channel:
            print(f"AutoMod: Configured log channel (ID: {log_channel_id}) not found.")
            return

        log_embed = discord.Embed(
            title="📝 AutoMod Log Entry",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )

        log_embed.add_field(name="👤 User", value=f"{message.author.display_name} ({message.author.mention})", inline=True)
        log_embed.add_field(name="📍 Channel", value=message.channel.mention, inline=True)
        log_embed.add_field(name="Guild", value=message.guild.name, inline=True)
        log_embed.add_field(name="⚠️ Warnings (User)", value=f"{warning_count}/{self.config['warning_threshold']}", inline=True)

        violation_text = "\n".join(f"• {v}" for v in violations)
        log_embed.add_field(name="🔍 Violations", value=violation_text, inline=False)

        # Truncate message content for logging if too long
        original_content = message.content
        if len(original_content) > 1000:
            original_content = original_content[:997] + "..."
        log_embed.add_field(name="Message Content", value=f"```\n{original_content if original_content else '*No text content*'}```", inline=False)

        log_embed.set_footer(text=f"User ID: {message.author.id} | Message ID: {message.id}")

        try:
            await log_channel.send(embed=log_embed)
        except discord.Forbidden:
            print(f"AutoMod: Missing permissions to send logs to {log_channel.name}.")
        except Exception as e:
            print(f"AutoMod Error sending log: {e}")

    async def apply_punishment(self, member: discord.Member, guild: discord.Guild):
        """Apply punishment (timeout) to the user."""
        timeout_minutes = self.config.get("punishment_timeout", 5)
        punishment_duration = timedelta(minutes=timeout_minutes)

        try:
            # Check if the bot has permissions to timeout the member
            if not guild.me.guild_permissions.moderate_members:
                print(f"AutoMod: Missing 'Moderate Members' permission to timeout {member.display_name} in {guild.name}.")
                # Log this to the log channel if possible
                log_channel_id = self.config.get("log_channel")
                if log_channel_id:
                    log_channel = self.bot.get_channel(log_channel_id)
                    if log_channel:
                        await log_channel.send(embed=discord.Embed(
                            title="⚠️ AutoMod Permission Error",
                            description=f"Could not timeout {member.mention}. Bot is missing `Moderate Members` permission.",
                            color=discord.Color.orange()
                        ))
                return

            # Check if the bot can timeout this specific member (hierarchy check)
            if member.top_role >= guild.me.top_role and member.id != guild.owner_id:
                print(f"AutoMod: Cannot timeout {member.display_name} due to role hierarchy.")
                # Log this to the log channel if possible
                log_channel_id = self.config.get("log_channel")
                if log_channel_id:
                    log_channel = self.bot.get_channel(log_channel_id)
                    if log_channel:
                        await log_channel.send(embed=discord.Embed(
                            title="⚠️ AutoMod Hierarchy Warning",
                            description=f"Could not timeout {member.mention}. Their highest role is equal to or higher than the bot's.",
                            color=discord.Color.orange()
                        ))
                return

            await member.timeout(punishment_duration, reason=f"AutoMod violation: Excessive warnings ({self.config['warning_threshold']})")
            timeout_end_time = datetime.utcnow() + punishment_duration
            self.user_timeouts[member.id] = timeout_end_time # Store timeout end time

            punishment_embed = discord.Embed(
                title="🚫 User Timed Out",
                description=f"{member.mention} has been timed out for {timeout_minutes} minute(s) due to excessive AutoMod violations.",
                color=discord.Color.dark_red(),
                timestamp=datetime.utcnow()
            )
            punishment_embed.add_field(name="Reason", value="Repeated AutoMod violations", inline=False)
            punishment_embed.set_footer(text="Warnings have been reset for this user.")

            # Send timeout message to the channel where the last violation occurred, or log channel
            try:
                if self.config.get("log_channel"):
                    log_channel_obj = self.bot.get_channel(self.config["log_channel"])
                    if log_channel_obj:
                        await log_channel_obj.send(embed=punishment_embed)
                # Optionally send to the user's last message channel if it's not a log channel, or direct message if possible
                # For simplicity, we'll stick to log channel for now or print.
            except discord.Forbidden:
                print(f"AutoMod: Could not send timeout message to log channel.")
            except Exception as e:
                print(f"AutoMod Error sending punishment message: {e}")

        except discord.Forbidden:
            print(f"AutoMod: Bot lacks permissions to timeout {member.display_name} in {guild.name}.")
        except Exception as e:
            print(f"AutoMod Error applying punishment: {e}")

async def setup(bot):
    await bot.add_cog(AutoMod(bot))
