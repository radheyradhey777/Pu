// commands/ping.js
import { SlashCommandBuilder } from 'discord.js';

export default {
    // The data property is used to register the slash command with Discord.
    data: new SlashCommandBuilder()
        .setName('ping') // The name of the command (what users type)
        .setDescription('Replies with Pong!'), // A brief description of the command

    // The execute method contains the logic for the command.
    async execute(interaction) {
        // Reply to the interaction.
        await interaction.reply('Pong!');
    },
};
