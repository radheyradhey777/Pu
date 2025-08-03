import discord, json, os, requests
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

SETTINGS_FILE = "welcome_settings.json"

def load_settings(guild_id):
    if not os.path.exists(SETTINGS_FILE):
        return {}
    with open(SETTINGS_FILE, "r") as f:
        data = json.load(f)
    return data.get(str(guild_id), {})

def save_settings(guild_id, data):
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            all_data = json.load(f)
    else:
        all_data = {}

    all_data[str(guild_id)] = data
    with open(SETTINGS_FILE, "w") as f:
        json.dump(all_data, f, indent=2)

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.invites = {}

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            self.invites[guild.id] = await guild.invites()

    @commands.has_permissions(administrator=True)
    @commands.hybrid_command(name="welcome_setup")
    async def welcome_setup(self, ctx, channel: discord.TextChannel, role: discord.Role,
                            background_url: str, *, message: str):
        """
        Slash Usage:
        /welcome_setup channel:<#> role:@ role background_url:<http> message:<text>
        Use {member} {count} {inviter} {invites}
        """
        save_settings(ctx.guild.id, {
            "channel_id": channel.id,
            "role_id": role.id,
            "background": background_url,
            "message": message
        })
        await ctx.reply("✅ Welcome system configured!")

    def make_banner(self, member, background):
        bg_raw = requests.get(background).content
        bg = Image.open(BytesIO(bg_raw)).convert("RGBA")

        avatar_url = member.display_avatar.with_size(256).url
        pfp = Image.open(BytesIO(requests.get(avatar_url).content)).convert("RGBA").resize((220,220))

        mask = Image.new("L", (220,220), 0)
        ImageDraw.Draw(mask).ellipse((0,0,220,220), fill=255)
        pfp.putalpha(mask)
        bg.paste(pfp, (bg.width//2 -110, 10), pfp)

        draw = ImageDraw.Draw(bg)
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 50)
        draw.text((bg.width//2, 260), member.name, fill="white", font=font, anchor="mm")

        buf = BytesIO()
        bg.save(buf, format="PNG")
        buf.seek(0)
        return buf

    @commands.Cog.listener()
    async def on_member_join(self, member):
        settings = load_settings(member.guild.id)
        if not settings:
            return

        guild = member.guild

        # Invite tracking:
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

        # Role
        role = guild.get_role(settings["role_id"])
        if role:
            try:
                await member.add_roles(role)
            except:
                pass

        # Send image embed
        channel = guild.get_channel(settings["channel_id"])
        if not channel:
            return

        file = discord.File(self.make_banner(member, settings["background"]), filename="welcome.png")
        embed = discord.Embed(
            description=settings["message"]\
                .replace("{member}", member.mention)\
                .replace("{count}", str(guild.member_count))\
                .replace("{inviter}", inviter_name)\
                .replace("{invites}", str(total_uses)),
            color=discord.Color.green()
        )
        embed.set_image(url="attachment://welcome.png")
        await channel.send(file=file, embed=embed)

async def setup(bot):
    await bot.add_cog(Welcome(bot))
