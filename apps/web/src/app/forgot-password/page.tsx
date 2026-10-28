"use client";

import { useState, type FormEvent } from "react";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Auth } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [done, setDone] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    await Auth.forgot(email);
    setDone(true);
  }

  return (
    <>
      <SiteHeader />
      <main className="mx-auto w-full max-w-md px-4 py-16">
        <h1 className="font-heading text-3xl">Reset password</h1>
        {done ? (
          <p className="mt-4 text-sm">If an account exists, a reset link was sent. In development it prints to the API console.</p>
        ) : (
          <form className="mt-6 grid gap-4" onSubmit={onSubmit}>
            <label className="grid gap-1.5">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
            </label>
            <Button type="submit">Send reset link</Button>
          </form>
        )}
      </main>
      <SiteFooter />
    </>
  );
}
