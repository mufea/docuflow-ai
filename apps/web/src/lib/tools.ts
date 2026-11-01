export type ToolDefinition = {
  slug: string;
  name: string;
  description: string;
  href: string;
  group: "edit" | "convert" | "ai";
  inputs: "pdf" | "pdf+" | "image+" | "docx";
};

export const TOOLS: ToolDefinition[] = [
  { slug: "merge", name: "Merge PDFs", description: "Combine two or more PDFs into one file.", href: "/tools/merge", group: "edit", inputs: "pdf+" },
  { slug: "split", name: "Split PDF", description: "Split a PDF into files by page ranges.", href: "/tools/split", group: "edit", inputs: "pdf" },
  { slug: "extract", name: "Extract pages", description: "Keep selected pages, in any order.", href: "/tools/extract", group: "edit", inputs: "pdf" },
  { slug: "reorder", name: "Reorder pages", description: "Rearrange every page without dropping content.", href: "/tools/reorder", group: "edit", inputs: "pdf" },
  { slug: "rotate", name: "Rotate pages", description: "Turn pages by 90, 180, or 270 degrees.", href: "/tools/rotate", group: "edit", inputs: "pdf" },
  { slug: "delete_pages", name: "Delete pages", description: "Remove pages and keep the rest intact.", href: "/tools/delete_pages", group: "edit", inputs: "pdf" },
  { slug: "compress", name: "Compress PDF", description: "Reduce file size with a quality setting.", href: "/tools/compress", group: "edit", inputs: "pdf" },
  { slug: "protect", name: "Protect PDF", description: "Encrypt a PDF with an AES-256 password.", href: "/tools/protect", group: "edit", inputs: "pdf" },
  { slug: "unlock", name: "Unlock PDF", description: "Remove a password you are authorized to use.", href: "/tools/unlock", group: "edit", inputs: "pdf" },
  { slug: "extract_text", name: "Extract text", description: "Pull text with page markers from a PDF.", href: "/tools/extract_text", group: "edit", inputs: "pdf" },
  { slug: "images_to_pdf", name: "Images to PDF", description: "Build a PDF from JPEG, PNG, GIF, or WebP.", href: "/tools/images_to_pdf", group: "convert", inputs: "image+" },
  { slug: "pdf_to_images", name: "PDF to images", description: "Export pages as PNG or JPEG.", href: "/tools/pdf_to_images", group: "convert", inputs: "pdf" },
  { slug: "pdf_to_docx", name: "PDF to Word", description: "Convert to DOCX. Layout is approximate.", href: "/tools/pdf_to_docx", group: "convert", inputs: "pdf" },
  { slug: "pdf_to_xlsx", name: "PDF to Excel", description: "Export detected tables to XLSX.", href: "/tools/pdf_to_xlsx", group: "convert", inputs: "pdf" },
  { slug: "docx_to_pdf", name: "Word to PDF", description: "Convert a Word document to PDF. Complex layout is approximate.", href: "/tools/docx_to_pdf", group: "convert", inputs: "docx" },
  { slug: "ocr", name: "OCR", description: "Recognize text on scanned pages.", href: "/tools/ocr", group: "ai", inputs: "pdf" },
  { slug: "summarize", name: "Summarize", description: "Summarize extracted text with page citations.", href: "/tools/summarize", group: "ai", inputs: "pdf" },
  { slug: "ask", name: "Ask a PDF", description: "Question a document using retrieved excerpts.", href: "/app/assistant", group: "ai", inputs: "pdf" },
  { slug: "extract_structured", name: "Extract data", description: "Pull structured fields from document text.", href: "/tools/extract_structured", group: "ai", inputs: "pdf" },
];

export function toolBySlug(slug: string) {
  return TOOLS.find((tool) => tool.slug === slug);
}
