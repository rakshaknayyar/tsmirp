"""SYNTHETIC incident-description generator (English, Hindi, romanised Hindi).

How it works: for every category there are hand-written sentence TEMPLATES with slots such
as {item} or {place}. A row is made by picking a template at random, filling the slots with
random words, and adding small random variations (a prefix like "Urgent:", a suffix like
"Please help.", lower-casing, a missing full stop).

Documented assumptions / limitations:
- All text is SYNTHETIC. Real tourist reports are messier (typos, mixed languages, several
  problems in one message), so any accuracy measured on this data is OPTIMISTIC and says
  nothing about real-world performance.
- Every row records its template_id, so train and test can be split BY TEMPLATE: the test
  set then only contains sentence patterns the model has never seen.
- The label of a row is the category its template was written for (no human labelling).
- Same seed -> exactly the same rows.
"""

import csv
import random
from dataclasses import dataclass
from pathlib import Path

CATEGORIES = [
    "theft",
    "harassment",
    "medical_emergency",
    "accident",
    "lost_person",
    "suspicious_activity",
    "natural_disaster",
    "fire",
    "other",
]
LANGUAGES = ["en", "hi", "hi-Latn"]  # English, Hindi (Devanagari), romanised Hindi

SLOTS = {
    "en": {
        "place": [
            "the market",
            "Johari Bazaar",
            "the railway station",
            "the bus stand",
            "Hawa Mahal",
            "the hotel",
            "the fort",
            "the City Palace",
            "the main road",
            "the temple",
            "the mall",
            "the parking lot",
        ],
        "time": [
            "this morning",
            "an hour ago",
            "just now",
            "last night",
            "a few minutes ago",
            "around noon",
        ],
        "item": ["phone", "mobile", "passport", "wallet", "purse", "bag", "camera", "laptop"],
        "person": [
            "my friend",
            "my wife",
            "my husband",
            "my son",
            "my daughter",
            "my father",
            "my mother",
            "a fellow tourist",
            "my colleague",
        ],
        "child": ["my son", "my daughter", "my child", "my little brother"],
    },
    "hi": {
        "place": ["बाज़ार", "रेलवे स्टेशन", "बस अड्डे", "हवा महल", "होटल", "किले", "मंदिर"],
        "item": ["फ़ोन", "मोबाइल", "पर्स", "बटुआ", "पासपोर्ट", "बैग", "कैमरा"],
        "person": ["मेरे दोस्त", "मेरी पत्नी", "मेरे पति", "मेरे पिताजी", "मेरी माँ"],
    },
    "hi-Latn": {
        "place": ["market", "railway station", "bus adda", "Hawa Mahal", "hotel", "kila", "mandir"],
        "item": ["phone", "mobile", "purse", "batua", "passport", "bag", "camera"],
        "person": ["mere dost", "meri patni", "mere pati", "mere papa", "meri mummy"],
    },
}

TEMPLATES: dict[str, dict[str, list[str]]] = {
    "en": {
        "theft": [
            "My {item} was stolen near {place}.",
            "Someone stole my {item} at {place} {time}.",
            "I think a pickpocket took my {item} {time}.",
            "My {item} is missing, I think it was stolen in the crowd at {place}.",
            "A man snatched my {item} and ran away near {place}.",
            "Two men on a bike grabbed my {item} near {place}.",
            "My {item} got stolen from my bag {time}.",
            "Somebody took my {item} from the table at {place}.",
            "A thief ran off with my {item}.",
            "My hotel room was broken into and my {item} is gone.",
            "I was robbed near {place}, they took my {item}.",
            "Pickpocket at {place}! My {item} is gone.",
            "Someone picked my pocket at {place} and took my {item}.",
            "I left my {item} on a bench for a minute and someone took it.",
            "My {item} was snatched from my hand at {place}.",
            "Robbery near {place}, a man grabbed my {item}.",
            "My {item} disappeared from my backpack while I was at {place}.",
            "A boy ran past me and stole my {item}.",
            "Thieves broke into our car at {place} and took my {item}.",
            "My {item} has been stolen, I saw the thief running away.",
        ],
        "harassment": [
            "A man has been following me since {place}.",
            "Some men are making rude comments at me near {place}.",
            "A shopkeeper at {place} touched me inappropriately.",
            "Someone keeps harassing me and will not leave me alone.",
            "I am being stalked by a man near {place}.",
            "A group of boys are teasing and bothering me at {place}.",
            "A driver is threatening me and demanding extra money.",
            "Someone is sending me abusive messages after I met him at {place}.",
            "A man tried to grab my hand and pull me at {place}.",
            "A stranger keeps staring at me and following me.",
            "The guide is pressuring me and being aggressive.",
            "A man is bothering me and will not stop asking for my number.",
            "Someone groped me in the crowd at {place}.",
            "A man is shouting at me and calling me names.",
            "Some men cornered me near {place} and made me uncomfortable.",
            "A taxi driver keeps sending me inappropriate messages.",
            "I am being harassed by a member of the hotel staff.",
            "A group of men are whistling and following me around {place}.",
            "Someone is intimidating me and refusing to let me pass.",
        ],
        "medical_emergency": [
            "{person} has collapsed at {place} and needs a doctor.",
            "{person} is having chest pain, please send an ambulance.",
            "I feel very dizzy and have a high fever.",
            "{person} fainted because of the heat near {place}.",
            "{person} is having trouble breathing.",
            "Severe stomach pain and vomiting since {time}.",
            "{person} is having an allergic reaction and their face is swelling.",
            "I think I have food poisoning, I need medical help.",
            "{person} is diabetic and is feeling very weak.",
            "{person} had a seizure at {place}.",
            "Need a doctor urgently, {person} is not feeling well.",
            "{person} is bleeding a lot and needs medical attention.",
            "I have a bad headache and keep vomiting.",
            "{person} is pregnant and has severe pain.",
            "{person} is unconscious at {place}.",
            "Heat stroke: {person} is very hot and confused.",
            "I need an ambulance, {person} cannot stand up.",
            "{person} has a very high temperature and is shivering.",
            "I was bitten by a dog near {place} and need a rabies injection.",
        ],
        "accident": [
            "There was a road accident near {place}.",
            "Our auto rickshaw crashed into a car at {place}.",
            "{person} fell down the stairs at {place}.",
            "A bike hit {person} while crossing the road near {place}.",
            "Our taxi had a collision on the highway {time}.",
            "{person} slipped and fell at {place} and hurt their leg.",
            "A car knocked down a pedestrian near {place}.",
            "I tripped on the broken pavement and twisted my ankle.",
            "{person} fell off a camel at {place}.",
            "Bus accident near {place}, some people are hurt.",
            "A truck crashed into our car near {place}.",
            "{person} was hit by a motorbike at {place}.",
            "Our cab overturned on the way to {place}.",
            "There has been a crash between two buses near {place}.",
            "{person} fell from the wall at {place}.",
            "A scooter skidded and hit me near {place}.",
            "Two cars collided in front of {place}.",
            "{person} got injured when a rickshaw hit them.",
        ],
        "lost_person": [
            "I cannot find {person}, we got separated at {place}.",
            "{person} has been missing since {time}.",
            "We lost {child} in the crowd at {place}.",
            "{person} went for a walk and has not come back.",
            "I am lost and do not know how to get back to my hotel.",
            "{person} is not answering the phone and we cannot find them.",
            "A member of our group is missing after the visit to {place}.",
            "{child} wandered off at {place} and we cannot find them.",
            "I lost my way near {place} and my phone battery is dead.",
            "Looking for {person} who was last seen at {place}.",
            "{child} is missing, we last saw them at {place}.",
            "We have been searching for {person} for hours.",
            "{person} did not come back to the hotel {time}.",
            "I got separated from my tour group at {place}.",
            "Has anyone seen {child}? They disappeared at {place}.",
            "{person} is elderly and has gone missing near {place}.",
            "Our friend never came back from {place}.",
            "I do not know where I am, I am lost near {place}.",
        ],
        "suspicious_activity": [
            "There is an unattended bag lying at {place}.",
            "Some people are acting suspiciously near {place}.",
            "Someone is trying to sell fake tickets at {place}.",
            "A person is checking car doors in the parking lot.",
            "I saw someone hiding something near {place}.",
            "There is a strange package near the entrance of {place}.",
            "A group is loitering near the ATM and watching people.",
            "Someone offered me a suspicious drink at {place}.",
            "A fake guide is collecting money from tourists at {place}.",
            "A man is secretly filming women at {place}.",
            "A man is fitting a card skimmer to the ATM near {place}.",
            "Unknown people are trying to enter the hotel at night.",
            "There is an abandoned suitcase at {place}.",
            "A van has been parked near {place} for hours with people watching.",
            "Someone is offering fake currency exchange at {place}.",
            "A person is asking tourists for their passport details at {place}.",
            "I saw a man trying to break a car window at {place}.",
            "Strangers are asking many questions about our hotel and room.",
        ],
        "natural_disaster": [
            "There is heavy flooding near {place}.",
            "The building is shaking, I think it is an earthquake.",
            "A big storm has damaged the roads near {place}.",
            "Strong winds have knocked down trees near {place}.",
            "Water is rising fast in the street near {place}.",
            "There was a landslide on the road to {place}.",
            "A dust storm hit {place} and we cannot see anything.",
            "Heavy rain has flooded the ground floor of our hotel.",
            "Lightning struck near {place} during the storm.",
            "A wall collapsed after the heavy rain near {place}.",
            "The river has overflowed near {place}.",
            "Our road is blocked by fallen trees after the storm.",
            "There was an earthquake and the walls have cracks.",
            "A hailstorm near {place} has damaged the roof.",
            "Flash flood near {place}, cars are under water.",
            "There is a cyclone warning and the wind is very strong.",
            "Rocks fell on the road near {place} after the rain.",
            "The heatwave is extreme and the power has gone out.",
        ],
        "fire": [
            "There is a fire at {place}.",
            "Smoke is coming out of a shop near {place}.",
            "Our hotel room is on fire.",
            "A car caught fire near {place}.",
            "I can see flames in the building next to {place}.",
            "There is a gas cylinder fire in the restaurant.",
            "Fire broke out in the market near {place}.",
            "Something is burning and the corridor is full of smoke.",
            "The kitchen of the guest house is on fire.",
            "A short circuit started a fire at {place}.",
            "The building next to {place} is in flames.",
            "There is a fire in our bus.",
            "The fire alarm is ringing and there is smoke on our floor.",
            "A shop at {place} is burning.",
            "The electrical wiring caught fire at {place}.",
            "Black smoke and flames are coming from the hotel roof.",
            "A fire started in a tent at the camp.",
            "There is a blaze near {place}, people are running out.",
        ],
        "other": [
            "The hotel is charging me much more than agreed.",
            "I need information about the visa extension office.",
            "My hotel booking was cancelled and I have nowhere to stay.",
            "The tour operator did not refund my money.",
            "I want to report a problem with my taxi fare.",
            "Where can I find an ATM that accepts foreign cards?",
            "The restaurant served me spoiled food and refused a refund.",
            "I need help contacting my embassy.",
            "My train was cancelled, what should I do?",
            "There is very loud noise near my hotel all night.",
            "I was overcharged by the auto driver.",
            "The guest house refuses to return my deposit.",
            "I need a translator to talk to the hotel manager.",
            "My flight was delayed and I need a place to stay.",
            "The shop sold me a fake product and will not take it back.",
            "Can you tell me where the nearest tourist information office is?",
            "The water supply in my room is not working.",
            "The museum ticket counter refused my card payment.",
        ],
    },
    "hi": {
        "theft": [
            "{place} के पास मेरा {item} चोरी हो गया।",
            "किसी ने मेरा {item} चुरा लिया।",
            "भीड़ में किसी ने मेरा {item} छीन लिया।",
            "मेरा {item} चोरी हो गया है, कृपया मदद करें।",
        ],
        "harassment": [
            "एक आदमी {place} से मेरा पीछा कर रहा है।",
            "कुछ लोग मुझे परेशान कर रहे हैं।",
            "एक आदमी ने मेरे साथ बदतमीज़ी की।",
            "कोई मुझे लगातार छेड़ रहा है।",
        ],
        "medical_emergency": [
            "{person} की तबीयत बहुत खराब है, डॉक्टर चाहिए।",
            "{person} को सीने में दर्द है, एम्बुलेंस भेजिए।",
            "मुझे तेज़ बुखार और चक्कर आ रहे हैं।",
            "{person} को सांस लेने में तकलीफ़ है।",
        ],
        "accident": [
            "{place} के पास सड़क दुर्घटना हुई है।",
            "हमारी टैक्सी की टक्कर हो गई।",
            "{person} को बाइक ने टक्कर मार दी।",
            "ऑटो पलट गया, कुछ लोग घायल हैं।",
        ],
        "lost_person": [
            "मेरा बच्चा {place} में खो गया है।",
            "{person} का कुछ पता नहीं चल रहा।",
            "मैं रास्ता भटक गया हूँ, होटल कैसे जाऊँ?",
            "हमारे ग्रुप का एक सदस्य लापता है।",
        ],
        "suspicious_activity": [
            "{place} पर एक लावारिस बैग पड़ा है।",
            "कुछ लोग {place} के पास संदिग्ध हरकत कर रहे हैं।",
            "कोई नकली टिकट बेच रहा है।",
            "एक आदमी पार्किंग में गाड़ियों के दरवाज़े खोलने की कोशिश कर रहा है।",
        ],
        "natural_disaster": [
            "{place} के पास बाढ़ आ गई है।",
            "इमारत हिल रही है, शायद भूकंप है।",
            "तेज़ आंधी से पेड़ गिर गए हैं।",
            "भारी बारिश से सड़क पर पानी भर गया है।",
        ],
        "fire": [
            "{place} में आग लग गई है।",
            "होटल के कमरे से धुआं निकल रहा है।",
            "एक गाड़ी में आग लग गई है।",
            "रसोई में सिलेंडर से आग लगी है।",
        ],
        "other": [
            "होटल वाले तय से ज़्यादा पैसे मांग रहे हैं।",
            "मुझे अपने दूतावास से संपर्क करना है।",
            "मेरी ट्रेन रद्द हो गई है, क्या करूँ?",
            "टूर वाले ने मेरे पैसे वापस नहीं किए।",
        ],
    },
    "hi-Latn": {
        "theft": [
            "Mera {item} chori ho gaya hai",
            "{place} ke paas mera {item} chori ho gaya",
            "Kisi ne mera {item} chura liya",
            "Bheed mein kisi ne mera {item} chheen liya",
        ],
        "harassment": [
            "Ek aadmi {place} se mera peecha kar raha hai",
            "Kuch log mujhe pareshan kar rahe hain",
            "Ek aadmi ne mere saath badtameezi ki",
            "Koi mujhe baar baar chhed raha hai",
        ],
        "medical_emergency": [
            "{person} ki tabiyat bahut kharab hai, doctor chahiye",
            "{person} ko seene mein dard hai, ambulance bhejiye",
            "Mujhe tez bukhar aur chakkar aa rahe hain",
            "{person} ko saans lene mein taklif hai",
        ],
        "accident": [
            "{place} ke paas accident ho gaya hai",
            "Hamari taxi ki takkar ho gayi",
            "{person} ko bike ne takkar maar di",
            "Auto palat gaya, kuch log ghayal hain",
        ],
        "lost_person": [
            "Mera bachcha {place} mein kho gaya hai",
            "{person} ka kuch pata nahi chal raha",
            "Main rasta bhatak gaya hoon",
            "Hamare group ka ek sadasya lapata hai",
        ],
        "suspicious_activity": [
            "{place} par ek lawaris bag pada hai",
            "Kuch log {place} ke paas sandigdh harkat kar rahe hain",
            "Koi nakli ticket bech raha hai",
            "Ek aadmi parking mein gaadiyon ke darwaze khol raha hai",
        ],
        "natural_disaster": [
            "{place} ke paas baadh aa gayi hai",
            "Building hil rahi hai, shayad bhookamp hai",
            "Tez aandhi se ped gir gaye hain",
            "Bhaari baarish se sadak par paani bhar gaya hai",
        ],
        "fire": [
            "{place} mein aag lag gayi hai",
            "Hotel ke kamre se dhuan nikal raha hai",
            "Ek gaadi mein aag lag gayi hai",
            "Kitchen mein cylinder se aag lagi hai",
        ],
        "other": [
            "Hotel wale tay se zyada paise maang rahe hain",
            "Mujhe apne embassy se sampark karna hai",
            "Meri train cancel ho gayi hai, kya karoon?",
            "Tour wale ne mere paise wapas nahi kiye",
        ],
    },
}

PREFIXES = {
    "en": ["", "", "", "Please help. ", "Urgent: ", "Hello, ", "Help! "],
    "hi": ["", "", "कृपया मदद करें, ", "जल्दी मदद कीजिए, "],
    "hi-Latn": ["", "", "Please help, ", "Jaldi madad kijiye, "],
}
SUFFIXES = {
    "en": ["", "", "", " Please help.", " What should I do?", " Please send someone."],
    "hi": ["", "", " कृपया मदद करें।"],
    "hi-Latn": ["", "", " please help", " kya karoon?"],
}


@dataclass(frozen=True)
class TextRow:
    text: str
    category: str
    language: str
    template_id: str  # e.g. "en-theft-03"; used to split train/test by template
    synthetic: bool = True


def _fill(template: str, slots: dict[str, list[str]], rng: random.Random) -> str:
    values = {name: rng.choice(words) for name, words in slots.items()}
    text = template.format(**values)
    return text[0].upper() + text[1:]


def generate_texts(seed: int, per_category: dict[str, int] | None = None) -> list[TextRow]:
    """Make the synthetic rows. per_category = rows per (language, category)."""
    per_category = per_category or {"en": 300, "hi": 60, "hi-Latn": 60}
    rng = random.Random(seed)
    rows = []
    for language in LANGUAGES:
        for category in CATEGORIES:
            templates = TEMPLATES[language][category]
            for _ in range(per_category[language]):
                index = rng.randrange(len(templates))
                text = _fill(templates[index], SLOTS[language], rng)
                text = rng.choice(PREFIXES[language]) + text + rng.choice(SUFFIXES[language])
                if language != "hi" and rng.random() < 0.2:
                    text = text.lower()
                if rng.random() < 0.3:
                    text = text.rstrip(".।")
                rows.append(
                    TextRow(
                        text=text,
                        category=category,
                        language=language,
                        template_id=f"{language}-{category}-{index:02d}",
                    )
                )
    return rows


def write_csv(rows: list[TextRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["text", "category", "language", "template_id", "synthetic"])
        for row in rows:
            writer.writerow([row.text, row.category, row.language, row.template_id, "true"])
