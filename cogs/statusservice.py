import discord
from discord.ext import commands, tasks
import aiohttp

class StatusService(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.services = {
            "Game Panel": "https://gpanel.coramtix.in/",
            "Node 1": "https://node1.coramtix.in/",
            "Node 2": "https://node2.coramtix.in/",
            "Node 3": "https://node3.coramtix.in/",
        }
        self.paid_role_id = 123456789012345678  # Replace with your role ID (int)
        self.last_overall_status = None
        self.check_services.start()

    def cog_unload(self):
        self.check_services.cancel()

    @tasks.loop(seconds=60)
    async def check_services(self):
        statuses = {}
        async with aiohttp.ClientSession() as session:
            for name, url in self.services.items():
                try:
                    async with session.get(url, timeout=10) as resp:
                        statuses[name] = resp.status == 200
                except Exception:
                    statuses[name] = False

        any_down = any(not up for up in statuses.values())

        if self.last_overall_status is None:
            self.last_overall_status = not any_down
            return

        # Only send message on status change
        if any_down != (not self.last_overall_status):
            self.last_overall_status = not any_down

            if any_down:
                down_services = [name for name, up in statuses.items() if not up]
                message = "🚨 **Alert! Some services are DOWN:**\n"
                for s in down_services:
                    message += f" - {s} ❌\n"
                message += "\nPlease check them ASAP!"
            else:
                message = "✅ All monitored services are UP now! Everything is working fine."

            for guild in self.bot.guilds:
                role = discord.utils.get(guild.roles, id=self.paid_role_id)
                if role:
                    for member in role.members:
                        try:
                            await member.send(message)
                        except Exception:
                            pass

    @check_services.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

def setup(bot):
    bot.add_cog(StatusService(bot))
