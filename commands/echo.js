// commands/echo.js
import { SlashCommandBuilder } from 'discord.js';

export default {
    data: new SlashCommandBuilder()
        .setName('echo')
        .setDescription('Repeats your message.')
        .addStringOption(option =>
            option.setName('input') // The name of the option
                .setDescription('The message to echo back.') // Description of the option
                .setRequired(true)), // Make this option mandatory

    async execute(interaction) {
        const input = interaction.options.getString('input'); // Get the value of the 'input' option
        await interaction.reply(`You said: "${input}"`);
    },
};
