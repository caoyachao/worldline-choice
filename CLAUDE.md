# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Worldline Choice (世界线·抉择) is an AI-driven interactive narrative game engine (v3.3.2). It is a pure-Python project with no external dependencies.

## Common Commands

- **Run tests**: `python3 test_engine.py`
- **Start a new game via CLI**: `python3 worldline_engine.py --new "赛博侦探" "黑客" "V"`
- **Load a save via CLI**: `python3 worldline_engine.py --load <save_id>`
- **Run dice check**: `python3 dice_roller.py <attribute_value> <dc> [attribute_name] [context]`
- **Run game engine with a save file**: `python3 game_engine.py /path/to/save.json`

## High-Level Architecture

### Engine Design

The codebase uses a single engine implementation:

**`worldline_engine.py`** — v3.3.2 monolithic engine containing:
- `GameState` — Manages player, NPCs, flags, history, milestones, and difficulty bias. Now includes rich structured fields for compatibility with `save_manager.py` schema.
- `UniversalChallengeEngine` — Parses actions, calculates DC, executes d20 checks, detects narrative cheese, and handles tactical multi-step evaluation with v3.3.2 anti-abuse mechanics.
- `WorldlineEngine` — High-level wrapper that initializes worlds, generates AI prompts, processes actions, and manages save/load.

**`save_manager.py`** — Standalone save format manager:
- `WorldlineSaveManager` manages a structured JSON save format with `metadata`, `world_state`, `player` (attributes include auto-computed `modifier`), `session_history`, `npc_database` (each NPC has a `relationship_matrix.towards_player` with dimensions like `trust`, `respect`, `fear`), `active_quests`, `inventory`, and `story_flags`.
- `worldline_engine.py` now embeds this schema internally; saves are compatible with both systems.

### d20 Check System

- Formula: `d20 + (attribute - 10) // 2 >= DC`
- Result degrees: 大成功 / 成功 / 勉强成功 / 勉强失败 / 失败 / 大失败
- Natural 20 = critical success; natural 1 = critical failure
- DC modifiers from previous results: 大成功(-5) / 成功(-3) / 勉强成功(-1) / 失败(+5) / 大失败(+5)

### Tactical Multi-Step System (`worldline_engine.py`)

`UniversalChallengeEngine` detects and evaluates multi-step tactical plans (e.g. "1. 派100人偷袭粮草，2. 主力诈败诱敌，3. 合围击杀"). Key behaviors:

- **Parsing priority**: number markers (`1.`, `1、`, `1)`) > comprehensive patterns > step markers > connectors.
- **Composite steps**: Actions sharing the same number marker execute simultaneously (each sub-action gets DC+2 and is checked independently).
- **Step dependencies**: Automatically established based on tactical purpose (e.g. "诱敌" depends on "埋伏").
- **Critical steps**: Purposes like `诱敌`, `偷袭`, `总攻`, `合围` are marked critical; failure can abort the entire plan.

### Anti-Abuse Mechanics (v3.3.2)

When modifying or extending the tactical system, these three rules must be preserved:

1. **Marginal success downgrade**: Marginal success only reduces subsequent DC by 1 (not 3).
2. **Command chain overload**: For step 4 and beyond, each step adds +1 DC to itself and all following steps.
3. **Info leak**: Any critical failure or natural 1 triggers an info leak. Each leak permanently adds +2 DC to all subsequent steps.

### Narrative Cheese Detection

`UniversalChallengeEngine` blocks three categories of player input:

- **Fabricated resources** — e.g. suddenly claiming helpers or items that don’t exist in `state.npcs`, `player.items`, or `player.tags`.
- **Declared results** — e.g. "我一剑秒杀了他" (directly stating an outcome).
- **New abilities** — e.g. "突然领悟绝世剑法" unless the player already has the corresponding tag/secret.

### Save Manager Schema (`save_manager.py`)

When working with saves programmatically, note these structural details:

- `player.attributes` maps attribute names to `{"value": int, "modifier": (value-10)//2}`.
- `player.resources` maps resource names to `{"type": str, "value": Any, "unit": str}`.
- NPC relationships live under `npc_database[<id>].relationship_matrix.towards_player`, where each dimension is `{"value": int, "max": int, "trend": str}`.
- `session_history` entries have a fixed schema with `session_id`, `entries`, `session_outcome`, etc.
