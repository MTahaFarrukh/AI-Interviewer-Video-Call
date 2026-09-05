"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input, Label, Textarea } from "@/components/ui/input";
import { ErrorState } from "@/components/error-state";
import { useAuth } from "@/lib/auth";
import { createJob } from "@/lib/api/jobs";
import type { JobStatus } from "@/lib/api/types";
import { ApiError } from "@/lib/api/client";

export default function NewJobPage() {
  const router = useRouter();
  const { organization } = useAuth();
  const [title, setTitle] = useState("");
  const [department, setDepartment] = useState("");
  const [location, setLocation] = useState("");
  const [employmentType, setEmploymentType] = useState("full_time");
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState<JobStatus>("draft");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!organization) return;
    if (!title.trim()) {
      setError("Title is required.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const job = await createJob(organization.id, {
        title: title.trim(),
        department: department || null,
        location: location || null,
        employment_type: employmentType || null,
        description,
        status,
      });
      router.push(`/jobs/${job.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "Failed to create job");
      setLoading(false);
    }
  }

  if (!organization) {
    return <ErrorState description="No organization selected." />;
  }

  return (
    <div>
      <PageHeader
        title="Create job"
        description="Define the role FirstRound will screen against"
      />
      <Card>
        <CardContent className="pt-5">
          <form className="space-y-4" onSubmit={onSubmit}>
            <div>
              <Label htmlFor="title">Title</Label>
              <Input
                id="title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Junior AI Engineer"
                required
              />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="department">Department</Label>
                <Input
                  id="department"
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="location">Location</Label>
                <Input
                  id="location"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                />
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="employment">Employment type</Label>
                <select
                  id="employment"
                  className="h-10 w-full rounded-lg border border-border bg-card px-3 text-sm"
                  value={employmentType}
                  onChange={(e) => setEmploymentType(e.target.value)}
                >
                  <option value="full_time">Full-time</option>
                  <option value="part_time">Part-time</option>
                  <option value="contract">Contract</option>
                  <option value="internship">Internship</option>
                </select>
              </div>
              <div>
                <Label htmlFor="status">Status</Label>
                <select
                  id="status"
                  className="h-10 w-full rounded-lg border border-border bg-card px-3 text-sm"
                  value={status}
                  onChange={(e) => setStatus(e.target.value as JobStatus)}
                >
                  <option value="draft">Draft</option>
                  <option value="active">Active</option>
                  <option value="closed">Closed</option>
                  <option value="archived">Archived</option>
                </select>
              </div>
            </div>
            <div>
              <Label htmlFor="description">Job description</Label>
              <Textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Paste or write the role description…"
              />
            </div>
            {error ? <p className="text-sm text-danger">{error}</p> : null}
            <div className="flex gap-2">
              <Button type="submit" disabled={loading}>
                {loading ? "Creating…" : "Create job"}
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={() => router.push("/jobs")}
              >
                Cancel
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
