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

export type Session = { token: string; user: User };

export const STAFF_ROLES: Role[] = ["operator", "supervisor", "administrator"];
