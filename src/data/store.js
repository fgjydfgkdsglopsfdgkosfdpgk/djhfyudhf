const fs = require("fs");
const path = require("path");
const { defaultLanguage, dataPath } = require("../config");

const DATA_PATH = path.join(__dirname, "..", "..", dataPath);

const getEmptyData = () => ({
  admins: [],
  settings: {
    language: defaultLanguage
  },
  notes: []
});

const migrateNote = (note, language) => {
  if (note.responses) {
    return note;
  }
  return {
    tag: note.tag,
    responses: {
      [language]: {
        patterns: note.patterns || [],
        answer: note.answer || ""
      }
    }
  };
};

const migrateData = (data) => {
  const language = data.settings?.language || defaultLanguage;
  const migratedNotes = Array.isArray(data.notes)
    ? data.notes.map((note) => migrateNote(note, language))
    : [];
  return {
    admins: Array.isArray(data.admins) ? data.admins : [],
    settings: {
      language
    },
    notes: migratedNotes
  };
};

const loadData = () => {
  if (!fs.existsSync(DATA_PATH)) {
    const initialAdmins = process.env.ADMIN_IDS
      ? process.env.ADMIN_IDS.split(",").map((id) => id.trim()).filter(Boolean)
      : [];
    const initialData = getEmptyData();
    initialData.admins = initialAdmins;
    fs.writeFileSync(DATA_PATH, JSON.stringify(initialData, null, 2));
    return initialData;
  }

  const raw = fs.readFileSync(DATA_PATH, "utf8");
  try {
    const parsed = JSON.parse(raw);
    const migrated = migrateData(parsed);
    if (JSON.stringify(parsed) !== JSON.stringify(migrated)) {
      fs.writeFileSync(DATA_PATH, JSON.stringify(migrated, null, 2));
    }
    return migrated;
  } catch (error) {
    console.error("Failed to parse responses.json:", error);
    return getEmptyData();
  }
};

const saveData = (data) => {
  fs.writeFileSync(DATA_PATH, JSON.stringify(data, null, 2));
};

module.exports = {
  loadData,
  saveData
};
