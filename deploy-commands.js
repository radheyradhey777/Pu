// deploy-commands.js
// This script is used to register your slash commands with Discord.
// You run this script separately to update your commands.

import { REST } from '@discordjs/rest';
import { Routes } from 'discord-api-types/v10';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';

// --- Configuration ---
const BOT_TOKEN = 'YOUR_BOT_TOKEN'; // <<< IMPORTANT: Replace with your bot's token!
const CLIENT_ID = 'YOUR_CLIENT_ID'; // <<< IMPORTANT: Replace with your bot's Client ID!
// If you want to deploy commands to a specific guild immediately for testing,
// uncomment and set GUILD_ID. For a public bot, you'll typically deploy globally.
// const GUILD_ID = 'YOUR_GUILD_ID'; // <<< Optional: For testing in a single guild

// Resolve __dirname equivalent for ES Modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const commands = [];
// Grab all the command files from the commands directory you created
const commandsPath = path.join(__dirname, 'commands');
const commandFiles = fs.readdirSync(commandsPath).filter(file => file.endsWith('.js'));

// Grab the SlashCommandBuilder#toJSON() output of each command's data for deployment
for (const file of commandFiles) {
    const filePath = path.join(commandsPath, file);
    // Use dynamic import for ES Modules
    import(filePath)
        .then(module => {
            const command = module.default;
            if ('data' in command && 'execute' in command) {
                commands.push(command.data.toJSON());
            } else {
                console.warn(`[WARNING] The command at ${filePath} is missing a required "data" or "execute" property.`);
            }
        })
        .catch(error => {
            console.error(`Error loading command file ${filePath}:`, error);
        });
}

// Construct and prepare an instance of the REST module
const rest = new REST({ version: '10' }).setToken(BOT_TOKEN);

// Deploy your commands!
(async () => {
    try {
        console.log(`Started refreshing ${commands.length} application (/) commands.`);

        // The put method is used to fully refresh all commands in the guild with the current set
        // For global commands:
        const data = await rest.put(
            Routes.applicationCommands(CLIENT_ID), // For global commands
            // Routes.applicationGuildCommands(CLIENT_ID, GUILD_ID), // For guild-specific commands (testing)
            { body: commands },
        );

        console.log(`Successfully reloaded ${data.length} application (/) commands.`);
    } catch (error) {
        // And of course, make sure you catch and log any errors!
        console.error(error);
    }
})();


