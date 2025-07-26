import discord
from discord.ext import commands
import os
import asyncio
from flask import Flask
from threading import Thread

# ⛔ WARNING: Do NOT share this token publicly. Regenerate it if already leaked.
TOKEN = "MTM4MTMyODM2MzA1MzkxMjA3NA.Gbb0Kp.y96-QuBnYqIdMvWBz7_0VSAIGFcykYdS7_PFPs"  # <- Replace this with your actual token

# Flask Web Server to keep bot alive
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Ticket Bot is Online!"

def run_web():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_web)
    t.start()

# Discord Bot Setup
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Bot is ready. Logged in as {bot.user}")
    await bot.tree.sync()

async def load_cogs():
    if not os.path.exists("./cogs"):
        print("❌ 'cogs' directory not found.")
        return
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            try:
                await bot.load_extension(f"cogs.{filename[:-3]}")
                print(f"✅ Loaded cog: {filename}")
            except Exception as e:
                print(f"❌ Failed to load cog {filename}: {e}")

async def main():
    try:
        keep_alive()
        await load_cogs()
        print("✅ Starting bot...")
        await bot.start(TOKEN)
    except Exception as e:
        print(f"❌ Bot start error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
