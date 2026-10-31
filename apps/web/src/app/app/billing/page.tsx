"use client";

import { useEffect, useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Billing } from "@/lib/api";

export default function BillingPage() {
  const [plans, setPlans] = useState<Array<Record<string, unknown>>>([]);

  useEffect(() => {
    Billing.plans().then(setPlans);
  }, []);

  return (
    <div className="space-y-4">
      <h1 className="font-heading text-3xl">Subscription</h1>
      <Alert>
        <AlertTitle>Free plan only</AlertTitle>
        <AlertDescription>
          All accounts use the Free plan. Paid Pro and Business checkout is disabled.
        </AlertDescription>
      </Alert>
      <ul className="grid gap-3 md:grid-cols-3">
        {plans.map((plan) => (
          <li key={String(plan.slug)} className="rounded-xl bg-card p-4 ring-1 ring-foreground/10">
            <p className="font-heading text-xl">{String(plan.name)}</p>
            <p className="text-sm text-muted-foreground">{String(plan.monthly_credits)} credits / month</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
