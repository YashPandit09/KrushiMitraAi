import { lazy, Suspense, useState } from "react";
import { NavLink, Route, Routes } from "react-router";
import { currentTheme, saveTheme, type Theme } from "./theme";

const Overview = lazy(() => import("./pages/Overview"));
const DistrictPage = lazy(() => import("./pages/District"));
const Methodology = lazy(() => import("./pages/Methodology"));
const About = lazy(() => import("./pages/About"));
const NotFound = lazy(() => import("./pages/NotFound"));

function Logo() {
  return (
    <svg width="26" height="26" viewBox="0 0 32 32" aria-hidden="true">
      <path
        fill="currentColor"
        d="M16 3c-5.5 4.2-8 9-8 14.2C8 23.1 11.6 27 16 27s8-3.9 8-9.8C24 12 21.5 7.2 16 3Zm0 21.5c-.6 0-1-.4-1-1V12.4c0-.6.4-1 1-1s1 .4 1 1v11.1c0 .6-.4 1-1 1Z"
      />
      <path fill="currentColor" opacity=".55" d="M5 27.5h22a1 1 0 0 1 0 2H5a1 1 0 0 1 0-2Z" />
    </svg>
  );
}

function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(() => currentTheme());
  const next: Theme = theme === "dark" ? "light" : "dark";
  return (
    <button
      type="button"
      className="theme-toggle"
      aria-label={`Switch to ${next} theme`}
      title={`Switch to ${next} theme`}
      onClick={() => {
        saveTheme(next);
        setTheme(next);
      }}
    >
      {theme === "dark" ? (
        <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="12" r="4.5" fill="currentColor" />
          <g stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
          </g>
        </svg>
      ) : (
        <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
          <path fill="currentColor" d="M20.5 14.6A8.5 8.5 0 0 1 9.4 3.5 8.5 8.5 0 1 0 20.5 14.6Z" />
        </svg>
      )}
    </button>
  );
}

export default function App() {
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="site-header">
        <div className="container">
          <NavLink to="/" className="brand" aria-label="KrushiMitra AI home">
            <Logo />
            KrushiMitra AI
          </NavLink>
          <nav className="nav" aria-label="Main">
            <NavLink to="/" end>
              Outlook
            </NavLink>
            <NavLink to="/methodology">How it works</NavLink>
            <NavLink to="/about">About</NavLink>
          </nav>
          <ThemeToggle />
        </div>
      </header>
      <main id="main" className="container">
        <Suspense fallback={<p className="state-msg">Loading…</p>}>
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/district/:slug" element={<DistrictPage />} />
            <Route path="/methodology" element={<Methodology />} />
            <Route path="/about" element={<About />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Suspense>
      </main>
      <footer className="site-footer">
        <div className="container">
          <p>
            KrushiMitra AI - open, district-level Kharif rice yield outlooks for Odisha. Forecasts are statistical
            estimates with stated uncertainty, not official statistics or agronomic advice.
          </p>
          <p>
            Data: DES and UPAg crop statistics (India Data Portal, ODC-By) · NASA POWER · NOAA IBTrACS · geoBoundaries
            (ODbL) · live weather by <a href="https://open-meteo.com/">Open-Meteo.com</a> (CC BY 4.0).
          </p>
          <p>
            Began as a Smart India Hackathon 2025 project (SIH25044). <a href="/about">Credits</a> ·{" "}
            <a href="https://github.com/YashPandit09/KrushiMitraAi">Source code</a>
          </p>
        </div>
      </footer>
    </>
  );
}
