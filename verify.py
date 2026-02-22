"""Quick verification script."""
import sys
sys.path.insert(0, "/Users/OmarBaher1/history-tales-script-generator")

print("1. Testing state models...")
from history_tales_agent.state import AgentState, TopicCandidate, Claim, QCReport
print("   ✅ State OK")

print("2. Testing config...")
from history_tales_agent.config import SCORING_WEIGHTS, ALL_FORMAT_TAGS
print(f"   ✅ Config OK — formats: {ALL_FORMAT_TAGS}")

print("3. Testing scoring...")
from history_tales_agent.scoring.topic_scorer import score_topic, rank_candidates
c = TopicCandidate(
    title="Test Topic", one_sentence_hook="Hook", era="WW2",
    geo="Europe", core_pov="Soldier", timeline_window="24 hours",
    twist_points=["a", "b", "c"],
)
r = score_topic(c, {
    "hook_curiosity_gap": 9, "stakes": 9, "timeline_tension": 9,
    "cliffhanger_density": 8, "human_pov_availability": 9,
    "evidence_availability": 9, "novelty_angle": 8,
    "controversy_defensible": 7, "sensitivity_fit": 9,
})
print(f"   ✅ Scoring OK — score: {r['final_score']}, status: {r['status']}")

print("4. Testing source registry...")
from history_tales_agent.research.source_registry import get_credibility_score, is_allowed_source
assert get_credibility_score("https://www.loc.gov/item/123") == 0.95
assert is_allowed_source("https://en.wikipedia.org/wiki/Test") == True
assert is_allowed_source("https://infowars.com/article") == False
print("   ✅ Source registry OK")

print("5. Testing prompt templates...")
from history_tales_agent.prompts.templates import get_tone_instructions, TOPIC_DISCOVERY_SYSTEM
assert len(get_tone_instructions("cinematic-serious")) > 50
print("   ✅ Prompts OK")

print("6. Testing graph compilation...")
from history_tales_agent.graph import compile_graph
graph = compile_graph()
nodes = list(graph.get_graph().nodes.keys())
print(f"   ✅ Graph compiled — {len(nodes)} nodes: {nodes}")

print("7. Testing CLI parser...")
from history_tales_agent.main import main
print("   ✅ CLI OK")

print()
print("=" * 50)
print("ALL TESTS PASSED ✅")
print("=" * 50)
