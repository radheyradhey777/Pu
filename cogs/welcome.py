import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO

# set your role id & channel id here
WELCOME_CHANNEL_ID = 1398305234442256394
AUTO_ROLE_ID = 1398318317135200256


class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def generate_banner(self, member):
        bg = Image.open("background.jpg").convert("RGBA")

        # avatar
        avatar_url = member.display_avatar.replace(size=256).url
        pfp_data = requests.get(avatar_url)
        pfp = Image.open(BytesIO(pfp_data.content)).convert("RGBA").resize((220, 220))

        mask = Image.new("L", pfp.size, 0)
        dmask = ImageDraw.Draw(mask)
        dmask.ellipse((0, 0, 220, 220), fill=255)
        pfp.putalpha(mask)
        bg.paste(pfp, (bg.width//2 - 110, 10), pfp)

        draw = ImageDraw.Draw(bg)
        f_big = ImageFont.truetype("arial.ttf", 50)
        f_small = ImageFont.truetype("arial.ttf", 30)

        draw.text((bg.width // 2, 260), member.name, font=f_big, fill="white", anchor="mm")
        draw.text((bg.width // 2, 320), "Welcome to this server, go read the", font=f_small, fill="white", anchor="mm")
        draw.text((bg.width // 2, 360), "rules please!", font=f_small, fill="white", anchor="mm")

        buf = BytesIO()
        bg.save(buf, format="PNG")
        buf.seek(0)
        return buf

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild

        # AUTO ROLE
        try:
            role = guild.get_role(AUTO_ROLE_ID)
            if role is not None:
                await member.add_roles(role, reason="Auto Welcome Role")
        except Exception as e:
            print("Failed to give role:", e)

        # WELCOME CHANNEL
        channel = guild.get_channel(WELCOME_CHANNEL_ID)
        if channel is None:
            return

        # Generate image
        banner = self.generate_banner(member)

        # Find inviter (basic)
        invites_before = await guild.invites()
        inviter = "Unknown"
        uses = 1
        try:
            invites_after = await guild.invites()
            for old in invites_before:
                for new in invites_after:
                    if old.code == new.code and new.uses > old.uses:
                        inviter = new.inviter.name
                        uses = new.uses
        except:
            pass

        # Embed
        embed = discord.Embed(
            description=f"• Welcome {member.mention} To **{guild.name}**\n"
                        f"• Members Count : **{guild.member_count}**\n"
                        f"• Invited By : **{inviter}**\n"
                        f"• invites : **{uses}**",
            colour=discord.Colour.green()
        )
        file = discord.File(banner, filename="welcome.png")
        embed.set_image(url="attachment://welcome.png")
        await channel.send(file=file, embed=embed)


async def setup(bot):
    await bot.add_cog(Welcome(bot))
