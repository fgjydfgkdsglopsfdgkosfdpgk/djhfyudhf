const { getQuestionWords } = require("../utils/i18n");
const { isQuestionLike, matchPattern, combineAnswers } = require("../utils/text");
const { maxCombinedMultiplier } = require("../config");

const collectMatchesForLang = (messageText, notes, lang) => {
  const results = [];
  for (const note of notes) {
    const response = note.responses[lang];
    if (!response) {
      continue;
    }
    const matched = response.patterns.some((pattern) => matchPattern(messageText, pattern));
    if (matched) {
      results.push(response.answer);
    }
  }
  return results;
};

const collectMatchesAnyLang = (messageText, notes) => {
  const results = [];
  for (const note of notes) {
    const responses = Object.values(note.responses || {});
    for (const response of responses) {
      const matched = response.patterns.some((pattern) => matchPattern(messageText, pattern));
      if (matched) {
        results.push(response.answer);
        break;
      }
    }
  }
  return results;
};

const buildAutoReply = (messageText, data) => {
  const lang = data.settings.language;
  const questionWords = getQuestionWords(lang);
  if (!isQuestionLike(messageText, questionWords)) {
    return null;
  }

  let answers = collectMatchesForLang(messageText, data.notes, lang);
  if (answers.length === 0) {
    answers = collectMatchesAnyLang(messageText, data.notes);
  }

  if (answers.length === 0) {
    return null;
  }

  const uniqueAnswers = [...new Set(answers)];
  return combineAnswers(uniqueAnswers, maxCombinedMultiplier);
};

module.exports = {
  buildAutoReply,
  collectMatchesForLang,
  collectMatchesAnyLang
};
