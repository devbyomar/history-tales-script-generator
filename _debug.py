"""Quick debug script for failing tests."""
import re

# Test 1: "order stood" matches personification
pat = re.compile(
    r"\b(?:Silence|Fear|Death|Time|History|War|Peace|Truth|Darkness|"
    r"Doubt|Hope|Memory|Grief|Shame|Guilt|Rage|Fury|Despair|"
    r"Chaos|Order|Fate|Justice|Freedom|Power)\s+"
    r"(?:carried|held|whispered|spoke|watched|waited|crept|settled|"
    r"lingered|descended|hung|pressed|wrapped|consumed|devoured|"
    r"gripped|seized|embraced|clung|weighed|bore|stretched|loomed|"
    r"arrived|moved|stood|sat)\b",
    re.IGNORECASE,
)
text = "Nobody spoke. The order stood."
m = [x.group() for x in pat.finditer(text)]
print("Test 1 matches:", m)

# Test 2: clause chain
text2 = (
    "Across the frozen steppe, through columns of smoke, past the "
    "wreckage of a dozen villages, beyond the river crossing, the "
    "convoy pressed forward into the unknown darkness ahead."
)
sentences = re.split(r"(?<=[.!?])\s+", text2)
print("\nTest 2 sentences:", len(sentences))
for s in sentences:
    print(f"  commas={s.count(',')}, words={len(s.split())}")

# Test 3: fact repetition 4-grams
text3 = (
    "seventeen escape attempts were recorded. "
    "Later seventeen escape attempts were documented. "
    "In total seventeen escape attempts occurred."
)
_stopwords = {
    "the", "a", "an", "of", "and", "in", "at", "on", "to", "for",
    "by", "is", "was", "are", "were", "has", "had", "have", "will",
    "would", "but", "or", "not", "it", "he", "she", "they", "we",
    "his", "her", "its", "their", "our", "this", "that", "from",
    "with", "into", "be", "been", "as", "which", "who", "whom",
}
words = [w.lower().strip('.,;:!?"\'()[]—–-') for w in text3.split()]
content_words = [w for w in words if w and w not in _stopwords and len(w) > 2]
print("\nTest 3 content words:", content_words)
for i in range(len(content_words) - 3):
    gram = tuple(content_words[i : i + 4])
    print(f"  {gram}")
