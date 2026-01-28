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

const bigrams = (word) => {
  if (word.length < 2) {
    return [word];
  }
  const result = [];
  for (let i = 0; i < word.length - 1; i += 1) {
    result.push(word.slice(i, i + 2));
  }
  return result;
};

const diceCoefficient = (a, b) => {
  if (!a.length || !b.length) {
    return 0;
  }
  const pairsA = bigrams(a);
  const pairsB = bigrams(b);
  const counts = new Map();
  for (const pair of pairsA) {
    counts.set(pair, (counts.get(pair) || 0) + 1);
  }
  let overlap = 0;
  for (const pair of pairsB) {
    const count = counts.get(pair) || 0;
    if (count > 0) {
      overlap += 1;
      counts.set(pair, count - 1);
    }
  }
  return (2 * overlap) / (pairsA.length + pairsB.length);
};

const isFuzzyTokenMatch = (token, word) => {
  if (token === word) {
    return true;
  }
  if (token.length <= 4 || word.length <= 4) {
    const maxDistance = Math.max(2, Math.floor(Math.min(token.length, word.length) / 2));
    return levenshteinDistance(token, word) <= maxDistance;
  }
  const maxDistance = Math.min(4, Math.floor(Math.max(token.length, word.length) / 2));
  if (levenshteinDistance(token, word) <= maxDistance) {
    return true;
  }
  return diceCoefficient(token, word) >= 0.4;
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
