import discord
from discord.ext import commands
from discord import app_commands
import json
import os

CONFIG_PATH = "data/config.json"

def load_config():
    if not os.path.exists(CONFIG_PATH):
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, 'w') as f:
            json.dump({}, f)
    try:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        # Reset corrupted config
        with open(CONFIG_PATH, 'w') as f:
            json.dump({}, f)
        return {}

def save_config(config):
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=4)

class AutoMod(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()

    def get_guild_config(self, guild_id: int):
        guild_id = str(guild_id)
        if guild_id not in self.config:
            self.config[guild_id] = {
                "anti_link": False,
                "anti_spam": {"enabled": False, "count": 5}
            }
            save_config(self.config)
        return self.config[guild_id]

    @app_commands.command(name="anti-link", description="Enable or disable anti-link protection")
    @app_commands.describe(enable="True to enable, False to disable")
    async def anti_link(self, interaction: discord.Interaction, enable: bool):
        guild_id = str(interaction.guild.id)
        config = self.get_guild_config(guild_id)
        config["anti_link"] = enable
        save_config(self.config)
        await interaction.response.send_message(
            f"✅ Anti-link has been {'enabled' if enable else 'disabled'}.", ephemeral=True
        )

    @app_commands.command(name="anti-spam", description="Enable/disable anti-spam and set message count limit")
    @app_commands.describe(enable="True to enable, False to disable", count="Max messages allowed in 10s")
    async def anti_spam(self, interaction: discord.Interaction, enable: bool, count: int = 5):
        guild_id = str(interaction.guild.id)
        config = self.get_guild_config(guild_id)
        config["anti_spam"]["enabled"] = enable
        config["anti_spam"]["count"] = count
        save_config(self.config)
        await interaction.response.send_message(
            f"✅ Anti-spam has been {'enabled' if enable else 'disabled'} with limit set to {count}.", ephemeral=True
        )

    async def cog_load(self):
        # Register slash commands
        self.bot.tree.add_command(self.anti_link)
        self.bot.tree.add_command(self.anti_spam)

async def setup(bot):
    await bot.add_cog(AutoMod(bot))
