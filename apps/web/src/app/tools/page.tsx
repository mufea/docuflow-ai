import Link from "next/link";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { TOOLS } from "@/lib/tools";

export default function ToolsPage() {
  const groups = [
    { id: "edit", title: "Edit PDFs" },
    { id: "convert", title: "Convert" },
    { id: "ai", title: "AI and OCR" },
  ] as const;

  return (
    <>
      <SiteHeader />
      <main className="mx-auto w-full max-w-6xl px-4 py-10">
        <h1 className="font-heading text-4xl">Tools</h1>
        <p className="mt-2 max-w-2xl text-muted-foreground">
          Every tool submits a real processing job. If an engine is missing on the server, the page says so instead of faking success.
        </p>
        {groups.map((group) => (
          <section key={group.id} className="mt-10">
            <h2 className="font-heading text-2xl">{group.title}</h2>
            <div className="mt-4 grid gap-4 md:grid-cols-3">
              {TOOLS.filter((tool) => tool.group === group.id).map((tool) => (
                <Link key={tool.slug} href={tool.href}>
                  <Card className="h-full">
                    <CardHeader>
                      <CardTitle>{tool.name}</CardTitle>
                      <CardDescription>{tool.description}</CardDescription>
                    </CardHeader>
                  </Card>
                </Link>
              ))}
            </div>
          </section>
        ))}
      </main>
      <SiteFooter />
    </>
  );
}
