"use client";

import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/lib/auth";
import { getApiBaseUrl } from "@/lib/api/client";

export default function SettingsPage() {
  const { organization, email, fullName } = useAuth();

  return (
    <div>
      <PageHeader
        title="Settings"
        description="Workspace preferences and development auth context"
      />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Organization</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex justify-between gap-4">
              <span className="text-muted-foreground">Name</span>
              <span>{organization?.name || "—"}</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-muted-foreground">Slug</span>
              <span>{organization?.slug || "—"}</span>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Development identity</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex justify-between gap-4">
              <span className="text-muted-foreground">Recruiter</span>
              <span>{fullName}</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-muted-foreground">Email</span>
              <span>{email}</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-muted-foreground">API</span>
              <span className="truncate">{getApiBaseUrl()}</span>
            </div>
            <p className="pt-2 text-xs text-muted-foreground">
              Auth is a Phase 2 placeholder. Supabase Auth will replace this
              without spreading fake-user logic across pages.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
