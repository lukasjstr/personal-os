"""OpenAI function/tool definitions — 21 tools for Personal OS."""
from typing import Any

TOOLS: list[dict[str, Any]] = [
    # ─── V3 P03 — Expansion Protection ───────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "list_active_objectives",
            "description": (
                "Liste alle aktiven Objectives mit stale_days (Tage seit letztem Log). "
                "PFLICHT vor jedem create_objective-Aufruf, um Expansionsschutz zu prüfen "
                "(≥4 aktive Objectives → erst Cut anfordern, nicht direkt anlegen). "
                "Auch nutzbar wenn User fragt 'was ist aktuell aktiv', 'meine Ziele', etc."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    # ─── Goal Onboarding Tool ────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "start_goal_onboarding",
            "description": (
                "Startet einen geführten Coaching-Dialog für ein NEUES Ziel. "
                "Der Bot stellt 3-7 adaptive Fragen und erstellt am Ende einen "
                "vollständigen Plan (Objective + KRs + Tasks + Routinen + Kalender). "
                "BEVORZUGE DIESES TOOL wenn der User ein neues Ziel/Vorhaben/Projekt "
                "nennt (z.B. 'gesünder leben', 'Spanisch lernen', 'Business aufbauen'). "
                "NICHT nutzen bei: einfachen Task-Anfragen, bestehende Ziele aktualisieren, "
                "Log-Einträge (Workout, Wasser, Mood)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "goal_text": {
                        "type": "string",
                        "description": "Das Ziel des Nutzers in seinen eigenen Worten",
                    },
                },
                "required": ["goal_text"],
            },
        },
    },
    # ─── OKR Tools ────────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "create_objective",
            "description": "Erstellt ein neues Ziel (Objective) im OKR-System. Nutze create_objective NUR wenn start_goal_onboarding nicht passt (z.B. wenn der User explizit kein Coaching will oder ein Objective manuell anlegen möchte).",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Titel des Ziels"},
                    "description": {"type": "string", "description": "Optionale Beschreibung"},
                    "category": {
                        "type": "string",
                        "enum": ["health", "business", "personal", "fitness", "finance", "learning"],
                        "description": "Kategorie des Ziels",
                    },
                    "target_date": {"type": "string", "description": "Zieldatum YYYY-MM-DD (optional)"},
                },
                "required": ["title", "category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_key_result",
            "description": "Erstellt ein messbares Key Result zu einem Objective. Beispiel: '3L Wasser täglich' oder '4x Training pro Woche'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "objective_id": {"type": "integer", "description": "ID des übergeordneten Objectives"},
                    "title": {"type": "string", "description": "Titel des Key Results"},
                    "metric_type": {
                        "type": "string",
                        "enum": ["percentage", "number", "boolean", "streak", "checklist"],
                        "description": "Art der Metrik",
                    },
                    "target_value": {"type": "number", "description": "Zielwert (z.B. 3 für 3L Wasser)"},
                    "unit": {"type": "string", "description": "Einheit (z.B. 'Liter', 'kg', 'Posts')"},
                    "frequency": {
                        "type": "string",
                        "enum": ["daily", "weekly", "monthly", "once"],
                        "description": "Häufigkeit der Messung",
                    },
                    "target_date": {"type": "string", "description": "Zieldatum YYYY-MM-DD (optional)"},
                },
                "required": ["objective_id", "title", "metric_type", "frequency"],
            },
        },
    },
    # ─── Task Tools ───────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Erstellt eine konkrete Aufgabe (Task). Für Einkaufsitems category='shopping' setzen. Wenn möglich immer objective_id setzen um Task mit einem Ziel zu verknüpfen.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Titel der Aufgabe"},
                    "description": {"type": "string", "description": "Optionale Beschreibung"},
                    "key_result_id": {"type": "integer", "description": "Zugehöriges Key Result (optional)"},
                    "objective_id": {"type": "integer", "description": "Direkt zugeordnetes Objective (optional, aber bevorzugt wenn möglich)"},
                    "parent_task_id": {"type": "integer", "description": "Übergeordnete Task ID für Sub-Tasks (optional)"},
                    "blocked_by_task_id": {"type": "integer", "description": "ID der Task die diese blockiert (optional)"},
                    "priority": {
                        "type": "integer",
                        "description": "Priorität: 1=höchste, 5=niedrigste",
                        "minimum": 1,
                        "maximum": 5,
                    },
                    "category": {
                        "type": "string",
                        "enum": ["general", "shopping", "errand", "work", "personal"],
                        "description": "Kategorie. 'shopping' für Einkaufsitems!",
                    },
                    "due_date": {"type": "string", "description": "Fälligkeitsdatum YYYY-MM-DD (optional)"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_task",
            "description": "Markiert eine Aufgabe als erledigt. Nutze wenn User 'fertig', 'done', 'erledigt' sagt.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "ID der Aufgabe"},
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_task_status",
            "description": "Aktualisiert den Status einer Aufgabe.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "ID der Aufgabe"},
                    "status": {
                        "type": "string",
                        "enum": ["todo", "in_progress", "done", "cancelled"],
                        "description": "Neuer Status",
                    },
                },
                "required": ["task_id", "status"],
            },
        },
    },
    # ─── Shopping Tools ───────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "get_shopping_list",
            "description": "Zeigt die aktuelle Einkaufsliste mit allen offenen Items.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_shopping",
            "description": "Markiert Einkaufsitems als erledigt. Ohne item_ids werden ALLE Items abgehakt.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Liste der Task-IDs. Leer = alle Shopping-Items abhaken.",
                    },
                },
                "required": [],
            },
        },
    },
    # ─── Logging Tools ────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "log_workout",
            "description": "Loggt ein Workout / eine Trainingseinheit. Nutze für Sport- und Fitness-Inputs. Wenn User einen Split nennt (z.B. 'Push Day'), split_id aus dem Kontext setzen.",
            "parameters": {
                "type": "object",
                "properties": {
                    "exercise": {"type": "string", "description": "Übungsname (z.B. 'Bankdrücken', 'Kniebeugen')"},
                    "weight": {"type": "number", "description": "Gewicht in kg (optional)"},
                    "reps": {"type": "integer", "description": "Wiederholungen pro Satz (optional)"},
                    "sets": {"type": "integer", "description": "Anzahl Sätze (optional)"},
                    "duration_minutes": {"type": "integer", "description": "Dauer in Minuten (optional)"},
                    "notes": {"type": "string", "description": "Zusätzliche Notizen (optional)"},
                    "key_result_id": {"type": "integer", "description": "Zugehöriges Key Result (optional)"},
                    "split_id": {"type": "integer", "description": "ID des Fitness-Splits (optional, wenn User Split nennt)"},
                },
                "required": ["exercise"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_water",
            "description": "Loggt die Wasseraufnahme in Litern.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount_liters": {"type": "number", "description": "Menge in Litern (z.B. 0.5, 1.5)"},
                },
                "required": ["amount_liters"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_mood",
            "description": "Loggt die Stimmung / Tages-Rating des Users.",
            "parameters": {
                "type": "object",
                "properties": {
                    "score": {"type": "integer", "description": "Rating von 1-10", "minimum": 1, "maximum": 10},
                    "notes": {"type": "string", "description": "Optionale Notiz zur Stimmung"},
                },
                "required": ["score"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_progress",
            "description": "Loggt Fortschritt für ein Key Result. Aktualisiert current_value.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key_result_id": {"type": "integer", "description": "ID des Key Results"},
                    "value": {"type": "number", "description": "Fortschrittswert"},
                    "increment": {
                        "type": "boolean",
                        "description": "True = Wert addieren, False = Wert ersetzen. Default: True.",
                    },
                    "notes": {"type": "string", "description": "Optionale Notiz"},
                },
                "required": ["key_result_id", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_food",
            "description": "Loggt eine Mahlzeit oder Nahrungsaufnahme.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "Beschreibung der Mahlzeit"},
                    "calories": {"type": "integer", "description": "Kalorien (optional)"},
                    "meal_type": {
                        "type": "string",
                        "enum": ["breakfast", "lunch", "dinner", "snack"],
                        "description": "Mahlzeitentyp (optional)",
                    },
                    "notes": {"type": "string", "description": "Zusätzliche Notizen (optional)"},
                },
                "required": ["description"],
            },
        },
    },
    # ─── Routine Tools ────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "create_routine",
            "description": "Erstellt eine neue wiederkehrende Routine. Erkenne Tageszeit-Referenzen: 'morgens/Morgen' → morning, 'mittags/Mittag' → midday, 'abends/Abend' → evening, sonst → anytime.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Name der Routine"},
                    "frequency_human": {"type": "string", "description": "Lesbare Beschreibung (z.B. 'Täglich', 'Jeden Dienstag', '3x pro Woche')"},
                    "schedule_cron": {"type": "string", "description": "Cron-Ausdruck optional (z.B. '0 9 * * 2')"},
                    "linked_key_result_id": {"type": "integer", "description": "Zugehöriges Key Result (optional)"},
                    "time_of_day": {
                        "type": "string",
                        "enum": ["morning", "midday", "evening", "anytime"],
                        "description": "Tageszeit: morning=morgens, midday=mittags, evening=abends, anytime=jederzeit",
                    },
                },
                "required": ["title", "frequency_human"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_routine",
            "description": "Markiert eine Routine als heute erledigt.",
            "parameters": {
                "type": "object",
                "properties": {
                    "routine_id": {"type": "integer", "description": "ID der Routine"},
                    "notes": {"type": "string", "description": "Optionale Notiz"},
                },
                "required": ["routine_id"],
            },
        },
    },
    # ─── Calendar Tool ────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "create_calendar_event",
            "description": "Erstellt einen Kalender-Eintrag für einen Termin.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Titel des Events"},
                    "start_time": {"type": "string", "description": "Startzeit im Format YYYY-MM-DD HH:MM"},
                    "end_time": {"type": "string", "description": "Endzeit im Format YYYY-MM-DD HH:MM (optional)"},
                    "all_day": {"type": "boolean", "description": "Ganztägiges Event (optional)"},
                    "event_type": {
                        "type": "string",
                        "enum": ["training", "meeting", "routine", "deadline", "reminder", "errand"],
                    },
                    "description": {"type": "string", "description": "Optionale Beschreibung"},
                    "linked_task_id": {"type": "integer", "description": "Zugehöriger Task (optional)"},
                },
                "required": ["title", "start_time"],
            },
        },
    },
    # ─── Contact Tool ─────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "create_contact",
            "description": (
                "Legt eine Person als Kontakt an. Nutze wenn eine Person namentlich erwähnt wird "
                "im Kontext von: Geburtstag, Party, Treffen, Dinner, Verabredung, Meeting (privat). "
                "Prüft automatisch auf Duplikate. Setzt birthday wenn ein Geburtstag erwähnt wird."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Vollständiger Name der Person"},
                    "relationship_type": {
                        "type": "string",
                        "enum": ["friend", "family", "colleague", "mentor", "partner"],
                        "description": "Art der Beziehung (Standard: friend)",
                    },
                    "birthday": {
                        "type": "string",
                        "description": "Geburtstag im Format YYYY-MM-DD (falls bekannt)",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Kurze Notiz z.B. 'Geburtstag 21. März', 'Treffen im Steakhouse'",
                    },
                },
                "required": ["name"],
            },
        },
    },
    # ─── Document Store Tool ──────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "store_document_entry",
            "description": "Speichert einen Eintrag in ein UserDocument (Journal, Dankbarkeit, etc.) und aktualisiert das zugehörige KR. Nutze für: Journal-Einträge → document='Tagebuch', Dankbarkeits-Einträge → document='Dankbarkeit'. Aktualisiert automatisch das passende KR.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document": {
                        "type": "string",
                        "description": "Name des Dokuments: 'Tagebuch' für Journal, 'Dankbarkeit' für Gratitude. Kann auch ein anderer Name sein.",
                    },
                    "content": {"type": "string", "description": "Der zu speichernde Text/Eintrag"},
                },
                "required": ["document", "content"],
            },
        },
    },
    # ─── Brain Dump Tool ──────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "store_brain_dump",
            "description": "Speichert einen unstrukturierten Gedanken / Brain Dump für spätere Einordnung. Nutze wenn Input nicht klar in eine Kategorie passt.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Der Gedanke / die Idee"},
                    "linked_objective_id": {"type": "integer", "description": "Passendes Objective (optional)"},
                },
                "required": ["content"],
            },
        },
    },
    # ─── Query Tools ──────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "get_todays_priorities",
            "description": "Gibt die Top-Prioritäten für heute zurück (offene Tasks, Routinen, Kalender).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_active_objectives",
            "description": "Gibt alle aktiven Objectives mit Key Results und Fortschritt zurück.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_progress_report",
            "description": "Gibt einen detaillierten Fortschrittsbericht für ein spezifisches Objective zurück.",
            "parameters": {
                "type": "object",
                "properties": {
                    "objective_id": {"type": "integer", "description": "ID des Objectives"},
                },
                "required": ["objective_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_logs",
            "description": "Sucht in den Log-Einträgen des Users. Nutze wenn User nach Verlauf fragt.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Suchbegriff (z.B. 'Bankdrücken')"},
                    "log_type": {
                        "type": "string",
                        "enum": ["workout", "water", "food", "mood", "progress", "note", "general"],
                        "description": "Log-Typ Filter (optional)",
                    },
                    "days_back": {"type": "integer", "description": "Wie viele Tage zurücksuchen (default: 30)"},
                },
                "required": ["query"],
            },
        },
    },
    # ─── Objective-Task Linking ───────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "suggest_tasks_for_objective",
            "description": "Erstellt 3-5 konkrete Tasks für ein Objective in einem Schritt. Nutze direkt nach create_objective oder wenn der User ein Objective hat und Tasks braucht.",
            "parameters": {
                "type": "object",
                "properties": {
                    "objective_id": {"type": "integer", "description": "ID des Objectives"},
                    "tasks": {
                        "type": "array",
                        "description": "Liste der zu erstellenden Tasks",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string", "description": "Titel der Task"},
                                "description": {"type": "string", "description": "Optionale Beschreibung"},
                                "priority": {
                                    "type": "integer",
                                    "description": "Priorität 1-5",
                                    "minimum": 1,
                                    "maximum": 5,
                                },
                            },
                            "required": ["title"],
                        },
                        "minItems": 1,
                        "maxItems": 8,
                    },
                },
                "required": ["objective_id", "tasks"],
            },
        },
    },
    # ─── Day Planning Tool ────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "plan_my_day",
            "description": "Erstellt einen vollständigen Tagesplan mit konkreten Zeitblöcken. Lädt offene Tasks (nach Priorität), heutige Routinen und bestehende Kalender-Events, erstellt daraus einen strukturierten Zeitplan und speichert jeden Block als Kalender-Event. Nutze dieses Tool wenn der User 'Plan meinen Tag', 'Tagesplan', 'Was soll ich heute machen' oder ähnliches sagt.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Datum für den Plan (YYYY-MM-DD, default: heute)"},
                    "work_start": {"type": "string", "description": "Arbeitsbeginn (HH:MM, default: 08:00)"},
                    "work_end": {"type": "string", "description": "Arbeitsende (HH:MM, default: 20:00)"},
                },
                "required": [],
            },
        },
    },
    # ─── Fitness Split Tools ──────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "create_fitness_split",
            "description": "Erstellt einen neuen Fitness-Split (z.B. Push Day, Pull Day, Leg Day) mit Übungsliste. Nutze wenn User einen Trainingsplan oder Split definiert.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name des Splits (z.B. 'Push Day', 'Pull Day', 'Leg Day', 'Oberkörper')"},
                    "exercises": {
                        "type": "array",
                        "description": "Liste der Übungen im Split",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "description": "Übungsname"},
                                "sets": {"type": "integer", "description": "Anzahl Sätze (optional)"},
                                "reps": {"type": "string", "description": "Wiederholungen, z.B. '8-10' oder '5' (optional)"},
                                "target_weight": {"type": "number", "description": "Zielgewicht in kg (optional)"},
                            },
                            "required": ["name"],
                        },
                        "minItems": 1,
                    },
                    "day_of_week": {
                        "type": "integer",
                        "description": "Wochentag: 0=Montag, 1=Dienstag, ..., 6=Sonntag (optional)",
                        "minimum": 0,
                        "maximum": 6,
                    },
                    "order_in_rotation": {
                        "type": "integer",
                        "description": "Reihenfolge in der Split-Rotation (1, 2, 3, ...). Wichtig für Push/Pull/Leg-Planung.",
                    },
                },
                "required": ["name", "exercises"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_fitness_plan",
            "description": "Zeigt alle Fitness-Splits und empfiehlt den nächsten Split basierend auf letzten Workouts. Nutze wenn User fragt 'Was trainiere ich heute?', 'Nächster Split?' oder 'Zeig meinen Trainingsplan'.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    # ─── Shopping Default Tools ───────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "create_shopping_default",
            "description": "Legt ein Standard-Einkaufsitem an, das immer auf der Einkaufsliste erscheint. Nutze wenn User sagt 'X ist immer auf meiner Liste' oder wenn ein Item 3x oder mehr gekauft wurde.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Name des Standard-Items (z.B. 'Milch', 'Brot')"},
                    "category": {"type": "string", "description": "Kategorie (z.B. 'Milchprodukte', 'Gemüse', 'Fleisch'). Optional."},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "load_shopping_defaults",
            "description": "Lädt alle aktiven Standard-Einkaufsitems als Tasks in die Einkaufsliste. Nutze wenn User 'Standard-Liste laden', 'Einkaufsliste auffüllen' oder 'normale Items hinzufügen' sagt.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    # ─── Finance Tools ────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "log_expense",
            "description": "Loggt eine Ausgabe. Nutze wenn User etwas kauft, bezahlt oder Geld ausgibt: 'Kaffee 4€', 'Gym-Abo 30€/Monat', 'Supermarkt 45€', 'Tanken 60€'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "description": "Betrag in Euro (positiv)"},
                    "category": {
                        "type": "string",
                        "enum": ["essen", "fitness", "bildung", "abonnements", "transport", "unterhaltung", "shopping", "gesundheit", "wohnen", "sonstiges"],
                        "description": "Kategorie der Ausgabe",
                    },
                    "description": {"type": "string", "description": "Kurze Beschreibung (z.B. 'Kaffee beim Bäcker', 'Gym-Abo Juli')"},
                    "date": {"type": "string", "description": "Datum YYYY-MM-DD (optional, default: heute)"},
                    "is_recurring": {"type": "boolean", "description": "True bei monatlichen Abos/Fixkosten"},
                },
                "required": ["amount", "category", "description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_income",
            "description": "Loggt eine Einnahme. Nutze wenn User Geld bekommt: 'Gehalt 2800€', 'Freiberuflich 500€', 'Rückzahlung 50€'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "description": "Betrag in Euro (positiv)"},
                    "source": {"type": "string", "description": "Quelle (z.B. 'Gehalt', 'Freelance', 'Erstattung')"},
                    "date": {"type": "string", "description": "Datum YYYY-MM-DD (optional, default: heute)"},
                },
                "required": ["amount", "source"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_financial_summary",
            "description": "Zeigt die finanzielle Übersicht: Einnahmen, Ausgaben, Sparquote, Budget-Status pro Kategorie. Nutze bei 'Finanzübersicht', 'Wie viel habe ich ausgegeben', 'Budget Status', 'Sparquote'.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_monthly_budget",
            "description": "Setzt ein monatliches Budget für eine Ausgaben-Kategorie. Nutze bei 'Ich will max X€ für Y ausgeben' oder 'Budget für Essen 300€'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["essen", "fitness", "bildung", "abonnements", "transport", "unterhaltung", "shopping", "gesundheit", "wohnen", "sonstiges"],
                    },
                    "monthly_limit": {"type": "number", "description": "Monatliches Budget in Euro"},
                },
                "required": ["category", "monthly_limit"],
            },
        },
    },
    # ─── Health Tracking Tools ────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "log_sleep",
            "description": "Loggt Schlafstunden. Nutze wenn User über Schlaf spricht: '7h geschlafen', 'schlecht geschlafen 5 Stunden', 'war um 23 Uhr im Bett, um 6 wach'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "hours": {"type": "number", "description": "Schlafstunden (z.B. 7.5)"},
                    "quality": {"type": "integer", "description": "Schlafqualität 1-10 (optional)", "minimum": 1, "maximum": 10},
                    "date": {"type": "string", "description": "Datum YYYY-MM-DD (default: heute/gestern je nach Kontext)"},
                },
                "required": ["hours"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_steps",
            "description": "Loggt tägliche Schritte. Nutze wenn User Schritte nennt: '9200 Schritte', 'bin 8km gelaufen', 'Schrittziel erreicht'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "description": "Anzahl Schritte"},
                    "date": {"type": "string", "description": "Datum YYYY-MM-DD (default: heute)"},
                },
                "required": ["count"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_hrv",
            "description": "Loggt HRV-Wert (Heart Rate Variability). Nutze wenn User HRV oder Erholungswert nennt.",
            "parameters": {
                "type": "object",
                "properties": {
                    "score": {"type": "integer", "description": "HRV in ms"},
                    "date": {"type": "string", "description": "Datum YYYY-MM-DD (default: heute)"},
                },
                "required": ["score"],
            },
        },
    },
    # ─── Settings Tool ────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "update_user_settings",
            "description": "Ändert User-Einstellungen/Toggles. Nutze wenn User Einstellungen ändern will.",
            "parameters": {
                "type": "object",
                "properties": {
                    "setting_key": {
                        "type": "string",
                        "enum": [
                            "priorities_enabled",
                            "review_enabled",
                            "proactive_enabled",
                            "reflection_enabled",
                            "morning_brief_time",
                            "evening_review_time",
                        ],
                        "description": "Schlüssel der Einstellung",
                    },
                    "setting_value": {
                        "type": "string",
                        "description": "Neuer Wert. Für Toggles: 'true' oder 'false'. Für Zeiten: 'HH:MM'.",
                    },
                },
                "required": ["setting_key", "setting_value"],
            },
        },
    },
]
