"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Auth, type User } from "@/lib/api";

export default function AccountPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [name, setName] = useState("");

  useEffect(() => {
    Auth.me().then((me) => {
      setUser(me);
      setName(me.name);
    });
  }, []);

  if (!user) return <p>Loading account…</p>;

  return (
    <div className="max-w-lg space-y-6">
      <h1 className="font-heading text-3xl">Account</h1>
      <form
        className="grid gap-3"
        onSubmit={async (event) => {
          event.preventDefault();
          setUser(await Auth.updateName(name));
        }}
      >
        <label className="grid gap-1.5">
          <Label htmlFor="name">Name</Label>
          <Input id="name" value={name} onChange={(event) => setName(event.target.value)} />
        </label>
        <p className="text-sm text-muted-foreground">{user.email} · {user.plan_slug} · {user.email_verified ? "verified" : "verification pending"}</p>
        <Button type="submit">Save profile</Button>
      </form>
      <Button
        variant="destructive"
        onClick={async () => {
          if (confirm("Delete this account and stored files?")) {
            await Auth.deleteAccount();
            router.push("/");
          }
        }}
      >
        Delete account
      </Button>
    </div>
  );
}
