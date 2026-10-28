import { notFound } from "next/navigation";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { ToolWorkspace } from "@/components/tool-workspace";
import { toolBySlug } from "@/lib/tools";

export default async function ToolPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const tool = toolBySlug(slug);
  if (!tool) notFound();

  return (
    <>
      <SiteHeader />
      <main className="mx-auto w-full max-w-6xl px-4 py-10">
        <p className="text-sm text-primary">PDF tool</p>
        <h1 className="font-heading text-4xl">{tool.name}</h1>
        <p className="mt-2 max-w-2xl text-muted-foreground">{tool.description}</p>
        <div className="mt-8">
          <ToolWorkspace tool={tool} />
        </div>
      </main>
      <SiteFooter />
    </>
  );
}
