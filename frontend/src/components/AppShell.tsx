import { useQuery } from "@tanstack/react-query";
import { BookOpen, Flame, Grid3x3, LayoutDashboard, ListOrdered, MessageSquare, Moon, Search, Sun, Info } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";

import { api, type Publication } from "@/lib/api";
import { cn } from "@/lib/format";

const NAV = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/investigations", label: "Investigations", icon: BookOpen },
  { to: "/ranking", label: "Environment ranking", icon: ListOrdered },
  { to: "/coverage", label: "Coverage and gaps", icon: Grid3x3 },
  { to: "/assistant", label: "Research assistant", icon: MessageSquare },
  { to: "/about", label: "About and method", icon: Info },
];

type Theme = "dark" | "light";

function initialTheme(): Theme {
  const stored = localStorage.getItem("theme");
  if (stored === "dark" || stored === "light") return stored;
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(initialTheme);
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);
  const toggle = () =>
    setTheme((current) => {
      const next = current === "dark" ? "light" : "dark";
      localStorage.setItem("theme", next);
      return next;
    });
  return [theme, toggle];
}

interface SearchResults {
  investigations: { psi_id: string; display_name: string; title: string }[];
  publications: Publication[];
  facilities: { id: number; name: string }[];
  fuels: { fuel: string; test_runs: number; investigations: number }[];
}

function GlobalSearch() {
  const [text, setText] = useState("");
  const [debounced, setDebounced] = useState("");
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const box = useRef<HTMLFormElement>(null);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(text.trim()), 250);
    return () => clearTimeout(timer);
  }, [text]);
  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (!box.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const { data } = useQuery({
    queryKey: ["search", debounced],
    queryFn: () => api<SearchResults>("/search/", { q: debounced }),
    enabled: debounced.length >= 2,
  });
  const go = (path: string) => {
    setOpen(false);
    setText("");
    navigate(path);
  };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (text.trim()) go(`/investigations?q=${encodeURIComponent(text.trim())}`);
  };
  const hasResults = data && (data.investigations.length || data.fuels.length || data.publications.length || data.facilities.length);

  return (
    <form ref={box} onSubmit={submit} role="search" className="relative w-full max-w-md">
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden />
      <input
        value={text}
        onChange={(event) => {
          setText(event.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(event) => event.key === "Escape" && setOpen(false)}
        placeholder="Search investigations, fuels, hardware, publications"
        aria-label="Global search"
        className="w-full rounded-lg border border-line bg-surface py-2 pl-9 pr-3 text-sm placeholder:text-muted"
      />
      {open && debounced.length >= 2 && data && (
        <div className="absolute z-30 mt-1 max-h-[70vh] w-full overflow-auto rounded-card border border-line bg-surface p-2 text-sm shadow-xl">
          {!hasResults && <p className="p-2 text-muted">No match for “{debounced}”. Try an acronym such as BASS or a fuel such as heptane.</p>}
          {data.investigations.length > 0 && <p className="px-2 pt-1 text-xs uppercase text-muted">Investigations</p>}
          {data.investigations.map((item) => (
            <button type="button" key={item.psi_id} onClick={() => go(`/investigations/${item.psi_id}`)} className="block w-full rounded-lg px-2 py-1.5 text-left hover:bg-surface-2">
              <span className="num mr-2 text-xs text-muted">{item.psi_id}</span>
              {item.display_name}
            </button>
          ))}
          {data.fuels.length > 0 && <p className="px-2 pt-2 text-xs uppercase text-muted">Fuels in test runs</p>}
          {data.fuels.map((item) => (
            <button type="button" key={item.fuel} onClick={() => go(`/investigations?fuel=${encodeURIComponent(item.fuel)}`)} className="block w-full rounded-lg px-2 py-1.5 text-left hover:bg-surface-2">
              {item.fuel} <span className="num text-xs text-muted">{item.test_runs} runs</span>
            </button>
          ))}
          {data.facilities.length > 0 && <p className="px-2 pt-2 text-xs uppercase text-muted">Hardware</p>}
          {data.facilities.map((item) => (
            <button type="button" key={item.id} onClick={() => go(`/investigations?facility=${encodeURIComponent(item.name)}`)} className="block w-full rounded-lg px-2 py-1.5 text-left hover:bg-surface-2">
              {item.name}
            </button>
          ))}
          {data.publications.length > 0 && <p className="px-2 pt-2 text-xs uppercase text-muted">Publications</p>}
          {data.publications.map((item) => (
            <button type="button" key={item.id} onClick={() => go(`/investigations/${item.psi_id}#publications`)} className="block w-full rounded-lg px-2 py-1.5 text-left hover:bg-surface-2">
              <span className="line-clamp-1">{item.title}</span>
              <span className="num text-xs text-muted">{item.psi_id}</span>
            </button>
          ))}
        </div>
      )}
    </form>
  );
}

export function AppShell() {
  const [theme, toggleTheme] = useTheme();
  return (
    <div className="flex min-h-screen">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-surface focus:p-2">
        Skip to content
      </a>
      <aside className="no-print sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-line bg-surface p-4 md:flex">
        <Link to="/" className="mb-6 flex items-center gap-2 px-2">
          <span className="grid h-8 w-8 place-items-center rounded-full bg-accent/20">
            <Flame className="h-4 w-4 text-accent" aria-hidden />
          </span>
          <span className="font-semibold leading-tight">Flame in Freefall</span>
        </Link>
        <nav aria-label="Main" className="flex flex-col gap-1">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm",
                  isActive ? "bg-accent/15 font-medium text-text" : "text-muted hover:bg-surface-2 hover:text-text",
                )
              }
            >
              <Icon className="h-4 w-4" aria-hidden />
              {label}
            </NavLink>
          ))}
        </nav>
        <p className="mt-auto px-2 text-xs text-muted">Data: NASA Physical Sciences Informatics (PSI). Independent project, not endorsed by NASA.</p>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="no-print sticky top-0 z-20 flex items-center gap-3 border-b border-line bg-bg/90 px-4 py-3 backdrop-blur md:px-8">
          <Link to="/" className="font-semibold md:hidden">Flame in Freefall</Link>
          <GlobalSearch />
          <div className="ml-auto flex items-center gap-2">
            <Link to="/assistant" className="inline-flex items-center gap-2 rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-bg hover:opacity-90">
              <MessageSquare className="h-4 w-4" aria-hidden />
              <span className="hidden sm:inline">Ask the assistant</span>
            </Link>
            <button
              type="button"
              onClick={toggleTheme}
              aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
              className="rounded-lg border border-line bg-surface p-2 text-muted hover:text-text"
            >
              {theme === "dark" ? <Sun className="h-4 w-4" aria-hidden /> : <Moon className="h-4 w-4" aria-hidden />}
            </button>
          </div>
        </header>
        <nav aria-label="Main, compact" className="no-print flex gap-1 overflow-x-auto border-b border-line px-4 py-2 md:hidden">
          {NAV.map(({ to, label, end }) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => cn("whitespace-nowrap rounded-lg px-2.5 py-1 text-sm", isActive ? "bg-accent/15 text-text" : "text-muted")}>
              {label}
            </NavLink>
          ))}
        </nav>
        <main id="main" className="mx-auto w-full max-w-content flex-1 px-4 py-6 md:px-8">
          <Outlet />
        </main>
        <footer className="border-t border-line px-4 py-4 text-xs text-muted md:px-8">
          Flame in Freefall is a research aid. It does not replace NASA flammability standards or testing. Independent project, not endorsed by NASA.
          AI-generated text is labelled and links to the PSI record it is based on. <Link to="/about" className="text-accent hover:underline">About and method</Link>
        </footer>
      </div>
    </div>
  );
}
