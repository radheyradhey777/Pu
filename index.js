// index.js
// This is the main file for your Discord bot.

// Import necessary classes from the discord.js library
import { Client, GatewayIntentBits, Events, Collection } from 'discord.js';
import { REST } from '@discordjs/rest';
import { Routes } from 'discord-api-types/v10';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';

// --- Configuration ---
// It's highly recommended to use environment variables for sensitive information.
// For simplicity in this example, we're hardcoding, but for production, use a .env file.
// Example: process.env.DISCORD_BOT_TOKEN, process.env.CLIENT_ID
const BOT_TOKEN = 'MTM4MTMyODM2MzA1MzkxMjA3NA.Gbb0Kp.y96-QuBnYqIdMvWBz7_0VSAIGFcykYdS7_PFPs'; // <<< IMPORTANT: Replace with your bot's token!
const CLIENT_ID = '1375756602216284223'; // <<< IMPORTANT: Replace with your bot's Client ID!

// Define the bot's command prefix for traditional text commands.
// Note: Slash commands are generally preferred in modern Discord.js bots.
const COMMAND_PREFIX = '&';

// Define intents. Intents specify which events your bot wants to receive from Discord.
// For a public bot, you often need specific intents enabled in the Discord Developer Portal
// and here in your code.
const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,           // Required for guild-related events (e.g., guildMemberAdd)
        GatewayIntentBits.GuildMessages,    // Required for message-related events (e.g., messageCreate)
        GatewayIntentBits.MessageContent,   // REQUIRED for accessing message content in commands (Discord.js v13+)
        GatewayIntentBits.GuildMembers,     // Required for member join/leave events (enable in Developer Portal)
        GatewayIntentBits.DirectMessages    // Optional: for direct messages to the bot
    ],
});

// Create a collection to store commands. This is a common practice for command handling.
client.commands = new Collection();

// Resolve __dirname equivalent for ES Modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// --- Load Commands ---
// This section dynamically loads command files from a 'commands' directory.
const commandsPath = path.join(__dirname, 'commands');
const commandFiles = fs.readdirSync(commandsPath).filter(file => file.endsWith('.js'));

for (const file of commandFiles) {
    const filePath = path.join(commandsPath, file);
    // Use dynamic import for ES Modules
    import(filePath)
        .then(module => {
            const command = module.default; // Assuming commands are exported as default
            if ('data' in command && 'execute' in command) {
                client.commands.set(command.data.name, command);
            } else {
                console.warn(`[WARNING] The command at ${filePath} is missing a required "data" or "execute" property.`);
            }
        })
        .catch(error => {
            console.error(`Error loading command file ${filePath}:`, error);
        });
}


// --- Bot Events ---

// Fires when the bot successfully connects to Discord.
client.once(Events.ClientReady, c => {
    console.log(`Logged in as ${c.user.tag}`);
    console.log('Bot is ready!');
    // You can set the bot's activity here, e.g., playing a game
    c.user.setActivity('with JavaScript!', { type: 0 }); // Type 0 is 'Playing'
});

// Fires when a new member joins a guild (server) where the bot is present.
client.on(Events.GuildMemberAdd, async member => {
    console.log(`${member.user.tag} has joined the server.`);
    // Find a suitable channel to send the welcome message
    // This tries to find a channel named 'general' or the first text channel it can find.
    const channel = member.guild.channels.cache.find(ch => ch.name === 'general' && ch.type === 0) || // type 0 is GUILD_TEXT
                    member.guild.channels.cache.find(ch => ch.type === 0);

    if (channel) {
        await channel.send(`Welcome to the server, ${member.user.toString()}! We're glad to have you here.`);
    } else {
        console.warn(`Could not find a channel to welcome ${member.user.tag}.`);
    }
});

// --- Command Handling ---

// Handles slash commands (interactions)
client.on(Events.InteractionCreate, async interaction => {
    if (!interaction.isChatInputCommand()) return; // Only process chat input commands

    const command = client.commands.get(interaction.commandName);

    if (!command) {
        console.error(`No command matching ${interaction.commandName} was found.`);
        return;
    }

    try {
        await command.execute(interaction);
    } catch (error) {
        console.error(error);
        if (interaction.replied || interaction.deferred) {
            await interaction.followUp({ content: 'There was an error while executing this command!', ephemeral: true });
        } else {
            await interaction.reply({ content: 'There was an error while executing this command!', ephemeral: true });
        }
    }
});

// Handles traditional prefix commands (text messages)
client.on(Events.MessageCreate, async message => {
    // Ignore messages from bots and messages that don't start with the prefix
    if (message.author.bot || !message.content.startsWith(COMMAND_PREFIX)) {
        return;
    }

    // Extract command name and arguments
    const args = message.content.slice(COMMAND_PREFIX.length).trim().split(/ +/);
    const commandName = args.shift().toLowerCase();

    // Basic prefix command handler (for demonstration)
    if (commandName === 'hello') {
        await message.reply(`Hello, ${message.author.toString()}!`);
    } else if (commandName === 'ping') {
        await message.reply(`Pong! Latency is ${client.ws.ping}ms.`);
    } else if (commandName === 'echo') {
        if (!args.length) {
            return message.reply(`You didn't provide any arguments, ${message.author.toString()}!`);
        }
        await message.reply(args.join(' '));
    }
    // You would typically use a more robust command handler for prefix commands too,
    // similar to how slash commands are handled with client.commands.
});

// --- Error Handling ---
// Basic error handling for the client
client.on(Events.Error, error => {
    console.error('A client error has occurred:', error);
});

// --- Log in to Discord ---
// Ensure the bot token and client ID are provided.
if (BOT_TOKEN === 'YOUR_BOT_TOKEN' || !BOT_TOKEN) {
    console.error("ERROR: Please replace 'YOUR_BOT_TOKEN' in the script with your actual bot token.");
    console.error("You can get this from the Discord Developer Portal (https://discord.com/developers/applications).");
    process.exit(1); // Exit the process if token is missing
}
if (CLIENT_ID === 'YOUR_CLIENT_ID' || !CLIENT_ID) {
    console.error("ERROR: Please replace 'YOUR_CLIENT_ID' in the script with your actual bot's Client ID.");
    console.error("You can get this from the Discord Developer Portal (https://discord.com/developers/applications) under 'General Information'.");
    process.exit(1); // Exit the process if client ID is missing
}

client.login(BOT_TOKEN)
    .catch(error => {
        console.error('Failed to log in to Discord:', error);
        if (error.code === 'TOKEN_INVALIDATION') {
            console.error('Please check if your bot token is correct and valid.');
        }
        process.exit(1);
    });
