"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BriefcaseBusiness,
  LayoutDashboard,
  Menu,
  Settings,
  Users,
  Video,
  X,
} from "lucide-react";
import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/jobs", label: "Jobs", icon: BriefcaseBusiness },
  { href: "/candidates", label: "Candidates", icon: Users },
  { href: "/interviews", label: "Interviews", icon: Video },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function AppSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { organization, organizations, setOrganizationId, fullName, email, leaveDemo } =
    useAuth();
  const [open, setOpen] = useState(false);

  const content = (
    <div className="flex h-full flex-col">
      <div className="border-b border-sidebar-border px-4 py-5">
        <Link href="/dashboard" className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-sm font-semibold text-primary-foreground">
            F
          </span>
          <div>
            <div className="text-sm font-semibold tracking-tight">FirstRound</div>
            <div className="text-xs text-muted-foreground">Technical screening</div>
          </div>
        </Link>
        <label className="mt-4 block text-xs font-medium text-muted-foreground">
          Organization
        </label>
        <select
          className="mt-1.5 h-9 w-full rounded-lg border border-border bg-card px-2 text-sm"
          value={organization?.id || ""}
          onChange={(e) => setOrganizationId(e.target.value)}
          aria-label="Organization switcher"
        >
          {organizations.map((org) => (
            <option key={org.id} value={org.id}>
              {org.name}
            </option>
          ))}
        </select>
      </div>

      <nav className="flex-1 space-y-1 p-3" aria-label="Primary">
        {nav.map((item) => {
          const active =
            pathname === item.href || pathname.startsWith(`${item.href}/`);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setOpen(false)}
              className={cn(
                "flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-sidebar-border p-4">
        <div className="text-sm font-medium">{fullName}</div>
        <div className="text-xs text-muted-foreground">{email}</div>
        <Button
          variant="ghost"
          size="sm"
          className="mt-3 px-0"
          onClick={() => {
            leaveDemo();
            router.push("/login");
          }}
        >
          Sign out
        </Button>
      </div>
    </div>
  );

  return (
    <>
      <div className="sticky top-0 z-30 flex items-center justify-between border-b border-border bg-card px-4 py-3 lg:hidden">
        <div className="text-sm font-semibold">FirstRound</div>
        <Button
          variant="secondary"
          size="icon"
          aria-label={open ? "Close menu" : "Open menu"}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
        </Button>
      </div>

      <aside className="hidden w-64 shrink-0 border-r border-sidebar-border bg-sidebar lg:block">
        {content}
      </aside>

      {open ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            className="absolute inset-0 bg-black/40"
            aria-label="Close navigation overlay"
            onClick={() => setOpen(false)}
          />
          <div className="absolute inset-y-0 left-0 w-72 bg-sidebar shadow-xl">
            {content}
          </div>
        </div>
      ) : null}
    </>
  );
}
