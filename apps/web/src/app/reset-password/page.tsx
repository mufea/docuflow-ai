"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Auth } from "@/lib/api";

function ResetForm() {
  const params = useSearchParams();
  const [password, setPassword] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const token = params.get("token") || "";

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    try {
      await Auth.reset(token, password);
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reset failed");
    }
  }

  if (!token) return <p>Missing token.</p>;
  if (done) return <p>Password updated. You can sign in.</p>;

  return (
    <form className="mt-6 grid gap-4" onSubmit={onSubmit}>
      <label className="grid gap-1.5">
        <Label htmlFor="password">New password</Label>
        <Input id="password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} minLength={10} required />
      </label>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <Button type="submit">Update password</Button>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <>
      <SiteHeader />
      <main className="mx-auto w-full max-w-md px-4 py-16">
        <h1 className="font-heading text-3xl">Choose a new password</h1>
        <Suspense>
          <ResetForm />
        </Suspense>
      </main>
      <SiteFooter />
    </>
  );
}
