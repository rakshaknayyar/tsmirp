// Tourist app. After logging in, the tourist moves between screens with the side menu (desktop)
// or the bottom bar (phone):
//   Safety    - SOS, location sharing with geofence alerts, map with nearby help
//   Report    - report an incident (English, Hindi or romanised Hindi)
//   Assistant - safety questions answered from a fixed list
//   My ID     - the digital tourist ID (QR code, hidden until the tourist shows it)
//   Activity  - my reports and my notifications
//   Profile   - my details and emergency contacts
// Status changes of my own incidents arrive live over /ws/tourist.

import { Bell, FilePen, IdCard, LogOut, MessagesSquare, ShieldCheck, UserRound } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { apiGet, apiRequest } from "../shared/api";
import { firstName } from "../shared/format";
import { openLiveSocket } from "../shared/liveSocket";
import LoginForm from "../shared/LoginForm";
import { link } from "../shared/router";
import { setSession, useSession } from "../shared/session";
import type {
  AppNotification,
  Category,
  EmergencyContact,
  FixResult,
  Incident,
  Position,
  Profile,
  Session,
} from "../shared/types";
import { LiveIndicator, Notice } from "../shared/ui";
import ActivityPanel from "./ActivityPanel";
import AssistantPanel from "./AssistantPanel";
import CredentialPanel from "./CredentialPanel";
import LocationPanel from "./LocationPanel";
import ProfilePanel from "./ProfilePanel";
import ReportPanel from "./ReportPanel";
import SosPanel from "./SosPanel";
import TouristMap from "./TouristMap";

const TABS = [
  { id: "safety", label: "Safety", icon: ShieldCheck, inBottomBar: true },
  { id: "report", label: "Report", icon: FilePen, inBottomBar: true },
  { id: "assistant", label: "Assistant", icon: MessagesSquare, inBottomBar: true },
  { id: "id", label: "My ID", icon: IdCard, inBottomBar: true },
  { id: "activity", label: "Activity", icon: Bell, inBottomBar: true },
  { id: "profile", label: "Profile", icon: UserRound, inBottomBar: false },
];

const SUBTITLES: Record<string, string> = {
  safety: "Your SOS button, location alerts and help nearby.",
  report: "Tell the control room what happened.",
  assistant: "Quick answers to common safety questions.",
  id: "Your digital tourist ID, for when staff ask for it.",
  activity: "Your reports and the messages sent to you.",
  profile: "Your details and the people to tell in an emergency.",
};

export default function TouristApp({ tab }: { tab?: string }) {
  const session = useSession("tourist");
  if (session === null) {
    return <LoginForm kind="tourist" onLoggedIn={(s) => setSession("tourist", s)} />;
  }
  const current = TABS.some((t) => t.id === tab) ? tab! : "safety";
  return <TouristHome session={session} tab={current} />;
}

function TouristHome({ session, tab }: { session: Session; tab: string }) {
  const { token } = session;
  const [profile, setProfile] = useState<Profile | null>(null);
  const [position, setPosition] = useState<Position | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [contacts, setContacts] = useState<EmergencyContact[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState(false);

  const showError = (err: Error) => setError(err.message);

  const loadLists = useCallback(() => {
    apiGet<Incident[]>("/incidents", token).then(setIncidents).catch(showError);
    apiGet<AppNotification[]>("/tourist/notifications", token)
      .then(setNotifications)
      .catch(showError);
  }, [token]);

  const loadContacts = useCallback(() => {
    apiGet<EmergencyContact[]>("/tourist/emergency-contacts", token)
      .then(setContacts)
      .catch(showError);
  }, [token]);

  useEffect(() => {
    apiGet<Profile>("/tourist/profile", token).then(setProfile).catch(showError);
    apiGet<Category[]>("/incident-categories", token).then(setCategories).catch(showError);
    loadLists();
    loadContacts();
  }, [token, loadLists, loadContacts]);

  // Live updates about my own incidents (e.g. "your SOS was acknowledged").
  useEffect(
    () =>
      openLiveSocket(
        "/ws/tourist",
        token,
        (event) => {
          if ("incident" in event) {
            const updated = event.incident as Incident;
            setIncidents((list) =>
              list.some((i) => i.id === updated.id)
                ? list.map((i) => (i.id === updated.id ? updated : i))
                : [updated, ...list],
            );
            apiGet<AppNotification[]>("/tourist/notifications", token)
              .then(setNotifications)
              .catch(showError);
          }
        },
        (status) => setLive(status.connected),
      ),
    [token],
  );

  async function changeConsent(consent: boolean) {
    setError(null);
    try {
      const updated = await apiRequest<Profile>("PUT", "/tourist/consent", {
        token,
        body: { location_consent: consent },
      });
      setProfile(updated);
      if (!consent) setPosition(null); // the server has deleted the stored location
    } catch (err) {
      showError(err as Error);
    }
  }

  function handleShared(newPosition: Position, result: FixResult) {
    if (result.accepted) setPosition(newPosition);
    if (result.alerts.length > 0) loadLists();
  }

  const consent = profile?.location_consent ?? false;

  let content;
  if (tab === "report") {
    content = (
      <ReportPanel
        token={token}
        categories={categories}
        consent={consent}
        position={position}
        onSent={loadLists}
      />
    );
  } else if (tab === "assistant") {
    content = <AssistantPanel token={token} />;
  } else if (tab === "id") {
    content = <CredentialPanel token={token} user={session.user} profile={profile} />;
  } else if (tab === "activity") {
    content = (
      <ActivityPanel incidents={incidents} notifications={notifications} onRefresh={loadLists} />
    );
  } else if (tab === "profile") {
    content = (
      <ProfilePanel
        token={token}
        profile={profile}
        onProfileSaved={setProfile}
        contacts={contacts}
        onContactsChanged={loadContacts}
      />
    );
  } else {
    content = (
      <>
        <SosPanel
          token={token}
          position={position}
          incidents={incidents}
          contactCount={contacts.length}
          onChanged={loadLists}
        />
        <LocationPanel
          token={token}
          consent={consent}
          onConsentChange={changeConsent}
          onShared={handleShared}
        />
        <TouristMap token={token} position={position} />
      </>
    );
  }

  return (
    <>
      <div className="app-header">
        <div>
          <h1>Hello, {firstName(session.user.full_name)}</h1>
          <p>{SUBTITLES[tab]}</p>
        </div>
        <div className="row">
          <LiveIndicator connected={live} />
          <a className="btn btn-ghost btn-sm" href={link("tourist", "profile")}>
            <UserRound aria-hidden="true" />
            Profile
          </a>
          <button className="btn btn-secondary btn-sm" onClick={() => setSession("tourist", null)}>
            <LogOut aria-hidden="true" />
            Log out
          </button>
        </div>
      </div>

      <div className="with-sidebar">
        <nav className="side-nav" aria-label="Tourist app">
          {TABS.map(({ id, label, icon: Icon }) => (
            <a key={id} href={link("tourist", id)} aria-current={tab === id ? "page" : undefined}>
              <Icon aria-hidden="true" />
              {label}
            </a>
          ))}
        </nav>
        <div className="stack-lg">
          {error && (
            <Notice tone="danger" live="alert">
              {error}
            </Notice>
          )}
          {content}
        </div>
      </div>

      <nav className="bottom-nav" aria-label="Tourist app">
        {TABS.filter((t) => t.inBottomBar).map(({ id, label, icon: Icon }) => (
          <a key={id} href={link("tourist", id)} aria-current={tab === id ? "page" : undefined}>
            <Icon aria-hidden="true" />
            {label}
          </a>
        ))}
      </nav>
    </>
  );
}
