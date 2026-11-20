// App shell: the header (brand, light/dark switch, log-in button), the prototype notice, the
// current page, and the footer.
//
// There is no menu of pages in the header. Everyone starts on the home page and uses the one
// "Log in" page, where a switch chooses Tourist or Authority. The TSMIRP logo always leads back
// to the home page. While someone is logged in, the header shows a button back to their app.

import { Building2, Compass, LogIn, Monitor, Moon, Sun } from "lucide-react";
import { useEffect } from "react";
import type { MouseEvent } from "react";

import DashboardApp from "./dashboard/DashboardApp";
import Home from "./home/Home";
import LoginForm from "./shared/LoginForm";
import { link, useRoute } from "./shared/router";
import { useSession } from "./shared/session";
import SimulationNotice from "./shared/SimulationNotice";
import { useTheme } from "./shared/theme";
import type { ThemePreference } from "./shared/theme";
import TouristApp from "./tourist/TouristApp";

const PAGE_TITLES: Record<string, string> = {
  login: "Log in",
  tourist: "Tourist app",
  dashboard: "Authority dashboard",
};

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

// The button on the right of the header: "Log in" for visitors, or a way back to your own app
// when you are already logged in (hidden while you are inside that app).
function AccountButtons({ section }: { section: string }) {
  const tourist = useSession("tourist");
  const staff = useSession("staff");

  if (!tourist && !staff) {
    // The log-in page, the tourist app and the dashboard all show the log-in form already.
    if (section !== "") return null;
    return (
      <a className="btn btn-primary btn-sm" href={link("login")}>
        <LogIn aria-hidden="true" />
        Log in
      </a>
    );
  }
  return (
    <>
      {tourist && section !== "tourist" && (
        <a className="btn btn-secondary btn-sm" href={link("tourist")}>
          <Compass aria-hidden="true" />
          My tourist app
        </a>
      )}
      {staff && section !== "dashboard" && (
        <a className="btn btn-secondary btn-sm" href={link("dashboard")}>
          <Building2 aria-hidden="true" />
          Control room
        </a>
      )}
    </>
  );
}

// The router uses the "#" part of the URL, so the skip link moves focus itself.
function skipToContent(event: MouseEvent<HTMLAnchorElement>) {
  event.preventDefault();
  document.getElementById("content")?.focus();
}

export default function App() {
  const [section = "", tab] = useRoute();
  const touristLoggedIn = useSession("tourist") !== null;

  useEffect(() => {
    const page = PAGE_TITLES[section];
    document.title = page ? `${page} | TSMIRP` : "TSMIRP | Tourist safety in Jaipur";
  }, [section]);

  let page;
  if (section === "tourist") page = <TouristApp tab={tab} />;
  else if (section === "dashboard") page = <DashboardApp tab={tab} />;
  else if (section === "login")
    // #/login, #/login/staff (Authority already selected), #/login/new (create an account)
    page = (
      <LoginForm
        key={tab ?? ""}
        initialKind={tab === "staff" ? "staff" : "tourist"}
        initialRegistering={tab === "new"}
      />
    );
  else page = <Home />;

  return (
    <>
      <a className="skip-link" href="#content" onClick={skipToContent}>
        Skip to content
      </a>
      <header className="topbar">
        <div className="topbar-inner">
          <a className="brand" href={link()} aria-label="TSMIRP home page">
            <BrandMark />
            <span>
              <span className="brand-name">TSMIRP</span>
              <span className="brand-tag">Tourist safety, Jaipur</span>
            </span>
          </a>
          <div className="topbar-actions">
            <AccountButtons section={section} />
            <ThemeSwitch />
          </div>
        </div>
      </header>
      <SimulationNotice />

      <main
        id="content"
        tabIndex={-1}
        className={section === "tourist" && touristLoggedIn ? "page has-bottom-nav" : "page"}
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
