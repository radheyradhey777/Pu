import discord
from discord.ext import commands
from discord import app_commands
import asyncio

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
        for label in [button1, button2, button3, button4]:
            if label:
                parts = label.strip().split(" ", 1)
                emoji, label_text = (parts[0], parts[1]) if len(parts) == 2 else (None, label)
                view.add_item(TicketButton(
                    label=label_text,
                    emoji=emoji,
                    category_id=category.id,
                    log_channel_id=log_channel.id,
                    staff_role_id=staff_role.id if staff_role else None
                ))

        await panel_channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Ticket panel sent successfully.", ephemeral=True)


class TicketView(discord.ui.View):
    def __init__(self, category_id, log_channel_id, staff_role_id):
        super().__init__(timeout=None)
        self.category_id = category_id
        self.log_channel_id = log_channel_id
        self.staff_role_id = staff_role_id


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

        # ADMIN VIEW EMBED
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

        if interaction.channel != self.ticket_channel:
            return await interaction.response.send_message("❌ This button can't be used here.", ephemeral=True)

        await self.ticket_channel.set_permissions(interaction.user, view_channel=True, send_messages=True)
        await self.ticket_channel.send(f"🔒 {interaction.user.mention} has **claimed** this ticket.")
        if self.log_channel:
            await self.log_channel.send(f"🔒 {interaction.user.mention} claimed ticket {self.ticket_channel.mention}.")

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="🔒")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_staff(interaction.user):
            return await interaction.response.send_message("🚫 You are not allowed to close tickets.", ephemeral=True)

        if interaction.channel != self.ticket_channel:
            return await interaction.response.send_message("❌ This button can't be used here.", ephemeral=True)

        await interaction.response.send_message("⏳ Closing this ticket in 5 seconds...", ephemeral=True)
        await asyncio.sleep(5)
        await self.ticket_channel.delete()
        if self.log_channel:
            await self.log_channel.send(f"❌ Ticket created by {self.creator.mention} closed by {interaction.user.mention}.")


# Setup function for the cog
async def setup(bot):
    await bot.add_cog(TicketCog(bot))
