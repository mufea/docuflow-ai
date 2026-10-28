import Link from "next/link";

export function SiteFooter() {
  return (
    <footer className="mt-auto border-t bg-card">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-4 px-4 py-8 text-sm text-muted-foreground md:flex-row md:items-center md:justify-between">
        <p>© {new Date().getFullYear()} DocuFlow AI. Uploads expire automatically. AI analysis uses extracted text, not silent document forwarding, unless you enable a live provider.</p>
        <div className="flex gap-4">
          <Link href="/privacy">Privacy</Link>
          <Link href="/pricing">Pricing</Link>
          <Link href="/tools">Tools</Link>
        </div>
      </div>
    </footer>
  );
}
