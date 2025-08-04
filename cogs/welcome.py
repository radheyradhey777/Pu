import discord, json, os, requests
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

SETTINGS_FILE = "welcome_settings.json"

# Pre-configured settings
DEFAULT_SETTINGS = {
    "channel_id": 1398305234442256394,
    "role_id": 1398318317135200256,
    "background": "https://cdn.discordapp.com/attachments/1391812903748894862/1401546686458757273/images_1.jpg?ex=68915451&is=689002d1&hm=63f69110ba8eb76ff0cd073ab8637477fca34730c29b48f98a8965af3c4c0b16&",
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

    def make_banner(self, member, background):
        bg_raw = requests.get(background).content
        bg = Image.open(BytesIO(bg_raw)).convert("RGBA")

        avatar_url = member.display_avatar.with_size(256).url
        pfp = Image.open(BytesIO(requests.get(avatar_url).content)).convert("RGBA").resize((220, 220))

        mask = Image.new("L", (220, 220), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 220, 220), fill=255)
        pfp.putalpha(mask)
        bg.paste(pfp, (bg.width // 2 - 110, 10), pfp)

        draw = ImageDraw.Draw(bg)
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 50)
        draw.text((bg.width // 2, 260), member.name, fill="white", font=font, anchor="mm")

        buf = BytesIO()
        bg.save(buf, format="PNG")
        buf.seek(0)
        return buf

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

        # Send welcome
        channel = guild.get_channel(settings["channel_id"])
        if not channel:
            return

        file = discord.File(self.make_banner(member, settings["background"]), filename="welcome.png")
        embed = discord.Embed(
            description=settings["message"]
                .replace("{member}", member.mention)
                .replace("{count}", str(guild.member_count))
                .replace("{inviter}", inviter_name)
                .replace("{invites}", str(total_uses)),
            color=discord.Color.green()
        )
        embed.set_image(url="attachment://welcome.png")
        await channel.send(file=file, embed=embed)

async def setup(bot):
    await bot.add_cog(Welcome(bot))
