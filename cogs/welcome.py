import discord, json, os
from discord.ext import commands

SETTINGS_FILE = "welcome_settings.json"

# Pre-configured settings
DEFAULT_SETTINGS = {
    "channel_id": 1404105987664646215,
    "role_id": 1404105974041542749,
    "message": (
        "• Welcome {member} To CoRamTix - Premium Hosting Experience\n"
        "• Members Count : {count}\n"
        "• Invited By : {inviter}\n"
        "• Invites : {invites}"
    )
}

def load_settings(guild_id):
    if not os.path.exists(SETTINGS_FILE):
        return DEFAULT_SETTINGS
    with open(SETTINGS_FILE, "r") as f:
        data = json.load(f)
    return data.get(str(guild_id), DEFAULT_SETTINGS)

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.invites = {}

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            self.invites[guild.id] = await guild.invites()

    @commands.Cog.listener()
    async def on_member_join(self, member):
        settings = load_settings(member.guild.id)
        guild = member.guild

        # Invite tracking
        old_invites = self.invites.get(guild.id, [])
        new_invites = await guild.invites()
        invite_used = None

        for old in old_invites:
            for new in new_invites:
                if old.code == new.code and old.uses < new.uses:
                    invite_used = new
                    break

        self.invites[guild.id] = new_invites
        inviter_name = invite_used.inviter.name if invite_used else "Unknown"
        total_uses = invite_used.uses if invite_used else 0

        # Auto-role
        role = guild.get_role(settings["role_id"])
        if role:
            try:
                await member.add_roles(role)
            except:
                pass

        # Send embed welcome message (no banner background)
        channel = guild.get_channel(settings["channel_id"])
        if not channel:
            return

        embed = discord.Embed(
            description=settings["message"]
                .replace("{member}", member.mention)
                .replace("{count}", str(guild.member_count))
                .replace("{inviter}", inviter_name)
                .replace("{invites}", str(total_uses)),
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="CoRamTix - Premium Hosting Experience")

        await channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Welcome(bot))
