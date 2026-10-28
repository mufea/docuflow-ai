import Link from "next/link";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const plans = [
  {
    slug: "free",
    name: "Free",
    credits: "50 credits / month",
    limits: "10 MB · 25 pages",
    detail: "Core PDF tools, retention windows, and mock AI. No card required.",
  },
  {
    slug: "pro",
    name: "Pro",
    credits: "500 credits / month",
    limits: "50 MB · 200 pages",
    detail: "Higher allowances for professionals. Stripe and Midtrans adapters are ready; live charges stay off until authorized.",
  },
  {
    slug: "business",
    name: "Business",
    credits: "2,000 credits / month",
    limits: "100 MB · 500 pages",
    detail: "Team-scale processing limits. Entitlements change only after verified webhooks, never after a browser redirect.",
  },
];

export default function PricingPage() {
  return (
    <>
      <SiteHeader />
      <main className="mx-auto w-full max-w-6xl px-4 py-10">
        <h1 className="font-heading text-4xl">Pricing</h1>
        <p className="mt-2 max-w-2xl text-muted-foreground">
          Usage is measured in integer credits. Operation costs live in the database so they can change without rewriting the app. Checkout is sandbox-ready and not live.
        </p>
        <div className="mt-8 grid gap-4 md:grid-cols-3">
          {plans.map((plan) => (
            <Card key={plan.slug} className="p-2">
              <CardHeader>
                <CardTitle>{plan.name}</CardTitle>
                <CardDescription>{plan.credits}</CardDescription>
              </CardHeader>
              <div className="space-y-3 px-6 pb-6 text-sm">
                <p>{plan.limits}</p>
                <p className="text-muted-foreground">{plan.detail}</p>
                <Link className={buttonVariants()} href="/register">
                  Create a {plan.name} account
                </Link>
              </div>
            </Card>
          ))}
        </div>
      </main>
      <SiteFooter />
    </>
  );
}
