import fs from 'fs';
import { SlashCommandBuilder } from 'discord.js';
const filePath = './data/autoresponses.json';

export default {
  data: new SlashCommandBuilder()
    .setName('addresponse')
    .setDescription('Add an auto-response')
    .addStringOption(opt => opt.setName('trigger').setDescription('Trigger word').setRequired(true))
    .addStringOption(opt => opt.setName('response').setDescription('Bot reply').setRequired(true)),
  
  async execute(interaction) {
    const trigger = interaction.options.getString('trigger').toLowerCase();
    const response = interaction.options.getString('response');
    let data = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    data[trigger] = response;
    fs.writeFileSync(filePath, JSON.stringify(data, null, 2));
    await interaction.reply(`✅ Response for "${trigger}" added!`);
  }
};
