import discord
from discord.ext import commands
import json
import os

# === CONFIG ===
VERIFY_CHANNEL_ID = 1404105990198001664  # Channel where verify message goes
VERIFIED_ROLE_ID = 1404526602649341963   # Verified role ID
VERIFY_DATA_FILE = "verify_message.json" # Store message ID

# === VERIFY BUTTON CLASS ===
class VerifyButton(discord.ui.View):
    def __init__(self, role_id):
        super().__init__(timeout=None)  # Persistent
        self.role_id = role_id

    @discord.ui.button(label="✅ Verify", style=discord.ButtonStyle.success, custom_id="verify_button")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(self.role_id)
        if role is None:
            return await interaction.response.send_message(
                "❌ Verification role not found! Please contact staff.",
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
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Failed to verify: {e}",
                ephemeral=True
            )

# === COG CLASS ===
class VerificationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def send_or_get_verify_message(self):
        channel = self.bot.get_channel(VERIFY_CHANNEL_ID)
        if channel is None:
            print(f"Verify channel with ID {VERIFY_CHANNEL_ID} not found.")
            return

        # Check if verify message already exists in file
        if os.path.exists(VERIFY_DATA_FILE):
            with open(VERIFY_DATA_FILE, "r") as f:
                data = json.load(f)
            msg_id = data.get("message_id")

            # Try fetching existing message
            try:
                msg = await channel.fetch_message(msg_id)
                print("✅ Found existing verify message.")
                return
            except discord.NotFound:
                print("⚠️ Old verify message not found, creating new one.")

        # Create new verify embed
        embed = discord.Embed(
            title="Welcome to CoRamTix Hosting!",
            description="Please read the rules below and click the **✅ Verify** button to gain access to the server.",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Rules",
            value=(
                "1️⃣ Be respectful & civil.\n"
                "2️⃣ No spamming or advertising.\n"
                "3️⃣ Use channels correctly.\n"
                "4️⃣ Follow support etiquette.\n"
                "5️⃣ Follow Discord's ToS."
            ),
            inline=False
        )
        embed.set_footer(text="Click the button below to verify.")

        view = VerifyButton(VERIFIED_ROLE_ID)
        msg = await channel.send(embed=embed, view=view)

        # Save message ID for future restarts
        with open(VERIFY_DATA_FILE, "w") as f:
            json.dump({"message_id": msg.id}, f)

        print("✅ Sent new verify message.")

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{self.bot.user} is ready!")
        # Keep the verify button alive
        self.bot.add_view(VerifyButton(VERIFIED_ROLE_ID))
        await self.send_or_get_verify_message()

# === BOT SETUP ===
async def setup(bot):
    await bot.add_cog(VerificationCog(bot))
