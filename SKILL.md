# Worldline Choice - AI驱动互动叙事游戏引擎

## 简介

Worldline Choice 是一个通用的AI驱动互动叙事游戏引擎，基于《世界线·抉择》的核心玩法设计。支持完全开放式的游戏体验，所有剧情、抉择点、选项都由AI实时生成，不预设固定故事情节。

## 核心特性

- **完全开放式叙事**：不预设固定剧情，AI根据玩家输入实时生成
- **智能状态追踪**：自动管理角色属性、关系、物品、标签
- **混合抉择系统**：支持预设选项和自由输入
- **多维度世界观**：支持历史、名著、原创等多种背景
- **上下文感知**：AI理解游戏历史和玩家行为模式

## 使用方法

### 启动游戏

```bash
# 使用默认设置启动
worldline_choice

# 指定世界观启动
worldline_choice --world "三国" --role "谋士"

# 加载存档继续游戏
worldline_choice --load save_001
```

### 在游戏内

1. **开局**：AI生成世界观介绍和角色设定
2. **场景推进**：AI根据当前状态生成场景描述和冲突
3. **做出选择**：
   - 选择A/B/C/D预设选项
   - 或直接输入自然语言描述行动
4. **剧情演化**：AI推演后果，生成新场景
5. **结局达成**：当满足条件时，AI生成结局

### Python API

```python
from worldline_choice import GameEngine

# 创建游戏引擎
game = GameEngine(
    world_setting="1960年代香港黑帮",
    player_role="卧底警察"
)

# 开始游戏
scene = game.start()
print(scene.description)

# 玩家行动
result = game.act("调查那个神秘女子")
print(result.narrative)

# 保存游戏
game.save("save_001.json")
```

## 核心设计变更：D选项（特殊路线）的代价机制

### 问题修复
原设计中，D选项（特殊路线）往往成为"万能钥匙"，让玩家可以轻松化解两难选择，失去了决策的紧张感。

### 新设计原则
**D选项不再是完美解决方案，而是有代价的双刃剑：**

1. **效率与代价并存**
   - D选项可能比A/B/C更高效，但会带来负面后果
   - 示例：用黑魔法快速解决问题，但获得【腐化】标签

2. **道德困境**
   - D选项可能涉及背叛、欺骗或牺牲原则
   - 示例：背叛盟友获得短期利益，但永久损失信任

3. **隐藏风险**
   - D选项可能带来意想不到的负面后果
   - 示例：使用禁忌力量拯救现在，但失去未来某种可能性

4. **代价追踪**
   - 引擎会记录玩家为使用D选项支付的代价
   - 道德腐化值、被破坏的信任关系等都会影响结局

### 示例对比

**旧设计（问题）：**
```
D. 【特殊】利用时间裂隙逃脱（需【时间行者】标签）
→ 完美逃脱，无代价
```

**新设计（修复）：**
```
D. 【特殊】利用时间裂隙逃脱（需【时间行者】标签）
→ 可以逃脱，但会留下时间残影，被时间守护者追杀
→ 获得【时间罪犯】标签，未来所有时间相关行动难度+50%
```

## 技术架构

### 状态管理

```json
{
  "world_setting": "世界观设定",
  "current_scene": "当前场景描述",
  "turn_count": 回合数,
  "player": {
    "name": "角色名",
    "role": "角色身份",
    "attributes": {"武力": 18, "智力": 20, ...},
    "items": [],
    "tags": []
  },
  "npcs": {
    "NPC名": {"relationship": 关系值, "secrets": []}
  },
  "flags": {},
  "history": [],
  "costs_paid": [],
  "moral_corruption": 0,
  "broken_trust": []
}
```

### AI生成流程

1. **场景生成**：基于世界观和当前状态生成场景
2. **冲突识别**：自动识别场景中的核心冲突
3. **选项生成**：基于冲突生成4个不同方向的选项
4. **行动解析**：解析玩家自由输入的意图
5. **后果推演**：推演行动后果，更新状态
6. **结局判定**：判断游戏是否达到结局条件

## 配置

### 环境变量

- `OPENAI_API_KEY` / `DEEPSEEK_API_KEY` / `ANTHROPIC_API_KEY`: AI模型API密钥
- `WORLDLINE_MODEL`: 使用的模型（默认：gpt-4）
- `WORLDLINE_LANG`: 游戏语言（默认：zh）

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

## 存档位置

- 存档文件：`~/.claude/skills/worldline_choice/saves/`
- 配置目录：`~/.claude/skills/worldline_choice/config/`

## 命令参考

| 命令 | 说明 |
|------|------|
| `worldline_choice --new` | 开始新游戏 |
| `worldline_choice --list` | 列出所有存档 |
| `worldline_choice --load <id>` | 加载存档 |
| `worldline_choice --delete <id>` | 删除存档 |
| `worldline_choice --worlds` | 列出可用世界观 |

## 示例

### 示例1：三国谍战

```
玩家：卧底曹魏的蜀汉密探
场景：官渡之战前夕，你发现袁绍的谋士许攸深夜独自出营...

AI生成选项：
A. 【拦截盘问】现身拦下许攸...
B. 【暗中跟踪】悄悄跟随看他要做什么...
C. 【通风报信】报告袁绍许攸有异动...
D. 【特殊】你有许攸的密谋线索...

玩家输入：我假装偶遇，请他喝酒试探口风
AI推演：许攸酒后吐真言，透露投曹意图...
```

### 示例2：现代悬疑

```
玩家：调查失踪案的记者
场景：你在废弃工厂发现同僚正在销毁证据...

AI生成选项：
A. 【当场揭发】拍照留证并报警...
B. 【利益交换】提出保密换取分成...
C. 【置身事外】假装没看见...
D. 【特殊】你发现他背后还有更大的人物...

玩家输入：我悄悄录音，然后问他为什么要这么做
AI推演：同僚崩溃，向你透露被威胁的真相...
```

## 开发

### 扩展游戏逻辑

编辑 `worldline_choice/engine.py`：

```python
def custom_rule(game_state, action):
    # 自定义规则
    if action.type == "特殊行动":
        game_state.flags["特殊标记"] = True
    return game_state
```

## 许可证

MIT License
