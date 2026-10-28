"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { SiteHeader } from "@/components/site-header";
import { Auth, type User } from "@/lib/api";
import { buttonVariants } from "@/components/ui/button";

const nav = [
  { href: "/app", label: "Overview" },
  { href: "/app/workspace", label: "Workspace" },
  { href: "/app/jobs", label: "Jobs" },
  { href: "/app/assistant", label: "AI assistant" },
  { href: "/app/usage", label: "Usage" },
  { href: "/app/billing", label: "Billing" },
  { href: "/app/account", label: "Account" },
];

export default function AppLayout({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    Auth.me()
      .then(setUser)
      .catch(() => router.push("/login"));
  }, [router]);

  if (!user) {
    return (
      <>
        <SiteHeader />
        <main className="mx-auto max-w-6xl px-4 py-16">Loading your workspace…</main>
      </>
    );
  }

  return (
    <>
      <SiteHeader />
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-8 md:flex-row">
        <aside className="md:w-52">
          <p className="text-sm text-muted-foreground">{user.name}</p>
          <p className="text-sm font-medium">{user.credits_available} credits</p>
          <nav className="mt-4 grid gap-1 text-sm">
            {nav.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`rounded-md px-3 py-2 ${pathname === item.href ? "bg-primary/10 text-primary" : "hover:bg-muted"}`}
              >
                {item.label}
              </Link>
            ))}
            {user.role === "admin" && (
              <Link href="/admin" className="rounded-md px-3 py-2 hover:bg-muted">
                Admin
              </Link>
            )}
            <button
              className={buttonVariants({ variant: "ghost" })}
              onClick={async () => {
                await Auth.logout();
                router.push("/");
              }}
            >
              Sign out
            </button>
          </nav>
        </aside>
        <div className="min-w-0 flex-1">{children}</div>
      </div>
    </>
  );
}
