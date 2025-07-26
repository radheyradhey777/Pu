from discord.ext import commands
from discord import app_commands, Embed
import discord

class Giveaway(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="giveaway", description="Create a giveaway")
    async def giveaway(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🎉 Giveaway!", description="React with 🎉 to join!", color=0x00ff00)
        embed.add_field(name="Prize", value="Mystery Gift", inline=False)
        embed.set_footer(text="Ends in 24h!")
        msg = await interaction.channel.send(embed=embed)
        await msg.add_reaction("🎉")
        await interaction.response.send_message("Giveaway created!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Giveaway(bot))
