// commands/hello.js
import { SlashCommandBuilder } from 'discord.js';

export default {
    data: new SlashCommandBuilder()
        .setName('hello')
        .setDescription('Says hello to you!'),
    async execute(interaction) {
        await interaction.reply(`Hello, ${interaction.user.toString()}!`);
    },
};
