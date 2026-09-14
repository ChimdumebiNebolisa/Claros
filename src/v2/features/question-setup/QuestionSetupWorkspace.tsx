import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  Check,
  MousePointer2,
  Plus,
  RotateCcw,
  ScanSearch,
  Trash2,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { createPluginRegistration } from "@embedpdf/core";
import { EmbedPDF } from "@embedpdf/core/react";
import { usePdfiumEngine } from "@embedpdf/engines/react";
import { ConsoleLogger } from "@embedpdf/models";
import {
  DocumentContent,
  DocumentManagerPluginPackage,
} from "@embedpdf/plugin-document-manager/react";
import {
  RenderPluginPackage,
  useRenderCapability,
} from "@embedpdf/plugin-render/react";
import type {
  ApiQuestionBlocks,
  ApiQuestionSelectionPreview,
  ApiQuestionSetupOperation,
} from "../../api/client";
import { getQuestionBlocks, previewQuestionSelection } from "../../api/client";
import type {
  Assignment,
  QuestionRegion,
  QuestionSetup,
} from "../../domain/contracts";
import { Button } from "../../ui/Button";
import { PDFIUM_WASM_URL } from "../../document/viewerConfig";
import styles from "./question-setup.module.css";

const logger = new ConsoleLogger();

type SelectionIntent =
  { kind: "add" } | { kind: "replace"; questionId: string };

type DragBox = {
  startX: number;
  startY: number;
  currentX: number;
  currentY: number;
};

type QuestionSetupWorkspaceProps = {
  assignment: Assignment;
  setup: QuestionSetup;
  editing: boolean;
  errorMessage?: string;
  onEnterEdit: () => void;
  onCancelEdit: () => void;
  onMutate: (operation: ApiQuestionSetupOperation) => Promise<void>;
  onAccept: () => Promise<void>;
  onError: (error: unknown) => void;
};

const percent = (value: number, total: number) => `${(value / total) * 100}%`;

function createPagePlugins(sourceUrl: string, assignmentId: string) {
  const documentId = `question-setup-${assignmentId}-${sourceUrl}`;
  return {
    documentId,
    plugins: [
      createPluginRegistration(DocumentManagerPluginPackage, {
        initialDocuments: [
          {
            url: sourceUrl,
            documentId,
            name: "Worksheet.pdf",
            mode: "range-request" as const,
            requestOptions: { credentials: "same-origin" as const },
            permissions: {
              overrides: {
                print: false,
                modifyContents: false,
                modifyAnnotations: false,
                fillForms: false,
                assembleDocument: false,
              },
            },
          },
        ],
      }),
      createPluginRegistration(RenderPluginPackage, {
        withAnnotations: false,
        withForms: false,
        defaultImageType: "image/png",
      }),
    ],
  };
}

function PageImage({
  documentId,
  pageIndex,
  widthMpt,
  heightMpt,
}: {
  documentId: string;
  pageIndex: number;
  widthMpt: number;
  heightMpt: number;
}) {
  const { provides } = useRenderCapability();
  const [imageUrl, setImageUrl] = useState<string>();
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!provides) return;
    let active = true;
    let ownedUrl: string | undefined;
    const task = provides.forDocument(documentId).renderPageRect({
      pageIndex,
      rect: {
        origin: { x: 0, y: 0 },
        size: { width: widthMpt / 1_000, height: heightMpt / 1_000 },
      },
      options: {
        scaleFactor: 1.35,
        dpr: Math.min(window.devicePixelRatio || 1, 2),
        imageType: "image/png",
        withAnnotations: false,
        withForms: false,
      },
    });
    void task.toPromise().then(
      (blob) => {
        const nextUrl = URL.createObjectURL(blob);
        if (!active) {
          URL.revokeObjectURL(nextUrl);
          return;
        }
        ownedUrl = nextUrl;
        setImageUrl(nextUrl);
      },
      () => {
        if (active) setFailed(true);
      },
    );
    return () => {
      active = false;
      if (ownedUrl) URL.revokeObjectURL(ownedUrl);
    };
  }, [documentId, heightMpt, pageIndex, provides, widthMpt]);

  if (failed) {
    return (
      <div className={styles.documentState} role="alert">
        The worksheet page could not be rendered. You can still select its text
        from the list below.
      </div>
    );
  }
  if (!imageUrl) {
    return (
      <div className={styles.documentState} role="status">
        Rendering worksheet page…
      </div>
    );
  }
  return (
    <img className={styles.pageImage} src={imageUrl} alt="" draggable={false} />
  );
}

function PageRuntime({
  assignmentId,
  sourceUrl,
  pageNumber,
  widthMpt,
  heightMpt,
  children,
}: {
  assignmentId: string;
  sourceUrl: string;
  pageNumber: number;
  widthMpt: number;
  heightMpt: number;
  children: React.ReactNode;
}) {
  const { documentId, plugins } = useMemo(
    () => createPagePlugins(sourceUrl, assignmentId),
    [assignmentId, sourceUrl],
  );
  const { engine, isLoading, error } = usePdfiumEngine({
    wasmUrl: PDFIUM_WASM_URL,
    worker: true,
    fontFallback: null,
    logger,
  });

  if (isLoading) {
    return <div className={styles.documentState}>Opening the worksheet…</div>;
  }
  if (error || !engine) {
    return (
      <div className={styles.documentState} role="alert">
        The visual preview is unavailable. Use the page text list below.
      </div>
    );
  }

  return (
    <EmbedPDF
      engine={engine}
      plugins={plugins}
      config={{
        logger,
        permissions: {
          overrides: {
            print: false,
            modifyContents: false,
            modifyAnnotations: false,
            fillForms: false,
            assembleDocument: false,
          },
        },
      }}
    >
      {({ activeDocumentId }) => (
        <DocumentContent documentId={activeDocumentId}>
          {({ isLoading: loadingDocument, isError, isLoaded }) =>
            isError ? (
              <div className={styles.documentState} role="alert">
                The visual preview is unavailable. Use the page text list below.
              </div>
            ) : loadingDocument || !isLoaded || !activeDocumentId ? (
              <div className={styles.documentState}>Loading the worksheet…</div>
            ) : (
              <div
                className={styles.pageStack}
                style={{ aspectRatio: `${widthMpt} / ${heightMpt}` }}
              >
                <PageImage
                  key={`${documentId}:${pageNumber}`}
                  documentId={documentId}
                  pageIndex={pageNumber - 1}
                  widthMpt={widthMpt}
                  heightMpt={heightMpt}
                />
                {children}
              </div>
            )
          }
        </DocumentContent>
      )}
    </EmbedPDF>
  );
}

function intersectionRatio(region: QuestionRegion, selection: QuestionRegion) {
  const left = Math.max(region.xMpt, selection.xMpt);
  const top = Math.max(region.yMpt, selection.yMpt);
  const right = Math.min(
    region.xMpt + region.widthMpt,
    selection.xMpt + selection.widthMpt,
  );
  const bottom = Math.min(
    region.yMpt + region.heightMpt,
    selection.yMpt + selection.heightMpt,
  );
  if (right <= left || bottom <= top) return 0;
  return (
    ((right - left) * (bottom - top)) / (region.widthMpt * region.heightMpt)
  );
}

export function QuestionSetupWorkspace({
  assignment,
  setup,
  editing,
  errorMessage,
  onEnterEdit,
  onCancelEdit,
  onMutate,
  onAccept,
  onError,
}: QuestionSetupWorkspaceProps) {
  const [selectedQuestionId, setSelectedQuestionId] = useState(
    setup.questions[0]?.id ?? "",
  );
  const effectiveSelectedQuestionId = setup.questions.some(
    (question) => question.id === selectedQuestionId,
  )
    ? selectedQuestionId
    : (setup.questions[0]?.id ?? "");
  const selectedQuestion = setup.questions.find(
    (question) => question.id === effectiveSelectedQuestionId,
  );
  const [pageNumber, setPageNumber] = useState(
    selectedQuestion?.pageNumber ?? 1,
  );
  const [selectionIntent, setSelectionIntent] = useState<SelectionIntent>();
  const [selectedBlockIds, setSelectedBlockIds] = useState<readonly string[]>(
    [],
  );
  const [blocksByPage, setBlocksByPage] = useState<
    Readonly<Record<number, ApiQuestionBlocks>>
  >({});
  const [preview, setPreview] = useState<ApiQuestionSelectionPreview>();
  const [drag, setDrag] = useState<DragBox>();
  const [pendingRemoveId, setPendingRemoveId] = useState<string>();
  const [pending, setPending] = useState(false);
  const liveRef = useRef<HTMLDivElement>(null);
  const dragMovedRef = useRef(false);
  const page =
    setup.pages.find((item) => item.pageNumber === pageNumber) ??
    setup.pages[0];
  const pageBlocks = blocksByPage[pageNumber]?.blocks ?? [];

  useEffect(() => {
    if (!editing || blocksByPage[pageNumber]) return;
    const controller = new AbortController();
    void getQuestionBlocks(assignment.id, pageNumber, controller.signal)
      .then((response) =>
        setBlocksByPage((current) => ({ ...current, [pageNumber]: response })),
      )
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === "AbortError")) {
          onError(error);
        }
      });
    return () => controller.abort();
  }, [assignment.id, blocksByPage, editing, onError, pageNumber]);

  useEffect(() => {
    if (selectionIntent) liveRef.current?.focus({ preventScroll: true });
  }, [selectionIntent]);

  const chooseQuestion = (questionId: string) => {
    const question = setup.questions.find((item) => item.id === questionId);
    setSelectedQuestionId(questionId);
    if (question) setPageNumber(question.pageNumber);
    setPendingRemoveId(undefined);
  };

  const beginSelection = (intent: SelectionIntent) => {
    setSelectionIntent(intent);
    setPreview(undefined);
    setSelectedBlockIds([]);
    if (intent.kind === "replace") {
      const question = setup.questions.find(
        (item) => item.id === intent.questionId,
      );
      if (question) setPageNumber(question.pageNumber);
    }
  };

  const cancelSelection = () => {
    setSelectionIntent(undefined);
    setPreview(undefined);
    setSelectedBlockIds([]);
    setDrag(undefined);
  };

  const toggleBlock = (blockId: string) => {
    setPreview(undefined);
    setSelectedBlockIds((current) =>
      current.includes(blockId)
        ? current.filter((item) => item !== blockId)
        : [...current, blockId].sort(
            (left, right) =>
              pageBlocks.find((block) => block.block_id === left)!
                .reading_order -
              pageBlocks.find((block) => block.block_id === right)!
                .reading_order,
          ),
    );
  };

  const showSelectionPreview = async () => {
    if (!selectionIntent || selectedBlockIds.length === 0) return;
    setPending(true);
    try {
      const result = await previewQuestionSelection(assignment.id, {
        assignment_version: setup.version,
        page_number: pageNumber,
        block_ids: [...selectedBlockIds],
        question_id:
          selectionIntent.kind === "replace"
            ? selectionIntent.questionId
            : null,
      });
      setPreview(result);
    } catch (error) {
      onError(error);
    } finally {
      setPending(false);
    }
  };

  const saveSelection = async () => {
    if (!selectionIntent || !preview) return;
    setPending(true);
    try {
      await onMutate(
        selectionIntent.kind === "add"
          ? {
              kind: "add",
              page_number: pageNumber,
              block_ids: [...preview.block_ids],
            }
          : {
              kind: "replace",
              question_id: selectionIntent.questionId,
              page_number: pageNumber,
              block_ids: [...preview.block_ids],
            },
      );
      cancelSelection();
    } catch (error) {
      onError(error);
    } finally {
      setPending(false);
    }
  };

  const runMutation = async (operation: ApiQuestionSetupOperation) => {
    setPending(true);
    try {
      await onMutate(operation);
    } catch (error) {
      onError(error);
    } finally {
      setPending(false);
    }
  };

  const handlePointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!selectionIntent || !page) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const x = Math.min(Math.max(event.clientX - bounds.left, 0), bounds.width);
    const y = Math.min(Math.max(event.clientY - bounds.top, 0), bounds.height);
    event.currentTarget.setPointerCapture(event.pointerId);
    dragMovedRef.current = false;
    setDrag({ startX: x, startY: y, currentX: x, currentY: y });
  };

  const handlePointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!drag) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    if (
      Math.abs(event.clientX - bounds.left - drag.startX) > 4 ||
      Math.abs(event.clientY - bounds.top - drag.startY) > 4
    ) {
      dragMovedRef.current = true;
    }
    setDrag((current) =>
      current
        ? {
            ...current,
            currentX: Math.min(
              Math.max(event.clientX - bounds.left, 0),
              bounds.width,
            ),
            currentY: Math.min(
              Math.max(event.clientY - bounds.top, 0),
              bounds.height,
            ),
          }
        : undefined,
    );
  };

  const finishDrag = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!drag || !page) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const left = Math.min(drag.startX, drag.currentX);
    const top = Math.min(drag.startY, drag.currentY);
    const width = Math.abs(drag.currentX - drag.startX);
    const height = Math.abs(drag.currentY - drag.startY);
    if (!dragMovedRef.current || width < 4 || height < 4) {
      setDrag(undefined);
      return;
    }
    const canonicalSelection = {
      xMpt: (left / bounds.width) * page.widthMpt,
      yMpt: (top / bounds.height) * page.heightMpt,
      widthMpt: (width / bounds.width) * page.widthMpt,
      heightMpt: (height / bounds.height) * page.heightMpt,
    };
    const selected = pageBlocks
      .filter((block) => {
        const region = {
          xMpt: block.region.x_mpt,
          yMpt: block.region.y_mpt,
          widthMpt: block.region.width_mpt,
          heightMpt: block.region.height_mpt,
        };
        const centerX = region.xMpt + region.widthMpt / 2;
        const centerY = region.yMpt + region.heightMpt / 2;
        const centerInside =
          centerX >= canonicalSelection.xMpt &&
          centerX <= canonicalSelection.xMpt + canonicalSelection.widthMpt &&
          centerY >= canonicalSelection.yMpt &&
          centerY <= canonicalSelection.yMpt + canonicalSelection.heightMpt;
        return (
          centerInside || intersectionRatio(region, canonicalSelection) >= 0.35
        );
      })
      .sort((left, right) => left.reading_order - right.reading_order)
      .map((block) => block.block_id);
    setSelectedBlockIds(selected);
    setPreview(undefined);
    setDrag(undefined);
  };

  const highlighted = setup.questions.filter(
    (question) => question.pageNumber === pageNumber,
  );

  return (
    <section
      className={styles.workspace}
      aria-labelledby="question-setup-title"
    >
      <div className={styles.taskPane}>
        <header className={styles.header}>
          <p className={styles.eyebrow}>
            {editing ? "Fix questions" : "One quick check"}
          </p>
          <h1 id="question-setup-title">
            {editing
              ? "Make the question list match."
              : "Check your questions."}
          </h1>
          <p>
            {editing
              ? "Choose the worksheet text that belongs to each question. Claros will use the exact text you confirm."
              : `We found ${setup.questions.length} ${setup.questions.length === 1 ? "question" : "questions"}. Make sure nothing is missing before you start.`}
          </p>
        </header>

        {errorMessage ? (
          <div className={styles.error} role="alert">
            {errorMessage}
          </div>
        ) : null}

        <ol className={styles.questionList} aria-label="Detected questions">
          {setup.questions.map((question, index) => (
            <li
              key={question.id}
              className={
                question.id === effectiveSelectedQuestionId
                  ? styles.questionItemSelected
                  : styles.questionItem
              }
            >
              <button
                type="button"
                className={styles.questionSelect}
                aria-current={
                  question.id === effectiveSelectedQuestionId
                    ? "true"
                    : undefined
                }
                onClick={() => chooseQuestion(question.id)}
              >
                <span className={styles.questionNumber}>{question.index}</span>
                <span>
                  <strong>{question.prompt}</strong>
                  <small>
                    Page {question.pageNumber}
                    {question.placement === "appendix" ? " · answer page" : ""}
                  </small>
                </span>
              </button>
              {editing ? (
                <div className={styles.questionActions}>
                  <Button
                    color="link-color"
                    size="sm"
                    iconLeading={ScanSearch}
                    onPress={() =>
                      beginSelection({
                        kind: "replace",
                        questionId: question.id,
                      })
                    }
                  >
                    Fix selection
                  </Button>
                  <Button
                    color="tertiary"
                    size="sm"
                    iconLeading={ArrowUp}
                    aria-label={`Move question ${question.index} up`}
                    isDisabled={index === 0 || pending}
                    onPress={() => {
                      const ids = setup.questions.map((item) => item.id);
                      [ids[index - 1], ids[index]] = [
                        ids[index],
                        ids[index - 1],
                      ];
                      void runMutation({
                        kind: "reorder",
                        ordered_question_ids: ids,
                      });
                    }}
                  />
                  <Button
                    color="tertiary"
                    size="sm"
                    iconLeading={ArrowDown}
                    aria-label={`Move question ${question.index} down`}
                    isDisabled={index === setup.questions.length - 1 || pending}
                    onPress={() => {
                      const ids = setup.questions.map((item) => item.id);
                      [ids[index], ids[index + 1]] = [
                        ids[index + 1],
                        ids[index],
                      ];
                      void runMutation({
                        kind: "reorder",
                        ordered_question_ids: ids,
                      });
                    }}
                  />
                  {pendingRemoveId === question.id ? (
                    <span
                      className={styles.removeConfirm}
                      role="group"
                      aria-label="Confirm removal"
                    >
                      <span>Remove it?</span>
                      <Button
                        color="link-gray"
                        size="sm"
                        onPress={() => setPendingRemoveId(undefined)}
                      >
                        Cancel
                      </Button>
                      <Button
                        color="link-destructive"
                        size="sm"
                        onPress={() => {
                          setPendingRemoveId(undefined);
                          void runMutation({
                            kind: "remove",
                            question_id: question.id,
                          });
                        }}
                      >
                        Remove
                      </Button>
                    </span>
                  ) : (
                    <Button
                      color="link-destructive"
                      size="sm"
                      iconLeading={Trash2}
                      aria-label={`Remove question ${question.index}`}
                      onPress={() => setPendingRemoveId(question.id)}
                    />
                  )}
                </div>
              ) : null}
            </li>
          ))}
        </ol>

        {editing ? (
          <div className={styles.editTools}>
            <Button
              color="secondary"
              iconLeading={Plus}
              onPress={() => beginSelection({ kind: "add" })}
            >
              Add missed question
            </Button>
            {setup.provenance === "student_corrected" ? (
              <Button
                color="link-gray"
                iconLeading={RotateCcw}
                isDisabled={pending}
                onPress={() => void runMutation({ kind: "reset" })}
              >
                Reset to detected questions
              </Button>
            ) : null}
          </div>
        ) : null}

        <div className={styles.footerActions}>
          {editing ? (
            <Button color="secondary" onPress={onCancelEdit}>
              Review changes
            </Button>
          ) : (
            <Button color="secondary" onPress={onEnterEdit}>
              Something looks wrong
            </Button>
          )}
          <Button
            iconTrailing={ArrowRight}
            isLoading={pending}
            showTextWhileLoading
            onPress={() => {
              setPending(true);
              void onAccept()
                .catch(onError)
                .finally(() => setPending(false));
            }}
          >
            Looks right — Start
          </Button>
        </div>
      </div>

      <div className={styles.documentPane}>
        <div className={styles.documentHeader}>
          <div>
            <strong>Worksheet</strong>
            <span>Original PDF · read only</span>
          </div>
          <div
            className={styles.pageControls}
            aria-label="Worksheet page controls"
          >
            <Button
              color="tertiary"
              size="sm"
              iconLeading={ArrowLeft}
              aria-label="Previous worksheet page"
              isDisabled={pageNumber === 1}
              onPress={() =>
                setPageNumber((current) => Math.max(1, current - 1))
              }
            />
            <span>
              Page {pageNumber} of {setup.pages.length}
            </span>
            <Button
              color="tertiary"
              size="sm"
              iconLeading={ArrowRight}
              aria-label="Next worksheet page"
              isDisabled={pageNumber === setup.pages.length}
              onPress={() =>
                setPageNumber((current) =>
                  Math.min(setup.pages.length, current + 1),
                )
              }
            />
          </div>
        </div>

        {selectionIntent ? (
          <div className={styles.selectionInstructions}>
            <MousePointer2 aria-hidden="true" />
            <span>
              Drag over the question, tap its text, or use the checkboxes below.
            </span>
            <Button color="link-gray" size="sm" onPress={cancelSelection}>
              Cancel selection
            </Button>
          </div>
        ) : null}

        {page ? (
          <div className={styles.pageFrame}>
            <PageRuntime
              assignmentId={assignment.id}
              sourceUrl={setup.sourceUrl}
              pageNumber={pageNumber}
              widthMpt={page.widthMpt}
              heightMpt={page.heightMpt}
            >
              <div
                className={
                  selectionIntent ? styles.overlaySelecting : styles.overlay
                }
                role="group"
                aria-label={
                  selectionIntent
                    ? "Select question text on worksheet"
                    : "Detected question highlights"
                }
                onPointerDown={handlePointerDown}
                onPointerMove={handlePointerMove}
                onPointerUp={finishDrag}
              >
                {!selectionIntent
                  ? highlighted.flatMap((question) =>
                      question.regions.map((region, regionIndex) => (
                        <button
                          key={`${question.id}-${regionIndex}`}
                          type="button"
                          className={
                            question.id === effectiveSelectedQuestionId
                              ? styles.highlightSelected
                              : styles.highlight
                          }
                          style={{
                            left: percent(region.xMpt, page.widthMpt),
                            top: percent(region.yMpt, page.heightMpt),
                            width: percent(region.widthMpt, page.widthMpt),
                            height: percent(region.heightMpt, page.heightMpt),
                          }}
                          aria-label={`Question ${question.index}: ${question.prompt}`}
                          onPointerDown={(event) => event.stopPropagation()}
                          onClick={() => chooseQuestion(question.id)}
                        >
                          <span>Q{question.index}</span>
                        </button>
                      )),
                    )
                  : pageBlocks.map((block) => {
                      const selected = selectedBlockIds.includes(
                        block.block_id,
                      );
                      return (
                        <button
                          key={block.block_id}
                          type="button"
                          tabIndex={-1}
                          aria-hidden="true"
                          className={
                            selected ? styles.blockSelected : styles.block
                          }
                          style={{
                            left: percent(block.region.x_mpt, page.widthMpt),
                            top: percent(block.region.y_mpt, page.heightMpt),
                            width: percent(
                              block.region.width_mpt,
                              page.widthMpt,
                            ),
                            height: percent(
                              block.region.height_mpt,
                              page.heightMpt,
                            ),
                          }}
                          onClick={() => {
                            if (dragMovedRef.current) {
                              dragMovedRef.current = false;
                              return;
                            }
                            toggleBlock(block.block_id);
                          }}
                        />
                      );
                    })}
                {drag ? (
                  <span
                    className={styles.dragBox}
                    style={{
                      left: Math.min(drag.startX, drag.currentX),
                      top: Math.min(drag.startY, drag.currentY),
                      width: Math.abs(drag.currentX - drag.startX),
                      height: Math.abs(drag.currentY - drag.startY),
                    }}
                  />
                ) : null}
              </div>
            </PageRuntime>
          </div>
        ) : null}

        {selectionIntent ? (
          <div className={styles.blockChooser}>
            <div
              ref={liveRef}
              tabIndex={-1}
              role="group"
              aria-label="Question text selection instructions"
              className={styles.blockChooserHeader}
            >
              <strong>Select the text that belongs to this question</strong>
              <span>{selectedBlockIds.length} selected</span>
            </div>
            <div
              className={styles.blockList}
              role="group"
              aria-label="Worksheet text blocks"
            >
              {pageBlocks.map((block) => (
                <label key={block.block_id} className={styles.blockChoice}>
                  <input
                    type="checkbox"
                    checked={selectedBlockIds.includes(block.block_id)}
                    onChange={() => toggleBlock(block.block_id)}
                  />
                  <span>{block.exact_text}</span>
                </label>
              ))}
            </div>
            {preview ? (
              <div className={styles.exactPreview} role="status">
                <span>Selected question · Page {preview.page_number}</span>
                <strong>{preview.exact_prompt}</strong>
                <p>This exact worksheet text will be used.</p>
                <div>
                  <Button
                    color="secondary"
                    onPress={() => setPreview(undefined)}
                  >
                    Change selection
                  </Button>
                  <Button
                    iconLeading={Check}
                    isLoading={pending}
                    onPress={() => void saveSelection()}
                  >
                    {selectionIntent.kind === "add"
                      ? "Add question"
                      : "Save question"}
                  </Button>
                </div>
              </div>
            ) : (
              <Button
                className={styles.previewButton}
                isDisabled={selectedBlockIds.length === 0}
                isLoading={pending}
                onPress={() => void showSelectionPreview()}
              >
                Check selected text
              </Button>
            )}
          </div>
        ) : null}
      </div>
    </section>
  );
}
