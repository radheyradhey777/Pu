from discord.ext import commands
from discord import app_commands
import discord
from datetime import datetime, timedelta
import asyncio

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def check_permissions(self, interaction: discord.Interaction, target: discord.Member = None):
        """Check if user has moderation permissions and can target the member"""
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return False
        
        if target and target.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            await interaction.response.send_message("❌ You cannot moderate someone with equal or higher role.", ephemeral=True)
            return False
        
        return True

    @app_commands.command(name="mute", description="Mute a member")
    @app_commands.describe(
        member="Member to mute", 
        reason="Reason for mute",
        duration="Duration (e.g., 10m, 1h, 2d)"
    )
    async def mute(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided", duration: str = None):
        # Permission check
        if not await self.check_permissions(interaction, member):
            return
        
        # Check if member is already muted
        mute_role = discord.utils.get(interaction.guild.roles, name="Muted")
        if mute_role and mute_role in member.roles:
            await interaction.response.send_message(f"❌ {member.mention} is already muted.", ephemeral=True)
            return
        
        # Create mute role if it doesn't exist
        if not mute_role:
            try:
                mute_role = await interaction.guild.create_role(
                    name="Muted",
                    color=discord.Color.dark_gray(),
                    reason="Auto-created mute role"
                )
                
                # Set permissions for all channels
                for channel in interaction.guild.channels:
                    try:
                        if isinstance(channel, discord.TextChannel):
                            await channel.set_permissions(mute_role, send_messages=False, add_reactions=False)
                        elif isinstance(channel, discord.VoiceChannel):
                            await channel.set_permissions(mute_role, speak=False)
                    except discord.Forbidden:
                        continue  # Skip channels we can't modify
                        
            except discord.Forbidden:
                await interaction.response.send_message("❌ I don't have permission to create roles.", ephemeral=True)
                return
        
        # Apply mute
        try:
            await member.add_roles(mute_role, reason=f"Muted by {interaction.user} | {reason}")
            
            # Parse duration if provided
            unmute_time = None
            if duration:
                try:
                    unmute_time = self.parse_duration(duration)
                except ValueError:
                    await interaction.response.send_message("❌ Invalid duration format. Use formats like: 10m, 1h, 2d", ephemeral=True)
                    return
            
            # Create response embed
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
                
                # Schedule unmute
                asyncio.create_task(self.schedule_unmute(member, mute_role, unmute_time))
            
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
                
                await member.send(embed=dm_embed)
            except discord.Forbidden:
                pass  # User has DMs disabled
                
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to mute this member.", ephemeral=True)

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
            await interaction.response.send_message("❌ I don't have permission to unmute this member.", ephemeral=True)

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
            await interaction.response.send_message("❌ I don't have permission to kick this member.", ephemeral=True)

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
            await interaction.response.send_message("❌ I don't have permission to ban this member.", ephemeral=True)

    @app_commands.command(name="serverinfo", description="Shows server information")
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        
        # Calculate member stats
        total_members = guild.member_count
        humans = len([m for m in guild.members if not m.bot])
        bots = total_members - humans
        
        # Create embed
        embed = discord.Embed(
            title=f"📊 {guild.name}",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        # Basic info
        embed.add_field(name="👑 Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
        embed.add_field(name="🆔 Server ID", value=guild.id, inline=True)
        embed.add_field(name="📅 Created", value=f"<t:{int(guild.created_at.timestamp())}:F>", inline=False)
        
        # Member stats
        embed.add_field(name="👥 Total Members", value=f"{total_members:,}", inline=True)
        embed.add_field(name="👤 Humans", value=f"{humans:,}", inline=True)
        embed.add_field(name="🤖 Bots", value=f"{bots:,}", inline=True)
        
        # Channel stats
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)
        
        embed.add_field(name="💬 Text Channels", value=text_channels, inline=True)
        embed.add_field(name="🔊 Voice Channels", value=voice_channels, inline=True)
        embed.add_field(name="📁 Categories", value=categories, inline=True)
        
        # Other stats
        embed.add_field(name="😀 Emojis", value=f"{len(guild.emojis)}/{guild.emoji_limit}", inline=True)
        embed.add_field(name="🎭 Roles", value=len(guild.roles), inline=True)
        embed.add_field(name="🚀 Boost Level", value=f"Level {guild.premium_tier} ({guild.premium_subscription_count} boosts)", inline=True)
        
        # Set thumbnail
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        # Set footer
        embed.set_footer(text="Server Information", icon_url=interaction.user.display_avatar.url)
        
        await interaction.response.send_message(embed=embed)

    def parse_duration(self, duration_str: str) -> datetime:
        """Parse duration string like '10m', '1h', '2d' into datetime"""
        duration_str = duration_str.lower().strip()
        
        time_units = {
            's': 1, 'sec': 1, 'second': 1, 'seconds': 1,
            'm': 60, 'min': 60, 'minute': 60, 'minutes': 60,
            'h': 3600, 'hr': 3600, 'hour': 3600, 'hours': 3600,
            'd': 86400, 'day': 86400, 'days': 86400,
            'w': 604800, 'week': 604800, 'weeks': 604800
        }
        
        # Find the unit
        unit = None
        for key in time_units:
            if duration_str.endswith(key):
                unit = key
                break
        
        if not unit:
            raise ValueError("Invalid duration format")
        
        # Extract the number
        try:
            number = int(duration_str[:-len(unit)])
        except ValueError:
            raise ValueError("Invalid duration format")
        
        if number <= 0:
            raise ValueError("Duration must be positive")
        
        # Calculate the future time
        seconds = number * time_units[unit]
        return datetime.utcnow() + timedelta(seconds=seconds)

    async def schedule_unmute(self, member: discord.Member, mute_role: discord.Role, unmute_time: datetime):
        """Schedule automatic unmute"""
        now = datetime.utcnow()
        if unmute_time <= now:
            return
        
        # Wait until unmute time
        await asyncio.sleep((unmute_time - now).total_seconds())
        
        # Check if member still has the mute role
        try:
            # Refresh member object
            member = await member.guild.fetch_member(member.id)
            if mute_role in member.roles:
                await member.remove_roles(mute_role, reason="Automatic unmute - duration expired")
        except (discord.NotFound, discord.Forbidden):
            pass  # Member left or bot lost permissions

async def setup(bot):
    await bot.add_cog(Moderation(bot))
