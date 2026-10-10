// What the Duck says. Fixed texts in simple English (ASD-STE100), no AI call. The Duck is kind: it never blames the student.
// say("win", n) gives the same text for the same n, so a test can check it. The pages count up n, so the Duck does not repeat itself at once.
export const LINES = {
  hello: ["Quack! Let us read something today.", "Hello! Your papers are waiting.", "Good to see you. Pick a paper."],
  back: ["Welcome back. Your knowledge is still here.", "You are back. That is the best part.", "Welcome back. We start again, one card at a time."],
  streak: ["Your streak is alive. Nice work.", "Day after day. That is how a thesis grows.", "A streak! Rest is part of the plan."],
  cardReady: ["A new card! Each claim has a quote.", "The card is ready. Read the verdict first."],
  word: ["A new word. Your glossary grows.", "Good word. Now you know it."],
  note: ["A note with a quote. A good habit."],
  link: ["You found a link between two papers.", "Two papers, one idea. Good eye."],
  eureka: ["Eureka! This is a lucky find.", "Quack! A lucky find!"],
  right: ["Yes! That is right.", "Correct. Good memory.", "You know this one."],
  crit: ["A combo hit! Keep going.", "Three in a row. Great."],
  wrong: ["Not this time. Read the proof, then go on.", "Close. The quote shows why.", "No problem. A mistake teaches you."],
  win: ["You defeated the boss. You know this paper.", "Victory! This paper is yours."],
  flawless: ["No hearts lost. Wow.", "A perfect fight. Quack!"],
  lose: ["The boss wins this round. Nothing is lost. We try again.", "Not today. Read the card again, then come back."],
  level: ["A new level! You grow fast.", "Level up! The path opens."],
  quest: ["A quest is done. Well done.", "Quest done! Take your Sparks."],
  tired: ["You are tired. Rest is good work too.", "A rest makes the next week better."],
  semester: ["A new semester. Plan your weeks.", "Twelve weeks. Read first, then test, then write."],
  empty: ["Add a paper in the library. Then we can play."],
};

export function say(event, n = 0) {
  const list = LINES[event] || LINES.hello;
  return list[Math.abs(n) % list.length];
}

// The mood of the Duck for an event.
export const MOOD = { right: "happy", crit: "cheer", win: "cheer", level: "cheer", eureka: "cheer", flawless: "cheer", quest: "happy", link: "happy", cardReady: "happy", wrong: "oops", lose: "oops", tired: "sleepy", back: "happy" };

// The Duck grows with the level. The look changes at the levels of this list.
export function stage(levelIndex = 0) {
  return levelIndex >= 4 ? "scholar" : levelIndex >= 2 ? "duck" : "duckling";
}

// The story line of each level (the same texts as in the server, so a level-up card does not need another request).
export const LEVEL_STORY = {
  Explorer: "You enter the Literature Forest. Each checked quote is a lantern.",
  Reader: "The paths are clearer now. You read with proof.",
  Critic: "You ask hard questions. The bosses know your name.",
  Connector: "You see links between papers that others miss.",
  Author: "Your ideas stand on solid ground. It is time to write.",
  Doctor: "You reached the Defense Castle. The gate is open.",
};
