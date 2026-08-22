import { describe, expect, it } from "vitest";
import { rejectionCopy, worksheetSchema } from "../src/domain/contracts";

describe("worksheet contract", () => {
  it("requires one physical answer region per question", () => {
    const worksheet = {
      id: "w1", title: "Sample", pageCount: 1, sourceHash: "b".repeat(64),
      questions: [{ id: "q1", index: 1, prompt: "Name a producer.", pageIndex: 0, answerRegion: { id: "r1", pageIndex: 0, bounds: { x: 1, y: 1, width: 2, height: 2 } } }],
    };
    expect(worksheetSchema.parse(worksheet).questions).toHaveLength(1);
  });

  it("keeps rejection reasons stable and human-readable", () => {
    expect(rejectionCopy.unsupported_scan_or_ocr_required).toContain("selectable text");
    expect(rejectionCopy.ambiguous_answer_region).toContain("more than one");
  });
});
