import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import json
import os

TICKET_CONFIG_FILE = "ticket_state.json"

# === Persistent Storage ===
class TicketStorage:
    @staticmethod
    def save(data):
        with open(TICKET_CONFIG_FILE, 'w') as f:
            json.dump(data, f, indent=4)

    @staticmethod
    def load():
        if not os.path.exists(TICKET_CONFIG_FILE):
            return []
        with open(TICKET_CONFIG_FILE, 'r') as f:
            return json.load(f)

# === Main Cog ===
class TicketCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.command(name="ticket", description="Setup ticket panel")
    @app_commands.describe(
        panel_channel="Channel to send the ticket panel",
        category="Category to create ticket channels in",
        log_channel="Channel to log ticket creations",
        title="Embed title",
        description="Embed description",
        image_url="Optional image URL",
        staff_role="Role allowed to manage tickets (claim/close)",
        button1="First button label (e.g., 🎫 Support)",
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
        staff_role: discord.Role = None,
        button1: str = None,
        button2: str = None,
        button3: str = None,
        button4: str = None,
    ):
        embed = discord.Embed(title=title, description=description, color=discord.Color.blurple())
        if image_url:
            embed.set_image(url=image_url)

        view = TicketView(category.id, log_channel.id, staff_role.id if staff_role else None)
        buttons = [button1, button2, button3, button4]
        saved_buttons = []

        for label in buttons:
            if label:
                parts = label.strip().split(" ", 1)
                emoji, label_text = (parts[0], parts[1]) if len(parts) == 2 else (None, label)
                view.add_ticket_button(label_text, emoji)
                saved_buttons.append({"label": label_text, "emoji": emoji})

        await panel_channel.send(embed=embed, view=view)

        TicketStorage.save([{
            "category_id": category.id,
            "log_channel_id": log_channel.id,
            "staff_role_id": staff_role.id if staff_role else None,
            "buttons": saved_buttons
        }])

        await interaction.response.send_message("✅ Ticket panel sent successfully.", ephemeral=True)

    @ticket_setup.error
    async def ticket_setup_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message("🚫 You must be an **Administrator** to use this command.", ephemeral=True)

# === Ticket Panel View ===
class TicketView(discord.ui.View):
    def __init__(self, category_id, log_channel_id, staff_role_id):
        super().__init__(timeout=None)
        self.category_id = category_id
        self.log_channel_id = log_channel_id
        self.staff_role_id = staff_role_id
        self.added_buttons = set()

    def add_ticket_button(self, label, emoji=None):
        if label in self.added_buttons:
            return
        self.add_item(TicketButton(label, self.category_id, self.log_channel_id, self.staff_role_id, emoji))
        self.added_buttons.add(label)

# === Ticket Button ===
class TicketButton(discord.ui.Button):
    def __init__(self, label, category_id, log_channel_id, staff_role_id=None, emoji=None):
        super().__init__(label=label, style=discord.ButtonStyle.secondary, emoji=emoji)
        self.label = label
        self.emoji = emoji
        self.category_id = category_id
        self.log_channel_id = log_channel_id
        self.staff_role_id = staff_role_id

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        category = guild.get_channel(self.category_id)
        log_channel = guild.get_channel(self.log_channel_id)

        for channel in category.text_channels:
            if channel.topic and str(interaction.user.id) in channel.topic:
                return await interaction.response.send_message(
                    f"⚠️ You already have an open ticket: {channel.mention}", ephemeral=True
                )

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }

        channel_name = f"{self.label.lower().replace(' ', '-')}-{interaction.user.name}".replace('🔧', '').strip()
        ticket_channel = await guild.create_text_channel(
            name=channel_name[:90],
            overwrites=overwrites,
            category=category,
            topic=f"Ticket opened by {interaction.user} via {self.label} | User ID: {interaction.user.id}"
        )

        view = TicketManagementView(ticket_channel, log_channel, interaction.user, self.staff_role_id)
        await ticket_channel.send(
            f"{interaction.user.mention}, your **{self.label}** ticket is open. Please wait for a staff member.",
            view=view
        )

        admin_embed = discord.Embed(
            title="Admin View",
            description=(
                f"**Ticket Type:** {self.label}\n"
                f"**Opened By:** {interaction.user.mention} ({interaction.user})\n"
                f"**Channel:** {ticket_channel.mention}\n"
                f"**User ID:** `{interaction.user.id}`"
            ),
            color=discord.Color.red()
        )

        if self.staff_role_id:
            staff_role = guild.get_role(self.staff_role_id)
            await ticket_channel.send(content=staff_role.mention, embed=admin_embed)
        else:
            await ticket_channel.send(embed=admin_embed)

        await interaction.response.send_message(f"🎟️ Ticket created: {ticket_channel.mention}", ephemeral=True)

        if log_channel:
            await log_channel.send(f"📨 {interaction.user.mention} opened a **{self.label}** ticket in {ticket_channel.mention}.")

# === Management Buttons (Claim/Close) ===
class TicketManagementView(discord.ui.View):
    def __init__(self, ticket_channel, log_channel, creator, staff_role_id):
        super().__init__(timeout=None)
        self.ticket_channel = ticket_channel
        self.log_channel = log_channel
        self.creator = creator
        self.staff_role_id = staff_role_id

    def is_staff(self, member: discord.Member):
        if self.staff_role_id is None:
            return True
        return discord.utils.get(member.roles, id=self.staff_role_id) is not None

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.primary, emoji="🛠️")
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_staff(interaction.user):
            return await interaction.response.send_message("🚫 You are not allowed to claim tickets.", ephemeral=True)

        await self.ticket_channel.set_permissions(interaction.user, view_channel=True, send_messages=True)
        await self.ticket_channel.send(f"🔒 {interaction.user.mention} has **claimed** this ticket.")
        if self.log_channel:
            await self.log_channel.send(f"🔒 {interaction.user.mention} claimed ticket {self.ticket_channel.mention}.")

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="🔒")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_staff(interaction.user):
            return await interaction.response.send_message("🚫 You are not allowed to close tickets.", ephemeral=True)

        await interaction.response.send_message("⏳ Closing this ticket in 5 seconds...", ephemeral=True)
        await asyncio.sleep(5)
        await self.ticket_channel.delete()
        if self.log_channel:
            await self.log_channel.send(f"❌ Ticket created by {self.creator.mention} closed by {interaction.user.mention}.")

# === Register Cog and Views on Restart ===
async def setup(bot: commands.Bot):
    await bot.add_cog(TicketCog(bot))

    # Register persistent views on restart
    for config in TicketStorage.load():
        view = TicketView(config['category_id'], config['log_channel_id'], config['staff_role_id'])
        for button in config['buttons']:
            view.add_ticket_button(button['label'], button['emoji'])
        bot.add_view(view)
