import discord
from discord.ext import commands
import os
import asyncio
from flask import Flask
from threading import Thread
from dotenv import load_dotenv  # Optional: for using a .env file

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")  # Use DISCORD_TOKEN from .env

# Flask Web Server to keep bot alive (for Replit or similar)
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Ticket Bot is Online!"

def run_web():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    thread = Thread(target=run_web)
    thread.start()

# Discord Bot Setup
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Bot is ready. Logged in as {bot.user}")

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

async def sync_commands():
    try:
        await bot.wait_until_ready()
        await bot.tree.sync()
        print("✅ Slash commands synced.")
    except Exception as e:
        print(f"❌ Slash command sync failed: {e}")

async def main():
    try:
        keep_alive()
        await load_cogs()
        bot.loop.create_task(sync_commands())  # Safer sync
        print("✅ Starting bot...")
        await bot.start(TOKEN)
    except Exception as e:
        print(f"❌ Bot start error: {e}")

if __name__ == "__main__":
    if TOKEN is None:
        print("❌ DISCORD_TOKEN is not set in the environment.")
    else:
        asyncio.run(main())
