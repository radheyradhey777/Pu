import discord
from discord.ext import commands

VERIFY_CHANNEL_ID = 1404105990198001664  # Jahan verify message jayega
VERIFIED_ROLE_ID = 1405000000000000000  # Yahan apne Verified role ki ID dalein

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.verify_message_id = None

    async def send_verify_message(self):
        channel = self.bot.get_channel(VERIFY_CHANNEL_ID)
        if channel is None:
            print(f"Verify channel with ID {VERIFY_CHANNEL_ID} not found.")
            return
        
        embed = discord.Embed(
            title="Welcome to CoRamTix Hosting!",
            description="To ensure a safe and productive environment, please adhere to the following rules. React with ✅ below to agree and gain access to the server.",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="1. Be Respectful & Civil",
            value="- No hate speech, racism, sexism, or discrimination.\n"
                  "- Do not harass, flame, or personally attack others.\n"
                  "- Keep conversations civil and constructive.",
            inline=False
        )
        embed.add_field(
            name="2. No Spamming or Advertising",
            value="- Do not spam text, emojis, images, or mentions.\n"
                  "- Unauthorized advertising is strictly forbidden.\n"
                  "- Do not send unsolicited DMs to members.",
            inline=False
        )
        embed.add_field(
            name="3. Use Channels Correctly",
            value="- Keep discussions in their relevant channels.\n"
                  "- Use `#🤖-bot-commands` for bot interactions.\n"
                  "- For support, please create a ticket in `#🎫-create-a-ticket`.",
            inline=False
        )
        embed.add_field(
            name="4. Support Etiquette",
            value="- Do not ping or DM Staff for help; please use tickets.\n"
                  "- Provide as much detail as possible in your ticket.",
            inline=False
        )
        embed.add_field(
            name="5. Follow Discord's ToS",
            value="- All activity must comply with Discord's Terms of Service.",
            inline=False
        )
        embed.set_footer(text="Thank you for being part of our community!")

        msg = await channel.send(embed=embed)
        await msg.add_reaction("✅")
        self.verify_message_id = msg.id  # store message ID to track reactions

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{self.bot.user} is ready!")
        # Send verify message once on startup, optionally add check so it doesn't spam every restart
        # (You can add logic to check if message already exists)
        await self.send_verify_message()

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        # Ye event har reaction ke liye fire hota hai (guild me ya dm me)
        if payload.message_id != self.verify_message_id:
            return  # Agar verify message pe reaction nahi hai to ignore karein

        if str(payload.emoji) != "✅":
            return  # Sirf ✅ emoji pe kaam karein

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        role = guild.get_role(VERIFIED_ROLE_ID)
        if role is None:
            print(f"Verified role ID {VERIFIED_ROLE_ID} not found!")
            return

        member = guild.get_member(payload.user_id)
        if member is None:
            return

        # Add role agar user ke paas nahi hai
        if role not in member.roles:
            try:
                await member.add_roles(role, reason="User verified via reaction.")
                print(f"Added Verified role to {member.display_name}")
            except Exception as e:
                print(f"Failed to add Verified role: {e}")

async def setup(bot):
    await bot.add_cog(Fun(bot))
