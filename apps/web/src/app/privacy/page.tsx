import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";

export default function PrivacyPage() {
  return (
    <>
      <SiteHeader />
      <main className="mx-auto w-full max-w-3xl px-4 py-10">
        <h1 className="font-heading text-4xl">Privacy and data processing</h1>
        <div className="mt-6 space-y-4 text-muted-foreground">
          <p>Uploaded files are stored in your account on object storage (filesystem locally, S3-compatible in production). They expire automatically.</p>
          <p>Core PDF tools run on the DocuFlow servers. Document bytes are not sent to an external AI provider unless a live provider is configured and you run an AI tool.</p>
          <p>AI features extract text first. The current default provider is a deterministic mock. Enabling `openai_compatible` sends extracted excerpts, not necessarily the original PDF bytes, to that provider.</p>
          <p>Passwords used to protect or unlock PDFs are used for that job and are not returned in job listings.</p>
          <p>Account deletion removes stored files and revokes sessions.</p>
        </div>
      </main>
      <SiteFooter />
    </>
  );
}
