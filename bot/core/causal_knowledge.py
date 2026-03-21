"""Causal knowledge base — maps nutrient/behavior correlations to scientific explanations."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CausalRelation:
    trigger: str  # e.g. "high_sodium"
    effect: str  # e.g. "poor_sleep"
    mechanism: str  # scientific explanation
    threshold: Optional[float] = None  # trigger threshold value
    threshold_unit: str = ""
    severity: str = "medium"  # low / medium / high
    recommendation: str = ""
    source: str = ""  # citation
    tags: list[str] = field(default_factory=list)


# ── Static knowledge base ────────────────────────────────────────────────────

CAUSAL_KNOWLEDGE: list[CausalRelation] = [
    # ── Sodium ────────────────────────────────────────────────────────────────
    CausalRelation(
        trigger="high_sodium",
        effect="poor_sleep",
        mechanism=(
            "Hoher Natriumkonsum (>4000 mg) erhöht die Plasmaosmolalität. "
            "Die Nieren müssen nachts mehr Wasser ausscheiden (osmotische Diurese), "
            "was zu Nykturie und fragmentiertem Schlaf führt."
        ),
        threshold=4000,
        threshold_unit="mg",
        severity="high",
        recommendation="Abendessen natriumarm halten (<600 mg). Kaliumreiche Lebensmittel als Gegengewicht.",
        source="J Clin Sleep Med 2019; Dietary sodium and sleep quality",
        tags=["sodium", "sleep", "nocturia"],
    ),
    CausalRelation(
        trigger="high_sodium",
        effect="high_blood_pressure",
        mechanism=(
            "Natrium bindet Wasser im Blut → erhöhtes Blutvolumen → "
            "höherer Druck auf Gefäßwände. Dauerhaft >5000 mg/Tag erhöht Hypertonie-Risiko."
        ),
        threshold=5000,
        threshold_unit="mg",
        severity="high",
        recommendation="Ziel: <2300 mg/Tag (WHO). Verarbeitete Lebensmittel reduzieren.",
        source="WHO guideline on sodium intake 2023",
        tags=["sodium", "blood_pressure"],
    ),
    # ── Caffeine ──────────────────────────────────────────────────────────────
    CausalRelation(
        trigger="high_caffeine",
        effect="poor_sleep",
        mechanism=(
            "Koffein blockiert Adenosin-Rezeptoren im Gehirn. Halbwertszeit ~5-6h. "
            "Konsum nach 14:00 kann Einschlafzeit um 40+ min verzögern und "
            "Tiefschlafphasen um bis zu 20% reduzieren."
        ),
        threshold=400,
        threshold_unit="mg",
        severity="high",
        recommendation="Koffein nur vor 14:00 Uhr. Max 400 mg/Tag (≈4 Espresso).",
        source="Sleep Medicine Reviews 2017; Clark & Landolt",
        tags=["caffeine", "sleep", "adenosine"],
    ),
    CausalRelation(
        trigger="high_caffeine",
        effect="anxiety",
        mechanism=(
            "Koffein >500 mg/Tag stimuliert das sympathische Nervensystem, "
            "erhöht Cortisol und Noradrenalin → Unruhe, Herzrasen, Angstgefühle."
        ),
        threshold=500,
        threshold_unit="mg",
        severity="medium",
        recommendation="Bei Angstgefühlen Koffein auf <200 mg/Tag reduzieren.",
        source="Psychopharmacology 2015",
        tags=["caffeine", "anxiety", "cortisol"],
    ),
    # ── Hydration ─────────────────────────────────────────────────────────────
    CausalRelation(
        trigger="low_hydration",
        effect="poor_cognition",
        mechanism=(
            "Bereits 1-2% Dehydrierung reduziert Arbeitsgedächtnis und "
            "Aufmerksamkeit. Das Gehirn besteht zu 75% aus Wasser — "
            "Volumenverlust beeinträchtigt neuronale Signalübertragung."
        ),
        threshold=1.5,
        threshold_unit="L",
        severity="medium",
        recommendation="Mindestens 2.5-3L Wasser/Tag. Morgens direkt 500ml trinken.",
        source="Br J Nutr 2011; Ganio et al.",
        tags=["hydration", "cognition", "brain"],
    ),
    CausalRelation(
        trigger="low_hydration",
        effect="fatigue",
        mechanism=(
            "Flüssigkeitsmangel reduziert Blutvolumen → Herz muss stärker pumpen "
            "→ erhöhte Herzfrequenz bei gleicher Belastung → schnellere Ermüdung."
        ),
        threshold=1.5,
        threshold_unit="L",
        severity="medium",
        recommendation="Regelmäßig über den Tag verteilt trinken, nicht erst bei Durst.",
        source="EFSA Scientific Opinion on water intake 2010",
        tags=["hydration", "fatigue", "cardiovascular"],
    ),
    # ── Exercise ──────────────────────────────────────────────────────────────
    CausalRelation(
        trigger="exercise",
        effect="improved_mood",
        mechanism=(
            "Bewegung erhöht Endorphin-, Serotonin- und BDNF-Spiegel. "
            "30 min moderate Aktivität kann Stimmung für 2-4 Stunden verbessern. "
            "Langfristig reduziert regelmäßiges Training Depressionsrisiko um ~25%."
        ),
        threshold=30,
        threshold_unit="min",
        severity="low",
        recommendation="Mindestens 150 min moderate Bewegung/Woche.",
        source="Lancet Psychiatry 2018; Schuch et al.",
        tags=["exercise", "mood", "serotonin", "endorphins"],
    ),
    CausalRelation(
        trigger="exercise",
        effect="improved_sleep",
        mechanism=(
            "Körperliche Aktivität erhöht den Adenosinaufbau und den "
            "homöostatischen Schlafdruck. Thermoregulation nach Sport "
            "fördert das Einschlafen. Aber: Intensives Training <2h vor "
            "dem Schlafen kann Einschlafzeit verlängern."
        ),
        threshold=20,
        threshold_unit="min",
        severity="low",
        recommendation="Training idealerweise morgens oder nachmittags abschließen.",
        source="Sleep Medicine Reviews 2015; Kredlow et al.",
        tags=["exercise", "sleep", "adenosine"],
    ),
    CausalRelation(
        trigger="no_exercise",
        effect="poor_sleep",
        mechanism=(
            "Ohne körperliche Aktivität fehlt der homöostatische Schlafdruck. "
            "Der Körper baut tagsüber nicht genug Adenosin auf → "
            "flacherer, weniger erholsamer Schlaf."
        ),
        severity="medium",
        recommendation="Auch an Ruhetagen leichte Bewegung (Spaziergang 20 min).",
        tags=["exercise", "sleep", "sedentary"],
    ),
    # ── Protein ───────────────────────────────────────────────────────────────
    CausalRelation(
        trigger="low_protein",
        effect="muscle_loss",
        mechanism=(
            "Ohne ausreichend Protein (<1.6 g/kg bei Krafttraining) kann der "
            "Körper beschädigtes Muskelgewebe nicht reparieren. "
            "Muskelproteinsynthese < Muskelproteinabbau → Nettoverlust."
        ),
        threshold=100,
        threshold_unit="g",
        severity="high",
        recommendation="1.6-2.2 g Protein pro kg Körpergewicht bei Krafttraining.",
        source="BJSM 2018; Morton et al. meta-analysis",
        tags=["protein", "muscle", "training"],
    ),
    CausalRelation(
        trigger="high_protein",
        effect="improved_satiety",
        mechanism=(
            "Protein hat den höchsten Sättigungseffekt aller Makronährstoffe. "
            "Es stimuliert GLP-1 und PYY (Sättigungshormone) stärker "
            "als Kohlenhydrate oder Fett."
        ),
        severity="low",
        recommendation="Jede Mahlzeit mit 25-40g Protein planen für bessere Sättigung.",
        source="Am J Clin Nutr 2015",
        tags=["protein", "satiety", "appetite"],
    ),
    # ── Sugar ─────────────────────────────────────────────────────────────────
    CausalRelation(
        trigger="high_sugar",
        effect="energy_crash",
        mechanism=(
            "Einfache Zucker verursachen schnellen Blutzuckeranstieg → "
            "überschießende Insulinreaktion → reaktive Hypoglykämie "
            "90-120 min nach Konsum → Müdigkeit und Heißhunger."
        ),
        threshold=50,
        threshold_unit="g",
        severity="medium",
        recommendation="Zucker mit Ballaststoffen/Protein kombinieren, um Spitzen abzuflachen.",
        source="Lancet 2018; Ludwig et al.",
        tags=["sugar", "energy", "insulin", "blood_sugar"],
    ),
    # ── Fiber ─────────────────────────────────────────────────────────────────
    CausalRelation(
        trigger="low_fiber",
        effect="poor_digestion",
        mechanism=(
            "Ballaststoffe (<25 g/Tag) verlangsamen Darmtransit, "
            "reduzieren Mikrobiom-Diversität und erhöhen Risiko für "
            "Verstopfung und Darmentzündungen."
        ),
        threshold=15,
        threshold_unit="g",
        severity="medium",
        recommendation="30g+ Ballaststoffe/Tag aus Gemüse, Hülsenfrüchten, Vollkorn.",
        source="Lancet 2019; Reynolds et al.",
        tags=["fiber", "digestion", "microbiome"],
    ),
    # ── Potassium ─────────────────────────────────────────────────────────────
    CausalRelation(
        trigger="low_potassium",
        effect="muscle_cramps",
        mechanism=(
            "Kalium ist essentiell für Muskelkontraktion und -relaxation. "
            "Mangel stört das Membranpotential → unkontrollierte Kontraktionen (Krämpfe). "
            "Besonders nach dem Training kritisch."
        ),
        threshold=2000,
        threshold_unit="mg",
        severity="medium",
        recommendation="Kaliumreiche Lebensmittel: Bananen, Kartoffeln, Spinat, Avocado.",
        source="NIH Potassium Fact Sheet 2022",
        tags=["potassium", "muscle", "cramps", "electrolytes"],
    ),
    CausalRelation(
        trigger="low_potassium_high_sodium",
        effect="high_blood_pressure",
        mechanism=(
            "Das Na/K-Verhältnis ist entscheidender als Natrium allein. "
            "Kalium fördert die renale Natriumausscheidung. "
            "Optimales Verhältnis: Na:K ≈ 1:2."
        ),
        severity="high",
        recommendation="Mehr Kalium (3500-4700 mg/Tag) bei gleichzeitiger Natriumreduktion.",
        source="WHO guideline on potassium intake 2012",
        tags=["potassium", "sodium", "blood_pressure"],
    ),
    # ── Sleep ─────────────────────────────────────────────────────────────────
    CausalRelation(
        trigger="poor_sleep",
        effect="poor_training",
        mechanism=(
            "Schlafmangel (<7h) reduziert Testosteron um 10-15%, "
            "erhöht Cortisol und senkt Wachstumshormon. "
            "Kraftleistung sinkt um 5-10%, Verletzungsrisiko steigt um 60%."
        ),
        severity="high",
        recommendation="7-9h Schlaf priorisieren. Bei <6h kein Maximaltraining.",
        source="Sleep 2011; Leproult & Van Cauter",
        tags=["sleep", "training", "testosterone", "recovery"],
    ),
    CausalRelation(
        trigger="poor_sleep",
        effect="increased_appetite",
        mechanism=(
            "Schlafmangel erhöht Ghrelin (Hungerhormon) und senkt Leptin "
            "(Sättigungshormon). Kalorienaufnahme steigt um ~300-400 kcal/Tag, "
            "bevorzugt hochkalorische Lebensmittel."
        ),
        severity="high",
        recommendation="Schlafqualität verbessern reduziert automatisch Überessen.",
        source="Ann Intern Med 2010; Spiegel et al.",
        tags=["sleep", "appetite", "ghrelin", "leptin"],
    ),
    # ── Alcohol ───────────────────────────────────────────────────────────────
    CausalRelation(
        trigger="alcohol",
        effect="poor_sleep",
        mechanism=(
            "Alkohol beschleunigt Einschlafen, aber unterdrückt REM-Schlaf "
            "in der 2. Nachthälfte. Metabolisierung erzeugt Acetaldehyd → "
            "sympathische Aktivierung → Aufwachen nach 4-5h."
        ),
        severity="high",
        recommendation="Letzter Alkohol ≥3h vor dem Schlafen. Ideal: alkoholfreie Tage.",
        source="Alcohol Clin Exp Res 2015; Ebrahim et al.",
        tags=["alcohol", "sleep", "REM"],
    ),
    CausalRelation(
        trigger="alcohol",
        effect="poor_recovery",
        mechanism=(
            "Alkohol hemmt Muskelproteinsynthese um bis zu 37%, "
            "stört Glykogenresynthese und erhöht Entzündungsmarker. "
            "Besonders schädlich innerhalb 24h nach dem Training."
        ),
        severity="high",
        recommendation="Nach Trainingstagen keinen Alkohol. Muskelaufbau priorisieren.",
        source="PLoS One 2014; Parr et al.",
        tags=["alcohol", "recovery", "muscle", "training"],
    ),
    # ── Stress / Mood ─────────────────────────────────────────────────────────
    CausalRelation(
        trigger="low_mood_streak",
        effect="reduced_productivity",
        mechanism=(
            "Anhaltend niedrige Stimmung (<5/10 über 3+ Tage) korreliert mit "
            "reduziertem präfrontalem Cortex-Engagement → weniger Motivation, "
            "schlechtere Entscheidungsfähigkeit und Prokrastination."
        ),
        severity="medium",
        recommendation="Gegensteuern: Bewegung, soziale Kontakte, Tageslicht-Exposition.",
        tags=["mood", "productivity", "mental_health"],
    ),
    # ── Meal Timing ───────────────────────────────────────────────────────────
    CausalRelation(
        trigger="late_eating",
        effect="poor_sleep",
        mechanism=(
            "Essen <2h vor dem Schlafen aktiviert die Verdauung und "
            "erhöht die Kerntemperatur. Der Körper braucht aber "
            "Temperaturabsenkung zum Einschlafen → verzögertes Einschlafen."
        ),
        severity="medium",
        recommendation="Letzte größere Mahlzeit ≥2-3h vor dem Schlafen.",
        source="Br J Nutr 2020",
        tags=["meal_timing", "sleep", "thermoregulation"],
    ),
    # ── Screen Time ───────────────────────────────────────────────────────────
    CausalRelation(
        trigger="late_screen_time",
        effect="poor_sleep",
        mechanism=(
            "Blaues Licht von Bildschirmen unterdrückt Melatonin-Produktion "
            "um 50%+ bei Exposition nach 21:00. Die circadiane Uhr wird "
            "um 1-2h nach hinten verschoben."
        ),
        severity="medium",
        recommendation="Ab 21:00 Blaulichtfilter oder keine Bildschirme.",
        source="PNAS 2014; Chang et al.",
        tags=["screen", "sleep", "melatonin", "circadian"],
    ),
    # ── Magnesium ─────────────────────────────────────────────────────────────
    CausalRelation(
        trigger="low_magnesium",
        effect="poor_sleep",
        mechanism=(
            "Magnesium aktiviert den Parasympathikus und reguliert Melatonin. "
            "Mangel (<300 mg/Tag) ist mit Einschlafstörungen und "
            "reduzierter Schlafqualität assoziiert."
        ),
        threshold=200,
        threshold_unit="mg",
        severity="medium",
        recommendation="400 mg Magnesium/Tag. Abends Magnesiumglycinat für besseren Schlaf.",
        source="Nutrients 2017; Abbasi et al.",
        tags=["magnesium", "sleep", "parasympathetic"],
    ),
]

# ── Lookup indexes ────────────────────────────────────────────────────────────

_BY_TRIGGER: dict[str, list[CausalRelation]] = {}
_BY_EFFECT: dict[str, list[CausalRelation]] = {}
_BY_TAG: dict[str, list[CausalRelation]] = {}

for _rel in CAUSAL_KNOWLEDGE:
    _BY_TRIGGER.setdefault(_rel.trigger, []).append(_rel)
    _BY_EFFECT.setdefault(_rel.effect, []).append(_rel)
    for _tag in _rel.tags:
        _BY_TAG.setdefault(_tag, []).append(_rel)


# ── Public API ────────────────────────────────────────────────────────────────

def get_explanations_for_trigger(trigger: str) -> list[CausalRelation]:
    """Get all causal relations triggered by a specific condition."""
    return _BY_TRIGGER.get(trigger, [])


def get_explanations_for_effect(effect: str) -> list[CausalRelation]:
    """Get all causal relations that lead to a specific effect."""
    return _BY_EFFECT.get(effect, [])


def get_explanations_by_tag(tag: str) -> list[CausalRelation]:
    """Find all relations related to a topic (e.g. 'sleep', 'sodium')."""
    return _BY_TAG.get(tag, [])


def explain_correlation(nutrient: str, health_metric: str) -> Optional[CausalRelation]:
    """Find the causal explanation linking a nutrient/behavior to a health outcome."""
    tag_matches = _BY_TAG.get(nutrient, [])
    for rel in tag_matches:
        if health_metric in rel.tags or health_metric in rel.effect:
            return rel
    return None


def get_relevant_explanations(
    nutrients: dict[str, float],
    water_l: float = 0,
) -> list[dict]:
    """Given today's nutrient intake, return all relevant causal warnings.

    Args:
        nutrients: dict with keys like 'sodium_mg', 'caffeine_mg', 'protein_g', etc.
        water_l: total water in liters today

    Returns:
        List of dicts with keys: trigger, effects, mechanism, recommendation, severity
    """
    results: list[dict] = []

    sodium = nutrients.get("sodium_mg", 0)
    if sodium >= 4000:
        for rel in _BY_TRIGGER.get("high_sodium", []):
            results.append(_rel_to_dict(rel, f"Natrium heute: {sodium:.0f} mg"))

    caffeine = nutrients.get("caffeine_mg", 0)
    if caffeine >= 400:
        for rel in _BY_TRIGGER.get("high_caffeine", []):
            results.append(_rel_to_dict(rel, f"Koffein heute: {caffeine:.0f} mg"))

    protein = nutrients.get("protein_g", 0)
    if 0 < protein < 100:
        for rel in _BY_TRIGGER.get("low_protein", []):
            results.append(_rel_to_dict(rel, f"Protein heute: {protein:.0f} g"))

    sugar = nutrients.get("sugar_g", 0)
    if sugar >= 50:
        for rel in _BY_TRIGGER.get("high_sugar", []):
            results.append(_rel_to_dict(rel, f"Zucker heute: {sugar:.0f} g"))

    fiber = nutrients.get("fiber_g", 0)
    if 0 < fiber < 15:
        for rel in _BY_TRIGGER.get("low_fiber", []):
            results.append(_rel_to_dict(rel, f"Ballaststoffe heute: {fiber:.0f} g"))

    if 0 < water_l < 1.5:
        for rel in _BY_TRIGGER.get("low_hydration", []):
            results.append(_rel_to_dict(rel, f"Wasser heute: {water_l:.1f} L"))

    # Sort by severity
    severity_order = {"high": 0, "medium": 1, "low": 2}
    results.sort(key=lambda r: severity_order.get(r["severity"], 9))

    return results


def get_daily_health_tips(nutrients: dict[str, float], water_l: float = 0) -> list[str]:
    """Return actionable tip strings based on today's intake."""
    explanations = get_relevant_explanations(nutrients, water_l)
    tips: list[str] = []
    for exp in explanations[:3]:
        tip = f"⚠️ {exp['context']}: {exp['mechanism'][:120]}..."
        if exp.get("recommendation"):
            tip += f"\n💡 {exp['recommendation']}"
        tips.append(tip)
    return tips


def _rel_to_dict(rel: CausalRelation, context: str) -> dict:
    return {
        "trigger": rel.trigger,
        "effect": rel.effect,
        "context": context,
        "mechanism": rel.mechanism,
        "recommendation": rel.recommendation,
        "severity": rel.severity,
        "source": rel.source,
    }
