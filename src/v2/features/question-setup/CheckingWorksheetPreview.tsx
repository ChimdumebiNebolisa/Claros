import { useMemo } from "react";
import { PDFViewer } from "@embedpdf/react-pdf-viewer";
import { createWorksheetViewerConfig } from "../../document/viewerConfig";
import styles from "./question-setup.module.css";

export function CheckingWorksheetPreview({
  sourceUrl,
  filename,
}: {
  sourceUrl: string;
  filename: string;
}) {
  const config = useMemo(
    () => createWorksheetViewerConfig(sourceUrl, filename),
    [filename, sourceUrl],
  );
  return (
    <aside
      className={styles.checkingPreview}
      aria-label="Worksheet preview while checking"
    >
      <div className={styles.documentHeader}>
        <div>
          <strong>Your worksheet</strong>
          <span>Read-only preview while Claros checks it</span>
        </div>
      </div>
      <div className={styles.checkingViewer}>
        <PDFViewer config={config} className={styles.checkingViewerEmbed} />
      </div>
    </aside>
  );
}
