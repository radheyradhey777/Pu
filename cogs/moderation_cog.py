import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
from typing import Optional, Union
import json
import logging
import asyncio
import re

# --- Setup professional logging ---
log = logging.getLogger('discord.moderation_cog')

class Moderation(commands.Cog):
    """
    A professional Discord.py cog for moderation commands.
    This version uses a JSON file for persistent warning storage,
    logs all moderation actions, and uses granular permissions.
    Enhanced with additional features like slowmode, purge, lockdown, etc.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.warnings_file = "warnings.json"
        self.warnings_cache = self._load_warnings()
        self.locked_channels = set()  # In-memory track of locked channels

    # --- Data Persistence for Warnings ---

    def _load_warnings(self) -> dict:
        """Loads the warnings dictionary from warnings.json."""
        try:
            with open(self.warnings_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            log.info("warnings.json not found or is invalid. Starting with an empty cache.")
            return {}

    def _save_warnings(self):
        """Saves the warnings cache to warnings.json."""
        try:
            with open(self.warnings_file, 'w', encoding='utf-8') as f:
                json.dump(self.warnings_cache, f, indent=4)
        except IOError as e:
            log.error(f"Failed to save warnings to {self.warnings_file}: {e}")

    def _get_warnings_key(self, guild_id: int, member_id: int) -> str:
        """Generates a consistent string key for JSON compatibility."""
        return f"{guild_id}-{member_id}"

    # --- Helper Methods ---

    async def check_hierarchy(self, interaction: discord.Interaction, target: discord.Member) -> bool:
        """Checks if the command user can moderate the target member."""
        if target.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            await interaction.response.send_message("❌ You cannot moderate someone with an equal or higher role.", ephemeral=True)
            return False
        if target == interaction.guild.owner:
            await interaction.response.send_message("❌ You cannot moderate the server owner.", ephemeral=True)
            return False
        if target.bot:
            await interaction.response.send_message("❌ You cannot moderate other bots.", ephemeral=True)
            return False
        return True

    def parse_duration(self, duration_str: str) -> Optional[timedelta]:
        """Parses a duration string (e.g., '10m', '5h', '3d') into a timedelta."""
        if not duration_str:
            return None
        unit = duration_str[-1].lower()
        try:
            value = int(duration_str[:-1])
            if unit == 's':
                return timedelta(seconds=value)
            elif unit == 'm':
                return timedelta(minutes=value)
            elif unit == 'h':
                return timedelta(hours=value)
            elif unit == 'd':
                return timedelta(days=value)
            else:
                return None
        except ValueError:
            return None

    async def send_dm_notification(self, member: discord.Member, action: str, reason: str, guild_name: str, duration: str = None):
        """Send DM notification to member about moderation action."""
        try:
            embed = discord.Embed(
                title=f"You were {action} in {guild_name}",
                color=discord.Color.red() if action in ['banned', 'kicked'] else discord.Color.yellow(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            if duration:
                embed.add_field(name="Duration", value=duration, inline=False)
            await member.send(embed=embed)
            return True
        except discord.Forbidden:
            log.warning(f"Could not DM {action} notification to user {member.id}.")
            return False

    # --- Cog-wide Error Handler ---
    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handles errors for all commands in this cog."""
        if isinstance(error, app_commands.MissingPermissions):
            perms = ", ".join(error.missing_permissions).replace("_", " ").title()
            await interaction.response.send_message(
                f"❌ You lack the required permissions to use this command. You need: `{perms}`.",
                ephemeral=True
            )
        elif isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(
                "❌ You do not meet the requirements to use this command.",
                ephemeral=True
            )
        else:
            log.error(f"An unexpected error occurred in command '{interaction.command.name}': {error}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "An unexpected error occurred. Please try again later.",
                    ephemeral=True
                )

    # --- Moderation Commands ---

    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.command(name="warn", description="Warn a member and log the warning.")
    @app_commands.describe(member="The member to warn", reason="The reason for the warning")
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        if not await self.check_hierarchy(interaction, member):
            return

        key = self._get_warnings_key(interaction.guild.id, member.id)
        new_warning = {
            "moderator_id": interaction.user.id,
            "reason": reason,
            "timestamp": int(datetime.utcnow().timestamp())
        }
        
        user_warnings = self.warnings_cache.setdefault(key, [])
        user_warnings.append(new_warning)
        self._save_warnings()
        
        log.info(f"'{interaction.user}' (ID: {interaction.user.id}) warned '{member}' (ID: {member.id}) in guild '{interaction.guild.name}' (ID: {interaction.guild.id}) for reason: {reason}")

        embed = discord.Embed(title="⚠️ Member Warned", color=discord.Color.yellow(), timestamp=datetime.utcnow())
        embed.add_field(name="Member", value=member.mention, inline=True)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        embed.add_field(name="Total Warnings", value=str(len(user_warnings)), inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_footer(text=f"Member ID: {member.id}")
        await interaction.response.send_message(embed=embed)

        dm_sent = await self.send_dm_notification(member, "warned", reason, interaction.guild.name)
        if not dm_sent:
            await interaction.followup.send("Could not notify the user via DM.", ephemeral=True)

    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.command(name="warnings", description="View all warnings for a member.")
    @app_commands.describe(member="The member whose warnings you want to see")
    async def warnings(self, interaction: discord.Interaction, member: discord.Member):
        key = self._get_warnings_key(interaction.guild.id, member.id)
        warnings_list = self.warnings_cache.get(key, [])

        if not warnings_list:
            await interaction.response.send_message(f"{member.mention} has no warnings.", ephemeral=True)
            return

        embed = discord.Embed(title=f"Warnings for {member.display_name}", color=discord.Color.orange(), timestamp=datetime.utcnow())
        embed.set_author(name=member, icon_url=member.display_avatar.url)
        
        # Display up to 10 most recent warnings
        for w in reversed(warnings_list[-10:]):
            moderator = interaction.guild.get_member(w["moderator_id"]) or f"ID: {w['moderator_id']}"
            embed.add_field(
                name=f"Warned on <t:{w['timestamp']}:D>",
                value=f"**Moderator:** {moderator}\n**Reason:** {w['reason']}",
                inline=False
            )
        
        embed.set_footer(text=f"Total warnings: {len(warnings_list)} | Showing latest 10")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.command(name="clearwarnings", description="Clear all warnings for a member.")
    @app_commands.describe(member="The member whose warnings you want to clear")
    async def clearwarnings(self, interaction: discord.Interaction, member: discord.Member):
        if not await self.check_hierarchy(interaction, member):
            return

        key = self._get_warnings_key(interaction.guild.id, member.id)
        if key in self.warnings_cache and self.warnings_cache[key]:
            warning_count = len(self.warnings_cache[key])
            del self.warnings_cache[key]
            self._save_warnings()
            log.info(f"'{interaction.user}' (ID: {interaction.user.id}) cleared {warning_count} warnings for '{member}' (ID: {member.id}).")
            await interaction.response.send_message(f"✅ Cleared {warning_count} warnings for {member.mention}.", ephemeral=True)
        else:
            await interaction.response.send_message(f"{member.mention} has no warnings to clear.", ephemeral=True)

    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.command(name="mute", description="Mute a member by applying a timeout.")
    @app_commands.describe(member="The member to mute", duration="Duration (e.g., 5m, 2h, 7d). Max 28 days.", reason="The reason for the mute")
    async def mute(self, interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = "No reason provided"):
        if not await self.check_hierarchy(interaction, member):
            return

        if member.is_timed_out():
            await interaction.response.send_message("❌ Member is already muted (timed out).", ephemeral=True)
            return
            
        delta = self.parse_duration(duration)
        if delta is None:
            await interaction.response.send_message("❌ Invalid duration format. Use 's', 'm', 'h', or 'd'. Ex: `30s`, `10m`, `5h`, `3d`.", ephemeral=True)
            return

        if delta > timedelta(days=28):
            await interaction.response.send_message("❌ Mute duration cannot exceed 28 days.", ephemeral=True)
            return

        try:
            await member.timeout(delta, reason=reason)
            log.info(f"'{interaction.user}' (ID: {interaction.user.id}) muted '{member}' (ID: {member.id}) for {duration}. Reason: {reason}")
            
            unmute_time = datetime.utcnow() + delta
            embed = discord.Embed(title="🔇 Member Muted", color=discord.Color.red(), timestamp=datetime.utcnow())
            embed.add_field(name="Member", value=member.mention, inline=True)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.add_field(name="Duration", value=duration, inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Unmutes On", value=f"<t:{int(unmute_time.timestamp())}:F>", inline=False)
            await interaction.response.send_message(embed=embed)
            
            await self.send_dm_notification(member, "muted", reason, interaction.guild.name, duration)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to time out this member.", ephemeral=True)

    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.command(name="unmute", description="Unmute a member by removing their timeout.")
    @app_commands.describe(member="The member to unmute", reason="The reason for the unmute")
    async def unmute(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Moderator decision"):
        if not await self.check_hierarchy(interaction, member):
            return

        if not member.is_timed_out():
            await interaction.response.send_message("❌ Member is not muted.", ephemeral=True)
            return
            
        try:
            await member.timeout(None, reason=reason)
            log.info(f"'{interaction.user}' (ID: {interaction.user.id}) unmuted '{member}' (ID: {member.id}). Reason: {reason}")
            embed = discord.Embed(title="🔊 Member Unmuted", color=discord.Color.green(), timestamp=datetime.utcnow())
            embed.add_field(name="Member", value=member.mention, inline=True)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to unmute this member.", ephemeral=True)

    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.command(name="kick", description="Kick a member from the server.")
    @app_commands.describe(member="The member to kick", reason="The reason for the kick")
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        if not await self.check_hierarchy(interaction, member):
            return

        await self.send_dm_notification(member, "kicked", reason, interaction.guild.name)
        
        try:
            await member.kick(reason=reason)
            log.info(f"'{interaction.user}' (ID: {interaction.user.id}) kicked '{member}' (ID: {member.id}). Reason: {reason}")
            embed = discord.Embed(title="👢 Member Kicked", color=discord.Color.red(), timestamp=datetime.utcnow())
            embed.add_field(name="Member", value=f"{member.name} ({member.id})", inline=True)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to kick this member.", ephemeral=True)

    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.command(name="ban", description="Ban a member from the server.")
    @app_commands.describe(
        member="The member to ban", 
        reason="The reason for the ban",
        delete_hours="How many hours of recent messages to delete (0-168, default 0)"
    )
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided", delete_hours: app_commands.Range[int, 0, 168] = 0):
        if not await self.check_hierarchy(interaction, member):
            return
            
        await self.send_dm_notification(member, "banned", reason, interaction.guild.name)

        try:
            delete_seconds = delete_hours * 3600
            await member.ban(reason=reason, delete_message_seconds=delete_seconds)
            log.info(f"'{interaction.user}' (ID: {interaction.user.id}) banned '{member}' (ID: {member.id}). Reason: {reason}")
            
            embed = discord.Embed(title="🔨 Member Banned", color=discord.Color.dark_red(), timestamp=datetime.utcnow())
            embed.add_field(name="Member", value=f"{member.name} ({member.id})", inline=True)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.add_field(name="Messages Deleted", value=f"Last {delete_hours} hours", inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to ban this member.", ephemeral=True)

    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.command(name="unban", description="Unban a user from the server.")
    @app_commands.describe(user_id="The ID of the user to unban", reason="The reason for the unban")
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str = "No reason provided"):
        try:
            user_id = int(user_id)
            user = await self.bot.fetch_user(user_id)
        except (ValueError, discord.NotFound):
            await interaction.response.send_message("❌ Invalid user ID or user not found.", ephemeral=True)
            return

        try:
            await interaction.guild.unban(user, reason=reason)
            log.info(f"'{interaction.user}' (ID: {interaction.user.id}) unbanned '{user}' (ID: {user.id}). Reason: {reason}")
            
            embed = discord.Embed(title="✅ Member Unbanned", color=discord.Color.green(), timestamp=datetime.utcnow())
            embed.add_field(name="User", value=f"{user.name} ({user.id})", inline=True)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            await interaction.response.send_message(embed=embed)
        except discord.NotFound:
            await interaction.response.send_message("❌ User is not banned.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to unban users.", ephemeral=True)

    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.command(name="purge", description="Delete multiple messages from a channel.")
    @app_commands.describe(
        amount="Number of messages to delete (1-100)",
        member="Only delete messages from this member (optional)",
        reason="Reason for purging messages"
    )
    async def purge(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100], member: discord.Member = None, reason: str = "No reason provided"):
        await interaction.response.defer(ephemeral=True)
        
        def check(message):
            if member:
                return message.author == member
            return True
        
        try:
            deleted = await interaction.channel.purge(limit=amount, check=check, before=interaction.created_at)
            log.info(f"'{interaction.user}' (ID: {interaction.user.id}) purged {len(deleted)} messages in #{interaction.channel.name}. Reason: {reason}")
            
            target_text = f" from {member.mention}" if member else ""
            await interaction.followup.send(
                f"✅ Successfully deleted {len(deleted)} message{'s' if len(deleted) != 1 else ''}{target_text}.",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send("❌ I don't have permission to delete messages in this channel.", ephemeral=True)

    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.command(name="slowmode", description="Set slowmode for a channel.")
    @app_commands.describe(
        seconds="Slowmode delay in seconds (0-21600, 0 to disable)",
        channel="Channel to apply slowmode to (defaults to current channel)"
    )
    async def slowmode(self, interaction: discord.Interaction, seconds: app_commands.Range[int, 0, 21600], channel: discord.TextChannel = None):
        target_channel = channel or interaction.channel
        
        try:
            await target_channel.edit(slowmode_delay=seconds)
            log.info(f"'{interaction.user}' (ID: {interaction.user.id}) set slowmode to {seconds}s in #{target_channel.name}")
            
            if seconds == 0:
                embed = discord.Embed(title="⏱️ Slowmode Disabled", color=discord.Color.green())
                embed.add_field(name="Channel", value=target_channel.mention)
            else:
                embed = discord.Embed(title="⏱️ Slowmode Enabled", color=discord.Color.orange())
                embed.add_field(name="Channel", value=target_channel.mention, inline=True)
                embed.add_field(name="Delay", value=f"{seconds} seconds", inline=True)
            
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to manage this channel.", ephemeral=True)

    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.command(name="lock", description="Lock a channel to prevent members from sending messages.")
    @app_commands.describe(
        channel="Channel to lock (defaults to current channel)",
        reason="Reason for locking the channel"
    )
    async def lock(self, interaction: discord.Interaction, channel: discord.TextChannel = None, reason: str = "No reason provided"):
        target_channel = channel or interaction.channel
        
        if target_channel.id in self.locked_channels:
            await interaction.response.send_message("❌ This channel is already locked by the bot.", ephemeral=True)
            return
        
        try:
            everyone_role = interaction.guild.default_role
            await target_channel.set_permissions(everyone_role, send_messages=False, reason=reason)
            self.locked_channels.add(target_channel.id)
            
            log.info(f"'{interaction.user}' (ID: {interaction.user.id}) locked #{target_channel.name}. Reason: {reason}")
            
            embed = discord.Embed(title="🔒 Channel Locked", color=discord.Color.red(), timestamp=datetime.utcnow())
            embed.add_field(name="Channel", value=target_channel.mention, inline=True)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to manage this channel.", ephemeral=True)

    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.command(name="unlock", description="Unlock a previously locked channel.")
    @app_commands.describe(
        channel="Channel to unlock (defaults to current channel)",
        reason="Reason for unlocking the channel"
    )
    async def unlock(self, interaction: discord.Interaction, channel: discord.TextChannel = None, reason: str = "No reason provided"):
        target_channel = channel or interaction.channel
        
        # Check current permissions to see if it's actually locked for @everyone
        current_perms = target_channel.permissions_for(interaction.guild.default_role)
        if current_perms.send_messages is not False:
             await interaction.response.send_message("❌ This channel does not appear to be locked.", ephemeral=True)
             if target_channel.id in self.locked_channels:
                 self.locked_channels.remove(target_channel.id) # Correct internal state
             return
        
        try:
            everyone_role = interaction.guild.default_role
            await target_channel.set_permissions(everyone_role, send_messages=None, reason=reason) # Reset to default
            if target_channel.id in self.locked_channels:
                self.locked_channels.remove(target_channel.id)
            
            log.info(f"'{interaction.user}' (ID: {interaction.user.id}) unlocked #{target_channel.name}. Reason: {reason}")
            
            embed = discord.Embed(title="🔓 Channel Unlocked", color=discord.Color.green(), timestamp=datetime.utcnow())
            embed.add_field(name="Channel", value=target_channel.mention, inline=True)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to manage this channel.", ephemeral=True)

    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.command(name="role", description="Add or remove a role from a member.")
    @app_commands.describe(
        member="The member to modify",
        role="The role to add or remove",
        action="Whether to add or remove the role"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Add", value="add"),
        app_commands.Choice(name="Remove", value="remove")
    ])
    async def role(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role, action: str):
        if not await self.check_hierarchy(interaction, member):
            return
        
        if role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            await interaction.response.send_message("❌ You cannot manage a role equal or higher than your highest role.", ephemeral=True)
            return
        
        if role.is_bot_managed() or role.is_premium_subscriber() or role.is_integration() or role.is_default():
            await interaction.response.send_message(f"❌ Cannot manage the role {role.mention} as it is managed by an integration or is a default role.", ephemeral=True)
            return
            
        if role >= interaction.guild.me.top_role:
            await interaction.response.send_message("❌ I cannot manage a role equal or higher than my highest role.", ephemeral=True)
            return
        
        try:
            if action == "add":
                if role in member.roles:
                    await interaction.response.send_message(f"❌ {member.mention} already has the {role.mention} role.", ephemeral=True)
                    return
                await member.add_roles(role, reason=f"Action by {interaction.user}")
                color = discord.Color.green()
                action_text = "Added"
                emoji = "➕"
            else: # remove
                if role not in member.roles:
                    await interaction.response.send_message(f"❌ {member.mention} doesn't have the {role.mention} role.", ephemeral=True)
                    return
                await member.remove_roles(role, reason=f"Action by {interaction.user}")
                color = discord.Color.red()
                action_text = "Removed"
                emoji = "➖"
            
            log.info(f"'{interaction.user}' (ID: {interaction.user.id}) {action}ed role '{role.name}' {'to' if action == 'add' else 'from'} '{member}' (ID: {member.id})")
            
            embed = discord.Embed(title=f"{emoji} Role {action_text}", color=color, timestamp=datetime.utcnow())
            embed.add_field(name="Member", value=member.mention, inline=True)
            embed.add_field(name="Role", value=role.mention, inline=True)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to manage roles for this user.", ephemeral=True)

    # --- Info Commands ---

    @app_commands.command(name="userinfo", description="Shows information about a user.")
    @app_commands.describe(member="The member to get info about (defaults to yourself)")
    async def userinfo(self, interaction: discord.Interaction, member: Union[discord.Member, discord.User] = None):
        target = member or interaction.user
        
        embed = discord.Embed(
            title=f"👤 User Info: {target.display_name}",
            color=target.color if isinstance(target, discord.Member) and target.color != discord.Color.default() else discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        
        # Basic info
        embed.add_field(name="Username", value=str(target), inline=True)
        embed.add_field(name="ID", value=target.id, inline=True)
        embed.add_field(name="Bot", value="Yes" if target.bot else "No", inline=True)
        
        # Dates
        embed.add_field(name="Account Created", value=f"<t:{int(target.created_at.timestamp())}:F>", inline=False)
        if isinstance(target, discord.Member):
            embed.add_field(name="Joined Server", value=f"<t:{int(target.joined_at.timestamp())}:F>", inline=False)
        
            # Roles
            roles = [role.mention for role in reversed(target.roles[1:])]  # Exclude @everyone
            roles_str = " ".join(roles) if roles else "None"
            if len(roles_str) > 1024:
                roles_str = f"{len(roles)} roles"
            embed.add_field(
                name=f"Roles ({len(roles)})",
                value=roles_str,
                inline=False
            )
        
            # Warnings count
            key = self._get_warnings_key(interaction.guild.id, target.id)
            warning_count = len(self.warnings_cache.get(key, []))
            embed.add_field(name="Warnings", value=str(warning_count), inline=True)
            
            # Status info
            embed.add_field(name="Status", value=str(target.status).title(), inline=True)
            if target.is_timed_out():
                embed.add_field(name="Muted", value=f"Until <t:{int(target.timed_out_until.timestamp())}:R>", inline=True)
        
        embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="serverinfo", description="Shows information about the server.")
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        embed = discord.Embed(
            title=f"🌐 Server Info: {guild.name}",
            color=guild.owner.color if guild.owner and guild.owner.color != discord.Color.default() else discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
        embed.add_field(name="Created On", value=f"<t:{int(guild.created_at.timestamp())}:F>", inline=True)
        
        humans = len([m for m in guild.members if not m.bot])
        bots = guild.member_count - humans
        embed.add_field(name="Members", value=f"**Total:** {guild.member_count}\n"
                                             f"**Humans:** {humans}\n"
                                             f"**Bots:** {bots}", inline=True)
        
        embed.add_field(name="Channels", value=f"**Text:** {len(guild.text_channels)}\n"
                                               f"**Voice:** {len(guild.voice_channels)}\n"
                                               f"**Stages:** {len(guild.stage_channels)}", inline=True)
                                               
        embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
        embed.add_field(name="Boosts", value=f"**Level {guild.premium_tier}** ({guild.premium_subscription_count} boosts)", inline=True)
        
        embed.set_footer(text=f"Server ID: {guild.id}")
        await interaction.response.send_message(embed=embed)

# --- Cog Setup Function ---
async def setup(bot: commands.Bot):
    """Loads the Moderation cog into the bot."""
    await bot.add_cog(Moderation(bot))
