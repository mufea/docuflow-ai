import { ToolWorkspace } from "@/components/tool-workspace";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { toolBySlug } from "@/lib/tools";

export default function AssistantPage() {
  const tool = toolBySlug("ask")!;
  return (
    <div className="space-y-4">
      <h1 className="font-heading text-3xl">AI document assistant</h1>
      <Alert>
        <AlertTitle>How answers are produced</AlertTitle>
        <AlertDescription>
          Text is extracted on the server first. The default mock provider never calls a paid model and only cites pages present in that text. Enabling a live provider sends excerpts to that vendor; original PDFs stay in your storage.
        </AlertDescription>
      </Alert>
      <ToolWorkspace tool={tool} credits={8} />
    </div>
  );
}
