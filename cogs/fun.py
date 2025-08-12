import discord
from discord.ext import commands

VERIFY_CHANNEL_ID = 1404105990198001664  # Jahan verify message jayega
VERIFIED_ROLE_ID = 1404526602649341963   # Verified role ki ID

# ===== Verify Button =====
class VerifyButton(discord.ui.View):
    def __init__(self, role_id):
        super().__init__(timeout=None)  # Persistent view
        self.role_id = role_id

    @discord.ui.button(label="✅ Verify", style=discord.ButtonStyle.success, custom_id="verify_button")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(self.role_id)
        if role is None:
            return await interaction.response.send_message(
                "❌ Verified role not found. Please contact staff.",
                ephemeral=True
            )

        if role in interaction.user.roles:
            return await interaction.response.send_message(
                "✅ You are already verified!",
                ephemeral=True
            )

        try:
            await interaction.user.add_roles(role, reason="User verified via button.")
            await interaction.response.send_message(
                "🎉 You have been verified! Welcome to the server!",
                ephemeral=True
            )
            print(f"Added Verified role to {interaction.user.display_name}")
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Failed to add Verified role: {e}",
                ephemeral=True
            )

# ===== Cog =====
class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def send_verify_message(self):
        channel = self.bot.get_channel(VERIFY_CHANNEL_ID)
        if channel is None:
            print(f"Verify channel with ID {VERIFY_CHANNEL_ID} not found.")
            return

        embed = discord.Embed(
            title="Welcome to CoRamTix Hosting!",
            description="To ensure a safe and productive environment, please adhere to the following rules. Click **✅ Verify** below to agree and gain access to the server.",
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

        view = VerifyButton(VERIFIED_ROLE_ID)
        await channel.send(embed=embed, view=view)

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{self.bot.user} is ready!")
        self.bot.add_view(VerifyButton(VERIFIED_ROLE_ID))  # Make button persistent
        await self.send_verify_message()

async def setup(bot):
    await bot.add_cog(Fun(bot))
