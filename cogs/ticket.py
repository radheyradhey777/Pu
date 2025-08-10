import discord
from discord.ext import commands
import logging
import re

CONFIG = {
    "GUILD_ID": 1380792281048678441,
    "TICKET_CATEGORY_ID": 1404116391778320586,
    "TICKET_PANEL_CHANNEL_ID": 1404105997215203350,
    "SUPPORT_ROLE_IDS": [1404105969599905954],
    "LOG_CHANNEL_ID": None,
    "DELETE_AFTER_CLOSE": True,
    "TICKET_PREFIX": "ticket",
    "CLOSED_PREFIX": "closed"
}

logger = logging.getLogger(__name__)


def sanitize_name(name: str) -> str:
    return re.sub(r'[^a-z0-9_-]', '', name.lower().replace(" ", "-"))


async def has_support_role(member: discord.Member) -> bool:
    return any(role.id in CONFIG["SUPPORT_ROLE_IDS"] for role in member.roles)


async def send_log(message: str, guild: discord.Guild):
    if CONFIG["LOG_CHANNEL_ID"] is None:
        return
    channel = guild.get_channel(CONFIG["LOG_CHANNEL_ID"])
    if channel:
        await channel.send(message)


class TicketModal(discord.ui.Modal):
    def __init__(self, reason: str):
        super().__init__(title=f"{reason} Ticket")
        self.reason = reason

        self.add_item(discord.ui.TextInput(label="Your Discord Name", placeholder="Your full name", required=True))

        if reason == "Private Support":
            self.add_item(discord.ui.TextInput(label="Describe your issue", style=discord.TextStyle.paragraph, required=True))

        elif reason == "Purchase Product":
            self.add_item(discord.ui.TextInput(label="Product to purchase", required=True))
            self.add_item(discord.ui.TextInput(label="Preferred Payment Method", placeholder="e.g., UPI, Paytm", required=True))

        elif reason == "Report":
            self.add_item(discord.ui.TextInput(label="Report Details", style=discord.TextStyle.paragraph, required=True))

        elif reason == "Sponsorship":
            self.add_item(discord.ui.TextInput(label="Why should we sponsor you?", style=discord.TextStyle.paragraph, required=True))

    async def on_submit(self, interaction: discord.Interaction):
        try:
            ticket_name = sanitize_name(f"{CONFIG['TICKET_PREFIX']}-{interaction.user.name}")
            existing = discord.utils.get(interaction.guild.text_channels, name=ticket_name)
            if existing:
                return await interaction.response.send_message(f"⚠️ Ticket already open: {existing.mention}", ephemeral=True)

            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True)
            }
            for rid in CONFIG["SUPPORT_ROLE_IDS"]:
                role = interaction.guild.get_role(rid)
                if role:
                    overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

            category = interaction.guild.get_channel(CONFIG["TICKET_CATEGORY_ID"])
            if category is None:
                return await interaction.response.send_message("❌ Ticket category not found.", ephemeral=True)

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
            for field in self.children:
                embed.add_field(name=field.label, value=field.value or "None", inline=False)

            await channel.send(content=f"{interaction.user.mention} <@&{CONFIG['SUPPORT_ROLE_IDS'][0]}>", embed=embed, view=TicketManagementView())
            await interaction.response.send_message(f"✅ Ticket created: {channel.mention}", ephemeral=True)
            await send_log(f"📥 New ticket from {interaction.user.mention} in {channel.mention}", interaction.guild)

        except Exception as e:
            logger.exception("Ticket creation failed")
            await interaction.response.send_message("❌ Ticket creation failed.", ephemeral=True)


class TicketReasonSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Private Support", description="Technical or account issues", emoji="🔧"),
            discord.SelectOption(label="Purchase Product", description="Buy a hosting product", emoji="💸"),
            discord.SelectOption(label="Report", description="Report a user, server or issue", emoji="📢"),
            discord.SelectOption(label="Sponsorship", description="Apply for partnership or sponsorship", emoji="🤝")
        ]
        super().__init__(placeholder="Choose ticket reason", options=options)

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
        if not await has_support_role(interaction.user):
            return await interaction.response.send_message("❌ You lack permission to close tickets.", ephemeral=True)

        try:
            channel = interaction.channel
            overwrites = channel.overwrites
            for target, perms in list(overwrites.items()):
                if isinstance(target, discord.Member):
                    perms.send_messages = False
                    overwrites[target] = perms
            await channel.edit(name=f"{CONFIG['CLOSED_PREFIX']}-{channel.name.split('-', 1)[1]}", overwrites=overwrites)
            await channel.send(embed=discord.Embed(description=f"🔒 Ticket closed by {interaction.user.mention}", color=discord.Color.red()))

            if CONFIG["DELETE_AFTER_CLOSE"]:
                await channel.send("🗑️ Deleting this ticket shortly...")
                await channel.delete(delay=5)
            else:
                await interaction.response.send_message("✅ Ticket closed.", ephemeral=True)

        except Exception as e:
            logger.exception("Failed to close ticket")
            await interaction.response.send_message("❌ Failed to close ticket.", ephemeral=True)


class TicketCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setup(self, ctx: commands.Context):
        await ctx.message.delete()
        guild = ctx.guild
        channel = guild.get_channel(CONFIG["TICKET_PANEL_CHANNEL_ID"])
        if channel:
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
        self.bot.add_view(TicketView())
        self.bot.add_view(TicketManagementView())


async def setup(bot: commands.Bot):
    await bot.add_cog(TicketCog(bot))
