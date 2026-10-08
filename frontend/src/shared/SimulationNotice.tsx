// Shown on every screen: this is a decision-support prototype, dispatch is simulated.

export default function SimulationNotice() {
  return (
    <p
      style={{
        background: "#fff4d6",
        color: "#5c4400",
        border: "1px solid #e6c768",
        padding: "8px 12px",
        borderRadius: 6,
      }}
    >
      <strong>Prototype for decision support.</strong> Dispatch, SMS and e-mail are simulated.
      This is not a replacement for police or emergency services. In a real emergency call{" "}
      <strong>112</strong>.
    </p>
  );
}
