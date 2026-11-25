import { Camera, ClipboardCheck, Cpu, Ellipsis, Images, Moon, ReceiptText, Shirt, Sparkles, Sun, TriangleAlert, UserRound } from "lucide-react";
import { useEffect, useState } from "react";
import { LOCKED_EVENT, accessKey, api, setAccessKey } from "./api";
import { Costs } from "./pages/Costs";
import { Garments } from "./pages/Garments";
import { Models } from "./pages/Models";
import { Review } from "./pages/Review";
import { Shoots } from "./pages/Shoots";
import { FittingRoom } from "./pages/FittingRoom";
import { AiModels } from "./pages/AiModels";
import { Results } from "./pages/Results";
import { ErrorNote, PageTitle, useHashRoute, usePolled } from "./ui";
import { ViewerHost } from "./Viewer";

/** The three main sections, then the studio tools. */
const NAV = [
  ["studio", "Fitting room", "Try on", Sparkles],
  ["models", "Models", "Models", Cpu],
  ["results", "Results", "Results", Images],
] as const;
const TOOLS = [
  ["people", "People", "People", UserRound],
  ["garments", "Garments", "Garments", Shirt],
  ["shoots", "Photoshoots", "Shoots", Camera],
  ["review", "Review", "Review", ClipboardCheck],
  ["costs", "Costs", "Costs", ReceiptText],
] as const;

/** On phones the tools sit behind "More"; this page lists them. */
function More() {
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <PageTitle>More</PageTitle>
          <p>Studio tools for your brand's people, garments, photoshoots, reviews and costs.</p>
        </div>
      </div>
      <nav className="more-list" aria-label="Studio tools">
        {TOOLS.map(([id, label, , Icon]) => (
          <a key={id} href={`#/${id}`}>
            <Icon size={20} aria-hidden /> {label}
          </a>
        ))}
      </nav>
    </div>
  );
}

/** Shown when the server asks for its access key (a FitShot reached over the internet). */
function AccessGate() {
  const [key, setKey] = useState("");
  const tried = !!accessKey();
  return (
    <div className="gate">
      <form
        className="panel gate-card"
        onSubmit={(event) => {
          event.preventDefault();
          setAccessKey(key.trim());
          window.location.reload();
        }}
      >
        <span className="masthead gate-mark">FitShot</span>
        <h1 className="title">This FitShot is private</h1>
        <p className="muted">Enter the access key set in this FitShot's .env file (FITSHOT_ACCESS_KEY).</p>
        {tried && <p className="note error" role="alert">That key didn't work. Check it and try again.</p>}
        <label className="field">
          <span className="field-label">Access key</span>
          <input type="password" autoComplete="current-password" value={key} onChange={(e) => setKey(e.target.value)} required />
        </label>
        <button className="btn primary">Unlock</button>
      </form>
    </div>
  );
}

function readTheme(): "light" | "dark" {
  try {
    const saved = localStorage.getItem("fitshot-theme");
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    /* Storage can be unavailable in private windows. */
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function App() {
  const route = useHashRoute();
  const page = route[0] ?? "studio";
  const [theme, setTheme] = useState(readTheme);
  const [locked, setLocked] = useState(false);
  useEffect(() => {
    const lock = () => setLocked(true);
    window.addEventListener(LOCKED_EVENT, lock);
    return () => window.removeEventListener(LOCKED_EVENT, lock);
  }, []);
  const status = usePolled(api.status, [], 10000);
  const review = usePolled(api.review, [], 4000);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", "#2b35f5");
    try {
      localStorage.setItem("fitshot-theme", theme);
    } catch {
      /* The theme still applies for this visit. */
    }
  }, [theme]);

  const info = status.data;
  const anyReady = info ? Object.values(info.generators).some((g) => g.ready) : true;
  const reviewCount = review.data?.length ?? 0;
  const nextTheme = theme === "dark" ? "light" : "dark";

  if (locked) return <AccessGate />;

  return (
    <div className="shell">
      <a className="skip" href="#main">
        Skip to content
      </a>
      <header className="rail">
        <a className="brand" href="#/studio" aria-label="FitShot, fitting room">
          <span className="masthead">FitShot</span>
        </a>
        <nav className="index" aria-label="Main">
          {[...NAV, ...TOOLS].map(([id, label, short, Icon], index) => (
            <a
              key={id}
              href={`#/${id}`}
              aria-current={page === id ? "page" : undefined}
              className={index >= NAV.length ? `tool${id === "review" ? " keep" : ""}${index === NAV.length ? " first-tool" : ""}` : undefined}
            >
              <Icon size={19} aria-hidden strokeWidth={1.8} />
              <span className="nav-label">
                <span className="nav-full">{label}</span>
                <span className="nav-short">{short}</span>
              </span>
              {id === "review" && reviewCount > 0 && (
                <span className="count" aria-label={`${reviewCount} waiting`}>
                  {reviewCount}
                </span>
              )}
            </a>
          ))}
          <a href="#/more" className="more-link" aria-current={page === "more" ? "page" : undefined}>
            <Ellipsis size={19} aria-hidden strokeWidth={1.8} />
            <span className="nav-label">
              <span className="nav-full">More</span>
              <span className="nav-short">More</span>
            </span>
          </a>
        </nav>
        <p className="rail-note">Every photo is checked before it ships.</p>
        <button className="theme" onClick={() => setTheme(nextTheme)} aria-label={`Switch to ${nextTheme} theme`}>
          {theme === "dark" ? <Sun size={18} aria-hidden /> : <Moon size={18} aria-hidden />}
          <span className="theme-label">{theme === "dark" ? "Light pages" : "Dark pages"}</span>
        </button>
      </header>

      <div className="desk">
        {info && (!anyReady || !info.judge_ready) && (
          <p className="setup-banner" role="status">
            <TriangleAlert size={16} aria-hidden />
            <span>
              {!anyReady
                ? "No AI model is ready. Open Models to add one or see why it is unavailable."
                : "Vision checks need a Gemini key. Until then, every photo waits for your review."}
            </span>
          </p>
        )}

        <main id="main" tabIndex={-1}>
          {status.error && !info ? (
            <div className="page">
              <ErrorNote message={status.error} />
            </div>
          ) : !info ? (
            <div className="page" aria-busy="true" />
          ) : page === "models" ? (
            <AiModels />
          ) : page === "people" ? (
            <Models status={info} modelId={route[1]} />
          ) : page === "results" ? (
            <Results status={info} />
          ) : page === "more" ? (
            <More />
          ) : page === "garments" ? (
            <Garments key={route[1] ?? "list"} status={info} fromStudio={route[1] === "new"} />
          ) : page === "review" ? (
            <Review status={info} onChange={review.refresh} />
          ) : page === "costs" ? (
            <Costs />
          ) : page === "studio" ? (
            <FittingRoom status={info} onChange={review.refresh} />
          ) : (
            <Shoots status={info} jobId={route[1]} onChange={review.refresh} />
          )}
        </main>
        <ViewerHost />
      </div>
    </div>
  );
}
