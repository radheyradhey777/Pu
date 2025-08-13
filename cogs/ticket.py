import discord
from discord.ext import commands
import logging
import re
import asyncio

# === CONFIG ===
CONFIG = {
    "GUILD_ID": 1380792281048678441,
    "TICKET_CATEGORY_ID": 1404116391778320586,
    "TICKET_PANEL_CHANNEL_ID": 1404105997215203350,
    "SUPPORT_ROLE_IDS": [1404105969599905954],
    "LOG_CHANNEL_ID": None,  # Set to your log channel ID or None to disable
    "DELETE_AFTER_CLOSE": True,
    "TICKET_PREFIX": "ticket",
    "CLOSED_PREFIX": "closed"
}

logger = logging.getLogger(__name__)


def sanitize_name(name: str) -> str:
    # Only allow a-z, 0-9, underscores and dashes, lowercased
    return re.sub(r'[^a-z0-9_-]', '', name.lower().replace(" ", "-"))


def has_support_role(member: discord.Member) -> bool:
    # Synchronous check for support roles
    return any(role.id in CONFIG["SUPPORT_ROLE_IDS"] for role in member.roles)


async def send_log(message: str, guild: discord.Guild):
    if CONFIG["LOG_CHANNEL_ID"] is None:
        return
    channel = guild.get_channel(CONFIG["LOG_CHANNEL_ID"])
    if channel:
        try:
            await channel.send(message)
        except Exception:
            logger.exception("Failed to send log message.")


class TicketModal(discord.ui.Modal):
    def __init__(self, reason: str):
        super().__init__(title=f"{reason} Ticket")
        self.reason = reason

        self.name_input = discord.ui.TextInput(
            label="Your Discord Name",
            placeholder="Your full name",
            required=True,
            max_length=100
        )
        self.add_item(self.name_input)

        if reason == "Private Support":
            self.issue_input = discord.ui.TextInput(
                label="Describe your issue",
                style=discord.TextStyle.paragraph,
                required=True,
                max_length=1000
            )
            self.add_item(self.issue_input)

        elif reason == "Purchase Product":
            self.product_input = discord.ui.TextInput(
                label="Product to purchase",
                required=True,
                max_length=100
            )
            self.payment_input = discord.ui.TextInput(
                label="Preferred Payment Method",
                placeholder="e.g., UPI, Paytm",
                required=True,
                max_length=100
            )
            self.add_item(self.product_input)
            self.add_item(self.payment_input)

        elif reason == "Report":
            self.report_input = discord.ui.TextInput(
                label="Report Details",
                style=discord.TextStyle.paragraph,
                required=True,
                max_length=1000
            )
            self.add_item(self.report_input)

        elif reason == "Sponsorship":
            self.sponsor_input = discord.ui.TextInput(
                label="Why should we sponsor you?",
                style=discord.TextStyle.paragraph,
                required=True,
                max_length=1000
            )
            self.add_item(self.sponsor_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            ticket_name = sanitize_name(f"{CONFIG['TICKET_PREFIX']}-{interaction.user.id}")
            existing = discord.utils.get(interaction.guild.text_channels, name=ticket_name)
            if existing:
                await interaction.response.send_message(f"⚠️ You already have an open ticket: {existing.mention}", ephemeral=True)
                return

            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
            }
            for rid in CONFIG["SUPPORT_ROLE_IDS"]:
                role = interaction.guild.get_role(rid)
                if role:
                    overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

            category = interaction.guild.get_channel(CONFIG["TICKET_CATEGORY_ID"])
            if category is None:
                await interaction.response.send_message("❌ Ticket category not found. Please contact an administrator.", ephemeral=True)
                return

            channel = await interaction.guild.create_text_channel(
                name=ticket_name,
                category=category,
                overwrites=overwrites,
                reason=f"{self.reason} ticket created by {interaction.user}"
            )

            embed = discord.Embed(
                title=f"🎫 {self.reason} Ticket",
                color=discord.Color.blurple(),
                timestamp=interaction.created_at
            )
            embed.add_field(name="User", value=interaction.user.mention, inline=False)

            # Add all input fields to embed
            for child in self.children:
                if isinstance(child, discord.ui.TextInput):
                    embed.add_field(name=child.label, value=child.value or "None", inline=False)

            await channel.send(
                content=f"{interaction.user.mention} <@&{CONFIG['SUPPORT_ROLE_IDS'][0]}>",
                embed=embed,
                view=TicketManagementView()
            )
            await interaction.response.send_message(f"✅ Ticket created: {channel.mention}", ephemeral=True)
            await send_log(f"📥 New ticket from {interaction.user.mention} in {channel.mention}", interaction.guild)

        except Exception:
            logger.exception("Ticket creation failed")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Ticket creation failed due to an error.", ephemeral=True)


class TicketReasonSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Private Support", description="Technical or account issues", emoji="🔧"),
            discord.SelectOption(label="Purchase Product", description="Buy a hosting product", emoji="💸"),
            discord.SelectOption(label="Report", description="Report a user, server or issue", emoji="📢"),
            discord.SelectOption(label="Sponsorship", description="Apply for partnership or sponsorship", emoji="🤝")
        ]
        super().__init__(placeholder="Choose ticket reason", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(TicketModal(self.values[0]))


class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketReasonSelect())


class TicketManagementView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Close", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_support_role(interaction.user):
            await interaction.response.send_message("❌ You lack permission to close tickets.", ephemeral=True)
            return

        try:
            channel = interaction.channel
            overwrites = channel.overwrites.copy()

            # Disable send_messages for all targets (roles & members)
            for target, perms in overwrites.items():
                perms.send_messages = False
                overwrites[target] = perms

            # Rename channel with CLOSED prefix if not already present
            base_name = channel.name
            if not base_name.startswith(CONFIG['CLOSED_PREFIX']):
                parts = base_name.split('-', 1)
                if len(parts) > 1:
                    new_name = f"{CONFIG['CLOSED_PREFIX']}-{parts[1]}"
                else:
                    new_name = f"{CONFIG['CLOSED_PREFIX']}-{base_name}"
            else:
                new_name = base_name

            await channel.edit(name=new_name, overwrites=overwrites)

            await channel.send(embed=discord.Embed(description=f"🔒 Ticket closed by {interaction.user.mention}", color=discord.Color.red()))

            await interaction.response.send_message("✅ Ticket closed.", ephemeral=True)

            if CONFIG["DELETE_AFTER_CLOSE"]:
                await channel.send("🗑️ Deleting this ticket shortly...")
                await asyncio.sleep(5)
                await channel.delete()

        except Exception:
            logger.exception("Failed to close ticket")
            if interaction.response.is_done():
                await interaction.followup.send("❌ Failed to close ticket.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Failed to close ticket.", ephemeral=True)


class TicketCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def setup(self, ctx: commands.Context):
        await ctx.message.delete()
        guild = ctx.guild
        channel = guild.get_channel(CONFIG["TICKET_PANEL_CHANNEL_ID"])
        if channel is None:
            await ctx.send("❌ Ticket panel channel not found.", delete_after=10)
            return
        await channel.purge(limit=5)

        embed = discord.Embed(
            title="<:cc:1399375648476102667> CoramTix | Support",
            description=(
                "**Need support or want to buy something?**\n"
                "Open a ticket by selecting a category below.\n\n"
                "📌 **Options**:\n"
                "• 🔧 Private Support – Get technical help\n"
                "• 💸 Purchase Product – Order hosting packages\n"
                "• 📢 Report – Report users/servers/problems\n"
                "• 🤝 Sponsorship – Apply for partner/sponsor\n\n"
                "⛔ **Rules**:\n"
                "• No spam\n"
                "• Provide valid information\n"
                "• One ticket per user"
            ),
            color=discord.Color.blue()
        )
        embed.set_image(url="https://cdn.discordapp.com/attachments/1391812903748894862/1395401983036227616/Image.png")

        await channel.send(embed=embed, view=TicketView())

    @commands.Cog.listener()
    async def on_ready(self):
        # Register persistent views so buttons/selects keep working after bot restart
        self.bot.add_view(TicketView())
        self.bot.add_view(TicketManagementView())
        logger.info("TicketCog ready and views registered.")


async def setup(bot: commands.Bot):
    await bot.add_cog(TicketCog(bot))
