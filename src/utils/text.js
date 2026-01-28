const normalizeText = (text) => text.toLowerCase().replace(/\s+/g, " ").trim();

const tokenize = (text) => {
  const normalized = normalizeText(text);
  return normalized.match(/[a-zа-я0-9]+/gi) || [];
};

const isQuestionLike = (text, questionWords) => {
  const normalized = normalizeText(text);
  if (normalized.includes("?")) {
    return true;
  }
  return questionWords.some((word) => normalized.includes(word));
};

const levenshteinDistance = (a, b) => {
  const matrix = Array.from({ length: a.length + 1 }, () => Array(b.length + 1).fill(0));
  for (let i = 0; i <= a.length; i += 1) {
    matrix[i][0] = i;
  }
  for (let j = 0; j <= b.length; j += 1) {
    matrix[0][j] = j;
  }
  for (let i = 1; i <= a.length; i += 1) {
    for (let j = 1; j <= b.length; j += 1) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      matrix[i][j] = Math.min(
        matrix[i - 1][j] + 1,
        matrix[i][j - 1] + 1,
        matrix[i - 1][j - 1] + cost
      );
    }
  }
  return matrix[a.length][b.length];
};

const isFuzzyTokenMatch = (token, word) => {
  if (token === word) {
    return true;
  }
  const maxDistance = token.length <= 4 ? 1 : 2;
  return levenshteinDistance(token, word) <= maxDistance;
};

const matchPattern = (messageText, pattern) => {
  const patternTokens = tokenize(pattern);
  if (patternTokens.length === 0) {
    return false;
  }
  const messageTokens = tokenize(messageText);
  return patternTokens.every((token) =>
    messageTokens.some((word) => isFuzzyTokenMatch(token, word))
  );
};

const shortenAnswer = (answer, maxLength) => {
  if (answer.length <= maxLength) {
    return answer;
  }
  const sentences = answer.split(/(?<=[.!?])\s+/);
  let result = "";
  for (const sentence of sentences) {
    if ((result + " " + sentence).trim().length > maxLength) {
      break;
    }
    result = `${result} ${sentence}`.trim();
  }
  if (!result) {
    return answer.slice(0, maxLength - 1).trimEnd() + "…";
  }
  return result;
};

const combineAnswers = (answers, maxCombinedMultiplier) => {
  if (answers.length === 1) {
    return answers[0];
  }
  const baseLength = Math.max(...answers.map((answer) => answer.length));
  const maxLength = Math.floor(baseLength * maxCombinedMultiplier);
  const shortened = answers.map((answer) => shortenAnswer(answer, Math.floor(maxLength / answers.length)));
  const combined = shortened.join("\n\n");
  return combined.length > maxLength ? shortenAnswer(combined, maxLength) : combined;
};

module.exports = {
  normalizeText,
  tokenize,
  isQuestionLike,
  matchPattern,
  combineAnswers
};
