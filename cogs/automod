import discord
from discord.ext import commands
from discord import app_commands
import json

# Default configuration
default_config = {
    "enabled": True,
    "discord_invite": False,
    "link": False,
    "spam_mention": False,
    "spam_emoji": False,
    "sticker": False,
    "ban_words": False,
    "wall_text": False,
    "caps": False,
    "spoiler": False,
    "ignored_channels": [],
    "ignored_roles": [],
    "ignored_users": [],
    "warning_threshold": 5,
    "punishment_timeout": 5
}

# Save/load config from a file (for persistence)
def load_config():
    try:
        with open("automod_config.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return default_config.copy()

def save_config(config):
    with open("automod_config.json", "w") as f:
        json.dump(config, f, indent=4)

class AutoModView(discord.ui.View):
    def __init__(self, config):
        super().__init__(timeout=None)
        self.config = config

    @discord.ui.select(
        placeholder="Make a selection",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(label="Discord Invite Filter"),
            discord.SelectOption(label="Link Filter"),
            discord.SelectOption(label="Spam Mention Filter"),
            discord.SelectOption(label="Spam Emoji Filter"),
            discord.SelectOption(label="Sticker Filter"),
            discord.SelectOption(label="Ban Words Filter"),
            discord.SelectOption(label="Wall Text Filter"),
            discord.SelectOption(label="Capital Letters Filter"),
            discord.SelectOption(label="Spoiler Filter"),
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        selected = select.values[0]
        key = selected.lower().replace(" ", "_").replace("capital_letters", "caps")

        # Toggle selected filter
        self.config[key] = not self.config.get(key, False)
        save_config(self.config)

        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    def get_embed(self):
        cfg = self.config
        embed = discord.Embed(title="Automod", color=discord.Color.blurple())
        embed.add_field(name="Enabled", value=str(cfg["enabled"]), inline=False)
        embed.add_field(name="Discord Invite Filter", value=self.status(cfg["discord_invite"]), inline=True)
        embed.add_field(name="Link Filter", value=self.status(cfg["link"]), inline=True)
        embed.add_field(name="Spam Mention Filter", value=self.status(cfg["spam_mention"]), inline=True)
        embed.add_field(name="Spam Emoji Filter", value=self.status(cfg["spam_emoji"]), inline=True)
        embed.add_field(name="Sticker Filter", value=self.status(cfg["sticker"]), inline=True)
        embed.add_field(name="Ban Words Filter", value=self.status(cfg["ban_words"]), inline=True)
        embed.add_field(name="Wall Text Filter", value=self.status(cfg["wall_text"]), inline=True)
        embed.add_field(name="Caps Filter", value=self.status(cfg["caps"]), inline=True)
        embed.add_field(name="Spoiler Filter", value=self.status(cfg["spoiler"]), inline=True)
        embed.add_field(name="Warning Threshold", value=str(cfg["warning_threshold"]), inline=True)
        embed.add_field(name="Punishment Timeout", value=f"{cfg['punishment_timeout']} minutes", inline=True)
        return embed

    def status(self, val):
        return "🟢 Enabled" if val else "🔴 Disabled"

class AutoModCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()

    @app_commands.command(name="automod", description="Show and configure AutoMod settings")
    async def automod(self, interaction: discord.Interaction):
        embed = AutoModView(self.config).get_embed()
        await interaction.response.send_message(embed=embed, view=AutoModView(self.config))

async def setup(bot):
    await bot.add_cog(AutoModCog(bot))
