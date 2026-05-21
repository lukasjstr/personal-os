# FIX: Objectives Tree View + Goal Hierarchy

## Git config (ALWAYS use this for commits)
user.name=lukasjstr  
user.email=lukasjstr@gmail.com

## Context
The objectives page was just refactored to add a tree view but it's broken in two ways:
1. The "life area" logic splits objectives into two groups — objectives WITHOUT key results/tasks are rendered as pill badges (lifeAreas), objectives WITH KRs/tasks go into the tree. This means the tree view never shows "parent" objectives that don't have KRs yet.
2. The goal "Mich intellektuell, persönlich und sportlich weiterentwickeln" (id=23) should be a sub-goal of "Ein besserer Mensch werden" (id=22) — this needs to be set in the database.

## Fix 1 — Set parent in DB via API call
SSH into server and run:
```bash
ssh root@95.111.252.176 "curl -s -X POST http://localhost:8000/api/objectives/23/set-parent \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer $(PGPASSWORD=personalos2026 psql -h localhost -U pos_user -d personal_os -c \"SELECT api_token FROM users LIMIT 1;\" -t | tr -d ' \n')' \
  -d '{\"parent_objective_id\": 22}'"
```

If that doesn't work (token not known), directly update the DB:
```bash
ssh root@95.111.252.176 "PGPASSWORD=personalos2026 psql -h localhost -U pos_user -d personal_os -c \"UPDATE objectives SET parent_objective_id = 22 WHERE id = 23;\""
```

## Fix 2 — Refactor ObjectivesPage: Remove the life area split, use a single unified tree

### File: `dashboard/src/app/objectives/page.tsx`

**Problem:** The current code has this logic:
```ts
const lifeAreas = all.filter((o) => o.key_results.length === 0 && o.tasks.length === 0 && o.status === "active");
const realObjectives = all.filter((o) => o.key_results.length > 0 || o.tasks.length > 0);
const filtered = filter === "all" ? realObjectives : realObjectives.filter((o) => o.status === filter);
const { roots, childMap } = buildTree(filtered);
```

This is wrong — it excludes "life area" objectives from the tree entirely.

**Solution:** Unify everything into a single tree. Remove the life area split:

```ts
// Replace the above with:
const filtered = filter === "all" ? all : all.filter((o) => o.status === filter);
const { roots, childMap } = buildTree(filtered);
```

Remove the "Life Areas" section entirely from the JSX (the separate pill display of lifeAreas).

An objective without KRs or tasks should just render as a "container objective" in the tree — same card but with a "🌳 Life Area" or "📂" badge instead of a progress bar.

### Update ObjectiveCard to handle no-KR objectives gracefully:

When `obj.key_results.length === 0 && obj.tasks.length === 0`, instead of rendering as a pill, render a simplified card:
- Show the title, category badge
- Instead of a progress bar, show: `N Unterziele` (count of children from childMap)
- "Noch keine Key Results — hinzufügen" link

### Update buildTree / ObjectiveTreeNode — currently the childMap is built from `filtered`, but children might be in `filtered` even if their parent is not. Make sure all objectives in the full `all` array can appear in the tree, not just those in `filtered`.

Actually simpler: always build the tree from ALL objectives, then filter which roots to show based on status filter:

```ts
// Build tree from all objectives always
const { roots: allRoots, childMap } = buildTree(all);
// Then filter roots based on current filter, but children are always included
const visibleRoots = filter === "all" 
  ? allRoots 
  : allRoots.filter((o) => o.status === filter);
```

## Fix 3 — Deploy

1. Apply DB fix (Fix 1 above)
2. Edit `dashboard/src/app/objectives/page.tsx` (Fix 2 above)
3. Build locally: `cd dashboard && npm run build` — must compile cleanly
4. Copy to server: `scp dashboard/src/app/objectives/page.tsx root@95.111.252.176:/opt/personal-os/dashboard/src/app/objectives/page.tsx`
5. Build on server: `ssh root@95.111.252.176 "cd /opt/personal-os/dashboard && npm run build && systemctl restart personal-os-dashboard"`
6. Commit: `git add -A && git commit -m "fix(objectives): unified tree view, remove life-area split, all objectives in tree" && git push`

## Expected result
- "Ein besserer Mensch werden" shows as a root objective card
- "Mich intellektuell, persönlich und sportlich weiterentwickeln" shows indented below it with a left border (tree branch)
- The "KI-Zielanalyse" button is visible at the top of the page
- When user clicks "Analyse starten", GPT analyzes the goals and returns hierarchy suggestions

## Completion signal
When done: `openclaw system event --text "Done: Objectives tree fixed — unified view, goals properly hierarchical" --mode now`
