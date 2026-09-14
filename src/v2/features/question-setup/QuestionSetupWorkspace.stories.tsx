import type { Meta, StoryObj } from "@storybook/react-vite";
import { fn } from "storybook/test";
import { fixtureAssignment } from "../../domain/fixtures";
import type { QuestionSetup } from "../../domain/contracts";
import { QuestionSetupWorkspace } from "./QuestionSetupWorkspace";

const fixtureSetup: QuestionSetup = {
  version: fixtureAssignment.version,
  verified: false,
  provenance: "detected",
  sourceUrl: "/api/v2/fixtures/biology/source",
  pages: [{ pageNumber: 1, widthMpt: 612_000, heightMpt: 792_000 }],
  questions: fixtureAssignment.questions.map((question, index) => ({
    ...question,
    regions: [
      {
        xMpt: 72_000,
        yMpt: 217_691 + index * 160_000,
        widthMpt: [184_912, 267_995, 329_381][index],
        heightMpt: 13_000,
      },
    ],
  })),
};

const meta = {
  title: "V2/Flow/Question setup",
  component: QuestionSetupWorkspace,
  parameters: { layout: "fullscreen" },
  decorators: [
    (Story) => (
      <main>
        <Story />
      </main>
    ),
  ],
  args: {
    assignment: fixtureAssignment,
    setup: fixtureSetup,
    editing: false,
    onEnterEdit: fn(),
    onCancelEdit: fn(),
    onMutate: fn(async () => undefined),
    onAccept: fn(async () => undefined),
    onError: fn(),
  },
} satisfies Meta<typeof QuestionSetupWorkspace>;

export default meta;
type Story = StoryObj<typeof meta>;

export const CheckQuestions: Story = {};

export const CorrectionMode: Story = {
  args: { editing: true },
};
