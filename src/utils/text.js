const normalizeText = (text) => text.toLowerCase().replace(/\s+/g, " ").trim();

const isQuestionLike = (text, questionWords) => {
  const normalized = normalizeText(text);
  if (normalized.includes("?")) {
    return true;
  }
  return questionWords.some((word) => normalized.includes(word));
};

const matchPattern = (messageText, pattern) => {
  const normalizedMessage = normalizeText(messageText);
  const normalizedPattern = normalizeText(pattern);
  if (!normalizedPattern) {
    return false;
  }
  const tokens = normalizedPattern.split(" ");
  return tokens.every((token) => normalizedMessage.includes(token));
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
  isQuestionLike,
  matchPattern,
  combineAnswers
};
