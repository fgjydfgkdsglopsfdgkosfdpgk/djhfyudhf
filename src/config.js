const DEFAULT_LANGUAGE = process.env.DEFAULT_LANG || "ru";

const parseEnvList = (value) =>
  value
    ? value
        .split(",")
        .map((id) => id.trim())
        .filter(Boolean)
    : [];

module.exports = {
  commandPrefix: "#",
  dataPath: "data/responses.json",
  defaultLanguage: DEFAULT_LANGUAGE,
  guildId: process.env.GUILD_ID || null,
  ownerId: process.env.OWNER_ID || null,
  adminIds: parseEnvList(process.env.ADMIN_IDS),
  maxCombinedMultiplier: 1.2
};
