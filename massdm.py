import discord
from discord.ext import commands

class MassDM(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="mdm")
    @commands.has_permissions(administrator=True)
    async def mass_dm(self, ctx, *, message: str):
        """Send a DM to all members in the server."""
        await ctx.send("📨 Sending DMs...")

        sent = 0
        failed = 0
        for member in ctx.guild.members:
            if member.bot:
                continue
            try:
                await member.send(message)
                sent += 1
            except:
                failed += 1

        await ctx.send(f"✅ Sent: {sent} | ❌ Failed: {failed}")

async def setup(bot):
    await bot.add_cog(MassDM(bot))
