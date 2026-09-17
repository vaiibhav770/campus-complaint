"""
Smart Campus AI Classification Engine
------------------------------------
Provides:
1. Category Detection: Hybrid TF-IDF + Multinomial Naive Bayes classifier with keyword boost.
2. Priority / Severity Prediction: Hazard detection, location impact multiplier, urgency cues.
3. Automated Department & Technician Routing.
4. SLA Window Calculation.
5. Explainable AI breakdown tags.
"""

import math
import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any


# ---------------------------------------------------------------------------
# CAMPUS CATEGORIES & KNOWLEDGE BASE
# ---------------------------------------------------------------------------

CATEGORIES = [
    "Wi-Fi & Networking",
    "Electrical Maintenance",
    "Plumbing & Water Supply",
    "Housekeeping & Sanitation",
    "HVAC & Air Conditioning",
    "Furniture & Classroom",
    "Computing & Lab Hardware",
    "Campus Infrastructure & Safety",
]

DEPARTMENT_DIRECTORY = {
    "Wi-Fi & Networking": {
        "department": "IT & Network Operations Cell",
        "officer": "Er. Arvind Kumar (Network Admin)",
        "contact": "netops@campus.edu",
        "base_sla_hours": 12,
    },
    "Electrical Maintenance": {
        "department": "Electrical Engineering & Maintenance",
        "officer": "Ramesh Sharma (Chief Electrician)",
        "contact": "electrical@campus.edu",
        "base_sla_hours": 8,
    },
    "Plumbing & Water Supply": {
        "department": "Water Works & Civil Plumbing Wing",
        "officer": "Suresh Patil (Plumbing Supervisor)",
        "contact": "plumbing@campus.edu",
        "base_sla_hours": 12,
    },
    "Housekeeping & Sanitation": {
        "department": "Campus Sanitation & Housekeeping Wing",
        "officer": "Sunita Rao (Housekeeping Head)",
        "contact": "housekeeping@campus.edu",
        "base_sla_hours": 6,
    },
    "HVAC & Air Conditioning": {
        "department": "Central HVAC & Mechanical Division",
        "officer": "Vikas Mehra (HVAC Engineer)",
        "contact": "hvac@campus.edu",
        "base_sla_hours": 24,
    },
    "Furniture & Classroom": {
        "department": "Estate & Classroom Maintenance",
        "officer": "Manoj Tiwari (Estate Manager)",
        "contact": "estate@campus.edu",
        "base_sla_hours": 36,
    },
    "Computing & Lab Hardware": {
        "department": "Central Computing Facilities (CCF)",
        "officer": "Pooja Verma (Systems Engineer)",
        "contact": "ccf@campus.edu",
        "base_sla_hours": 16,
    },
    "Campus Infrastructure & Safety": {
        "department": "Civil Infrastructure & Campus Safety",
        "officer": "Col. R. S. Bhullar (Security & Works)",
        "contact": "safety.works@campus.edu",
        "base_sla_hours": 18,
    },
}

KEYWORD_RULES: Dict[str, List[str]] = {
    "Wi-Fi & Networking": [
        "wifi", "wi-fi", "internet", "network", "router", "lan", "ethernet", "slow net",
        "packet drop", "dns", "ip address", "signal", "portal", "login page", "hotspot",
        "bandwidth", "disconnect", "wlan", "ssid", "no connectivity"
    ],
    "Electrical Maintenance": [
        "electric", "electricity", "switch", "socket", "power", "plug", "short circuit",
        "spark", "shock", "fan", "ceiling fan", "light", "tube light", "bulb", "mcb",
        "breaker", "fuse", "tripped", "generator", "voltage", "blackout", "flickering"
    ],
    "Plumbing & Water Supply": [
        "water", "tap", "leak", "leakage", "pipe", "drain", "drainage", "sink", "flush",
        "toilet", "washroom tap", "cooler", "drinking water", "overflow", "clogged",
        "sewage", "basin", "faucet", "jet spray", "geyser"
    ],
    "Housekeeping & Sanitation": [
        "dirty", "garbage", "trash", "dustbin", "unclean", "smell", "bad odor", "stink",
        "cleaning", "sweeping", "mopping", "sanitation", "restroom", "hygiene", "mosquito",
        "pest", "cockroach", "litter", "food waste", "spill"
    ],
    "HVAC & Air Conditioning": [
        "ac", "air conditioner", "cooling", "ac water", "compressor", "chiller", "remote",
        "filter", "ac not cooling", "hvac", "thermostat", "duct", "blower", "gas refill"
    ],
    "Furniture & Classroom": [
        "chair", "desk", "bench", "table", "board", "whiteboard", "blackboard", "podium",
        "projector screen", "broken seat", "furniture", "curtain", "blinds", "marker"
    ],
    "Computing & Lab Hardware": [
        "computer", "pc", "monitor", "cpu", "keyboard", "mouse", "printer", "scanner",
        "lab pc", "ram", "hard drive", "operating system", "boot", "blue screen", "projector",
        "hdmi cable", "speaker"
    ],
    "Campus Infrastructure & Safety": [
        "wall", "ceiling", "roof", "crack", "door", "door lock", "window", "broken glass",
        "stairs", "handrail", "elevator", "lift", "pothole", "fire extinguisher", "railing",
        "boundary", "gate", "cctv", "slippery tile"
    ],
}

TRAINING_DATA: List[Tuple[str, str]] = [
    # Wi-Fi & Networking
    ("Wi-Fi in 3rd floor library is extremely slow and disconnecting every 2 minutes", "Wi-Fi & Networking"),
    ("Hostel B router seems down, unable to connect to campus Wi-Fi network", "Wi-Fi & Networking"),
    ("LAN port in room 302 is not responding or giving any IP address", "Wi-Fi & Networking"),
    ("Captive portal page is not loading for student authentication", "Wi-Fi & Networking"),
    ("Very high packet loss and poor ping on campus internet", "Wi-Fi & Networking"),
    ("No signal from Wi-Fi access point in C-block corridor", "Wi-Fi & Networking"),
    ("Cannot access academic portal due to DNS resolution failure on hostel network", "Wi-Fi & Networking"),
    ("Ethernet cable in computer science seminar room is damaged", "Wi-Fi & Networking"),
    ("Wireless router in dining hall blinking red, no internet available", "Wi-Fi & Networking"),
    ("Students unable to submit online assignment due to continuous network outage", "Wi-Fi & Networking"),

    # Electrical Maintenance
    ("Sparking observed in switch board near room 204 electrical socket", "Electrical Maintenance"),
    ("Ceiling fan is making abnormal grinding noise and rotating very slowly", "Electrical Maintenance"),
    ("Tube light in lecture hall 101 is continuously flickering and humming", "Electrical Maintenance"),
    ("MCB breaker in corridor keeps tripping every time the switch is turned on", "Electrical Maintenance"),
    ("Power socket on teacher podium is completely dead, no voltage", "Electrical Maintenance"),
    ("Mild electric shock felt when touching the metal casing of the switch", "Electrical Maintenance"),
    ("Corridor lights on the entire 2nd floor are completely off tonight", "Electrical Maintenance"),
    ("Exhaust fan in laboratory is not rotating, smells like burning wire", "Electrical Maintenance"),
    ("Exposed wire hanging from the false ceiling in chemistry corridor", "Electrical Maintenance"),
    ("Complete power blackout in Wing A since the heavy rain started", "Electrical Maintenance"),

    # Plumbing & Water Supply
    ("Major water pipe burst near washroom causing water flooding into hallway", "Plumbing & Water Supply"),
    ("Tap in 1st floor boys washroom is continuously dripping and wasting water", "Plumbing & Water Supply"),
    ("Drinking water water cooler near library is giving warm and turbid water", "Plumbing & Water Supply"),
    ("Washroom flush tank is broken and water is overflowing onto the floor", "Plumbing & Water Supply"),
    ("Sink drain in mechanical workshop is severely choked, water not draining", "Plumbing & Water Supply"),
    ("No water supply in hostel wing C since morning, taps are completely dry", "Plumbing & Water Supply"),
    ("Geyser in bathroom 4 is leaking water from the bottom valve", "Plumbing & Water Supply"),
    ("Severely clogged drainage line causing foul water to back up in sinks", "Plumbing & Water Supply"),
    ("Water pressure is practically zero on the top floor restrooms", "Plumbing & Water Supply"),
    ("Water fountain tap handle broken off, continuous high pressure fountain", "Plumbing & Water Supply"),

    # Housekeeping & Sanitation
    ("Dustbins outside cafeteria are overflowing with garbage and food waste", "Housekeeping & Sanitation"),
    ("Restroom on ground floor is in extremely unclean condition with foul odor", "Housekeeping & Sanitation"),
    ("Coffee spill on staircase steps between 2nd and 3rd floor is sticky and slippery", "Housekeeping & Sanitation"),
    ("Heavy mosquito menace in hostel common room, needs immediate fogging", "Housekeeping & Sanitation"),
    ("Corridors have not been swept or mopped for two days, thick dust everywhere", "Housekeeping & Sanitation"),
    ("Dead pigeon and droppings found near auditorium ventilation window", "Housekeeping & Sanitation"),
    ("Sanitation supplies and hand soap dispensers in lecture hall restrooms are empty", "Housekeeping & Sanitation"),
    ("Pest and cockroach infestation observed in pantry cupboards", "Housekeeping & Sanitation"),
    ("Unpleasant drainage stink permeating through the entire corridor", "Housekeeping & Sanitation"),
    ("Litter and plastic bottles accumulated behind the basketball court stands", "Housekeeping & Sanitation"),

    # HVAC & Air Conditioning
    ("Air conditioner in seminar hall 2 is not cooling at all, only blowing warm air", "HVAC & Air Conditioning"),
    ("AC unit in lab 4 is leaking water heavily onto the floor right next to computer tables", "HVAC & Air Conditioning"),
    ("AC remote is missing or batteries dead in lecture hall 305", "HVAC & Air Conditioning"),
    ("Loud rattling noise coming from central HVAC blower duct above classroom", "HVAC & Air Conditioning"),
    ("Thermostat in server room is reading 32C, immediate cooling needed to protect servers", "HVAC & Air Conditioning"),
    ("Chiller plant seems shut down, all AC units in the main administrative building off", "HVAC & Air Conditioning"),
    ("Air conditioning air filter is clogged with thick dust, causing asthma irritation", "HVAC & Air Conditioning"),
    ("Split AC display shows Error E4 and shuts down after 5 minutes", "HVAC & Air Conditioning"),
    ("Excessive ice buildup on cooling coil of indoor air conditioning unit", "HVAC & Air Conditioning"),
    ("Very bad burning smell coming from AC vents when turned on", "HVAC & Air Conditioning"),

    # Furniture & Classroom
    ("Three student study chairs in room 108 have broken backrests and sharp edges", "Furniture & Classroom"),
    ("Teacher podium desk has a wobbly leg and is on the verge of collapsing", "Furniture & Classroom"),
    ("Whiteboard in tutorial room 12 is badly stained and cannot be erased", "Furniture & Classroom"),
    ("Projector screen pull-down cord snapped and screen is stuck midway", "Furniture & Classroom"),
    ("Window roller blinds in lecture theater are broken, glare blinding the projector", "Furniture & Classroom"),
    ("Desk bench joint came loose, injuring student's arm on sharp screw", "Furniture & Classroom"),
    ("Auditorium seats row E cushions are torn and springs poking out", "Furniture & Classroom"),
    ("Notice board glass shutter is cracked and lock is broken", "Furniture & Classroom"),
    ("Missing chairs in room 201, insufficient seats for the scheduled class", "Furniture & Classroom"),
    ("Door handle of conference hall is loose and wobbling", "Furniture & Classroom"),

    # Computing & Lab Hardware
    ("System PC-14 in Computer Lab 3 has a continuous blue screen crash on boot", "Computing & Lab Hardware"),
    ("Network laser printer in library paper tray jammed and showing error 49", "Computing & Lab Hardware"),
    ("Monitor display in CAD lab is completely blank with green power LED", "Computing & Lab Hardware"),
    ("Keyboard keys sticking and mouse right click broken on terminal 22", "Computing & Lab Hardware"),
    ("Classroom ceiling projector HDMI cable is bent and showing purple tint", "Computing & Lab Hardware"),
    ("Lab computer hard drive making clicking sound and failing to load OS", "Computing & Lab Hardware"),
    ("Speaker system in multimedia hall producing loud buzzing sound and feedback", "Computing & Lab Hardware"),
    ("Projector bulb exploded or burned out during morning lecture", "Computing & Lab Hardware"),
    ("CPU fan in terminal 8 is screaming loudly and system overheating", "Computing & Lab Hardware"),
    ("Scanner attached to departmental workstation not detected over USB", "Computing & Lab Hardware"),

    # Campus Infrastructure & Safety
    ("Cracked and broken concrete steps on main library staircase, risk of tripping", "Campus Infrastructure & Safety"),
    ("Heavy wooden door of fire exit does not close properly, latch misaligned", "Campus Infrastructure & Safety"),
    ("Glass pane in 3rd floor hallway window is cracked and might fall in strong winds", "Campus Infrastructure & Safety"),
    ("Passenger elevator in Academic Block B is stuck between 2nd and 3rd floor", "Campus Infrastructure & Safety"),
    ("Fire extinguisher in chemical lab shows pressure gauge in red recharge zone", "Campus Infrastructure & Safety"),
    ("Deep pothole right at the campus vehicle entrance causing bike skids", "Campus Infrastructure & Safety"),
    ("Staircase handrail is completely detached from the wall on one side", "Campus Infrastructure & Safety"),
    ("Severe ceiling plaster peeling and falling chunks near classroom entrance", "Campus Infrastructure & Safety"),
    ("Emergency exit sign illumination bulb is dead in basement parking", "Campus Infrastructure & Safety"),
    ("Balcony protective railing in hostel 5 is loose and dangerous", "Campus Infrastructure & Safety"),
]


class TextClassifier:
    """Lightweight, zero-dependency TF-IDF + Multinomial Naive Bayes classifier."""

    def __init__(self):
        self.vocab: Dict[str, int] = {}
        self.doc_count: int = 0
        self.doc_freq: Dict[str, int] = {}
        self.class_doc_counts: Dict[str, int] = {c: 0 for c in CATEGORIES}
        self.class_word_counts: Dict[str, Dict[str, float]] = {c: {} for c in CATEGORIES}
        self.class_total_weights: Dict[str, float] = {c: 0.0 for c in CATEGORIES}
        self._train()

    def _tokenize(self, text: str) -> List[str]:
        clean = re.sub(r"[^a-zA-Z0-9\s-]", " ", text.lower())
        tokens = [w.strip() for w in clean.split() if len(w.strip()) > 2]
        return tokens

    def _train(self):
        docs = [(self._tokenize(text), cat) for text, cat in TRAINING_DATA]
        self.doc_count = len(docs)

        for tokens, cat in docs:
            self.class_doc_counts[cat] = self.class_doc_counts.get(cat, 0) + 1
            unique_tokens = set(tokens)
            for t in unique_tokens:
                self.doc_freq[t] = self.doc_freq.get(t, 0) + 1
                if t not in self.vocab:
                    self.vocab[t] = len(self.vocab)

        for tokens, cat in docs:
            tf = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            total_tokens = len(tokens) or 1

            for t, count in tf.items():
                idf = math.log((self.doc_count + 1) / (self.doc_freq.get(t, 1) + 1)) + 1
                tfidf = (count / total_tokens) * idf
                self.class_word_counts[cat][t] = self.class_word_counts[cat].get(t, 0.0) + tfidf
                self.class_total_weights[cat] += tfidf

    def predict(self, text: str) -> Tuple[str, float, Dict[str, float], List[str]]:
        tokens = self._tokenize(text)
        text_lower = text.lower()

        scores: Dict[str, float] = {}
        alpha = 1.0
        vocab_size = max(len(self.vocab), 1)
        matched_keywords: List[str] = []

        for cat in CATEGORIES:
            prior = math.log(max(self.class_doc_counts.get(cat, 1), 1) / self.doc_count)
            log_prob = prior
            denom = self.class_total_weights[cat] + (alpha * vocab_size)

            for t in tokens:
                num = self.class_word_counts[cat].get(t, 0.0) + alpha
                log_prob += math.log(num / denom)

            kw_boost = 0.0
            for kw in KEYWORD_RULES.get(cat, []):
                if re.search(r"\b" + re.escape(kw) + r"\b", text_lower):
                    kw_boost += 3.5
                    if kw not in matched_keywords:
                        matched_keywords.append(kw)
                elif kw in text_lower:
                    kw_boost += 1.5
                    if kw not in matched_keywords:
                        matched_keywords.append(kw)

            scores[cat] = log_prob + kw_boost

        max_score = max(scores.values()) if scores else 0.0
        exp_scores = {c: math.exp(min(max(s - max_score, -50.0), 50.0)) for c, s in scores.items()}
        total_exp = sum(exp_scores.values()) or 1.0
        probabilities = {c: round((val / total_exp) * 100, 1) for c, val in exp_scores.items()}

        best_cat = max(probabilities, key=probabilities.get)
        confidence = probabilities[best_cat]

        if len(tokens) == 0:
            best_cat = "Campus Infrastructure & Safety"
            confidence = 50.0

        return best_cat, confidence, probabilities, matched_keywords


_CLASSIFIER = TextClassifier()


# ---------------------------------------------------------------------------
# PRIORITY & SEVERITY PREDICTION ENGINE
# ---------------------------------------------------------------------------

CRITICAL_TRIGGERS = [
    "fire", "spark", "sparking", "shock", "electric shock", "smoke", "burning", "gas leak",
    "short circuit", "burst", "pipe burst", "flooding", "collapsed", "collapse", "injury",
    "injured", "blood", "danger", "dangerous", "emergency", "stuck in lift", "stuck in elevator",
    "explosion", "fainted"
]

HIGH_TRIGGERS = [
    "urgent", "urgently", "immediately", "blackout", "no water", "exam", "examination", "interview",
    "placement", "server down", "leaking heavily", "broken glass", "falling", "heavy leak",
    "ac not cooling", "all off", "cannot study", "tripping continuously"
]

MEDIUM_TRIGGERS = [
    "not working", "broken", "damaged", "leak", "flickering", "slow", "noise", "smell",
    "odor", "choked", "clogged", "overflow", "stuck", "loose", "empty", "jammed"
]

HIGH_IMPACT_LOCATIONS = [
    "exam hall", "examination hall", "server room", "auditorium", "seminar hall",
    "library", "girls hostel", "boys hostel", "medical center", "dispensary",
    "chemistry lab", "computer lab", "cafeteria", "mess"
]


def predict_priority_and_severity(
    text: str,
    category: str,
    location: str = ""
) -> Tuple[str, str, int]:
    """
    Computes priority ('Critical', 'High', 'Medium', 'Low'),
    along with an explainable reason and recommended SLA hours.
    """
    text_l = (text + " " + location).lower()
    reasons = []

    # 1. Critical / Safety Hazard Check
    matched_critical = [w for w in CRITICAL_TRIGGERS if w in text_l]
    if matched_critical:
        reasons.append(f"Safety hazard / emergency detected: '{', '.join(matched_critical[:2])}'")
        return "Critical", " & ".join(reasons), 4

    # 2. Location Multiplier Check
    location_boost = False
    matched_loc = [loc for loc in HIGH_IMPACT_LOCATIONS if loc in text_l]
    if matched_loc:
        location_boost = True
        reasons.append(f"High-impact campus area: '{matched_loc[0].title()}'")

    # 3. High Urgency Keywords
    matched_high = [w for w in HIGH_TRIGGERS if w in text_l]
    if matched_high:
        reasons.append(f"Urgent condition detected: '{', '.join(matched_high[:2])}'")
        return "High", " & ".join(reasons), 8

    # 4. Medium or Moderate issues
    matched_med = [w for w in MEDIUM_TRIGGERS if w in text_l]
    if location_boost:
        reasons.append("Impact elevated due to sensitive campus location")
        return "High", " & ".join(reasons), 12

    if matched_med:
        reasons.append(f"Operational disruption: '{', '.join(matched_med[:2])}'")
        return "Medium", " & ".join(reasons), 24

    # 5. Category-specific baseline
    if category in ["Electrical Maintenance", "Plumbing & Water Supply", "HVAC & Air Conditioning"]:
        reasons.append(f"Standard utility issue for {category}")
        return "Medium", " & ".join(reasons), 24

    reasons.append("General maintenance / non-urgent inquiry")
    return "Low", " & ".join(reasons), 48


# ---------------------------------------------------------------------------
# ROUTING & SLA ENGINE
# ---------------------------------------------------------------------------

def calculate_sla_target(sla_hours: int) -> Tuple[str, str]:
    """Returns ISO formatted SLA target timestamp and human readable string."""
    deadline = datetime.now() + timedelta(hours=sla_hours)
    return deadline.strftime("%Y-%m-%d %H:%M:%S"), deadline.strftime("%b %d, %Y at %I:%M %p")


def route_complaint(text: str, location: str = "") -> Dict[str, Any]:
    """
    Complete end-to-end pipeline:
    Analyzes input text -> Predicts Category -> Predicts Priority -> Assigns Department & SLA.
    """
    cat, confidence, probabilities, keywords = _CLASSIFIER.predict(text)
    priority, priority_reason, sla_hours = predict_priority_and_severity(text, cat, location)

    dept_info = DEPARTMENT_DIRECTORY.get(
        cat,
        {
            "department": "Administration Office",
            "officer": "Campus Admin",
            "contact": "admin@campus.edu",
            "base_sla_hours": 24,
        }
    )

    if priority == "Critical":
        effective_sla = 4
    elif priority == "High":
        effective_sla = 8
    elif priority == "Medium":
        effective_sla = min(sla_hours, dept_info["base_sla_hours"])
    else:
        effective_sla = max(48, dept_info["base_sla_hours"])

    sla_iso, sla_readable = calculate_sla_target(effective_sla)

    return {
        "category": cat,
        "confidence": confidence,
        "top_probabilities": dict(sorted(probabilities.items(), key=lambda x: x[1], reverse=True)[:4]),
        "matched_keywords": keywords[:5],
        "priority": priority,
        "priority_reason": priority_reason,
        "department": dept_info["department"],
        "assigned_officer": dept_info["officer"],
        "department_contact": dept_info["contact"],
        "sla_hours": effective_sla,
        "sla_target_iso": sla_iso,
        "sla_target_readable": sla_readable,
    }
