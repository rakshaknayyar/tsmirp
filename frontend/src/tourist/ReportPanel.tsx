// Report an incident. The description can be in English, Hindi or romanised Hindi; if no
// category is chosen, the server suggests one (and an operator checks it).

import { Send } from "lucide-react";
import { useId, useState } from "react";
import type { FormEvent } from "react";

import { apiRequest } from "../shared/api";
import { LANGUAGE_NAMES, SEVERITY_LABELS } from "../shared/format";
import { link } from "../shared/router";
import type { Category, Incident, Position } from "../shared/types";
import { Field, Notice, Panel } from "../shared/ui";

type Props = {
  token: string;
  categories: Category[];
  consent: boolean;
  position: Position | null;
  onSent: () => void;
};

const MAX_LENGTH = 2000;

export default function ReportPanel({ token, categories, consent, position, onSent }: Props) {
  const [description, setDescription] = useState("");
  const [categoryCode, setCategoryCode] = useState("");
  const [attachLocation, setAttachLocation] = useState(false);
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState<Incident | null>(null);
  const [error, setError] = useState<string | null>(null);
  const id = useId();
  const canAttach = consent && position !== null;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    const location =
      attachLocation && canAttach
        ? { lat: position!.lat, lon: position!.lon, accuracy_m: position!.accuracy_m }
        : null;
    try {
      const created = await apiRequest<Incident>("POST", "/incidents", {
        token,
        body: { description, category_code: categoryCode || null, location },
      });
      setSent(created);
      setDescription("");
      setCategoryCode("");
      setAttachLocation(false);
      onSent();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel
      title="Report an incident"
      description="Describe what happened in English, Hindi or romanised Hindi. Not in danger right now? This is the right place. If you are in danger, use SOS or call 112."
    >
      <form className="stack" onSubmit={handleSubmit}>
        <Field
          id={`${id}-description`}
          label="What happened?"
          hint={`${description.length} / ${MAX_LENGTH} characters. For example: "My phone was stolen near the market" or "Mera phone chori ho gaya".`}
        >
          <textarea
            id={`${id}-description`}
            className="textarea"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            minLength={5}
            maxLength={MAX_LENGTH}
            aria-describedby={`${id}-description-hint`}
            required
          />
        </Field>

        <Field
          id={`${id}-category`}
          label="Category"
          hint="Optional. If you are not sure, we suggest one from your description."
        >
          <select
            id={`${id}-category`}
            className="select"
            value={categoryCode}
            onChange={(e) => setCategoryCode(e.target.value)}
            aria-describedby={`${id}-category-hint`}
          >
            <option value="">Not sure, suggest one for me</option>
            {categories.map((c) => (
              <option key={c.code} value={c.code}>
                {c.name}
              </option>
            ))}
          </select>
        </Field>

        <label className="check">
          <input
            type="checkbox"
            checked={attachLocation}
            disabled={!canAttach}
            onChange={(e) => setAttachLocation(e.target.checked)}
          />
          <span>
            Attach my last shared location
            {!canAttach && (
              <span className="muted">
                {" "}
                (share your location on the <a href={link("tourist", "safety")}>Safety</a> screen
                first)
              </span>
            )}
          </span>
        </label>

        {error && (
          <Notice tone="danger" live="alert">
            {error}
          </Notice>
        )}

        <div className="row">
          <button type="submit" className="btn btn-primary" disabled={busy}>
            <Send aria-hidden="true" />
            {busy ? "Sending…" : "Send report"}
          </button>
        </div>
      </form>

      {sent && (
        <div className="mt-md">
          <Notice tone="success" live="status" title={`Report #${sent.id} sent`}>
            <p>
              Language: {LANGUAGE_NAMES[sent.language] ?? sent.language}
              {sent.language !== "en" && ", translated with a simple word list"}.{" "}
              {sent.category && sent.confidence !== null
                ? `Suggested category: ${sent.category.name} (confidence ${Math.round(sent.confidence * 100)}%). `
                : sent.category
                  ? `Category: ${sent.category.name}. `
                  : "An operator will choose the category. "}
              Severity: {SEVERITY_LABELS[sent.severity]}.
            </p>
            <p>
              An operator can see it now and may correct it. Follow it under{" "}
              <a href={link("tourist", "activity")}>Activity</a>.
            </p>
          </Notice>
        </div>
      )}
    </Panel>
  );
}
