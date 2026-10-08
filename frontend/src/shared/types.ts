// Shapes of the data the backend sends (they mirror the Pydantic schemas in backend/app/schemas).

export type Role = "tourist" | "operator" | "supervisor" | "administrator";

export type User = {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
};

export type Tokens = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};

export type Category = {
  code: string;
  name: string;
  department: string;
};

export type IncidentStatus =
  | "NEW"
  | "ACKNOWLEDGED"
  | "ASSIGNED"
  | "EN_ROUTE"
  | "RESOLVED"
  | "CLOSED";

export type Incident = {
  id: number;
  reporter_user_id: number | null;
  category: Category | null;
  description: string;
  language: string;
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  status: IncidentStatus;
  is_sos: boolean;
  confidence: number | null;
  created_at: string;
  updated_at: string;
  location: { lat: number; lon: number; accuracy_m: number | null; recorded_at: string } | null;
};

export type RecommendedResource = {
  id: number;
  name: string;
  resource_type: "police_station" | "hospital" | "fire_station";
  source: string;
  capabilities: string[];
  availability_sim: "AVAILABLE" | "BUSY" | "OFFLINE"; // simulated
  lat: number;
  lon: number;
  distance_m: number;
  distance_kind: "straight_line";
  capability_match: boolean;
};

export type RiskLevel = "LOW" | "MODERATE" | "HIGH" | "CRITICAL";

export type ZoneBrief = { id: number; name: string; level: RiskLevel; is_synthetic: boolean };

export type AppNotification = {
  id: number;
  kind: string;
  channel: "in_app" | "sms_sandbox" | "email_sandbox";
  title: string;
  body: string;
  incident_id: number | null;
  zone_id: number | null;
  simulated: boolean;
  created_at: string;
  read_at: string | null;
};

export type FixResult = {
  accepted: boolean;
  reason: string | null;
  inside_zones: ZoneBrief[];
  nearby_zones: ZoneBrief[];
  alerts: AppNotification[];
};

export type Position = { lat: number; lon: number; accuracy_m: number; simulated: boolean };

export type Profile = {
  nationality: string | null;
  phone: string | null;
  preferred_language: string;
  location_consent: boolean;
  consent_time: string | null;
};

export type NearbyResource = Omit<RecommendedResource, "capability_match">;

export type SosResponse = {
  incident: Incident;
  created: boolean;
  contacts_notified: number; // sandbox SMS only
  nearest_help: NearbyResource[];
  advice: string;
};

export type Session = { token: string; user: User };

export const STAFF_ROLES: Role[] = ["operator", "supervisor", "administrator"];
