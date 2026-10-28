"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Docs, Jobs, type DocumentRecord, type JobRecord } from "@/lib/api";

export default function DashboardPage() {
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [docs, setDocs] = useState<DocumentRecord[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([Jobs.list(), Docs.list()])
      .then(([jobRows, docRows]) => {
        setJobs(jobRows);
        setDocs(docRows);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Unable to load dashboard"));
  }, []);

  if (error) return <p className="text-destructive">{error}</p>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-heading text-3xl">Dashboard</h1>
        <p className="text-muted-foreground">Recent jobs, files, and a shortcut into the workspace.</p>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>{jobs.length}</CardTitle>
            <CardDescription>Jobs in history</CardDescription>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{docs.length}</CardTitle>
            <CardDescription>Files still retained</CardDescription>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>
              <Link href="/app/workspace" className="underline">
                Open workspace
              </Link>
            </CardTitle>
            <CardDescription>Upload and process a document</CardDescription>
          </CardHeader>
        </Card>
      </div>
      <section>
        <h2 className="font-heading text-xl">Latest jobs</h2>
        <ul className="mt-3 divide-y rounded-xl bg-card ring-1 ring-foreground/10">
          {jobs.slice(0, 8).map((job) => (
            <li key={job.id} className="flex items-center justify-between px-4 py-3 text-sm">
              <span>
                {job.operation} · {job.status}
              </span>
              <Link className="text-primary underline" href={`/app/jobs/${job.id}`}>
                View
              </Link>
            </li>
          ))}
          {jobs.length === 0 && <li className="px-4 py-6 text-sm text-muted-foreground">No jobs yet.</li>}
        </ul>
      </section>
    </div>
  );
}
