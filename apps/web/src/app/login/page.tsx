"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Auth } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await Auth.login({ email, password });
      router.push("/app");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to sign in");
    }
  }

  return (
    <>
      <SiteHeader />
      <main className="mx-auto w-full max-w-md px-4 py-16">
        <h1 className="font-heading text-3xl">Sign in</h1>
        <form className="mt-6 grid gap-4" onSubmit={onSubmit}>
          <label className="grid gap-1.5">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
          </label>
          <label className="grid gap-1.5">
            <Label htmlFor="password">Password</Label>
            <Input id="password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required />
          </label>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit">Sign in</Button>
        </form>
        <p className="mt-4 text-sm">
          <Link className="text-primary underline" href="/forgot-password">
            Forgot password
          </Link>
          {" · "}
          <Link className="text-primary underline" href="/register">
            Create an account
          </Link>
        </p>
      </main>
      <SiteFooter />
    </>
  );
}
