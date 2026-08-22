import { createHash } from "node:crypto";

const prompts = [
  "Name one producer in a food chain.",
  "Why do plants need sunlight?",
  "Give one example of a decomposer.",
];

function escapePdfText(value) {
  return value.replaceAll("\\", "\\\\").replaceAll("(", "\\(").replaceAll(")", "\\)");
}

export function buildWorksheetPdf(answers = []) {
  const lines = [
    "CLAROS SAMPLE WORKSHEET",
    "Ecosystems: short-answer practice",
    "",
    ...prompts.flatMap((prompt, index) => [
      `${index + 1}. ${prompt}`,
      "____________________________________________________________",
      answers[index] ? `Answer: ${answers[index]}` : "",
      "",
    ]),
  ];
  const commands = lines.map((line, index) => {
    const y = 740 - index * 28;
    return `BT /F1 12 Tf 72 ${y} Td (${escapePdfText(line)}) Tj ET`;
  }).join("\n");
  const content = `q\n${commands}\nQ\n`;
  const objects = [
    "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
    "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
    "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n",
    "4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    `5 0 obj\n<< /Length ${Buffer.byteLength(content, "ascii")} >>\nstream\n${content}endstream\nendobj\n`,
  ];
  let pdf = "%PDF-1.4\n";
  const offsets = [0];
  for (const object of objects) {
    offsets.push(Buffer.byteLength(pdf, "ascii"));
    pdf += object;
  }
  const xrefOffset = Buffer.byteLength(pdf, "ascii");
  pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  for (let index = 1; index < offsets.length; index += 1) {
    pdf += `${String(offsets[index]).padStart(10, "0")} 00000 n \n`;
  }
  pdf += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF\n`;
  return Buffer.from(pdf, "ascii");
}

export const demoPdf = buildWorksheetPdf();
export const demoSourceHash = createHash("sha256").update(demoPdf).digest("hex");

export function createDemoWorksheet() {
  return {
    id: "worksheet_ecosystems",
    title: "Ecosystems: short-answer practice",
    pageCount: 1,
    sourceHash: demoSourceHash,
    questions: prompts.map((prompt, index) => ({
      id: `question_${index + 1}`,
      index: index + 1,
      prompt,
      pageIndex: 0,
      answerRegion: {
        id: `region_${index + 1}`,
        pageIndex: 0,
        bounds: { x: 72, y: 576 - index * 112, width: 468, height: 54 },
      },
    })),
  };
}
