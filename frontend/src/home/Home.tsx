// Home page: what TSMIRP does, the way into both apps, what is simulated, and system status.

import { Building2, Compass, IdCard, Languages, MapPinned, Phone, Siren } from "lucide-react";
import { useEffect, useState } from "react";

import { apiGet } from "../shared/api";
import { link } from "../shared/router";
import { Badge } from "../shared/ui";
import HawaMahal from "./HawaMahal";

type Health = {
  status: string;
  api: string;
  database: { status: string; postgis_version?: string | null; error?: string };
  redis: { status: string; error?: string };
};

const FEATURES = [
  {
    icon: Siren,
    title: "SOS with a 5-second cancel window",
    text: "One press alerts the control room and your emergency contacts. Pressed it by mistake? Cancel it within five seconds.",
  },
  {
    icon: MapPinned,
    title: "Alerts near higher-risk areas",
    text: "Share your location and you are warned if you stay in a high-risk area. Levels are relative estimates, not predictions of crime.",
  },
  {
    icon: Languages,
    title: "Report in English or Hindi",
    text: "Describe what happened in your own words, in English, Hindi or romanised Hindi. A category is suggested for you.",
  },
  {
    icon: IdCard,
    title: "A digital tourist ID",
    text: "A signed, time-limited QR code that staff can check. It holds your name and nationality, never your location.",
  },
];

const SIMULATED = [
  {
    title: "Dispatch, SMS and e-mail",
    text: "Recorded and logged only. No real police, ambulance or phone is contacted.",
  },
  {
    title: "Risk zones and risk model",
    text: "Built from synthetic data for the Jaipur demo, never from arrest records.",
  },
  {
    title: "Police stations and hospitals",
    text: "Real places from OpenStreetMap. Their availability is simulated.",
  },
];

function SystemStatus() {
  const [health, setHealth] = useState<Health | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    apiGet<Health>("/health")
      .then(setHealth)
      .catch(() => setFailed(true));
  }, []);

  if (failed) return <Badge tone="danger">The API is not reachable</Badge>;
  if (!health) return <Badge>Checking system status…</Badge>;
  const up = (status: string) => status === "ok";
  return (
    <div className="status-row">
      <Badge tone={up(health.api) ? "success" : "danger"}>API {health.api}</Badge>
      <Badge tone={up(health.database.status) ? "success" : "danger"}>
        Database {health.database.status}
      </Badge>
      <Badge tone={up(health.redis.status) ? "success" : "warning"}>
        {up(health.redis.status) ? "Live events via Redis" : "Live events in-process"}
      </Badge>
    </div>
  );
}

export default function Home() {
  return (
    <>
      <section className="hero">
        <div>
          <h1>Explore Jaipur with help close at hand</h1>
          <p className="hero-hindi" lang="hi">
            सुरक्षित यात्रा, हिंदी में भी।
          </p>
          <p className="hero-lead">
            A safety companion for travellers and the people who look after them. Get alerts near
            higher-risk areas, send an SOS to the control room, and report a problem in your own
            words. Your location is shared only when you switch it on.
          </p>
          <div className="hero-actions">
            <a className="btn btn-primary" href={link("tourist")}>
              <Compass aria-hidden="true" />
              Open the tourist app
            </a>
            <a className="btn btn-secondary" href={link("dashboard")}>
              <Building2 aria-hidden="true" />
              Authority dashboard
            </a>
          </div>
          <p className="emergency-line">
            <Phone aria-hidden="true" />
            <span>
              In an emergency, call <strong>112</strong>. Tourist helpline <strong>1363</strong>.
            </span>
          </p>
        </div>
        <div className="hero-art">
          <HawaMahal />
        </div>
      </section>

      <section className="section" aria-labelledby="features-title">
        <div className="section-head">
          <h2 id="features-title">Made for a day out in the Pink City</h2>
          <p>Everything a visitor needs in one place, built to work on a phone.</p>
        </div>
        <div className="feature-list">
          {FEATURES.map(({ icon: Icon, title, text }) => (
            <div className="feature" key={title}>
              <span className="feature-icon">
                <Icon aria-hidden="true" />
              </span>
              <div>
                <h3>{title}</h3>
                <p>{text}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="section" aria-labelledby="simulated-title">
        <div className="section-head">
          <h2 id="simulated-title">What is real and what is simulated</h2>
          <p>
            TSMIRP is a prototype for the Smart India Hackathon (SIH25002). It supports decisions;
            it does not replace police or emergency services.
          </p>
        </div>
        <ul className="simulated-list">
          {SIMULATED.map((item) => (
            <li key={item.title}>
              <strong>{item.title}</strong>
              {item.text}
            </li>
          ))}
        </ul>
      </section>

      <section className="section" aria-labelledby="status-title">
        <div className="section-head">
          <h2 id="status-title">System status</h2>
        </div>
        <SystemStatus />
      </section>
    </>
  );
}
