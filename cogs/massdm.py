import discord
from discord import app_commands
from discord.ext import commands

class MassDM(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="mdm", description="Send a DM to all members in the server")
    @app_commands.checks.has_permissions(administrator=True)
    async def mass_dm(self, interaction: discord.Interaction, message: str):
        await interaction.response.send_message("📨 Sending DMs... Please wait.", ephemeral=True)

        sent = 0
        failed = 0
        for member in interaction.guild.members:
            if member.bot:
                continue
            try:
                await member.send(message)
                sent += 1
            except:
                failed += 1

        await interaction.followup.send(f"✅ Sent: {sent} | ❌ Failed: {failed}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(MassDM(bot))
