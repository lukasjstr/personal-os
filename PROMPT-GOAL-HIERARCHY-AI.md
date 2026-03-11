# PROMPT: Goal Hierarchy Tree + AI Synergy/Dependency Analysis

## Vision
Goals (Objectives) and Tasks should be organized in a **visual tree**. The AI should analyze all goals,
detect overlaps, recognize which goals are subsets of others, find synergies between tasks across goals,
and suggest a cleaner structure. The user can accept or reject AI suggestions.

Example problem: "Ein besserer Mensch werden" and "Mich intellektuell, persönlich und sportlich weiterentwickeln"
— the AI should recognize the second is a sub-goal of the first and suggest making it a child objective.

## Git config (always use this)
user.name=lukasjstr, user.email=lukasjstr@gmail.com

---

## 1. Backend — AI Goal Analysis endpoint

### File: `bot/api/routes.py`
Add a new endpoint `GET /api/objectives/ai-analysis`:

```python
@router.get("/objectives/ai-analysis")
async def analyze_objectives(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    """AI analyzes all objectives + tasks, returns structure suggestions."""
    import json
    from bot.ai.client import get_ai_client

    # Load all objectives with sub-objectives and key results
    result = await session.execute(
        select(Objective)
        .where(Objective.user_id == user.id, Objective.status == "active")
        .options(selectinload(Objective.key_results), selectinload(Objective.sub_objectives))
    )
    objectives = result.scalars().all()

    # Load open tasks
    tasks_result = await session.execute(
        select(Task).where(Task.user_id == user.id, Task.status == "open").limit(100)
    )
    tasks = tasks_result.scalars().all()

    # Build compact context for AI
    obj_list = []
    for o in objectives:
        obj_list.append({
            "id": o.id,
            "title": o.title,
            "description": o.description,
            "category": o.category,
            "parent_objective_id": o.parent_objective_id,
            "key_results": [kr.title for kr in o.key_results],
        })

    task_list = [{"id": t.id, "title": t.title, "objective_id": t.objective_id} for t in tasks]

    prompt = f"""Du bist ein strategischer Life-Coach. Analysiere diese Ziele und Aufgaben eines Nutzers und gib strukturierte Empfehlungen zurück.

## Aktive Ziele:
{json.dumps(obj_list, ensure_ascii=False, indent=2)}

## Offene Aufgaben (Auswahl):
{json.dumps(task_list[:50], ensure_ascii=False, indent=2)}

## Deine Aufgabe:
Analysiere die Ziele und erkenne:
1. **Hierarchie**: Welche Ziele sind Unterziele anderer? (z.B. "sportlich weiterentwickeln" ist Teil von "besserer Mensch werden")
2. **Synergien**: Welche Tasks/Ziele ergänzen sich gegenseitig und könnten kombiniert werden?
3. **Überlappungen**: Welche Ziele sind zu ähnlich und könnten zusammengeführt werden?
4. **Fehlende Verbindungen**: Welche Ziele hängen logisch zusammen, sind aber nicht verknüpft?

Antworte NUR mit einem JSON-Objekt in diesem exakten Format:
{{
  "parent_suggestions": [
    {{
      "child_objective_id": <int>,
      "child_title": "<string>",
      "suggested_parent_id": <int>,
      "parent_title": "<string>",
      "reason": "<kurze Begründung auf Deutsch>"
    }}
  ],
  "synergies": [
    {{
      "objective_ids": [<int>, <int>],
      "titles": ["<string>", "<string>"],
      "synergy": "<was haben sie gemeinsam, auf Deutsch>"
    }}
  ],
  "overlaps": [
    {{
      "objective_ids": [<int>, <int>],
      "titles": ["<string>", "<string>"],
      "overlap": "<was überschneidet sich, auf Deutsch>",
      "suggestion": "<was tun, auf Deutsch>"
    }}
  ],
  "missing_links": [
    {{
      "objective_ids": [<int>, <int>],
      "titles": ["<string>", "<string>"],
      "connection": "<warum sie zusammenhängen, auf Deutsch>"
    }}
  ],
  "summary": "<1-2 Sätze Gesamtbewertung der Zielstruktur auf Deutsch>"
}}"""

    try:
        client = get_ai_client()
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        analysis = json.loads(response.choices[0].message.content)
    except Exception as e:
        analysis = {
            "parent_suggestions": [],
            "synergies": [],
            "overlaps": [],
            "missing_links": [],
            "summary": f"Analyse konnte nicht durchgeführt werden: {str(e)}",
        }

    return analysis
```

Also add endpoint to **apply a parent suggestion** (set parent_objective_id):
```python
class SetParentBody(BaseModel):
    parent_objective_id: Optional[int] = None  # None = remove parent

@router.post("/objectives/{objective_id}/set-parent")
async def set_objective_parent(
    objective_id: int,
    body: SetParentBody,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    obj = await session.get(Objective, objective_id)
    if not obj or obj.user_id != user.id:
        raise HTTPException(404)
    # Prevent circular references
    if body.parent_objective_id and body.parent_objective_id == objective_id:
        raise HTTPException(400, "Cannot be its own parent")
    obj.parent_objective_id = body.parent_objective_id
    await session.flush()
    return {"ok": True, "objective_id": objective_id, "parent_objective_id": obj.parent_objective_id}
```

---

## 2. Frontend — Objectives page: Tree View + AI Analysis

### File: `dashboard/src/app/objectives/page.tsx`
This is a **significant UI overhaul**. Requirements:

### 2a. Tree View (default view)
- Add a toggle: "Baum 🌳" | "Liste 📋" (default: Baum)
- In tree view, render objectives as a hierarchical tree:
  - Root objectives (no parent) shown at top level
  - Sub-objectives indented beneath their parent with a connecting line (left border)
  - Each objective shows: emoji (from category), title, status badge, progress bar (avg of KR progress)
  - Expand/collapse button to show/hide sub-objectives and key results
  - "Unterziel hinzufügen" button on each objective card

### 2b. Create Objective Modal — add parent selector
In the existing create/edit modal, add:
- "Übergeordnetes Ziel (optional)" dropdown
- Shows all active objectives (exclude self when editing)
- Nullable — user can clear it

### 2c. AI Analysis Panel
Add a collapsible panel below the objectives tree: "🤖 KI-Zielanalyse"
- Button: "Analyse starten" (calls GET /api/objectives/ai-analysis, shows loading spinner)
- Once loaded, show sections:
  
  **Hierarchie-Vorschläge** (if parent_suggestions.length > 0):
  - Each suggestion: "[child_title] → könnte Unterziel von [parent_title] sein — [reason]"
  - Two buttons: "✓ Übernehmen" (calls POST /api/objectives/{id}/set-parent) | "✗ Ignorieren"
  - On accept: mutate the objectives list, remove the suggestion from the panel
  
  **Synergien** (if synergies.length > 0):
  - Each: shows the two objective titles and the synergy text
  - Info only, no action needed
  
  **Überlappungen** (if overlaps.length > 0):
  - Each: shows overlap and suggestion
  - Info card with a link to open each objective
  
  **Gesamtbewertung**:
  - The `summary` text shown prominently

### 2d. API client additions in `dashboard/src/lib/api.ts`:
```typescript
analyzeObjectives: () => apiFetch<ObjectiveAnalysis>("/api/objectives/ai-analysis"),
setObjectiveParent: (id: number, parentId: number | null) =>
  apiPost<{ ok: boolean }>(`/api/objectives/${id}/set-parent`, { parent_objective_id: parentId }),
```

Add type:
```typescript
export interface ObjectiveAnalysis {
  parent_suggestions: Array<{
    child_objective_id: number;
    child_title: string;
    suggested_parent_id: number;
    parent_title: string;
    reason: string;
  }>;
  synergies: Array<{
    objective_ids: number[];
    titles: string[];
    synergy: string;
  }>;
  overlaps: Array<{
    objective_ids: number[];
    titles: string[];
    overlap: string;
    suggestion: string;
  }>;
  missing_links: Array<{
    objective_ids: number[];
    titles: string[];
    connection: string;
  }>;
  summary: string;
}
```

---

## 3. Frontend — Tasks: show subtask hierarchy

### File: `dashboard/src/app/tasks/page.tsx`
In the task list, for tasks that have sub_tasks (check if `task.sub_task_count > 0` or if sub_tasks array exists):
- Show a small "▶ N Unteraufgaben" toggle below the task title
- Expand to show sub-tasks indented with left border
- Sub-tasks should also be completable inline

This is lower priority — do it if time allows. The objectives hierarchy is the main goal.

---

## 4. Deploy

After all changes:
1. `python3 -m py_compile bot/api/routes.py bot/database/models.py` — must pass
2. SSH: `ssh root@95.111.252.176`
3. `cd /opt/personal-os && git pull` — or scp files if git pull fails (no git credentials on server)
4. Restart bot: `systemctl restart personal-os`
5. Build + restart dashboard: `cd dashboard && npm run build && systemctl restart personal-os-dashboard`
6. Local commit: `git add -A && git commit -m "feat(objectives): hierarchy tree + AI goal analysis (synergies, parent suggestions)" && git push`

## Important
- Keep existing functionality intact — don't break the current objectives CRUD
- The AI analysis is async/on-demand — no background jobs needed
- Python compile check is mandatory before deploy
- If the OpenAI client import pattern is unclear, check `bot/jobs/daily_suggestions.py` for the correct import pattern

## Completion signal
When done: `openclaw system event --text "Done: Goal hierarchy tree + AI analysis shipped" --mode now`
