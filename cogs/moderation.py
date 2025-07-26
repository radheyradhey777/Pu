import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import asyncio
import json
import sqlite3
from typing import Optional, Union

class ModerationDatabase:
    def __init__(self, db_path: str = "moderation.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Moderation logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS mod_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                moderator_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                reason TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                duration INTEGER,
                active BOOLEAN DEFAULT 1
            )
        ''')
        
        # Warnings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                moderator_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                active BOOLEAN DEFAULT 1
            )
        ''')
        
        # Temporary punishments table (mutes, temp bans)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS temp_punishments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                punishment_type TEXT NOT NULL,
                expires_at DATETIME NOT NULL,
                active BOOLEAN DEFAULT 1
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def log_action(self, guild_id: int, user_id: int, moderator_id: int, action: str, reason: str = None, duration: int = None):
        """Log a moderation action"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO mod_logs (guild_id, user_id, moderator_id, action, reason, duration)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (guild_id, user_id, moderator_id, action, reason, duration))
        conn.commit()
        conn.close()
    
    def add_warning(self, guild_id: int, user_id: int, moderator_id: int, reason: str):
        """Add a warning to the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO warnings (guild_id, user_id, moderator_id, reason)
            VALUES (?, ?, ?, ?)
        ''', (guild_id, user_id, moderator_id, reason))
        conn.commit()
        conn.close()
    
    def get_warnings(self, guild_id: int, user_id: int):
        """Get all active warnings for a user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM warnings 
            WHERE guild_id = ? AND user_id = ? AND active = 1
            ORDER BY timestamp DESC
        ''', (guild_id, user_id))
        warnings = cursor.fetchall()
        conn.close()
        return warnings
    
    def add_temp_punishment(self, guild_id: int, user_id: int, punishment_type: str, expires_at: datetime):
        """Add a temporary punishment"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO temp_punishments (guild_id, user_id, punishment_type, expires_at)
            VALUES (?, ?, ?, ?)
        ''', (guild_id, user_id, punishment_type, expires_at.isoformat()))
        conn.commit()
        conn.close()
    
    def remove_temp_punishment(self, guild_id: int, user_id: int, punishment_type: str):
        """Remove a temporary punishment"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE temp_punishments 
            SET active = 0 
            WHERE guild_id = ? AND user_id = ? AND punishment_type = ? AND active = 1
        ''', (guild_id, user_id, punishment_type))
        conn.commit()
        conn.close()

    def get_active_temp_punishments(self):
        """Get all active temporary punishments"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT guild_id, user_id, punishment_type, expires_at 
            FROM temp_punishments 
            WHERE active = 1
        ''')
        punishments = cursor.fetchall()
        conn.close()
        return punishments

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = ModerationDatabase()
        self.bot.loop.create_task(self.check_temp_punishments())

    async def check_permissions(self, interaction: discord.Interaction, target: discord.Member = None):
        """Check if user has moderation permissions and can target the member"""
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return False
        
        if target and target.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            await interaction.response.send_message("❌ You cannot moderate someone with equal or higher role.", ephemeral=True)
            return False
        
        if target and target == interaction.guild.owner:
            await interaction.response.send_message("❌ You cannot moderate the server owner.", ephemeral=True)
            return False
        
        return True

    def parse_duration(self, duration_str: str) -> datetime:
        """Parses a duration string (e.g., 10m, 1h, 2d) into a datetime object."""
        unit = duration_str[-1].lower()
        value = int(duration_str[:-1])
        
        if unit == 'm':
            return datetime.utcnow() + timedelta(minutes=value)
        elif unit == 'h':
            return datetime.utcnow() + timedelta(hours=value)
        elif unit == 'd':
            return datetime.utcnow() + timedelta(days=value)
        else:
            raise ValueError("Invalid duration unit. Use 'm' for minutes, 'h' for hours, or 'd' for days.")

    async def get_or_create_mute_role(self, guild: discord.Guild) -> Optional[discord.Role]:
        """Get existing mute role or create a new one"""
        mute_role = discord.utils.get(guild.roles, name="Muted")
        
        if not mute_role:
            try:
                mute_role = await guild.create_role(
                    name="Muted",
                    color=discord.Color.dark_gray(),
                    reason="Auto-created mute role"
                )
                
                # Set permissions for all channels
                for channel in guild.channels:
                    try:
                        if isinstance(channel, discord.TextChannel):
                            await channel.set_permissions(mute_role, send_messages=False, add_reactions=False, speak=False)
                        elif isinstance(channel, discord.VoiceChannel):
                            await channel.set_permissions(mute_role, speak=False, connect=False)
                        elif isinstance(channel, discord.StageChannel):
                            await channel.set_permissions(mute_role, speak=False, request_to_speak=False)
                    except discord.Forbidden:
                        continue
                        
            except discord.Forbidden:
                return None
                
        return mute_role

    async def schedule_unmute(self, member: discord.Member, mute_role: discord.Role, unmute_time: datetime):
        """Schedules the unmuting of a member."""
        await discord.utils.sleep_until(unmute_time)
        
        if mute_role in member.roles:
            try:
                await member.remove_roles(mute_role, reason="Automatic unmute")
                self.db.remove_temp_punishment(member.guild.id, member.id, "mute")
                self.db.log_action(member.guild.id, member.id, self.bot.user.id, "unmute", "Automatic unmute", 0) # Bot as moderator
                
                # Notify the guild or log channel if available
                print(f"Automatically unmuted {member.display_name} in {member.guild.name}")
            except discord.Forbidden:
                print(f"Failed to automatically unmute {member.display_name} in {member.guild.name} (Missing Permissions)")
            except Exception as e:
                print(f"Error during automatic unmute for {member.display_name}: {e}")

    async def check_temp_punishments(self):
        """Periodically checks for expired temporary punishments and lifts them."""
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            punishments = self.db.get_active_temp_punishments()
            now = datetime.utcnow()

            for guild_id, user_id, punishment_type, expires_at_str in punishments:
                expires_at = datetime.fromisoformat(expires_at_str)

                if now >= expires_at:
                    guild = self.bot.get_guild(guild_id)
                    if not guild:
                        self.db.remove_temp_punishment(guild_id, user_id, punishment_type) # Remove if guild not found
                        continue
                    
                    member = guild.get_member(user_id)
                    if not member:
                        self.db.remove_temp_punishment(guild_id, user_id, punishment_type) # Remove if member not found
                        continue

                    if punishment_type == "mute":
                        mute_role = discord.utils.get(guild.roles, name="Muted")
                        if mute_role and mute_role in member.roles:
                            await self.schedule_unmute(member, mute_role, expires_at) # Re-use schedule_unmute logic
                        else:
                            self.db.remove_temp_punishment(guild_id, user_id, punishment_type) # Not muted, so remove record
                    # Add other punishment types (e.g., temp ban) here if needed
            
            await asyncio.sleep(60) # Check every minute

    ---

    ## Moderation Commands

    @app_commands.command(name="warn", description="Warn a member")
    @app_commands.describe(member="Member to warn", reason="Reason for warning")
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        if not await self.check_permissions(interaction, member):
            return
        
        # Add warning to database
        self.db.add_warning(interaction.guild.id, member.id, interaction.user.id, reason)
        self.db.log_action(interaction.guild.id, member.id, interaction.user.id, "warn", reason)
        
        # Get total warnings
        warnings = self.db.get_warnings(interaction.guild.id, member.id)
        warning_count = len(warnings)
        
        embed = discord.Embed(
            title="⚠️ Member Warned",
            color=discord.Color.yellow(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="Member", value=member.mention, inline=True)
        embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        embed.add_field(name="Total Warnings", value=warning_count, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)
        
        await interaction.response.send_message(embed=embed)
        
        # Try to DM the user
        try:
            dm_embed = discord.Embed(
                title=f"You received a warning in {interaction.guild.name}",
                color=discord.Color.yellow(),
                timestamp=datetime.utcnow()
            )
            dm_embed.add_field(name="Reason", value=reason, inline=False)
            dm_embed.add_field(name="Total Warnings", value=warning_count, inline=True)
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            pass

    @app_commands.command(name="warnings", description="View warnings for a member")
    @app_commands.describe(member="Member to check warnings for")
    async def warnings(self, interaction: discord.Interaction, member: discord.Member):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You don't have permission to view warnings.", ephemeral=True)
            return
        
        warnings = self.db.get_warnings(interaction.guild.id, member.id)
        
        if not warnings:
            await interaction.response.send_message(f"✅ {member.mention} has no warnings.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"⚠️ Warnings for {member.display_name}",
            color=discord.Color.yellow(),
            timestamp=datetime.utcnow()
        )
        
        for i, warning in enumerate(warnings[:10], 1):  # Show only last 10 warnings
            moderator = self.bot.get_user(warning[3])
            mod_name = moderator.display_name if moderator else f"ID: {warning[3]}"
            # Adjusting for different datetime formats if needed, assuming ISO format from DB
            timestamp = datetime.fromisoformat(warning[5])
            
            embed.add_field(
                name=f"Warning #{i}",
                value=f"**Moderator:** {mod_name}\n**Reason:** {warning[4]}\n**Date:** <t:{int(timestamp.timestamp())}:R>",
                inline=False
            )
        
        if len(warnings) > 10:
            embed.set_footer(text=f"Showing latest 10 of {len(warnings)} warnings")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="mute", description="Mute a member")
    @app_commands.describe(
        member="Member to mute", 
        reason="Reason for mute",
        duration="Duration (e.g., 10m, 1h, 2d)"
    )
    async def mute(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided", duration: str = None):
        if not await self.check_permissions(interaction, member):
            return
        
        mute_role = await self.get_or_create_mute_role(interaction.guild)
        if not mute_role:
            await interaction.response.send_message("❌ I don't have permission to create or manage the mute role. Please ensure I have 'Manage Roles' permission.", ephemeral=True)
            return
        
        if mute_role in member.roles:
            await interaction.response.send_message(f"❌ {member.mention} is already muted.", ephemeral=True)
            return
        
        try:
            # Parse duration if provided
            unmute_time = None
            duration_seconds = None
            if duration:
                try:
                    unmute_time = self.parse_duration(duration)
                    duration_seconds = int((unmute_time - datetime.utcnow()).total_seconds())
                except ValueError:
                    await interaction.response.send_message("❌ Invalid duration format. Use formats like: 10m, 1h, 2d", ephemeral=True)
                    return
            
            await member.add_roles(mute_role, reason=f"Muted by {interaction.user} | {reason}")
            
            # Log to database
            self.db.log_action(interaction.guild.id, member.id, interaction.user.id, "mute", reason, duration_seconds)
            
            if unmute_time:
                self.db.add_temp_punishment(interaction.guild.id, member.id, "mute", unmute_time)
                asyncio.create_task(self.schedule_unmute(member, mute_role, unmute_time))
            
            embed = discord.Embed(
                title="🔇 Member Muted",
                color=discord.Color.orange(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Member", value=member.mention, inline=True)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            
            if unmute_time:
                embed.add_field(name="Duration", value=duration, inline=True)
                embed.add_field(name="Unmutes at", value=f"<t:{int(unmute_time.timestamp())}:F>", inline=True)
            
            await interaction.response.send_message(embed=embed)
            
            # Try to DM the user
            try:
                dm_embed = discord.Embed(
                    title=f"You were muted in {interaction.guild.name}",
                    color=discord.Color.orange(),
                    timestamp=datetime.utcnow()
                )
                dm_embed.add_field(name="Reason", value=reason, inline=False)
                if unmute_time:
                    dm_embed.add_field(name="Duration", value=duration, inline=True)
                    dm_embed.add_field(name="Unmutes at", value=f"<t:{int(unmute_time.timestamp())}:F>", inline=True)
                await member.send(embed=dm_embed)
            except discord.Forbidden:
                pass
                
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to mute this member. Please check my role hierarchy.", ephemeral=True)

    @app_commands.command(name="unmute", description="Unmute a member")
    @app_commands.describe(member="Member to unmute", reason="Reason for unmute")
    async def unmute(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        if not await self.check_permissions(interaction, member):
            return
        
        mute_role = discord.utils.get(interaction.guild.roles, name="Muted")
        if not mute_role or mute_role not in member.roles:
            await interaction.response.send_message(f"❌ {member.mention} is not muted.", ephemeral=True)
            return
        
        try:
            await member.remove_roles(mute_role, reason=f"Unmuted by {interaction.user} | {reason}")
            
            # Remove from temp punishments
            self.db.remove_temp_punishment(interaction.guild.id, member.id, "mute")
            self.db.log_action(interaction.guild.id, member.id, interaction.user.id, "unmute", reason)
            
            embed = discord.Embed(
                title="🔊 Member Unmuted",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Member", value=member.mention, inline=True)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            
            await interaction.response.send_message(embed=embed)
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to unmute this member. Please check my role hierarchy.", ephemeral=True)

    @app_commands.command(name="timeout", description="Timeout a member (Discord's built-in timeout)")
    @app_commands.describe(
        member="Member to timeout",
        duration="Duration (e.g., 10m, 1h, 2d, max 28d)",
        reason="Reason for timeout"
    )
    async def timeout(self, interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = "No reason provided"):
        if not await self.check_permissions(interaction, member):
            return
        
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ You don't have permission to timeout members.", ephemeral=True)
            return
        
        try:
            timeout_until = self.parse_duration(duration)
            max_timeout = datetime.utcnow() + timedelta(days=28)
            
            if timeout_until > max_timeout:
                await interaction.response.send_message("❌ Timeout duration cannot exceed 28 days.", ephemeral=True)
                return
                
        except ValueError:
            await interaction.response.send_message("❌ Invalid duration format. Use formats like: 10m, 1h, 2d", ephemeral=True)
            return
        
        try:
            # Check if member is already timed out
            if member.is_timed_out():
                await interaction.response.send_message(f"❌ {member.mention} is already timed out. Use `/untimeout` first if you wish to change their timeout.", ephemeral=True)
                return

            await member.timeout(timeout_until, reason=f"Timed out by {interaction.user} | {reason}")
            
            duration_seconds = int((timeout_until - datetime.utcnow()).total_seconds())
            self.db.log_action(interaction.guild.id, member.id, interaction.user.id, "timeout", reason, duration_seconds)
            
            embed = discord.Embed(
                title="⏰ Member Timed Out",
                color=discord.Color.orange(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Member", value=member.mention, inline=True)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.add_field(name="Duration", value=duration, inline=True)
            embed.add_field(name="Ends at", value=f"<t:{int(timeout_until.timestamp())}:F>", inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            
            await interaction.response.send_message(embed=embed)

            # Try to DM the user
            try:
                dm_embed = discord.Embed(
                    title=f"You were timed out in {interaction.guild.name}",
                    color=discord.Color.orange(),
                    timestamp=datetime.utcnow()
                )
                dm_embed.add_field(name="Reason", value=reason, inline=False)
                dm_embed.add_field(name="Duration", value=duration, inline=True)
                dm_embed.add_field(name="Ends at", value=f"<t:{int(timeout_until.timestamp())}:F>", inline=True)
                await member.send(embed=dm_embed)
            except discord.Forbidden:
                pass
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to timeout this member. Please check my role hierarchy and 'Moderate Members' permission.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An unexpected error occurred: {e}", ephemeral=True)


    @app_commands.command(name="untimeout", description="Remove timeout from a member")
    @app_commands.describe(member="Member to remove timeout from", reason="Reason for removing timeout")
    async def untimeout(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        if not await self.check_permissions(interaction, member):
            return
        
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ You don't have permission to manage timeouts.", ephemeral=True)
            return
        
        if not member.is_timed_out():
            await interaction.response.send_message(f"❌ {member.mention} is not timed out.", ephemeral=True)
            return
        
        try:
            await member.timeout(None, reason=f"Timeout removed by {interaction.user} | {reason}")
            
            self.db.log_action(interaction.guild.id, member.id, interaction.user.id, "untimeout", reason)
            
            embed = discord.Embed(
                title="⏰ Timeout Removed",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Member", value=member.mention, inline=True)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            
            await interaction.response.send_message(embed=embed)

            # Try to DM the user
            try:
                dm_embed = discord.Embed(
                    title=f"Your timeout was removed in {interaction.guild.name}",
                    color=discord.Color.green(),
                    timestamp=datetime.utcnow()
                )
                dm_embed.add_field(name="Reason", value=reason, inline=False)
                await member.send(embed=dm_embed)
            except discord.Forbidden:
                pass
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to remove timeout from this member. Please check my role hierarchy and 'Moderate Members' permission.", ephemeral=True)

    @app_commands.command(name="kick", description="Kick a member")
    @app_commands.describe(member="Member to kick", reason="Reason for kick")
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        if not await self.check_permissions(interaction, member):
            return
        
        if not interaction.user.guild_permissions.kick_members:
            await interaction.response.send_message("❌ You don't have permission to kick members.", ephemeral=True)
            return
        
        try:
            # Try to DM before kicking
            try:
                dm_embed = discord.Embed(
                    title=f"You were kicked from {interaction.guild.name}",
                    color=discord.Color.red(),
                    timestamp=datetime.utcnow()
                )
                dm_embed.add_field(name="Reason", value=reason, inline=False)
                await member.send(embed=dm_embed)
            except discord.Forbidden:
                pass
            
            await member.kick(reason=f"Kicked by {interaction.user} | {reason}")
            
            self.db.log_action(interaction.guild.id, member.id, interaction.user.id, "kick", reason)
            
            embed = discord.Embed(
                title="👢 Member Kicked",
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Member", value=f"{member} ({member.id})", inline=True)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            
            await interaction.response.send_message(embed=embed)
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to kick this member. Please check my role hierarchy.", ephemeral=True)

    @app_commands.command(name="ban", description="Ban a member")
    @app_commands.describe(
        member="Member to ban", 
        reason="Reason for ban",
        delete_days="Days of messages to delete (0-7)"
    )
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided", delete_days: int = 0):
        if not await self.check_permissions(interaction, member):
            return
        
        if not interaction.user.guild_permissions.ban_members:
            await interaction.response.send_message("❌ You don't have permission to ban members.", ephemeral=True)
            return
        
        if delete_days < 0 or delete_days > 7:
            await interaction.response.send_message("❌ Delete days must be between 0 and 7.", ephemeral=True)
            return
        
        try:
            # Try to DM before banning
            try:
                dm_embed = discord.Embed(
                    title=f"You were banned from {interaction.guild.name}",
                    color=discord.Color.dark_red(),
                    timestamp=datetime.utcnow()
                )
                dm_embed.add_field(name="Reason", value=reason, inline=False)
                await member.send(embed=dm_embed)
            except discord.Forbidden:
                pass
            
            await member.ban(reason=f"Banned by {interaction.user} | {reason}", delete_message_days=delete_days)
            
            self.db.log_action(interaction.guild.id, member.id, interaction.user.id, "ban", reason)
            
            embed = discord.Embed(
                title="🔨 Member Banned",
                color=discord.Color.dark_red(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Member", value=f"{member} ({member.id})", inline=True)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            if delete_days > 0:
                embed.add_field(name="Messages Deleted", value=f"{delete_days} days", inline=True)
            
            await interaction.response.send_message(embed=embed)
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to ban this member. Please check my role hierarchy.", ephemeral=True)

    @app_commands.command(name="unban", description="Unban a user")
    @app_commands.describe(user_id="User ID to unban", reason="Reason for unban")
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str = "No reason provided"):
        if not interaction.user.guild_permissions.ban_members:
            await interaction.response.send_message("❌ You don't have permission to unban members.", ephemeral=True)
            return
        
        try:
            user_id_int = int(user_id)
        except ValueError:
            await interaction.response.send_message("❌ Invalid user ID. Please provide a numerical user ID.", ephemeral=True)
            return
        
        try:
            user = await self.bot.fetch_user(user_id_int)
            await interaction.guild.unban(user, reason=f"Unbanned by {interaction.user} | {reason}")
            
            self.db.log_action(interaction.guild.id, user_id_int, interaction.user.id, "unban", reason)
            
            embed = discord.Embed(
                title="🔓 User Unbanned",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="User", value=f"{user} ({user.id})", inline=True)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            
            await interaction.response.send_message(embed=embed)
            
        except discord.NotFound:
            await interaction.response.send_message("❌ User not found in ban list or not banned.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to unban users.", ephemeral=True)

    @app_commands.command(name="modlogs", description="View moderation logs for a user")
    @app_commands.describe(member="Member to view logs for", limit="Number of logs to show (default 10)")
    async def modlogs(self, interaction: discord.Interaction, member: discord.Member, limit: int = 10):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You don't have permission to view moderation logs.", ephemeral=True)
            return
        
        if limit < 1 or limit > 25:
            limit = 10
        
        # Get logs from database
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT action, reason, timestamp, moderator_id, duration FROM mod_logs 
            WHERE guild_id = ? AND user_id = ? 
            ORDER BY timestamp DESC LIMIT ?
        ''', (interaction.guild.id, member.id, limit))
        logs = cursor.fetchall()
        conn.close()
        
        if not logs:
            await interaction.response.send_message(f"✅ {member.mention} has no moderation history.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"📋 Moderation Logs for {member.display_name}",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        for log in logs:
            action, reason, timestamp, moderator_id, duration = log
            moderator = self.bot.get_user(moderator_id)
            mod_name = moderator.display_name if moderator else f"ID: {moderator_id}"
            
            # Parse timestamp
            try:
                log_time = datetime.fromisoformat(timestamp)
                time_str = f"<t:{int(log_time.timestamp())}:R>"
            except:
                time_str = timestamp # Fallback if parsing fails
            
            log_detail = f"**Moderator:** {mod_name}\n**Reason:** {reason or 'No reason provided'}"
            if duration is not None and action in ["mute", "timeout"]:
                # Convert duration seconds back to a human-readable format if possible
                if duration < 60:
                    duration_str = f"{duration} seconds"
                elif duration < 3600:
                    duration_str = f"{round(duration/60)} minutes"
                elif duration < 86400:
                    duration_str = f"{round(duration/3600)} hours"
                else:
                    duration_str = f"{round(duration/86400)} days"
                log_detail += f"\n**Duration:** {duration_str}"

            embed.add_field(
                name=f"{action.title()} - {time_str}",
                value=log_detail,
                inline=False
            )
        
        embed.set_footer(text=f"Showing {len(logs)} most recent logs")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="purge", description="Delete multiple messages")
    @app_commands.describe(amount="Number of messages to delete (1-100)", member="Only delete messages from this member")
    async def purge(self, interaction: discord.Interaction, amount: int, member: Optional[discord.Member] = None):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You don't have permission to manage messages.", ephemeral=True)
            return
        
        if amount < 1 or amount > 100:
            await interaction.response.send_message("❌ Amount must be between 1 and 100.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            def check(message):
                if member:
                    return message.author == member and not message.pinned
                return not message.pinned # Don't delete pinned messages by default
            
            deleted = await interaction.channel.purge(limit=amount, check=check)
            
            # Log the action. If `member` is None, log user_id as 0 or a placeholder indicating "all"
            self.db.log_action(
                interaction.guild.id, 
                member.id if member else 0, # Use 0 or a specific ID to denote "all users" if member is None
                interaction.user.id, 
                "purge", 
                f"Deleted {len(deleted)} messages" + (f" from {member.display_name}" if member else "")
            )
            
            embed = discord.Embed(
                title="🧹 Messages Purged",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Messages Deleted", value=len(deleted), inline=True)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            if member:
                embed.add_field(name="Target User", value=member.mention, inline=True)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except discord.Forbidden:
            await interaction.followup.send("❌ I don't have permission to delete messages in this channel. Please ensure I have 'Manage Messages' permission.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"An unexpected error occurred during purge: {e}", ephemeral=True)


    ---

    ## Utility Commands

    @app_commands.command(name="serverinfo", description="Shows server information")
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        
        # Calculate member stats
        total_members = guild.member_count
        humans = len([m for m in guild.members if not m.bot])
        bots = total_members - humans
        
        # Get online members
        online_members = [m for m in guild.members if m.status != discord.Status.offline and not m.bot]
        online_count = len(online_members)

        # Get creation date
        created_at = guild.created_at

        # Get verification level
        verification_levels = {
            discord.VerificationLevel.none: "None",
            discord.VerificationLevel.low: "Low (Must have a verified email)",
            discord.VerificationLevel.medium: "Medium (Must be registered on Discord for >5 minutes)",
            discord.VerificationLevel.high: "High (Must be a member of the server for >10 minutes)",
            discord.VerificationLevel.extreme: "Extreme (Must have a verified phone on their Discord account)"
        }
        verification_level = verification_levels.get(guild.verification_level, "Unknown")

        # Get features
        features = ", ".join([f.replace('_', ' ').title() for f in guild.features]) if guild.features else "None"

        embed = discord.Embed(
            title=f"🌐 Server Info: {guild.name}",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        embed.add_field(name="🆔 Server ID", value=guild.id, inline=True)
        embed.add_field(name="👑 Owner", value=guild.owner.mention, inline=True)
        embed.add_field(name="📅 Created On", value=f"<t:{int(created_at.timestamp())}:F> (<t:{int(created_at.timestamp())}:R>)", inline=False)
        embed.add_field(name="👥 Members", value=f"Total: {total_members}\nHumans: {humans}\nBots: {bots}", inline=True)
        embed.add_field(name="🟢 Online Members", value=online_count, inline=True)
        embed.add_field(name="💬 Channels", value=f"Text: {len(guild.text_channels)}\nVoice: {len(guild.voice_channels)}\nCategories: {len(guild.categories)}", inline=True)
        embed.add_field(name="🎭 Roles", value=len(guild.roles), inline=True)
        embed.add_field(name="Verification Level", value=verification_level, inline=False)
        embed.add_field(name="🚀 Boosts", value=f"{guild.premium_subscription_count} (Level {guild.premium_tier})", inline=True)
        embed.add_field(name="Region", value=str(guild.region).replace('-', ' ').title(), inline=True) # region is deprecated
        if features:
            embed.add_field(name="Features", value=features, inline=False)

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Moderation(bot))
