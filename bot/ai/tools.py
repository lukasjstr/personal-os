"""OpenAI function/tool definitions — 21 tools for Personal OS."""
from typing import Any

TOOLS: list[dict[str, Any]] = [
    # ─── OKR Tools ────────────────────────────────────────────────────────────
    {
        "type": "function",
        "function": {
            "name": "create_objective",
            "description": "Erstellt ein neues Ziel (Objective) im OKR-System. Nutze dies wenn der User ein neues großes Ziel nennt wie 'Ich will gesünder leben' oder 'Business aufbauen'. Nach der Erstellung: suggest_tasks_for_objective aufrufen um 3-5 konkrete Tasks automatisch zu erstellen.",
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
            "description": "Erstellt eine neue wiederkehrende Routine.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Name der Routine"},
                    "frequency_human": {"type": "string", "description": "Lesbare Beschreibung (z.B. 'Täglich', 'Jeden Dienstag', '3x pro Woche')"},
                    "schedule_cron": {"type": "string", "description": "Cron-Ausdruck optional (z.B. '0 9 * * 2')"},
                    "linked_key_result_id": {"type": "integer", "description": "Zugehöriges Key Result (optional)"},
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
