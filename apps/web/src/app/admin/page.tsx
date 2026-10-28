"use client";

import { useEffect, useState } from "react";
import { SiteHeader } from "@/components/site-header";
import { Admin } from "@/lib/api";

export default function AdminPage() {
  const [overview, setOverview] = useState<Record<string, unknown> | null>(null);
  const [users, setUsers] = useState<Array<Record<string, unknown>>>([]);
  const [jobs, setJobs] = useState<Array<Record<string, unknown>>>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([Admin.overview(), Admin.users(), Admin.jobs()])
      .then(([o, u, j]) => {
        setOverview(o);
        setUsers(u);
        setJobs(j);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Admin access required"));
  }, []);

  return (
    <>
      <SiteHeader />
      <main className="mx-auto w-full max-w-6xl px-4 py-10">
        <h1 className="font-heading text-3xl">Admin</h1>
        {error && <p className="mt-4 text-destructive">{error}</p>}
        {overview && (
          <p className="mt-2 text-muted-foreground">
            {String(overview.users)} users · {String(overview.jobs)} jobs · {String(overview.failed_jobs)} failed
          </p>
        )}
        <section className="mt-8">
          <h2 className="font-heading text-xl">Users</h2>
          <ul className="mt-2 divide-y rounded-xl bg-card ring-1 ring-foreground/10">
            {users.map((user) => (
              <li key={String(user.id)} className="px-4 py-3 text-sm">
                {String(user.email)} · {String(user.plan_slug)} · {String(user.role)}
              </li>
            ))}
          </ul>
        </section>
        <section className="mt-8">
          <h2 className="font-heading text-xl">Jobs</h2>
          <ul className="mt-2 divide-y rounded-xl bg-card ring-1 ring-foreground/10">
            {jobs.map((job) => (
              <li key={String(job.id)} className="px-4 py-3 text-sm">
                {String(job.operation)} · {String(job.status)} · {String(job.error_code || "ok")}
              </li>
            ))}
          </ul>
        </section>
      </main>
    </>
  );
}
