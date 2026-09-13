import { access, readFile } from "node:fs/promises";

const packageJson = JSON.parse(
  await readFile(new URL("../package.json", import.meta.url), "utf8"),
);
const lock = JSON.parse(
  await readFile(new URL("../package-lock.json", import.meta.url), "utf8"),
);

const required = {
  "@embedpdf/core": ["2.15.0", "MIT"],
  "@embedpdf/engines": ["2.15.0", "MIT"],
  "@embedpdf/models": ["2.15.0", "MIT"],
  "@embedpdf/pdfium": ["2.15.0", "MIT"],
  "@embedpdf/plugin-document-manager": ["2.15.0", "MIT"],
  "@embedpdf/plugin-render": ["2.15.0", "MIT"],
  "@embedpdf/react-pdf-viewer": ["2.15.0", "MIT"],
  "@fontsource/instrument-serif": ["5.3.0", "OFL-1.1"],
  "@openai/agents": ["0.18.0", "MIT"],
  "@tanstack/react-query": ["5.102.8", "MIT"],
  "lucide-react": ["0.468.0", "ISC"],
  motion: ["12.43.0", "MIT"],
  "openapi-fetch": ["0.17.0", "MIT"],
  "radix-ui": ["1.6.7", "MIT"],
  msw: ["2.15.0", "MIT"],
  "msw-storybook-addon": ["3.0.0", "MIT"],
  "openapi-typescript": ["7.13.0", "MIT"],
};

const direct = { ...packageJson.dependencies, ...packageJson.devDependencies };
const problems = [];

if (packageJson.engines?.node !== ">=22.12 <23") {
  problems.push(
    `Node engine must be >=22.12 <23; found ${packageJson.engines?.node ?? "missing"}`,
  );
}

for (const [name, declared] of Object.entries(direct)) {
  if (/^[~^*]|\s|\|/.test(declared)) {
    problems.push(`${name} is not exactly pinned (${declared})`);
  }
}

for (const [name, [version, license]] of Object.entries(required)) {
  if (direct[name] !== version) {
    problems.push(
      `${name} must be declared at ${version}; found ${direct[name] ?? "missing"}`,
    );
  }
  const locked = lock.packages?.[`node_modules/${name}`];
  if (locked?.version !== version) {
    problems.push(
      `${name} lock must resolve ${version}; found ${locked?.version ?? "missing"}`,
    );
  }
  if (locked?.license !== license) {
    problems.push(
      `${name} license must be ${license}; found ${locked?.license ?? "missing"}`,
    );
  }
}

for (const legacy of [
  "radix-ui",
  "react-pdf",
  "react-dropzone",
  "react-resizable-panels",
  "lucide-react",
]) {
  if (!packageJson.dependencies[legacy]) {
    problems.push(`${legacy} must remain present until the Gate 6 cutover`);
  }
}

for (const component of [
  "ui/Button.tsx",
  "ui/Textarea.tsx",
  "ui/LoadingState.tsx",
  "ui/cn.ts",
  "components/AssignmentUploadPanel.tsx",
  "components/StatusNotice.tsx",
  "document/WorksheetDialog.tsx",
]) {
  try {
    await access(new URL(`../src/v2/${component}`, import.meta.url));
  } catch {
    problems.push(
      `Approved Claros open-code component is missing: ${component}`,
    );
  }
}

if (problems.length) {
  throw new Error(
    `Gate 1 dependency verification failed:\n- ${problems.join("\n- ")}`,
  );
}

console.log(
  `Verified ${Object.keys(required).length} exact Gate 1 versions/licenses, seven approved Claros open-code components, Node 22, and retained legacy dependencies.`,
);
