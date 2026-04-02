#!/usr/bin/env python3
"""
Worldline Choice - LLM驱动 + d20检定混合架构
面向OpenClaw智能体和CLI的Skill实现

核心设计：
1. LLM负责：意图理解、DC评估、叙事生成
2. d20负责：客观判定（成功/失败程度）
3. 引擎负责：状态管理、规则执行
"""

import json
import os
import random
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from enum import Enum


# ============ 核心数据模型 ============

class AttributeDimension(Enum):
    FORCE = "FORCE"           # 力量/战斗
    MIND = "MIND"             # 智力/技术
    INFLUENCE = "INFLUENCE"   # 魅力/社交
    REFLEX = "REFLEX"         # 敏捷/潜行
    RESILIENCE = "RESILIENCE" # 体质/意志
    LUCK = "LUCK"             # 运气


@dataclass
class CheckResult:
    """d20检定结果"""
    roll: int           # 原始骰子 (1-20)
    modifier: int       # 属性修正
    total: int          # 总计
    dc: int             # 难度
    success: bool       # 是否成功
    margin: int         # 差值
    degree: str         # 程度：大成功/成功/勉强成功/勉强失败/失败/大失败

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ActionAnalysis:
    """LLM对玩家行动的分析结果"""
    intention: str              # 玩家真实意图
    action_type: str            # 行动类型（战斗/社交/潜行/技术等）
    primary_attribute: str      # 主属性
    base_dc: int                # 基础DC
    dc_reasoning: str           # DC评估理由
    risks: List[str]            # 失败风险
    required_items: List[str]   # 需要的物品（如果有）
    required_knowledge: List[str]  # 需要的知识/能力

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class NarrativeContext:
    """叙事生成上下文"""
    action: str                 # 原始行动
    intention: str              # 意图
    check_result: CheckResult   # 检定结果
    world_setting: str          # 世界观
    scene_description: str      # 当前场景
    player_name: str

    def to_dict(self) -> Dict:
        return {
            "action": self.action,
            "intention": self.intention,
            "check_result": self.check_result.to_dict(),
            "world_setting": self.world_setting,
            "scene_description": self.scene_description,
            "player_name": self.player_name
        }


# ============ 纯d20检定系统（客观判定） ============

class D20Engine:
    """
    纯代码实现的d20检定系统
    完全客观，不受LLM影响
    """

    @staticmethod
    def calculate_modifier(attribute_value: int) -> int:
        """D&D 5e风格修正：(属性-10)/2"""
        return (attribute_value - 10) // 2

    @staticmethod
    def execute_check(
        attribute_value: int,
        dc: int,
        advantage: bool = False,
        disadvantage: bool = False
    ) -> CheckResult:
        """
        执行d20检定

        Args:
            attribute_value: 属性值
            dc: 难度等级
            advantage: 优势（投2个取高）
            disadvantage: 劣势（投2个取低）
        """
        modifier = D20Engine.calculate_modifier(attribute_value)

        # 投骰
        if advantage and not disadvantage:
            roll = max(random.randint(1, 20), random.randint(1, 20))
        elif disadvantage and not advantage:
            roll = min(random.randint(1, 20), random.randint(1, 20))
        else:
            roll = random.randint(1, 20)

        total = roll + modifier
        success = total >= dc
        margin = total - dc

        # 确定程度
        if roll == 20:
            degree = "大成功"
        elif roll == 1:
            degree = "大失败"
        elif margin >= 10:
            degree = "大成功"
        elif margin >= 5:
            degree = "成功"
        elif margin >= 0:
            degree = "勉强成功"
        elif margin >= -4:
            degree = "勉强失败"
        elif margin >= -9:
            degree = "失败"
        else:
            degree = "大失败"

        return CheckResult(
            roll=roll,
            modifier=modifier,
            total=total,
            dc=dc,
            success=success,
            margin=margin,
            degree=degree
        )


# ============ 游戏状态管理 ============

class GameState:
    """精简版游戏状态，专注核心数据"""

    VERSION = "4.0.0-llm-driven"

    def __init__(self):
        # 基础信息
        self.world_setting: str = ""
        self.world_description: str = ""
        self.current_scene: str = ""

        # 玩家状态
        self.player = {
            "name": "",
            "role": "",
            "attributes": {
                "FORCE": 10,
                "MIND": 10,
                "INFLUENCE": 10,
                "REFLEX": 10,
                "RESILIENCE": 10,
                "LUCK": 10
            },
            "items": [],
            "tags": [],
            "secrets": []
        }

        # NPC关系（扁平结构）
        self.npcs: Dict[str, Dict] = {}

        # 历史与进度
        self.history: List[Dict] = []
        self.turn_count: int = 0
        self.flags: Dict[str, Any] = {}

        # 结局
        self.ending_triggered: bool = False
        self.ending_type: str = ""

    def update_attribute(self, attr: str, delta: int):
        """更新属性"""
        if attr in self.player["attributes"]:
            current = self.player["attributes"][attr]
            self.player["attributes"][attr] = max(1, min(20, current + delta))

    def add_item(self, item: str):
        """添加物品"""
        if item not in self.player["items"]:
            self.player["items"].append(item)

    def remove_item(self, item: str):
        """移除物品"""
        if item in self.player["items"]:
            self.player["items"].remove(item)

    def update_npc(self, name: str, **kwargs):
        """更新NPC关系"""
        if name not in self.npcs:
            self.npcs[name] = {
                "relationship": 0,
                "attitude": "中立",
                "known_secrets": []
            }
        self.npcs[name].update(kwargs)

    def add_history(self, action: str, result: Dict):
        """添加历史记录"""
        self.turn_count += 1
        self.history.append({
            "turn": self.turn_count,
            "action": action,
            "result": result,
            "timestamp": datetime.now().isoformat()
        })

    def to_dict(self) -> Dict:
        """序列化"""
        return {
            "version": self.VERSION,
            "world_setting": self.world_setting,
            "world_description": self.world_description,
            "current_scene": self.current_scene,
            "player": self.player,
            "npcs": self.npcs,
            "history": self.history[-50:],  # 只保留最近50条
            "turn_count": self.turn_count,
            "flags": self.flags,
            "ending_triggered": self.ending_triggered,
            "ending_type": self.ending_type
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "GameState":
        """反序列化"""
        state = cls()
        state.world_setting = data.get("world_setting", "")
        state.world_description = data.get("world_description", "")
        state.current_scene = data.get("current_scene", "")
        state.player = data.get("player", state.player)
        state.npcs = data.get("npcs", {})
        state.history = data.get("history", [])
        state.turn_count = data.get("turn_count", 0)
        state.flags = data.get("flags", {})
        state.ending_triggered = data.get("ending_triggered", False)
        state.ending_type = data.get("ending_type", "")
        return state


# ============ LLM驱动层（抽象接口） ============

class LLMDriver:
    """
    LLM驱动层抽象
    实际实现由OpenClaw提供或CLI模拟
    """

    def __init__(self, callback: Optional[Callable] = None):
        """
        Args:
            callback: 调用LLM的回调函数
                     签名: fn(prompt: str, response_format: str) -> Dict
        """
        self.callback = callback

    def analyze_action(
        self,
        player_input: str,
        game_state: GameState
    ) -> ActionAnalysis:
        """
        分析玩家行动
        输出检定配置，不决定结果
        """
        prompt = self._build_analysis_prompt(player_input, game_state)

        if self.callback:
            result = self.callback(prompt, "json")
        else:
            # 默认实现（用于测试）
            result = self._default_analysis(player_input, game_state)

        return ActionAnalysis(**result)

    def generate_narrative(
        self,
        context: NarrativeContext
    ) -> Dict:
        """
        根据骰子结果生成叙事
        """
        prompt = self._build_narrative_prompt(context)

        if self.callback:
            result = self.callback(prompt, "json")
        else:
            result = self._default_narrative(context)

        return result

    def _build_analysis_prompt(self, action: str, state: GameState) -> str:
        """构建行动分析Prompt"""
        return f"""你是一个公正的TRPG游戏主持人。你的任务是分析玩家的行动意图，设定检定参数，但**不决定成败**。

【当前游戏状态】
世界观: {state.world_setting}
场景: {state.current_scene}
玩家: {state.player['name']} ({state.player['role']})
属性: {json.dumps(state.player['attributes'], ensure_ascii=False)}
持有物品: {', '.join(state.player['items']) or '无'}

【玩家输入】
{action}

【你的任务】
分析这个行动，输出JSON：
{{
  "intention": "玩家真实意图的简要描述",
  "action_type": "行动类型（如：战斗/社交/潜行/技术/魔法/探索）",
  "primary_attribute": "主属性（FORCE/MIND/INFLUENCE/REFLEX/RESILIENCE/LUCK之一）",
  "base_dc": "建议的DC数值（5-25之间的整数）",
  "dc_reasoning": "为什么设置这个DC的理由",
  "risks": ["失败可能发生的风险1", "风险2"],
  "required_items": ["需要的物品（如果有）"],
  "required_knowledge": ["需要的知识或能力（如果有）"]
}}

【重要约束】
1. 只分析可行性，**不要预测骰子结果**
2. 不要给玩家建议（"你应该..."）
3. 基于世界观判断什么是合理的
4. 如果玩家声明了不存在的能力/物品，在分析中指出"但玩家目前不具备"
"""

    def _build_narrative_prompt(self, ctx: NarrativeContext) -> str:
        """构建叙事生成Prompt"""
        return f"""你是一个叙事AI。骰子结果已经确定，你必须基于这个结果生成叙事。

【游戏背景】
世界观: {ctx.world_setting}
场景: {ctx.scene_description}
玩家: {ctx.player_name}

【行动描述】
意图: {ctx.intention}
原始输入: {ctx.action}

【骰子结果 - 这是不可更改的事实】
骰子点数: {ctx.check_result.roll}
属性修正: {ctx.check_result.modifier:+d}
总计: {ctx.check_result.total}
难度DC: {ctx.check_result.dc}
差值: {ctx.check_result.margin:+d}
结果程度: {ctx.check_result.degree}

【你的任务】
基于上述骰子结果，生成JSON：
{{
  "narrative": "剧情描述（200-300字），必须符合骰子结果的程度",
  "consequences": {{
    "attribute_changes": {{"属性名": 变化值}},
    "items_gained": ["获得的物品"],
    "items_lost": ["失去的物品"],
    "relationship_changes": {{"NPC名": 变化值}},
    "flags_set": {{"标志名": true}},
    "tags_gained": ["获得的标签"],
    "scene_change": "场景变化（如果有）"
  }},
  "ending_triggered": false,
  "ending_type": ""
}}

【叙事约束 - 严格遵守】
1. **骰子结果是绝对的**：如果程度是"失败"，叙事必须明确描述失败，禁止写"但意外成功"
2. **程度对应**：
   - 大成功: 超额完成，有额外收益
   - 成功: 顺利完成
   - 勉强成功: 完成但有代价或瑕疵
   - 勉强失败: 失败但有机会补救
   - 失败: 明确失败，承担后果
   - 大失败: 灾难性后果，可能有额外惩罚
3. **状态变更必须与叙事一致**：如果叙事中说"受伤了", consequences中要有相应体现
4. **不要编造**：所有状态变更必须基于叙事中实际发生的事件
"""

    def _default_analysis(self, action: str, state: GameState) -> Dict:
        """默认分析（用于无LLM时的回退）"""
        # 简单的关键词匹配作为回退
        action_lower = action.lower()

        # 判断行动类型和属性
        if any(w in action_lower for w in ["打", "杀", "战", "攻", "fight", "attack"]):
            return {
                "intention": "进行战斗",
                "action_type": "战斗",
                "primary_attribute": "FORCE",
                "base_dc": 15,
                "dc_reasoning": "标准战斗难度",
                "risks": ["受伤", "敌人警觉"],
                "required_items": [],
                "required_knowledge": []
            }
        elif any(w in action_lower for w in ["说", "劝", "骗", "talk", "persuade"]):
            return {
                "intention": "进行社交互动",
                "action_type": "社交",
                "primary_attribute": "INFLUENCE",
                "base_dc": 12,
                "dc_reasoning": "一般社交难度",
                "risks": ["对方反感", "信息泄露"],
                "required_items": [],
                "required_knowledge": []
            }
        elif any(w in action_lower for w in ["偷", "躲", "潜", "hide", "steal"]):
            return {
                "intention": "进行潜行",
                "action_type": "潜行",
                "primary_attribute": "REFLEX",
                "base_dc": 14,
                "dc_reasoning": "潜行需要不被发现",
                "risks": ["被发现", "陷入包围"],
                "required_items": [],
                "required_knowledge": []
            }
        else:
            return {
                "intention": "进行一般行动",
                "action_type": "通用",
                "primary_attribute": "MIND",
                "base_dc": 10,
                "dc_reasoning": "一般难度",
                "risks": ["失败"],
                "required_items": [],
                "required_knowledge": []
            }

    def _default_narrative(self, ctx: NarrativeContext) -> Dict:
        """默认叙事（回退）"""
        degree = ctx.check_result.degree

        templates = {
            "大成功": f"你完美地执行了计划，效果超出预期！",
            "成功": f"你顺利地完成了行动。",
            "勉强成功": f"你完成了行动，但过程有些惊险。",
            "勉强失败": f"你差一点就成功了，但最终还是失败了。",
            "失败": f"你的行动失败了。",
            "大失败": f"灾难！你的行动彻底失败，还引发了额外的问题。"
        }

        return {
            "narrative": templates.get(degree, "行动结束。"),
            "consequences": {
                "attribute_changes": {},
                "items_gained": [],
                "items_lost": [],
                "relationship_changes": {},
                "flags_set": {},
                "tags_gained": [],
                "scene_change": ""
            },
            "ending_triggered": False,
            "ending_type": ""
        }


# ============ 核心游戏引擎 ============

class WorldlineSkill:
    """
    Worldline Choice Skill
    LLM驱动 + d20检定的混合架构
    """

    def __init__(self, llm_callback: Optional[Callable] = None):
        self.state = GameState()
        self.d20 = D20Engine()
        self.llm = LLMDriver(llm_callback)
        self.save_dir = "./saves"
        os.makedirs(self.save_dir, exist_ok=True)

    def start_game(
        self,
        world_setting: str,
        player_role: str,
        player_name: str,
        world_desc: str = ""
    ) -> Dict:
        """开始新游戏"""
        self.state = GameState()
        self.state.world_setting = world_setting
        self.state.world_description = world_desc
        self.state.current_scene = world_desc or f"{world_setting}的世界"
        self.state.player["name"] = player_name
        self.state.player["role"] = player_role

        # 生成初始属性（简化版，可扩展）
        for attr in self.state.player["attributes"]:
            self.state.player["attributes"][attr] = random.randint(8, 16)

        return {
            "initialized": True,
            "world": world_setting,
            "player": self.state.player,
            "scene": self.state.current_scene
        }

    def process_turn(self, player_input: str) -> Dict:
        """
        处理一个游戏回合

        流程：
        1. LLM分析意图 → 检定配置
        2. d20投骰 → 客观结果
        3. LLM生成叙事（基于骰子结果）
        4. 应用状态变更
        """
        if not self.state.world_setting:
            return {"error": "游戏未初始化，请先调用start_game"}

        # Step 1: LLM分析意图
        analysis = self.llm.analyze_action(player_input, self.state)

        # 检查前置条件（物品、知识）
        missing_items = [
            item for item in analysis.required_items
            if item not in self.state.player["items"]
        ]

        if missing_items:
            return {
                "turn": self.state.turn_count + 1,
                "action": player_input,
                "error": f"缺少必要物品: {', '.join(missing_items)}",
                "can_retry": True
            }

        # Step 2: d20检定（客观判定）
        attr_value = self.state.player["attributes"].get(
            analysis.primary_attribute, 10
        )
        check_result = self.d20.execute_check(
            attribute_value=attr_value,
            dc=analysis.base_dc
        )

        # Step 3: LLM生成叙事（基于骰子结果）
        narrative_ctx = NarrativeContext(
            action=player_input,
            intention=analysis.intention,
            check_result=check_result,
            world_setting=self.state.world_setting,
            scene_description=self.state.current_scene,
            player_name=self.state.player["name"]
        )

        narrative_result = self.llm.generate_narrative(narrative_ctx)

        # Step 4: 应用状态变更
        self._apply_consequences(narrative_result.get("consequences", {}))

        # 记录历史
        turn_result = {
            "turn": self.state.turn_count + 1,
            "action": player_input,
            "intention": analysis.intention,
            "check": check_result.to_dict(),
            "narrative": narrative_result.get("narrative", ""),
            "consequences": narrative_result.get("consequences", {}),
            "ending_triggered": narrative_result.get("ending_triggered", False)
        }

        self.state.add_history(player_input, turn_result)

        # 检查结局
        if narrative_result.get("ending_triggered"):
            self.state.ending_triggered = True
            self.state.ending_type = narrative_result.get("ending_type", "")

        return turn_result

    def _apply_consequences(self, consequences: Dict):
        """应用状态变更"""
        # 属性变化
        for attr, delta in consequences.get("attribute_changes", {}).items():
            self.state.update_attribute(attr, delta)

        # 物品变化
        for item in consequences.get("items_gained", []):
            self.state.add_item(item)
        for item in consequences.get("items_lost", []):
            self.state.remove_item(item)

        # 关系变化
        for npc, delta in consequences.get("relationship_changes", {}).items():
            current = self.state.npcs.get(npc, {}).get("relationship", 0)
            self.state.update_npc(npc, relationship=current + delta)

        # 标志
        for flag, value in consequences.get("flags_set", {}).items():
            self.state.flags[flag] = value

        # 场景变化
        scene_change = consequences.get("scene_change", "")
        if scene_change:
            self.state.current_scene = scene_change

    def save_game(self, save_id: str) -> str:
        """保存游戏"""
        filepath = os.path.join(self.save_dir, f"{save_id}.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.state.to_dict(), f, ensure_ascii=False, indent=2)
        return filepath

    def load_game(self, save_id: str) -> bool:
        """加载游戏"""
        filepath = os.path.join(self.save_dir, f"{save_id}.json")
        if not os.path.exists(filepath):
            return False
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.state = GameState.from_dict(data)
        return True

    def get_state(self) -> Dict:
        """获取当前状态"""
        return self.state.to_dict()

    def get_history_summary(self, limit: int = 5) -> str:
        """获取历史摘要（用于LLM上下文）"""
        recent = self.state.history[-limit:]
        lines = []
        for h in recent:
            lines.append(f"回合{h['turn']}: {h['action']}")
            if 'result' in h and 'check' in h['result']:
                check = h['result']['check']
                lines.append(f"  → {check['degree']} (骰子{check['roll']})")
        return "\n".join(lines)


# ============ CLI接口 ============

def cli_main():
    """CLI模式入口"""
    print("="*60)
    print("Worldline Choice - LLM驱动 + d20检定")
    print("="*60)

    skill = WorldlineSkill()

    # 初始化
    print("\n开始新游戏...")
    world = input("世界观: ") or "武侠"
    role = input("角色: ") or "剑客"
    name = input("姓名: ") or "无名"

    result = skill.start_game(world, role, name)
    print(f"\n游戏开始: {result['world']}")
    print(f"属性: {result['player']['attributes']}")

    # 游戏循环
    while not skill.state.ending_triggered:
        print(f"\n{'='*40}")
        print(f"场景: {skill.state.current_scene}")
        print(f"回合 {skill.state.turn_count + 1}")
        print("-"*40)

        action = input("你的行动: ").strip()
        if not action:
            continue

        if action.lower() in ["save", "保存"]:
            save_id = input("存档ID: ") or "auto"
            path = skill.save_game(save_id)
            print(f"已保存到: {path}")
            continue

        if action.lower() in ["quit", "退出"]:
            break

        # 处理回合
        print("\n处理中...")
        result = skill.process_turn(action)

        if "error" in result:
            print(f"[错误] {result['error']}")
            continue

        # 显示结果
        check = result['check']
        print(f"\n【检定】{check['degree']}")
        print(f"骰子: {check['roll']} + 修正{check['modifier']:+d} = {check['total']} vs DC{check['dc']}")
        print(f"\n【剧情】")
        print(result['narrative'])

        if result.get('ending_triggered'):
            print(f"\n{'='*40}")
            print(f"游戏结束: {result.get('ending_type', '结局')}")
            break


if __name__ == "__main__":
    cli_main()
