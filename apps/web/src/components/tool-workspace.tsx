"use client";

import { useMemo, useState, type ReactNode } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Textarea } from "@/components/ui/textarea";
import { FileDrop } from "@/components/file-drop";
import { Auth, Docs, Jobs, type JobRecord } from "@/lib/api";
import { type ToolDefinition } from "@/lib/tools";

type Props = {
  tool: ToolDefinition;
  available?: boolean;
  unavailableReason?: string;
  credits?: number;
};

function acceptFor(tool: ToolDefinition) {
  if (tool.inputs === "image+") return "image/png,image/jpeg,image/gif,image/webp,.png,.jpg,.jpeg,.gif,.webp";
  if (tool.inputs === "docx") return ".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document";
  return "application/pdf,.pdf";
}

export function ToolWorkspace({ tool, available = true, unavailableReason, credits }: Props) {
  const [runCount, setRunCount] = useState(0);
  const [files, setFiles] = useState<File[]>([]);
  const [ranges, setRanges] = useState("1-2");
  const [pages, setPages] = useState("1,2");
  const [order, setOrder] = useState("1,2,3");
  const [rotations, setRotations] = useState("1:90");
  const [level, setLevel] = useState("medium");
  const [password, setPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [format, setFormat] = useState("png");
  const [question, setQuestion] = useState("What is this document about?");
  const [busy, setBusy] = useState(false);
  const [job, setJob] = useState<JobRecord | null>(null);
  const multiple = tool.inputs.endsWith("+");

  const hint = useMemo(() => {
    if (tool.inputs === "pdf+") return "PDF files, maximum 50 MB each on Free. Contents are validated, not just the extension.";
    if (tool.inputs === "image+") return "JPEG, PNG, GIF, or WebP. Images are inspected before conversion.";
    if (tool.inputs === "docx") return "DOCX only. Text, tables, and images are converted. Complex Word layout is approximate.";
    return "A single PDF. Encrypted files need the password you are authorized to use.";
  }, [tool.inputs]);

  async function run() {
    setBusy(true);
    setJob(null);
    try {
      await Auth.me();
      if (!files.length) throw new Error("Choose at least one file.");
      const uploaded = [];
      for (const file of files) {
        uploaded.push(await Docs.upload(file));
      }
      const params: Record<string, unknown> = {};
      if (["split"].includes(tool.slug)) params.ranges = ranges;
      if (["extract", "delete_pages", "pdf_to_images", "extract_text", "ocr", "summarize"].includes(tool.slug)) {
        params.pages = pages.includes("-") ? pages : pages.split(",").map((item) => Number(item.trim())).filter(Boolean);
      }
      if (tool.slug === "reorder") params.order = order.split(",").map((item) => Number(item.trim()));
      if (tool.slug === "rotate") {
        params.rotations = Object.fromEntries(
          rotations.split(",").map((pair) => {
            const [page, angle] = pair.split(":").map((item) => Number(item.trim()));
            return [page, angle];
          })
        );
      }
      if (tool.slug === "compress") params.level = level;
      if (tool.slug === "protect") params.new_password = newPassword;
      if (["unlock", "protect"].includes(tool.slug) && password) params.password = password;
      if (tool.slug === "unlock") params.password = password;
      if (tool.slug === "pdf_to_images") params.format = format;
      if (tool.slug === "ask") params.question = question;
      if (tool.slug === "extract_structured") {
        params.schema = {
          type: "object",
          properties: { title: { type: "string" }, dates: { type: "array" } },
        };
      }
      const nextRun = runCount + 1;
      setRunCount(nextRun);
      const created = await Jobs.create({
        operation: tool.slug,
        document_ids: uploaded.map((item) => item.id),
        params,
        idempotency_key: `${tool.slug}-${uploaded.map((item) => item.id).join("-")}-${nextRun}`,
      });
      setJob(created);
      await poll(created.id);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Processing failed");
    } finally {
      setBusy(false);
    }
  }

  async function poll(id: string) {
    for (let attempt = 0; attempt < 80; attempt += 1) {
      const current = await Jobs.get(id);
      setJob(current);
      if (["completed", "failed", "cancelled"].includes(current.status)) {
        if (current.status === "completed") toast.success("Processing finished");
        if (current.status === "failed") toast.error(current.error_message || "Job failed");
        return;
      }
      await new Promise((resolve) => setTimeout(resolve, 400));
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
      <div className="space-y-4">
        {!available && (
          <Alert>
            <AlertTitle>Unavailable on this server</AlertTitle>
            <AlertDescription>{unavailableReason || "The required engine is not installed."}</AlertDescription>
          </Alert>
        )}
        <FileDrop accept={acceptFor(tool)} multiple={multiple} files={files} onChange={setFiles} hint={hint} />
        <div className="grid gap-4 md:grid-cols-2">
          {tool.slug === "split" && (
            <Field label="Page ranges" hint="Example: 1-2,4">
              <Input value={ranges} onChange={(event) => setRanges(event.target.value)} />
            </Field>
          )}
          {["extract", "delete_pages", "pdf_to_images", "extract_text", "ocr", "summarize"].includes(tool.slug) && (
            <Field label="Pages" hint="Comma list or a range such as 2-5">
              <Input value={pages} onChange={(event) => setPages(event.target.value)} />
            </Field>
          )}
          {tool.slug === "reorder" && (
            <Field label="New order" hint="Permutation of every page, e.g. 3,2,1">
              <Input value={order} onChange={(event) => setOrder(event.target.value)} />
            </Field>
          )}
          {tool.slug === "rotate" && (
            <Field label="Rotations" hint="page:degrees, e.g. 1:90,2:180">
              <Input value={rotations} onChange={(event) => setRotations(event.target.value)} />
            </Field>
          )}
          {tool.slug === "compress" && (
            <Field label="Level">
              <select
                className="h-8 rounded-lg border bg-background px-2"
                value={level}
                onChange={(event) => setLevel(event.target.value)}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </Field>
          )}
          {tool.slug === "pdf_to_images" && (
            <Field label="Image format">
              <select
                className="h-8 rounded-lg border bg-background px-2"
                value={format}
                onChange={(event) => setFormat(event.target.value)}
              >
                <option value="png">PNG</option>
                <option value="jpeg">JPEG</option>
              </select>
            </Field>
          )}
          {tool.slug === "protect" && (
            <Field label="New password">
              <Input type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} />
            </Field>
          )}
          {["unlock", "protect"].includes(tool.slug) && (
            <Field label={tool.slug === "unlock" ? "Current password" : "Password if already encrypted"}>
              <Input type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
            </Field>
          )}
          {tool.slug === "ask" && (
            <div className="md:col-span-2">
              <Field label="Question">
                <Textarea value={question} onChange={(event) => setQuestion(event.target.value)} />
              </Field>
            </div>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={run} disabled={busy || !available}>
            {busy ? "Working…" : `Run ${tool.name}`}
          </Button>
          {typeof credits === "number" && (
            <span className="text-sm text-muted-foreground">{credits} credit{credits === 1 ? "" : "s"} reserved for this operation</span>
          )}
          <Link className="text-sm text-primary underline" href="/login">
            Sign in required
          </Link>
        </div>
      </div>
      <aside className="space-y-4 rounded-xl bg-card p-5 ring-1 ring-foreground/10">
        <h2 className="font-heading text-lg">Job status</h2>
        {!job && <p className="text-sm text-muted-foreground">Results appear here. Original uploads are never overwritten.</p>}
        {job && (
          <div className="space-y-3 text-sm">
            <p className="capitalize">{job.status}</p>
            <Progress value={job.progress} />
            {job.error_message && <p className="text-destructive">{job.error_message}</p>}
            {job.result_document_ids.map((id) => (
              <a key={id} className="block text-primary underline" href={Docs.downloadUrl(id)}>
                Download result
              </a>
            ))}
            {typeof job.result_payload.text === "string" && (
              <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-md bg-muted p-3 text-xs">
                {job.result_payload.text}
              </pre>
            )}
            {Array.isArray(job.result_payload.citations) && (
              <ul className="list-disc pl-4">
                {(job.result_payload.citations as Array<{ page: number; quote: string }>).map((item, index) => (
                  <li key={index}>
                    Page {item.page}: {item.quote}
                  </li>
                ))}
              </ul>
            )}
            {Array.isArray(job.result_payload.limitations) && (
              <Alert>
                <AlertTitle>Conversion limits</AlertTitle>
                <AlertDescription>
                  {(job.result_payload.limitations as string[]).slice(0, 3).join(" ")}
                </AlertDescription>
              </Alert>
            )}
            <Link className="text-primary underline" href={`/app/jobs/${job.id}`}>
              Open in job history
            </Link>
          </div>
        )}
        <div className="text-xs text-muted-foreground">
          Files are stored in your account and expire on a retention schedule. Live AI providers are off unless an operator enables them. The mock assistant only cites pages that exist in extracted text.
        </div>
      </aside>
    </div>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="grid gap-1.5">
      <Label>{label}</Label>
      {children}
      {hint && <span className="text-xs text-muted-foreground">{hint}</span>}
    </label>
  );
}
