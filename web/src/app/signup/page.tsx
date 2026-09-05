"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { useAuth } from "@/lib/auth";

export default function SignupPage() {
  const router = useRouter();
  const { enterDemo, error } = useAuth();
  const [loading, setLoading] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setLocalError(null);
    try {
      await enterDemo();
      router.push("/dashboard");
    } catch {
      setLocalError("Unable to create the demo workspace session.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-10">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="text-xl">Create your FirstRound workspace</CardTitle>
          <p className="text-sm text-muted-foreground">
            Phase 2 uses a clear development auth placeholder. Real email/password
            and Google login will plug into this screen later via Supabase Auth.
          </p>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={onSubmit}>
            <div>
              <Label htmlFor="name">Full name</Label>
              <Input id="name" defaultValue="Northwind Recruiter" />
            </div>
            <div>
              <Label htmlFor="org">Organization</Label>
              <Input id="org" defaultValue="Northwind Labs" />
            </div>
            <div>
              <Label htmlFor="email">Work email</Label>
              <Input
                id="email"
                type="email"
                defaultValue="recruiter@northwind.local"
              />
            </div>
            <div>
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" defaultValue="demo-password" />
            </div>
            {(localError || error) && (
              <p className="text-sm text-danger">{localError || error}</p>
            )}
            <Button className="w-full" disabled={loading}>
              {loading ? "Creating session…" : "Start interviewing"}
            </Button>
          </form>
          <p className="mt-4 text-sm text-muted-foreground">
            Already have access?{" "}
            <Link href="/login" className="font-medium text-foreground">
              Log in
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
