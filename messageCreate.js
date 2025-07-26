import { checkMessage } from '../utils/automod.js';

export default async (message) => {
  if (message.author.bot) return;

  // Auto-response
  // ...

  if (checkMessage(message)) {
    await message.delete().catch(() => {});
    await message.channel.send(`${message.author}, that message was not allowed.`);
  }
};
