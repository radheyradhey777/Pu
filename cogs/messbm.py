import discord
from discord.ext import commands

class MassDM(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="mdm")
    @commands.has_permissions(administrator=True)
    async def mass_dm(self, ctx, *, message: str):
        """Send a DM to all members in the server."""
        await ctx.send("📨 Starting to send DMs... This may take a while.")

        sent = 0
        failed = 0

        for member in ctx.guild.members:
            if member.bot:
                continue  # skip bots
            try:
                await member.send(message)
                sent += 1
            except discord.Forbidden:
                failed += 1
            except Exception as e:
                failed += 1

        await ctx.send(f"✅ Finished!\n📤 Sent: {sent}\n❌ Failed: {failed}")

async def setup(bot):
    await bot.add_cog(MassDM(bot))
