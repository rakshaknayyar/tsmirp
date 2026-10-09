// Shown under the header on every screen: this is a decision-support prototype and
// dispatch, SMS and e-mail are simulated.

import { FlaskConical } from "lucide-react";

export default function SimulationNotice() {
  return (
    <div className="sim-strip">
      <p className="sim-strip-inner">
        <FlaskConical aria-hidden="true" />
        <span>
          <strong>Prototype for decision support.</strong> Dispatch, SMS and e-mail are simulated.
          In a real emergency, call <strong>112</strong>.
        </span>
      </p>
    </div>
  );
}
