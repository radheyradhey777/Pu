import { SlashCommandBuilder, EmbedBuilder } from 'discord.js';

export default {
  data: new SlashCommandBuilder()
    .setName('giveaway')
    .setDescription('Start a giveaway')
    .addIntegerOption(opt => opt.setName('duration').setDescription('Duration in seconds').setRequired(true))
    .addStringOption(opt => opt.setName('prize').setDescription('Prize').setRequired(true)),
    
  async execute(interaction) {
    const duration = interaction.options.getInteger('duration');
    const prize = interaction.options.getString('prize');

    const embed = new EmbedBuilder()
      .setTitle('🎉 Giveaway Started!')
      .setDescription(`Prize: **${prize}**\nReact with 🎉 to enter!\nEnds in **${duration}** seconds.`)
      .setColor('Gold')
      .setTimestamp();

    const msg = await interaction.reply({ embeds: [embed], fetchReply: true });
    await msg.react('🎉');

    setTimeout(async () => {
      const msgFetched = await interaction.channel.messages.fetch(msg.id);
      const users = (await msgFetched.reactions.cache.get('🎉').users.fetch()).filter(u => !u.bot).map(u => u.id);
      const winner = users[Math.floor(Math.random() * users.length)];
      if (winner) {
        interaction.followUp(`🎊 Winner is <@${winner}>! Congrats!`);
      } else {
        interaction.followUp('❌ No valid entries.');
      }
    }, duration * 1000);
  }
};
