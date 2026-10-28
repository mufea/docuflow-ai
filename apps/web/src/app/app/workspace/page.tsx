import { ToolWorkspace } from "@/components/tool-workspace";
import { toolBySlug } from "@/lib/tools";

export default function WorkspacePage() {
  const tool = toolBySlug("merge")!;
  return (
    <div className="space-y-4">
      <h1 className="font-heading text-3xl">Workspace</h1>
      <p className="text-muted-foreground">
        Start with merge or pick any tool from the directory. Processing happens in a background job so the browser is never held open for OCR, conversion, or AI.
      </p>
      <ToolWorkspace tool={tool} credits={1} />
    </div>
  );
}
