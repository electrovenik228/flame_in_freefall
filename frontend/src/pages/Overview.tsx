import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Grid3x3, ListOrdered, MessageSquare, Play } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { Card, ExternalA, PILLARS, SectionTitle, Skeleton } from "@/components/ui";
import { api, type Pillar, type Stats } from "@/lib/api";
import { cn, dateTime } from "@/lib/format";

// Quotes are word for word from the NASA pages named in section 4.1, retrieved on 15 November 2026.
const INCIDENTS = [
  {
    name: "Apollo 1",
    when: "Jan. 27, 1967",
    what: "a fire swept through the Command Module (CM).",
    why: "Because of the pure oxygen atmosphere, the fire spread quickly, causing a rapid rise in temperature and pressure",
    after: "NASA decided that all future Apollo crews would fly aboard the more advanced Block II version of the spacecraft.",
    url: "https://sma.nasa.gov/sma-disciplines/accllp/apollo-1",
  },
  {
    name: "Apollo 13",
    when: "Third day in space",
    what: "oxygen tank number two blew up, leading to the subsequent failure of tank number one.",
    why: "the heaters were left on for an extended period and reached temperatures around 1000 degrees Fahrenheit",
    after: "engineers at NASA and North American Rockwell redesigned the oxygen tank system by adding a third tank in a different bay",
    url: "https://sma.nasa.gov/sma-disciplines/accllp/apollo-13",
  },
  {
    name: "Space station Mir",
    when: "Feb. 24, 1997",
    what: "a fire ignited in an oxygen generating system.",
    why: "They identified the most likely culprit as latex working glove material inadvertently introduced into the canister.",
    after: "The lessons learned from the incident were passed on in the design and operations of the International Space Station.",
    url: "https://www.nasa.gov/history/25-years-ago-fire-aboard-space-station-mir/",
  },
];

/** The same flame at 1 g and in free fall, with a slider between them. An illustration, not a photograph. */
function FlameComparison() {
  const [split, setSplit] = useState(50);
  return (
    <figure className="relative h-64 overflow-hidden rounded-card border border-line bg-[#070A12] md:h-full md:min-h-72">
      <svg viewBox="0 0 400 260" className="absolute inset-0 h-full w-full" aria-hidden preserveAspectRatio="xMidYMid slice">
        <defs>
          <radialGradient id="sphere" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#0B0F1A" stopOpacity="0.2" />
            <stop offset="62%" stopColor="#4DA3FF" stopOpacity="0.55" />
            <stop offset="82%" stopColor="#4DA3FF" stopOpacity="0.9" />
            <stop offset="100%" stopColor="#4DA3FF" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="tear" x1="0" y1="1" x2="0" y2="0">
            <stop offset="0%" stopColor="#4DA3FF" />
            <stop offset="22%" stopColor="#FFE9B0" />
            <stop offset="60%" stopColor="#FFB454" />
            <stop offset="100%" stopColor="#FF7A3D" stopOpacity="0.15" />
          </linearGradient>
        </defs>
        <rect x="197" y="150" width="6" height="70" rx="2" fill="#E8ECF4" opacity="0.35" />
        <circle cx="200" cy="130" r="62" fill="url(#sphere)" />
      </svg>
      <svg viewBox="0 0 400 260" className="absolute inset-0 h-full w-full" aria-hidden preserveAspectRatio="xMidYMid slice" style={{ clipPath: `inset(0 ${100 - split}% 0 0)` }}>
        <rect width="400" height="260" fill="#120C08" />
        <rect x="197" y="150" width="6" height="70" rx="2" fill="#E8ECF4" opacity="0.35" />
        <path d="M200 20 C 226 80, 238 118, 222 146 C 214 160, 186 160, 178 146 C 162 118, 174 80, 200 20 Z" fill="url(#tear)" />
      </svg>
      <div className="pointer-events-none absolute inset-y-0 w-px bg-white/70" style={{ left: `${split}%` }} />
      <figcaption className="pointer-events-none absolute inset-x-0 top-0 flex justify-between p-3 text-xs text-white/80">
        <span>On Earth, 1 g: hot gas rises, the flame is a teardrop</span>
        <span className="text-right">In free fall: no buoyancy, the flame is a sphere</span>
      </figcaption>
      <label className="absolute inset-x-3 bottom-3 flex items-center gap-2 text-xs text-white/80">
        <span className="shrink-0">Illustration</span>
        <input type="range" min={0} max={100} value={split} onChange={(event) => setSplit(Number(event.target.value))} aria-label="Slide between the flame at 1 g and in microgravity" className="w-full accent-[#4DA3FF]" />
      </label>
    </figure>
  );
}

function Stat({ value, label }: { value: number | undefined; label: string }) {
  return (
    <Card className="p-4">
      {value === undefined ? <Skeleton className="h-9 w-20" /> : <div className="num text-3xl">{value.toLocaleString("en-US")}</div>}
      <div className="mt-1 text-sm text-muted">{label}</div>
    </Card>
  );
}

export default function Overview() {
  const { data } = useQuery({ queryKey: ["stats"], queryFn: () => api<Stats>("/meta/stats/") });
  const [video, setVideo] = useState(false);
  return (
    <div className="space-y-8">
      <section className="grid gap-5 md:grid-cols-2">
        <div className="flex flex-col justify-center">
          <h1 className="text-3xl font-semibold leading-tight md:text-4xl">What NASA&rsquo;s flames in free fall tell us about fire safety</h1>
          <p className="mt-3 max-w-prose text-muted">
            A catalogue of the Combustion Science investigations in NASA&rsquo;s Physical Sciences Informatics repository: ranked for a crew
            environment, comparable by test conditions, and summarized by AI with a source for every statement.
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            <Link to="/ranking?env=lunar-habitat" className="inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2 font-medium text-bg hover:opacity-90">
              Rank for a lunar habitat <ArrowRight className="h-4 w-4" aria-hidden />
            </Link>
            <Link to="/investigations" className="inline-flex items-center gap-2 rounded-lg border border-line bg-surface px-4 py-2 font-medium hover:border-accent">Browse investigations</Link>
          </div>
        </div>
        <FlameComparison />
      </section>

      <section aria-label="Key counts" className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat value={data?.investigations} label="investigations from PSI" />
        <Stat value={data?.test_runs} label="test runs with conditions" />
        <Stat value={data?.investigations_with_test_runs} label="records with test-by-test data" />
        <Stat value={data?.publications} label="linked publications" />
      </section>

      <section>
        <SectionTitle>Three sides of fire safety</SectionTitle>
        <div className="grid gap-4 md:grid-cols-3">
          {(Object.keys(PILLARS) as Pillar[]).map((pillar) => {
            const { label, icon: Icon, text, hint } = PILLARS[pillar];
            return (
              <Link key={pillar} to={`/investigations?safety_function=${pillar}`} className="group" data-testid={`tile-${pillar}`}>
                <Card className="h-full transition-colors group-hover:border-accent/60">
                  <div className={cn("flex items-center gap-2 font-semibold", text)}>
                    <Icon className="h-5 w-5" aria-hidden />
                    <span className="text-text">{label}</span>
                  </div>
                  <p className="mt-1 text-sm text-muted">{hint}</p>
                  <p className="mt-3 text-sm">
                    <span className="num text-2xl">{data?.safety_pillars[pillar] ?? "–"}</span> investigations
                  </p>
                </Card>
              </Link>
            );
          })}
        </div>
      </section>

      <section>
        <SectionTitle>Start here</SectionTitle>
        <div className="grid gap-4 md:grid-cols-3">
          {[
            { to: "/ranking?env=lunar-habitat", icon: ListOrdered, title: "Which results apply to my cabin atmosphere?", text: "Pick a crew environment and see investigations ranked by an open rubric, with the reason for every score." },
            { to: "/coverage", icon: Grid3x3, title: "What has been tested, and what has not?", text: "A map of tested oxygen and pressure with the exploration atmospheres drawn on it, and the gaps listed." },
            { to: "/assistant", icon: MessageSquare, title: "Ask a question across studies", text: "The assistant answers from PSI records only and gives a numbered source for each statement." },
          ].map(({ to, icon: Icon, title, text }) => (
            <Link key={to} to={to} className="group">
              <Card className="h-full transition-colors group-hover:border-accent/60">
                <Icon className="h-5 w-5 text-accent" aria-hidden />
                <h3 className="mt-2 font-semibold">{title}</h3>
                <p className="mt-1 text-sm text-muted">{text}</p>
              </Card>
            </Link>
          ))}
        </div>
      </section>

      <section>
        <SectionTitle>Why it matters</SectionTitle>
        <ol className="grid gap-4 md:grid-cols-3" data-testid="timeline">
          {INCIDENTS.map((incident) => (
            <li key={incident.name}>
              <Card className="h-full border-warm/30">
                <div className="num text-xs text-warm">{incident.when}</div>
                <h3 className="font-semibold">{incident.name}</h3>
                <p className="mt-2 text-sm">&ldquo;{incident.what}&rdquo;</p>
                <p className="mt-2 text-sm text-muted">&ldquo;{incident.why}&rdquo;</p>
                <p className="mt-2 text-sm text-muted">Afterwards: &ldquo;{incident.after}&rdquo;</p>
                <ExternalA href={incident.url} className="mt-3 text-sm">Source: NASA</ExternalA>
              </Card>
            </li>
          ))}
        </ol>
      </section>

      <section className="grid gap-5 md:grid-cols-2">
        <div>
          <SectionTitle>Watch</SectionTitle>
          <div className="aspect-video overflow-hidden rounded-card border border-line bg-surface">
            {video ? (
              <iframe
                className="h-full w-full"
                src="https://www.youtube-nocookie.com/embed/W1oXykoz9zg?autoplay=1"
                title="NASA ScienceCast video on flames in microgravity"
                allow="autoplay; encrypted-media; picture-in-picture"
                allowFullScreen
              />
            ) : (
              <button type="button" onClick={() => setVideo(true)} className="flex h-full w-full flex-col items-center justify-center gap-3 text-muted hover:text-text">
                <span className="grid h-14 w-14 place-items-center rounded-full bg-accent/20"><Play className="h-6 w-6 text-accent" aria-hidden /></span>
                <span>Play the NASA ScienceCast video</span>
                <span className="text-xs">Loads from YouTube when you press play</span>
              </button>
            )}
          </div>
          <p className="mt-2 text-xs text-muted">Video: NASA ScienceCast, <ExternalA href="https://www.youtube.com/watch?v=W1oXykoz9zg">on YouTube</ExternalA>.</p>
        </div>
        <div>
          <SectionTitle>About the data</SectionTitle>
          <Card className="space-y-2 text-sm">
            <p>Every number on a chart comes from the database, which is loaded from PSI records. AI text is labelled, and each statement links to the PSI record it is based on.</p>
            <p className="text-muted">PSI holds no partial-gravity combustion data yet. Results for the Moon and Mars are bounded by microgravity and 1 g tests, not measured.</p>
            <p className="text-muted">
              {data?.source_retrieved_at ? `PSI records retrieved on ${dateTime(data.source_retrieved_at)}.` : "Loading the retrieval date…"}{" "}
              <Link to="/about" className="text-accent hover:underline">Sources, method and limitations</Link>
            </p>
          </Card>
        </div>
      </section>
    </div>
  );
}
