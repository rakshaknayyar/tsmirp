// A tiny router based on the part of the URL after "#", so the browser's back and forward
// buttons work and every screen has its own link:
//   #/                      home page
//   #/tourist/<tab>         tourist app (tabs: safety, report, assistant, id, activity, profile)
//   #/dashboard/<tab>       authority dashboard (tabs: operations, analytics, verify)

import { useEffect, useState } from "react";

function parse(hash: string): string[] {
  return hash.replace(/^#\/?/, "").split("/").filter(Boolean);
}

// The current route as a list of parts, e.g. "#/tourist/report" -> ["tourist", "report"].
export function useRoute(): string[] {
  const [parts, setParts] = useState(() => parse(window.location.hash));
  useEffect(() => {
    const onChange = () => {
      setParts(parse(window.location.hash));
      window.scrollTo({ top: 0 });
    };
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return parts;
}

export function link(...parts: string[]): string {
  return `#/${parts.join("/")}`;
}
