import { FileCheck2, UploadCloud } from "lucide-react";
import { useRef, useState, type DragEvent } from "react";
import { Button } from "@/v2/ui/Button";
import { LoadingState } from "@/v2/ui/LoadingState";
import { StatusNotice } from "./StatusNotice";

export const MAX_WORKSHEET_BYTES = 10 * 1024 * 1024;

export type UploadValidationError = "file_too_large" | "not_pdf";

export type UploadPanelState =
  | { kind: "empty" }
  | { kind: "loading"; message?: string }
  | {
      kind: "ready";
      title: string;
      pageCount: number;
      questionCount: number;
      inlineCount?: number;
      answerPageCount?: number;
      warnings?: readonly string[];
    }
  | { kind: "error"; message: string; recoverable: boolean };

type AssignmentUploadPanelProps = {
  state: UploadPanelState;
  onFileSelected: (file: File) => void;
  onValidationError: (error: UploadValidationError) => void;
  onTrySample: () => void;
  onStart?: () => void;
  onViewWorksheet?: () => void;
  onShowLimitations?: () => void;
  validationMessage?: string;
};

const uploadErrorId = "worksheet-upload-validation-error";

function UploadControl({
  onFileSelected,
  onValidationError,
  onTrySample,
  onShowLimitations,
  validationMessage,
}: Pick<
  AssignmentUploadPanelProps,
  | "onFileSelected"
  | "onValidationError"
  | "onTrySample"
  | "onShowLimitations"
  | "validationMessage"
>) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  const acceptFile = (file?: File) => {
    if (!file) return;
    if (file.size > MAX_WORKSHEET_BYTES) {
      onValidationError("file_too_large");
      return;
    }
    if (
      file.type !== "application/pdf" &&
      !file.name.toLowerCase().endsWith(".pdf")
    ) {
      onValidationError("not_pdf");
      return;
    }
    onFileSelected(file);
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
    acceptFile(event.dataTransfer.files.item(0) ?? undefined);
  };

  return (
    <div className="grid gap-4">
      <div
        className={`grid min-h-[230px] place-items-center rounded-[16px] border border-dashed px-6 py-9 text-center transition-[border-color,background-color,box-shadow] ${isDragging ? "border-[var(--claros-blue)] bg-[var(--claros-blue-soft)] ring-4 ring-[rgba(21,94,239,.1)]" : "border-[var(--claros-line-strong)] bg-[var(--claros-canvas)]"}`}
        onDragEnter={(event) => {
          event.preventDefault();
          setIsDragging(true);
        }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget as Node))
            setIsDragging(false);
        }}
        onDrop={handleDrop}
      >
        <div className="grid max-w-[420px] justify-items-center">
          <span
            className="grid size-12 place-items-center rounded-[12px] border border-[var(--claros-line)] bg-white text-[var(--claros-blue)] shadow-[0_1px_2px_rgba(17,32,51,.06)]"
            aria-hidden="true"
          >
            <UploadCloud className="size-5" />
          </span>
          <h2 className="mt-5 text-lg font-semibold tracking-[-0.02em] text-[var(--claros-ink)]">
            Bring in a worksheet
          </h2>
          <p className="mt-2 text-sm leading-6 text-[var(--claros-muted)]">
            Drop a text-based PDF here, or choose one from your device.
          </p>
          <input
            ref={inputRef}
            className="sr-only"
            type="file"
            accept="application/pdf,.pdf"
            tabIndex={-1}
            aria-label="Choose a PDF worksheet"
            aria-invalid={validationMessage ? true : undefined}
            aria-describedby={validationMessage ? uploadErrorId : undefined}
            onChange={(event) =>
              acceptFile(event.currentTarget.files?.item(0) ?? undefined)
            }
          />
          <Button
            color="primary"
            size="md"
            className="mt-5"
            aria-describedby={validationMessage ? uploadErrorId : undefined}
            onPress={() => inputRef.current?.click()}
          >
            Choose a PDF
          </Button>
          <span className="mt-3 text-xs text-[var(--claros-quiet)]">
            Up to 10 MiB and 8 pages
          </span>
        </div>
      </div>
      {validationMessage ? (
        <p
          id={uploadErrorId}
          role="alert"
          className="m-0 text-sm text-[var(--claros-error)]"
        >
          {validationMessage}
        </p>
      ) : null}
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
        <Button color="secondary" size="md" onPress={onTrySample}>
          Try the biology sample
        </Button>
        {onShowLimitations ? (
          <Button color="link-gray" size="md" onPress={onShowLimitations}>
            Which PDFs work?
          </Button>
        ) : (
          <p className="m-0 text-sm text-[var(--claros-muted)]">
            Native-text short-answer worksheets only.
          </p>
        )}
      </div>
    </div>
  );
}

export function AssignmentUploadPanel(props: AssignmentUploadPanelProps) {
  const { state } = props;

  if (state.kind === "loading") {
    return (
      <section
        className="grid min-h-72 place-items-center border-y border-[var(--claros-line)] bg-[var(--claros-canvas)] p-8"
        aria-label="Worksheet check"
      >
        <LoadingState label={state.message ?? "Checking your worksheet…"} />
      </section>
    );
  }

  if (state.kind === "ready") {
    return (
      <section
        className="border-l-2 border-[var(--claros-green)] bg-white py-2 pl-5"
        aria-labelledby="worksheet-ready-title"
      >
        <div className="flex items-start gap-4">
          <span
            className="grid size-11 shrink-0 place-items-center rounded-[10px] bg-[var(--claros-green-soft)] text-[var(--claros-green)]"
            aria-hidden="true"
          >
            <FileCheck2 className="size-5" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="m-0 text-xs font-bold uppercase tracking-[0.14em] text-[var(--claros-green)]">
              Worksheet ready
            </p>
            <h2
              id="worksheet-ready-title"
              className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-[var(--claros-ink)]"
            >
              {state.title}
            </h2>
            <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4">
              {[
                { label: "Pages", value: state.pageCount },
                { label: "Questions", value: state.questionCount },
                ...(state.inlineCount !== undefined
                  ? [{ label: "Fit on worksheet", value: state.inlineCount }]
                  : []),
                ...(state.answerPageCount !== undefined
                  ? [{ label: "Use answer page", value: state.answerPageCount }]
                  : []),
              ].map(({ label, value }) => (
                <div key={label}>
                  <dt className="text-xs font-medium text-[var(--claros-muted)]">
                    {label}
                  </dt>
                  <dd className="mt-1 text-base font-semibold text-[var(--claros-ink)]">
                    {value}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
        {state.warnings?.map((warning) => (
          <StatusNotice
            key={warning}
            tone="warning"
            title="Check before you begin"
            className="mt-5"
          >
            <p className="m-0">{warning}</p>
          </StatusNotice>
        ))}
        <div className="mt-7 flex flex-wrap gap-3">
          <Button
            color="primary"
            size="lg"
            onPress={props.onStart}
            isDisabled={!props.onStart}
          >
            Start session
          </Button>
          <Button
            color="secondary"
            size="lg"
            onPress={props.onViewWorksheet}
            isDisabled={!props.onViewWorksheet}
          >
            View worksheet
          </Button>
        </div>
      </section>
    );
  }

  return (
    <section aria-label="Worksheet upload" className="grid gap-5">
      {state.kind === "error" ? (
        <StatusNotice
          tone="error"
          title={
            state.recoverable
              ? "Choose a different worksheet"
              : "This worksheet could not be opened"
          }
        >
          <p className="m-0">{state.message}</p>
        </StatusNotice>
      ) : null}
      <UploadControl {...props} />
    </section>
  );
}
