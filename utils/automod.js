const badWords = ['badword1', 'badword2', 'discord.gg'];

export function checkMessage(message) {
  return badWords.some(word => message.content.toLowerCase().includes(word));
}
