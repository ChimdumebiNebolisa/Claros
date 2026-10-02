export const DEMO_QUESTIONS = {
  math: {
    subject: "Math",
    question: "How would you add ¾ and ½?",
    spokenQuestion: "How would you add three quarters and one half?",
  },
  english: {
    subject: "English",
    question: "Why might a writer describe the sky as “a blanket of grey”?",
    spokenQuestion: "Why might a writer describe the sky as a blanket of grey?",
  },
} as const;

export type DemoQuestionId = keyof typeof DEMO_QUESTIONS;
export const DEMO_DURATION_SECONDS = 120;