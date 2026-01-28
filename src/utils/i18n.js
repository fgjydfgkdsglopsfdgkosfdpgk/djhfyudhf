const fs = require("fs");
const path = require("path");

const LOCALES_PATH = path.join(__dirname, "..", "locales");

const loadLocales = () => {
  const locales = {};
  if (!fs.existsSync(LOCALES_PATH)) {
    return locales;
  }
  const files = fs.readdirSync(LOCALES_PATH).filter((file) => file.endsWith(".json"));
  for (const file of files) {
    const raw = fs.readFileSync(path.join(LOCALES_PATH, file), "utf8");
    try {
      const data = JSON.parse(raw);
      if (data.meta && data.meta.code) {
        locales[data.meta.code] = data;
      }
    } catch (error) {
      console.error(`Failed to parse locale ${file}:`, error);
    }
  }
  return locales;
};

const locales = loadLocales();
const fallbackLang = locales.en ? "en" : Object.keys(locales)[0];

const getLocale = (lang) => locales[lang] || locales[fallbackLang];

const t = (lang, key, vars = {}) => {
  const locale = getLocale(lang);
  if (!locale || !locale.messages) {
    return key;
  }
  const template = locale.messages[key] || key;
  return Object.entries(vars).reduce((acc, [varKey, value]) => {
    return acc.replace(new RegExp(`\\{${varKey}\\}`, "g"), value);
  }, template);
};

const getQuestionWords = (lang) => {
  const locale = getLocale(lang);
  if (!locale || !locale.questionWords) {
    return [];
  }
  return locale.questionWords;
};

const listLanguages = () =>
  Object.values(locales).map((locale) => ({
    code: locale.meta.code,
    name: locale.meta.name
  }));

module.exports = {
  t,
  getQuestionWords,
  listLanguages,
  getLocale,
  fallbackLang
};
