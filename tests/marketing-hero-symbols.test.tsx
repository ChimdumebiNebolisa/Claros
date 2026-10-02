// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import MarketingShell from "../src/v2/MarketingShell";

afterEach(cleanup);

function renderHomepage() {
  return render(
    <MemoryRouter>
      <MarketingShell />
    </MemoryRouter>,
  );
}

describe("existing Claros hero with scattered symbols", () => {
  it("uses sans-serif typography for the main and section headings", () => {
    renderHomepage();
    const headings = [
      screen.getByRole("heading", { level: 1 }),
      ...screen.getAllByRole("heading", { level: 2 }),
    ];
    for (const heading of headings) {
      expect(heading).toHaveClass("font-sans");
      expect(heading).not.toHaveClass("font-display");
    }
  });

  it("adds only non-interactive, screen-reader-hidden decoration to the hero", () => {
    renderHomepage();
    const hero = screen
      .getByRole("heading", { name: "Think it. Say it. Put it on the page." })
      .closest("section")!;
    const decoration = hero.querySelector(".claros-hero-symbols")!;
    expect(decoration).toHaveAttribute("aria-hidden", "true");
    expect(decoration.querySelectorAll(".claros-hero-symbol")).toHaveLength(25);
    expect(decoration).toHaveTextContent("x²");
    expect(decoration).toHaveTextContent("Aa");
    expect(decoration.querySelector("a, button, input, [tabindex]")).toBeNull();
    expect(within(hero).getAllByRole("link")).toHaveLength(1);
  });

  it("preserves the original content, primary action, and page structure", () => {
    renderHomepage();
    expect(
      screen.getByText("Built for students who find typing difficult"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Talk through a question or say the answer you already know. Review the exact wording, approve it, and Claros places it into your PDF.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Nothing reaches your worksheet until you approve it."),
    ).toBeInTheDocument();
    for (const link of screen.getAllByRole("link", { name: "Try Claros" })) {
      expect(link).toHaveAttribute("href", "/app");
    }
    expect(
      screen.getAllByRole("heading", { level: 2 }).map((el) => el.textContent),
    ).toEqual([
      "Just talk to Claros.",
      "Your answer stays yours.",
      "Voice-first, never voice-only.",
      "Have a worksheet to finish?",
    ]);
    expect(screen.queryByText("Talk it through")).not.toBeInTheDocument();
  });
});
