"""OpenAI function/tool definitions for the Personal OS COO."""
from typing import Any

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "create_objective",
            "description": "Erstellt ein neues Ziel (Objective) im OKR-System. Nutze dies wenn der User ein neues großes Ziel nennt.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Titel des Ziels"},
                    "description": {"type": "string", "description": "Optionale Beschreibung"},
                    "category": {
                        "type": "string",
                        "enum": ["health", "business", "personal", "fitness", "finance"],
                        "description": "Kategorie des Ziels",
                    },
                    "target_date": {"type": "string", "description": "Zieldatum im Format YYYY-MM-DD (optional)"},
                },
                "required": ["title", "category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_key_result",
            "description": "Erstellt ein messbares Key Result zu einem Objective.",
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
                "required": ["objective_id", "title", "metric_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Erstellt eine konkrete Aufgabe (Task). Nutze dies für spezifische To-Dos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Titel der Aufgabe"},
                    "description": {"type": "string", "description": "Optionale Beschreibung"},
                    "key_result_id": {"type": "integer", "description": "Zugehöriges Key Result (optional)"},
                    "priority": {"type": "integer", "description": "Priorität 1-5 (5 = höchste)", "minimum": 1, "maximum": 5},
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
            "description": "Markiert eine Aufgabe als erledigt.",
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
    {
        "type": "function",
        "function": {
            "name": "log_workout",
            "description": "Loggt ein Workout / eine Trainingseinheit. Nutze dies für alle Sport- und Fitness-Inputs.",
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
                    "amount_liters": {"type": "number", "description": "Menge in Litern (z.B. 0.5 für 500ml, 1.5 für 1.5L)"},
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
            "description": "Loggt Fortschritt für ein Key Result.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key_result_id": {"type": "integer", "description": "ID des Key Results"},
                    "value": {"type": "number", "description": "Fortschrittswert"},
                    "notes": {"type": "string", "description": "Optionale Notiz"},
                },
                "required": ["key_result_id", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_routine",
            "description": "Erstellt eine neue wiederkehrende Routine.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Name der Routine"},
                    "schedule_cron": {"type": "string", "description": "Cron-Ausdruck (z.B. '0 9 * * *' für täglich 9 Uhr)"},
                    "frequency_human": {"type": "string", "description": "Lesbare Beschreibung (z.B. 'Täglich', 'Jeden Dienstag')"},
                    "linked_key_result_id": {"type": "integer", "description": "Zugehöriges Key Result (optional)"},
                },
                "required": ["title", "schedule_cron", "frequency_human"],
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
    {
        "type": "function",
        "function": {
            "name": "create_calendar_event",
            "description": "Erstellt einen Kalender-Eintrag.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Titel des Events"},
                    "start_time": {"type": "string", "description": "Startzeit im Format YYYY-MM-DD HH:MM"},
                    "end_time": {"type": "string", "description": "Endzeit im Format YYYY-MM-DD HH:MM (optional)"},
                    "event_type": {
                        "type": "string",
                        "enum": ["training", "meeting", "routine", "deadline", "reminder"],
                    },
                    "description": {"type": "string", "description": "Optionale Beschreibung"},
                    "linked_task_id": {"type": "integer", "description": "Zugehöriger Task (optional)"},
                },
                "required": ["title", "start_time", "event_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "store_brain_dump",
            "description": "Speichert einen unstrukturierten Gedanken / Brain Dump für spätere Einordnung.",
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
            "description": "Gibt einen Fortschrittsbericht für ein spezifisches Objective zurück.",
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
            "description": "Sucht in den Log-Einträgen des Users.",
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
]
