// The tourist's details (nationality, phone, preferred language) and emergency contacts.
// Emergency contacts get a (simulated) SMS when the tourist presses SOS.

import { Save, Trash2, UserPlus, UsersRound } from "lucide-react";
import { useEffect, useId, useState } from "react";
import type { FormEvent } from "react";

import { apiRequest } from "../shared/api";
import type { EmergencyContact, Profile } from "../shared/types";
import { EmptyState, Field, Notice, Panel } from "../shared/ui";

const PHONE_PATTERN = "^\\+?[0-9 ]{7,20}$"; // same rule as the API

type Props = {
  token: string;
  profile: Profile | null;
  onProfileSaved: (profile: Profile) => void;
  contacts: EmergencyContact[];
  onContactsChanged: () => void;
};

function DetailsForm({ token, profile, onProfileSaved }: Omit<Props, "contacts" | "onContactsChanged">) {
  const [nationality, setNationality] = useState("");
  const [phone, setPhone] = useState("");
  const [language, setLanguage] = useState("en");
  const [message, setMessage] = useState<{ tone: "success" | "danger"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const id = useId();

  useEffect(() => {
    if (!profile) return;
    setNationality(profile.nationality ?? "");
    setPhone(profile.phone ?? "");
    setLanguage(profile.preferred_language);
  }, [profile]);

  async function save(event: FormEvent) {
    event.preventDefault();
    setMessage(null);
    setBusy(true);
    try {
      const saved = await apiRequest<Profile>("PUT", "/tourist/profile", {
        token,
        body: {
          nationality: nationality.trim() || null,
          phone: phone.trim() || null,
          preferred_language: language,
        },
      });
      onProfileSaved(saved);
      setMessage({ tone: "success", text: "Your details are saved." });
    } catch (err) {
      setMessage({ tone: "danger", text: (err as Error).message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel
      title="Your details"
      description="Your nationality appears on your digital tourist ID. Your phone number is never put on the ID."
    >
      <form className="stack" onSubmit={save}>
        <div className="form-grid">
          <Field id={`${id}-nationality`} label="Nationality">
            <input
              id={`${id}-nationality`}
              className="input"
              autoComplete="country-name"
              value={nationality}
              onChange={(e) => setNationality(e.target.value)}
              maxLength={60}
            />
          </Field>
          <Field id={`${id}-phone`} label="Phone number" hint="Digits and spaces, e.g. +91 98765 43210">
            <input
              id={`${id}-phone`}
              className="input"
              type="tel"
              autoComplete="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              pattern={PHONE_PATTERN}
              aria-describedby={`${id}-phone-hint`}
            />
          </Field>
          <Field id={`${id}-language`} label="Preferred language">
            <select
              id={`${id}-language`}
              className="select"
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
            >
              <option value="en">English</option>
              <option value="hi">Hindi</option>
            </select>
          </Field>
        </div>
        {message && (
          <Notice tone={message.tone} live={message.tone === "danger" ? "alert" : "status"}>
            {message.text}
          </Notice>
        )}
        <div className="row">
          <button type="submit" className="btn btn-primary" disabled={busy || !profile}>
            <Save aria-hidden="true" />
            {busy ? "Saving…" : "Save details"}
          </button>
        </div>
      </form>
    </Panel>
  );
}

function ContactsPanel({ token, contacts, onContactsChanged }: Pick<Props, "token" | "contacts" | "onContactsChanged">) {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [relation, setRelation] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const id = useId();

  async function add(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await apiRequest("POST", "/tourist/emergency-contacts", {
        token,
        body: { name: name.trim(), phone: phone.trim(), relation: relation.trim() || null },
      });
      setName("");
      setPhone("");
      setRelation("");
      onContactsChanged();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(contact: EmergencyContact) {
    if (!window.confirm(`Remove ${contact.name} from your emergency contacts?`)) return;
    setError(null);
    try {
      await apiRequest("DELETE", `/tourist/emergency-contacts/${contact.id}`, { token });
      onContactsChanged();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <Panel
      title="Emergency contacts"
      description="When you press SOS, these people get a text message. In this prototype the message is simulated and only stored, never sent."
    >
      <div className="stack">
        {contacts.length === 0 ? (
          <EmptyState icon={<UsersRound aria-hidden="true" />} title="No emergency contacts yet">
            Add a friend or family member below.
          </EmptyState>
        ) : (
          <ul className="list">
            {contacts.map((contact) => (
              <li className="list-item" key={contact.id}>
                <span className="list-item-main">
                  <span className="list-item-title">{contact.name}</span>
                  <span className="list-item-sub">
                    {contact.phone}
                    {contact.relation ? `, ${contact.relation}` : ""}
                  </span>
                </span>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => void remove(contact)}
                  aria-label={`Remove ${contact.name}`}
                >
                  <Trash2 aria-hidden="true" />
                  Remove
                </button>
              </li>
            ))}
          </ul>
        )}

        <form className="stack" onSubmit={add}>
          <h3>Add a contact</h3>
          <div className="form-grid">
            <Field id={`${id}-name`} label="Name">
              <input
                id={`${id}-name`}
                className="input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={120}
                required
              />
            </Field>
            <Field id={`${id}-phone`} label="Phone number">
              <input
                id={`${id}-phone`}
                className="input"
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                pattern={PHONE_PATTERN}
                required
              />
            </Field>
            <Field id={`${id}-relation`} label="Relation" hint="Optional, e.g. sister or friend">
              <input
                id={`${id}-relation`}
                className="input"
                value={relation}
                onChange={(e) => setRelation(e.target.value)}
                maxLength={40}
                aria-describedby={`${id}-relation-hint`}
              />
            </Field>
          </div>
          {error && (
            <Notice tone="danger" live="alert">
              {error}
            </Notice>
          )}
          <div className="row">
            <button type="submit" className="btn btn-primary" disabled={busy}>
              <UserPlus aria-hidden="true" />
              {busy ? "Adding…" : "Add contact"}
            </button>
          </div>
        </form>
      </div>
    </Panel>
  );
}

export default function ProfilePanel(props: Props) {
  return (
    <>
      <DetailsForm token={props.token} profile={props.profile} onProfileSaved={props.onProfileSaved} />
      <ContactsPanel
        token={props.token}
        contacts={props.contacts}
        onContactsChanged={props.onContactsChanged}
      />
    </>
  );
}
