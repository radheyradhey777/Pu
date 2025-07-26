import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# Load .env variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Flask Keep-Alive Web Server
app = Flask(__name__)

@app.route('/')
def home():
    return "Ticket Bot is Online!"

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
    keep_alive()  # Start Flask keep-alive
    await load_cogs()
    await bot.start(TOKEN)

# Run the bot
asyncio.run(main())
