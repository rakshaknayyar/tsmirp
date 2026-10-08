"""Sending notifications.

IMPORTANT: only SANDBOX adapters exist. SMS and e-mail are written to the notifications
table (marked simulated) and to the log - nothing is ever sent to a real phone, mailbox or
emergency service. A real SMS / e-mail provider is deliberately not implemented.

In-app notifications are real (the tourist sees them in the app).
"""

import logging

from sqlalchemy.orm import Session

from app.models.incident import Incident, IncidentStatus
from app.models.notification import Notification, NotificationChannel

logger = logging.getLogger("tsmirp.sandbox")


def _mask(recipient: str) -> str:
    """Logs show only the last 4 characters of a phone number or e-mail address."""
    return "***" + recipient[-4:] if len(recipient) > 4 else "***"


class SandboxSender:
    """Pretends to send an SMS or e-mail: stores it and logs it, nothing more."""

    def __init__(self, channel: NotificationChannel, label: str) -> None:
        self.channel = channel
        self.label = label

    def send(
        self,
        db: Session,
        *,
        recipient: str,
        kind: str,
        title: str,
        body: str,
        incident_id: int | None = None,
        user_id: int | None = None,
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            recipient=recipient,
            channel=self.channel,
            kind=kind,
            title=title,
            body=f"[SIMULATED {self.label} - not sent] {body}",
            incident_id=incident_id,
            simulated=True,
        )
        db.add(notification)
        logger.info("SANDBOX %s (not sent) to %s: %s", self.label, _mask(recipient), title)
        return notification


sandbox_sms = SandboxSender(NotificationChannel.SMS_SANDBOX, "SMS")
sandbox_email = SandboxSender(NotificationChannel.EMAIL_SANDBOX, "E-MAIL")


def notify_in_app(
    db: Session,
    user_id: int,
    *,
    kind: str,
    title: str,
    body: str,
    incident_id: int | None = None,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        channel=NotificationChannel.IN_APP,
        kind=kind,
        title=title,
        body=body,
        incident_id=incident_id,
        simulated=False,
    )
    db.add(notification)
    return notification


STATUS_MESSAGES = {
    IncidentStatus.ACKNOWLEDGED: "An operator has seen your report.",
    IncidentStatus.ASSIGNED: (
        "A response unit has been assigned (simulated dispatch: this prototype does not "
        "send real units)."
    ),
    IncidentStatus.EN_ROUTE: "The assigned unit is marked as on its way (simulated).",
    IncidentStatus.RESOLVED: "Your report has been marked as resolved.",
    IncidentStatus.CLOSED: "Your report has been closed.",
}


def notify_reporter_of_status(db: Session, incident: Incident) -> None:
    """Tell the tourist who reported the incident that its status changed."""
    if incident.reporter_user_id is None or incident.status not in STATUS_MESSAGES:
        return
    body = STATUS_MESSAGES[incident.status]
    if incident.is_sos and incident.status not in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED):
        body += " If you are in danger, call 112 now."
    notify_in_app(
        db,
        incident.reporter_user_id,
        kind="incident_update",
        title=f"Update on {'your SOS' if incident.is_sos else 'your report'} #{incident.id}: "
        f"{incident.status.value}",
        body=body,
        incident_id=incident.id,
    )
