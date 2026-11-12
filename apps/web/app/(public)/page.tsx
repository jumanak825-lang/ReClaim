import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";
import {
  ArrowRight,
  BedDouble,
  Building2,
  Check,
  ChevronDown,
  ClipboardList,
  Eye,
  EyeOff,
  GraduationCap,
  KeyRound,
  Lock,
  PackageCheck,
  Plane,
  Search,
  ShieldAlert,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  Ticket,
  UserCheck,
  type LucideIcon,
} from "lucide-react";
import { BrandLogo } from "@/components/brand-logo";
import { SimBadge } from "@/components/page";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import s from "./landing.module.css";

// Screen 1 (docs/02 §2.4). No accuracy figures or "find anything instantly" claims.
// Every product example on this page is labelled as an example or illustration.

const stagger = (i: number) => ({ "--i": i }) as CSSProperties;

const places: { icon: LucideIcon; label: string }[] = [
  { icon: Plane, label: "Airports" },
  { icon: BedDouble, label: "Hotels" },
  { icon: Ticket, label: "Venues" },
  { icon: ShoppingBag, label: "Malls" },
  { icon: GraduationCap, label: "Campuses" },
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

const faqs = [
  {
    q: "Does AI decide who gets the item back?",
    a: "No. AI suggests possible matches and helps reviewers compare details. A person at the organisation holding the item approves or rejects every claim, and the reason is recorded.",
  },
  {
    q: "Who can see my private details?",
    a: "Only you and authorised reviewers at the organisation holding a possible match. Serial numbers, distinctive marks and what was inside never appear in listings or to finders.",
  },
  {
    q: "What does it cost to get my item back?",
    a: "Collecting it is free. If you choose delivery, you see the exact price before paying with PayPal. The fee covers delivery only; it isn't a reward for the finder. This demo uses PayPal Sandbox, so no real money moves.",
  },
  {
    q: "I found something. What should I do?",
    a: "Report it, or hand it to a participating organisation's lost property desk and tell us which one. Don't post where it's stored, access codes or anything that identifies the owner.",
  },
];

export default function LandingPage() {
  return (
    <>
      <header className="sticky top-0 z-30 border-b bg-card/90 backdrop-blur">
        <div className="mx-auto flex h-[72px] max-w-6xl items-center gap-2 px-4">
          <div className="mr-auto">
            <BrandLogo className="h-8 md:h-9" priority />
          </div>
          <nav aria-label="Sections" className="mr-4 hidden items-center gap-1 text-sm font-medium lg:flex">
            {[
              ["#how", "How it works"],
              ["#privacy", "Privacy"],
              ["#organisations", "For organisations"],
              ["#faq", "Questions"],
            ].map(([href, label]) => (
              <a key={href} href={href} className="rounded-md px-3 py-2 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground">
                {label}
              </a>
            ))}
          </nav>
          <Button asChild variant="ghost" className="hidden sm:inline-flex">
            <Link href="/sign-in">Sign in</Link>
          </Button>
          <Button asChild>
            <Link href="/register">Create account</Link>
          </Button>
        </div>
      </header>

      <main id="main" className="flex-1">
        {/* Hero */}
        <section className="relative overflow-hidden bg-ink text-ink-foreground">
          <div className={cn("pointer-events-none absolute inset-0", s.dots)} aria-hidden />
          <div className={cn("pointer-events-none absolute inset-0", s.glow)} aria-hidden />
          <div className="relative mx-auto grid max-w-6xl gap-12 px-4 pt-14 pb-20 md:pt-20 md:pb-28 lg:grid-cols-[1.05fr_1fr] lg:items-center">
            <div className="grid gap-6">
              <p className={cn("text-sm font-semibold tracking-wide text-brand-bright uppercase", s.rise)} style={stagger(0)}>
                Lost and found network
              </p>
              <h1
                className={cn("text-[2.6rem] leading-[1.04] font-bold tracking-tight sm:text-5xl lg:text-display", s.rise)}
                style={stagger(1)}
              >
                Lost something? Let AI bring it back.
              </h1>
              <p className={cn("max-w-xl text-lg text-ink-muted", s.rise)} style={stagger(2)}>
                One report. A connected network of participating locations. A safer way home for your belongings.
              </p>
              <ul className={cn("grid gap-2.5", s.rise)} style={stagger(3)}>
                {[
                  "One report, checked across participating locations",
                  "Ownership verified privately, decided by people",
                  "Collect it, or have it delivered",
                ].map((t) => (
                  <li key={t} className="flex items-start gap-2.5">
                    <Check className="mt-1 size-4 shrink-0 text-brand-bright" aria-hidden />
                    {t}
                  </li>
                ))}
              </ul>
              <div className={cn("flex flex-col gap-3 pt-2 sm:flex-row", s.rise)} style={stagger(4)}>
                <Button asChild size="lg" variant="cta">
                  <Link href="/report/lost">
                    Report a lost item <ArrowRight aria-hidden />
                  </Link>
                </Button>
                <Button
                  asChild
                  size="lg"
                  variant="outline"
                  className="border-ink-muted/40 bg-transparent text-ink-foreground hover:border-ink-foreground"
                >
                  <Link href="/report/found">Report a found item</Link>
                </Button>
              </div>
            </div>
            <div className={s.rise} style={stagger(3)}>
              <NetworkIllustration />
            </div>
          </div>
        </section>

        {/* Where it works */}
        <section aria-label="Where Reclaim works" className="border-b bg-card">
          <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-6 md:flex-row md:items-center md:gap-8">
            <p className="shrink-0 text-sm font-semibold text-muted-foreground">Built for the places things go missing</p>
            <ul className="flex flex-wrap gap-2">
              {places.map((p) => (
                <li key={p.label} className="inline-flex items-center gap-2 rounded-full border bg-background px-3.5 py-1.5 text-sm font-medium">
                  <p.icon className="size-4 text-brand" aria-hidden />
                  {p.label}
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* How it works */}
        <section id="how" aria-labelledby="how-heading" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-20 md:py-28">
          <SectionIntro
            eyebrow="How it works"
            id="how-heading"
            title="Report, match, recover."
            body="You describe it once. Reclaim does the searching across every participating location, and a person checks ownership before anything changes hands."
          />
          <ol className="mt-12 grid gap-6 lg:grid-cols-3">
            <Step n={1} icon={ClipboardList} title="Report" body="Describe what you lost or found, once. Add a photo if you have one.">
              <ReportExample />
            </Step>
            <Step n={2} icon={Search} title="Match" body="AI compares descriptions, photos, places and times across participating locations to suggest possible matches.">
              <MatchExample />
            </Step>
            <Step n={3} icon={PackageCheck} title="Recover" body="Prove it's yours privately, then collect it or have it delivered.">
              <RecoverExample />
            </Step>
          </ol>
        </section>

        {/* Privacy */}
        <section id="privacy" aria-labelledby="privacy-heading" className="scroll-mt-20 border-y bg-card">
          <div className="mx-auto grid max-w-6xl gap-10 px-4 py-20 md:py-28 lg:grid-cols-[0.9fr_1.1fr] lg:items-center">
            <SectionIntro
              eyebrow="Privacy by default"
              id="privacy-heading"
              title="What others see, and what stays private."
              body="Every report is split in two. Possible matches see enough to recognise the item. The details that prove it's yours stay hidden, so nobody can claim your item by copying your listing."
            />
            <div className={cn("grid gap-4 sm:grid-cols-2", s.reveal)}>
              <div className="grid content-start gap-3 surface p-5">
                <p className="flex items-center gap-2 font-semibold">
                  <Eye className="size-4 text-brand" aria-hidden /> Shown to possible matches
                </p>
                <ul className="grid gap-2 text-sm">
                  {["Category and description", "Main colour", "Approximate place", "Time window", "Photos you mark as safe"].map((t) => (
                    <li key={t} className="flex gap-2">
                      <Check className="mt-0.5 size-4 shrink-0 text-brand" aria-hidden /> {t}
                    </li>
                  ))}
                </ul>
              </div>
              <div className="grid content-start gap-3 surface-private p-5">
                <p className="flex items-center gap-2 font-semibold">
                  <EyeOff className="size-4" aria-hidden /> Only you and authorised reviewers
                </p>
                <ul className="grid gap-2 text-sm">
                  {["Serial numbers", "Distinctive marks", "What was inside", "Where a found item is stored", "Your contact details"].map((t) => (
                    <li key={t} className="flex gap-2">
                      <Lock className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden /> {t}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </section>

        {/* Organisations */}
        <section id="organisations" aria-labelledby="orgs-heading" className="mx-auto max-w-6xl scroll-mt-20 px-4 py-20 md:py-28">
          <div className={cn("grid gap-10 rounded-3xl bg-ink px-6 py-10 text-ink-foreground md:rounded-4xl md:px-12 md:py-14 lg:grid-cols-2 lg:items-center", s.reveal)}>
            <div className="grid gap-5">
              <Building2 className="size-7 text-brand-bright" aria-hidden />
              <h2 id="orgs-heading" className="text-3xl font-bold tracking-tight md:text-4xl">
                For airports, hotels, venues and campuses
              </h2>
              <p className="text-ink-muted">
                Participating organisations keep their own custody workflow. Reclaim makes the items they hold
                discoverable across the network, with AI-assisted matching, claim review and recovery tracking in one place.
              </p>
              <ul className="grid gap-2.5">
                {[
                  "Log found items once and see possible owners",
                  "Review claims with private evidence and an audit trail",
                  "Hand over with one-time codes, or ship with tracked delivery",
                  "Send events to your own tools through Zapier",
                ].map((t) => (
                  <li key={t} className="flex items-start gap-2.5">
                    <Check className="mt-1 size-4 shrink-0 text-brand-bright" aria-hidden />
                    {t}
                  </li>
                ))}
              </ul>
            </div>
            <OperationsExample />
          </div>
        </section>

        {/* Trust */}
        <section aria-labelledby="trust-heading" className="mx-auto max-w-6xl px-4 pb-20 md:pb-28">
          <SectionIntro eyebrow="Built for trust" id="trust-heading" title="Technology suggests. People decide." />
          <ul className="mt-12 grid gap-8 md:grid-cols-3">
            {trust.map((t) => (
              <li key={t.title} className={cn("grid content-start gap-3 border-t-2 border-foreground pt-5", s.reveal)}>
                <t.icon className="size-6 text-brand" aria-hidden />
                <h3 className="text-xl font-bold">{t.title}</h3>
                <p className="text-muted-foreground">{t.body}</p>
              </li>
            ))}
          </ul>
        </section>

        {/* FAQ */}
        <section id="faq" aria-labelledby="faq-heading" className="scroll-mt-20 border-t bg-card">
          <div className="mx-auto grid max-w-6xl gap-10 px-4 py-20 md:py-28 lg:grid-cols-[0.8fr_1.2fr]">
            <SectionIntro eyebrow="Questions" id="faq-heading" title="What people ask first." />
            <div className="divide-y border-y">
              {faqs.map((f) => (
                <details key={f.q} className="group py-1">
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-4 rounded-md py-4 text-lg font-semibold [&::-webkit-details-marker]:hidden">
                    {f.q}
                    <ChevronDown className="size-5 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" aria-hidden />
                  </summary>
                  <p className="max-w-2xl pb-5 text-muted-foreground">{f.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* Closing call to action */}
        <section aria-labelledby="cta-heading" className="mx-auto max-w-6xl px-4 py-20 md:py-24">
          <div className={cn("grid gap-6 rounded-3xl bg-accent px-6 py-12 text-center md:rounded-4xl md:px-12 md:py-16", s.reveal)}>
            <h2 id="cta-heading" className="text-3xl font-bold tracking-tight md:text-5xl">
              The sooner you report, the sooner we can look.
            </h2>
            <p className="mx-auto max-w-xl text-accent-foreground">
              It takes a few minutes. You can save a draft and come back to it.
            </p>
            <div className="flex flex-col justify-center gap-3 sm:flex-row">
              <Button asChild size="lg" variant="cta">
                <Link href="/report/lost">Start a lost item report</Link>
              </Button>
              <Button asChild size="lg" variant="outline">
                <Link href="/report/found">I found something</Link>
              </Button>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t bg-card px-4 py-12">
        <div className="mx-auto grid max-w-6xl gap-6 md:grid-cols-[1fr_auto] md:items-end">
          <div className="grid gap-3">
            <BrandLogo className="h-8" />
            <p className="max-w-md text-sm text-muted-foreground">
              Reclaim is a hackathon demo. Payments run in PayPal Sandbox and courier tracking is simulated.
            </p>
          </div>
          <nav aria-label="Account" className="flex gap-5 text-sm text-muted-foreground">
            <Link href="/sign-in" className="hover:text-foreground">Sign in</Link>
            <Link href="/register" className="hover:text-foreground">Create account</Link>
          </nav>
        </div>
      </footer>
    </>
  );
}

function SectionIntro({ eyebrow, id, title, body }: { eyebrow: string; id: string; title: string; body?: string }) {
  return (
    <div className={cn("grid max-w-2xl gap-3", s.reveal)}>
      <p className="text-sm font-semibold tracking-wide text-brand uppercase">{eyebrow}</p>
      <h2 id={id} className="text-3xl font-bold tracking-tight md:text-[2.75rem] md:leading-[1.1]">
        {title}
      </h2>
      {body && <p className="text-lg text-muted-foreground">{body}</p>}
    </div>
  );
}

function Step({ n, icon: Icon, title, body, children }: { n: number; icon: LucideIcon; title: string; body: string; children: ReactNode }) {
  return (
    <li className={cn("grid content-start gap-5", s.reveal)}>
      <div className={cn("grid gap-4 surface p-5", s.lift)}>{children}</div>
      <div className="grid gap-2">
        <h3 className="flex items-center gap-3 text-xl font-bold">
          <span className="flex size-8 items-center justify-center rounded-full bg-ink text-sm text-ink-foreground tabular-nums">{n}</span>
          {title}
          <Icon className="size-5 text-brand" aria-hidden />
        </h3>
        <p className="text-muted-foreground">{body}</p>
      </div>
    </li>
  );
}

function ExampleLabel({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">{children}</span>
      <SimBadge>Example</SimBadge>
    </div>
  );
}

function ReportExample() {
  const rows = [
    ["What is it?", "Silver laptop"],
    ["Where?", "Terminal 1, airport"],
    ["When?", "Yesterday, 18:00 – 20:00"],
  ];
  return (
    <>
      <ExampleLabel>Lost report</ExampleLabel>
      <dl className="grid gap-2 text-sm">
        {rows.map(([k, v]) => (
          <div key={k} className="grid gap-0.5 rounded-lg border bg-background px-3 py-2">
            <dt className="text-xs text-muted-foreground">{k}</dt>
            <dd className="font-medium">{v}</dd>
          </div>
        ))}
      </dl>
      <p className="flex items-center gap-2 rounded-lg border border-dashed border-input/70 bg-muted/60 px-3 py-2 text-sm">
        <EyeOff className="size-4 text-muted-foreground" aria-hidden />
        Serial number
        <span className="ml-auto text-xs font-semibold text-muted-foreground">Private</span>
      </p>
    </>
  );
}

function MatchExample() {
  return (
    <>
      <ExampleLabel>Possible match</ExampleLabel>
      <div className="grid gap-2 text-sm">
        <div className="flex items-center justify-between rounded-lg bg-muted px-3 py-2">
          <span className="text-muted-foreground">Your report</span>
          <span className="font-semibold">Silver laptop</span>
        </div>
        <div className="flex items-center justify-between rounded-lg bg-muted px-3 py-2">
          <span className="text-muted-foreground">Found item</span>
          <span className="font-semibold">Laptop, airport desk</span>
        </div>
      </div>
      <div className="grid gap-2">
        <p className="flex items-baseline justify-between text-sm">
          <span className="inline-flex items-center gap-1.5 font-medium">
            <Sparkles className="size-4 text-brand" aria-hidden /> AI relevance
          </span>
          <span className="text-2xl font-bold tabular-nums">87</span>
        </p>
        <div className="h-2 overflow-hidden rounded-full bg-secondary" aria-hidden>
          <div className={cn("h-full w-[87%] rounded-full bg-brand", s.fill)} />
        </div>
        <p className="text-sm text-muted-foreground">Same colour, place and time window</p>
      </div>
      <p className="flex items-start gap-1.5 border-t pt-3 text-sm font-medium">
        <ShieldAlert className="mt-0.5 size-4 shrink-0 text-brand" aria-hidden />
        Not proof of ownership. A person decides.
      </p>
    </>
  );
}

function RecoverExample() {
  const stages: [string, "done" | "current" | "upcoming"][] = [
    ["Claim approved", "done"],
    ["Ready for pickup", "current"],
    ["Handed over", "upcoming"],
  ];
  return (
    <>
      <ExampleLabel>Collection</ExampleLabel>
      <div className="grid justify-items-start gap-1 rounded-lg bg-ink px-4 py-3 text-ink-foreground">
        <span className="flex items-center gap-1.5 text-xs text-ink-muted">
          <KeyRound className="size-3.5" aria-hidden /> One-time pickup code
        </span>
        <span className="text-2xl font-bold tracking-[0.2em] tabular-nums">7K4 Q2M</span>
        <span className="text-xs text-ink-muted">Show it at the desk with photo ID</span>
      </div>
      <ol className="grid gap-2 text-sm">
        {stages.map(([label, state]) => (
          <li key={label} className="flex items-center gap-2.5">
            <span
              className={cn(
                "flex size-5 items-center justify-center rounded-full border-2",
                state === "done" && "border-brand bg-brand text-brand-foreground",
                state === "current" && "border-foreground",
                state === "upcoming" && "border-border",
              )}
              aria-hidden
            >
              {state === "done" && <Check className="size-3" />}
              {state === "current" && <span className="size-1.5 rounded-full bg-foreground" />}
            </span>
            <span className={cn(state === "current" && "font-semibold", state === "upcoming" && "text-muted-foreground")}>{label}</span>
          </li>
        ))}
      </ol>
    </>
  );
}

function OperationsExample() {
  const rows = [
    { id: "RC-3C237C", item: "Backpack", note: "Claim pending review", high: true },
    { id: "RC-5AA55A", item: "Laptop", note: "Possible match", high: false },
    { id: "RC-5AD041", item: "Laptop", note: "Ready for pickup", high: false },
  ];
  return (
    <div className="grid gap-3 rounded-2xl bg-card p-4 text-card-foreground md:p-5">
      <ExampleLabel>Operations</ExampleLabel>
      <ul className="divide-y rounded-xl border">
        {rows.map((r) => (
          <li key={r.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-3 text-sm">
            <span className="font-semibold tabular-nums">{r.id}</span>
            <span>{r.item}</span>
            <span className="ml-auto text-muted-foreground">{r.note}</span>
            {r.high && (
              <span className="rounded-full bg-warning px-2 py-0.5 text-xs font-semibold text-warning-foreground">High priority</span>
            )}
          </li>
        ))}
      </ul>
      <div className="grid grid-cols-3 gap-2 text-center">
        {[
          ["3", "Active cases"],
          ["1", "Pending claims"],
          ["1", "Recoveries"],
        ].map(([v, l]) => (
          <div key={l} className="rounded-lg bg-muted px-2 py-3">
            <p className="text-xl font-bold tabular-nums">{v}</p>
            <p className="text-xs text-muted-foreground">{l}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Participating location types linked through Reclaim. Decorative; the copy carries the meaning. */
function NetworkIllustration() {
  const hub = { x: 262, y: 205 };
  const nodes: { x: number; y: number; icon: LucideIcon; label: string; begin: string }[] = [
    { x: 95, y: 70, icon: Plane, label: "Airport", begin: "-0.4s" },
    { x: 425, y: 62, icon: BedDouble, label: "Hotel", begin: "-1.5s" },
    { x: 482, y: 238, icon: ShoppingBag, label: "Mall", begin: "-2.3s" },
    { x: 400, y: 380, icon: GraduationCap, label: "Campus", begin: "-0.9s" },
    { x: 48, y: 222, icon: Ticket, label: "Venue", begin: "-1.9s" },
  ];
  return (
    <figure className="relative mx-auto w-full max-w-[540px]">
      <svg viewBox="0 0 520 440" className="h-auto w-full" role="img" aria-label="Illustration: participating locations connected through Reclaim">
        {nodes.map((n) => (
          <line
            key={`l-${n.label}`}
            x1={n.x}
            y1={n.y}
            x2={hub.x}
            y2={hub.y}
            className={cn("stroke-ink-muted/35", s.link)}
            strokeWidth={1.5}
          />
        ))}
        {nodes.map((n) => (
          <circle key={`p-${n.label}`} r={4} className={cn("fill-brand-bright", s.pulse)}>
            <animateMotion dur="2.8s" begin={n.begin} repeatCount="indefinite" path={`M${n.x} ${n.y} L${hub.x} ${hub.y}`} />
            <animate attributeName="opacity" values="0;1;1;0" dur="2.8s" begin={n.begin} repeatCount="indefinite" />
          </circle>
        ))}
        <circle cx={hub.x} cy={hub.y} r={48} className={cn("fill-brand/40", s.ring)} />
        <circle cx={hub.x} cy={hub.y} r={48} className="fill-card stroke-brand" strokeWidth={3} />
        <image href="/brand/reclaim-mark.png" x={hub.x - 30} y={hub.y - 30} width={60} height={60} />
        {nodes.map((n) => (
          <g key={`n-${n.label}`}>
            <circle cx={n.x} cy={n.y} r={30} className="fill-ink stroke-ink-muted/40" strokeWidth={1.5} />
            <n.icon x={n.x - 11} y={n.y - 11} width={22} height={22} className="text-ink-foreground" strokeWidth={1.75} />
            <text x={n.x} y={n.y + 50} textAnchor="middle" className="fill-ink-muted text-[13px] font-medium">
              {n.label}
            </text>
          </g>
        ))}
      </svg>
      <figcaption className="sr-only">Illustration only. Participating locations vary.</figcaption>

      {/* A match surfacing from the network. */}
      <div
        className={cn(
          "relative mt-2 grid w-full gap-2 rounded-2xl bg-card p-4 text-sm text-card-foreground shadow-overlay sm:absolute sm:bottom-2 sm:left-0 sm:mt-0 sm:w-[min(300px,85%)]",
          s.toast,
        )}
        aria-hidden
      >
        <p className="flex items-center justify-between gap-2">
          <span className="inline-flex items-center gap-1.5 font-semibold">
            <Sparkles className="size-4 text-brand" /> Possible match
          </span>
          <span className="text-xs font-semibold text-muted-foreground">Example</span>
        </p>
        <p className="text-muted-foreground">Silver laptop, Terminal 1, matched with an item at the airport desk</p>
        <p className="flex items-center gap-1.5 text-xs font-medium">
          <ShieldAlert className="size-3.5 text-brand" /> A person checks ownership before release
        </p>
      </div>
    </figure>
  );
}
