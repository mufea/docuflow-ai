import Link from "next/link";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { TOOLS } from "@/lib/tools";

export default function HomePage() {
  return (
    <>
      <SiteHeader />
      <main className="mx-auto w-full max-w-6xl px-4 py-12">
        <section className="grid items-center gap-10 lg:grid-cols-[1.2fr_0.8fr]">
          <div>
            <p className="text-sm uppercase tracking-[0.2em] text-primary">PDF processing for real documents</p>
            <h1 className="mt-3 max-w-2xl font-heading text-4xl leading-tight md:text-6xl">
              Merge, repair, convert, and question PDFs without pretending the hard parts are done.
            </h1>
            <p className="mt-5 max-w-xl text-lg text-muted-foreground">
              DocuFlow AI runs actual server-side PDF operations, stores files off the web process, and keeps AI optional. Free accounts include monthly credits. Paid plans are defined in configuration, not hardcoded UI.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link className={buttonVariants({ size: "lg" })} href="/register">
                Start on the Free plan
              </Link>
              <Link className={buttonVariants({ size: "lg", variant: "outline" })} href="/tools">
                Browse tools
              </Link>
            </div>
          </div>
          <Card className="p-6">
            <CardHeader>
              <CardTitle>What is implemented</CardTitle>
              <CardDescription>Not a gallery of inert buttons.</CardDescription>
            </CardHeader>
            <ul className="space-y-2 px-6 pb-6 text-sm">
              <li>12 core PDF tools with content validation</li>
              <li>Background jobs with progress and downloads</li>
              <li>Argon2 accounts, CSRF, and per-user file isolation</li>
              <li>Integer credit ledger and plan limits</li>
              <li>Mock AI with page citations; live providers stay off until configured</li>
            </ul>
          </Card>
        </section>
        <section className="mt-16 grid gap-4 md:grid-cols-3">
          {TOOLS.slice(0, 9).map((tool) => (
            <Link key={tool.slug} href={tool.href}>
              <Card className="h-full hover:ring-primary/30">
                <CardHeader>
                  <CardTitle>{tool.name}</CardTitle>
                  <CardDescription>{tool.description}</CardDescription>
                </CardHeader>
              </Card>
            </Link>
          ))}
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
