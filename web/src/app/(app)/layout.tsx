"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { AppSidebar } from "@/components/app-sidebar";
import { PageSkeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/error-state";
import { useAuth } from "@/lib/auth";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { ready, authenticated, error, enterDemo } = useAuth();

  useEffect(() => {
    if (ready && !authenticated) {
      // Allow View demo deep-links by auto-entering demo when visiting app routes.
      void enterDemo();
    }
  }, [ready, authenticated, enterDemo]);

  if (!ready) {
    return (
      <div className="mx-auto max-w-6xl p-6">
        <PageSkeleton />
      </div>
    );
  }

  if (error && !authenticated) {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <ErrorState
          title="API unavailable"
          description={error}
          onRetry={() => router.push("/login")}
        />
      </div>
    );
  }

  return (
    <div className="min-h-screen lg:flex">
      <AppSidebar />
      <main className="min-w-0 flex-1">
        <div className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:py-8">
          {children}
        </div>
      </main>
    </div>
  );
}
