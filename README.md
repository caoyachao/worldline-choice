# Worldline Choice

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> "每一个选择，都创造一条新的世界线"

**Worldline Choice** 是一个通用的AI驱动互动叙事游戏引擎。它支持完全开放式的游戏体验，所有剧情、抉择点、选项都由AI实时生成，不预设固定故事情节。

## ✨ 核心特性

### 🎮 完全开放式叙事
- **无预设剧情**：AI根据玩家输入实时生成场景和冲突
- **混合抉择系统**：4个剧情方向选项 + 1个自由输入
- **智能状态追踪**：自动管理角色属性、关系、物品、标签

### ⚖️ 严格的可行性评估
自由输入选项会进行**严格客观的可行性评估**：
- ✅ **客观能力检查**：玩家是否有执行此行动所需的技能/能力/物品
- ✅ **情境限制检查**：环境、时间、物理限制是否允许
- ✅ **信息掌握检查**：不能假设玩家知道未发现的秘密
- ✅ **合理性评估**：符合游戏世界的基本逻辑和物理法则
- ✅ **不刻意迎合**：不会因为玩家想这么做就让其轻易成功
- ✅ **不刻意刁难**：不会因为玩家想这么做就故意使其失败

### 🔪 D选项（特殊路线）的代价机制
D选项不再是"万能钥匙"，而是**有代价的双刃剑**：
- 可能比常规选项更高效，但会带来负面后果
- 涉及道德困境、隐藏风险或未来限制
- 使用D选项会记录代价，影响最终结局

### 🌍 多维度世界观支持
支持历史架空、名著改编、原创世界等多种背景。

## 🚀 快速开始

### 安装

```bash
git clone https://github.com/caoyachao/worldline-choice.git
cd worldline-choice
```

### Python API 使用

```python
from worldline_engine import WorldlineEngine

# 创建游戏引擎
game = WorldlineEngine()

# 开始游戏
game.start_game(
    world_setting="魔兽世界 - 巫妖王之怒时期",
    player_role="潜行者",
    player_name="玩家"
)

# 获取AI Prompt用于生成场景
system_prompt = game.get_system_prompt()

# 处理玩家行动（AI返回的响应）
result = game.process_action(
    player_input="调查那个神秘女子",
    ai_response={
        "intention": "调查",
        "feasible": True,
        "narrative": "你悄悄跟踪神秘女子，发现她进入了黑帮据点...",
        "consequences": {
            "attribute_changes": {"智力": 1},
            "secrets_learned": ["女子是黑帮成员"]
        }
    }
)

# 保存游戏
game.save_game("save_001")
```

### 命令行使用

```bash
# 开始新游戏
python3 worldline_engine.py --new "三国" "谋士" "诸葛亮"

# 列出所有存档
python3 worldline_engine.py --list

# 加载存档
python3 worldline_engine.py --load save_001

# 运行测试
python3 test_engine.py
```

## 🎯 游戏玩法示例

### 示例1：魔兽世界 - 三方对峙

```
场景：你作为潜行者，发现部落刺客和联盟法师正在对峙...

A. 【阵营选择】站在部落一边
B. 【阵营选择】站在联盟一边
C. 【第三方路线】提议合作
D. 【特殊路线】坐收渔利（需【声望】≥15）

玩家输入：提议三方合作潜入龙眠神殿

AI评估：
- 可行性：✅ 可行
- 难度：困难
- 需要：魅力≥15说服双方（当前16，满足）
- 后果：建立临时同盟，但双方随时可能背叛
```

### 示例2：严格可行性评估

```
玩家输入：我直接用禁咒毁灭整个城市

AI评估：
- 可行性：❌ 不可能
- 原因：
  1. 玩家没有禁咒能力（属性不足）
  2. 玩家没有相关知识和物品
  3. 超出凡人能力范围
- 结果：玩家尝试念咒，但只产生了一些火花，引来了守卫...
```

## 🏗️ 技术架构

### 状态管理

```json
{
  "world_setting": "世界观设定",
  "player": {
    "name": "角色名",
    "role": "角色身份",
    "attributes": {"武力": 18, "智力": 20},
    "items": ["龙息药剂"],
    "tags": ["时间行者"],
    "secrets": []
  },
  "npcs": {
    "NPC名": {"relationship": 30, "attitude": "信任"}
  },
  "flags": {"三方同盟": true},
  "costs_paid": [],
  "moral_corruption": 0,
  "broken_trust": []
}
```

### AI生成流程

1. **场景生成**：基于世界观和当前状态生成场景
2. **冲突识别**：自动识别场景中的核心冲突
3. **选项生成**：生成4个不同方向的选项（A/B/C/D）
4. **可行性评估**：对自由输入进行严格客观的可行性检查
5. **后果推演**：推演行动后果，更新状态
6. **结局判定**：判断是否达到结局条件

## 🛠️ 开发

### 扩展游戏逻辑

```python
def custom_rule(game_state, action):
    # 自定义规则
    if action.type == "特殊行动":
        # 检查可行性
        check = game_state.check_feasibility({
            "required_attributes": {"智力": 20},
            "required_items": ["魔法书"],
            "required_tags": ["法师学徒"]
        })
        
        if check["feasible"]:
            game_state.flags["特殊标记"] = True
        else:
            # 返回失败原因
            return {"success": False, "reason": check["missing"]}
    
    return game_state
```

### 自定义世界观

在 `~/.claude/skills/worldline_choice/worlds/` 目录下创建JSON文件：

```json
{
  "name": "赛博朋克2077",
  "description": "高科技低生活的未来都市",
  "default_role": "黑客",
  "attributes": ["智力", "反应", "技术", "冷静"],
  "sample_npcs": ["公司高管", "街头义体医生", "AI意识"]
}
```

## 📁 项目结构

```
worldline-choice/
├── README.md                 # 项目说明
├── SKILL.md                  # Skill 详细文档
├── worldline_engine.py       # 核心引擎
├── worldline_choice.sh       # 启动脚本
├── test_engine.py            # 测试脚本
└── saves/                    # 存档目录
```

## 🧪 测试

运行测试套件：

```bash
python3 test_engine.py
```

测试覆盖：
- ✅ 游戏状态管理
- ✅ 引擎初始化
- ✅ Prompt生成
- ✅ 行动处理与状态更新
- ✅ 存档与加载
- ✅ 结局生成
- ✅ 不同角色类型的属性生成
- ✅ 复杂场景模拟

## 📝 设计原则

### 1. 严格可行性评估
- 不刻意迎合玩家，也不刻意刁难
- 完全基于客观事实判断
- 失败也应该产生有意义的后果

### 2. D选项（特殊路线）的代价
- 不是"万能钥匙"
- 有真实的代价和风险
- 可能影响最终结局

### 3. 开放式叙事
- 不预设固定剧情
- AI根据玩家行为实时生成内容
- 每个玩家体验独一无二

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📄 许可证

MIT License

---

<p align="center">
  <i>"在无限的世界线中，你的选择定义了唯一的故事"</i>
</p>
