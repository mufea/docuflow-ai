"use client";

import { useEffect, useState } from "react";
import { Billing } from "@/lib/api";

export default function UsagePage() {
  const [usage, setUsage] = useState<Record<string, unknown> | null>(null);
  const [ledger, setLedger] = useState<Array<Record<string, unknown>>>([]);

  useEffect(() => {
    Billing.usage().then(setUsage);
    Billing.ledger().then(setLedger);
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="font-heading text-3xl">Usage and credits</h1>
      {usage && (
        <div className="grid gap-3 md:grid-cols-3">
          <Stat label="Available" value={String(usage.available)} />
          <Stat label="Reserved" value={String(usage.reserved)} />
          <Stat label="Used this period" value={String(usage.period_used)} />
        </div>
      )}
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-muted-foreground">
            <th className="py-2">Type</th>
            <th>Amount</th>
            <th>Description</th>
          </tr>
        </thead>
        <tbody>
          {ledger.map((row) => (
            <tr key={String(row.id)} className="border-t">
              <td className="py-2">{String(row.entry_type)}</td>
              <td>{String(row.amount)}</td>
              <td>{String(row.description)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="font-heading text-2xl">{value}</p>
    </div>
  );
}
