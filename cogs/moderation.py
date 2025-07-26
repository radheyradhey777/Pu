from discord.ext import commands
from discord import app_commands
import discord

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="mute", description="Mute a member")
    @app_commands.describe(member="Member to mute", reason="Reason for mute")
    async def mute(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        mute_role = discord.utils.get(interaction.guild.roles, name="Muted")
        if not mute_role:
            mute_role = await interaction.guild.create_role(name="Muted")
            for channel in interaction.guild.channels:
                await channel.set_permissions(mute_role, send_messages=False, speak=False)
        
        await member.add_roles(mute_role, reason=reason)
        await interaction.response.send_message(f"{member.mention} has been muted. Reason: {reason}", ephemeral=True)

    @app_commands.command(name="serverinfo", description="Shows server info")
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        embed = discord.Embed(title="Server Info", color=0x00ffcc)
        embed.add_field(name="Server Name", value=guild.name, inline=True)
        embed.add_field(name="Members", value=guild.member_count, inline=True)
        embed.add_field(name="Created At", value=guild.created_at.strftime("%Y-%m-%d"), inline=False)
        embed.set_thumbnail(url=guild.icon.url if guild.icon else discord.Embed.Empty)
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Moderation(bot))
