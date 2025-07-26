from discord.ext import commands
from discord import app_commands
import discord
from datetime import datetime, timedelta
import asyncio
import json
import os
from collections import defaultdict

CONFIG_PATH = "data/mod_config.json"

def load_config():
    if not os.path.exists(CONFIG_PATH):
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, 'w') as f:
            json.dump({}, f)
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=4)

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()
        self.spam_tracker = defaultdict(lambda: [])

    def save(self):
        save_config(self.config)

    async def check_permissions(self, interaction: discord.Interaction, target: discord.Member = None):
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return False

        if target and target.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            await interaction.response.send_message("❌ You cannot moderate someone with equal or higher role.", ephemeral=True)
            return False

        return True

    @app_commands.command(name="antilink", description="Enable or disable anti-link system")
    @app_commands.describe(status="Enable or disable (true/false)")
    async def antilink(self, interaction: discord.Interaction, status: bool):
        guild_id = str(interaction.guild_id)
        self.config.setdefault(guild_id, {})
        self.config[guild_id]["anti_link"] = status
        self.save()

        state = "enabled" if status else "disabled"
        await interaction.response.send_message(f"🔗 Anti-Link has been **{state}** for this server.", ephemeral=True)

    @app_commands.command(name="antispam", description="Enable or disable anti-spam system")
    @app_commands.describe(status="Enable or disable", count="Messages allowed per 5 seconds")
    async def antispam(self, interaction: discord.Interaction, status: bool, count: int = 5):
        guild_id = str(interaction.guild_id)
        self.config.setdefault(guild_id, {})
        self.config[guild_id]["anti_spam"] = {"enabled": status, "count": count}
        self.save()

        state = "enabled" if status else "disabled"
        await interaction.response.send_message(
            f"💬 Anti-Spam has been **{state}** with a limit of **{count} messages/5s**.", ephemeral=True
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        guild_id = str(message.guild.id)
        config = self.config.get(guild_id, {})

        # Anti-Link
        if config.get("anti_link"):
            if "http://" in message.content or "https://" in message.content or "discord.gg" in message.content:
                try:
                    await message.delete()
                    await message.channel.send(f"🚫 {message.author.mention}, links are not allowed here.", delete_after=5)
                except discord.Forbidden:
                    pass

        # Anti-Spam
        spam_cfg = config.get("anti_spam", {})
        if spam_cfg.get("enabled"):
            now = datetime.utcnow()
            window = timedelta(seconds=5)
            max_msgs = spam_cfg.get("count", 5)

            self.spam_tracker[message.author.id] = [
                msg_time for msg_time in self.spam_tracker[message.author.id]
                if (now - msg_time) <= window
            ]
            self.spam_tracker[message.author.id].append(now)

            if len(self.spam_tracker[message.author.id]) > max_msgs:
                try:
                    await message.delete()
                    await message.channel.send(f"🛑 {message.author.mention}, you're sending messages too quickly!", delete_after=5)
                except discord.Forbidden:
                    pass

    # --- MUTE / UNMUTE / KICK / BAN / SERVERINFO --- (Omitted here for brevity)

    # Insert the existing full mute, unmute, kick, ban, serverinfo, parse_duration, schedule_unmute methods below...

    # Include your full mute/unmute/kick/ban/serverinfo code here
    # As shown earlier in your original message
    # (To keep this reply shorter)

async def setup(bot):
    await bot.add_cog(Moderation(bot))
