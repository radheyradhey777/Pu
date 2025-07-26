import discord
from discord.ext import commands
import os

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Bot connected as {bot.user}")
    await bot.tree.sync()

# Load cogs
for filename in os.listdir('./cogs'):
    if filename.endswith('.py'):
        bot.load_extension(f'cogs.{filename[:-3]}')

bot.run("MTM4MTMyODM2MzA1MzkxMjA3NA.Gbb0Kp.y96-QuBnYqIdMvWBz7_0VSAIGFcykYdS7_PFPs")
