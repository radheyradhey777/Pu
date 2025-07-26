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
        embed = discord.Embed(title=title, description=description, color=discord.Color.blurple())
        if image_url:
            embed.set_image(url=image_url)

        view = TicketView(category.id, log_channel.id)
        for label in [button1, button2, button3, button4]:
            if label:
                # Check for emoji in label (format: "🔧 Support")
                parts = label.strip().split(" ", 1)
                if len(parts) == 2 and parts[0].startswith("<") or parts[0].isemoji():
                    emoji, label_text = parts
                else:
                    emoji, label_text = None, label
                view.add_item(TicketButton(label=label_text, emoji=emoji, category_id=category.id, log_channel_id=log_channel.id))

        await panel_channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Ticket panel sent successfully.", ephemeral=True)


class TicketView(discord.ui.View):
    def __init__(self, category_id, log_channel_id):
        super().__init__(timeout=None)
        self.category_id = category_id
        self.log_channel_id = log_channel_id


class TicketButton(discord.ui.Button):
    def __init__(self, label, category_id, log_channel_id, emoji=None):
        super().__init__(label=label, style=discord.ButtonStyle.green, emoji=emoji)
        self.label = label
        self.emoji = emoji
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

        channel_name = f"{self.label.lower().replace(' ', '-')}-{interaction.user.name}".replace("🔧", "").strip()
        ticket_channel = await guild.create_text_channel(
            name=channel_name[:90],
            overwrites=overwrites,
            category=category,
            topic=f"Ticket opened by {interaction.user} via {self.label}"
        )

        # Add Claim & Close buttons inside the ticket
        view = TicketManagementView(ticket_channel, log_channel, interaction.user)

        await ticket_channel.send(
            f"{interaction.user.mention}, your **{self.label}** ticket is open. Please wait for a staff member.",
            view=view
        )

        await interaction.response.send_message(f"🎟️ Ticket created: {ticket_channel.mention}", ephemeral=True)

        if log_channel:
            await log_channel.send(f"📨 {interaction.user.mention} opened a **{self.label}** ticket in {ticket_channel.mention}.")


class TicketManagementView(discord.ui.View):
    def __init__(self, ticket_channel, log_channel, creator):
        super().__init__(timeout=None)
        self.ticket_channel = ticket_channel
        self.log_channel = log_channel
        self.creator = creator

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.primary, emoji="🛠️")
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.channel != self.ticket_channel:
            return await interaction.response.send_message("❌ This button can't be used here.", ephemeral=True)
        await self.ticket_channel.set_permissions(interaction.user, view_channel=True, send_messages=True)
        await self.ticket_channel.send(f"🔒 {interaction.user.mention} has **claimed** this ticket.")
        if self.log_channel:
            await self.log_channel.send(f"🔒 {interaction.user.mention} claimed ticket {self.ticket_channel.mention}.")

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="🔒")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.channel != self.ticket_channel:
            return await interaction.response.send_message("❌ This button can't be used here.", ephemeral=True)
        await interaction.response.send_message("⏳ Closing this ticket in 5 seconds...", ephemeral=True)
        await discord.utils.sleep_until(discord.utils.utcnow() + discord.utils.timedelta(seconds=5))
        await self.ticket_channel.delete()
        if self.log_channel:
            await self.log_channel.send(f"❌ Ticket created by {self.creator.mention} closed by {interaction.user.mention}.")


async def setup(bot):
    await bot.add_cog(TicketCog(bot))
