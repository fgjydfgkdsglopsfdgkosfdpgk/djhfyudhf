const { getQuestionWords } = require("../utils/i18n");
const { isQuestionLike, matchPatternScore } = require("../utils/text");

const MATCH_THRESHOLD = 0.62;
const STRICT_MATCH_THRESHOLD = 0.8;

const collectBestMatchForLang = (messageText, notes, lang) => {
  let best = null;
  for (const note of notes) {
    const response = note.responses[lang];
    if (!response) {
      continue;
    }
    let bestScore = 0;
    for (const pattern of response.patterns) {
      const score = matchPatternScore(messageText, pattern);
      if (score > bestScore) {
        bestScore = score;
      }
    }
    if (bestScore >= MATCH_THRESHOLD) {
      if (!best || bestScore > best.score) {
        best = { response, score: bestScore };
      }
    }
  }
  return best;
};

const collectBestMatchAnyLang = (messageText, notes) => {
  let best = null;
  for (const note of notes) {
    const responses = Object.values(note.responses || {});
    for (const response of responses) {
      let bestScore = 0;
      for (const pattern of response.patterns) {
        const score = matchPatternScore(messageText, pattern);
        if (score > bestScore) {
          bestScore = score;
        }
      }
      if (bestScore >= MATCH_THRESHOLD) {
        if (!best || bestScore > best.score) {
          best = { response, score: bestScore };
        }
      }
    }
  }
  return best;
};

const buildAutoReply = (messageText, data) => {
  const lang = data.settings.language;
  const questionWords = getQuestionWords(lang);

  let best = collectBestMatchForLang(messageText, data.notes, lang);
  if (!best) {
    best = collectBestMatchAnyLang(messageText, data.notes);
  }

  if (!best) {
    return null;
  }

  const questionLike = isQuestionLike(messageText, questionWords);
  if (!questionLike && best.score < STRICT_MATCH_THRESHOLD) {
    return null;
  }

  return best.response.answer;
};

module.exports = {
  buildAutoReply,
  collectBestMatchForLang,
  collectBestMatchAnyLang
};
