require("dotenv").config();

const { Client, GatewayIntentBits, Partials } = require("discord.js");
const { commandPrefix, guildId } = require("./config");
const { loadData } = require("./data/store");
const { handleAdminCommand, handlePublicCommand } = require("./handlers/commands");
const { buildAutoReply } = require("./handlers/messages");
const { t, fallbackLang } = require("./utils/i18n");

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.DirectMessages
  ],
  partials: [Partials.Channel]
});

let isReady = false;

const shouldRespondInGuild = (message) => {
  if (!message.guild) {
    return true;
  }
  return !guildId || message.guild.id === guildId;
};

client.on("messageCreate", async (message) => {
  if (!isReady || message.author.bot) {
    return;
  }

  if (!shouldRespondInGuild(message)) {
    return;
  }

  const data = loadData();
  const content = message.content.trim();

  if (content.startsWith(commandPrefix)) {
    const withoutPrefix = content.slice(commandPrefix.length).trim();
    const [command, ...args] = withoutPrefix.split(/\s+/);

    const handledPublic = await handlePublicCommand(message, data, command);
    if (handledPublic) {
      return;
    }

    await handleAdminCommand(message, data, command, args);
    return;
  }

  const reply = buildAutoReply(content, data);
  if (reply) {
    await message.reply(reply);
  }
});

client.once("ready", () => {
  isReady = true;
  console.log(`Logged in as ${client.user.tag}`);
});

if (!process.env.DISCORD_TOKEN) {
  console.error(t(fallbackLang, "missingToken"));
  process.exit(1);
}

client.login(process.env.DISCORD_TOKEN);
