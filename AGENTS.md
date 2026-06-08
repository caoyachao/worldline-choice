# AGENTS.md — Worldline Choice 开发指南

> 本文件供 AI 编码智能体阅读。阅读者应当被假定为对项目一无所知。
> 当前版本：v4.5.0 (角色成长版)

---

## 1. 项目概述

**Worldline Choice (世界线·抉择)** 是一个 AI 驱动的开放式互动叙事游戏引擎。核心设计理念是 **LLM + d20 混合架构**：

- **LLM** 负责：意图理解、DC 评估、基于骰子结果的叙事生成
- **d20 引擎** 负责：客观判定行动成败（纯代码实现，不受 LLM 影响）
- **游戏引擎** 负责：状态管理、规则执行、存档管理、强制自动保存、回合结算（HP/金钱/状态效果）

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
├── worldline_skill.py      # 核心实现（~1800行）—— 主引擎、D20系统、GameState、LLMDriver、角色成长系统
├── worldline_engine.py     # 向后兼容入口（~430行）—— 兼容层、旧版API映射、CLI参数解析
├── openclaw_adapter.py     # OpenClaw 适配器（276行）—— 封装为 OpenClaw 可调用的 Skill
├── skill.json              # OpenClaw Skill 工具清单（定义所有可调用的工具/参数）
├── manifest.yaml           # OpenClaw 运行时清单（入口、命令、依赖声明）
├── demo_game.py            # 演示脚本（91行）—— 展示 d20 强制检定 + 自动保存 + 回合结算
├── test_llm_skill.py       # 新版测试套件（~600行）—— 测试 v4.x 架构
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
  ├─ 玩家属性 / 背包 / 标签 / 秘密
  ├─ NPC 关系（扁平结构）
  ├─ 历史记录（保留最近50条）
  ├─ HP / 最大HP
  ├─ 资源（金币、声望等）
  ├─ 状态效果（Buff/Debuff）
  ├─ 属性成长历史（审计日志）
  ├─ 每回合金钱变化（money_per_turn）
  ├─ active_benefits（战术加成，v4.3.0）
  ├─ scene_objects（场景互动物体）
  └─ npc_assist_log（NPC 协助记录）

LLMDriver                         # LLM 驱动抽象层
  ├─ analyze_action()             # 分析意图 → ActionAnalysis
  ├─ generate_options()           # 生成回合选项
  ├─ generate_narrative()         # 基于骰子结果生成叙事
  └─ 默认回退实现（无 LLM 时走关键词匹配）

WorldlineSkill                    # 主控制器
  ├─ start_game()                 # 初始化游戏（含世界观金钱映射）
  ├─ process_turn()               # 处理回合（核心链路）
  ├─ generate_turn_options()      # 生成本回合选项
  ├─ process_option()             # 处理 A/B/C/D/E 选择
  ├─ save_game() / load_game()    # 存档/读档（游戏目录隔离）
  ├─ settle_turn()                # 回合结算（v4.5.0：HP/金钱/状态效果）
  ├─ 战术增强系统（v4.3.0）
  │   ├─ set_scene_objects()
  │   ├─ interact_with_scene_object()
  │   ├─ execute_npc_check()
  │   ├─ add_active_benefit()
  │   ├─ consume_active_benefit()
  │   ├─ get_active_benefits()
  │   └─ calculate_effective_dc()
  └─ 自动保存（v4.4.1+，每回合强制执行）
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
6. 应用状态变更（_apply_consequences：属性/物品/HP/金钱/状态效果）
  ↓
7. 回合结算（settle_turn：tick衰减→修正计算→体质联动→金钱结算→死亡检测）
  ↓
8. 记录历史 + 强制自动保存
  ↓
返回 TurnResult（含 auto_save + settlement 字段）
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
- 当前版本号：**4.5.0**

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
| `test_growth_system()` | 属性升级、上限50、成长审计、死亡检测 |
| `test_settlement()` | 状态效果tick、体质联动HP、暂停衰减、有效属性 |
| `test_directory_isolation()` | 游戏目录隔离、多游戏存档 |

**运行方式：** `python3 test_llm_skill.py`
**状态：** 全部通过 ✓

### 7.2 建议的测试增补方向
- 战术增强系统（`active_benefits` 的叠加与消耗）
- 场景物体互动（`interact_with_scene_object`）
- NPC 协助检定（`execute_npc_check`）
- 存档迁移（v3.x → v4.x）
- 自动保存异常处理
- 金钱结算机制（世界观映射、每回合结算）

---

## 8. 存档格式与迁移

### 8.1 当前存档格式（v4.5.0）

存档以 JSON 文件保存，按 `game_id` 隔离目录：
```
saves/
└── game_{timestamp}_{world_setting}/
    ├── game.json          # 主存档（GameState 最新状态）
    └── auto.json          # 自动存档（由引擎每回合自动写入）
```

**注意**：`save_game()` 方法在写入前会向 `to_dict()` 结果中注入 `game_id` 字段（非 GameState 原生属性），用于加载时恢复目录上下文。

结构为扁平字典，核心字段：
```json
{
  "version": "4.5.0",
  "game_id": "game_1780885435_武侠",
  "world_setting": "武侠",
  "world_description": "",
  "current_scene": "客栈大堂",
  "player": {
    "name": "李逍遥",
    "role": "剑客",
    "attributes": {"FORCE": 12, "MIND": 14, ...},
    "inventory": {"capacity": 20, "items": [...]},
    "tags": [],
    "secrets": []
  },
  "npcs": {
    "店小二": {
      "relationship": 10,        # 总体关系 (-100~100)
      "attitude": "友善",
      "known_secrets": [],
      "trust": 15,               # 信任度 (-100~100)
      "fear": 0,                 # 恐惧度 (-100~100)
      "loyalty": 5,              # 忠诚度 (-100~100)
      "affection": 8,            # 好感度 (-100~100)
      "reputation": 10,          # 声誉 (-100~100)
      "interaction_count": 3,    # 互动次数
      "first_met_turn": 1,       # 首次相遇回合
      "last_interaction_turn": 5, # 上次互动回合
      "memories": [
        {"event": "玩家给了小费", "turn": 1, "type": "positive"}
      ],
      "tags": ["客栈员工"],
      "faction": "",
      "location": "客栈大堂",
      "status": "alive",
      "role": "店小二",
      "description": "热情的客栈伙计"
    }
  },
  "history": [...],
  "turn_count": 5,
  "flags": {},
  "hp": 100,
  "max_hp": 100,
  "resources": {"金币": 50},
  "status_effects": [],
  "attribute_history": {},
  "money_per_turn": -2,
  "ending_triggered": false,     # 结局是否触发
  "ending_type": "",             # 结局类型
  "death_triggered": false,      # 死亡是否触发
  "active_benefits": [],
  "scene_objects": [],
  "npc_assist_log": []
}
```

### 8.2 旧版兼容（v3.x → v4.x）

`worldline_engine.py` 中的 `_migrate_legacy_save()` 方法会自动处理：
- 中文属性名映射到 6 大通用维度（武力→FORCE、智力→MIND 等）
- 旧版 `npc_database` 扁平化为 `npcs`，并映射多维度情感（trust→信任、fear→恐惧、respect→忠诚/声誉）
- 旧版 `story_flags` 合并到 `flags`
- 历史记录从字典格式转为列表格式
- 缺失属性补全为默认值 10
- 补全 v4.5.0 新增字段（hp、resources、status_effects、attribute_history、money_per_turn、death_triggered、ending_triggered/ending_type）
- 补全 v4.5.0 NPC 完整关系字段（trust、fear、loyalty、affection、reputation、interaction_count、memories 等）

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

### 11.2 强制自动保存原则（v4.4.1+）
- 每回合 `process_turn` 返回前，**引擎层强制执行**自动保存。
- 返回结果中包含 `auto_save` 字段（`save_id`, `success`, `timestamp`, `filepath`）。
- LLM 不应再主动提及"保存"行为，避免幻觉。

### 11.3 角色成长系统（v4.5.0）
- 回合结算 `settle_turn` 是程序化补充，不替代 d20 检定，叙事仍基于 `CheckResult`。
- 属性升级单轮单项上限 ±5，上限 50，下限 1。所有变化记入 `attribute_history`。
- 金钱结算每回合强制执行，世界观决定 `money_per_turn`（收入/开销）。
- 死亡检测后 `death_triggered=True`，后续回合拒绝处理。

### 11.4 存档修改须知
- 修改 `GameState` 的字段时，必须同步更新 `to_dict()` 和 `from_dict()`。
- 如果新增战术字段，需在 `GameState.__init__`、`to_dict()`、`from_dict()` 中同步添加。

---

## 12. 版本历史摘要

| 版本 | 日期 | 核心变更 |
|------|------|----------|
| v4.5.0 | 2026-06-08 | 角色成长版。引入 HP/资源/背包/状态效果/属性历史审计；回合结算引擎（tick衰减→修正→体质联动→金钱结算→死亡检测）；游戏目录隔离；属性上限50；世界观金钱映射。 |
| v4.4.1 | 2026-04-09 | 强制自动保存版。引擎层每回合强制自动保存。 |
| v4.4.0 | 2026-04-07 | d20 强制检定版。`execute_check` 工具强制调用，禁止 LLM 脑补骰子。 |
| v4.3.0 | 2026-04-04 | 战术增强版。引入 `active_benefits` 加成链机制（前置准备 + NPC 协作 + 环境互动）。 |
| v4.2.0 | 2026-04-04 | `worldline_engine.py` 重写为兼容薄层，支持 v3.x 存档自动迁移。 |
| v4.0.0 | 2026-04-01 | 架构革命。升级为 LLM + d20 混合架构，引入 ABCD+E 选项系统。 |

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
| 新增测试 | 写在 `test_llm_skill.py` 中。 |
| 修改版本号 | 同步更新 `GameState.VERSION`、`skill.json` 中的 `version`、以及本文件顶部版本标记。 |
