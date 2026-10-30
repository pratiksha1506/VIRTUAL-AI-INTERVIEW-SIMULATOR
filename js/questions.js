/*
 * questions.js — static question bank (mirrors ai/question_generator.py's
 * fallback bank from the Python version, since there's no LLM call here).
 */
const QUESTION_BANK = {
  "Software Developer": {
    "Technical": [
      { q: "Explain the difference between an array and a linked list.", expected: "array memory layout access time linked list insertion deletion cost pointer" },
      { q: "What is the time complexity of binary search, and why?", expected: "binary search logarithmic time halves search space each step sorted" },
      { q: "What is a REST API and what makes an API RESTful?", expected: "rest api stateless resource url http verbs representation client server" },
    ],
    "Behavioral": [
      { q: "Tell me about a bug that took you a long time to fix.", expected: "debugging systematic approach root cause learned process" },
      { q: "Describe a time you disagreed with a teammate's technical decision.", expected: "disagreement respectful communication resolution compromise team" },
    ],
    "Situational": [
      { q: "If your code passes all tests but breaks in production, what would you do?", expected: "logs monitoring reproduce rollback root cause regression test" },
    ],
  },
  "Data Analyst": {
    "Technical": [
      { q: "What is the difference between INNER JOIN and LEFT JOIN in SQL?", expected: "inner join matching rows left join all left table null unmatched" },
      { q: "How would you handle missing data in a dataset?", expected: "missing data removal imputation mean median mode appropriate context" },
    ],
    "Behavioral": [
      { q: "Tell me about a time your analysis changed a business decision.", expected: "analysis insight impact business decision communication stakeholder" },
    ],
    "Situational": [
      { q: "A stakeholder disagrees with your data-driven conclusion. What do you do?", expected: "validate data methodology explain open alternative interpretation" },
    ],
  },
  "HR Interview": {
    "HR": [
      { q: "Tell me about yourself.", expected: "background experience motivation relevant summary career" },
      { q: "Why do you want to work here?", expected: "company role specific motivation values mission fit" },
      { q: "Where do you see yourself in five years?", expected: "career growth goals development role progression" },
      { q: "What is your greatest weakness?", expected: "self awareness weakness improvement effort growth honest" },
    ],
    "Behavioral": [
      { q: "Describe a time you had to work under pressure.", expected: "pressure deadline situation action result managed stress" },
      { q: "Tell me about a conflict with a coworker and how you resolved it.", expected: "conflict coworker resolution communication ownership constructive" },
    ],
  },
};

function getQuestion(jobRole, interviewType, askedTexts) {
  const roleBank = QUESTION_BANK[jobRole] || QUESTION_BANK["Software Developer"];
  let pool = [];
  if (interviewType === "Mixed") {
    Object.values(roleBank).forEach(arr => pool.push(...arr));
    Object.values(QUESTION_BANK["HR Interview"]).forEach(arr => pool.push(...arr));
  } else {
    pool = roleBank[interviewType] || QUESTION_BANK["HR Interview"]["Behavioral"];
  }
  const unused = pool.filter(item => !askedTexts.includes(item.q));
  const choice = (unused.length ? unused : pool)[Math.floor(Math.random() * (unused.length ? unused.length : pool.length))];
  return { question: choice.q, expectedKeywords: choice.expected, questionType: interviewType === "Mixed" ? "Mixed" : interviewType };
}
