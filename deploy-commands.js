import { REST, Routes } from 'discord.js';
import fs from 'fs';
import dotenv from 'dotenv';
dotenv.config();

const commands = [];
const commandFiles = fs.readdirSync('./commands').filter(file => file.endsWith('.js'));

for (const file of commandFiles) {
  const command = await import(`./commands/${file}`);
  commands.push(command.default.data.toJSON());
}

const rest = new REST({ version: '10' }).setToken(process.env.TOKEN);

try {
  console.log('📤 Deploying commands...');
  await rest.put(
    Routes.applicationCommands(process.env.CLIENT_ID),
    { body: commands }
  );
  console.log('✅ Commands deployed!');
} catch (err) {
  console.error(err);
}
