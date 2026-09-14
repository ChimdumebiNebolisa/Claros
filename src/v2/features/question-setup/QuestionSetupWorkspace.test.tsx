/** @vitest-environment jsdom */

import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, describe, expect, it, vi } from "vitest";
import type { QuestionSetup } from "../../domain/contracts";
import { QuestionSetupWorkspace } from "./QuestionSetupWorkspace";

const { getQuestionBlocks, previewQuestionSelection } = vi.hoisted(() => ({
  getQuestionBlocks: vi.fn(),
  previewQuestionSelection: vi.fn(),
}));

vi.mock("../../api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/client")>()),
  getQuestionBlocks,
  previewQuestionSelection,
}));

vi.mock("@embedpdf/core", () => ({
  createPluginRegistration: () => ({}),
}));
vi.mock("@embedpdf/core/react", () => ({
  EmbedPDF: ({
    children,
  }: {
    children: (value: { activeDocumentId: string }) => unknown;
  }) => children({ activeDocumentId: "document" }),
}));
vi.mock("@embedpdf/engines/react", () => ({
  usePdfiumEngine: () => ({ engine: {}, isLoading: false, error: null }),
}));
vi.mock("@embedpdf/models", () => ({ ConsoleLogger: class {} }));
vi.mock("@embedpdf/plugin-document-manager/react", () => ({
  DocumentManagerPluginPackage: {},
  DocumentContent: ({ children }: { children: (value: object) => unknown }) =>
    children({ isLoading: false, isError: false, isLoaded: true }),
}));
vi.mock("@embedpdf/plugin-render/react", () => ({
  RenderPluginPackage: {},
  useRenderCapability: () => ({
    provides: {
      forDocument: () => ({
        renderPageRect: () => ({ toPromise: async () => new Blob(["page"]) }),
      }),
    },
  }),
}));

const setup: QuestionSetup = {
  version: 7,
  verified: false,
  provenance: "student_corrected",
  sourceUrl: "/api/v2/assignments/asn_test/source",
  pages: [{ pageNumber: 1, widthMpt: 600_000, heightMpt: 800_000 }],
  questions: [
    {
      id: "q_one",
      index: 1,
      prompt: "Why do plants need sunlight?",
      instruction: "Use evidence.",
      pageNumber: 1,
      placement: "inline",
      regions: [
        { xMpt: 60_000, yMpt: 120_000, widthMpt: 320_000, heightMpt: 28_000 },
      ],
    },
    {
      id: "q_two",
      index: 2,
      prompt: "How does sunlight help a plant make food?",
      instruction: "",
      pageNumber: 1,
      placement: "appendix",
      regions: [
        { xMpt: 60_000, yMpt: 320_000, widthMpt: 390_000, heightMpt: 28_000 },
      ],
    },
  ],
};

const assignment = {
  id: "asn_test",
  version: 7,
  title: "Biology",
  filename: "biology.pdf",
  pageCount: 1,
  questions: setup.questions,
};

const blocks = {
  version: 7,
  page_number: 1,
  page_width_mpt: 600_000,
  page_height_mpt: 800_000,
  source_url: setup.sourceUrl,
  blocks: [
    {
      block_id: "blk_prompt",
      exact_text: "Explain how evaporation contributes to the water cycle.",
      page_number: 1,
      reading_order: 4,
      region: {
        x_mpt: 60_000,
        y_mpt: 220_000,
        width_mpt: 420_000,
        height_mpt: 30_000,
      },
      selected_question_ids: [],
    },
  ],
};

function renderWorkspace(
  overrides: Partial<React.ComponentProps<typeof QuestionSetupWorkspace>> = {},
) {
  const props = {
    assignment,
    setup,
    editing: false,
    onEnterEdit: vi.fn(),
    onCancelEdit: vi.fn(),
    onMutate: vi.fn(async () => undefined),
    onAccept: vi.fn(async () => undefined),
    onError: vi.fn(),
    ...overrides,
  };
  render(<QuestionSetupWorkspace {...props} />);
  return props;
}

beforeAll(() => {
  Object.defineProperty(URL, "createObjectURL", {
    configurable: true,
    value: vi.fn(() => "blob:page"),
  });
  Object.defineProperty(URL, "revokeObjectURL", {
    configurable: true,
    value: vi.fn(),
  });
});

describe("QuestionSetupWorkspace", () => {
  it("keeps the correct-detection path to one obvious start action", async () => {
    const user = userEvent.setup();
    const props = renderWorkspace();

    expect(
      screen.getByRole("heading", { name: "Check your questions." }),
    ).toBeVisible();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByRole("button", { name: /Question 1:/ })).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Looks right — Start" }),
    );
    expect(props.onAccept).toHaveBeenCalledOnce();
  });

  it("keeps the overlay aligned to the canonical page aspect ratio", async () => {
    renderWorkspace({
      setup: {
        ...setup,
        pages: [{ pageNumber: 1, widthMpt: 792_000, heightMpt: 612_000 }],
      },
    });

    const overlay = await screen.findByLabelText(
      "Detected question highlights",
    );
    expect(overlay.parentElement).toHaveStyle({
      aspectRatio: "792000 / 612000",
    });
  });

  it("offers keyboard selection and exact server text before adding", async () => {
    getQuestionBlocks.mockResolvedValue(blocks);
    previewQuestionSelection.mockResolvedValue({
      version: 7,
      page_number: 1,
      block_ids: ["blk_prompt"],
      exact_prompt: blocks.blocks[0].exact_text,
      prompt_regions: [blocks.blocks[0].region],
      placement_capability: "inline_possible",
    });
    const user = userEvent.setup();
    const props = renderWorkspace({ editing: true });

    await user.click(
      screen.getByRole("button", { name: "Add missed question" }),
    );
    expect(
      screen.getByLabelText("Question text selection instructions"),
    ).toHaveFocus();
    const checkbox = await screen.findByRole("checkbox", {
      name: blocks.blocks[0].exact_text,
    });
    await user.click(checkbox);
    await user.click(
      screen.getByRole("button", { name: "Check selected text" }),
    );

    expect(
      (await screen.findAllByText(blocks.blocks[0].exact_text)).at(-1),
    ).toBeVisible();
    expect(
      screen.getByText("This exact worksheet text will be used."),
    ).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Add question" }));
    expect(props.onMutate).toHaveBeenCalledWith({
      kind: "add",
      page_number: 1,
      block_ids: ["blk_prompt"],
    });
  });

  it("replaces an existing question through canonical server block IDs", async () => {
    getQuestionBlocks.mockResolvedValue(blocks);
    previewQuestionSelection.mockResolvedValue({
      version: 7,
      page_number: 1,
      block_ids: ["blk_prompt"],
      exact_prompt: blocks.blocks[0].exact_text,
      prompt_regions: [blocks.blocks[0].region],
      placement_capability: "inline_possible",
    });
    const user = userEvent.setup();
    const props = renderWorkspace({ editing: true });

    await user.click(
      screen.getAllByRole("button", { name: "Fix selection" })[0],
    );
    await user.click(
      await screen.findByRole("checkbox", {
        name: blocks.blocks[0].exact_text,
      }),
    );
    await user.click(
      screen.getByRole("button", { name: "Check selected text" }),
    );
    expect(previewQuestionSelection).toHaveBeenCalledWith("asn_test", {
      assignment_version: 7,
      page_number: 1,
      block_ids: ["blk_prompt"],
      question_id: "q_one",
    });
    await user.click(screen.getByRole("button", { name: "Save question" }));
    expect(props.onMutate).toHaveBeenCalledWith({
      kind: "replace",
      question_id: "q_one",
      page_number: 1,
      block_ids: ["blk_prompt"],
    });
  });

  it("forwards validation failures and presents stale-version recovery copy", async () => {
    getQuestionBlocks.mockResolvedValue(blocks);
    const validationError = new Error(
      "That selection is not valid source text.",
    );
    previewQuestionSelection.mockRejectedValue(validationError);
    const user = userEvent.setup();
    const props = renderWorkspace({
      editing: true,
      errorMessage:
        "This worksheet changed in another tab. Reload before changing questions.",
    });

    expect(screen.getByRole("alert")).toHaveTextContent(
      "This worksheet changed in another tab",
    );
    await user.click(
      screen.getByRole("button", { name: "Add missed question" }),
    );
    await user.click(
      await screen.findByRole("checkbox", {
        name: blocks.blocks[0].exact_text,
      }),
    );
    await user.click(
      screen.getByRole("button", { name: "Check selected text" }),
    );
    await waitFor(() =>
      expect(props.onError).toHaveBeenCalledWith(validationError),
    );
  });

  it("exposes fix, reorder, remove, and reset without changing identity locally", async () => {
    getQuestionBlocks.mockResolvedValue(blocks);
    const user = userEvent.setup();
    const props = renderWorkspace({ editing: true });

    await user.click(
      screen.getByRole("button", { name: "Move question 2 up" }),
    );
    expect(props.onMutate).toHaveBeenCalledWith({
      kind: "reorder",
      ordered_question_ids: ["q_two", "q_one"],
    });
    expect(screen.getByText("Why do plants need sunlight?")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Remove question 1" }));
    await user.click(screen.getByRole("button", { name: "Remove" }));
    expect(props.onMutate).toHaveBeenCalledWith({
      kind: "remove",
      question_id: "q_one",
    });

    await user.click(
      screen.getByRole("button", { name: "Reset to detected questions" }),
    );
    expect(props.onMutate).toHaveBeenCalledWith({ kind: "reset" });
  });

  it("maps pointer drag to visible server block IDs, never rectangle geometry", async () => {
    getQuestionBlocks.mockResolvedValue(blocks);
    const user = userEvent.setup();
    renderWorkspace({ editing: true });
    await user.click(
      screen.getByRole("button", { name: "Add missed question" }),
    );
    const overlay = await screen.findByLabelText(
      "Select question text on worksheet",
    );
    Object.defineProperty(overlay, "getBoundingClientRect", {
      value: () => ({
        left: 0,
        top: 0,
        width: 600,
        height: 800,
        right: 600,
        bottom: 800,
      }),
    });
    Object.defineProperty(overlay, "setPointerCapture", { value: vi.fn() });
    fireEvent.pointerDown(overlay, { pointerId: 1, clientX: 55, clientY: 215 });
    fireEvent.pointerMove(overlay, {
      pointerId: 1,
      clientX: 500,
      clientY: 270,
    });
    fireEvent.pointerUp(overlay, { pointerId: 1, clientX: 500, clientY: 270 });
    await waitFor(() =>
      expect(
        screen.getByRole("checkbox", { name: blocks.blocks[0].exact_text }),
      ).toBeChecked(),
    );
  });
});
