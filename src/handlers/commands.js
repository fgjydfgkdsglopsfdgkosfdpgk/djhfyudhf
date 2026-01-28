const { t, listLanguages } = require("../utils/i18n");
const { saveData } = require("../data/store");

const isOwner = (data, userId) => data.settings.ownerId && data.settings.ownerId === userId;
const isAdmin = (data, userId) => isOwner(data, userId) || data.admins.includes(userId);

const parseNoteCommand = (content, defaultLanguage) => {
  const parts = content.split("|").map((part) => part.trim());
  if (parts.length < 3) {
    return null;
  }

  let tag;
  let lang;
  let patternPart;
  let answerParts;

  if (parts.length >= 4) {
    [tag, lang, patternPart, ...answerParts] = parts;
  } else {
    [tag, patternPart, ...answerParts] = parts;
    lang = defaultLanguage;
  }

  const patterns = patternPart
    .split(";")
    .map((pattern) => pattern.trim())
    .filter(Boolean);
  const answer = answerParts.join(" | ").trim();
  if (!tag || patterns.length === 0 || !answer || !lang) {
    return null;
  }
  return { tag, lang, patterns, answer };
};

const findNote = (data, tag) => data.notes.find((note) => note.tag === tag);

const handleAdminCommand = async (message, data, command, args) => {
  const lang = data.settings.language;

  if (["addadmin", "deladmin"].includes(command)) {
    if (!isOwner(data, message.author.id)) {
      await message.reply(t(lang, "ownerOnly"));
      return true;
    }
  } else if (!isAdmin(data, message.author.id)) {
    await message.reply(t(lang, "noAccess"));
    return true;
  }

  if (command === "addadmin") {
    const userId = args[0];
    if (!userId) {
      await message.reply(t(lang, "needUserId"));
      return true;
    }
    if (!data.admins.includes(userId)) {
      data.admins.push(userId);
      saveData(data);
    }
    await message.reply(t(lang, "adminAdded", { userId }));
    return true;
  }

  if (command === "deladmin") {
    const userId = args[0];
    if (!userId) {
      await message.reply(t(lang, "needUserId"));
      return true;
    }
    data.admins = data.admins.filter((id) => id !== userId);
    saveData(data);
    await message.reply(t(lang, "adminRemoved", { userId }));
    return true;
  }

  if (command === "listadmins") {
    const list = data.admins.length ? data.admins.join(", ") : "-";
    await message.reply(t(lang, "adminsList", { list }));
    return true;
  }

  if (command === "setlang") {
    const newLang = args[0];
    if (!newLang) {
      await message.reply(t(lang, "invalidLang"));
      return true;
    }
    const available = listLanguages();
    if (!available.some((item) => item.code === newLang)) {
      const list = available.map((item) => item.code).join(", ");
      await message.reply(t(lang, "languageUnknown", { list }));
      return true;
    }
    data.settings.language = newLang;
    saveData(data);
    await message.reply(t(newLang, "languageSet", { lang: newLang }));
    return true;
  }

  if (command === "getlang") {
    await message.reply(t(lang, "currentLanguage", { lang }));
    return true;
  }

  if (command === "addnote" || command === "updatenote") {
    const parsed = parseNoteCommand(args.join(" "), lang);
    if (!parsed) {
      await message.reply(t(lang, "invalidNoteFormat"));
      return true;
    }

    let note = findNote(data, parsed.tag);
    if (!note) {
      note = { tag: parsed.tag, responses: {} };
      data.notes.push(note);
    }
    note.responses[parsed.lang] = { patterns: parsed.patterns, answer: parsed.answer };
    saveData(data);
    const replyKey = command === "addnote" ? "noteAdded" : "noteUpdated";
    await message.reply(t(lang, replyKey, { tag: parsed.tag, lang: parsed.lang }));
    return true;
  }

  if (command === "delnote") {
    const tag = args[0];
    const langArg = args[1];
    if (!tag) {
      await message.reply(t(lang, "invalidTag"));
      return true;
    }
    const note = findNote(data, tag);
    if (!note) {
      await message.reply(t(lang, "noteNotFound", { tag }));
      return true;
    }
    if (langArg) {
      delete note.responses[langArg];
      if (Object.keys(note.responses).length === 0) {
        data.notes = data.notes.filter((item) => item.tag !== tag);
      }
      saveData(data);
      await message.reply(t(lang, "noteLangRemoved", { tag, lang: langArg }));
      return true;
    }
    data.notes = data.notes.filter((item) => item.tag !== tag);
    saveData(data);
    await message.reply(t(lang, "noteRemoved", { tag }));
    return true;
  }

  return false;
};

const handlePublicCommand = async (message, data, command) => {
  const lang = data.settings.language;
  if (command === "notes") {
    if (data.notes.length === 0) {
      await message.reply(t(lang, "notesEmpty"));
      return true;
    }
    const list = data.notes
      .map((note) => {
        const langs = Object.keys(note.responses || {});
        return langs.length ? `${note.tag} (${langs.join("/")})` : note.tag;
      })
      .join(", ");
    await message.reply(t(lang, "notesList", { list }));
    return true;
  }

  if (command === "langs") {
    const list = listLanguages()
      .map((item) => `${item.code} (${item.name})`)
      .join(", ");
    await message.reply(t(lang, "languagesList", { list }));
    return true;
  }

  const note = findNote(data, command);
  if (note) {
    const response = note.responses[lang] || Object.values(note.responses)[0];
    if (!response) {
      await message.reply(t(lang, "noteNotFound", { tag: command }));
      return true;
    }
    await message.reply(response.answer);
    return true;
  }

  return false;
};

module.exports = {
  handleAdminCommand,
  handlePublicCommand,
  isAdmin,
  isOwner
};
