import discord
from discord import app_commands
from discord.ext import commands

class EmbedCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Slash command: /embed
    @app_commands.command(name="embed", description="Send an embed to a selected channel")
    @app_commands.describe(
        channel="Channel where the embed will be sent",
        title="Title of the embed",
        description="Description of the embed",
        image_url="Image URL to include (optional)"
    )
    @app_commands.checks.has_permissions(administrator=True)  # Restrict to administrators
    async def embed(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        title: str,
        description: str,
        image_url: str = None
    ):
        # Create embed
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.blue()
        )
        if image_url:
            embed.set_image(url=image_url)

        # Send embed to target channel
        await channel.send(embed=embed)

        # Confirm to user
        await interaction.response.send_message(
            f"✅ Embed sent to {channel.mention}",
            ephemeral=True
        )

    # Error handler for the embed command
    @embed.error
    async def embed_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message(
                "❌ You need **Administrator** permission to use this command.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ An error occurred while running the command.",
                ephemeral=True
            )
            print(f"Error in /embed command: {error}")

    # Sync command on bot ready
    @commands.Cog.listener()
    async def on_ready(self):
        try:
            self.bot.tree.add_command(self.embed)
            print("✅ Embed command loaded.")
        except Exception as e:
            print(f"❌ Failed to add embed command: {e}")

# Setup function to load the cog
async def setup(bot: commands.Bot):
    await bot.add_cog(EmbedCog(bot))
