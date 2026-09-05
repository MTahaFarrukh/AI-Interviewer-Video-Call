import Link from "next/link";
import {
  MarketingFooter,
  MarketingHeader,
} from "@/components/marketing/chrome";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const tiers = [
  {
    name: "Starter",
    blurb: "For small teams testing AI interviews",
    points: ["Single workspace", "Core interview workflow", "Evidence-backed scorecards"],
    cta: "Get started",
    href: "/signup",
  },
  {
    name: "Growth",
    blurb: "For active hiring teams",
    points: ["Multiple roles", "Candidate pipeline", "Recruiter review tools"],
    cta: "Get started",
    href: "/signup",
    featured: true,
  },
  {
    name: "Enterprise",
    blurb: "For organizations needing custom controls",
    points: ["Advanced permissions", "Security review", "Dedicated onboarding"],
    cta: "Contact sales",
    href: "mailto:hello@firstround.local",
  },
];

export default function PricingPage() {
  return (
    <div className="min-h-screen">
      <MarketingHeader />
      <main className="mx-auto w-full max-w-6xl px-4 py-14 sm:px-6">
        <div className="max-w-2xl">
          <p className="text-sm font-medium text-primary">Early access</p>
          <h1 className="mt-2 text-4xl font-semibold tracking-tight">Pricing</h1>
          <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
            Billing is not live yet. These tiers describe the planned product
            packages for FirstRound. Join early access to explore the recruiter
            workspace with seeded demo data.
          </p>
        </div>
        <div className="mt-10 grid gap-4 lg:grid-cols-3">
          {tiers.map((tier) => (
            <Card
              key={tier.name}
              className={tier.featured ? "border-primary/40 shadow-md" : undefined}
            >
              <CardHeader>
                <CardTitle className="text-lg">{tier.name}</CardTitle>
                <p className="text-sm text-muted-foreground">{tier.blurb}</p>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="text-sm font-medium text-muted-foreground">
                  Coming soon
                </div>
                <ul className="space-y-2 text-sm text-muted-foreground">
                  {tier.points.map((point) => (
                    <li key={point}>• {point}</li>
                  ))}
                </ul>
                <Link
                  href={tier.href}
                  className="inline-flex h-10 items-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground hover:opacity-90"
                >
                  {tier.cta}
                </Link>
              </CardContent>
            </Card>
          ))}
        </div>
      </main>
      <MarketingFooter />
    </div>
  );
}
