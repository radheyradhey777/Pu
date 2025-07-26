import discord
from discord.ext import commands
from discord import app_commands
import re
import json
import asyncio
import os

CONFIG_FILE = "automod_config.json"

default_config = {
    "enabled": True,
    "filters": {
        "discord_invite": False,
        "link": False,
        "spam_mention": False,
        "caps": False
    },
    "ignored_channels": [],
    "ignored_roles": [],
    "ignored_users": [],
    "warning_threshold": 3,
    "punishment_timeout": 5
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    else:
        return default_config.copy()

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

class AutoModView(discord.ui.View):
    def __init__(self, config, save_callback):
        super().__init__(timeout=None)
        self.config = config
        self.save_callback = save_callback

    @discord.ui.select(
        placeholder="Toggle filters",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label="Discord Invite Filter"),
            discord.SelectOption(label="Link Filter"),
            discord.SelectOption(label="Spam Mention Filter"),
            discord.SelectOption(label="Caps Filter")
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        label_to_key = {
            "Discord Invite Filter": "discord_invite",
            "Link Filter": "link",
            "Spam Mention Filter": "spam_mention",
            "Caps Filter": "caps"
        }
        selected_key = label_to_key[select.values[0]]
        self.config["filters"][selected_key] = not self.config["filters"].get(selected_key, False)
        self.save_callback(self.config)

        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    def create_embed(self):
        filters = self.config["filters"]
        embed = discord.Embed(title="🛡️ AutoMod Settings", color=discord.Color.blue())
        embed.add_field(name="Enabled", value=str(self.config["enabled"]), inline=False)
        for k, v in filters.items():
            embed.add_field(name=k.replace("_", " ").title(), value="✅ Enabled" if v else "❌ Disabled", inline=True)
        embed.add_field(name="Warning Threshold", value=str(self.config["warning_threshold"]), inline=True)
        embed.add_field(name="Timeout", value=f"{self.config['punishment_timeout']} min", inline=True)
        return embed

class AutoModCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()
        self.user_warnings = {}

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not self.config["enabled"]:
            return

        if str(message.channel.id) in self.config["ignored_channels"]:
            return
        if str(message.author.id) in self.config["ignored_users"]:
            return
        if any(role.id in self.config["ignored_roles"] for role in message.author.roles):
            return

        violations = []

        if self.config["filters"].get("discord_invite") and "discord.gg/" in message.content:
            violations.append("Invite Link")
        if self.config["filters"].get("link") and re.search(r"http[s]?://", message.content):
            violations.append("Link")
        if self.config["filters"].get("spam_mention") and len(message.mentions) >= 5:
            violations.append("Mass Mention")
        if self.config["filters"].get("caps") and message.content.isupper() and len(message.content) > 10:
            violations.append("Excessive Caps")

        if violations:
            await message.delete()
            await self.warn_user(message.author, message.channel, ", ".join(violations))

    async def warn_user(self, member, channel, reason):
        user_id = str(member.id)
        self.user_warnings[user_id] = self.user_warnings.get(user_id, 0) + 1

        await channel.send(f"{member.mention} ⚠️ Warning for: `{reason}` (Total: {self.user_warnings[user_id]})", delete_after=10)

        if self.user_warnings[user_id] >= self.config["warning_threshold"]:
            try:
                await member.timeout(discord.utils.utcnow() + discord.timedelta(minutes=self.config["punishment_timeout"]))
                await channel.send(f"🚫 {member.mention} has been timed out for repeated violations.")
                self.user_warnings[user_id] = 0  # Reset warnings after punishment
            except discord.Forbidden:
                await channel.send("❌ Missing permissions to timeout this user.")

    @app_commands.command(name="automod", description="View and configure AutoMod")
    async def automod(self, interaction: discord.Interaction):
        view = AutoModView(self.config, save_callback=save_config)
        await interaction.response.send_message(embed=view.create_embed(), view=view, ephemeral=True)

async def setup(bot):
    await bot.add_cog(AutoModCog(bot))
