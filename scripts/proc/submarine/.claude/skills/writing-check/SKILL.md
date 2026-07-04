---
name: writing-check
description: Check a LaTeX file for common writing pet peeves based on Margo Seltzer's writing guidelines
argument-hint: "[file-path]"
---

Read the file at `$ARGUMENTS` and check it against the writing pet peeves listed below. For each violation found, report:

1. The line number and the offending text
2. Which rule it violates
3. A suggested fix

Group violations by rule. At the end, provide a summary count of violations per rule.

Only report clear violations -- do not flag ambiguous cases. Focus on the prose text, not LaTeX commands, labels, or comments.

## Writing Pet Peeves (from Margo Seltzer)

### 1. References as nouns

Never use citations as the subject of a sentence. Write "Smith et al. show that X [1]" not "In [1], X is shown." The reader should never have to look at the bibliography to parse a sentence.

### 2. Which vs. that

Use **"that"** for restrictive (essential) clauses and **"which"** (preceded by a comma) for non-restrictive (parenthetical) clauses. If the clause can be removed without changing the meaning, use ", which". If it's essential to the meaning, use "that" with no comma.

### 3. Placement of "only"

Place "only" immediately before the word or clause it modifies. "We only run three experiments" (implies we don't do anything else with them) vs. "We run only three experiments" (implies the number is small).

### 4. Comma separating predicates

Do not put a comma between two predicates that share the same subject. "We build a system, and evaluate it" is wrong -- remove the comma.

### 5. Laundry lists of references

Do not dump multiple citations without context, e.g., "Many systems have addressed this problem [1,2,3,4,5]." Instead, briefly describe each reference's contribution.

### 6. Avoid "very"

Delete "very" or replace with a stronger word. "Very large" -> "enormous". "Very important" -> "critical".

### 7. Avoid "attempts" / hedging

Don't say "This paper attempts to..." or "We try to...". State what the work **does**. "We present..." not "We attempt to present..."

### 8. Passive voice

Prefer active voice. "We designed the system" not "The system was designed." Passive voice is acceptable when the actor is irrelevant or unknown.

### 9. Don't write mystery novels

State results and contributions upfront (especially in abstracts and introductions). Don't build suspense.

### 10. Fewer vs. less

Use **"fewer"** for countable nouns (fewer threads, fewer errors). Use **"less"** for uncountable nouns (less memory, less time).

### 11. Like vs. such as

Use **"such as"** when giving actual examples. Use **"like"** only for inexact comparisons. "Mechanisms such as containers and VMs" not "Mechanisms like containers and VMs."

### 12. Avoid "impact" (as a verb)

Use "affect" or "effect" instead. "This impacts performance" -> "This affects performance."

### 13. Avoid "seeks to" / "aims to"

Be direct. "We build..." not "We seek to build..." or "We aim to build..."

### 14. Replace "and so" with "so"

"And so we conclude..." -> "So we conclude..." (or better, just "We conclude...")

### 15. Figures illustrate; people visualize

Say "Figure 3 illustrates..." or "Figure 3 shows..." Never say "Figure 3 visualizes..."

### 16. Avoid "argue"

Use "point out", "note", or "observe" instead. "We argue" sounds adversarial.

### 17. Run spell check

Flag obvious typos and misspellings in prose (not in commands/identifiers).

### 18. Lead with claims, then explain

Present the main point first, then the reasoning. "X is better because Y" not "Because of Y, X is better."

### 19. Composed of vs. comprises

Big things are **composed of** small things. Small things **comprise** big things. "The system comprises three modules" or "The system is composed of three modules." Never say "comprised of."

### 20. Avoid "incentivize"

Rephrase to avoid this word. "This encourages..." or "This motivates..."

### 21. Avoid "This is because"

Combine sentences: "X happens because Y" instead of "X happens. This is because Y."

### 22. May vs. can vs. might

"May" = permission. "Can" = ability. "Might" = possibility. Be precise.

### 23. The Four C's

Overall, writing should be: **Concise, Crisp, Clear, and Correct**.

### 24. Avoid em-dashes

Do not use em-dashes (`---` in LaTeX). Replace with a comma, colon, semicolon, or parentheses depending on the context. Em-dashes are informal and interrupt flow.
