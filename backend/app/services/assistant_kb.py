"""The assistant's knowledge base: a fixed, hand-written list of safety topics.

Rules for this file:
- Phone numbers: ONLY 112 (India's single emergency number) and 1363 (Ministry of Tourism
  tourist helpline). A test fails if any other number appears, so nothing can be invented.
- Answers are general guidance for tourists, not legal or medical advice.
- Keywords are English (and lower case). Hindi and romanised Hindi questions are translated to
  English first, by the same word list as incident reports.
- Order matters: when two topics match equally well, the one higher in the list wins, so the
  most urgent topics come first.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Topic:
    id: str
    title: str
    keywords: tuple[str, ...]
    answer: str


TOPICS = [
    Topic(
        "emergency",
        "Emergency number",
        ("emergency", "danger", "police", "attack", "attacked", "urgent", "help me", "112"),
        "Call 112, India's single emergency number for police, fire and ambulance. In this app "
        "you can also press SOS. Note: in this prototype the SOS dispatch is simulated, so in "
        "real danger always call 112 as well.",
    ),
    Topic(
        "fire",
        "Fire",
        ("fire", "smoke", "burning", "flames"),
        "Leave the building straight away using the stairs, not the lift. Stay low if there is "
        "smoke, and close doors behind you. Call 112 once you are safe. Do not go back inside "
        "for belongings.",
    ),
    Topic(
        "medical",
        "Medical help",
        (
            "doctor",
            "hospital",
            "sick",
            "fever",
            "pain",
            "unwell",
            "medical",
            "ambulance",
            "dizzy",
            "breathing",
            "heat",
            "medicine",
        ),
        "For a serious medical problem call 112 for an ambulance. The 'Nearby help' list on the "
        "map shows hospitals close to you (straight-line distance). In hot weather drink plenty "
        "of water and rest in the shade.",
    ),
    Topic(
        "harassment",
        "Harassment or being followed",
        (
            "harassment",
            "harassing",
            "harassed",
            "following",
            "followed",
            "stalking",
            "teasing",
            "touched",
            "groped",
            "bothering",
            "misbehaved",
        ),
        "Move to a busy, well-lit place such as a shop or hotel lobby and tell people around "
        "you. If you feel unsafe, call 112. You can report it in this app; harassment reports "
        "are marked HIGH severity for the operators.",
    ),
    Topic(
        "passport",
        "Lost or stolen passport",
        # The phrases help against the general "lost" topic ("passport kho gaya" ->
        # "passport lost missing" would otherwise score 2 for "lost" and only 1 here).
        ("passport", "visa", "passport lost", "lost passport", "lost my passport"),
        "Report the loss at the nearest police station and ask for a copy of the report. Then "
        "contact your country's embassy or consulate for an emergency travel document. It "
        "helps to keep a photo of your passport and visa separately from the originals.",
    ),
    Topic(
        "theft",
        "Theft",
        (
            "stolen",
            "theft",
            "stole",
            "pickpocket",
            "snatched",
            "robbed",
            "robbery",
            "wallet",
            "purse",
            "phone",
            "mobile",
            "bag",
        ),
        "First move to a safe place. Report the theft at the nearest police station (the map "
        "shows police stations near you) and ask for a copy of the complaint (FIR): you may "
        "need it for insurance or new documents. Block your bank cards and SIM through their "
        "providers. You can also report it in this app.",
    ),
    Topic(
        "lost",
        "Lost person or lost your way",
        ("lost", "missing", "child", "separated", "cannot find", "way", "directions"),
        "If someone from your group is missing, stay where you last saw them if it is safe, "
        "tell staff or police nearby, and call 112 if a child is missing. If you are lost, go "
        "into a shop, hotel or police post and ask for help; share your location in this app "
        "only if you want to.",
    ),
    Topic(
        "disaster",
        "Flood, storm or earthquake",
        ("flood", "flooding", "earthquake", "storm", "rain", "landslide", "cyclone", "shaking"),
        "Earthquake: drop, cover and hold on; move away from windows. Flood: go to higher ground "
        "and do not walk or drive through moving water. Storm: stay indoors away from trees and "
        "power lines. Follow instructions from local authorities and call 112 if in danger.",
    ),
    Topic(
        "scam",
        "Overcharging, fake guides and scams",
        (
            "overcharged",
            "overcharging",
            "fare",
            "taxi",
            "auto",
            "scam",
            "fake",
            "guide",
            "refund",
            "charging",
            "price",
            "money",
            "cheated",
        ),
        "Agree on the fare before the ride, or use a meter, a prepaid booth or an app cab. Use "
        "only licensed guides and keep receipts. You can report fraud to the police or ask the "
        "tourist helpline 1363 for advice.",
    ),
    Topic(
        "helpline",
        "Tourist helpline",
        ("helpline", "information", "tourist information", "1363", "tourism"),
        "The Ministry of Tourism's tourist helpline is 1363. For any emergency call 112.",
    ),
    Topic(
        "embassy",
        "Embassy or consulate",
        ("embassy", "consulate"),
        "Contact your country's embassy or consulate; their phone numbers are on your own "
        "government's travel website. This app does not list embassy numbers.",
    ),
    Topic(
        "sos",
        "How SOS works",
        ("sos", "button", "panic"),
        "Press SOS and you have 5 seconds to cancel. Then a CRITICAL incident is created with "
        "your last shared location, operators see it on the dashboard, and your emergency "
        "contacts are notified. In this prototype the dispatch, SMS and e-mail are SIMULATED, "
        "so in real danger also call 112.",
    ),
    Topic(
        "risk",
        "Risk levels and alerts on the map",
        ("risk", "zone", "zones", "alert", "alerts", "safe", "unsafe", "dangerous", "area"),
        "The coloured areas show relative risk levels (LOW, MODERATE, HIGH, CRITICAL). They are "
        "estimates for decision support, not predictions that a crime will occur, and the demo "
        "areas are based on synthetic data. If you share your location and stay in a HIGH or "
        "CRITICAL area for a while, you get an in-app alert.",
    ),
    Topic(
        "privacy",
        "Location and privacy",
        ("location", "privacy", "consent", "tracking", "data", "share"),
        "Your location is used only after you switch on consent, and you can switch it off at "
        "any time: the stored location is then deleted. Authorities can see your location only "
        "while consent is on or during an active SOS, and every view is logged.",
    ),
    Topic(
        "report",
        "How to report an incident",
        ("report", "complaint", "incident"),
        "Use 'Report an incident' in this app. Describe what happened in English, Hindi or "
        "romanised Hindi; the category is suggested automatically and an operator checks it.",
    ),
]

EMERGENCY_LINE = "Emergency: 112. Tourist helpline: 1363."
FALLBACK_ANSWER = (
    "Sorry, I can only answer a fixed set of tourist-safety questions: emergencies, theft, lost "
    "passport, harassment, medical help, lost persons, fire, floods and storms, scams, SOS, "
    "risk levels and privacy. Please try asking in other words."
)
