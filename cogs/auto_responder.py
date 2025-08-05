import discord
from discord.ext import commands
import asyncio
import re
import difflib # <-- YEH IMPORT KAREIN

class AutoResponder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        # --- Similarity Threshold ---
        # Shabdon ko kitna similar hone par match maana jaye (0.0 se 1.0)
        # 1.0 = Exact match | 0.85 = 85% similar. Aap isey apne hisab se badal sakte hain.
        self.similarity_threshold = 0.85

        # Dictionary of trigger : reply
        self.triggers = {
            "hello": "Bot Reply Message",
            "website": "http://coramtix.in/",
            "minecraft": """__**Minecraft Hosting Plans – CoRamTix**__

**Dirt Plan — ₹100/month** • 2 GB RAM • 100% CPU • 5 GB NVMe

**Grass Plan — ₹150/month** • 4 GB RAM • 150% CPU • 8 GB NVMe

**Stone Plan — ₹270/month** • 6 GB RAM • 200% CPU • 15 GB NVMe

**Coal Plan — ₹350/month** • 8 GB RAM • 220% CPU • 20 GB NVMe

**Iron Plan — ₹540/month** • 12 GB RAM • 300% CPU • 30 GB NVMe

**Gold Plan — ₹700/month** • 16 GB RAM • 350% CPU • 40 GB NVMe

**Diamond Plan — ₹1080/month** • 24 GB RAM • 400% CPU • 50 GB NVMe

**Obsidian Plan — ₹1590/month** • 32 GB RAM • 700% CPU • 70 GB NVMe

**Netherite Plan — ₹2990/month** • 64 GB RAM • 1000% CPU • 120 GB NVMe

**Included with All Plans:** • Instant Setup • DDoS Protection • Easy Panel + FTP Access  
• NVMe SSD Speed • 24/7 Support"""
        }

        # Aliases for same reply
        self.aliases = {
            "minecraft hosting": "minecraft",
            "minecraft plans": "minecraft",
            "minecraft plan": "minecraft"
        }

        # Cooldown tracker per-channel
        self.cooldowns = {}

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        channel_id = message.channel.id

        # Cooldown check (10 seconds)
        now = discord.utils.utcnow().timestamp()
        if channel_id in self.cooldowns and self.cooldowns[channel_id] > now:
            return

        content = message.content.lower()

        # Pehle aliases check karein, yeh exact match hona chahiye
        for alias, main_trigger in self.aliases.items():
            if alias in content:
                # Alias milne par, hum seedha reply bhej denge aur aage check nahi karenge
                try:
                    await message.channel.send(self.triggers[main_trigger])
                    self.cooldowns[channel_id] = now + 10
                except discord.Forbidden:
                    pass
                return # Function se bahar aa jayein

        # === FUZZY MATCHING LOGIC ===
        # Message ko shabdon mein todein
        message_words = content.split()

        # Har shabd ko har trigger ke saath compare karein
        for trigger, reply in self.triggers.items():
            for word in message_words:
                # Similarity ratio calculate karein
                similarity = difflib.SequenceMatcher(None, word, trigger).ratio()

                # Agar similarity threshold se zyada hai
                if similarity >= self.similarity_threshold:
                    try:
                        await message.channel.send(reply)
                        self.cooldowns[channel_id] = now + 10
                    except discord.Forbidden:
                        pass
                    return # Match mil gaya, function se bahar nikal jayein

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def addtrigger(self, ctx, trigger: str, *, reply: str):
        self.triggers[trigger.lower()] = reply
        await ctx.send(f"Added trigger: **{trigger}** → {reply}")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def removetrigger(self, ctx, trigger: str):
        removed = self.triggers.pop(trigger.lower(), None)
        if removed:
            await ctx.send(f"Removed trigger: **{trigger}**")
        else:
            await ctx.send("Trigger not found.")

def setup(bot):
    bot.add_cog(AutoResponder(bot))
