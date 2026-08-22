import { z } from "zod";

export const placementKinds = [
  "fits_in_answer_area",
  "requires_continuation_page",
  "blocked",
] as const;

export const rejectionCodes = [
  "unsupported_scan_or_ocr_required",
  "unsupported_choice_question",
  "unsupported_table_or_grid",
  "unsupported_drawing_or_diagram",
  "unsupported_long_form_response",
  "unsupported_multicolumn_layout",
  "missing_local_answer_region",
  "ambiguous_answer_region",
  "remote_answer_region",
  "competing_writable_region",
  "unsupported_page_transform",
  "teacher_or_answer_key_content_detected",
  "page_limit_exceeded",
  "question_limit_exceeded",
  "document_parse_failed",
  "document_validation_failed",
] as const;

export const answerRegionSchema = z.object({
  id: z.string(),
  pageIndex: z.number().int().nonnegative(),
  bounds: z.object({
    x: z.number(),
    y: z.number(),
    width: z.number().positive(),
    height: z.number().positive(),
  }),
});

export const questionSchema = z.object({
  id: z.string(),
  index: z.number().int().positive(),
  prompt: z.string().min(1),
  pageIndex: z.number().int().nonnegative(),
  answerRegion: answerRegionSchema,
});

export const worksheetSchema = z.object({
  id: z.string(),
  title: z.string().min(1),
  pageCount: z.number().int().positive(),
  sourceHash: z.string().regex(/^[a-f0-9]{64}$/),
  questions: z.array(questionSchema).min(1).max(40),
});

export const placementPlanSchema = z.object({
  questionId: z.string(),
  answerText: z.string(),
  placement: z.enum(placementKinds),
  planToken: z.string().min(20),
  expiresAt: z.string().datetime(),
});

export const committedAnswerSchema = z.object({
  questionId: z.string(),
  text: z.string(),
  placement: z.enum(["fits_in_answer_area", "requires_continuation_page"]),
  revision: z.number().int().positive(),
  committedAt: z.string().datetime(),
});

export const assignmentSchema = z.object({
  id: z.string(),
  worksheet: worksheetSchema,
  committedAnswers: z.array(committedAnswerSchema),
  activeQuestionId: z.string(),
});

export type PlacementKind = (typeof placementKinds)[number];
export type RejectionCode = (typeof rejectionCodes)[number];
export type AnswerRegion = z.infer<typeof answerRegionSchema>;
export type Question = z.infer<typeof questionSchema>;
export type SupportedWorksheet = z.infer<typeof worksheetSchema>;
export type PlacementPlan = z.infer<typeof placementPlanSchema>;
export type CommittedAnswer = z.infer<typeof committedAnswerSchema>;
export type Assignment = z.infer<typeof assignmentSchema>;

export const rejectionCopy: Record<RejectionCode, string> = {
  unsupported_scan_or_ocr_required: "This PDF is a scan. Claros needs selectable text.",
  unsupported_choice_question: "This worksheet includes choice questions. Claros currently supports short answers.",
  unsupported_table_or_grid: "This worksheet uses a table or grid for responses.",
  unsupported_drawing_or_diagram: "This worksheet asks for a drawing or diagram label.",
  unsupported_long_form_response: "This worksheet has a long-form response area.",
  unsupported_multicolumn_layout: "This worksheet uses a complex multi-column layout.",
  missing_local_answer_region: "A question is missing one local answer area directly below it.",
  ambiguous_answer_region: "A question has more than one possible answer area.",
  remote_answer_region: "A response area is on another page or too far from its question.",
  competing_writable_region: "A question has competing writable regions.",
  unsupported_page_transform: "This PDF uses an unsupported page transformation.",
  teacher_or_answer_key_content_detected: "Teacher or answer-key content is not supported.",
  page_limit_exceeded: "This worksheet is longer than Claros supports.",
  question_limit_exceeded: "This worksheet has more questions than Claros supports.",
  document_parse_failed: "Claros could not read this PDF as selectable worksheet text.",
  document_validation_failed: "This PDF did not pass the supported worksheet checks.",
};
