export const JOB_STATUSES = ["queued", "processing", "completed", "failed", "cancelled"] as const;
export type JobStatus = (typeof JOB_STATUSES)[number];

export const OPERATIONS = [
  "merge",
  "split",
  "extract",
  "reorder",
  "rotate",
  "delete_pages",
  "compress",
  "images_to_pdf",
  "pdf_to_images",
  "extract_text",
  "protect",
  "unlock",
  "thumbnails",
  "pdf_to_docx",
  "pdf_to_xlsx",
  "docx_to_pdf",
  "ocr",
  "summarize",
  "ask",
  "extract_structured",
] as const;

export type Operation = (typeof OPERATIONS)[number];
