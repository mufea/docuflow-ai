"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Menu } from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Auth, type User } from "@/lib/api";

const links = [
  { href: "/tools", label: "Tools" },
  { href: "/pricing", label: "Pricing" },
  { href: "/app/assistant", label: "AI assistant" },
];

export function SiteHeader() {
  const [user, setUser] = useState<User | null | undefined>(undefined);

  useEffect(() => {
    Auth.me()
      .then(setUser)
      .catch(() => setUser(null));
  }, []);

  return (
    <header className="sticky top-0 z-40 border-b bg-card/80 backdrop-blur">
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-4">
        <Link href="/" className="font-heading text-xl tracking-tight">
          DocuFlow <span className="text-primary">AI</span>
        </Link>
        <nav className="hidden items-center gap-6 text-sm md:flex">
          {links.map((link) => (
            <Link key={link.href} href={link.href} className="text-muted-foreground hover:text-foreground">
              {link.label}
            </Link>
          ))}
        </nav>
        <div className="hidden items-center gap-2 md:flex">
          {user ? (
            <>
              <span className="text-sm text-muted-foreground">{user.credits_available} credits</span>
              <Link className={buttonVariants()} href="/app">
                Dashboard
              </Link>
            </>
          ) : user === null ? (
            <>
              <Link className={buttonVariants({ variant: "ghost" })} href="/login">
                Sign in
              </Link>
              <Link className={buttonVariants()} href="/register">
                Create account
              </Link>
            </>
          ) : null}
        </div>
        <Sheet>
          <SheetTrigger className="md:hidden" aria-label="Open menu">
            <Menu className="size-5" />
          </SheetTrigger>
          <SheetContent>
            <div className="mt-8 flex flex-col gap-4 p-4">
              {links.map((link) => (
                <Link key={link.href} href={link.href}>
                  {link.label}
                </Link>
              ))}
              <Link href={user ? "/app" : "/login"}>{user ? "Dashboard" : "Sign in"}</Link>
            </div>
          </SheetContent>
        </Sheet>
      </div>
    </header>
  );
}
