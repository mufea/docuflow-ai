import Link from "next/link";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function PricingPage() {
  return (
    <>
      <SiteHeader />
      <main className="mx-auto w-full max-w-6xl px-4 py-10">
        <h1 className="font-heading text-4xl">Pricing</h1>
        <p className="mt-2 max-w-2xl text-muted-foreground">
          Every account is on the Free plan. There is no paid Pro or Business checkout.
        </p>
        <div className="mt-8 max-w-md">
          <Card className="p-2">
            <CardHeader>
              <CardTitle>Free</CardTitle>
              <CardDescription>50 credits / month</CardDescription>
            </CardHeader>
            <div className="space-y-3 px-6 pb-6 text-sm">
              <p>10 MB · 25 pages</p>
              <p className="text-muted-foreground">
                Core PDF tools, conversion, OCR when installed, and the mock AI assistant. No card required.
              </p>
              <Link className={buttonVariants()} href="/register">
                Create a free account
              </Link>
            </div>
          </Card>
        </div>
      </main>
      <SiteFooter />
    </>
  );
}
