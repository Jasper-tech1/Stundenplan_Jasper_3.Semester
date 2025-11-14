import re
import requests
from icalendar import Calendar

# ==============================
# KONFIGURATION
# ==============================

# HIER deine Uni-Stundenplan-ICS-Links eintragen:
FEED_URLS = [
    "https://sked.lin.hs-osnabrueck.de/sked/grp/24BTS-CPV-3.ics",
    "https://sked.lin.hs-osnabrueck.de/sked/grp/24BTS-EAT-3.ics",
]

# Module, die du NICHT sehen willst:
EXCLUDE_KEYWORDS = [
    "grundlagen data science",
    "englisch",
    "physikalische chemie",
    "thermodynamik",
    "Elektrotechnik",
    "Metallbau",
]

# ==============================
# HILFSFUNKTIONEN
# ==============================

def normalize_summary(summary: str) -> str:
    """
    Vereinfacht den Titel:
    - entfernt alles in Klammern (Gruppenangaben etc.)
    - reduziert Mehrfach-Leerzeichen
    - alles klein
    -> hilft bei Duplikat-Erkennung
    """
    if not summary:
        return ""
    s = str(summary)

    s = re.sub(r"\([^)]*\)", "", s)  # Klammern entfernen
    s = re.sub(r"\s+", " ", s)       # Mehrfach-Leerzeichen
    return s.strip().lower()


def should_keep_event(summary: str) -> bool:
    """
    Event behalten? -> Ja, außer es enthält eins der EXCLUDE_KEYWORDS.
    """
    s = (summary or "").lower()

    for bad in EXCLUDE_KEYWORDS:
        if bad.lower() in s:
            print(f"Filtere Event wegen Keyword '{bad}': {summary}")
            return False
    return True


# ==============================
# HAUPT-LOGIK
# ==============================

def build_merged_calendar() -> Calendar:
    print("Baue zusammengeführten Kalender ...")
    merged_cal = Calendar()
    merged_cal.add("prodid", "-//Merged Uni Plan//DE")
    merged_cal.add("version", "2.0")

    seen = set()  # (dtstart, normalisierter Titel)
    total_events = 0
    kept_events = 0

    for url in FEED_URLS:
        try:
            print(f"Lade {url} ...")
            resp = requests.get(url, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            print(f"Fehler beim Laden von {url}: {e}")
            continue

        try:
            src_cal = Calendar.from_ical(resp.text)
        except Exception as e:
            print(f"Fehler beim Parsen von {url}: {e}")
            continue

        for component in src_cal.walk():
            if component.name != "VEVENT":
                continue

            total_events += 1
            summary = str(component.get("summary", ""))

            if not should_keep_event(summary):
                continue

            dtstart = component.get("dtstart")
            if not dtstart:
                continue
            dtstart = dtstart.dt

            norm_title = normalize_summary(summary)
            key = (dtstart, norm_title)

            if key in seen:
                print(f"Duplikat, überspringe: {summary} @ {dtstart}")
                continue
            seen.add(key)

            merged_cal.add_component(component)
            kept_events += 1

    print(f"Fertig: {kept_events} von {total_events} Events übernommen.")
    return merged_cal


def main():
    cal = build_merged_calendar()
    ics_data = cal.to_ical()

    output_path = "merged_calendar.ics"
    with open(output_path, "wb") as f:
        f.write(ics_data)

    print(f"Kalender-Datei gespeichert unter: {output_path}")


if __name__ == "__main__":
    main()
