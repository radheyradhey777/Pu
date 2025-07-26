import discord
from discord import app_commands
from discord.ext import commands

class EmbedCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="embed", description="Send an embed to a selected channel")
    @app_commands.describe(
        channel="Channel where the embed will be sent",
        title="Title of the embed",
        description="Description of the embed",
        image_url="Image URL to include (optional)"
    )
    async def embed(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        title: str,
        description: str,
        image_url: str = None
    ):
        embed = discord.Embed(title=title, description=description, color=discord.Color.blue())
        if image_url:
            embed.set_image(url=image_url)

        await channel.send(embed=embed)
        await interaction.response.send_message(f"✅ Embed sent to {channel.mention}", ephemeral=True)

    @commands.Cog.listener()
    async def on_ready(self):
        try:
            self.bot.tree.add_command(self.embed)
        except Exception as e:
            print(f"❌ Failed to add embed command: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(EmbedCog(bot))
