"use client";

import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";

type Props = {
  accept: string;
  multiple?: boolean;
  files: File[];
  onChange: (files: File[]) => void;
  hint: string;
};

export function FileDrop({ accept, multiple = false, files, onChange, hint }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [active, setActive] = useState(false);

  function add(list: FileList | null) {
    if (!list) return;
    const next = Array.from(list);
    onChange(multiple ? [...files, ...next] : next.slice(0, 1));
  }

  return (
    <div
      onDragOver={(event) => {
        event.preventDefault();
        setActive(true);
      }}
      onDragLeave={() => setActive(false)}
      onDrop={(event) => {
        event.preventDefault();
        setActive(false);
        add(event.dataTransfer.files);
      }}
      className={`rounded-xl border-2 border-dashed p-6 text-center transition ${
        active ? "border-primary bg-primary/5" : "border-border bg-card"
      }`}
    >
      <p className="font-medium">Drop files here</p>
      <p className="mt-1 text-sm text-muted-foreground">{hint}</p>
      <input
        ref={inputRef}
        className="sr-only"
        type="file"
        accept={accept}
        multiple={multiple}
        onChange={(event) => add(event.target.files)}
      />
      <Button type="button" className="mt-4" onClick={() => inputRef.current?.click()}>
        Choose files
      </Button>
      {files.length > 0 && (
        <ul className="mt-4 space-y-1 text-left text-sm">
          {files.map((file) => (
            <li key={`${file.name}-${file.size}`} className="rounded-md bg-muted px-3 py-2">
              {file.name} · {(file.size / 1024 / 1024).toFixed(2)} MB
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
