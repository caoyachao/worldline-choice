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
  "history": []
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
