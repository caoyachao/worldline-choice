# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Worldline Choice (世界线·抉择) is an AI-driven interactive narrative game engine.

**Current Version**: 4.0.0 - LLM驱动 + d20检定混合架构

This is a pure-Python project with no external dependencies.

## Common Commands

- **Run legacy tests**: `python3 test_engine.py`
- **Run new skill tests**: `python3 test_llm_skill.py`
- **Start CLI mode**: `python3 worldline_skill.py`
- **Test OpenClaw adapter**: `python3 openclaw_adapter.py`

## Architecture (v4.0.0 - LLM Driven)

### Core Design Philosophy

**Separation of Concerns**:
1. **LLM** handles: Intent understanding, DC assessment, narrative generation
2. **d20 engine** handles: Objective success/failure determination
3. **Game engine** handles: State management, rule enforcement

This architecture eliminates hardcoded keyword matching while maintaining objective game mechanics.

### File Structure

**`worldline_skill.py`** — Core skill implementation:
- `WorldlineSkill` — Main game controller
- `D20Engine` — Pure code dice rolling (no LLM involvement)
- `LLMDriver` — Abstract interface for LLM calls
- `GameState` — Simplified state management

**`openclaw_adapter.py`** — OpenClaw integration:
- `OpenClawAdapter` — Wraps skill for OpenClaw runtime
- `create_skill()` — Factory function for OpenClaw
- Tool definitions for OpenClaw function calling

**`skill.json`** — OpenClaw skill manifest with tool schemas

**Legacy files** (maintained for backward compatibility):
- `worldline_engine.py` — v3.3.2 legacy engine
- `save_manager.py` — Standalone save manager
- `test_engine.py` — Legacy tests

### Game Flow

```
Player Input
    ↓
LLM Analysis → ActionAnalysis (intent, DC, attribute)
    ↓
Pre-condition Check (items, knowledge)
    ↓
d20 Roll → CheckResult (objective success/failure)
    ↓
LLM Narrative Generation (based on dice result)
    ↓
Apply Consequences → Update State
```

### Key Constraint: LLM Cannot Override Dice

The LLM is explicitly prompted to:
- Analyze intent and suggest DC **before** rolling
- Generate narrative **only after** seeing the dice result
- Never "adjust" a failure into success narratively

### d20 Check System

- Formula: `d20 + (attribute - 10) // 2 >= DC`
- Result degrees: 大成功 / 成功 / 勉强成功 / 勉强失败 / 失败 / 大失败
- Natural 20 = critical success; natural 1 = critical failure
- No DC modifiers from previous results (simplified from v3.3.2)

### Attributes

Six universal attributes used across all world settings:
- `FORCE` — Combat, physical power
- `MIND` — Intellect, technology, magic
- `INFLUENCE` — Social, persuasion, leadership
- `REFLEX` — Stealth, agility, reaction
- `RESILIENCE` — Constitution, willpower
- `LUCK` — Fortune, coincidence

### Running Modes

**1. CLI Mode** (`python3 worldline_skill.py`):
```python
skill = WorldlineSkill()
skill.start_game("武侠", "剑客", "李逍遥")
result = skill.process_turn("我尝试与店主交谈")
```

**2. OpenClaw Mode**:
```python
from openclaw_adapter import create_skill
adapter = create_skill(openclaw_llm_call)
adapter.start_game("赛博朋克", "黑客", "V")
```

**3. Hybrid Mode** (LLM for analysis, code for dice):
```python
# LLM analyzes intent
analysis = llm.analyze_action("hack the system", state)

# Code executes dice
result = D20Engine.execute_check(
    attribute_value=state.player['attributes']['MIND'],
    dc=analysis.base_dc
)

# LLM generates narrative
narrative = llm.generate_narrative(action, analysis.intention, result, world)
```

### Save Format

Simplified v4.0.0 format:
```json
{
  "version": "4.0.0-llm-driven",
  "world_setting": "武侠",
  "player": {
    "name": "李逍遥",
    "attributes": {"FORCE": 12, "MIND": 14, ...},
    "items": ["长剑", "干粮"]
  },
  "history": [...],
  "turn_count": 15,
  "flags": {"met_master": true}
}
```

### Testing

- `test_llm_skill.py` — Tests for new LLM-driven architecture
- `test_engine.py` — Legacy tests for backward compatibility

Key test scenarios:
- d20 randomness and distribution
- LLM analysis (with mock)
- State serialization
- Multi-world setting compatibility
- LLM/dice separation (verifying dice results are objective)

### Migration from v3.x

v3.x saves can be loaded but will be converted to v4 format:
- Rich fields (npc_database, session_history) flattened
- Complex tactical checks simplified
- Focus on single-action turns

### Extending

To add new world setting support:
1. No code changes needed (LLM understands any setting)
2. Update `world_setting` parameter in `start_game()`
3. LLM automatically adapts DC assessment and narrative style

To customize mechanics:
1. Modify `LLMDriver._build_analysis_prompt()` for DC logic
2. Modify `D20Engine.execute_check()` for dice mechanics
3. State management in `GameState`
