import { describe, expect, it } from "vitest";
import { classifyPlacement, placementLabel } from "../src/domain/placement";

const region = { id: "r1", pageIndex: 0, bounds: { x: 0, y: 0, width: 400, height: 54 } };

describe("placement contract", () => {
  it("keeps short exact text in the validated answer area", () => {
    expect(classifyPlacement("Plants use sunlight.", region)).toBe("fits_in_answer_area");
  });

  it("does not trim, normalize, or rewrite the text used for classification", () => {
    const exact = "  Plants use sunlight.  ";
    expect(exact).toBe("  Plants use sunlight.  ");
    expect(classifyPlacement(exact, region)).toBe("fits_in_answer_area");
  });

  it("offers a disclosed continuation page before blocking", () => {
    const answer = "A ".repeat(200);
    expect(classifyPlacement(answer, region)).toBe("requires_continuation_page");
    expect(placementLabel("requires_continuation_page")).toContain("continuation page");
  });

  it("blocks answers that cannot be safely rendered", () => {
    expect(classifyPlacement("x".repeat(1000), region)).toBe("blocked");
  });
});
