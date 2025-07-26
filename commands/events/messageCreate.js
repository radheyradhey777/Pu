import fs from 'fs';
const responses = JSON.parse(fs.readFileSync('./data/autoresponses.json', 'utf8'));

export default async (message) => {
  if (message.author.bot) return;
  const content = message.content.toLowerCase();
  for (const key in responses) {
    if (content.includes(key)) {
      message.reply(responses[key]);
      break;
    }
  }
};
