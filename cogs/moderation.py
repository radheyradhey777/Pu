import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import asyncio
import json
import sqlite3
from typing import Optional, Union

# Define the path for the SQLite database
DB_PATH = "moderation.db"

class ModerationDatabase:
    """
    Manages all database interactions for moderation logs, warnings, and temporary punishments.
    Uses SQLite for persistent storage.
    """
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """
        Initializes the SQLite database by creating necessary tables if they don't exist.
        Tables include:
        - mod_logs: Records all moderation actions (kick, ban, mute, warn, etc.)
        - warnings: Stores active warnings for users.
        - temp_punishments: Tracks temporary mutes/bans with their expiration times.
        """
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
                duration INTEGER, -- Duration in seconds for temp punishments
                active BOOLEAN DEFAULT 1 -- For future use, e.g., to mark overturned actions
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
                active BOOLEAN DEFAULT 1 -- To mark warnings as dismissed/removed
            )
        ''')
        
        # Temporary punishments table (mutes, temp bans)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS temp_punishments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                punishment_type TEXT NOT NULL, -- e.g., 'mute', 'temp_ban'
                expires_at DATETIME NOT NULL,
                active BOOLEAN DEFAULT 1 -- To mark if the punishment is still active
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def log_action(self, guild_id: int, user_id: int, moderator_id: int, action: str, reason: str = None, duration: int = None):
        """
        Logs a moderation action to the 'mod_logs' table.
        
        Args:
            guild_id (int): The ID of the guild where the action occurred.
            user_id (int): The ID of the user who was moderated.
            moderator_id (int): The ID of the moderator who performed the action.
            action (str): The type of moderation action (e.g., 'warn', 'mute', 'kick', 'ban').
            reason (str, optional): The reason for the moderation action. Defaults to None.
            duration (int, optional): Duration in seconds for temporary punishments. Defaults to None.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO mod_logs (guild_id, user_id, moderator_id, action, reason, duration)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (guild_id, user_id, moderator_id, action, reason, duration))
        conn.commit()
        conn.close()
    
    def add_warning(self, guild_id: int, user_id: int, moderator_id: int, reason: str):
        """
        Adds a warning entry to the 'warnings' table.
        
        Args:
            guild_id (int): The ID of the guild.
            user_id (int): The ID of the user who received the warning.
            moderator_id (int): The ID of the moderator who issued the warning.
            reason (str): The reason for the warning.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO warnings (guild_id, user_id, moderator_id, reason)
            VALUES (?, ?, ?, ?)
        ''', (guild_id, user_id, moderator_id, reason))
        conn.commit()
        conn.close()
    
    def get_warnings(self, guild_id: int, user_id: int):
        """
        Retrieves all active warnings for a specific user in a guild.
        
        Args:
            guild_id (int): The ID of the guild.
            user_id (int): The ID of the user.
            
        Returns:
            list: A list of warning records.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, guild_id, user_id, moderator_id, reason, timestamp, active FROM warnings 
            WHERE guild_id = ? AND user_id = ? AND active = 1
            ORDER BY timestamp DESC
        ''', (guild_id, user_id))
        warnings = cursor.fetchall()
        conn.close()
        return warnings
    
    def add_temp_punishment(self, guild_id: int, user_id: int, punishment_type: str, expires_at: datetime):
        """
        Adds a temporary punishment entry to the 'temp_punishments' table.
        
        Args:
            guild_id (int): The ID of the guild.
            user_id (int): The ID of the user.
            punishment_type (str): The type of punishment (e.g., 'mute').
            expires_at (datetime): The UTC datetime when the punishment expires.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO temp_punishments (guild_id, user_id, punishment_type, expires_at)
            VALUES (?, ?, ?, ?)
        ''', (guild_id, user_id, punishment_type, expires_at.isoformat()))
        conn.commit()
        conn.close()
    
    def remove_temp_punishment(self, guild_id: int, user_id: int, punishment_type: str):
        """
        Marks a temporary punishment as inactive in the database.
        
        Args:
            guild_id (int): The ID of the guild.
            user_id (int): The ID of the user.
            punishment_type (str): The type of punishment to remove (e.g., 'mute').
        """
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
        """
        Retrieves all currently active temporary punishments from the database.
        
        Returns:
            list: A list of active temporary punishment records.
        """
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
    """
    A Discord.py cog for moderation commands.
    Includes commands for warning, muting, kicking, banning, and viewing logs.
    """
    def __init__(self, bot):
        self.bot = bot
        self.db = ModerationDatabase(db_path=DB_PATH)
        # Create a background task to check for expired temporary punishments
        self.bot.loop.create_task(self.check_temp_punishments())

    async def check_permissions(self, interaction: discord.Interaction, target: discord.Member = None):
        """
        Checks if the interacting user has the necessary permissions to perform moderation
        and if they can moderate the target member based on role hierarchy.
        
        Args:
            interaction (discord.Interaction): The interaction object.
            target (discord.Member, optional): The member being targeted. Defaults to None.
            
        Returns:
            bool: True if permissions are sufficient, False otherwise.
        """
        # Check if the user has 'manage_roles' permission (a common moderation permission)
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return False
        
        # If a target member is provided, check role hierarchy
        if target:
            # Cannot moderate someone with an equal or higher role, unless the moderator is the guild owner
            if target.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
                await interaction.response.send_message("❌ You cannot moderate someone with an equal or higher role.", ephemeral=True)
                return False
            
            # Cannot moderate the server owner
            if target == interaction.guild.owner:
                await interaction.response.send_message("❌ You cannot moderate the server owner.", ephemeral=True)
                return False
        
        return True

    def parse_duration(self, duration_str: str) -> datetime:
        """
        Parses a duration string (e.g., "10m", "1h", "2d") into a datetime object
        representing the expiration time from now (UTC).
        
        Args:
            duration_str (str): The duration string.
            
        Returns:
            datetime: The calculated expiration datetime.
            
        Raises:
            ValueError: If the duration string format is invalid.
        """
        # Ensure duration_str is not empty
        if not duration_str:
            raise ValueError("Duration string cannot be empty.")

        unit = duration_str[-1].lower()
        try:
            value = int(duration_str[:-1])
        except ValueError:
            raise ValueError("Invalid duration value. Please provide a number.")
        
        if unit == 'm':
            return datetime.utcnow() + timedelta(minutes=value)
        elif unit == 'h':
            return datetime.utcnow() + timedelta(hours=value)
        elif unit == 'd':
            return datetime.utcnow() + timedelta(days=value)
        else:
            raise ValueError("Invalid duration unit. Use 'm' for minutes, 'h' for hours, or 'd' for days.")

    async def get_or_create_mute_role(self, guild: discord.Guild) -> Optional[discord.Role]:
        """
        Gets the existing "Muted" role in a guild, or creates it if it doesn't exist.
        Sets up channel permissions for the mute role to prevent sending messages/speaking.
        
        Args:
            guild (discord.Guild): The guild to get/create the mute role for.
            
        Returns:
            Optional[discord.Role]: The mute role, or None if creation failed due to permissions.
        """
        mute_role = discord.utils.get(guild.roles, name="Muted")
        
        if not mute_role:
            try:
                # Create the mute role
                mute_role = await guild.create_role(
                    name="Muted",
                    color=discord.Color.dark_gray(),
                    reason="Auto-created mute role for moderation"
                )
                
                # Set permissions for all existing channels to deny sending messages/speaking
                for channel in guild.channels:
                    try:
                        if isinstance(channel, discord.TextChannel):
                            await channel.set_permissions(mute_role, send_messages=False, add_reactions=False, speak=False)
                        elif isinstance(channel, discord.VoiceChannel):
                            await channel.set_permissions(mute_role, speak=False, connect=False)
                        elif isinstance(channel, discord.StageChannel):
                            await channel.set_permissions(mute_role, speak=False, request_to_speak=False)
                    except discord.Forbidden:
                        # Bot doesn't have permissions for this specific channel, skip it
                        print(f"Warning: Could not set permissions for mute role in channel {channel.name} (ID: {channel.id}) due to missing permissions.")
                        continue
                
                print(f"Created mute role '{mute_role.name}' in guild '{guild.name}' (ID: {guild.id})")
                        
            except discord.Forbidden:
                # Bot doesn't have 'manage_roles' permission at the guild level
                print(f"Error: Bot lacks 'Manage Roles' permission to create mute role in guild '{guild.name}' (ID: {guild.id})")
                return None
            except Exception as e:
                print(f"An unexpected error occurred while creating mute role: {e}")
                return None
                
        return mute_role

    async def schedule_unmute(self, member: discord.Member, mute_role: discord.Role, unmute_time: datetime):
        """
        Schedules the unmuting of a member at a specific time. This is run as an asyncio task.
        
        Args:
            member (discord.Member): The member to unmute.
            mute_role (discord.Role): The mute role to remove.
            unmute_time (datetime): The UTC datetime when the unmute should occur.
        """
        # Wait until the specified unmute time
        await discord.utils.sleep_until(unmute_time)
        
        # Check if the member is still in the guild and still has the mute role
        if member.guild.get_member(member.id) and mute_role in member.roles:
            try:
                await member.remove_roles(mute_role, reason="Automatic unmute")
                # Remove the temporary punishment record from the database
                self.db.remove_temp_punishment(member.guild.id, member.id, "mute")
                # Log the automatic unmute action
                self.db.log_action(member.guild.id, member.id, self.bot.user.id, "unmute", "Automatic unmute", 0) # Bot as moderator
                
                print(f"Automatically unmuted {member.display_name} (ID: {member.id}) in {member.guild.name} (ID: {member.guild.id})")
            except discord.Forbidden:
                print(f"Failed to automatically unmute {member.display_name} (ID: {member.id}) in {member.guild.name} (Missing Permissions)")
            except Exception as e:
                print(f"Error during automatic unmute for {member.display_name} (ID: {member.id}): {e}")
        else:
            # If member left or mute role was already removed, just clean up the DB record
            self.db.remove_temp_punishment(member.guild.id, member.id, "mute")
            print(f"Cleaned up mute record for {member.display_name} (ID: {member.id}) as they are no longer muted or in guild.")


    async def check_temp_punishments(self):
        """
        A background task that periodically checks for expired temporary punishments
        (like mutes) and lifts them. Runs every 60 seconds.
        """
        await self.bot.wait_until_ready() # Wait until the bot is ready
        while not self.bot.is_closed(): # Keep running while the bot is online
            punishments = self.db.get_active_temp_punishments()
            now = datetime.utcnow() # Get current UTC time

            for guild_id, user_id, punishment_type, expires_at_str in punishments:
                try:
                    expires_at = datetime.fromisoformat(expires_at_str)
                except ValueError:
                    print(f"Warning: Invalid datetime format for punishment {user_id} in guild {guild_id}. Removing record.")
                    self.db.remove_temp_punishment(guild_id, user_id, punishment_type)
                    continue

                if now >= expires_at:
                    guild = self.bot.get_guild(guild_id)
                    if not guild:
                        # Guild not found, remove the punishment record from DB
                        self.db.remove_temp_punishment(guild_id, user_id, punishment_type)
                        print(f"Removed expired punishment record for user {user_id} (guild {guild_id}): Guild not found.")
                        continue
                    
                    member = guild.get_member(user_id)
                    if not member:
                        # Member not found in guild, remove the punishment record from DB
                        self.db.remove_temp_punishment(guild_id, user_id, punishment_type)
                        print(f"Removed expired punishment record for user {user_id} (guild {guild_id}): Member not found in guild.")
                        continue

                    if punishment_type == "mute":
                        mute_role = discord.utils.get(guild.roles, name="Muted")
                        # Only attempt to unmute if the role exists and the member actually has it
                        if mute_role and mute_role in member.roles:
                            # Re-use schedule_unmute logic for consistency and error handling
                            await self.schedule_unmute(member, mute_role, expires_at) 
                        else:
                            # If they are not muted, but a record exists, clean it up
                            self.db.remove_temp_punishment(guild_id, user_id, punishment_type)
                            print(f"Cleaned up mute record for {member.display_name} (ID: {member.id}) as they were not muted.")
                    # Add other punishment types (e.g., temp ban) here if implemented
            
            await asyncio.sleep(60) # Check every 60 seconds

    # --- Moderation Commands ---

    @app_commands.command(name="warn", description="Warn a member")
    @app_commands.describe(member="Member to warn", reason="Reason for warning")
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        """
        Warns a member, logs the warning, and informs the member via DM if possible.
        """
        # Check permissions before proceeding
        if not await self.check_permissions(interaction, member):
            return
        
        # Add warning to database
        self.db.add_warning(interaction.guild.id, member.id, interaction.user.id, reason)
        self.db.log_action(interaction.guild.id, member.id, interaction.user.id, "warn", reason)
        
        # Get total active warnings for the member
        warnings = self.db.get_warnings(interaction.guild.id, member.id)
        warning_count = len(warnings)
        
        # Create and send embed response to the channel
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
        
        # Try to DM the warned user
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
            # User has DMs disabled
            pass
        except Exception as e:
            print(f"Error sending DM to {member.display_name} for warning: {e}")

    @app_commands.command(name="warnings", description="View warnings for a member")
    @app_commands.describe(member="Member to check warnings for")
    async def warnings(self, interaction: discord.Interaction, member: discord.Member):
        """
        Displays a list of active warnings for a specified member.
        Requires 'manage_messages' permission to view.
        """
        # Check if the user has permission to view warnings
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You don't have permission to view warnings.", ephemeral=True)
            return
        
        warnings = self.db.get_warnings(interaction.guild.id, member.id)
        
        if not warnings:
            await interaction.response.send_message(f"✅ {member.mention} has no active warnings.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"⚠️ Active Warnings for {member.display_name}",
            color=discord.Color.yellow(),
            timestamp=datetime.utcnow()
        )
        
        # Iterate through warnings and add them as fields to the embed
        # Limiting to 10 for readability, and showing newest first (due to ORDER BY DESC)
        for i, warning in enumerate(warnings[:10], 1): 
            # warning structure: (id, guild_id, user_id, moderator_id, reason, timestamp, active)
            moderator = self.bot.get_user(warning[3]) # Get moderator user object
            mod_name = moderator.display_name if moderator else f"ID: {warning[3]}" # Fallback if mod not found
            
            # Convert ISO format timestamp from DB to datetime object
            try:
                timestamp = datetime.fromisoformat(warning[5])
            except ValueError:
                timestamp = datetime.utcnow() # Fallback to current time if parsing fails
            
            embed.add_field(
                name=f"Warning #{i}",
                value=f"**Moderator:** {mod_name}\n**Reason:** {warning[4]}\n**Date:** <t:{int(timestamp.timestamp())}:F> (<t:{int(timestamp.timestamp())}:R>)",
                inline=False
            )
        
        if len(warnings) > 10:
            embed.set_footer(text=f"Showing latest 10 of {len(warnings)} active warnings")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="mute", description="Mute a member")
    @app_commands.describe(
        member="Member to mute", 
        reason="Reason for mute",
        duration="Duration (e.g., 10m, 1h, 2d)"
    )
    async def mute(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided", duration: str = None):
        """
        Mutes a member by applying a 'Muted' role. Can be temporary with a specified duration.
        """
        if not await self.check_permissions(interaction, member):
            return
        
        # Get or create the mute role
        mute_role = await self.get_or_create_mute_role(interaction.guild)
        if not mute_role:
            await interaction.response.send_message("❌ I don't have permission to create or manage the mute role. Please ensure I have 'Manage Roles' permission.", ephemeral=True)
            return
        
        # Check if member is already muted
        if mute_role in member.roles:
            await interaction.response.send_message(f"❌ {member.mention} is already muted.", ephemeral=True)
            return
        
        try:
            unmute_time = None
            duration_seconds = None
            
            # Parse duration if provided
            if duration:
                try:
                    unmute_time = self.parse_duration(duration)
                    duration_seconds = int((unmute_time - datetime.utcnow()).total_seconds())
                except ValueError as e:
                    await interaction.response.send_message(f"❌ Invalid duration format: {e}. Use formats like: 10m, 1h, 2d", ephemeral=True)
                    return
            
            # Add the mute role to the member
            await member.add_roles(mute_role, reason=f"Muted by {interaction.user.display_name} | {reason}")
            
            # Log the mute action to the database
            self.db.log_action(interaction.guild.id, member.id, interaction.user.id, "mute", reason, duration_seconds)
            
            # If it's a temporary mute, add to temp_punishments and schedule unmute
            if unmute_time:
                self.db.add_temp_punishment(interaction.guild.id, member.id, "mute", unmute_time)
                # Schedule the unmute as a background task
                asyncio.create_task(self.schedule_unmute(member, mute_role, unmute_time))
            
            # Create and send embed response
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
            
            # Try to DM the muted user
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
                pass # User has DMs disabled
                
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to mute this member. Please check my role hierarchy.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An unexpected error occurred during mute: {e}", ephemeral=True)

    @app_commands.command(name="unmute", description="Unmute a member")
    @app_commands.describe(member="Member to unmute", reason="Reason for unmute")
    async def unmute(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        """
        Unmutes a member by removing the 'Muted' role.
        """
        if not await self.check_permissions(interaction, member):
            return
        
        mute_role = discord.utils.get(interaction.guild.roles, name="Muted")
        
        # Check if the mute role exists and if the member actually has it
        if not mute_role or mute_role not in member.roles:
            await interaction.response.send_message(f"❌ {member.mention} is not currently muted or the 'Muted' role does not exist.", ephemeral=True)
            return
        
        try:
            # Remove the mute role from the member
            await member.remove_roles(mute_role, reason=f"Unmuted by {interaction.user.display_name} | {reason}")
            
            # Remove the temporary punishment record from the database
            self.db.remove_temp_punishment(interaction.guild.id, member.id, "mute")
            # Log the unmute action
            self.db.log_action(interaction.guild.id, member.id, interaction.user.id, "unmute", reason)
            
            # Create and send embed response
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
        except Exception as e:
            await interaction.response.send_message(f"An unexpected error occurred during unmute: {e}", ephemeral=True)

    @app_commands.command(name="timeout", description="Timeout a member (Discord's built-in timeout)")
    @app_commands.describe(
        member="Member to timeout",
        duration="Duration (e.g., 10m, 1h, 2d, max 28d)",
        reason="Reason for timeout"
    )
    async def timeout(self, interaction: discord.Interaction, member: discord.Member, duration: str, reason: str = "No reason provided"):
        """
        Applies Discord's built-in timeout to a member.
        Requires 'moderate_members' permission.
        """
        if not await self.check_permissions(interaction, member):
            return
        
        # Check for specific 'moderate_members' permission for timeout
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ You don't have permission to timeout members.", ephemeral=True)
            return
        
        timeout_until = None
        duration_seconds = None
        try:
            timeout_until = self.parse_duration(duration)
            max_timeout = datetime.utcnow() + timedelta(days=28) # Discord's maximum timeout duration
            
            if timeout_until > max_timeout:
                await interaction.response.send_message("❌ Timeout duration cannot exceed 28 days.", ephemeral=True)
                return
            duration_seconds = int((timeout_until - datetime.utcnow()).total_seconds())
                
        except ValueError as e:
            await interaction.response.send_message(f"❌ Invalid duration format: {e}. Use formats like: 10m, 1h, 2d", ephemeral=True)
            return
        
        try:
            # Check if member is already timed out
            if member.is_timed_out():
                await interaction.response.send_message(f"❌ {member.mention} is already timed out. Use `/untimeout` first if you wish to change their timeout.", ephemeral=True)
                return

            # Apply the timeout
            await member.timeout(timeout_until, reason=f"Timed out by {interaction.user.display_name} | {reason}")
            
            # Log the timeout action
            self.db.log_action(interaction.guild.id, member.id, interaction.user.id, "timeout", reason, duration_seconds)
            
            # Create and send embed response
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

            # Try to DM the timed out user
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
                pass # User has DMs disabled
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to timeout this member. Please check my role hierarchy and 'Moderate Members' permission.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An unexpected error occurred: {e}", ephemeral=True)


    @app_commands.command(name="untimeout", description="Remove timeout from a member")
    @app_commands.describe(member="Member to remove timeout from", reason="Reason for removing timeout")
    async def untimeout(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        """
        Removes Discord's built-in timeout from a member.
        Requires 'moderate_members' permission.
        """
        if not await self.check_permissions(interaction, member):
            return
        
        # Check for specific 'moderate_members' permission for timeout
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ You don't have permission to manage timeouts.", ephemeral=True)
            return
        
        # Check if the member is actually timed out
        if not member.is_timed_out():
            await interaction.response.send_message(f"❌ {member.mention} is not currently timed out.", ephemeral=True)
            return
        
        try:
            # Remove the timeout (by setting timeout_until to None)
            await member.timeout(None, reason=f"Timeout removed by {interaction.user.display_name} | {reason}")
            
            # Log the untimeout action
            self.db.log_action(interaction.guild.id, member.id, interaction.user.id, "untimeout", reason)
            
            # Create and send embed response
            embed = discord.Embed(
                title="⏰ Timeout Removed",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Member", value=member.mention, inline=True)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            
            await interaction.response.send_message(embed=embed)

            # Try to DM the user whose timeout was removed
            try:
                dm_embed = discord.Embed(
                    title=f"Your timeout was removed in {interaction.guild.name}",
                    color=discord.Color.green(),
                    timestamp=datetime.utcnow()
                )
                dm_embed.add_field(name="Reason", value=reason, inline=False)
                await member.send(embed=dm_embed)
            except discord.Forbidden:
                pass # User has DMs disabled
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to remove timeout from this member. Please check my role hierarchy and 'Moderate Members' permission.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An unexpected error occurred: {e}", ephemeral=True)

    @app_commands.command(name="kick", description="Kick a member")
    @app_commands.describe(member="Member to kick", reason="Reason for kick")
    async def kick(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        """
        Kicks a member from the guild.
        Requires 'kick_members' permission.
        """
        if not await self.check_permissions(interaction, member):
            return
        
        # Check for specific 'kick_members' permission
        if not interaction.user.guild_permissions.kick_members:
            await interaction.response.send_message("❌ You don't have permission to kick members.", ephemeral=True)
            return
        
        try:
            # Try to DM the member before kicking them (as they will no longer be in the guild)
            try:
                dm_embed = discord.Embed(
                    title=f"You were kicked from {interaction.guild.name}",
                    color=discord.Color.red(),
                    timestamp=datetime.utcnow()
                )
                dm_embed.add_field(name="Reason", value=reason, inline=False)
                await member.send(embed=dm_embed)
            except discord.Forbidden:
                pass # User has DMs disabled
            
            # Perform the kick
            await member.kick(reason=f"Kicked by {interaction.user.display_name} | {reason}")
            
            # Log the kick action
            self.db.log_action(interaction.guild.id, member.id, interaction.user.id, "kick", reason)
            
            # Create and send embed response
            embed = discord.Embed(
                title="👢 Member Kicked",
                color=discord.Color.red(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Member", value=f"{member.display_name} ({member.id})", inline=True)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            
            await interaction.response.send_message(embed=embed)
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to kick this member. Please check my role hierarchy.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An unexpected error occurred during kick: {e}", ephemeral=True)

    @app_commands.command(name="ban", description="Ban a member")
    @app_commands.describe(
        member="Member to ban", 
        reason="Reason for ban",
        delete_days="Days of messages to delete (0-7)"
    )
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided", delete_days: int = 0):
        """
        Bans a member from the guild, with an option to delete their recent messages.
        Requires 'ban_members' permission.
        """
        if not await self.check_permissions(interaction, member):
            return
        
        # Check for specific 'ban_members' permission
        if not interaction.user.guild_permissions.ban_members:
            await interaction.response.send_message("❌ You don't have permission to ban members.", ephemeral=True)
            return
        
        # Validate delete_days input
        if delete_days < 0 or delete_days > 7:
            await interaction.response.send_message("❌ Delete days must be between 0 and 7.", ephemeral=True)
            return
        
        try:
            # Try to DM the member before banning them
            try:
                dm_embed = discord.Embed(
                    title=f"You were banned from {interaction.guild.name}",
                    color=discord.Color.dark_red(),
                    timestamp=datetime.utcnow()
                )
                dm_embed.add_field(name="Reason", value=reason, inline=False)
                await member.send(embed=dm_embed)
            except discord.Forbidden:
                pass # User has DMs disabled
            
            # Perform the ban
            await member.ban(reason=f"Banned by {interaction.user.display_name} | {reason}", delete_message_days=delete_days)
            
            # Log the ban action
            self.db.log_action(interaction.guild.id, member.id, interaction.user.id, "ban", reason)
            
            # Create and send embed response
            embed = discord.Embed(
                title="🔨 Member Banned",
                color=discord.Color.dark_red(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Member", value=f"{member.display_name} ({member.id})", inline=True)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            if delete_days > 0:
                embed.add_field(name="Messages Deleted", value=f"{delete_days} days", inline=True)
            
            await interaction.response.send_message(embed=embed)
            
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to ban this member. Please check my role hierarchy.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An unexpected error occurred during ban: {e}", ephemeral=True)

    @app_commands.command(name="unban", description="Unban a user")
    @app_commands.describe(user_id="User ID to unban", reason="Reason for unban")
    async def unban(self, interaction: discord.Interaction, user_id: str, reason: str = "No reason provided"):
        """
        Unbans a user from the guild using their user ID.
        Requires 'ban_members' permission.
        """
        # Check for specific 'ban_members' permission
        if not interaction.user.guild_permissions.ban_members:
            await interaction.response.send_message("❌ You don't have permission to unban members.", ephemeral=True)
            return
        
        # Validate user_id input
        try:
            user_id_int = int(user_id)
        except ValueError:
            await interaction.response.send_message("❌ Invalid user ID. Please provide a numerical user ID.", ephemeral=True)
            return
        
        try:
            # Fetch the user object (even if they are not in the guild)
            user = await self.bot.fetch_user(user_id_int)
            # Perform the unban
            await interaction.guild.unban(user, reason=f"Unbanned by {interaction.user.display_name} | {reason}")
            
            # Log the unban action
            self.db.log_action(interaction.guild.id, user_id_int, interaction.user.id, "unban", reason)
            
            # Create and send embed response
            embed = discord.Embed(
                title="🔓 User Unbanned",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="User", value=f"{user.display_name} ({user.id})", inline=True)
            embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            
            await interaction.response.send_message(embed=embed)
            
        except discord.NotFound:
            await interaction.response.send_message("❌ User not found in ban list or not banned.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to unban users.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An unexpected error occurred during unban: {e}", ephemeral=True)

    @app_commands.command(name="modlogs", description="View moderation logs for a user")
    @app_commands.describe(member="Member to view logs for", limit="Number of logs to show (default 10)")
    async def modlogs(self, interaction: discord.Interaction, member: discord.Member, limit: int = 10):
        """
        Displays recent moderation logs for a specified member.
        Requires 'manage_messages' permission to view.
        """
        # Check if the user has permission to view moderation logs
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You don't have permission to view moderation logs.", ephemeral=True)
            return
        
        # Validate limit input
        if limit < 1 or limit > 25:
            limit = 10 # Default to 10 if invalid limit is provided
        
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
            action, reason, timestamp_str, moderator_id, duration = log
            moderator = self.bot.get_user(moderator_id)
            mod_name = moderator.display_name if moderator else f"ID: {moderator_id}"
            
            # Parse timestamp from string to datetime object
            try:
                log_time = datetime.fromisoformat(timestamp_str)
                time_str = f"<t:{int(log_time.timestamp())}:F> (<t:{int(log_time.timestamp())}:R>)"
            except ValueError:
                time_str = timestamp_str # Fallback if parsing fails
            
            log_detail = f"**Moderator:** {mod_name}\n**Reason:** {reason or 'No reason provided'}"
            
            # Add duration detail for temporary punishments
            if duration is not None and action in ["mute", "timeout"]:
                if duration < 60:
                    duration_human_readable = f"{duration} seconds"
                elif duration < 3600:
                    duration_human_readable = f"{round(duration/60)} minutes"
                elif duration < 86400:
                    duration_human_readable = f"{round(duration/3600)} hours"
                else:
                    duration_human_readable = f"{round(duration/86400)} days"
                log_detail += f"\n**Duration:** {duration_human_readable}"

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
        """
        Deletes a specified number of messages from the current channel.
        Can optionally filter messages by a specific member.
        Requires 'manage_messages' permission.
        """
        # Check for specific 'manage_messages' permission
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You don't have permission to manage messages.", ephemeral=True)
            return
        
        # Validate amount input
        if amount < 1 or amount > 100:
            await interaction.response.send_message("❌ Amount must be between 1 and 100.", ephemeral=True)
            return
        
        # Defer the response as purge can take some time
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Define a check function for purging messages
            def check(message):
                # Do not delete pinned messages by default
                if message.pinned:
                    return False
                # If a member is specified, only delete their messages
                if member:
                    return message.author == member
                return True # Delete all messages if no member is specified
            
            # Perform the purge operation
            deleted = await interaction.channel.purge(limit=amount, check=check)
            
            # Log the purge action
            # If `member` is None, use a placeholder ID (e.g., 0) to denote "all users"
            target_user_id = member.id if member else 0 
            self.db.log_action(
                interaction.guild.id, 
                target_user_id, 
                interaction.user.id, 
                "purge", 
                f"Deleted {len(deleted)} messages" + (f" from {member.display_name}" if member else "")
            )
            
            # Create and send embed response
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


    # --- Utility Commands ---

    @app_commands.command(name="serverinfo", description="Shows server information")
    async def serverinfo(self, interaction: discord.Interaction):
        """
        Displays detailed information about the current Discord guild (server).
        """
        guild = interaction.guild
        
        # Calculate member statistics
        total_members = guild.member_count
        humans = len([m for m in guild.members if not m.bot])
        bots = total_members - humans
        
        # Get online members (excluding bots)
        online_members = [m for m in guild.members if m.status != discord.Status.offline and not m.bot]
        online_count = len(online_members)

        # Get server creation date
        created_at = guild.created_at

        # Map Discord's VerificationLevel enum to human-readable strings
        verification_levels = {
            discord.VerificationLevel.none: "None",
            discord.VerificationLevel.low: "Low (Must have a verified email)",
            discord.VerificationLevel.medium: "Medium (Must be registered on Discord for >5 minutes)",
            discord.VerificationLevel.high: "High (Must be a member of the server for >10 minutes)",
            discord.VerificationLevel.extreme: "Extreme (Must have a verified phone on their Discord account)"
        }
        verification_level = verification_levels.get(guild.verification_level, "Unknown")

        # Format guild features (e.g., 'COMMUNITY', 'VERIFIED')
        features = ", ".join([f.replace('_', ' ').title() for f in guild.features]) if guild.features else "None"

        # Create and send embed response
        embed = discord.Embed(
            title=f"🌐 Server Info: {guild.name}",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        # Set server icon as thumbnail if available
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        embed.add_field(name="🆔 Server ID", value=guild.id, inline=True)
        embed.add_field(name="👑 Owner", value=guild.owner.mention, inline=True)
        # Use Discord's timestamp formatting for relative and absolute times
        embed.add_field(name="📅 Created On", value=f"<t:{int(created_at.timestamp())}:F> (<t:{int(created_at.timestamp())}:R>)", inline=False)
        embed.add_field(name="👥 Members", value=f"Total: {total_members}\nHumans: {humans}\nBots: {bots}", inline=True)
        embed.add_field(name="🟢 Online Members", value=online_count, inline=True)
        embed.add_field(name="💬 Channels", value=f"Text: {len(guild.text_channels)}\nVoice: {len(guild.voice_channels)}\nCategories: {len(guild.categories)}", inline=True)
        embed.add_field(name="🎭 Roles", value=len(guild.roles), inline=True)
        embed.add_field(name="Verification Level", value=verification_level, inline=False)
        embed.add_field(name="🚀 Boosts", value=f"{guild.premium_subscription_count} (Level {guild.premium_tier})", inline=True)
        # Note: guild.region is deprecated in newer Discord API versions, but included for compatibility
        embed.add_field(name="Region", value=str(guild.region).replace('-', ' ').title(), inline=True) 
        if features != "None": # Only show features field if there are any
            embed.add_field(name="Features", value=features, inline=False)

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    """
    Sets up the Moderation cog by adding it to the bot.
    This function is called by the bot when loading the cog.
    """
    await bot.add_cog(Moderation(bot))
