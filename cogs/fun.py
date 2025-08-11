import discord
from discord.ext import commands

# Put your IDs here or load from config
TARGET_ROLE_ID = 1404526602649341963
TARGET_CHANNEL_ID = 1404105990198001664

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("Fun Cog loaded successfully.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setupverify(self, ctx):
        """Posts the verification message and adds a reaction."""
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

        await ctx.message.delete()
        msg = await ctx.send(embed=embed)
        await msg.add_reaction("✅")

    @setupverify.error
    async def setupverify_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You do not have permission to use this command.", delete_after=10)

    @commands.command()
    async def hello(self, ctx):
        await ctx.send(f"Hello, {ctx.author.mention}!")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return
        await self.bot.process_commands(message)
        if not message.guild:
            return

        target_role = discord.utils.get(message.author.roles, id=TARGET_ROLE_ID)
        if target_role:
            target_channel = self.bot.get_channel(TARGET_CHANNEL_ID)
            if target_channel:
                alert_msg = (
                    f"**Alert!** A message was sent by a user with the '{target_role.name}' role.\n"
                    f"> **User:** {message.author.mention} (`{message.author.id}`)\n"
                    f"> **Channel:** {message.channel.mention}\n"
                    f"> **Message:** {message.content}\n"
                    f"> [Jump to Message]({message.jump_url})"
                )
                await target_channel.send(alert_msg)
            else:
                print(f"Error: Could not find channel with ID {TARGET_CHANNEL_ID}")

async def setup(bot):
    await bot.add_cog(Fun(bot))
