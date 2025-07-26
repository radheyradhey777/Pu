import { SlashCommandBuilder, EmbedBuilder } from 'discord.js';

export default {
  data: new SlashCommandBuilder()
    .setName('embed')
    .setDescription('Send a custom embed')
    .addStringOption(opt => opt.setName('title').setDescription('Title').setRequired(true))
    .addStringOption(opt => opt.setName('desc').setDescription('Description').setRequired(true)),

  async execute(interaction) {
    const title = interaction.options.getString('title');
    const desc = interaction.options.getString('desc');
    const embed = new EmbedBuilder().setTitle(title).setDescription(desc).setColor('Random');
    await interaction.reply({ embeds: [embed] });
  }
};
