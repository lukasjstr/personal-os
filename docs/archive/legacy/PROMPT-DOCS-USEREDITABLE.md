# PROMPT: User-Editable Docs (replace hardcoded content)

## Goal
The `/docs` page currently shows hardcoded German content (Morgenroutine, Training-Split, etc.).
Replace it with a fully user-editable CRUD document system. This is the user's personal reference library —
a place for journal templates, gratitude notes, meal plans, routines, anything they want to write down.

## Git config (always use this)
user.name=lukasjstr, user.email=lukasjstr@gmail.com

---

## 1. Backend — New DB model + migration

### File: `bot/database/models.py`
Add this model after `BrainDump`:

```python
class UserDocument(Base):
    __tablename__ = "user_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    emoji: Mapped[str] = mapped_column(String(10), default="📄")
    content: Mapped[str] = mapped_column(Text, default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="documents")
```

Also add to `User` model: `documents: Mapped[list["UserDocument"]] = relationship(back_populates="user", cascade="all, delete-orphan")`

### File: `bot/database/migrations/versions/003_user_documents.py`
Create Alembic migration:
```python
"""Add user_documents table

Revision ID: 003
Revises: 002
Create Date: 2026-03-11
"""
from alembic import op
import sqlalchemy as sa

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'user_documents',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('emoji', sa.String(10), nullable=False, server_default='📄'),
        sa.Column('content', sa.Text(), nullable=False, server_default=''),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )

def downgrade():
    op.drop_table('user_documents')
```

---

## 2. Backend — API routes

### File: `bot/api/routes.py`
Add these endpoints (after the existing brain_dump routes, before the auth section):

```python
# ─── User Documents ───────────────────────────────────────────────────────────

class CreateDocBody(BaseModel):
    title: str
    emoji: str = "📄"
    content: str = ""
    sort_order: int = 0

class UpdateDocBody(BaseModel):
    title: Optional[str] = None
    emoji: Optional[str] = None
    content: Optional[str] = None
    sort_order: Optional[int] = None

@router.get("/docs")
async def list_docs(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)) -> dict:
    from bot.database.models import UserDocument
    result = await session.execute(
        select(UserDocument).where(UserDocument.user_id == user.id).order_by(UserDocument.sort_order, UserDocument.id)
    )
    docs = result.scalars().all()
    return {"docs": [{"id": d.id, "title": d.title, "emoji": d.emoji, "content": d.content, "sort_order": d.sort_order, "created_at": d.created_at.isoformat(), "updated_at": d.updated_at.isoformat()} for d in docs]}

@router.post("/docs")
async def create_doc(body: CreateDocBody, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)) -> dict:
    from bot.database.models import UserDocument
    doc = UserDocument(user_id=user.id, title=body.title, emoji=body.emoji, content=body.content, sort_order=body.sort_order)
    session.add(doc)
    await session.flush()
    return {"id": doc.id, "title": doc.title, "emoji": doc.emoji, "content": doc.content, "sort_order": doc.sort_order}

@router.put("/docs/{doc_id}")
async def update_doc(doc_id: int, body: UpdateDocBody, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)) -> dict:
    from bot.database.models import UserDocument
    doc = await session.get(UserDocument, doc_id)
    if not doc or doc.user_id != user.id:
        raise HTTPException(404)
    if body.title is not None: doc.title = body.title
    if body.emoji is not None: doc.emoji = body.emoji
    if body.content is not None: doc.content = body.content
    if body.sort_order is not None: doc.sort_order = body.sort_order
    doc.updated_at = datetime.utcnow()
    await session.flush()
    return {"id": doc.id, "title": doc.title, "emoji": doc.emoji, "content": doc.content, "sort_order": doc.sort_order}

@router.delete("/docs/{doc_id}")
async def delete_doc(doc_id: int, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)) -> dict:
    from bot.database.models import UserDocument
    doc = await session.get(UserDocument, doc_id)
    if not doc or doc.user_id != user.id:
        raise HTTPException(404)
    await session.delete(doc)
    return {"ok": True}
```

---

## 3. Frontend — Dashboard docs page

### File: `dashboard/src/app/docs/page.tsx`
Replace the entire file. Requirements:
- Fetch docs from `GET /api/docs`
- Show docs as cards with emoji + title, expand/collapse to show content
- "Neues Dokument" button opens a modal
- Each doc card has edit (pencil) and delete (trash) buttons
- Edit modal has: emoji picker (simple text input), title input, large textarea for content (markdown-friendly)
- Empty state: "Noch keine Dokumente — leg dein erstes an!" with a "+ Erstellen" button
- Use the existing design system (zinc-900 cards, same style as other pages)
- Use SWR for data fetching with optimistic updates

### API client additions in `dashboard/src/lib/api.ts`:
```typescript
// Docs
listDocs: () => apiFetch<{ docs: UserDoc[] }>("/api/docs"),
createDoc: (body: { title: string; emoji: string; content: string }) => apiPost<UserDoc>("/api/docs", body),
updateDoc: (id: number, body: Partial<{ title: string; emoji: string; content: string; sort_order: number }>) => apiPut<UserDoc>(`/api/docs/${id}`, body),
deleteDoc: (id: number) => apiDelete(`/api/docs/${id}`),
```

Add type:
```typescript
export interface UserDoc {
  id: number;
  title: string;
  emoji: string;
  content: string;
  sort_order: number;
  created_at: string;
  updated_at: string;
}
```

---

## 4. Deploy

After all changes:
1. `python3 -m py_compile bot/database/models.py bot/api/routes.py` — must pass
2. SSH to server: `ssh root@95.111.252.176`
3. `cd /opt/personal-os && git pull` — if that fails due to auth, scp changed files directly
4. Run migration: `cd /opt/personal-os && python3 -m alembic upgrade head`
5. Restart bot: `systemctl restart personal-os`
6. Build dashboard: `cd dashboard && npm run build`
7. Restart dashboard: `systemctl restart personal-os-dashboard`
8. Commit locally: `git add -A && git commit -m "feat(docs): user-editable document library (CRUD)" && git push`

## Completion signal
When done: `openclaw system event --text "Done: User-editable docs system shipped — CRUD backend + dashboard UI" --mode now`
