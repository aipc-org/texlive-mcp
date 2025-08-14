function splitSentences(text) {
  return text
    .replace(/\s+/g, ' ')
    .match(/[^.!?]+[.!?]?/g) || [];
}

function summarizeText({ text = '', maxSentences = 3 }) {
  const sentences = splitSentences(text).map(s => s.trim()).filter(Boolean);
  return sentences.slice(0, maxSentences).join(' ');
}

module.exports = { summarizeText };
