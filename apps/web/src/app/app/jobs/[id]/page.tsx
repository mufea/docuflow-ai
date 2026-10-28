"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Docs, Jobs, type JobRecord } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";

export default function JobDetailPage() {
  const params = useParams<{ id: string }>();
  const [job, setJob] = useState<JobRecord | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let timer: number;
    async function load() {
      try {
        const current = await Jobs.get(params.id);
        setJob(current);
        if (!["completed", "failed", "cancelled"].includes(current.status)) {
          timer = window.setTimeout(load, 800);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Job not found");
      }
    }
    load();
    return () => window.clearTimeout(timer);
  }, [params.id]);

  if (error) return <p className="text-destructive">{error}</p>;
  if (!job) return <p>Loading job…</p>;

  return (
    <div className="space-y-4">
      <h1 className="font-heading text-3xl">{job.operation}</h1>
      <p className="capitalize">{job.status}</p>
      <Progress value={job.progress} />
      {job.error_message && <p className="text-destructive">{job.error_message}</p>}
      {job.status === "queued" && (
        <Button
          onClick={async () => {
            setJob(await Jobs.cancel(job.id));
          }}
        >
          Cancel
        </Button>
      )}
      <div className="space-y-2">
        {job.result_document_ids.map((id) => (
          <a key={id} className="block text-primary underline" href={Docs.downloadUrl(id)}>
            Download {id}
          </a>
        ))}
      </div>
      {typeof job.result_payload.text === "string" && (
        <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-xl bg-card p-4 text-sm ring-1 ring-foreground/10">
          {job.result_payload.text}
        </pre>
      )}
    </div>
  );
}
