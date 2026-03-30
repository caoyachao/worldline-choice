---
name: worldline-choice
description: AI驱动互动叙事游戏引擎 v3.0 - 通用挑战框架版。当用户想要玩文字冒险游戏、互动叙事、角色扮演游戏时激活。核心特性：严格d20检定系统、硬边界规则、NPC主动性、自适应难度，确保游戏有真实挑战性。
---

# Worldline Choice v3.0 - 通用挑战框架版

## 简介

Worldline Choice 是一个**真正具有挑战性**的AI驱动互动叙事游戏引擎。

与早期版本不同，v3.0引入了**通用挑战框架**：
- 不依赖AI"自觉"遵守规则，而是**强制检定系统**
- **d20掷骰**决定结果，AI无法 override
- **硬边界规则**，明确阻止不可能的行动
- **资源消耗**，限制玩家无限尝试
- **NPC主动性**，敌对NPC会主动反击

## 核心特性

### 1. 通用能力维度（适配任何世界观）

无论你在什么世界，角色能力都映射到6个通用维度：

| 维度 | 武侠世界 | 科幻世界 | 现代都市 |
|------|----------|----------|----------|
| FORCE | 武力 | 火力 | 力量 |
| MIND | 智力 | 科技 | 智商 |
| INFLUENCE | 魅力 | 外交 | 人脉 |
| REFLEX | 敏捷 | 闪避 | 反应 |
| RESILIENCE | 体质 | 护盾 | 健康 |
| LUCK | 运气 | 随机 | 机遇 |

### 2. 强制检定系统

**检定公式**: `d20 + (属性-10)/2 >= DC`

难度等级:
- **简单(DC 5)**: 90%成功率
- **普通(DC 10)**: 70%成功率
- **困难(DC 15)**: 50%成功率
- **极难(DC 20)**: 30%成功率
- **不可能(DC 25+)**: 10%成功率

**结果等级**:
- 大成功 (超10+): 超额完成，有额外收益
- 成功 (超5+): 顺利完成
- 勉强成功: 完成但有代价
- 勉强失败: 失败但有机会补救
- 失败: 明确失败，承担后果
- 大失败 (差10+): 灾难性后果

**自然20必成功，自然1必失败**

### 3. 硬边界规则

AI在游戏初始化时生成世界的"物理法则"：

```json
{
  "impossible_rules": [
    "没有轻功无法飞檐走壁",
    "凡人无法击败化神期修士",
    "没有钥匙无法开锁"
  ]
}
```

违反硬边界的行动会被**明确阻止**，而不是让玩家"意外成功"。

### 4. 资源消耗机制

```json
{
  "resources": {
    "health": 100,    // 生命，归零=死亡/失败
    "stamina": 100,   // 体力，归零=无法行动
    "money": 50,      // 金钱，用于交易
    "time": 10,       // 时间，归零=机会丧失
    "reputation": 0   // 声望，负数=被追杀
  }
}
```

每次行动消耗资源，失败时消耗更多。

### 5. NPC主动性

敌对NPC（关系<-30）有30%概率每回合采取行动：
- 攻击
- 追击
- 设伏
- 警告

玩家不能只考虑自己想做什么，还要应对NPC的反击。

## 使用方法

### 启动游戏

```bash
# 使用默认设置启动
python3 worldline_engine.py --new "武侠江湖" "剑客" "李逍遥"

# Python API
from worldline_engine import WorldlineEngine

engine = WorldlineEngine()
result = engine.start_game("武侠江湖", "剑客", "李逍遥")
print(result['system_prompt'])  # 获取AI Prompt
```

### 处理玩家行动

```python
# 玩家输入行动
action = "我要和山贼头目战斗"

# 引擎自动评估
result = engine.process_player_action(action)

# 结果包含：
# - success: 是否成功
# - degree: 成功/失败程度
# - check_result: 检定详情（d20结果）
# - resource_costs: 资源消耗
# - npc_action: NPC反击（如果有）

if result['blocked']:
    print(f"行动被阻止: {result['reason']}")
    print(f"建议: {result['suggestion']}")
else:
    print(f"结果: {result['degree']}")
    print(f"检定: d20={result['evaluation']['check_result']['roll']}")
```

### AI Prompt 工作流程

1. **获取场景Prompt**
```python
scene_prompt = engine.get_system_prompt()
# 发送给AI生成场景描述和选项
```

2. **处理玩家选择**
```python
# 玩家选择后
action_prompt = engine.get_action_prompt(player_input, evaluation)
# 发送给AI生成剧情叙述
```

3. **AI必须遵守的规则**

**❌ 绝对禁止**:
- 让检定失败的行动"意外成功"
- 为玩家编造不存在的物品或能力
- 让玩家轻松完成明显超出能力的事
- 因为"剧情需要"而降低难度

**✅ 必须执行**:
- 严格按检定结果决定剧情走向
- 失败必须有真实后果（受伤、损失、关系恶化）
- 超出能力的尝试明确拒绝并提供替代方案
- 资源耗尽时限制行动

## 测试框架

```bash
python3 worldline_engine.py --test
```

测试内容包括：
- 行动解析
- 难度计算
- 检定执行（多次掷骰）
- 硬边界阻止
- NPC主动性

## 技术架构

### 核心类

```
WorldlineEngine          # 主引擎
├── GameState           # 游戏状态管理
├── UniversalChallengeEngine  # 通用挑战引擎
│   ├── analyze_action()      # 行动解析
│   ├── check_hard_limits()   # 硬边界检查
│   ├── calculate_difficulty() # 难度计算
│   ├── execute_check()       # 执行检定
│   └── npc_take_action()     # NPC主动性
└── WorldRules          # 世界规则
```

### 数据流

```
玩家输入
  ↓
analyze_action() → ActionProfile
  ↓
check_hard_limits() → 是否违反规则？
  ↓ 是 → 阻止并建议替代方案
  ↓ 否
calculate_difficulty() → DC值
  ↓
execute_check() → d20掷骰
  ↓
process_resource_cost() → 资源消耗
  ↓
生成结果 → AI根据结果生成叙述
```

## 为什么这样设计？

### 问题：AI太容易迎合玩家

早期版本的提示词告诉AI"要客观评估"，但AI的"helpful"本能会让它找到理由让玩家成功。

### 解决：强制检定系统

不是"建议"AI要客观，而是**掷骰结果决定一切**。AI只能根据骰子结果生成叙述，不能改变结果。

### 通用性如何保证？

通过**6个抽象维度**映射到任何世界观：
- 武侠世界的"内力" = 科幻世界的"能量" = 现代都市的"体力"
- 系统只关心数值，不关心具体名称

AI在游戏初始化时生成具体的世界规则，但检查逻辑是通用的。

## 示例游戏流程

### 开局

```
世界观: 武侠江湖
角色: 剑客 李逍遥
属性: 武力12, 智力16, 魅力15, 敏捷18, 体质10, 运气13

【场景】你在客栈休息，一群山贼闯入。

【选项】
A. 拔剑迎战 (DC 12, FORCE, 中等难度)
B. 尝试说服他们离开 (DC 15, INFLUENCE, 困难)
C. 从窗户逃走 (DC 10, REFLEX, 普通)
D. 用金钱收买 (DC 10, INFLUENCE, 但损失金钱)
```

### 玩家选择

```
玩家: 我要迎战

【检定】d20=5 + 1 = 6 vs DC=12 → 失败

【结果】你的剑法尚未成熟，山贼头目的刀法凶狠。
你一个照面就被压制，左臂被划出一道伤口。

【后果】
- 生命值 -15 (当前 85/100)
- 体力值 -10 (当前 90/100)
- 获得标签【受伤】

【NPC行动】山贼头目见你受伤，狞笑着追击！

【建议】你的武力不足以正面对抗，建议：
1. 使用轻功逃走 (需要敏捷检定)
2. 寻找帮手
3. 使用暗器偷袭
```

### 不可能的行动

```
玩家: 我要一剑秒杀山贼头目

【阻止】违反世界规则: 你的武力(12)远低于山贼头目(20)
正面对抗不可能成功。

【建议】
1. 寻找帮手
2. 使用计谋
3. 寻找对方的弱点
```

## 存档系统

```python
# 保存
engine.save_game("save_001")

# 加载
engine.load_game("save_001")

# 存档包含完整历史记录
```

## 许可证

MIT License
