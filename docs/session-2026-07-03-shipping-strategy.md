# Session Notes — 2026-07-03: Why Adquest Works & Shipping Strategy

## Why Traditional Tools Failed

| Tool | Failure mode |
|------|-------------|
| Todo apps (generic) | Separate app = context switch = lost attention |
| Notion / Evernote | Too much structure overhead to maintain |
| Habitica | UI friction on adding/completing tasks (clicks, navigation, forms) |
| Google Tasks | Actually worked — because it was embedded in communication flow (Google Chat). No context switch needed. |

## Why Adquest Works

The core insight: **friction to access** matters more than features.

1. **Zero context switch** — CLI lives where I already am (terminal, next to code, next to AI agent)
2. **No app-switching** — checking every 5 min is only sustainable if checking costs ~0 effort
3. **Natural language input via AI** — don't need to remember commands, just prompt it
4. **RPG dopamine** — gamification gives small reward hit on completion (novelty + immediate feedback)
5. **5-minute attention reset** — brain naturally cycles back to "what am I doing?" and there's a frictionless answer RIGHT THERE

### The Google Tasks Principle

Google Tasks worked because it was *inside* the tool I was already using. Adquest replicates that same principle for my current workflow: terminal + AI agent.

### ADHD Need → How Adquest Solves It

| Need | Solution |
|------|----------|
| Minimal activation energy | CLI = already open |
| Immediate reward | RPG progression |
| No context switch | Same terminal as work |
| Low friction input | AI handles command syntax |
| Frequent re-anchoring | Trivial to check every 5 min |
| Urgency/visibility | Always in your face, not buried in an app |

---

## Shipping as Open Source

### Motivation
- Not driven by monetization (would trigger perfectionism block)
- Driven by: sharing, feedback, potential contributors
- OSS culture aligns with "ship early, iterate" — removes perfectionism trap

### Why OSS is the right model for me

- Issues/PRs/feature requests = constant new problems to solve (novelty)
- Stars and "this changed my life" comments = dopamine
- Community using it = healthy urgency to maintain (can't abandon)
- No "is this good enough to charge for?" blocker
- Portfolio piece showing architecture thinking + product sense
- I become the architect/maintainer, not the CRUD monkey

### Market validation
- ~5-7% of adults globally have ADHD (350-500M people)
- ~1.4M developers with ADHD conservatively
- "ADHD + dev tools" content consistently hits front page on HN/Reddit
- No CLI-native RPG task manager exists (that I'm aware of)
- Habitica proved gamification works but fails on friction

---

## Branding Decision

**Will NOT brand as "designed for ADHD"** because:
- Not professionally diagnosed yet
- Don't want "are you qualified?" discourse distracting from the tool
- Wider appeal without the label — neurotypical devs also hate todo apps
- ADHD community will self-identify ("holy shit this works for my brain")

**Better framing:**
> "A CLI-based RPG task manager for people who hate task managers."
> "Built for devs who live in their terminal and need zero-friction task tracking."

Personal story can mention traditional tools never worked without making clinical claims.

### Validation path:
1. Ship with honest framing ("built for myself, sharing it")
2. Find 3-5 diagnosed ADHD people to try it
3. Collect organic feedback
4. If confirmed → "people with ADHD report this works well" (evidence-based, not self-claimed)

### Where to share:
- r/adhdprogrammers — "looking for feedback"
- Hacker News — "Show HN: CLI RPG task manager for people who hate task managers"
- Twitter/X dev community — demo GIF + personal story
- r/commandline, r/unixporn

---

## Competitor Research — Intentionally Avoided

**Decision:** not looking at similar tools right now.

**Why:**
- Current motivation is intrinsic (enjoying the build). Seeing a "better" version would kill it.
- Comparison → "why bother" → abandoned project. Classic project death.
- My tool works for me because it was built around me. No existing tool has that advantage.
- OSS thrives on alternatives. 50 static site generators exist. Another one is fine.

**When to look (later):**
- After shipping and having real users
- When deciding what to build next (features)
- When someone asks "how is this different from X?" in issues

---

## Next Steps (when ready)

- [ ] Write README with personal story (the "why")
- [ ] Add install instructions
- [ ] Add basic usage examples
- [ ] Choose license (MIT)
- [ ] Ship. Ugly is fine. Incomplete is fine. TODOs in code is fine.

Frame it as sharing, not launching. Low stakes.
