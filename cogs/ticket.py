import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import json
import os
import datetime
from typing import Optional, List, Dict, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TICKET_CONFIG_FILE = "ticket_config.json"
TICKET_TRANSCRIPTS_DIR = "ticket_transcripts"

# === Persistent Storage ===
class TicketStorage:
    @staticmethod
    def save(data: List[Dict[Any, Any]]) -> None:
        """Save ticket configuration to file"""
        try:
            os.makedirs(os.path.dirname(TICKET_CONFIG_FILE), exist_ok=True)
            with open(TICKET_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save ticket config: {e}")

    @staticmethod
    def load() -> List[Dict[Any, Any]]:
        """Load ticket configuration from file"""
        try:
            if not os.path.exists(TICKET_CONFIG_FILE):
                return []
            with open(TICKET_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load ticket config: {e}")
            return []

    @staticmethod
    def save_transcript(channel_name: str, messages: List[str]) -> str:
        """Save ticket transcript"""
        try:
            os.makedirs(TICKET_TRANSCRIPTS_DIR, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{channel_name}_{timestamp}.txt"
            filepath = os.path.join(TICKET_TRANSCRIPTS_DIR, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"Ticket Transcript: {channel_name}\n")
                f.write(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 50 + "\n\n")
                f.write("\n".join(messages))
            
            return filepath
        except Exception as e:
            logger.error(f"Failed to save transcript: {e}")
            return None

# === Utility Functions ===
class TicketUtils:
    @staticmethod
    def create_embed(title: str, description: str, color: discord.Color = discord.Color.blue(), **kwargs) -> discord.Embed:
        """Create a standardized embed"""
        embed = discord.Embed(title=title, description=description, color=color)
        embed.timestamp = datetime.datetime.utcnow()
        
        for key, value in kwargs.items():
            if key == 'footer':
                embed.set_footer(text=value)
            elif key == 'thumbnail':
                embed.set_thumbnail(url=value)
            elif key == 'image':
                embed.set_image(url=value)
            elif key == 'author':
                embed.set_author(name=value.get('name', ''), icon_url=value.get('icon_url', ''))
        
        return embed

    @staticmethod
    def sanitize_channel_name(name: str, max_length: int = 90) -> str:
        """Sanitize channel name for Discord requirements"""
        # Remove emojis and special characters
        import re
        name = re.sub(r'[^\w\s-]', '', name)
        name = name.lower().replace(' ', '-').strip('-')
        return name[:max_length]

    @staticmethod
    async def get_channel_messages(channel: discord.TextChannel, limit: int = 100) -> List[str]:
        """Get formatted messages from a channel for transcript"""
        messages = []
        try:
            async for message in channel.history(limit=limit, oldest_first=True):
                timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
                content = message.content or "[No text content]"
                
                # Handle attachments
                if message.attachments:
                    attachments = ", ".join([att.filename for att in message.attachments])
                    content += f" [Attachments: {attachments}]"
                
                # Handle embeds
                if message.embeds:
                    content += f" [Embeds: {len(message.embeds)}]"
                
                messages.append(f"[{timestamp}] {message.author}: {content}")
        except Exception as e:
            logger.error(f"Failed to get channel messages: {e}")
        
        return messages

# === Main Cog ===
class TicketCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_tickets = {}  # Track active tickets per user

    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.command(name="ticket-setup", description="Create a professional ticket panel")
    @app_commands.describe(
        panel_channel="Channel where the ticket panel will be posted",
        category="Category where ticket channels will be created",
        log_channel="Channel for ticket activity logs",
        staff_role="Role that can manage tickets (optional)",
        title="Title for the ticket panel embed",
        description="Description for the ticket panel",
        color="Embed color (hex code, e.g., #3498db)",
        image_url="Optional image URL for the embed",
        thumbnail_url="Optional thumbnail URL for the embed",
        max_tickets_per_user="Maximum tickets per user (default: 1)",
        auto_close_hours="Auto-close tickets after X hours of inactivity (0 to disable)"
    )
    async def ticket_setup(
        self,
        interaction: discord.Interaction,
        panel_channel: discord.TextChannel,
        category: discord.CategoryChannel,
        log_channel: discord.TextChannel,
        title: str = "🎫 Support Tickets",
        description: str = "Need help? Click a button below to create a support ticket.",
        staff_role: Optional[discord.Role] = None,
        color: str = "#3498db",
        image_url: Optional[str] = None,
        thumbnail_url: Optional[str] = None,
        max_tickets_per_user: int = 1,
        auto_close_hours: int = 24
    ):
        """Setup the ticket system"""
        await interaction.response.defer(ephemeral=True)

        try:
            # Parse color
            try:
                embed_color = discord.Color(int(color.replace('#', ''), 16))
            except ValueError:
                embed_color = discord.Color.blue()

            # Create embed
            embed = TicketUtils.create_embed(
                title=title,
                description=description,
                color=embed_color,
                footer="Professional Ticket System",
                thumbnail=thumbnail_url,
                image=image_url
            )

            # Create view
            view = TicketPanelView(
                category_id=category.id,
                log_channel_id=log_channel.id,
                staff_role_id=staff_role.id if staff_role else None,
                max_tickets_per_user=max_tickets_per_user,
                auto_close_hours=auto_close_hours
            )

            # Send the panel
            panel_message = await panel_channel.send(embed=embed, view=view)

            # Save configuration
            config_data = TicketStorage.load()
            new_config = {
                "guild_id": interaction.guild.id,
                "panel_message_id": panel_message.id,
                "panel_channel_id": panel_channel.id,
                "category_id": category.id,
                "log_channel_id": log_channel.id,
                "staff_role_id": staff_role.id if staff_role else None,
                "max_tickets_per_user": max_tickets_per_user,
                "auto_close_hours": auto_close_hours,
                "embed_config": {
                    "title": title,
                    "description": description,
                    "color": color,
                    "image_url": image_url,
                    "thumbnail_url": thumbnail_url
                }
            }
            
            config_data.append(new_config)
            TicketStorage.save(config_data)

            success_embed = TicketUtils.create_embed(
                "✅ Ticket System Setup Complete",
                f"**Panel Channel:** {panel_channel.mention}\n"
                f"**Category:** {category.name}\n"
                f"**Log Channel:** {log_channel.mention}\n"
                f"**Staff Role:** {staff_role.mention if staff_role else 'None'}\n"
                f"**Max Tickets/User:** {max_tickets_per_user}\n"
                f"**Auto-close:** {auto_close_hours}h",
                discord.Color.green()
            )

            await interaction.followup.send(embed=success_embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Ticket setup error: {e}")
            error_embed = TicketUtils.create_embed(
                "❌ Setup Failed",
                f"An error occurred during setup: {str(e)}",
                discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

    @ticket_setup.error
    async def ticket_setup_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.errors.MissingPermissions):
            embed = TicketUtils.create_embed(
                "🚫 Permission Denied",
                "You need **Administrator** permissions to use this command.",
                discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.checks.has_permissions(manage_channels=True)
    @app_commands.command(name="ticket-stats", description="View ticket system statistics")
    async def ticket_stats(self, interaction: discord.Interaction):
        """Display ticket statistics"""
        category_channels = [ch for ch in interaction.guild.channels if isinstance(ch, discord.CategoryChannel)]
        ticket_channels = []
        
        for category in category_channels:
            for channel in category.text_channels:
                if channel.topic and "User ID:" in channel.topic:
                    ticket_channels.append(channel)

        embed = TicketUtils.create_embed(
            "📊 Ticket System Statistics",
            f"**Active Tickets:** {len(ticket_channels)}\n"
            f"**Total Categories:** {len(category_channels)}\n"
            f"**Transcript Files:** {len(os.listdir(TICKET_TRANSCRIPTS_DIR)) if os.path.exists(TICKET_TRANSCRIPTS_DIR) else 0}",
            discord.Color.blue()
        )

        if ticket_channels:
            recent_tickets = sorted(ticket_channels, key=lambda x: x.created_at, reverse=True)[:5]
            ticket_list = "\n".join([f"• {ch.mention} ({ch.created_at.strftime('%m/%d %H:%M')})" for ch in recent_tickets])
            embed.add_field(name="Recent Tickets", value=ticket_list, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

# === Ticket Panel View ===
class TicketPanelView(discord.ui.View):
    def __init__(self, category_id: int, log_channel_id: int, staff_role_id: Optional[int] = None, 
                 max_tickets_per_user: int = 1, auto_close_hours: int = 24):
        super().__init__(timeout=None)
        self.category_id = category_id
        self.log_channel_id = log_channel_id
        self.staff_role_id = staff_role_id
        self.max_tickets_per_user = max_tickets_per_user
        self.auto_close_hours = auto_close_hours

    @discord.ui.button(label="General Support", style=discord.ButtonStyle.primary, emoji="🎫")
    async def general_support(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "General Support", "🎫")

    @discord.ui.button(label="Technical Issue", style=discord.ButtonStyle.danger, emoji="🔧")
    async def technical_issue(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "Technical Issue", "🔧")

    @discord.ui.button(label="Bug Report", style=discord.ButtonStyle.secondary, emoji="🐛")
    async def bug_report(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "Bug Report", "🐛")

    @discord.ui.button(label="Feature Request", style=discord.ButtonStyle.success, emoji="💡")
    async def feature_request(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "Feature Request", "💡")

    async def create_ticket(self, interaction: discord.Interaction, ticket_type: str, emoji: str):
        """Create a new ticket"""
        await interaction.response.defer(ephemeral=True)

        try:
            guild = interaction.guild
            category = guild.get_channel(self.category_id)
            log_channel = guild.get_channel(self.log_channel_id)
            user = interaction.user

            if not category:
                raise ValueError("Ticket category not found")

            # Check existing tickets
            existing_tickets = [ch for ch in category.text_channels 
                             if ch.topic and str(user.id) in ch.topic]

            if len(existing_tickets) >= self.max_tickets_per_user:
                embed = TicketUtils.create_embed(
                    "⚠️ Ticket Limit Reached",
                    f"You already have {len(existing_tickets)} active ticket(s).\n"
                    f"Please close existing tickets before creating new ones.\n\n"
                    f"**Your active tickets:**\n" + 
                    "\n".join([f"• {ch.mention}" for ch in existing_tickets]),
                    discord.Color.orange()
                )
                return await interaction.followup.send(embed=embed, ephemeral=True)

            # Create channel overwrites
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                user: discord.PermissionOverwrite(
                    view_channel=True, 
                    send_messages=True, 
                    read_message_history=True,
                    attach_files=True
                ),
                guild.me: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    manage_messages=True,
                    read_message_history=True
                )
            }

            # Add staff role permissions
            if self.staff_role_id:
                staff_role = guild.get_role(self.staff_role_id)
                if staff_role:
                    overwrites[staff_role] = discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True,
                        manage_messages=True
                    )

            # Create ticket channel
            channel_name = TicketUtils.sanitize_channel_name(f"{ticket_type}-{user.name}")
            ticket_channel = await guild.create_text_channel(
                name=channel_name,
                overwrites=overwrites,
                category=category,
                topic=f"🎫 {ticket_type} | Created by {user} | User ID: {user.id} | Created: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            # Create welcome embed
            welcome_embed = TicketUtils.create_embed(
                f"{emoji} {ticket_type} Ticket",
                f"Hello {user.mention}! 👋\n\n"
                f"Thank you for creating a **{ticket_type}** ticket.\n"
                f"Please describe your issue in detail and a staff member will assist you shortly.\n\n"
                f"**Guidelines:**\n"
                f"• Be respectful and patient\n"
                f"• Provide as much detail as possible\n"
                f"• Attach screenshots if relevant\n"
                f"• Wait for staff response before bumping",
                discord.Color.blue(),
                footer=f"Ticket ID: {ticket_channel.id}",
                thumbnail=user.display_avatar.url
            )

            # Create ticket management view
            management_view = TicketManagementView(
                ticket_channel=ticket_channel,
                log_channel=log_channel,
                creator=user,
                staff_role_id=self.staff_role_id,
                ticket_type=ticket_type
            )

            await ticket_channel.send(embed=welcome_embed, view=management_view)

            # Ping staff if role exists
            if self.staff_role_id:
                staff_role = guild.get_role(self.staff_role_id)
                if staff_role:
                    staff_embed = TicketUtils.create_embed(
                        "🔔 New Ticket Alert",
                        f"**Type:** {ticket_type}\n"
                        f"**Created by:** {user.mention} ({user})\n"
                        f"**User ID:** `{user.id}`\n"
                        f"**Channel:** {ticket_channel.mention}",
                        discord.Color.gold(),
                        author={"name": user.display_name, "icon_url": user.display_avatar.url}
                    )
                    await ticket_channel.send(content=staff_role.mention, embed=staff_embed)

            # Log ticket creation
            if log_channel:
                log_embed = TicketUtils.create_embed(
                    "📝 Ticket Created",
                    f"**User:** {user.mention}\n"
                    f"**Type:** {ticket_type}\n"
                    f"**Channel:** {ticket_channel.mention}",
                    discord.Color.green()
                )
                await log_channel.send(embed=log_embed)

            # Success response
            success_embed = TicketUtils.create_embed(
                "✅ Ticket Created Successfully",
                f"Your **{ticket_type}** ticket has been created!\n"
                f"**Channel:** {ticket_channel.mention}\n\n"
                f"You can access your ticket anytime by clicking the channel.",
                discord.Color.green()
            )
            await interaction.followup.send(embed=success_embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Ticket creation error: {e}")
            error_embed = TicketUtils.create_embed(
                "❌ Ticket Creation Failed",
                f"Sorry, there was an error creating your ticket.\n"
                f"Please try again or contact an administrator.\n\n"
                f"**Error:** {str(e)}",
                discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

# === Ticket Management View ===
class TicketManagementView(discord.ui.View):
    def __init__(self, ticket_channel: discord.TextChannel, log_channel: discord.TextChannel, 
                 creator: discord.Member, staff_role_id: Optional[int], ticket_type: str):
        super().__init__(timeout=None)
        self.ticket_channel = ticket_channel
        self.log_channel = log_channel
        self.creator = creator
        self.staff_role_id = staff_role_id
        self.ticket_type = ticket_type
        self.claimed_by = None

    def is_staff_or_creator(self, user: discord.Member) -> bool:
        """Check if user is staff or ticket creator"""
        if user == self.creator:
            return True
        if self.staff_role_id is None:
            return user.guild_permissions.manage_channels
        return discord.utils.get(user.roles, id=self.staff_role_id) is not None

    def is_staff(self, user: discord.Member) -> bool:
        """Check if user is staff"""
        if self.staff_role_id is None:
            return user.guild_permissions.manage_channels
        return discord.utils.get(user.roles, id=self.staff_role_id) is not None

    @discord.ui.button(label="Claim Ticket", style=discord.ButtonStyle.primary, emoji="🙋‍♂️")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_staff(interaction.user):
            embed = TicketUtils.create_embed(
                "🚫 Access Denied",
                "Only staff members can claim tickets.",
                discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if self.claimed_by:
            embed = TicketUtils.create_embed(
                "⚠️ Already Claimed",
                f"This ticket is already claimed by {self.claimed_by.mention}.",
                discord.Color.orange()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        self.claimed_by = interaction.user
        
        # Update permissions
        await self.ticket_channel.set_permissions(
            interaction.user, 
            view_channel=True, 
            send_messages=True, 
            manage_messages=True
        )

        claim_embed = TicketUtils.create_embed(
            "🙋‍♂️ Ticket Claimed",
            f"{interaction.user.mention} has claimed this ticket and will assist you.",
            discord.Color.blue(),
            author={"name": interaction.user.display_name, "icon_url": interaction.user.display_avatar.url}
        )

        button.label = f"Claimed by {interaction.user.display_name}"
        button.disabled = True
        button.style = discord.ButtonStyle.success

        await interaction.response.edit_message(view=self)
        await self.ticket_channel.send(embed=claim_embed)

        if self.log_channel:
            log_embed = TicketUtils.create_embed(
                "🙋‍♂️ Ticket Claimed",
                f"**Staff:** {interaction.user.mention}\n"
                f"**Ticket:** {self.ticket_channel.mention}\n"
                f"**Creator:** {self.creator.mention}",
                discord.Color.blue()
            )
            await self.log_channel.send(embed=log_embed)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_staff_or_creator(interaction.user):
            embed = TicketUtils.create_embed(
                "🚫 Access Denied",
                "Only staff members or the ticket creator can close tickets.",
                discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Create confirmation view
        confirm_view = TicketCloseConfirmView(self.ticket_channel, self.log_channel, 
                                            self.creator, interaction.user, self.ticket_type)
        
        confirm_embed = TicketUtils.create_embed(
            "⚠️ Confirm Ticket Closure",
            f"Are you sure you want to close this ticket?\n\n"
            f"**Type:** {self.ticket_type}\n"
            f"**Creator:** {self.creator.mention}\n"
            f"**Closing Staff:** {interaction.user.mention}\n\n"
            f"This action cannot be undone, but a transcript will be saved.",
            discord.Color.orange()
        )

        await interaction.response.send_message(embed=confirm_embed, view=confirm_view, ephemeral=True)

    @discord.ui.button(label="Add User", style=discord.ButtonStyle.secondary, emoji="👥")
    async def add_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_staff(interaction.user):
            embed = TicketUtils.create_embed(
                "🚫 Access Denied",
                "Only staff members can add users to tickets.",
                discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        modal = AddUserModal(self.ticket_channel, self.log_channel)
        await interaction.response.send_modal(modal)

# === Close Confirmation View ===
class TicketCloseConfirmView(discord.ui.View):
    def __init__(self, ticket_channel: discord.TextChannel, log_channel: discord.TextChannel,
                 creator: discord.Member, closer: discord.Member, ticket_type: str):
        super().__init__(timeout=30)
        self.ticket_channel = ticket_channel
        self.log_channel = log_channel
        self.creator = creator
        self.closer = closer
        self.ticket_type = ticket_type

    @discord.ui.button(label="Yes, Close Ticket", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

        try:
            # Get transcript
            messages = await TicketUtils.get_channel_messages(self.ticket_channel)
            transcript_path = TicketStorage.save_transcript(self.ticket_channel.name, messages)

            # Send closing message
            close_embed = TicketUtils.create_embed(
                "🔒 Ticket Closing",
                f"This ticket is being closed by {self.closer.mention}.\n"
                f"Channel will be deleted in 10 seconds...",
                discord.Color.red(),
                footer="Thank you for using our support system!"
            )
            
            await self.ticket_channel.send(embed=close_embed)

            # Log closure
            if self.log_channel:
                log_embed = TicketUtils.create_embed(
                    "🔒 Ticket Closed",
                    f"**Creator:** {self.creator.mention}\n"
                    f"**Closed by:** {self.closer.mention}\n"
                    f"**Type:** {self.ticket_type}\n"
                    f"**Transcript:** {'✅ Saved' if transcript_path else '❌ Failed'}",
                    discord.Color.red()
                )
                
                if transcript_path and os.path.exists(transcript_path):
                    with open(transcript_path, 'rb') as f:
                        transcript_file = discord.File(f, filename=f"{self.ticket_channel.name}_transcript.txt")
                        await self.log_channel.send(embed=log_embed, file=transcript_file)
                else:
                    await self.log_channel.send(embed=log_embed)

            # Wait and delete
            await asyncio.sleep(10)
            await self.ticket_channel.delete(reason=f"Ticket closed by {self.closer}")

        except Exception as e:
            logger.error(f"Error closing ticket: {e}")
            error_embed = TicketUtils.create_embed(
                "❌ Close Error",
                f"Failed to close ticket properly: {str(e)}",
                discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        cancel_embed = TicketUtils.create_embed(
            "✅ Cancelled",
            "Ticket closure has been cancelled.",
            discord.Color.green()
        )
        await interaction.response.edit_message(embed=cancel_embed, view=None)

# === Add User Modal ===
class AddUserModal(discord.ui.Modal, title="Add User to Ticket"):
    def __init__(self, ticket_channel: discord.TextChannel, log_channel: discord.TextChannel):
        super().__init__()
        self.ticket_channel = ticket_channel
        self.log_channel = log_channel

    user_input = discord.ui.TextInput(
        label="User ID or Mention",
        placeholder="Enter user ID (e.g., 123456789) or mention (@user)",
        required=True,
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Parse user input
            user_id_str = self.user_input.value.strip().replace('<@', '').replace('!', '').replace('>', '')
            user_id = int(user_id_str)
            
            user = interaction.guild.get_member(user_id)
            if not user:
                raise ValueError("User not found in this server")

            # Add permissions
            await self.ticket_channel.set_permissions(
                user,
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )

            success_embed = TicketUtils.create_embed(
                "✅ User Added",
                f"{user.mention} has been added to this ticket.",
                discord.Color.green()
            )
            
            await interaction.response.send_message(embed=success_embed)
            await self.ticket_channel.send(f"👋 {user.mention} has been added to this ticket!")

            if self.log_channel:
                log_embed = TicketUtils.create_embed(
                    "👥 User Added to Ticket",
                    f"**Added User:** {user.mention}\n"
                    f"**Added by:** {interaction.user.mention}\n"
                    f"**Ticket:** {self.ticket_channel.mention}",
                    discord.Color.blue()
                )
                await self.log_channel.send(embed=log_embed)

        except ValueError as e:
            error_embed = TicketUtils.create_embed(
                "❌ Invalid Input",
                "Please provide a valid user ID or mention.",
                discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error adding user: {e}")
            error_embed = TicketUtils.create_embed(
                "❌ Error",
                f"Failed to add user: {str(e)}",
                discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)

# === Setup Function ===
async def setup(bot: commands.Bot):
    """Setup function for the cog"""
    await bot.add_cog(TicketCog(bot))
    
    # Register persistent views on bot restart
    try:
        config_data = Ticket
