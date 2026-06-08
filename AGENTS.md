# AGENTS.md — Worldline Choice 开发指南

> 本文件供 AI 编码智能体阅读。阅读者应当被假定为对项目一无所知。
> 当前版本：v4.4.1 (强制自动保存版)

---

## 1. 项目概述

**Worldline Choice (世界线·抉择)** 是一个 AI 驱动的开放式互动叙事游戏引擎。核心设计理念是 **LLM + d20 混合架构**：

- **LLM** 负责：意图理解、DC 评估、基于骰子结果的叙事生成
- **d20 引擎** 负责：客观判定行动成败（纯代码实现，不受 LLM 影响）
- **游戏引擎** 负责：状态管理、规则执行、存档管理、强制自动保存

本项目是一个**纯 Python 项目**，零外部依赖，仅使用 Python 标准库。面向 OpenClaw 智能体运行时和命令行 CLI 两种使用场景。

---

## 2. 技术栈

| 层级 | 技术 |
|------|------|
| 语言 | Python 3.8+ |
| 依赖 | 无外部依赖（纯标准库） |
| 包管理 | 无（未使用 `pyproject.toml`、`requirements.txt`、`setup.py` 等） |
| 构建工具 | 无（直接运行 `.py` 文件） |
| 运行时 | OpenClaw 智能体框架 / 本地 CLI |

---

## 3. 项目结构

```
.
├── worldline_skill.py      # 核心实现（1354行）—— 主引擎、D20系统、GameState、LLMDriver
├── worldline_engine.py     # 向后兼容入口（378行）—— 兼容层、旧版API映射、CLI参数解析
├── openclaw_adapter.py     # OpenClaw 适配器（276行）—— 封装为 OpenClaw 可调用的 Skill
├── save_manager.py         # 旧版存档管理器（505行）—— v3.x 富结构存档格式，仍保留兼容
├── skill.json              # OpenClaw Skill 工具清单（定义所有可调用的工具/参数）
├── manifest.yaml           # OpenClaw 运行时清单（入口、命令、依赖声明）
├── demo_game.py            # 演示脚本（91行）—— 展示 d20 强制检定 + 自动保存
├── test_llm_skill.py       # 新版测试套件（369行）—— 测试 v4.x 架构
├── test_engine.py          # 旧版测试脚本（633行）—— ⚠️ 已过时，大量方法在当前代码中不存在
├── worldline_choice.sh     # Bash 启动脚本（默认启动 `worldline_skill.py`）
├── README.md               # 用户文档（中文）
├── SKILL.md                # 智能体主持手册（中文）—— Agent 行为规则与 API 速查
├── CLAUDE.md               # Claude Code 专用指南（英文）
└── saves/                  # 存档目录（运行时生成，已被 `.gitignore` 忽略）
```

---

## 4. 构建与运行命令

**本项目无需构建步骤。** 直接运行 Python 文件即可。

### 启动 CLI 交互模式
```bash
# 方式一：直接运行核心 Skill（推荐，带 ABCDE 选项 + d20 检定）
python3 worldline_skill.py

# 方式二：使用启动脚本
./worldline_choice.sh

# 方式三：使用兼容入口（旧版参数风格）
python3 worldline_engine.py --new "赛博侦探" "黑客" "V"
python3 worldline_engine.py --list
python3 worldline_engine.py --load save_001
```

### 运行测试
```bash
# 新版架构测试（推荐，当前维护中，全部通过）
python3 test_llm_skill.py

# 旧版兼容性测试（⚠️ 已严重过时，运行会失败）
python3 test_engine.py
```

### 运行演示
```bash
python3 demo_game.py
```

---

## 5. 代码组织与架构

### 5.1 核心类层次（`worldline_skill.py`）

```
AttributeDimension (Enum)       # 6大通用属性：FORCE/MIND/INFLUENCE/REFLEX/RESILIENCE/LUCK
CheckResult (dataclass)           # d20 检定结果
ActionAnalysis (dataclass)        # LLM 行动分析结果
NarrativeContext (dataclass)      # 叙事生成上下文
TurnOption / TurnOptions          # ABCD + E 选项结构

D20Engine                         # 纯 d20 检定系统（完全客观）
  ├─ calculate_modifier()         # 属性修正：(value-10)//2
  └─ execute_check()              # 执行检定（支持优势/劣势）

GameState                         # 精简游戏状态
  ├─ 玩家属性 / 物品 / 标签 / 秘密
  ├─ NPC 关系（扁平结构）
  ├─ 历史记录（保留最近50条）
  ├─ active_benefits（战术加成，v4.3.0）
  ├─ scene_objects（场景互动物体）
  └─ npc_assist_log（NPC 协助记录）

LLMDriver                         # LLM 驱动抽象层
  ├─ analyze_action()             # 分析意图 → ActionAnalysis
  ├─ generate_options()           # 生成回合选项
  ├─ generate_narrative()         # 基于骰子结果生成叙事
  └─ 默认回退实现（无 LLM 时走关键词匹配）

WorldlineSkill                    # 主控制器
  ├─ start_game()                 # 初始化游戏
  ├─ process_turn()               # 处理回合（核心链路）
  ├─ generate_turn_options()      # 生成本回合选项
  ├─ process_option()             # 处理 A/B/C/D/E 选择
  ├─ save_game() / load_game()    # 存档/读档
  ├─ 战术增强系统（v4.3.0）
  │   ├─ set_scene_objects()
  │   ├─ interact_with_scene_object()
  │   ├─ execute_npc_check()
  │   ├─ add_active_benefit()
  │   ├─ consume_active_benefit()
  │   └─ calculate_effective_dc()
  └─ 自动保存（v4.4.1，每回合强制执行）
```

### 5.2 兼容层（`worldline_engine.py`）

`WorldlineEngine` 继承自 `WorldlineSkill`，提供：
- 旧版 API 兼容映射（`initialize_world`, `get_system_prompt`, `process_action`, `roll_check`）
- v3.x 存档自动迁移（`_migrate_legacy_save`）—— 将旧版富结构存档转换为新版扁平结构
- CLI 参数解析（`--new`, `--load`, `--list`, `--delete`, `--help`）

### 5.3 回合处理核心链路（`process_turn`）

```
玩家输入
  ↓
1. LLM 分析意图 → ActionAnalysis (primary_attribute, base_dc, ...)
  ↓
2. 检查前置条件（物品缺失则直接返回错误）
  ↓
3. 应用外部 DC 修正（来自 active_benefits）
  ↓
4. d20.execute_check() → CheckResult（客观投骰）
  ↓
5. LLM.generate_narrative()（基于骰子结果生成叙事）
  ↓
6. 应用状态变更（_apply_consequences）
  ↓
7. 记录历史 + 强制自动保存
  ↓
返回 TurnResult（含 auto_save 字段）
```

---

## 6. 开发规范

### 6.1 语言与注释
- 所有代码注释、文档字符串、用户可见字符串使用**中文**。
- 类名、方法名、变量名使用英文（遵循 Python PEP 8）。
- 数据类字段使用中文键名仅出现在 `to_dict()` 和 `from_dict()` 的边界处；内部代码使用英文。

### 6.2 类型注解
- 广泛使用 `typing` 模块：`Dict`, `List`, `Optional`, `Any`, `Callable`。
- 使用 `@dataclass` 定义数据模型。
- 使用 `Enum` 定义属性维度。

### 6.3 代码风格
- 字符串格式化优先使用 f-string。
- JSON 序列化始终使用 `ensure_ascii=False` 以支持中文。
- 文件操作始终指定 `encoding='utf-8'`。
- 存档目录使用 `os.makedirs(..., exist_ok=True)` 确保存在。

### 6.4 版本号管理
- `GameState.VERSION` 和 `skill.json` 中的 `version` 字段必须同步更新。
- 当前版本号：**4.4.1**

---

## 7. 测试策略

### 7.1 当前有效测试（`test_llm_skill.py`）

| 测试函数 | 测试内容 |
|----------|----------|
| `test_d20_engine()` | 修正值计算、随机性分布、优势/劣势机制 |
| `test_game_state()` | 属性边界、物品/NPC/历史管理、序列化往返 |
| `test_skill_integration()` | 无 LLM 模式下的完整回合链路、存档/读档 |
| `test_openclaw_adapter()` | 适配器封装、analyze/execute_check/narrative 分离 |
| `test_llm_d20_separation()` | 验证骰子随机性、叙事与检定结果一致性 |
| `test_multi_world_settings()` | 多世界观通用性验证 |
| `test_turn_options()` | ABCD + E 选项生成与选择处理 |
| `test_openclaw_options()` | OpenClaw 接口的选项相关调用 |

**运行方式：** `python3 test_llm_skill.py`
**状态：** 全部通过 ✓

### 7.2 已过时测试（`test_engine.py`）

⚠️ **严重警告：** `test_engine.py` 引用大量在当前代码库中不存在的方法，包括但不限于：
- `get_system_prompt()` / `get_action_prompt()` / `get_ending_prompt()`
- `process_action()`
- `list_saves()`
- `raw_history` / `history_summaries` / `milestones`
- `challenge_engine.execute_tactical_check()`
- `update_world_state()` / `create_npc_rich()` / `update_npc_relationship_rich()`
- `create_quest()` / `add_inventory_item()` / `set_story_flag()` / `add_session()` / `add_session_entry()`
- `session_history` / `npc_database` / `active_quests` / `inventory` / `story_flags`

**状态：** 运行即失败。该文件是 v3.x 时代的遗留物，未被更新以匹配 v4.x 的精简扁平架构。

### 7.3 建议的测试增补方向
- 战术增强系统（`active_benefits` 的叠加与消耗）
- 场景物体互动（`interact_with_scene_object`）
- NPC 协助检定（`execute_npc_check`）
- 存档迁移（v3.x → v4.x）
- 自动保存异常处理

---

## 8. 存档格式与迁移

### 8.1 当前存档格式（v4.4.1）

存档以 JSON 文件保存，默认位置：
- `worldline_skill.py` 内：`./saves/`
- `worldline_engine.py` 内：`~/.claude/skills/worldline_choice/saves/`

结构为扁平字典，核心字段：
```json
{
  "version": "4.4.1",
  "world_setting": "武侠",
  "world_description": "",
  "current_scene": "客栈大堂",
  "player": {
    "name": "李逍遥",
    "role": "剑客",
    "attributes": {"FORCE": 12, "MIND": 14, ...},
    "items": ["长剑"],
    "tags": [],
    "secrets": []
  },
  "npcs": {"店小二": {"relationship": 10, "attitude": "友善"}},
  "history": [...],
  "turn_count": 5,
  "flags": {},
  "active_benefits": [],
  "scene_objects": [],
  "npc_assist_log": []
}
```

### 8.2 旧版兼容（v3.x → v4.x）

`worldline_engine.py` 中的 `_migrate_legacy_save()` 方法会自动处理：
- 中文属性名映射到 6 大通用维度（武力→FORCE、智力→MIND 等）
- 旧版 `npc_database` 扁平化为 `npcs`
- 旧版 `story_flags` 合并到 `flags`
- 历史记录从字典格式转为列表格式
- 缺失属性补全为默认值 10

---

## 9. OpenClaw 集成

### 9.1 工具清单（`skill.json`）

当前暴露给 OpenClaw 的工具共 18 个，分为：
- **游戏流程**：`start_game`, `process_turn`, `generate_turn_options`, `process_option`
- **检定与叙事**：`analyze_action`, `execute_check`, `generate_narrative`
- **存档**：`save_game`, `load_game`, `get_game_state`
- **战术增强**：`set_scene_objects`, `interact_with_scene_object`, `execute_npc_check`, `add_active_benefit`, `consume_active_benefit`, `get_active_benefits`, `calculate_effective_dc`

### 9.2 适配器（`openclaw_adapter.py`）

`OpenClawAdapter` 将 `WorldlineSkill` 封装为 OpenClaw 可调用的形式。关键设计：
- 内部 `_llm_callback` 负责解析 LLM 返回的 JSON（自动处理 Markdown 代码块包裹）
- 解析失败时提供默认回退响应，避免调用链中断
- `create_skill()` 工厂函数为 OpenClaw 运行时入口

---

## 10. 安全考量

| 方面 | 说明 |
|------|------|
| 网络通信 | 无。纯本地 Python 代码，无 HTTP/WebSocket 调用。 |
| 外部依赖 | 无。不引入第三方库，避免供应链风险。 |
| 文件系统 | 仅在 `./saves/` 或 `~/.claude/skills/worldline_choice/saves/` 目录读写 `.json` 存档文件。 |
| 输入验证 | `process_turn` 检查 `required_items`；`process_option` 校验选项字母为 A/B/C/D/E；`execute_check` 的 `attribute` 限制为枚举值。 |
| 序列化安全 | 使用标准库 `json` 模块，不涉及 `pickle`。 |
| 随机性 | 使用 `random.randint`，非加密安全级别；对于游戏用途足够。 |

---

## 11. 关键约束（修改前必读）

### 11.1 d20 强制检定原则（v4.4.0）
- **禁止**让 LLM 自行决定成功或失败。
- `execute_check` 必须通过代码客观执行，结果通过 `CheckResult` 传递给叙事生成。
- 叙事 Prompt 中包含严格的"红线"约束：禁止用转折词弱化失败、禁止给失败添加补偿收益。

### 11.2 强制自动保存原则（v4.4.1）
- 每回合 `process_turn` 返回前，**引擎层强制执行**自动保存。
- 返回结果中包含 `auto_save` 字段（`save_id`, `success`, `timestamp`, `filepath`）。
- LLM 不应再主动提及"保存"行为，避免幻觉。

### 11.3 存档修改须知
- 修改 `GameState` 的字段时，必须同步更新 `to_dict()` 和 `from_dict()`。
- 旧版 `save_manager.py` 中的 v3.x 富结构（`npc_database`, `session_history`, `inventory`, `active_quests` 等）在 `worldline_engine.py` 的 `_migrate_legacy_save()` 中被扁平化，但 `save_manager.py` 本身仍保留独立的 v3.x 逻辑。
- 如果新增战术字段，需在 `GameState.__init__`、`to_dict()`、`from_dict()` 中同步添加。

---

## 12. 版本历史摘要

| 版本 | 日期 | 核心变更 |
|------|------|----------|
| v4.4.1 | 2026-04-09 | 强制自动保存版。引擎层每回合强制自动保存。 |
| v4.4.0 | 2026-04-07 | d20 强制检定版。`execute_check` 工具强制调用，禁止 LLM 脑补骰子。 |
| v4.3.0 | 2026-04-04 | 战术增强版。引入 `active_benefits` 加成链机制（前置准备 + NPC 协作 + 环境互动）。 |
| v4.2.0 | 2026-04-04 | `worldline_engine.py` 重写为兼容薄层，支持 v3.x 存档自动迁移。 |
| v4.0.0 | 2026-04-01 | 架构革命。升级为 LLM + d20 混合架构，引入 ABCD+E 选项系统。 |
| v3.x | 2026-03-30 | 纯代码驱动的多步骤战术检定系统（`save_manager.py` 和 `test_engine.py` 仍反映此时代架构）。 |

---

## 13. 快速参考：修改代码时该怎么做

| 场景 | 建议 |
|------|------|
| 新增游戏机制 | 优先修改 `worldline_skill.py` 中的 `WorldlineSkill` 和 `GameState`。 |
| 新增 OpenClaw 工具 | 同步更新 `skill.json` 的工具定义 + `openclaw_adapter.py` 的封装方法。 |
| 修改 d20 规则 | 仅修改 `D20Engine` 类；确保 `test_llm_skill.py` 中的 `test_d20_engine` 通过。 |
| 修改存档格式 | 同步更新 `GameState.to_dict()` / `from_dict()` + `worldline_engine.py` 的 `_migrate_legacy_save()`。 |
| 修改选项生成逻辑 | 修改 `LLMDriver._build_options_prompt()` 和 `_default_options()`。 |
| 修改叙事约束 | 修改 `LLMDriver._build_narrative_prompt()` — 这是约束 LLM 叙事行为的唯一位置。 |
| 新增测试 | 写在 `test_llm_skill.py` 中，避免触碰 `test_engine.py`（已过时）。 |
| 修改版本号 | 同步更新 `GameState.VERSION`、`skill.json` 中的 `version`、以及本文件顶部版本标记。 |
