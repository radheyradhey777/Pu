import discord
from discord.ext import commands, tasks
from discord import app_commands, Embed
import asyncio
import random
import json
import os
from datetime import datetime, timedelta
from typing import Optional

class GiveawaySystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_giveaways = {}
        self.giveaway_data_file = "giveaways.json"
        self.load_giveaways()
        self.check_giveaways.start()

    def cog_unload(self):
        self.check_giveaways.cancel()
        self.save_giveaways()

    def load_giveaways(self):
        """Load active giveaways from file"""
        try:
            if os.path.exists(self.giveaway_data_file):
                with open(self.giveaway_data_file, 'r') as f:
                    data = json.load(f)
                    self.active_giveaways = data
        except Exception as e:
            print(f"Error loading giveaways: {e}")
            self.active_giveaways = {}

    def save_giveaways(self):
        """Save active giveaways to file"""
        try:
            with open(self.giveaway_data_file, 'w') as f:
                json.dump(self.active_giveaways, f, indent=2, default=str)
        except Exception as e:
            print(f"Error saving giveaways: {e}")

    @app_commands.command(name="giveaway", description="Create a professional giveaway")
    @app_commands.describe(
        prize="The prize for the giveaway",
        duration="Duration in minutes (default: 1440 = 24 hours)",
        winners="Number of winners (default: 1)",
        requirements="Special requirements to join (optional)"
    )
    async def create_giveaway(
        self, 
        interaction: discord.Interaction, 
        prize: str,
        duration: Optional[int] = 1440,  # 24 hours default
        winners: Optional[int] = 1,
        requirements: Optional[str] = None
    ):
        # Validate inputs
        if duration < 1 or duration > 10080:  # Max 1 week
            await interaction.response.send_message("❌ Duration must be between 1 minute and 1 week!", ephemeral=True)
            return
        
        if winners < 1 or winners > 20:
            await interaction.response.send_message("❌ Number of winners must be between 1 and 20!", ephemeral=True)
            return

        if len(prize) > 256:
            await interaction.response.send_message("❌ Prize description too long! Maximum 256 characters.", ephemeral=True)
            return

        # Calculate end time
        end_time = datetime.utcnow() + timedelta(minutes=duration)
        
        # Create embed
        embed = discord.Embed(
            title="🎉 **GIVEAWAY** 🎉",
            color=0x00ff00,
            timestamp=end_time
        )
        
        embed.add_field(
            name="🏆 Prize",
            value=f"```{prize}```",
            inline=False
        )
        
        embed.add_field(
            name="👥 Winners",
            value=f"```{winners} winner{'s' if winners > 1 else ''}```",
            inline=True
        )
        
        embed.add_field(
            name="⏰ Duration",
            value=f"```{duration} minute{'s' if duration != 1 else ''}```",
            inline=True
        )
        
        if requirements:
            embed.add_field(
                name="📋 Requirements",
                value=f"```{requirements}```",
                inline=False
            )
        
        embed.add_field(
            name="🎯 How to Join",
            value="React with 🎉 to enter this giveaway!",
            inline=False
        )
        
        embed.set_footer(
            text="Ends at",
            icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
        )
        
        embed.set_author(
            name=f"Hosted by {interaction.user.display_name}",
            icon_url=interaction.user.avatar.url if interaction.user.avatar else None
        )

        # Send the giveaway message
        await interaction.response.send_message("Creating your giveaway...", ephemeral=True)
        msg = await interaction.followup.send(embed=embed)
        await msg.add_reaction("🎉")

        # Store giveaway data
        giveaway_id = str(msg.id)
        self.active_giveaways[giveaway_id] = {
            "message_id": msg.id,
            "channel_id": msg.channel.id,
            "guild_id": interaction.guild.id,
            "host_id": interaction.user.id,
            "prize": prize,
            "winners": winners,
            "end_time": end_time.isoformat(),
            "requirements": requirements,
            "ended": False
        }
        
        self.save_giveaways()
        
        await interaction.edit_original_response(
            content=f"✅ Giveaway created successfully! It will end <t:{int(end_time.timestamp())}:R>"
        )

    @app_commands.command(name="reroll", description="Reroll a giveaway")
    @app_commands.describe(message_id="The message ID of the giveaway to reroll")
    async def reroll_giveaway(self, interaction: discord.Interaction, message_id: str):
        if message_id not in self.active_giveaways:
            await interaction.response.send_message("❌ Giveaway not found!", ephemeral=True)
            return

        giveaway = self.active_giveaways[message_id]
        
        if not giveaway.get("ended", False):
            await interaction.response.send_message("❌ This giveaway hasn't ended yet!", ephemeral=True)
            return

        try:
            channel = self.bot.get_channel(giveaway["channel_id"])
            message = await channel.fetch_message(int(message_id))
            
            # Get reaction users
            reaction = discord.utils.get(message.reactions, emoji="🎉")
            if not reaction:
                await interaction.response.send_message("❌ No reactions found on this giveaway!", ephemeral=True)
                return

            users = [user async for user in reaction.users() if not user.bot]
            
            if len(users) == 0:
                await interaction.response.send_message("❌ No valid participants found!", ephemeral=True)
                return

            winners_count = min(giveaway["winners"], len(users))
            winners = random.sample(users, winners_count)

            # Create winner announcement
            embed = discord.Embed(
                title="🎉 Giveaway Rerolled! 🎉",
                color=0xffd700,
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(
                name="🏆 Prize",
                value=f"```{giveaway['prize']}```",
                inline=False
            )
            
            winners_mention = ", ".join([winner.mention for winner in winners])
            embed.add_field(
                name=f"🎊 New Winner{'s' if len(winners) > 1 else ''}",
                value=winners_mention,
                inline=False
            )
            
            embed.set_footer(text="Rerolled by " + interaction.user.display_name)

            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Error rerolling giveaway: {str(e)}", ephemeral=True)

    @app_commands.command(name="end", description="End a giveaway early")
    @app_commands.describe(message_id="The message ID of the giveaway to end")
    async def end_giveaway(self, interaction: discord.Interaction, message_id: str):
        if message_id not in self.active_giveaways:
            await interaction.response.send_message("❌ Giveaway not found!", ephemeral=True)
            return

        giveaway = self.active_giveaways[message_id]
        
        # Check if user is host or has manage messages permission
        if (interaction.user.id != giveaway["host_id"] and 
            not interaction.user.guild_permissions.manage_messages):
            await interaction.response.send_message("❌ You don't have permission to end this giveaway!", ephemeral=True)
            return

        if giveaway.get("ended", False):
            await interaction.response.send_message("❌ This giveaway has already ended!", ephemeral=True)
            return

        await interaction.response.send_message("Ending giveaway...", ephemeral=True)
        await self.end_giveaway_by_id(message_id, early_end=True)
        await interaction.edit_original_response(content="✅ Giveaway ended successfully!")

    async def end_giveaway_by_id(self, giveaway_id: str, early_end: bool = False):
        """End a specific giveaway"""
        try:
            giveaway = self.active_giveaways[giveaway_id]
            channel = self.bot.get_channel(giveaway["channel_id"])
            message = await channel.fetch_message(giveaway["message_id"])
            
            # Get reaction users
            reaction = discord.utils.get(message.reactions, emoji="🎉")
            if not reaction:
                # No participants
                embed = discord.Embed(
                    title="🎉 Giveaway Ended 🎉",
                    description="No one participated in this giveaway!",
                    color=0xff0000,
                    timestamp=datetime.utcnow()
                )
                await channel.send(embed=embed)
                self.active_giveaways[giveaway_id]["ended"] = True
                self.save_giveaways()
                return

            users = [user async for user in reaction.users() if not user.bot]
            
            if len(users) == 0:
                # No valid participants
                embed = discord.Embed(
                    title="🎉 Giveaway Ended 🎉",
                    description="No valid participants found!",
                    color=0xff0000,
                    timestamp=datetime.utcnow()
                )
                await channel.send(embed=embed)
                self.active_giveaways[giveaway_id]["ended"] = True
                self.save_giveaways()
                return

            # Select winners
            winners_count = min(giveaway["winners"], len(users))
            winners = random.sample(users, winners_count)

            # Create winner announcement
            embed = discord.Embed(
                title="🎉 Giveaway Ended! 🎉",
                color=0xffd700,
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(
                name="🏆 Prize",
                value=f"```{giveaway['prize']}```",
                inline=False
            )
            
            winners_mention = ", ".join([winner.mention for winner in winners])
            embed.add_field(
                name=f"🎊 Winner{'s' if len(winners) > 1 else ''}",
                value=winners_mention,
                inline=False
            )
            
            embed.add_field(
                name="📊 Participants",
                value=f"```{len(users)} participant{'s' if len(users) != 1 else ''}```",
                inline=True
            )
            
            if early_end:
                embed.set_footer(text="Ended early")
            else:
                embed.set_footer(text="Giveaway completed")

            # Send winner announcement
            await channel.send(embed=embed)
            
            # Mark as ended
            self.active_giveaways[giveaway_id]["ended"] = True
            self.save_giveaways()

        except Exception as e:
            print(f"Error ending giveaway {giveaway_id}: {e}")

    @tasks.loop(minutes=1)
    async def check_giveaways(self):
        """Check for giveaways that need to end"""
        current_time = datetime.utcnow()
        ended_giveaways = []
        
        for giveaway_id, giveaway in self.active_giveaways.items():
            if giveaway.get("ended", False):
                continue
                
            end_time = datetime.fromisoformat(giveaway["end_time"])
            if current_time >= end_time:
                await self.end_giveaway_by_id(giveaway_id)
                ended_giveaways.append(giveaway_id)

    @check_giveaways.before_loop
    async def before_check_giveaways(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="giveaways", description="List all active giveaways")
    async def list_giveaways(self, interaction: discord.Interaction):
        active = [g for g in self.active_giveaways.values() if not g.get("ended", False)]
        
        if not active:
            await interaction.response.send_message("No active giveaways found!", ephemeral=True)
            return

        embed = discord.Embed(
            title="🎉 Active Giveaways",
            color=0x00ff00,
            timestamp=datetime.utcnow()
        )

        for giveaway in active[:10]:  # Limit to 10 to avoid embed limits
            end_time = datetime.fromisoformat(giveaway["end_time"])
            embed.add_field(
                name=f"🏆 {giveaway['prize'][:50]}{'...' if len(giveaway['prize']) > 50 else ''}",
                value=f"Ends <t:{int(end_time.timestamp())}:R>\nMessage ID: `{giveaway['message_id']}`",
                inline=False
            )

        embed.set_footer(text=f"Showing {min(len(active), 10)} of {len(active)} active giveaways")
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(GiveawaySystem(bot))
