"""Narrative Lens Registry — structured lens contracts for storytelling emphasis.

Each lens is a self-contained contract that tells the planning and writing nodes
HOW to shift emphasis without altering facts.  When no lens is selected the agent
behaves identically to the default macro-political framing.

Backward-compatible: every helper returns neutral/empty values when ``lenses`` is
None or empty.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Lens contract data structure
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LensContract:
    """Structured storytelling lens — defines emphasis, not facts."""

    lens_id: str
    short_description: str
    scene_priorities: list[str]          # ranked
    tension_patterns: list[str]          # e.g. "time pressure", "info gaps"
    preferred_artifacts: list[str]       # letters, maps, manifests, transcripts …
    forbidden_moves: list[str]           # things this lens must NOT do
    hook_templates: list[str]            # re-hook starter patterns


# ---------------------------------------------------------------------------
# The lens library
# ---------------------------------------------------------------------------

LENS_REGISTRY: dict[str, LensContract] = {
    # ── Everyday people in the blast radius ────────────────────────────
    "civilians": LensContract(
        lens_id="civilians",
        short_description="Ordinary people caught in the blast radius of state decisions",
        scene_priorities=[
            "Daily routine disrupted by event",
            "Decision to stay or flee",
            "Moments of resourcefulness under pressure",
            "Community bonds tested",
        ],
        tension_patterns=["info gaps", "resource scarcity", "moral trap", "uncertainty"],
        preferred_artifacts=["diaries", "letters", "oral histories", "ration cards", "photographs"],
        forbidden_moves=[
            "Centering generals or heads of state as protagonists",
            "Treating civilians as backdrop to military action",
            "Inventing civilian characters",
        ],
        hook_templates=[
            "While the generals debated, {name} had exactly {time} to decide…",
            "Nobody told the people on {street} what was coming next…",
            "The order reached headquarters at {time}. It reached {name}'s kitchen {delay} later…",
        ],
    ),

    "children": LensContract(
        lens_id="children",
        short_description="Coming-of-age or survival through a child's limited vantage point",
        scene_priorities=[
            "Adult world interpreted through incomplete understanding",
            "Loss of normalcy",
            "Unexpected responsibility forced onto young shoulders",
            "Moments of play or innocence amid chaos",
        ],
        tension_patterns=["info gaps", "dependency", "separation anxiety", "moral confusion"],
        preferred_artifacts=["school records", "evacuation lists", "letters home", "photographs", "oral histories"],
        forbidden_moves=[
            "Gratuitous depiction of violence against children",
            "Invented child characters",
            "Sentimentalising — let the situation carry the emotion",
        ],
        hook_templates=[
            "{name} was {age} when the world outside the window changed…",
            "The teacher said it would be temporary. That was {time_ago}…",
        ],
    ),

    "families": LensContract(
        lens_id="families",
        short_description="Family separation, reunion, and bonds under pressure",
        scene_priorities=[
            "Moment of separation",
            "Communication attempts across distance",
            "Divergent fates of family members",
            "Reunion or permanent loss",
        ],
        tension_patterns=["separation", "info gaps", "moral trap", "time pressure"],
        preferred_artifacts=["letters", "telegrams", "Red Cross messages", "family photographs", "immigration records"],
        forbidden_moves=[
            "Inventing family relationships",
            "Reducing families to a single emotional beat",
        ],
        hook_templates=[
            "{name} sent the letter on {date}. It arrived {delay} later — to an empty house…",
            "The last time the family was in the same room was {date}…",
        ],
    ),

    "refugees": LensContract(
        lens_id="refugees",
        short_description="Displacement, flight, and the bureaucracy of survival",
        scene_priorities=[
            "Decision to leave",
            "Journey conditions and obstacles",
            "Border encounters and documentation",
            "Arrival and disorientation in new place",
        ],
        tension_patterns=["time pressure", "resource scarcity", "bureaucratic maze", "identity loss"],
        preferred_artifacts=["transit papers", "refugee camp records", "ship manifests", "oral histories", "UNHCR reports"],
        forbidden_moves=[
            "Flattening refugee experience into a single narrative arc",
            "Inventing refugee characters",
        ],
        hook_templates=[
            "The border closed in {time}. {name} was {distance} away…",
            "The document said {name_on_paper}. That wasn't the name {pronoun} was born with…",
        ],
    ),

    # ── Systems under strain ──────────────────────────────────────────
    "medics": LensContract(
        lens_id="medics",
        short_description="Medical personnel making triage decisions under impossible conditions",
        scene_priorities=[
            "Triage decision under resource constraint",
            "Improvisation with limited supplies",
            "Ethical boundary tested",
            "Aftermath and psychological cost",
        ],
        tension_patterns=["time pressure", "resource scarcity", "moral trap", "exhaustion"],
        preferred_artifacts=["field hospital logs", "medical reports", "evacuation records", "memoirs", "casualty lists"],
        forbidden_moves=[
            "Gratuitous medical detail for shock value",
            "Inventing medical personnel",
        ],
        hook_templates=[
            "There were {count} wounded and {supplies} left. {name} had to choose…",
            "The textbook said one thing. The field said another…",
        ],
    ),

    "logistics": LensContract(
        lens_id="logistics",
        short_description="Supply chains, transport networks, and the machinery that keeps operations alive",
        scene_priorities=[
            "Critical supply bottleneck",
            "Improvised solution to systemic failure",
            "Human cost of logistical failure",
            "The moment the chain breaks",
        ],
        tension_patterns=["time pressure", "cascading failure", "resource scarcity", "distance"],
        preferred_artifacts=["shipping manifests", "railway timetables", "supply requisitions", "quartermaster logs"],
        forbidden_moves=[
            "Turning logistics into dry exposition",
            "Ignoring the humans inside the system",
        ],
        hook_templates=[
            "The convoy needed {resource} by {deadline}. The nearest depot was {distance} away…",
            "On paper, the supply line was secure. On the ground, {problem}…",
        ],
    ),

    "engineers": LensContract(
        lens_id="engineers",
        short_description="Infrastructure under strain — building, destroying, or holding together",
        scene_priorities=[
            "Technical problem under time/resource constraint",
            "Improvised engineering solution",
            "Structural failure with human consequence",
            "The moment the design is tested by reality",
        ],
        tension_patterns=["time pressure", "material limits", "cascading failure", "physics vs orders"],
        preferred_artifacts=["blueprints", "construction logs", "inspection reports", "after-action assessments"],
        forbidden_moves=[
            "Technical jargon without narrative payoff",
            "Ignoring the people building or dying inside the structure",
        ],
        hook_templates=[
            "The bridge was built for {capacity}. {actual_load} was crossing it…",
            "{name} had {time} to fix what took {original_time} to build…",
        ],
    ),

    "couriers": LensContract(
        lens_id="couriers",
        short_description="Drivers, dispatch riders, and couriers — people who carry messages through danger",
        scene_priorities=[
            "Message in transit — what it says, who sent it, who needs it",
            "Route danger and obstacles",
            "Arrival too late or just in time",
            "Miscommunication chain",
        ],
        tension_patterns=["time pressure", "info gaps", "exposure", "distance"],
        preferred_artifacts=["dispatch logs", "route maps", "radio transcripts", "motor pool records"],
        forbidden_moves=[
            "Treating the courier as a plot device — they are the POV",
        ],
        hook_templates=[
            "The message was three sentences long. Getting it there took {time} and cost {cost}…",
            "{name} knew what the envelope said. {pronoun} didn't know if {recipient} was still alive to read it…",
        ],
    ),

    "translators": LensContract(
        lens_id="translators",
        short_description="Interpreters and translators — people who control the flow of meaning between sides",
        scene_priorities=[
            "Translation decision that changes meaning",
            "Caught between two sides with conflicting interests",
            "Mistranslation with operational consequences",
            "Trust and suspicion from both sides",
        ],
        tension_patterns=["info gaps", "moral trap", "dual loyalty", "time pressure"],
        preferred_artifacts=["meeting transcripts", "diplomatic cables", "interpreter memoirs", "interrogation records"],
        forbidden_moves=[
            "Treating translation as mechanical — it is a decision under pressure",
        ],
        hook_templates=[
            "The word in {language_a} meant {meaning_a}. {name} chose to translate it as {meaning_b}…",
            "Both sides trusted {name}. Neither side knew what {pronoun} left out…",
        ],
    ),

    "bureaucracy": LensContract(
        lens_id="bureaucracy",
        short_description="Administrative machinery — paper, stamps, signatures that determine fates",
        scene_priorities=[
            "Paper trail that seals or saves a fate",
            "Bureaucratic bottleneck with life-or-death stakes",
            "Individual discretion inside a rigid system",
            "The form that was never filed",
        ],
        tension_patterns=["bureaucratic maze", "moral trap", "time pressure", "anonymity"],
        preferred_artifacts=["government forms", "visa applications", "committee minutes", "filing records", "stamps and seals"],
        forbidden_moves=[
            "Making bureaucracy boring — every stamp is a decision",
            "Ignoring the human behind the desk",
        ],
        hook_templates=[
            "The application sat on {name}'s desk for {time}. One signature would change everything…",
            "The form had a box for '{field}'. There was no box for the truth…",
        ],
    ),

    # ── Limited-control observers ─────────────────────────────────────
    "pow": LensContract(
        lens_id="pow",
        short_description="Prisoners of war — captivity, resistance, and survival under detention",
        scene_priorities=[
            "Capture and disorientation",
            "Daily survival strategies",
            "Resistance or collaboration pressure",
            "Communication with outside world",
        ],
        tension_patterns=["claustrophobia", "info gaps", "moral trap", "time distortion"],
        preferred_artifacts=["camp records", "Red Cross reports", "escape plans", "prisoner diaries", "interrogation transcripts"],
        forbidden_moves=[
            "Glorifying captivity",
            "Inventing POW characters",
        ],
        hook_templates=[
            "On day {count}, {name} learned something about the guards that changed the equation…",
            "The Red Cross package arrived on {date}. Inside was {item} — and a message…",
        ],
    ),

    "journalists": LensContract(
        lens_id="journalists",
        short_description="War correspondents and journalists — reporting under constraint",
        scene_priorities=[
            "What the journalist saw vs what got published",
            "Censorship and self-censorship",
            "Relationship with military authorities",
            "The story that changed public perception",
        ],
        tension_patterns=["info gaps", "censorship", "moral trap", "exposure"],
        preferred_artifacts=["dispatches", "press credentials", "censor's marks", "published articles", "unpublished drafts"],
        forbidden_moves=[
            "Treating the journalist as omniscient narrator",
        ],
        hook_templates=[
            "{name} filed the story at {time}. The censor cut {detail} — the one thing the public needed to know…",
            "The photograph showed {visible}. What it didn't show was {hidden}…",
        ],
    ),

    "spies": LensContract(
        lens_id="spies",
        short_description="Intelligence networks — gathering, transmitting, and acting on secret information",
        scene_priorities=[
            "Information acquisition under cover",
            "Communication chain and its vulnerabilities",
            "Double identity and trust mechanics",
            "The moment intelligence becomes (or fails to become) action",
        ],
        tension_patterns=["info gaps", "dual identity", "time pressure", "exposure risk"],
        preferred_artifacts=["decoded messages", "agent files", "surveillance logs", "dead drop instructions", "debriefing transcripts"],
        forbidden_moves=[
            "Glamorising espionage — focus on tension and vulnerability",
            "Inventing agents or operations",
        ],
        hook_templates=[
            "{name} transmitted the message at {time}. {pronoun} had no way to know if anyone was listening…",
            "The intelligence was accurate. The question was whether it would arrive in time…",
        ],
    ),

    "diplomats": LensContract(
        lens_id="diplomats",
        short_description="Consular and diplomatic staff — negotiating, stalling, or failing between powers",
        scene_priorities=[
            "Negotiation under time pressure",
            "Gap between instructions from capital and reality on ground",
            "Personal risk for diplomatic staff",
            "The cable that arrived too late",
        ],
        tension_patterns=["time pressure", "info gaps", "dual loyalty", "bureaucratic maze"],
        preferred_artifacts=["diplomatic cables", "treaty drafts", "embassy logs", "personal correspondence"],
        forbidden_moves=[
            "Reducing diplomacy to a single handshake",
        ],
        hook_templates=[
            "The cable from {capital} said {instruction}. On the ground, {reality}…",
            "{name} had until {deadline} to prevent {consequence}. The phone line was dead…",
        ],
    ),

    # ── Combat-adjacent ───────────────────────────────────────────────
    "pilots": LensContract(
        lens_id="pilots",
        short_description="Pilots and air crews — altitude, exposure, and split-second decisions",
        scene_priorities=[
            "Pre-mission briefing and uncertainty",
            "In-flight decision under technical/tactical pressure",
            "Target-area reality vs briefing expectation",
            "Return (or failure to return)",
        ],
        tension_patterns=["time pressure", "exposure", "technical failure", "isolation"],
        preferred_artifacts=["mission logs", "flight plans", "debriefing transcripts", "cockpit recordings", "loss records"],
        forbidden_moves=[
            "Top Gun glamorisation",
            "Ignoring ground consequences of air operations",
        ],
        hook_templates=[
            "At {altitude} feet, {name} could see {visible}. What {pronoun} couldn't see was {hidden}…",
            "The fuel gauge read {amount}. The target was {distance} away…",
        ],
    ),

    "submariners": LensContract(
        lens_id="submariners",
        short_description="Submarine crews — confinement, silence, and pressure",
        scene_priorities=[
            "Confinement and crew dynamics",
            "Silent running — sound discipline under threat",
            "Technical failure in a sealed environment",
            "Surfacing — first contact with the outside",
        ],
        tension_patterns=["claustrophobia", "time pressure", "technical failure", "silence"],
        preferred_artifacts=["patrol logs", "sonar recordings", "crew manifests", "depth charge reports"],
        forbidden_moves=[
            "Hollywood submarine clichés",
        ],
        hook_templates=[
            "At {depth} metres, sound was the enemy. Then someone dropped a wrench…",
            "The air scrubbers had {time} of capacity left. The destroyer above wasn't leaving…",
        ],
    ),

    "artillery": LensContract(
        lens_id="artillery",
        short_description="Artillery crews and forward observers — distance between trigger and impact",
        scene_priorities=[
            "Calculation and preparation",
            "Communication chain from observer to gun",
            "Gap between mathematical precision and human reality at target",
            "The misfire, short round, or friendly fire incident",
        ],
        tension_patterns=["distance", "info gaps", "miscommunication", "moral weight"],
        preferred_artifacts=["fire mission logs", "observer reports", "trajectory calculations", "after-action damage assessments"],
        forbidden_moves=[
            "Reducing artillery to spectacle",
        ],
        hook_templates=[
            "The coordinates were {coords}. The target was {description}. The observer was {distance} away…",
        ],
    ),

    "tank_crews": LensContract(
        lens_id="tank_crews",
        short_description="Armoured vehicle crews — visibility limits, heat, and mechanical dependence",
        scene_priorities=[
            "Limited visibility — what the crew can and cannot see",
            "Mechanical failure under combat stress",
            "Crew coordination in a confined space",
            "The moment the armour is tested",
        ],
        tension_patterns=["claustrophobia", "visibility limits", "mechanical failure", "heat"],
        preferred_artifacts=["tank crew diaries", "maintenance logs", "combat reports", "vehicle loss records"],
        forbidden_moves=[
            "Tank-as-invincible-machine fantasy",
        ],
        hook_templates=[
            "Through the viewport, {name} could see {degrees} degrees of the world. The threat was in the other {remaining}…",
        ],
    ),

    "partisans": LensContract(
        lens_id="partisans",
        short_description="Underground networks and partisan fighters — secrecy, betrayal, and improvisation",
        scene_priorities=[
            "Cell structure and trust mechanics",
            "Improvised operation under resource constraint",
            "Betrayal risk and counter-intelligence",
            "Civilian relationships and exposure risk",
        ],
        tension_patterns=["exposure risk", "moral trap", "info gaps", "dual identity"],
        preferred_artifacts=["coded messages", "trial records", "resistance memoirs", "post-war testimonies", "occupation decrees"],
        forbidden_moves=[
            "Glorifying violence without showing cost",
            "Inventing resistance figures",
        ],
        hook_templates=[
            "Only three people knew about the operation. One of them was talking to the wrong side…",
            "{name} buried {item} under {location}. If found, it meant death for {count} people…",
        ],
    ),

    # ── Moral friction ────────────────────────────────────────────────
    "collaborators_resistance": LensContract(
        lens_id="collaborators_resistance",
        short_description="The spectrum between collaboration and resistance — grey zones",
        scene_priorities=[
            "First compromise and its justification",
            "Escalation of complicity",
            "Moment of moral reckoning",
            "Post-war accountability or erasure",
        ],
        tension_patterns=["moral trap", "dual identity", "exposure risk", "self-justification"],
        preferred_artifacts=["trial transcripts", "collaboration orders", "post-war testimonies", "purge records"],
        forbidden_moves=[
            "Binary good/evil framing",
            "Judging without showing the pressure",
        ],
        hook_templates=[
            "The first time, {name} told {pronoun_self} it was survival. By the {nth} time, {pronoun} had stopped explaining…",
        ],
    ),

    "defectors": LensContract(
        lens_id="defectors",
        short_description="Defectors and deserters — crossing lines that can't be uncrossed",
        scene_priorities=[
            "Decision point and what triggered it",
            "Physical act of crossing",
            "Reception on the other side — trust deficit",
            "Identity after defection — belonging nowhere",
        ],
        tension_patterns=["exposure risk", "moral trap", "identity crisis", "time pressure"],
        preferred_artifacts=["debriefing transcripts", "asylum records", "court-martial files", "memoirs"],
        forbidden_moves=[
            "Simple hero narrative — defection is always complicated",
        ],
        hook_templates=[
            "{name} had {time} to cross {boundary}. On the other side, nobody was expecting {pronoun}…",
        ],
    ),

    "enforcers": LensContract(
        lens_id="enforcers",
        short_description="Low-level enforcers — guards, police, minor officials who carry out orders",
        scene_priorities=[
            "The order and the moment of compliance",
            "Rationalisation and small resistances",
            "Witness to consequences of own actions",
            "Post-war reckoning or evasion",
        ],
        tension_patterns=["moral trap", "obedience pressure", "witness burden", "complicity"],
        preferred_artifacts=["duty rosters", "trial testimonies", "orders", "post-war depositions"],
        forbidden_moves=[
            "Sympathising with perpetrators without showing victims",
            "Inventing enforcers",
        ],
        hook_templates=[
            "The order was {order}. {name} carried it out. Years later, {pronoun} would say {quote}…",
        ],
    ),

    # ── Systems lenses ────────────────────────────────────────────────
    "command_failure": LensContract(
        lens_id="command_failure",
        short_description="Command-and-control failure — when the chain of command breaks",
        scene_priorities=[
            "The order as issued",
            "Distortion through communication chain",
            "Ground reality vs headquarters assumption",
            "Consequence of the gap",
        ],
        tension_patterns=["info gaps", "miscommunication", "cascading failure", "distance"],
        preferred_artifacts=["command logs", "radio transcripts", "after-action reports", "court of inquiry records"],
        forbidden_moves=[
            "Simple blame assignment — show the system, not just the person",
        ],
        hook_templates=[
            "The order left {headquarters} at {time}. By the time it reached {unit}, it said something different…",
            "Headquarters assumed {assumption}. On the ground, {reality}…",
        ],
    ),

    "technology": LensContract(
        lens_id="technology",
        short_description="Technology turning points — when new tools change the rules mid-conflict",
        scene_priorities=[
            "First deployment and unexpected effects",
            "Human adaptation to new technology",
            "Counter-measure and escalation cycle",
            "Ethical boundary created by new capability",
        ],
        tension_patterns=["technical surprise", "escalation", "moral boundary", "adaptation pressure"],
        preferred_artifacts=["technical reports", "field trial records", "operator manuals", "combat reports"],
        forbidden_moves=[
            "Tech fetishism — the focus is human consequence",
        ],
        hook_templates=[
            "The device was designed for {intended_use}. In the field, it did {actual_use}…",
            "Nobody had trained for {technology}. {name} was the first to face it…",
        ],
    ),

    "propaganda": LensContract(
        lens_id="propaganda",
        short_description="Propaganda and information warfare — the battle for narrative control",
        scene_priorities=[
            "Construction of the message",
            "Dissemination and reception",
            "Gap between propaganda and ground truth",
            "Long-term effect on belief and memory",
        ],
        tension_patterns=["info gaps", "credibility contest", "moral trap", "narrative control"],
        preferred_artifacts=["propaganda posters", "broadcast transcripts", "censorship directives", "public opinion surveys"],
        forbidden_moves=[
            "Treating propaganda as obviously false — it worked because it was persuasive",
        ],
        hook_templates=[
            "The poster said {message}. The soldiers who saw it knew {reality}…",
            "The broadcast reached {audience_size} people. {percentage} believed it…",
        ],
    ),

    # ── Aftermath ─────────────────────────────────────────────────────
    "trial": LensContract(
        lens_id="trial",
        short_description="Legal reckoning — trials, accountability, and the limits of justice",
        scene_priorities=[
            "Charges and the evidence marshalled",
            "Courtroom confrontation — accuser and accused",
            "Defense strategy and its implications",
            "Verdict and its reception — justice or inadequacy",
        ],
        tension_patterns=["moral trap", "credibility contest", "time pressure", "public spectacle"],
        preferred_artifacts=["trial transcripts", "indictments", "witness statements", "verdict documents", "press coverage"],
        forbidden_moves=[
            "Presenting verdict as simple closure",
        ],
        hook_templates=[
            "The prosecution had {evidence_count} pieces of evidence. The defense had one argument: {defense}…",
            "{name} entered the courtroom as {title}. {pronoun} would leave as {verdict}…",
        ],
    ),

    "reconstruction": LensContract(
        lens_id="reconstruction",
        short_description="Reconstruction and demobilisation — rebuilding from rubble",
        scene_priorities=[
            "Scale of destruction — what needs rebuilding",
            "First practical steps and resource constraints",
            "Social reconstruction — trust, identity, governance",
            "What was lost permanently",
        ],
        tension_patterns=["resource scarcity", "time pressure", "identity crisis", "political contest"],
        preferred_artifacts=["damage surveys", "reconstruction plans", "demobilisation records", "aid distribution logs"],
        forbidden_moves=[
            "Triumphalist rebuilding narrative — show what was permanently lost",
        ],
        hook_templates=[
            "Before the first brick could be laid, {name} had to answer a harder question: {question}…",
        ],
    ),

    "recovery": LensContract(
        lens_id="recovery",
        short_description="Recovery and missing persons — searching for the lost",
        scene_priorities=[
            "Disappearance and uncertainty",
            "Search process and bureaucracy of loss",
            "Discovery or permanent ambiguity",
            "Impact on those left searching",
        ],
        tension_patterns=["info gaps", "time distortion", "bureaucratic maze", "hope vs acceptance"],
        preferred_artifacts=["missing persons lists", "Red Cross tracing files", "exhumation records", "identification documents"],
        forbidden_moves=[
            "False closure — some searches never end",
        ],
        hook_templates=[
            "{name} last heard from {relative} on {date}. {years} later, {pronoun} was still looking…",
        ],
    ),
}


# ---------------------------------------------------------------------------
# Lookup and validation helpers
# ---------------------------------------------------------------------------

ALL_LENS_IDS: list[str] = sorted(LENS_REGISTRY.keys())


def get_lens(lens_id: str) -> Optional[LensContract]:
    """Return a lens contract by ID, or None if not found."""
    return LENS_REGISTRY.get(lens_id.lower().replace(" ", "_").replace("-", "_"))


def resolve_lenses(raw: str | list[str] | None) -> list[LensContract]:
    """Resolve a user-supplied lens spec into a list of LensContract objects.

    Accepts a single string, a comma-separated string, or a list.
    Unknown IDs are silently skipped (with a warning-level log).
    Returns empty list when input is None → backward-compatible default.
    """
    if raw is None:
        return []

    if isinstance(raw, str):
        ids = [s.strip() for s in raw.split(",") if s.strip()]
    else:
        ids = [s.strip() for s in raw if s.strip()]

    result: list[LensContract] = []
    for lid in ids:
        contract = get_lens(lid)
        if contract:
            result.append(contract)
    return result


# ---------------------------------------------------------------------------
# Prompt-building helpers — called by nodes to inject lens context
# ---------------------------------------------------------------------------

def build_lens_prompt_block(
    lenses: list[LensContract],
    strength: float = 0.6,
) -> str:
    """Build a prompt block that tells the LLM how to apply the selected lenses.

    Returns empty string when no lenses are active → zero impact on existing prompts.
    """
    if not lenses:
        return ""

    strength = max(0.0, min(1.0, strength))
    intensity = (
        "lightly" if strength < 0.3
        else "moderately" if strength < 0.7
        else "strongly"
    )

    parts = [
        "\n\n--- NARRATIVE LENS INSTRUCTIONS ---",
        f"Lens strength: {strength:.1f} (apply {intensity})",
        f"Active lens(es): {', '.join(l.lens_id for l in lenses)}",
        "",
        "RULES FOR ALL LENSES:",
        "- Lenses bias emphasis, scene selection, and re-hook design — they NEVER override facts.",
        "- NEVER invent fictional internal thoughts to satisfy a lens.",
        "- NEVER suppress uncertainty labelling to make a lens work.",
        "- If multiple lenses are active, blend coherently — avoid POV whiplash.",
        "  Prioritise tension-producing combinations. Do NOT alternate randomly.",
        "",
    ]

    for lens in lenses:
        parts.append(f"### Lens: {lens.lens_id} — {lens.short_description}")
        parts.append(f"Scene priorities (ranked): {', '.join(lens.scene_priorities)}")
        parts.append(f"Tension patterns: {', '.join(lens.tension_patterns)}")
        parts.append(f"Preferred artifacts: {', '.join(lens.preferred_artifacts)}")
        parts.append(f"Forbidden moves: {'; '.join(lens.forbidden_moves)}")
        parts.append(f"Hook templates (for inspiration, not verbatim): {'; '.join(lens.hook_templates[:2])}")
        parts.append("")

    parts.append("--- END LENS INSTRUCTIONS ---\n")
    return "\n".join(parts)
