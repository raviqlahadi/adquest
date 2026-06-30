# SPEC.md — adquest Design Specification

## 1. Data Model

### state.json

```json
{
  "level": 1,
  "title": "Apprentice of the Forge",
  "xp": 0,
  "xp_next": 100,
  "hp": 100,
  "mp": 100,
  "streak": 0,
  "last_quest_date": null,
  "quests": {},
  "chains": {},
  "history": [],
  "buffs": [],
  "achievements": []
}
```

### Quest Object

```json
{
  "desc": "string",
  "xp": 10,
  "status": "active|done",
  "type": "main|side",
  "focus": false,
  "parent": null,
  "children": [],
  "chain": null,
  "created": "ISO8601",
  "completed": null
}
```

- `type`: Quest category. `"main"` for work/priority quests, `"side"` for personal/optional. Default: `"main"`. Existing quests without this field are treated as `"main"`.
- `focus`: Whether the quest is currently being worked on. Max 3 focused quests at a time. Default: `false`.

### Chain Object

```json
{
  "name": "string",
  "quests": ["Q1", "Q2", "Q3"],
  "current": 0
}
```

## 2. ID Assignment

- Top-level quests: `Q{n}` where n = max existing top-level ID + 1
- Sub-quests: `Q{parent}.{n}` where n = len(parent.children) + 1
- IDs are string keys in the `quests` dict

## 3. Command Specifications

### `quest "desc" [--xp N] [--type main|side]`
1. Compute next available Q-ID
2. Create quest object with status "active", type from flag (default "main")
3. Save state
4. Print: `⚔️  Quest Q{n} added: {desc} [+{xp} XP]` (or 🌙 for side quests)

### `sub Q{n} "desc" [--xp N]`
1. Validate parent exists and is active
2. Compute sub-ID (Q{n}.{m})
3. Create quest object with parent reference; inherit `type` from parent
4. Append sub-ID to parent's children list
5. Print: `📜 Sub-quest Q{n}.{m} added under Q{n}`

### `done Q{id}`
1. Validate quest exists and is active
2. If quest is in a chain, verify it's the current step
3. Mark status = "done", set completed timestamp
4. Award XP, check for level-up
5. If parent exists and all siblings done → auto-complete parent (+5 bonus XP)
6. If in chain → advance chain.current
7. Update last_quest_date (for streak tracking)
8. Print XP award, level-up fanfare if applicable

### `quests`
1. Iterate top-level quests (parent == null, status == "active")
2. Split into main and side categories by `type` field
3. Print each category with header: `⚔️ Main Quests` / `🌙 Side Quests`
4. Focused quests show 🔶 icon and [FOCUS] tag; others show ⬜
5. Show sub-quests indented under parents
6. Show chain indicators if applicable

### `focus Q{id}`
1. Validate quest exists and is active
2. Check focus count < 3 (ADHD guard rail)
3. Set quest.focus = true
4. Print: `🔶 Q{id} is now in focus: {desc}`

### `unfocus Q{id}`
1. Validate quest exists and is focused
2. Set quest.focus = false
3. Print: `⬜ Q{id} unfocused: {desc}`

### `status`
1. Print character sheet:
   - Level, title
   - XP bar (current/next)
   - HP/MP bars
   - Streak (with fire emoji scaling)
   - Active buffs (if any)
   - Focused quests (if any) with 🔶 icon

### `drain <hp> <mp> "reason"`
1. Deduct HP and MP (floor at 0)
2. Print: `💀 Drained: -{hp} HP, -{mp} MP ({reason})`
3. Warning if HP or MP below 20

### `rest <activity>`
1. Lookup activity in config presets
2. Apply HP/MP changes (+ is additive, = is set-to, cap at 100)
3. Print: `🧪 {activity}: +{hp} HP, +{mp} MP`

### `log`
1. Collect all quests with status "done" and completed date == today
2. Append to `~/.adquest/logs/log-YYYY-MM-DD.md`
3. Format as markdown checklist
4. Remove logged quests from active state
5. Move to history array (keep last 50)

### `chain "name" Q1 Q2 Q3`
1. Validate all quest IDs exist
2. Create chain object with current=0
3. Store in state.chains
4. Tag each quest's chain field
5. Print: `🔗 Chain "{name}": Q1 → Q2 → Q3`

### `newday`
1. Check if any quests were completed on last_quest_date
   - If yes → streak += 1
   - If no → streak = 0 (broken)
2. Reset HP = 100, MP = 100
3. Carry over incomplete quests as-is
4. Print day summary with streak status

## 4. Level-Up Mechanics

```
Level table (from config.json):
L1: 100 XP → L2
L2: 150 XP → L3
...
L9: 1000 XP → L10
L10: ∞ (max level)
```

On level-up:
1. xp resets to 0 (overflow carries: if 15 XP over threshold, xp = 15)
2. xp_next = next level's requirement
3. title updates
4. Print fanfare: banner, new title, emoji explosion

## 5. Output Formatting

- All output uses ANSI escape codes for color
- Bars rendered with unicode block characters: `█░`
- Color scheme:
  - Green: success, XP gain, level-up
  - Red: drain, low HP/MP warning
  - Yellow: streak, chains
  - Cyan: status info
  - Magenta: quest completion

## 6. Error Handling

- Invalid quest ID → "Quest {id} not found"
- Quest already done → "Quest {id} already completed"
- Chain ordering violation → "Quest {id} is blocked — complete {prev} first"
- Unknown rest activity → "Unknown activity. Available: ..."
- Missing args → argparse handles with usage message

## 7. Implementation Task Breakdown

1. **Scaffold** — argparse setup with all subcommands, state load/save helpers
2. **State management** — init_state(), load_state(), save_state(), ensure dirs
3. **Quest commands** — quest, sub, done (core loop)
4. **Display commands** — quests (tree view), status (character sheet)
5. **Energy system** — drain, rest (with config lookup)
6. **Workflow commands** — log, chain, newday
7. **Output formatting** — color helpers, bars, fanfare
8. **Config bootstrap** — default config.json with presets and level table

Implementation order: 7 → 2 → 1 → 3 → 4 → 5 → 6 → 8
(Output helpers first since everything uses them)
