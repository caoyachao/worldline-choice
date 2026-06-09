# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Worldline Choice (世界线·抉择) is an AI-driven interactive narrative game engine using LLM + d20 check hybrid architecture.

**Current Version**: 4.6.0 - DC Calibration & Reward Edition

This is a pure-Python project with no external dependencies.

## Common Commands

- **Run all tests**: `python3 test_llm_skill.py`
- **Run specific test**: `python3 test_llm_skill.py test_d20_engine`
- **Start CLI mode**: `python3 worldline_skill.py` or `./worldline_choice.sh`
- **Start new game (CLI)**: `python3 worldline_engine.py --new "world_setting" "role" "name"`
- **List saves**: `python3 worldline_engine.py --list`
- **Load save**: `python3 worldline_engine.py --load <save_id>`

## Architecture (v4.6.0 - DC Calibration & Reward)

### Core Design Philosophy

**Separation of Concerns**:
1. **LLM** handles: Intent understanding, DC assessment, narrative generation (based on dice results)
2. **d20 engine** handles: Objective success/failure determination (mandatory via `execute_check`)
3. **Game engine** handles: State management, rule enforcement, turn settlement (HP/money/status effects), narrative validation
4. **Tactical system** handles: Preparation benefits, NPC assistance, scene object interactions

**Character Growth System (v4.5.0)**:
- HP system (0-100), death detection
- Resources (gold, reputation, etc.) with per-turn settlement
- Inventory with capacity limit (consumables/equipment/special items)
- Status effects (buffs/debuffs) with tick decay
- Attribute growth audit log (history of every change with reason)
- Per-turn money settlement based on world setting

**Mandatory d20 Check Principle**:
- LLM **MUST** call `execute_check` tool to get dice results
- LLM is **PROHIBITED** from inventing dice results
- Narrative generation **REQUIRES** `check_result` parameter
- Dice results are absolute and cannot be overridden narratively

### File Structure

**`worldline_skill.py`** — Core skill implementation (v4.5.0):
- `WorldlineSkill` — Main game controller with tactical enhancement APIs, turn settlement, character growth
- `D20Engine` — Pure code dice rolling (no LLM involvement)
- `GameState` — Game state with HP, resources, inventory, status effects, attribute history, money per turn
- `LLMDriver` — Intent analysis, narrative generation, option generation
- Tactical APIs: `set_scene_objects()`, `execute_npc_check()`, `add_active_benefit()`, `calculate_effective_dc()`
- Growth APIs: `settle_turn()` (HP/status/money settlement), `update_attribute()` (with audit log)

**`worldline_engine.py`** — Backward compatibility layer:
- `WorldlineEngine` — Wraps `WorldlineSkill` with legacy API compatibility
- Handles save migration from v3.x to v4.x format
- CLI entry point with `--new`, `--load`, `--list` commands

**`openclaw_adapter.py`** — OpenClaw integration:
- `OpenClawAdapter` — Wraps skill for OpenClaw runtime
- Tool definitions matching `skill.json`

**`skill.json`** — OpenClaw skill manifest with tool schemas

### Key Constraint: Mandatory d20 Check Execution

**Strict Enforcement Rules**:
1. **LLM MUST call `execute_check` tool** - Self-invented dice results are prohibited
2. **Narrative generation requires `check_result` parameter** - No narrative without dice
3. **Dice results are absolute** - LLM cannot "soften" failures or "enhance" successes narratively
4. **Validation prompts** include checklists ensuring narrative fidelity to dice results

The prompt system includes explicit "red line" prohibitions:
- ❌ Using "but", "however", "unexpectedly" to reverse outcomes
- ❌ Describing failures as "almost succeeded" or "close calls"
- ❌ Adding compensatory benefits to failed rolls
- ❌ Generating result-oriented narratives before dice execution

### Tactical Enhancement System (v4.3.0)

Three new mechanics enable strategic depth through "benefit chains":

1. **Preparation Actions**: Players can spend turns setting up advantages (e.g., observing environment, laying traps)
2. **NPC Assistance**: Allied NPCs can attempt checks to grant players advantage on subsequent turns
3. **Scene Objects**: Interactive environmental elements can provide DC modifiers when utilized

**Active Benefit Lifecycle**:
```
Player/NPC succeeds at preparation action
    ↓
Engine calls `add_active_benefit()` with DC modifier/advantage/usage count
    ↓
On subsequent turns, `process_turn()` automatically applies matching benefits
    ↓
Benefit is consumed when used (or expires after specified uses)
```

**Tactical APIs**:
- `set_scene_objects(objects)` — Define interactable scene elements with potential benefits
- `interact_with_scene_object(object_id, player_input)` — Player attempts to use an object
- `execute_npc_check(npc_name, action, attribute, dc)` — NPC attempts assist action
- `add_active_benefit(...)` — Manually register a tactical benefit
- `calculate_effective_dc(base_dc, attribute)` — Compute DC after applying all active benefits

### d20 Check System

- Formula: `d20 + (attribute - 10) // 2 >= DC`
- Result degrees: 大成功 / 成功 / 勉强成功 / 勉强失败 / 失败 / 大失败
- Natural 20 = critical success; natural 1 = critical failure
- Advantage/disadvantage supported via `advantage`/`disadvantage` parameters

### Attributes

Six universal attributes used across all world settings:
- `FORCE` — Combat, physical power
- `MIND` — Intellect, technology, magic
- `INFLUENCE` — Social, persuasion, leadership
- `REFLEX` — Stealth, agility, reaction
- `RESILIENCE` — Constitution, willpower
- `LUCK` — Fortune, coincidence

### Game Flow

```
Player Input
    ↓
LLM Analysis → ActionAnalysis (intent, DC, attribute)
    ↓
calculate_effective_dc() ← Apply active_benefits
    ↓
d20 Roll → CheckResult (objective success/failure)
    ↓
LLM Narrative Generation (based on dice result)
    ↓
Apply Consequences → Update State
    ↓
(If preparation action) → add_active_benefit()
```

### Running Modes

**1. CLI Mode** (`python3 worldline_skill.py` or `./worldline_choice.sh`):
```python
skill = WorldlineSkill()
skill.start_game("武侠", "剑客", "李逍遥")
# Set up scene objects for tactical play
skill.set_scene_objects([{
    "id": "chandelier",
    "name": "吊灯",
    "description": "摇摇欲坠的古老吊灯",
    "interaction_hint": "可以试着割断绳索制造混乱",
    "benefit": {"dc_modifier": -3, "applies_to": ["REFLEX"]}
}])
result = skill.process_turn("我尝试与店主交谈")
```

**2. OpenClaw Mode**:
```python
from openclaw_adapter import create_skill
adapter = create_skill(openclaw_llm_call)
adapter.start_game("赛博朋克", "黑客", "V")
```

### Save Format

v4.3.0 format with tactical data:
```json
{
  "version": "4.6.0",
  "world_setting": "武侠",
  "player": {
    "name": "李逍遥",
    "attributes": {"FORCE": 12, "MIND": 14, ...},
    "items": ["长剑", "干粮"]
  },
  "active_benefits": [
    {"name": "埋伏就绪", "dc_modifier": -3, "advantage": false, "remaining_uses": 1}
  ],
  "scene_objects": [...],
  "npc_assist_log": [...],
  "history": [...],
  "turn_count": 15
}
```

Save location: `~/.claude/skills/worldline_choice/saves/`

### Testing

- `test_llm_skill.py` — Tests for v4.3.0 architecture including tactical system
- `test_engine.py` — Legacy backward compatibility tests

Key test scenarios:
- d20 randomness and distribution
- Active benefit application and consumption
- NPC assist check flow
- Scene object interaction
- Save/load with tactical data

### Migration from v3.x

v3.x saves can be loaded via `worldline_engine.py` and are automatically converted:
- Rich fields (npc_database, session_history) flattened
- Attribute names mapped to 6 universal dimensions
- Tactical fields initialized empty

### Extending

To add new tactical mechanics:
1. Extend `GameState` with new tactical fields
2. Add management methods to `WorldlineSkill`
3. Update `process_turn()` to check and apply new modifiers
4. Update `skill.json` with new tool definitions
5. Update `openclaw_adapter.py` with new tool handlers
