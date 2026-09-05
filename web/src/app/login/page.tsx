"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
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
      setLocalError("Unable to enter the demo workspace.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-10">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="text-xl">Log in to FirstRound</CardTitle>
          <p className="text-sm text-muted-foreground">
            Authentication is in demo mode for Phase 2. Continue to open the
            Northwind Labs workspace against the local API.
          </p>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={onSubmit}>
            <div>
              <Label htmlFor="email">Work email</Label>
              <Input
                id="email"
                type="email"
                defaultValue="recruiter@northwind.local"
                autoComplete="email"
              />
            </div>
            <div>
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                defaultValue="demo-password"
                autoComplete="current-password"
              />
            </div>
            {(localError || error) && (
              <p className="text-sm text-danger">{localError || error}</p>
            )}
            <Button className="w-full" disabled={loading}>
              {loading ? "Opening workspace…" : "Continue to dashboard"}
            </Button>
          </form>
          <p className="mt-4 text-sm text-muted-foreground">
            Need an account?{" "}
            <Link href="/signup" className="font-medium text-foreground">
              Sign up
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
