/*
 * scoring.js — "simulated AI" scoring engine for the frontend-only demo.
 *
 * IMPORTANT: this is NOT the real ML pipeline. The full Python project
 * (ai/nlp_evaluator.py, ai/confidence_analyzer.py, ai/facial_analyzer.py)
 * uses Sentence-BERT semantic similarity, Librosa acoustic feature
 * extraction, and OpenCV/MediaPipe/DeepFace facial analysis. This file
 * computes scores from real, observable signals captured in the browser
 * (transcript keywords, speaking pace, filler-word count, pixel-variance
 * as an engagement proxy) using transparent formulas — not from a trained
 * model, and not from Math.random(). It exists so this demo can run with
 * zero backend, and is labeled as a demo heuristic everywhere it's shown.
 */
const FILLER_WORDS = ["um", "uh", "umm", "uhh", "like", "you know", "actually", "basically", "i mean"];

function countFillers(text) {
  const lower = ` ${text.toLowerCase()} `;
  return FILLER_WORDS.reduce((sum, w) => {
    const re = new RegExp(`\\b${w.replace(" ", "\\s+")}\\b`, "g");
    const matches = lower.match(re);
    return sum + (matches ? matches.length : 0);
  }, 0);
}

function wordsPerMinute(text, seconds) {
  if (!seconds || seconds < 1) return 0;
  const words = text.trim().split(/\s+/).filter(Boolean).length;
  return Math.round((words / seconds) * 60);
}

function keywordOverlapScore(transcript, expectedKeywords) {
  const clean = s => new Set(s.toLowerCase().match(/[a-z']+/g) || []);
  const a = clean(transcript);
  const b = clean(expectedKeywords);
  if (a.size === 0 || b.size === 0) return 0;
  let hits = 0;
  b.forEach(w => { if (a.has(w)) hits++; });
  return Math.round((hits / b.size) * 100);
}

function grammarHeuristic(text) {
  const words = text.trim().split(/\s+/).filter(Boolean);
  if (words.length < 3) return 40;
  const uniqueRatio = new Set(words.map(w => w.toLowerCase())).size / words.length;
  const avgWordLen = words.reduce((s, w) => s + w.length, 0) / words.length;
  let score = 60 + uniqueRatio * 30 + Math.min(10, avgWordLen);
  return Math.round(Math.max(35, Math.min(95, score)));
}

function confidenceScore(wpm, fillerCount, wordCount) {
  const paceScore = wpm <= 0 ? 30 : Math.max(0, 100 - Math.abs(wpm - 135) * 0.8);
  const fillerRatio = wordCount > 0 ? fillerCount / wordCount : 0;
  const fillerScore = Math.max(0, 100 - fillerRatio * 400);
  const overall = Math.round(paceScore * 0.6 + fillerScore * 0.4);
  const bounded = Math.max(0, Math.min(100, overall));
  let label = "Poor";
  if (bounded >= 80) label = "Excellent";
  else if (bounded >= 60) label = "Good";
  else if (bounded >= 40) label = "Average";
  return { score: bounded, label };
}

function communicationScore(wpm, grammar, fillerCount, wordCount) {
  const paceComponent = wpm <= 0 ? 35 : Math.max(0, 100 - Math.abs(wpm - 135) * 0.7);
  const fillerRatio = wordCount > 0 ? fillerCount / wordCount : 0;
  const fluencyComponent = Math.max(0, 100 - fillerRatio * 350);
  const score = Math.round(paceComponent * 0.35 + fluencyComponent * 0.25 + grammar * 0.40);
  return Math.max(0, Math.min(100, score));
}

/*
 * Facial "engagement" proxy — samples pixel variance from the video feed.
 * This has NO relationship to real facial expression recognition; it is
 * a placeholder signal only, present because the camera capture itself
 * is real and needs *some* downstream number to demonstrate the flow.
 */
function facialEngagementScore(frameVarianceSamples) {
  if (!frameVarianceSamples || frameVarianceSamples.length === 0) return null;
  const avg = frameVarianceSamples.reduce((a, b) => a + b, 0) / frameVarianceSamples.length;
  const normalized = Math.max(0, Math.min(100, Math.round((avg / 40) * 100)));
  return Math.max(35, normalized); // floor so a still/dim frame doesn't read as "0% engaged"
}

function computeOverallScore(content, confidence, communication, facial) {
  const WEIGHTS = { content: 0.40, confidence: 0.30, communication: 0.20, facial: 0.10 };
  let weights = Object.assign({}, WEIGHTS);
  let overall;
  if (facial === null || facial === undefined) {
    const facialWeight = weights.facial;
    delete weights.facial;
    const remainingTotal = weights.content + weights.confidence + weights.communication;
    Object.keys(weights).forEach(k => { weights[k] += facialWeight * (weights[k] / remainingTotal); });
    overall = content * weights.content + confidence * weights.confidence + communication * weights.communication;
  } else {
    overall = content * weights.content + confidence * weights.confidence + communication * weights.communication + facial * weights.facial;
  }
  return Math.round(Math.max(0, Math.min(100, overall)));
}

function scoreAnswer(transcript, expectedKeywords, durationSec, frameVarianceSamples) {
  const wordCount = transcript.trim().split(/\s+/).filter(Boolean).length;
  const fillerCount = countFillers(transcript);
  const wpm = wordsPerMinute(transcript, durationSec);

  const content = keywordOverlapScore(transcript, expectedKeywords);
  const grammar = grammarHeuristic(transcript);
  const confidence = confidenceScore(wpm, fillerCount, wordCount);
  const communication = communicationScore(wpm, grammar, fillerCount, wordCount);
  const facial = facialEngagementScore(frameVarianceSamples);
  const overall = computeOverallScore(content, confidence.score, communication, facial);

  return {
    transcript, wordCount, fillerCount, wpm,
    contentScore: content, grammarScore: grammar,
    confidenceScore: confidence.score, confidenceLabel: confidence.label,
    communicationScore: communication, facialScore: facial, overallScore: overall,
  };
}

function buildFeedback(results) {
  const avg = key => Math.round(results.reduce((s, r) => s + r[key], 0) / results.length);
  const strengths = [], weaknesses = [], suggestions = [];

  const avgConfidence = avg("confidenceScore");
  if (avgConfidence >= 65) strengths.push("Consistent, controlled speaking pace across answers.");
  else { weaknesses.push("Speaking pace and filler words were inconsistent — practice pacing your answers."); suggestions.push("Practice answering out loud with a timer to build a steadier pace."); }

  const avgGrammar = avg("grammarScore");
  if (avgGrammar >= 75) strengths.push("Clear, well-structured answers.");
  else { weaknesses.push("A few answers could be tightened up structurally."); suggestions.push("Read your answers back or record yourself to catch phrasing issues."); }

  const avgContent = avg("contentScore");
  if (avgContent >= 55) strengths.push("Answers stayed relevant to what was asked.");
  else { weaknesses.push("Some answers drifted from the core of the question."); suggestions.push("Before answering, restate the question in your head to stay on-topic."); }

  if (!suggestions.length) suggestions.push("Keep practicing with harder difficulty settings to keep improving.");

  const overall = Math.round(results.reduce((s, r) => s + r.overallScore, 0) / results.length);
  const overallFeedback = `Overall this session scored around ${overall}/100. ` +
    (overall >= 70 ? "Strong session overall — " : "A solid foundation with room to grow — ") +
    `focus on ${suggestions[0].toLowerCase()}`;

  return { strengths, weaknesses, suggestions, overallFeedback, overall };
}
