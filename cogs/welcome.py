import discord, json, requests, os
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

    @commands.has_permissions(administrator=True)
    @commands.hybrid_command(name="welcome_setup")
    async def welcome_setup(self, ctx, channel: discord.TextChannel, role: discord.Role,
                            background_url: str, *, message: str):
        save_settings(ctx.guild.id, {
            "channel_id": channel.id,
            "role_id": role.id,
            "background": background_url,
            "message": message
        })
        await ctx.reply("✅ Welcome system configured!")

    def generate_banner(self, member, bg_url: str):
        bg_data = requests.get(bg_url).content
        bg = Image.open(BytesIO(bg_data)).convert("RGBA")

        avatar_url = member.display_avatar.replace(size=256).url
        pfp_data = requests.get(avatar_url)
        pfp = Image.open(BytesIO(pfp_data.content)).convert("RGBA").resize((220, 220))

        mask = Image.new("L", pfp.size, 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 220, 220), fill=255)
        pfp.putalpha(mask)
        bg.paste(pfp, (bg.width // 2 - 110, 10), pfp)

        draw = ImageDraw.Draw(bg)
        font_big = ImageFont.truetype("arial.ttf", 50)
        draw.text((bg.width // 2, 260), member.name, font=font_big, fill="white", anchor="mm")

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

        # Auto-role
        role = guild.get_role(settings["role_id"])
        if role:
            try:
                await member.add_roles(role, reason="Auto welcome role")
            except Exception as e:
                print("Failed to give role:", e)

        # Channel
        channel = guild.get_channel(settings["channel_id"])
        if channel is None:
            return

        banner = self.generate_banner(member, settings["background"])

        embed = discord.Embed(
            description=settings["message"]
                .replace("{member}", member.mention)
                .replace("{count}", str(guild.member_count)),
            color=discord.Color.green()
        )

        file = discord.File(banner, filename="welcome.png")
        embed.set_image(url="attachment://welcome.png")
        await channel.send(file=file, embed=embed)

async def setup(bot):
    await bot.add_cog(Welcome(bot))
