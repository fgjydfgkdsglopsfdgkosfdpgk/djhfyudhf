const DEFAULT_LANGUAGE = process.env.DEFAULT_LANG || "ru";

module.exports = {
  commandPrefix: "#",
  dataPath: "data/responses.json",
  defaultLanguage: DEFAULT_LANGUAGE,
  guildId: process.env.GUILD_ID || null,
  maxCombinedMultiplier: 1.2
};
