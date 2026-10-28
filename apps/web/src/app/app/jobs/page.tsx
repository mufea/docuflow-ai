"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Jobs, type JobRecord } from "@/lib/api";

export default function JobsPage() {
  const [jobs, setJobs] = useState<JobRecord[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Jobs.list()
      .then(setJobs)
      .catch((err) => setError(err instanceof Error ? err.message : "Unable to load jobs"));
  }, []);

  if (error) return <p className="text-destructive">{error}</p>;

  return (
    <div>
      <h1 className="font-heading text-3xl">Job history</h1>
      <ul className="mt-4 divide-y rounded-xl bg-card ring-1 ring-foreground/10">
        {jobs.map((job) => (
          <li key={job.id} className="grid gap-1 px-4 py-3 md:grid-cols-[1fr_auto_auto] md:items-center">
            <div>
              <p className="font-medium">{job.operation}</p>
              <p className="text-sm text-muted-foreground">{job.id}</p>
            </div>
            <span className="capitalize">{job.status}</span>
            <Link className="text-primary underline" href={`/app/jobs/${job.id}`}>
              Details
            </Link>
          </li>
        ))}
        {jobs.length === 0 && <li className="px-4 py-8 text-muted-foreground">No processing jobs yet.</li>}
      </ul>
    </div>
  );
}
