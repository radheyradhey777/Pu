import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import asyncio
from typing import Optional

class Moderation(commands.Cog):
    """
    A Discord.py cog for moderation commands.
    This version uses in-memory storage for warnings and relies on Discord's
    native timeout for temporary punishments. Data is NOT persistent across restarts.
    """

    def __init__(self, bot):
        self.bot = bot
        self.warnings_cache = {}

    async def check_permissions(self, interaction: discord.Interaction, target: discord.Member = None):
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return False

        if target:
            if target.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
                await interaction.response.send_message("❌ You cannot moderate someone with an equal or higher role.", ephemeral=True)
                return False
            if target == interaction.guild.owner:
                await interaction.response.send_message("❌ You cannot moderate the server owner.", ephemeral=True)
                return False
        return True

    def parse_duration(self, duration_str: str) -> datetime:
        if not duration_str:
            raise ValueError("Duration string cannot be empty.")
        unit = duration_str[-1].lower()
        try:
            value = int(duration_str[:-1])
        except ValueError:
            raise ValueError("Invalid duration value.")
        if unit == 'm':
            return datetime.utcnow() + timedelta(minutes=value)
        elif unit == 'h':
            return datetime.utcnow() + timedelta(hours=value)
        elif unit == 'd':
            return datetime.utcnow() + timedelta(days=value)
        else:
            raise ValueError("Invalid duration unit. Use 'm', 'h', or 'd'.")

    async def get_or_create_mute_role(self, guild: discord.Guild) -> Optional[discord.Role]:
        mute_role = discord.utils.get(guild.roles, name="Muted")
        if not mute_role:
            try:
                mute_role = await guild.create_role(name="Muted", color=discord.Color.dark_gray(), reason="Auto-created mute role")
                for channel in guild.channels:
                    try:
                        if isinstance(channel, discord.TextChannel):
                            await channel.set_permissions(mute_role, send_messages=False, add_reactions=False)
                        elif isinstance(channel, discord.VoiceChannel):
                            await channel.set_permissions(mute_role, speak=False, connect=False)
                        elif isinstance(channel, discord.StageChannel):
                            await channel.set_permissions(mute_role, speak=False, request_to_speak=False)
                    except discord.Forbidden:
                        continue
            except discord.Forbidden:
                return None
            except Exception:
                return None
        return mute_role

    # --- Moderation Commands ---

    @app_commands.command(name="warn", description="Warn a member")
    async def warn(self, interaction: discord.Interaction, member: discord.Member, reason: str):
        if not await self.check_permissions(interaction, member):
            return
        key = (interaction.guild.id, member.id)
        self.warnings_cache.setdefault(key, []).append({
            "moderator_id": interaction.user.id,
            "reason": reason,
            "timestamp": datetime.utcnow()
        })
        warning_count = len(self.warnings_cache[key])
        embed = discord.Embed(title="⚠️ Member Warned", color=discord.Color.yellow(), timestamp=datetime.utcnow())
        embed.add_field(name="Member", value=member.mention)
        embed.add_field(name="Moderator", value=interaction.user.mention)
        embed.add_field(name="Warnings", value=warning_count)
        embed.add_field(name="Reason", value=reason, inline=False)
        await interaction.response.send_message(embed=embed)
        try:
            dm = discord.Embed(
                title=f"You were warned in {interaction.guild.name}",
                color=discord.Color.yellow(),
                timestamp=datetime.utcnow()
            )
            dm.add_field(name="Reason", value=reason)
            dm.add_field(name="Warnings", value=warning_count)
            await member.send(embed=dm)
        except discord.Forbidden:
            pass

    @app_commands.command(name="warnings", description="View warnings for a member")
    async def warnings(self, interaction: discord.Interaction, member: discord.Member):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You don't have permission.", ephemeral=True)
            return
        key = (interaction.guild.id, member.id)
        warnings = self.warnings_cache.get(key, [])
        if not warnings:
            await interaction.response.send_message(f"{member.mention} has no warnings.", ephemeral=True)
            return
        embed = discord.Embed(title=f"Warnings for {member}", color=discord.Color.yellow(), timestamp=datetime.utcnow())
        for i, w in enumerate(reversed(warnings[-10:]), 1):
            mod = self.bot.get_user(w["moderator_id"])
            embed.add_field(
                name=f"Warning #{i}",
                value=f"**By:** {mod.display_name if mod else 'Unknown'}\n**Reason:** {w['reason']}\n**Time:** <t:{int(w['timestamp'].timestamp())}:F>",
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="mute", description="Mute a member")
    async def mute(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason", duration: str = None):
        if not await self.check_permissions(interaction, member): return
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ You lack timeout permission.", ephemeral=True)
            return
        mute_role = await self.get_or_create_mute_role(interaction.guild)
        if not mute_role:
            await interaction.response.send_message("❌ Cannot manage mute role.", ephemeral=True)
            return
        timeout_until = None
        if duration:
            try:
                timeout_until = self.parse_duration(duration)
                if timeout_until > datetime.utcnow() + timedelta(days=28):
                    await interaction.response.send_message("❌ Duration exceeds 28 days.", ephemeral=True)
                    return
            except ValueError as e:
                await interaction.response.send_message(f"❌ {e}", ephemeral=True)
                return
        if member.is_timed_out() or (mute_role in member.roles):
            await interaction.response.send_message("❌ Member already muted.", ephemeral=True)
            return
        try:
            await member.timeout(timeout_until, reason=reason)
            if mute_role not in member.roles:
                await member.add_roles(mute_role, reason=reason)
            embed = discord.Embed(title="🔇 Member Muted", color=discord.Color.orange(), timestamp=datetime.utcnow())
            embed.add_field(name="Member", value=member.mention)
            embed.add_field(name="Moderator", value=interaction.user.mention)
            embed.add_field(name="Reason", value=reason, inline=False)
            if timeout_until:
                embed.add_field(name="Duration", value=duration)
                embed.add_field(name="Unmute", value=f"<t:{int(timeout_until.timestamp())}:F>")
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Cannot mute this member.", ephemeral=True)

    @app_commands.command(name="unmute", description="Unmute a member")
    async def unmute(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason"):
        if not await self.check_permissions(interaction, member): return
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message("❌ You lack permission.", ephemeral=True)
            return
        mute_role = discord.utils.get(interaction.guild.roles, name="Muted")
        if not member.is_timed_out() and (not mute_role or mute_role not in member.roles):
            await interaction.response.send_message("❌ Member is not muted.", ephemeral=True)
            return
        try:
            if member.is_timed_out():
                await member.timeout(None, reason=reason)
            if mute_role and mute_role in member.roles:
                await member.remove_roles(mute_role, reason=reason)
            embed = discord.Embed(title="🔊 Member Unmuted", color=discord.Color.green(), timestamp=datetime.utcnow())
            embed.add_field(name="Member", value=member.mention)
            embed.add_field(name="Moderator", value=interaction.user.mention)
            embed.add_field(name="Reason", value=reason, inline=False)
            await interaction.response.send_message(embed=embed)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Cannot unmute this member.", ephemeral=True)

    # Additional commands like kick, ban, timeout, unban, etc., can be added below similarly.

    # --- Utility Commands ---

    @app_commands.command(name="serverinfo", description="Shows server information")
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        total = guild.member_count
        humans = len([m for m in guild.members if not m.bot])
        bots = total - humans
        embed = discord.Embed(
            title=f"🌐 Server Info: {guild.name}",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        embed.add_field(name="Owner", value=guild.owner.mention)
        embed.add_field(name="Members", value=f"Humans: {humans}, Bots: {bots}")
        embed.add_field(name="Created", value=f"<t:{int(guild.created_at.timestamp())}:F>")
        embed.add_field(name="Boosts", value=f"{guild.premium_subscription_count} (Level {guild.premium_tier})")
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Moderation(bot))
