import re
import requests
from copy import deepcopy
from icalendar import Calendar


# Kalenderquellen
FEED_URLS = [
    "https://sked.lin.hs-osnabrueck.de/sked/grp/24BTS-EAT-5.ics",
    "https://sked.lin.hs-osnabrueck.de/sked/grp/24DNE-PDM-5.ics",
    
]


# Nur diese Module werden in den neuen Kalender übernommen
INCLUDE_KEYWORDS = [
    "Mess- und Sensortechnik",
    "Methoden der KI - Deep and Reinforcement Learning",
    "Produktionsplanung und -steuerung",
    "Agiles Projektmanagement & Change Management",
    "Experimentelle Steuerungs- und Digitaltechnik",
    "Projektierung technischer Systeme",
]


# Name der erzeugten Kalenderdatei
OUTPUT_FILE = "merged_calendar.ics"


def normalize_encoding(s: str) -> str:
    """
    Korrigiert typische fehlerhafte UTF-8-Zeichen.
    """
    if not s:
        return ""

    replacements = {
        "Ã¼": "ü",
        "Ã¶": "ö",
        "Ã¤": "ä",
        "Ãœ": "Ü",
        "Ã–": "Ö",
        "Ã„": "Ä",
        "ÃŸ": "ß",
        "â€“": "–",
        "â€”": "—",
        "â€ž": "„",
        "â€œ": "“",
        "â€š": "‚",
        "â€™": "’",
        "â€¦": "…",
        "Â": "",
    }

    for wrong, right in replacements.items():
        s = s.replace(wrong, right)

    return s


def clean_text(s: str) -> str:
    """
    Bereinigt einen Text und entfernt überflüssige Leerzeichen.
    """
    if not s:
        return ""

    s = str(s)
    s = normalize_encoding(s)
    s = re.sub(r"\s+", " ", s)

    return s.strip()


def normalize_summary(summary: str) -> str:
    """
    Vereinheitlicht einen Veranstaltungstitel für den Vergleich.

    Dabei werden:
    - fehlerhafte Zeichen korrigiert,
    - Inhalte in Klammern entfernt,
    - überflüssige Leerzeichen entfernt,
    - Groß- und Kleinschreibung ignoriert.
    """
    s = clean_text(summary)

    # Zusätze in Klammern entfernen
    s = re.sub(r"\([^)]*\)", "", s)

    # Unterschiedliche Bindestriche vereinheitlichen
    s = s.replace("–", "-")
    s = s.replace("—", "-")

    # Mehrere Leerzeichen entfernen
    s = re.sub(r"\s+", " ", s)

    return s.strip().casefold()


def should_keep_event(summary: str) -> bool:
    """
    Prüft, ob eine Veranstaltung übernommen werden soll.

    Eine Veranstaltung wird nur übernommen, wenn mindestens
    ein Begriff aus INCLUDE_KEYWORDS im Titel vorkommt.
    """
    normalized_summary = normalize_summary(summary)

    if not normalized_summary:
        print("Filtere Event ohne Titel.")
        return False

    for keyword in INCLUDE_KEYWORDS:
        normalized_keyword = normalize_summary(keyword)

        if normalized_keyword in normalized_summary:
            print(
                f"Übernehme Event wegen Modul '{keyword}': {summary}"
            )
            return True

    print(f"Filtere nicht ausgewähltes Event: {summary}")
    return False


def sanitize_component_text_fields(component) -> None:
    """
    Bereinigt die Textfelder eines Kalendereintrags.
    """
    for field in ["summary", "description", "location"]:
        value = component.get(field)

        if value is not None:
            component[field] = clean_text(str(value))


def fetch_calendar(url: str):
    """
    Lädt und verarbeitet einen ICS-Kalender.
    """
    try:
        print(f"Lade Kalender: {url}")

        response = requests.get(
            url,
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0 Calendar-Merger/1.0"
            },
        )

        response.raise_for_status()

        print(f"HTTP-Status: {response.status_code}")
        print(f"Geladene Bytes: {len(response.content)}")

        calendar = Calendar.from_ical(response.content)

        print("Kalender erfolgreich geladen und verarbeitet.")
        return calendar

    except requests.RequestException as error:
        print(f"Netzwerkfehler beim Laden von {url}: {error}")
        return None

    except Exception as error:
        print(f"Fehler beim Verarbeiten von {url}: {error}")
        return None


def build_merged_calendar() -> Calendar:
    """
    Lädt alle Kalender und führt die ausgewählten Module zusammen.
    """
    print("Baue zusammengeführten Kalender ...")

    merged_calendar = Calendar()

    merged_calendar.add(
        "prodid",
        "-//Merged Uni Plan//DE",
    )
    merged_calendar.add("version", "2.0")
    merged_calendar.add("X-WR-CALNAME", "Uni Stundenplan")
    merged_calendar.add("X-WR-TIMEZONE", "Europe/Berlin")
    merged_calendar.add("CALSCALE", "GREGORIAN")
    merged_calendar.add("METHOD", "PUBLISH")

    seen_events = set()

    total_events = 0
    kept_events = 0
    filtered_events = 0
    duplicate_events = 0

    for url in FEED_URLS:
        source_calendar = fetch_calendar(url)

        if source_calendar is None:
            print(f"Überspringe nicht verfügbaren Kalender: {url}")
            continue

        for component in source_calendar.walk():
            if component.name != "VEVENT":
                continue

            total_events += 1

            summary = str(component.get("summary", ""))
            summary_clean = clean_text(summary)

            print(f"Gefundenes Event: {summary_clean}")

            # Nur angegebene Module übernehmen
            if not should_keep_event(summary_clean):
                filtered_events += 1
                continue

            dtstart_field = component.get("dtstart")
            dtend_field = component.get("dtend")

            if dtstart_field is None:
                print(
                    f"Überspringe Event ohne DTSTART: "
                    f"{summary_clean}"
                )
                continue

            dtstart = dtstart_field.dt
            dtend = (
                dtend_field.dt
                if dtend_field is not None
                else None
            )

            normalized_title = normalize_summary(summary_clean)

            # Schlüssel zum Erkennen doppelter Veranstaltungen
            deduplication_key = (
                dtstart,
                dtend,
                normalized_title,
            )

            if deduplication_key in seen_events:
                duplicate_events += 1

                print(
                    f"Duplikat, überspringe: "
                    f"{summary_clean} @ {dtstart}"
                )
                continue

            seen_events.add(deduplication_key)

            new_component = deepcopy(component)
            sanitize_component_text_fields(new_component)

            merged_calendar.add_component(new_component)
            kept_events += 1

    print("")
    print("Auswertung:")
    print(f"Gefundene Veranstaltungen: {total_events}")
    print(f"Übernommene Veranstaltungen: {kept_events}")
    print(f"Gefilterte Veranstaltungen: {filtered_events}")
    print(f"Entfernte Duplikate: {duplicate_events}")

    return merged_calendar


def save_calendar(
    calendar: Calendar,
    output_path: str,
) -> None:
    """
    Speichert den zusammengeführten Kalender als ICS-Datei.
    """
    try:
        ics_data = calendar.to_ical()

        print("")
        print(f"Ausgabedatei: {output_path}")
        print(f"Dateigröße: {len(ics_data)} Bytes")

        with open(output_path, "wb") as file:
            file.write(ics_data)

        print(
            f"Kalender erfolgreich gespeichert unter: "
            f"{output_path}"
        )

    except OSError as error:
        print(
            f"Fehler beim Speichern von {output_path}: {error}"
        )
        raise


def main() -> None:
    """
    Startpunkt des Programms.
    """
    print("Starte Kalender-Skript ...")
    print(f"Zieldatei: {OUTPUT_FILE}")
    print(f"Anzahl Kalenderquellen: {len(FEED_URLS)}")
    print(f"Anzahl ausgewählter Module: {len(INCLUDE_KEYWORDS)}")
    print("")

    calendar = build_merged_calendar()
    save_calendar(calendar, OUTPUT_FILE)

    print("")
    print("Skript erfolgreich abgeschlossen.")


if __name__ == "__main__":
    main()
