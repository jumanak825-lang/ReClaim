import Link from "next/link";
import { Building2, ClipboardList, Lock, PackageCheck, Search, ShieldCheck, Sparkles, UserCheck } from "lucide-react";
import { Button } from "@/components/ui/button";

// Screen 1 (docs/02 §2.4). No accuracy figures or "find anything instantly" claims.
const steps = [
  {
    icon: ClipboardList,
    title: "Report",
    body: "Describe what you lost or found, once. Add a photo if you have one.",
  },
  {
    icon: Search,
    title: "Match",
    body: "AI compares descriptions, photos, places and times across participating locations to suggest possible matches.",
  },
  {
    icon: PackageCheck,
    title: "Recover",
    body: "Prove it's yours privately, then collect it or have it delivered.",
  },
];

const trust = [
  {
    icon: Lock,
    title: "Private verification",
    body: "Identifying details stay hidden from public listings. You prove ownership privately.",
  },
  {
    icon: UserCheck,
    title: "Human-reviewed claims",
    body: "AI suggests matches, but authorised staff decide every claim. A match is never proof of ownership.",
  },
  {
    icon: ShieldCheck,
    title: "Secure recovery",
    body: "One-time pickup codes and a tracked recovery timeline for every handover.",
  },
];

export default function LandingPage() {
  return (
    <>
      <header className="border-b bg-card">
        <div className="mx-auto flex max-w-6xl items-center gap-2 px-4 py-3">
          <Link href="/" className="mr-auto text-lg font-semibold tracking-tight">
            Reclaim
          </Link>
          <Button asChild variant="ghost" size="sm">
            <Link href="/sign-in">Sign in</Link>
          </Button>
          <Button asChild size="sm">
            <Link href="/register">Create account</Link>
          </Button>
        </div>
      </header>

      <main className="flex-1">
        <section className="mx-auto max-w-3xl px-4 py-16 text-center sm:py-24">
          <p className="mb-4 inline-flex items-center gap-1.5 rounded-full bg-accent px-3 py-1 text-sm text-accent-foreground">
            <Sparkles className="size-4" aria-hidden /> AI-assisted lost and found network
          </p>
          <h1 className="text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
            Lost something? Let AI bring it back.
          </h1>
          <p className="mt-4 text-lg text-balance text-muted-foreground">
            One report. A connected network of participating locations. A safer way home for your belongings.
          </p>
          <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
            <Button asChild size="lg">
              <Link href="/report/lost">Report a lost item</Link>
            </Button>
            <Button asChild size="lg" variant="outline">
              <Link href="/report/found">Report a found item</Link>
            </Button>
          </div>
        </section>

        <section aria-labelledby="how-heading" className="border-y bg-card">
          <div className="mx-auto max-w-6xl px-4 py-14">
            <h2 id="how-heading" className="text-center text-2xl font-semibold">
              How it works
            </h2>
            <ol className="mt-8 grid gap-6 sm:grid-cols-3">
              {steps.map((s, i) => (
                <li key={s.title} className="rounded-lg border bg-background p-5">
                  <s.icon className="size-6 text-primary" aria-hidden />
                  <h3 className="mt-3 font-semibold">
                    {i + 1}. {s.title}
                  </h3>
                  <p className="mt-1 text-muted-foreground">{s.body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section aria-labelledby="orgs-heading" className="mx-auto max-w-3xl px-4 py-14 text-center">
          <Building2 className="mx-auto size-7 text-primary" aria-hidden />
          <h2 id="orgs-heading" className="mt-3 text-2xl font-semibold">
            For airports, hotels, venues and campuses
          </h2>
          <p className="mt-2 text-muted-foreground">
            Participating organisations keep their own custody workflow. Reclaim makes the items they hold
            discoverable across the network, with AI-assisted matching, claim review and recovery tracking in one place.
          </p>
        </section>

        <section aria-labelledby="trust-heading" className="border-t bg-card">
          <div className="mx-auto max-w-6xl px-4 py-14">
            <h2 id="trust-heading" className="text-center text-2xl font-semibold">
              Built for trust
            </h2>
            <ul className="mt-8 grid gap-6 sm:grid-cols-3">
              {trust.map((t) => (
                <li key={t.title} className="rounded-lg border bg-background p-5">
                  <t.icon className="size-6 text-primary" aria-hidden />
                  <h3 className="mt-3 font-semibold">{t.title}</h3>
                  <p className="mt-1 text-muted-foreground">{t.body}</p>
                </li>
              ))}
            </ul>
          </div>
        </section>
      </main>

      <footer className="border-t px-4 py-6 text-center text-sm text-muted-foreground">
        Reclaim is a hackathon demo. Payments run in PayPal Sandbox and courier tracking is simulated.
      </footer>
    </>
  );
}
