"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";
import { Auth } from "@/lib/api";

function Verify() {
  const params = useSearchParams();
  const token = params.get("token") || "";
  const [message, setMessage] = useState(token ? "Confirming…" : "Missing verification token.");

  useEffect(() => {
    if (!token) {
      return;
    }
    Auth.verify(token)
      .then(() => setMessage("Email verified. You can return to the dashboard."))
      .catch((error) => setMessage(error instanceof Error ? error.message : "Verification failed"));
  }, [token]);

  return <p className="mt-4">{message}</p>;
}

export default function VerifyEmailPage() {
  return (
    <>
      <SiteHeader />
      <main className="mx-auto w-full max-w-md px-4 py-16">
        <h1 className="font-heading text-3xl">Email verification</h1>
        <Suspense>
          <Verify />
        </Suspense>
      </main>
      <SiteFooter />
    </>
  );
}
