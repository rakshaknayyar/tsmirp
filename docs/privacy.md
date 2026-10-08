# Privacy and safety principles

These rules apply to every phase of the project.

1. **Consent first.** A tourist's location is collected only after explicit consent, which can
   be revoked at any time. The consent time is recorded.
2. **Limited visibility.** Authorities see a tourist's location only if the tourist consented,
   or while an SOS is active.
3. **Retention.** Stored locations have an expiry time and are deleted by a retention job
   (Phase 9).
4. **Simulation, not dispatch.** Emergency dispatch, SMS and e-mail are simulated sandbox
   adapters that only write to the database and logs. The system never contacts real
   emergency services. In a real emergency, call **112**.
5. **Synthetic data.** Datasets are open or synthetic, and every synthetic dataset and result
   is labelled "synthetic". No real-world accuracy is claimed.
6. **No biased labels.** Models are not trained on arrests or other enforcement-derived labels.
7. **Audit trail.** Sensitive actions are written to a hash-chained audit log (Phase 1).
8. **Risk wording.** Risk scores are relative decision-support estimates, never a prediction
   that a crime will occur.
