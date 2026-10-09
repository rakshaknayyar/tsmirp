// Light / dark / system colour theme.
//
// The choice is remembered in localStorage (a per-browser convenience). "system" follows the
// operating system setting and changes live when that setting changes. The resolved theme is
// written to <html data-theme="light|dark">, which theme.css reads. index.html runs the same
// logic before the page draws, so there is no flash of the wrong theme on load.

import { useEffect, useState } from "react";

export type ThemePreference = "light" | "dark" | "system";

const STORAGE_KEY = "tsmirp.theme";

function readPreference(): ThemePreference {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved === "light" || saved === "dark" || saved === "system") return saved;
  } catch {
    // storage blocked: fall back to the system setting
  }
  return "system";
}

export function useTheme(): [ThemePreference, (preference: ThemePreference) => void] {
  const [preference, setPreference] = useState<ThemePreference>(readPreference);

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      const dark = preference === "dark" || (preference === "system" && media.matches);
      document.documentElement.dataset.theme = dark ? "dark" : "light";
    };
    apply();
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [preference]);

  function choose(next: ThemePreference) {
    setPreference(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // storage blocked: the choice lasts until the page is reloaded
    }
  }

  return [preference, choose];
}
