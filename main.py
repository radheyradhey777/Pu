import discord
from discord.ext import commands
import os
import asyncio
from flask import Flask
from threading import Thread
from dotenv import load_dotenv

# Load .env variables
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Web server to keep bot alive
app = Flask(__name__)
@app.route('/')
def home():
    return "✅ Ticket Bot is Online!"
def run_web():
    app.run(host='0.0.0.0', port=8080)
def keep_alive():
    thread = Thread(target=run_web)
    thread.start()

# Custom Bot class
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Load cogs
        if not os.path.exists("./cogs"):
            print("❌ 'cogs' directory not found.")
        else:
            for filename in os.listdir("./cogs"):
                if filename.endswith(".py"):
                    try:
                        await self.load_extension(f"cogs.{filename[:-3]}")
                        print(f"✅ Loaded cog: {filename}")
                    except Exception as e:
                        print(f"❌ Failed to load cog {filename}: {e}")
        
        # Sync slash commands globally (you can also sync per guild)
        try:
            await self.tree.sync()
            print("✅ Slash commands synced.")
        except Exception as e:
            print(f"❌ Slash command sync failed: {e}")

# Initialize bot
bot = MyBot()

@bot.event
async def on_ready():
    print(f"✅ Bot is ready. Logged in as {bot.user}")

# Run everything
async def main():
    try:
        keep_alive()
        print("✅ Starting bot...")
        await bot.start(TOKEN)
    except Exception as e:
        print(f"❌ Bot start error: {e}")

if __name__ == "__main__":
    if TOKEN is None:
        print("❌ DISCORD_TOKEN is not set in the environment.")
    else:
        asyncio.run(main())
