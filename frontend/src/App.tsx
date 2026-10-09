// App shell: the header (brand, main navigation, light/dark switch), the prototype notice, the
// current page, and the footer. The header is on every page, so you can always get back to the
// home page, the tourist app or the authority dashboard.

import { Building2, Compass, House, Monitor, Moon, Sun } from "lucide-react";
import { useEffect } from "react";
import type { MouseEvent } from "react";

import DashboardApp from "./dashboard/DashboardApp";
import Home from "./home/Home";
import { link, useRoute } from "./shared/router";
import SimulationNotice from "./shared/SimulationNotice";
import { useTheme } from "./shared/theme";
import type { ThemePreference } from "./shared/theme";
import TouristApp from "./tourist/TouristApp";

const NAV: { section: string; label: string; short?: string; icon: typeof House }[] = [
  { section: "", label: "Home", icon: House },
  { section: "tourist", label: "Tourist app", icon: Compass },
  { section: "dashboard", label: "Authority dashboard", short: "Dashboard", icon: Building2 },
];

const THEMES: { value: ThemePreference; label: string; icon: typeof Sun }[] = [
  { value: "light", label: "Light theme", icon: Sun },
  { value: "system", label: "Use system theme", icon: Monitor },
  { value: "dark", label: "Dark theme", icon: Moon },
];

function BrandMark() {
  // A jharokha arch, the window shape found all over Jaipur's palaces.
  return (
    <svg className="brand-mark" viewBox="0 0 32 32" aria-hidden="true">
      <path
        d="M6 29V14Q6 5 16 3q10 2 10 11v15"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinejoin="round"
      />
      <path
        d="M11 29V17q0-5 5-6.5q5 1.5 5 6.5v12"
        fill="currentColor"
        fillOpacity="0.18"
        stroke="currentColor"
        strokeWidth="1.6"
      />
      <path d="M3 29h26" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
    </svg>
  );
}

function ThemeSwitch() {
  const [preference, setPreference] = useTheme();
  return (
    <div className="theme-switch" role="group" aria-label="Colour theme">
      {THEMES.map(({ value, label, icon: Icon }) => (
        <button
          key={value}
          type="button"
          aria-pressed={preference === value}
          aria-label={label}
          title={label}
          onClick={() => setPreference(value)}
        >
          <Icon aria-hidden="true" />
        </button>
      ))}
    </div>
  );
}

// The router uses the "#" part of the URL, so the skip link moves focus itself.
function skipToContent(event: MouseEvent<HTMLAnchorElement>) {
  event.preventDefault();
  document.getElementById("content")?.focus();
}

export default function App() {
  const [section = "", tab] = useRoute();

  useEffect(() => {
    const page = NAV.find((item) => item.section === section)?.label ?? "Home";
    document.title = section ? `${page} | TSMIRP` : "TSMIRP | Tourist safety in Jaipur";
  }, [section]);

  let page;
  if (section === "tourist") page = <TouristApp tab={tab} />;
  else if (section === "dashboard") page = <DashboardApp tab={tab} />;
  else page = <Home />;

  return (
    <>
      <a className="skip-link" href="#content" onClick={skipToContent}>
        Skip to content
      </a>
      <header className="topbar">
        <div className="topbar-inner">
          <a className="brand" href={link()}>
            <BrandMark />
            <span>
              <span className="brand-name">TSMIRP</span>
              <span className="brand-tag">Tourist safety, Jaipur</span>
            </span>
          </a>
          <nav className="main-nav" aria-label="Main">
            {NAV.map(({ section: target, label, short, icon: Icon }) => (
              <a
                key={label}
                href={target ? link(target) : link()}
                aria-current={section === target ? "page" : undefined}
                aria-label={short ? label : undefined}
              >
                <Icon aria-hidden="true" />
                {short ? (
                  <>
                    <span className="nav-long">{label}</span>
                    <span className="nav-short" aria-hidden="true">
                      {short}
                    </span>
                  </>
                ) : (
                  label
                )}
              </a>
            ))}
          </nav>
          <ThemeSwitch />
        </div>
      </header>
      <SimulationNotice />

      <main
        id="content"
        tabIndex={-1}
        className={section === "tourist" ? "page has-bottom-nav" : "page"}
      >
        {page}
      </main>

      <footer className="site-footer">
        <div className="site-footer-inner">
          <span>
            TSMIRP, a decision-support prototype for SIH25002. Not a replacement for emergency
            services.
          </span>
          <span>
            Map data &copy;{" "}
            <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">
              OpenStreetMap
            </a>{" "}
            contributors (ODbL)
          </span>
        </div>
      </footer>
    </>
  );
}
