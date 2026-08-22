import type { AnswerRegion, PlacementKind } from "./contracts";

const CHARACTERS_PER_LINE = 58;
const LINE_HEIGHT = 18;

export function classifyPlacement(answerText: string, region: AnswerRegion): PlacementKind {
  if (!answerText) return "fits_in_answer_area";
  const lineCount = answerText.split(/\r?\n/).reduce((total, line) => {
    return total + Math.max(1, Math.ceil(line.length / CHARACTERS_PER_LINE));
  }, 0);
  const availableLines = Math.max(1, Math.floor(region.bounds.height / LINE_HEIGHT));
  if (lineCount <= availableLines) return "fits_in_answer_area";
  if (lineCount <= availableLines + 5) return "requires_continuation_page";
  return "blocked";
}

export function placementLabel(kind: PlacementKind): string {
  switch (kind) {
    case "fits_in_answer_area":
      return "Fits in the detected answer area.";
    case "requires_continuation_page":
      return "This answer is too long for the detected answer area. Claros will place it on a labeled continuation page.";
    case "blocked":
      return "Placement needs attention before this answer can be added.";
  }
}
