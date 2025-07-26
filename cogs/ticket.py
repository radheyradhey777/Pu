import discord
from discord.ext import commands
from discord import app_commands

class TicketCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ticket", description="Setup ticket panel")
    @app_commands.describe(
        panel_channel="Channel to send the ticket panel",
        category="Category to create ticket channels in",
        log_channel="Channel to log ticket creations",
        title="Embed title",
        description="Embed description",
        image_url="Optional image URL",
        button1="First button label",
        button2="Second button label",
        button3="Third button label",
        button4="Fourth button label"
    )
    async def ticket_setup(
        self,
        interaction: discord.Interaction,
        panel_channel: discord.TextChannel,
        category: discord.CategoryChannel,
        log_channel: discord.TextChannel,
        title: str,
        description: str,
        image_url: str = None,
        button1: str = None,
        button2: str = None,
        button3: str = None,
        button4: str = None,
    ):
        embed = discord.Embed(title=title, description=description, color=discord.Color.blue())
        if image_url:
            embed.set_image(url=image_url)

        view = TicketView(category.id, log_channel.id)
        for label in [button1, button2, button3, button4]:
            if label:
                view.add_item(TicketButton(label=label, category_id=category.id, log_channel_id=log_channel.id))

        await panel_channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Ticket panel sent successfully.", ephemeral=True)


class TicketView(discord.ui.View):
    def __init__(self, category_id, log_channel_id):
        super().__init__(timeout=None)
        self.category_id = category_id
        self.log_channel_id = log_channel_id


class TicketButton(discord.ui.Button):
    def __init__(self, label, category_id, log_channel_id):
        super().__init__(label=label, style=discord.ButtonStyle.green)
        self.label = label
        self.category_id = category_id
        self.log_channel_id = log_channel_id

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        category = guild.get_channel(self.category_id)
        log_channel = guild.get_channel(self.log_channel_id)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }

        channel_name = f"{self.label.lower().replace(' ', '-')}-{interaction.user.name}"
        ticket_channel = await guild.create_text_channel(
            name=channel_name[:90],
            overwrites=overwrites,
            category=category,
            topic=f"Ticket opened by {interaction.user} via {self.label}"
        )

        await ticket_channel.send(f"{interaction.user.mention}, your **{self.label}** ticket is open. Please wait for a staff member.")
        await interaction.response.send_message(f"🎟️ Ticket created: {ticket_channel.mention}", ephemeral=True)

        if log_channel:
            await log_channel.send(f"📨 {interaction.user.mention} opened a **{self.label}** ticket in {ticket_channel.mention}.")

async def setup(bot):
    await bot.add_cog(TicketCog(bot))
