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

export default function RegisterPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await Auth.register({ name, email, password });
      await Auth.login({ email, password });
      router.push("/app");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to register");
    }
  }

  return (
    <>
      <SiteHeader />
      <main className="mx-auto w-full max-w-md px-4 py-16">
        <h1 className="font-heading text-3xl">Create your account</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Free plan includes 50 credits each month. A verification email is sent through the configured email adapter (console in development).
        </p>
        <form className="mt-6 grid gap-4" onSubmit={onSubmit}>
          <label className="grid gap-1.5">
            <Label htmlFor="name">Name</Label>
            <Input id="name" value={name} onChange={(event) => setName(event.target.value)} required minLength={2} />
          </label>
          <label className="grid gap-1.5">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
          </label>
          <label className="grid gap-1.5">
            <Label htmlFor="password">Password</Label>
            <Input id="password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required minLength={10} />
          </label>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit">Create account</Button>
        </form>
        <p className="mt-4 text-sm">
          Already registered?{" "}
          <Link className="text-primary underline" href="/login">
            Sign in
          </Link>
        </p>
      </main>
      <SiteFooter />
    </>
  );
}
