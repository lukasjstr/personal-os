"use client";

import Header from "@/components/Header";

const DOCS = [
  {
    title: "Morgenroutine",
    emoji: "🌅",
    content: `**Ziel:** Strukturierter Tagesstart für maximale Energie und Fokus.

**06:30** — Aufstehen
**06:35** — Großes Glas Wasser (0.5L) + Supplements
**06:45** — 10 Minuten Journaling
   → Was will ich heute erreichen?
   → Wofür bin ich dankbar?
   → Eine Sache die ich verbessern will

**07:00** — Kalte Dusche (2 Min)
**07:10** — Tagesplan im Personal OS bestätigen
**07:15** — Erste Tiefarbeits-Session beginnen

**Supplements:**
- Vitamin D3 + K2
- Omega 3
- Magnesium (abends)
- Kreatin`,
  },
  {
    title: "Training-Split",
    emoji: "💪",
    content: `**4er-Split — Push/Pull/Legs/Full**

**Montag — Push (Brust, Schulter, Trizeps)**
- Bankdrücken: 4×8-10
- Schulterdrücken: 3×10-12
- Seitheben: 3×12-15
- Trizeps Pushdown: 3×12-15
- Dips: 2×10

**Dienstag — Pull (Rücken, Bizeps)**
- Klimmzüge: 4×6-8
- Langhantelrudern: 3×8-10
- Latzug: 3×10-12
- Bizepscurl: 3×10-12

**Donnerstag — Legs**
- Kniebeugen: 4×8-10
- Beinpresse: 3×10-12
- Ausfallschritte: 3×10
- Wadenheben: 4×15

**Freitag — Full Body / Schwächen**
- Freie Auswahl je nach Schwachstellen

**Progressionsziel:** +2.5kg alle 2 Wochen bei gleichbleibenden Reps`,
  },
  {
    title: "Ernährungsplan",
    emoji: "🍽️",
    content: `**Ziel:** Muskelaufbau bei sauberem Bulk

**Kalorien:** ~2800 kcal
**Protein:** 160g+
**Kohlenhydrate:** 280g
**Fett:** 80g

**Mahlzeiten:**

🌅 **Frühstück (7:30)**
— Haferflocken 100g + Whey 1 Portion + Banane
→ ~600 kcal, 45g Protein

🕙 **Snack (10:00)**
— Griechischer Joghurt 200g + Nüsse 30g
→ ~350 kcal, 25g Protein

🕛 **Mittagessen (12:30)**
— Hähnchenbrust 200g + Reis 150g + Gemüse
→ ~700 kcal, 55g Protein

🕔 **Pre-Workout (16:00)**
— Reis 100g + Thunfisch 1 Dose
→ ~400 kcal, 35g Protein

🕗 **Abendessen (19:00)**
— Magerquark 250g + Lachs 150g + Salat
→ ~550 kcal, 65g Protein

💊 **Supplements:**
Kreatin 5g täglich, Vitamin D, Omega 3`,
  },
  {
    title: "Wochenziele",
    emoji: "🎯",
    content: `**Wiederkehrende Wochenziele:**

**Fitness:**
☐ 4 Trainingseinheiten
☐ 3L Wasser täglich
☐ 7h+ Schlaf / Nacht

**Business:**
☐ 2 LinkedIn Posts
☐ 3h Deep Work täglich
☐ 1 Networking-Gespräch

**Persönlich:**
☐ 30min Lesen täglich
☐ 1 neue Sache lernen
☐ Wochenreview Sonntag

**Review jeden Sonntag:**
→ Was lief gut diese Woche?
→ Was hätte besser laufen können?
→ Top 3 Prioritäten nächste Woche?`,
  },
  {
    title: "Produktivitäts-System",
    emoji: "⚡",
    content: `**Personal OS — Das System**

**OKR-Struktur:**
Objective → Key Result → Task → Log

**Tagesablauf:**
- Morgens: 3 Top-Prioritäten festlegen
- Tiefarbeit: 09:00–12:00 (keine Ablenkungen)
- Kommunikation: 12:00–13:00
- Arbeit: 14:00–17:00
- Sport: 17:00–18:30
- Abends: Review & Vorbereitung nächster Tag

**Regeln:**
1. Die 3 Prioritäten kommen zuerst
2. E-Mails nur 2x täglich checken
3. Handy auf Stumm beim Deep Work
4. Jeder Input → ins System (Telegram)

**Weekly Review (Sonntag 20:00):**
- Was habe ich erreicht?
- Was war schwierig?
- Welche Gewohnheiten aufbauen?
- Top 3 Ziele nächste Woche`,
  },
];

export default function DocsPage() {
  return (
    <div>
      <Header title="📄 Dokumente" subtitle="Persönliche Referenz-Docs" />

      <div className="grid grid-cols-1 gap-4">
        {DOCS.map((doc) => (
          <details key={doc.title} className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden group">
            <summary className="flex items-center gap-3 px-5 py-4 cursor-pointer hover:bg-zinc-800/50 transition-colors list-none">
              <span className="text-2xl">{doc.emoji}</span>
              <h2 className="text-white font-semibold flex-1">{doc.title}</h2>
              <span className="text-zinc-500 group-open:rotate-180 transition-transform">▼</span>
            </summary>
            <div className="px-5 pb-5 border-t border-zinc-800">
              <div className="prose prose-invert prose-sm max-w-none pt-4">
                <pre className="whitespace-pre-wrap text-sm text-zinc-300 font-sans leading-relaxed bg-transparent p-0">
                  {doc.content}
                </pre>
              </div>
            </div>
          </details>
        ))}
      </div>
    </div>
  );
}
