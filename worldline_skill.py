#!/usr/bin/env python3
"""
Worldline Choice - LLM驱动 + d20检定混合架构 (v4.6.0)
面向OpenClaw智能体和CLI的Skill实现

核心设计：
1. LLM负责：意图理解、DC评估、叙事生成（基于骰子结果）
2. d20负责：客观判定（成功/失败程度）- 必须通过execute_check工具执行
3. 引擎负责：状态管理、规则执行、强制骰子结果不可被LLM覆盖、强制自动保存
4. 角色成长（v4.5.0）：回合结算、属性升级、HP/资源/背包/状态效果
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
    dc_value: int = 0           # 原始DC值
    dc_level: str = ""          # DC等级：简单/中等/困难/极难

    def to_dict(self) -> Dict:
        return {
            "action": self.action,
            "intention": self.intention,
            "check_result": self.check_result.to_dict(),
            "world_setting": self.world_setting,
            "scene_description": self.scene_description,
            "player_name": self.player_name,
            "dc_value": self.dc_value,
            "dc_level": self.dc_level
        }


@dataclass
class TurnOption:
    """单个回合选项"""
    letter: str                 # A/B/C/D/E
    description: str            # 选项描述（展示给玩家）
    action: str                 # 实际执行的行动（传给引擎）
    dc_hint: Optional[int] = None  # 可选的难度提示（用于UI显示）
    attr_hint: Optional[str] = None  # 可选的属性提示
    dc_level: Optional[str] = None   # DC等级：简单/中等/困难/极难
    reward_hint: Optional[str] = None  # 收益描述（如"少量金币"）
    risk_hint: Optional[str] = None    # 风险描述

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class TurnOptions:
    """回合选项集合 (ABCD预定义 + E自由)"""
    options: List[TurnOption]   # A/B/C/D选项
    free_text: TurnOption       # E选项（自由输入）
    context: str                # 当前情境描述

    def to_dict(self) -> Dict:
        return {
            "options": [opt.to_dict() for opt in self.options],
            "free_text": self.free_text.to_dict(),
            "context": self.context
        }

    def get_option(self, letter: str) -> Optional[TurnOption]:
        """获取指定字母的选项"""
        letter = letter.upper()
        if letter == "E":
            return self.free_text
        for opt in self.options:
            if opt.letter == letter:
                return opt
        return None


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

    VERSION = "4.6.0"

    # 属性上限
    ATTRIBUTE_MAX = 50
    ATTRIBUTE_MIN = 1
    # 单轮属性变化上限
    ATTRIBUTE_CHANGE_PER_TURN_MAX = 5

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
            "inventory": {
                "capacity": 20,
                "items": []
            },
            "tags": [],
            "secrets": []
        }

        # NPC关系（扁平结构）
        self.npcs: Dict[str, Dict] = {}

        # 历史与进度
        self.history: List[Dict] = []
        self.turn_count: int = 0
        self.flags: Dict[str, Any] = {}

        # 角色成长系统（v4.5.0）
        self.hp: int = 100
        self.max_hp: int = 100
        self.resources: Dict[str, int] = {}  # 财务/资源
        self.status_effects: List[Dict] = []  # 状态效果
        self.attribute_history: Dict[str, List[Dict]] = {}  # 属性成长审计

        # 金钱系统（v4.5.0）：每回合基础金钱变化（正数=收入，负数=开销）
        self.money_per_turn: int = 0

        # 战术增强系统（v4.3.0）：前置准备 + NPC协助 + 场景互动
        self.active_benefits: List[Dict] = []    # 当前可用的战术加成
        self.scene_objects: List[Dict] = []      # 场景中的可互动物体
        self.npc_assist_log: List[Dict] = []     # NPC协助历史记录

        # 结局与死亡
        self.ending_triggered: bool = False
        self.ending_type: str = ""
        self.death_triggered: bool = False

    def update_attribute(self, attr: str, delta: int, reason: str = ""):
        """更新属性，带成长审计"""
        if attr not in self.player["attributes"]:
            return

        # 硬截断：单轮变化上限
        if abs(delta) > self.ATTRIBUTE_CHANGE_PER_TURN_MAX:
            delta = self.ATTRIBUTE_CHANGE_PER_TURN_MAX if delta > 0 else -self.ATTRIBUTE_CHANGE_PER_TURN_MAX

        current = self.player["attributes"][attr]
        new_val = max(self.ATTRIBUTE_MIN, min(self.ATTRIBUTE_MAX, current + delta))
        actual_delta = new_val - current
        self.player["attributes"][attr] = new_val

        # 记录成长历史
        if actual_delta != 0:
            if attr not in self.attribute_history:
                self.attribute_history[attr] = []
            self.attribute_history[attr].append({
                "change": actual_delta,
                "reason": reason or "未说明",
                "turn": self.turn_count,
                "timestamp": datetime.now().isoformat()
            })

    def get_attribute_history(self, attr: str) -> List[Dict]:
        """获取某属性的成长历史"""
        return [h.copy() for h in self.attribute_history.get(attr, [])]

    def add_item(self, item: Any):
        """添加物品（兼容旧版字符串和新版字典）"""
        if isinstance(item, dict):
            self.add_inventory_item(item)
        else:
            self.add_inventory_item({
                "id": str(item),
                "name": str(item),
                "type": "consumable",
                "quantity": 1,
                "description": f"物品：{item}"
            })

    def remove_item(self, item: Any):
        """移除物品（兼容旧版字符串和新版字典）"""
        if isinstance(item, dict):
            self.remove_inventory_item(item.get("id", item.get("name", "")))
        else:
            self.remove_inventory_item(str(item))

    def add_inventory_item(self, item: Dict) -> bool:
        """添加物品到背包"""
        inv = self.player["inventory"]
        items = inv.get("items", [])
        capacity = inv.get("capacity", 20)

        # 检查容量
        if len(items) >= capacity:
            return False

        # 如果已有同ID物品且是消耗品，合并数量
        item_id = item.get("id") or item.get("name", "")
        for existing in items:
            existing_id = existing.get("id") or existing.get("name", "")
            if existing_id == item_id and existing.get("type") == "consumable" and item.get("type") == "consumable":
                existing["quantity"] = existing.get("quantity", 1) + item.get("quantity", 1)
                return True

        items.append(item)
        return True

    def remove_inventory_item(self, item_id: str) -> bool:
        """从背包移除物品"""
        items = self.player["inventory"].get("items", [])
        for i, item in enumerate(items):
            if (item.get("id") == item_id) or (item.get("name") == item_id):
                items.pop(i)
                return True
        return False

    def use_inventory_item(self, item_id: str) -> Optional[Dict]:
        """使用消耗品"""
        items = self.player["inventory"].get("items", [])
        for item in items:
            if (item.get("id") == item_id) or (item.get("name") == item_id):
                if item.get("type") != "consumable":
                    return None
                qty = item.get("quantity", 1)
                if qty <= 0:
                    return None
                item["quantity"] = qty - 1
                if item["quantity"] <= 0:
                    items.remove(item)
                return item.get("effects", {})
        return None

    def add_status_effect(self, effect: Dict):
        """添加状态效果"""
        self.status_effects.append(effect)

    def remove_status_effect(self, effect_id: str) -> bool:
        """移除状态效果"""
        for i, se in enumerate(self.status_effects):
            if se.get("id") == effect_id:
                self.status_effects.pop(i)
                return True
        return False

    def tick_status_effects(self) -> Dict:
        """
        状态效果 Tick 衰减
        返回被移除的效果列表
        """
        remaining = []
        ticked = []
        for se in self.status_effects:
            dur = se.get("duration", 0)
            if dur > 0:
                se["duration"] = dur - 1
                if se["duration"] > 0:
                    remaining.append(se)
                else:
                    ticked.append(se.get("id", ""))
            elif dur == -1:
                # 持续到场景结束
                remaining.append(se)
            else:
                # duration == 0 或无效，直接移除
                ticked.append(se.get("id", ""))
        self.status_effects = remaining
        return {"ticked": [t for t in ticked if t]}

    def update_resource(self, name: str, delta: int) -> int:
        """更新资源，不允许负值"""
        current = self.resources.get(name, 0)
        after = max(0, current + delta)
        self.resources[name] = after
        return after

    def update_hp(self, delta: int) -> int:
        """更新HP，限制在 [0, max_hp]"""
        self.hp = max(0, min(self.max_hp, self.hp + delta))
        return self.hp

    def update_npc(self, name: str, **kwargs):
        """更新NPC关系，支持完整多维度数据结构"""
        if name not in self.npcs:
            self.npcs[name] = {
                "relationship": 0,        # 总体关系 (-100~100)
                "attitude": "中立",
                "known_secrets": [],
                # 多维度情感
                "trust": 0,               # 信任度 (-100~100)
                "fear": 0,                # 恐惧度 (-100~100)
                "loyalty": 0,             # 忠诚度 (-100~100)
                "affection": 0,           # 好感度 (-100~100)
                "reputation": 0,          # 声誉 (-100~100)
                # 交互历史
                "interaction_count": 0,
                "first_met_turn": self.turn_count,
                "last_interaction_turn": self.turn_count,
                "memories": [],           # [{"event": "", "turn": 0, "type": "positive/negative/neutral"}]
                # 身份与状态
                "tags": [],
                "faction": "",
                "location": "",
                "status": "alive",        # alive/dead/missing/injured
                "role": "",
                "description": ""
            }
        self.npcs[name].update(kwargs)

    def add_npc_memory(self, name: str, event: str, memory_type: str = "neutral"):
        """为NPC添加记忆事件"""
        if name not in self.npcs:
            self.update_npc(name)
        self.npcs[name]["memories"].append({
            "event": event,
            "turn": self.turn_count,
            "type": memory_type,  # positive / negative / neutral
            "timestamp": datetime.now().isoformat()
        })
        # 限制记忆数量，防止无限增长
        if len(self.npcs[name]["memories"]) > 20:
            self.npcs[name]["memories"] = self.npcs[name]["memories"][-20:]

    def get_npc_summary(self, name: str) -> Dict:
        """获取NPC格式化摘要"""
        npc = self.npcs.get(name, {})
        if not npc:
            return {}
        return {
            "name": name,
            "relationship": npc.get("relationship", 0),
            "attitude": npc.get("attitude", "中立"),
            "trust": npc.get("trust", 0),
            "fear": npc.get("fear", 0),
            "loyalty": npc.get("loyalty", 0),
            "affection": npc.get("affection", 0),
            "reputation": npc.get("reputation", 0),
            "interaction_count": npc.get("interaction_count", 0),
            "status": npc.get("status", "alive"),
            "faction": npc.get("faction", ""),
            "role": npc.get("role", ""),
            "recent_memories": npc.get("memories", [])[-3:]
        }

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
            "history": self.history,
            "turn_count": self.turn_count,
            "flags": self.flags,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "resources": self.resources,
            "status_effects": self.status_effects,
            "attribute_history": self.attribute_history,
            "money_per_turn": self.money_per_turn,
            "ending_triggered": self.ending_triggered,
            "ending_type": self.ending_type,
            "death_triggered": self.death_triggered,
            "active_benefits": self.active_benefits,
            "scene_objects": self.scene_objects,
            "npc_assist_log": self.npc_assist_log,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "GameState":
        """反序列化，兼容旧版存档"""
        state = cls()

        # 基础信息
        state.world_setting = data.get("world_setting", "")
        state.world_description = data.get("world_description", "")
        state.current_scene = data.get("current_scene", "")

        # 玩家状态兼容迁移
        player = data.get("player", {})
        state.player["name"] = player.get("name", "")
        state.player["role"] = player.get("role", "")
        state.player["attributes"] = player.get("attributes", state.player["attributes"])
        state.player["tags"] = player.get("tags", [])
        state.player["secrets"] = player.get("secrets", [])

        # 背包兼容迁移：旧版 items 是字符串列表，新版是 inventory 结构
        if "inventory" in player:
            state.player["inventory"] = player["inventory"]
        elif "items" in player:
            old_items = player["items"]
            if isinstance(old_items, list) and len(old_items) > 0 and isinstance(old_items[0], str):
                # 旧版字符串列表，迁移为简单物品
                state.player["inventory"]["items"] = [
                    {
                        "id": item,
                        "name": item,
                        "type": "consumable",
                        "quantity": 1,
                        "description": f"物品：{item}"
                    }
                    for item in old_items
                ]
            else:
                state.player["inventory"]["items"] = old_items if isinstance(old_items, list) else []

        # NPC
        state.npcs = data.get("npcs", {})
        # 补全NPC缺失字段（v4.5.0+完整关系系统）
        for name, npc in state.npcs.items():
            if not isinstance(npc, dict):
                state.npcs[name] = {"relationship": 0, "attitude": "中立", "known_secrets": []}
                continue
            defaults = {
                "relationship": 0,
                "attitude": "中立",
                "known_secrets": [],
                "trust": 0,
                "fear": 0,
                "loyalty": 0,
                "affection": 0,
                "reputation": 0,
                "interaction_count": 0,
                "first_met_turn": 0,
                "last_interaction_turn": 0,
                "memories": [],
                "tags": [],
                "faction": "",
                "location": "",
                "status": "alive",
                "role": "",
                "description": ""
            }
            for k, v in defaults.items():
                if k not in npc:
                    npc[k] = v


        # 历史与进度
        state.history = data.get("history", [])
        state.turn_count = data.get("turn_count", 0)
        state.flags = data.get("flags", {})

        # 角色成长系统（v4.5.0 新增字段，旧版缺失时补全）
        state.hp = data.get("hp", 100)
        state.max_hp = data.get("max_hp", 100)
        state.resources = data.get("resources", {})
        state.status_effects = data.get("status_effects", [])
        state.attribute_history = data.get("attribute_history", {})
        state.money_per_turn = data.get("money_per_turn", 0)

        # 战术增强
        state.active_benefits = data.get("active_benefits", [])
        state.scene_objects = data.get("scene_objects", [])
        state.npc_assist_log = data.get("npc_assist_log", [])

        # 结局与死亡
        state.ending_triggered = data.get("ending_triggered", False)
        state.ending_type = data.get("ending_type", "")
        state.death_triggered = data.get("death_triggered", False)

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

    def generate_options(
        self,
        game_state: GameState,
        previous_result: Optional[Dict] = None
    ) -> TurnOptions:
        """
        生成本回合的ABCD预定义选项 + E自由选项

        Args:
            game_state: 当前游戏状态
            previous_result: 上一回合的结果（如果有）
        """
        prompt = self._build_options_prompt(game_state, previous_result)

        if self.callback:
            result = self.callback(prompt, "json")
        else:
            result = self._default_options(game_state)

        # 解析选项
        options = []
        for opt_data in result.get("options", []):
            options.append(TurnOption(**opt_data))

        free_text = TurnOption(
            letter="E",
            description=result.get("free_text", {}).get("description", "自定义行动..."),
            action="__FREE_TEXT__",  # 特殊标记表示需要玩家输入
            dc_hint=None,
            attr_hint=None
        )

        return TurnOptions(
            options=options,
            free_text=free_text,
            context=result.get("context", "请选择你的行动：")
        )

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
        inv_names = [it.get("name", it.get("id", "未知")) for it in state.player["inventory"].get("items", [])]
        return f"""你是一个公正的TRPG游戏主持人。你的任务是分析玩家的行动意图，设定检定参数，但**不决定成败**。

【当前游戏状态】
世界观: {state.world_setting}
场景: {state.current_scene}
玩家: {state.player['name']} ({state.player['role']})
属性: {json.dumps(state.player['attributes'], ensure_ascii=False)}
持有物品: {', '.join(inv_names) or '无'}
HP: {state.hp}/{state.max_hp}
资源: {json.dumps(state.resources, ensure_ascii=False) or '无'}
状态效果: {', '.join(se.get('name', se.get('id', '')) for se in state.status_effects) or '无'}

【玩家输入】
{action}

【你的任务】
分析这个行动，输出JSON：
{{
  "intention": "玩家真实意图的简要描述",
  "action_type": "行动类型（如：战斗/社交/潜行/技术/魔法/探索）",
  "primary_attribute": "主属性（FORCE/MIND/INFLUENCE/REFLEX/RESILIENCE/LUCK之一）",
  "base_dc": "建议的DC数值（2-17之间的整数，根据难度客观评估）",
  "dc_reasoning": "为什么设置这个DC的理由，基于情境中的客观事实",
  "risks": ["失败可能发生的风险1", "风险2"],
  "required_items": ["需要的物品（如果有）"],
  "required_knowledge": ["需要的知识或能力（如果有）"]
}}

【DC评估标准 - 必须严格遵守】
- DC 2-3: 极简单（走路、开门、正常说话、做日常熟悉的事）
- DC 4-5: 简单（爬矮墙、说服朋友、做熟悉的事）
- DC 6-7: 较简单（轻微跳跃、普通潜行、一般请求）
- DC 8-10: 中等（说服陌生人、标准战斗、标准潜行）
- DC 11-12: 较难（说服敌人、对抗训练有素的对手）
- DC 13-15: 困难（击败强敌、潜入严密守卫区域、欺骗高手）
- DC 16-17: 极难（近乎不可能的任务、对抗传说级敌人）
- DC 18-25: 传奇（仅用于特殊剧情，非常罕见）

【收益与风险对应 - 评估DC时必须考虑】
- DC 2-7（简单）: 成功收益小，失败风险低
- DC 8-12（中等）: 成功收益中等，失败风险中等
- DC 13-17（困难）: 成功收益大，失败风险高

【DC评估标准】
- DC 2-3: 极简单（走路、开门、正常说话）
- DC 4-5: 简单（爬矮墙、说服朋友、做熟悉的事）
- DC 6-7: 较简单（轻微跳跃、普通潜行、一般请求）
- DC 8-10: 中等（说服陌生人、标准战斗、标准潜行）
- DC 11-12: 较难（说服敌人、对抗训练有素的对手）
- DC 13-15: 困难（击败强敌、潜入严密守卫区域、欺骗高手）
- DC 16-17: 极难（近乎不可能的任务、对抗传说级敌人）
- DC 18-25: 传奇（仅用于特殊剧情，非常罕见）

【收益与风险对应】
- DC 2-7（简单）: 成功收益小，失败风险低
- DC 8-12（中等）: 成功收益中等，失败风险中等
- DC 13-17（困难）: 成功收益大，失败风险高
- 高风险选项成功后收益必须显著高于低风险选项

【重要约束 - 违反将导致机制失效】
1. **只分析可行性，绝对不要预测骰子结果**：
   - 你不能说"你很有可能成功"或"这很难成功"
   - 你的任务只是设定DC和属性，成败由骰子决定
   - 在调用 execute_check 之前，你不知道结果

2. **不要给玩家建议**（"你应该..."）

3. **基于世界观判断什么是合理的**

4. **如果玩家声明了不存在的能力/物品，在分析中指出"但玩家目前不具备"**

【执行顺序提醒】
正确的流程是：analyze_action → execute_check → generate_narrative
你必须调用 execute_check 获取骰子结果，禁止自行脑补结果。
"""

    def _build_options_prompt(self, state: GameState, previous_result: Optional[Dict]) -> str:
        """构建回合选项生成Prompt"""
        prev_narrative = ""
        if previous_result:
            prev_narrative = f"""
【上一回合结果】
{previous_result.get('narrative', '无')}

上一回合检定: {previous_result.get('check', {}).get('degree', '未知')}
"""
        inv_names = [it.get("name", it.get("id", "未知")) for it in state.player["inventory"].get("items", [])]
        return f"""你是一个游戏主持人，为玩家提供有意义的行动选择。

【当前游戏状态】
世界观: {state.world_setting}
场景: {state.current_scene}
玩家: {state.player['name']} ({state.player['role']})
属性: {json.dumps(state.player['attributes'], ensure_ascii=False)}
持有物品: {', '.join(inv_names) or '无'}
HP: {state.hp}/{state.max_hp}
当前回合: {state.turn_count + 1}
{prev_narrative}

【你的任务】
基于当前情境，生成4个预定义选项(A/B/C/D)和1个自由选项(E)。

输出JSON格式:
{{
  "context": "当前情境的简短描述（1-2句话）",
  "options": [
    {{
      "letter": "A",
      "description": "选项描述（15-20字，展示给玩家看的）",
      "action": "实际执行的行动（详细描述，传给引擎的）",
      "dc_hint": 12,
      "attr_hint": "MIND"
    }},
    {{
      "letter": "B",
      "description": "...",
      "action": "...",
      "dc_hint": 15,
      "attr_hint": "FORCE"
    }},
    {{
      "letter": "C",
      "description": "...",
      "action": "...",
      "dc_hint": 10,
      "attr_hint": "INFLUENCE"
    }},
    {{
      "letter": "D",
      "description": "...",
      "action": "...",
      "dc_hint": 13,
      "attr_hint": "REFLEX"
    }}
  ],
  "free_text": {{
    "description": "自定义行动（输入你想做的任何事情）"
  }}
}}

【选项设计原则 - 剧情导向】
1. **情境沉浸**: 选项必须紧密结合当前场景的具体元素，不是通用模板
2. **戏剧张力**: 四个选项应呈现真实的两难或多元价值观（如：道德vs效率，安全vs收益）
3. **角色扮演**: 选项应反映不同的人物性格或行事风格（如：鲁莽/谨慎/狡诈/仁慈）
4. **后果分化**: 每个选项应该导向明显不同的剧情分支，不只是换皮
5. **属性自然**: 属性使用应自然融入剧情，不要为了凑属性而硬塞
6. **难度合理**: DC应由情境复杂度决定，不是人为设置

【DC评估标准】
- DC 2-7（简单）: 低风险低收益选项（如：安全路线、保守策略、日常对话）
- DC 8-12（中等）: 标准风险标准收益选项（如：常规战斗、说服陌生人、一般潜行）
- DC 13-17（困难）: 高风险高回报选项（如：挑战强敌、欺骗高手、潜入重兵把守区域）
- 四个选项中应至少有1个简单（DC≤7）、1个中等（DC 8-10）、1个困难（DC 13+）

【选项示例 - 不要照搬】
场景：你发现受伤的敌人倒在路边
A- "救他，可能获得情报但也可能暴露自己" (DC13, 高风险高回报，INFLUENCE)
B- "搜刮物资后离开，不管他的死活" (DC7, 安全但可能有道德代价，MIND)
C- "给他个痛快，结束他的痛苦" (DC9, 残酷但确定，FORCE)
D- "藏起来观察，等他的同伴来" (DC8, 被动但信息丰富，REFLEX)

【反例 - 避免这种】
❌ A- "用力量攻击" B- "用智力解谜" C- "用魅力说服" D- "用敏捷闪避"
这种选项只是换了个说法的属性选择，完全没有剧情意义。
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
    "attribute_change_reasons": {{"属性名": "变化原因"}},
    "items_gained": [{{"id": "物品ID", "name": "物品名", "type": "consumable", "quantity": 1}}],
    "items_lost": ["失去的物品ID或名称"],
    "hp_change": 0,
    "resource_changes": {{"资源名": 变化值}},
    "money_change": 0,
    "status_effects_added": [{{"id": "效果ID", "name": "效果名", "type": "buff/debuff", "duration": 3, "effects": {{"hp": 0, "attributes": {{"RESILIENCE": -2}}}}, "pause_hp_decay": false}}],
    "status_effects_removed": ["效果ID"],
    "relationship_changes": {{"NPC名": 变化值}},  # 向后兼容，新版推荐使用下方完整结构
    "npc_relationship_changes": {{
      "NPC名": {{
        "relationship": 5,    # 总体关系变化
        "trust": 3,           # 信任度变化
        "fear": -2,           # 恐惧度变化
        "loyalty": 2,         # 忠诚度变化
        "affection": 1,       # 好感度变化
        "reputation": 0,      # 声誉变化
        "memories": [{{"event": "简短描述", "type": "positive/negative/neutral"}}],  # 新增记忆
        "attitude": "可选：新态度",  # 仅在态度改变时填写
        "faction": "可选：阵营",     # 仅在阵营改变时填写
        "location": "可选：位置",     # 仅在位置改变时填写
        "status": "可选：alive/dead/missing/injured",  # 仅在状态改变时填写
        "tags": ["可选：新增标签"],
        "known_secrets": ["可选：新增秘密"]
      }}
    }},
    "flags_set": {{"标志名": true}},
    "tags_gained": ["获得的标签"],
    "scene_change": "场景变化（如果有）"
  }},
  "ending_triggered": false,
  "ending_type": ""
}}

【叙事约束 - 严格遵守，违反将导致游戏机制崩溃】
1. **骰子结果是绝对不可更改的物理法则**：
   - 结果程度: {ctx.check_result.degree}
   - 你必须严格按照这个结果生成叙事，没有任何例外
   - **绝对禁止**：用"但是"、"然而"、"没想到"等转折词弱化失败或改写结果

2. **结果程度与叙事必须严格对应**：
   - 大成功: 超额完成，有意外之喜，效果显著
   - 成功: 顺利完成，达到预期目标
   - 勉强成功: 完成但付出代价、有瑕疵、或埋下隐患
   - 勉强失败: 明确失败，但留有补救机会或线索
   - 失败: 明确失败，承担负面后果，目标未达成
   - 大失败: 灾难性后果，目标彻底失败，可能引发连锁危机

3. **禁止行为（红线）**：
   ❌ 骰子失败却写成"虽然失败但意外获得好处"
   ❌ 骰子大失败却写成"差点失败"或"有惊无险"
   ❌ 用"运气不好"、"意外"来软化失败后果
   ❌ 给失败添加不应有的补偿性收益

4. **状态变更必须与叙事一致**：如果叙事中说"受伤了", consequences中要有相应体现
5. **不要编造**：所有状态变更必须基于叙事中实际发生的事件
6. **属性变化单轮绝对值不超过5**：如果叙事暗示属性变化超过5，引擎会自动截断
7. **金钱结算**：如果叙事中涉及金钱交易（贿赂、购买、偷窃、获得报酬等），使用 `money_change` 字段。正值=获得，负值=消耗。每回合结束引擎会自动结算世界观基础金钱变化。
8. **收益与DC必须严格对应**：
   - 如果DC在2-7之间（简单），成功后收益应较小：少量金币（1-5）、轻微关系提升（1-3）、小型物品、一般信息
   - 如果DC在8-12之间（中等），成功后收益应中等：属性提升（1-3）、有用物品（消耗品/装备）、重要信息、NPC关系+3-5
   - 如果DC在13-17之间（困难），成功后收益应显著：大量金币（10-30）、强力装备、重大剧情推进、NPC关系+5-10、属性提升（2-5）
   - 高风险高回报原则必须遵守：DC越高，成功后的consequences中正面变化应越大
   - 大成功（≥10高出DC或骰出20）在上述基础上额外增加收益
   - 勉强成功（≥0）虽然成功但应附带代价（HP下降、负面状态、物品损耗等）

【验证检查清单】
生成叙事前确认：
□ 骰子结果是 {ctx.check_result.degree}（{ctx.check_result.total} vs DC {ctx.check_result.dc}）
□ 叙事基调与结果程度一致
□ 没有使用转折词弱化结果
□ 状态变更有叙事支撑
□ 收益大小与DC等级（{ctx.dc_level}，DC={ctx.dc_value}）一致
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
                "base_dc": 12,
                "dc_reasoning": "标准战斗难度，中等",
                "risks": ["受伤", "敌人警觉"],
                "required_items": [],
                "required_knowledge": []
            }
        elif any(w in action_lower for w in ["说", "劝", "骗", "talk"]):
            return {
                "intention": "进行社交互动",
                "action_type": "社交",
                "primary_attribute": "INFLUENCE",
                "base_dc": 7,
                "dc_reasoning": "普通社交难度，较简单",
                "risks": ["对方反感", "信息泄露"],
                "required_items": [],
                "required_knowledge": []
            }
        elif any(w in action_lower for w in ["说服", "欺骗", "persuade", "bribe", "convince", "intimidate"]):
            return {
                "intention": "进行高难度社交",
                "action_type": "社交",
                "primary_attribute": "INFLUENCE",
                "base_dc": 10,
                "dc_reasoning": "说服或欺骗他人，中等难度",
                "risks": ["被识破", "反遭利用"],
                "required_items": [],
                "required_knowledge": []
            }
        elif any(w in action_lower for w in ["偷", "躲", "潜", "hide", "steal"]):
            return {
                "intention": "进行潜行",
                "action_type": "潜行",
                "primary_attribute": "REFLEX",
                "base_dc": 11,
                "dc_reasoning": "标准潜行难度，中等",
                "risks": ["被发现", "陷入包围"],
                "required_items": [],
                "required_knowledge": []
            }
        else:
            return {
                "intention": "进行一般行动",
                "action_type": "通用",
                "primary_attribute": "MIND",
                "base_dc": 7,
                "dc_reasoning": "一般行动，较简单",
                "risks": ["失败"],
                "required_items": [],
                "required_knowledge": []
            }

    def _default_options(self, state: GameState) -> Dict:
        """默认选项（用于无LLM时的回退）- 剧情导向设计"""
        # 基于回合数轮换不同的情境模板，展示多样化的剧情选项
        templates = [
            {
                "context": f"你站在{state.current_scene}的十字路口，前方传来奇怪的声音...",
                "options": [
                    {
                        "letter": "A",
                        "description": "握紧武器，大步走向声音来源",
                        "action": "毫不畏惧地走向声音来源，准备面对任何危险",
                        "dc_hint": 12,
                        "attr_hint": "FORCE"
                    },
                    {
                        "letter": "B",
                        "description": "躲进阴影，先观察情况",
                        "action": "悄悄躲进附近的阴影中，仔细观察声音来源",
                        "dc_hint": 7,
                        "attr_hint": "REFLEX"
                    },
                    {
                        "letter": "C",
                        "description": "大声喊话，试图交流",
                        "action": "朝声音方向喊话，表明自己没有敌意，试图沟通",
                        "dc_hint": 9,
                        "attr_hint": "INFLUENCE"
                    },
                    {
                        "letter": "D",
                        "description": "分析环境，寻找其他路径",
                        "action": "冷静分析周围环境，寻找可以绕行的安全路径",
                        "dc_hint": 8,
                        "attr_hint": "MIND"
                    }
                ]
            },
            {
                "context": f"一个陌生人拦住了你，眼神中带着试探...",
                "options": [
                    {
                        "letter": "A",
                        "description": "坦诚相待，说出真实目的",
                        "action": "直视对方的眼睛，坦诚地说出自己的真实目的",
                        "dc_hint": 9,
                        "attr_hint": "INFLUENCE"
                    },
                    {
                        "letter": "B",
                        "description": "编造谎言，试探对方反应",
                        "action": "编造一个半真半假的故事，观察对方的反应",
                        "dc_hint": 12,
                        "attr_hint": "MIND"
                    },
                    {
                        "letter": "C",
                        "description": "保持沉默，让对方先开口",
                        "action": "冷冷地看着对方，一言不发，等待对方表明来意",
                        "dc_hint": 8,
                        "attr_hint": "LUCK"
                    },
                    {
                        "letter": "D",
                        "description": "手按剑柄，警告对方不要挡路",
                        "action": "手按在武器上，用肢体语言表明自己不想惹事但也不怕事",
                        "dc_hint": 11,
                        "attr_hint": "FORCE"
                    }
                ]
            },
            {
                "context": f"你发现了一个可疑的线索，但时间紧迫...",
                "options": [
                    {
                        "letter": "A",
                        "description": "仔细搜查，不放过任何细节",
                        "action": "花时间仔细搜查现场，寻找所有可能的线索",
                        "dc_hint": 7,
                        "attr_hint": "MIND"
                    },
                    {
                        "letter": "B",
                        "description": "拿上明显的东西就走",
                        "action": "只拿取最明显、最有价值的物品，尽快离开",
                        "dc_hint": 10,
                        "attr_hint": "REFLEX"
                    },
                    {
                        "letter": "C",
                        "description": "设置陷阱，以防有人跟踪",
                        "action": "在离开前设置一个简单的警报陷阱，防止被跟踪",
                        "dc_hint": 13,
                        "attr_hint": "MIND"
                    },
                    {
                        "letter": "D",
                        "description": "破坏现场，不留下痕迹",
                        "action": "故意破坏现场，让别人无法追踪你的行踪",
                        "dc_hint": 11,
                        "attr_hint": "FORCE"
                    }
                ]
            }
        ]

        # 根据回合数选择模板
        template_index = (state.turn_count // 3) % len(templates)
        selected = templates[template_index]

        return {
            "context": selected["context"],
            "options": selected["options"],
            "free_text": {
                "description": "自定义行动（描述你想做的其他事情）"
            }
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
                "attribute_change_reasons": {},
                "items_gained": [],
                "items_lost": [],
                "hp_change": 0,
                "resource_changes": {},
                "status_effects_added": [],
                "status_effects_removed": [],
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

    def __init__(self, llm_callback: Optional[Callable] = None, auto_save: bool = True, show_dice: bool = False):
        """
        Args:
            llm_callback: LLM调用回调函数
            auto_save: 是否每回合自动存档（默认True）
            show_dice: 是否显示骰子结果（默认False，后台静默投骰）
        """
        self.state = GameState()
        self.d20 = D20Engine()
        self.llm = LLMDriver(llm_callback)
        self.game_id: Optional[str] = None
        self.save_dir = "./saves"
        self.auto_save = auto_save
        self.show_dice = show_dice
        os.makedirs(self.save_dir, exist_ok=True)

    def _get_game_save_dir(self) -> str:
        """获取当前游戏的存档目录"""
        if not self.game_id:
            return self.save_dir
        return os.path.join(self.save_dir, self.game_id)

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

        # 初始化默认值
        self.state.hp = 100
        self.state.max_hp = 100
        self.state.resources = {}
        self.state.status_effects = []
        self.state.attribute_history = {}

        # 金钱系统：根据世界观设定初始金币和每回合金钱变化
        self.state.money_per_turn = self._get_world_money_rate(world_setting)
        # 初始金币：给世界观相关的启动资金
        start_gold = self._get_world_start_gold(world_setting)
        if start_gold > 0:
            self.state.update_resource("金币", start_gold)

        # 生成游戏ID
        timestamp = int(datetime.now().timestamp())
        safe_world = "".join(c for c in world_setting if c.isalnum() or c in "_-")
        self.game_id = f"game_{timestamp}_{safe_world}"

        # 创建游戏目录
        game_dir = self._get_game_save_dir()
        os.makedirs(game_dir, exist_ok=True)

        # 保存初始存档
        self.save_game("game")

        return {
            "initialized": True,
            "world": world_setting,
            "player": self.state.player,
            "scene": self.state.current_scene,
            "game_id": self.game_id
        }

    def process_turn(
        self,
        player_input: str,
        dc_modifier: int = 0,
        advantage: bool = False,
        disadvantage: bool = False
    ) -> Dict:
        """
        处理一个游戏回合

        流程：
        1. LLM分析意图 → 检定配置
        2. d20投骰 → 客观结果（支持外部DC修正和优势/劣势）
        3. LLM生成叙事（基于骰子结果）
        4. 应用状态变更
        5. 回合结算（程序化）
        """
        if not self.state.world_setting:
            return {"error": "游戏未初始化，请先调用start_game"}

        # 死亡检测
        if self.state.death_triggered:
            return {
                "turn": self.state.turn_count + 1,
                "action": player_input,
                "error": "角色已死亡，无法继续行动",
                "death_triggered": True
            }

        # Step 1: LLM分析意图
        analysis = self.llm.analyze_action(player_input, self.state)

        # 检查前置条件（物品、知识）
        inv_items = self.state.player["inventory"].get("items", [])
        inv_names = [it.get("name", it.get("id", "")) for it in inv_items]
        missing_items = [
            item for item in analysis.required_items
            if item not in inv_names
        ]

        if missing_items:
            return {
                "turn": self.state.turn_count + 1,
                "action": player_input,
                "error": f"缺少必要物品: {', '.join(missing_items)}",
                "can_retry": True
            }

        # Step 2: d20检定（客观判定）
        # 应用外部修正（来自战术准备、NPC协助、环境互动）
        effective_dc = max(1, analysis.base_dc + dc_modifier)

        attr_value = self.state.player["attributes"].get(
            analysis.primary_attribute, 10
        )
        check_result = self.d20.execute_check(
            attribute_value=attr_value,
            dc=effective_dc,
            advantage=advantage,
            disadvantage=disadvantage
        )

        # Step 3: LLM生成叙事（基于骰子结果）
        # 计算DC等级
        dc_value = analysis.base_dc
        dc_level = (
            "简单" if dc_value <= 7 else
            "中等" if dc_value <= 12 else
            "困难" if dc_value <= 17 else
            "极难"
        )
        
        narrative_ctx = NarrativeContext(
            action=player_input,
            intention=analysis.intention,
            check_result=check_result,
            world_setting=self.state.world_setting,
            scene_description=self.state.current_scene,
            player_name=self.state.player["name"],
            dc_value=dc_value,
            dc_level=dc_level
        )

        narrative_result = self.llm.generate_narrative(narrative_ctx)

        # Step 4: 应用状态变更
        self._apply_consequences(narrative_result.get("consequences", {}))

        # Step 4.5: 回合结算
        settlement = self.settle_turn()

        # 记录历史
        turn_result = {
            "turn": self.state.turn_count + 1,
            "action": player_input,
            "intention": analysis.intention,
            "narrative": narrative_result.get("narrative", ""),
            "consequences": narrative_result.get("consequences", {}),
            "ending_triggered": narrative_result.get("ending_triggered", False),
            "settlement": settlement
        }

        # 根据配置决定是否显示骰子结果
        if self.show_dice:
            turn_result["check"] = check_result.to_dict()
        else:
            # 不显示详细骰子结果，只显示程度
            turn_result["degree"] = check_result.degree
            turn_result["success"] = check_result.success

        self.state.add_history(player_input, turn_result)

        # 检查结局
        if narrative_result.get("ending_triggered"):
            self.state.ending_triggered = True
            self.state.ending_type = narrative_result.get("ending_type", "")

        # 强制自动存档（每回合结束时更新game.json）
        auto_save_info = {"filepath": None, "success": False, "timestamp": None, "error": None}
        if self.auto_save:
            try:
                filepath = self.save_game()
                auto_save_info = {
                    "filepath": filepath,
                    "success": True,
                    "timestamp": datetime.now().isoformat()
                }
            except Exception as e:
                auto_save_info = {
                    "filepath": None,
                    "success": False,
                    "timestamp": datetime.now().isoformat(),
                    "error": str(e)
                }

        # 返回结果中包含强制保存状态
        turn_result["auto_save"] = auto_save_info
        return turn_result

    def generate_turn_options(
        self,
        previous_result: Optional[Dict] = None
    ) -> TurnOptions:
        """
        生成本回合的ABCD预定义选项 + E自由选项

        Args:
            previous_result: 上一回合的结果（用于上下文）

        Returns:
            TurnOptions对象，包含A/B/C/D选项和E自由选项
        """
        return self.llm.generate_options(self.state, previous_result)

    def process_option(
        self,
        options: TurnOptions,
        choice: str,
        free_text: Optional[str] = None
    ) -> Dict:
        """
        处理玩家选择的选项

        Args:
            options: 本回合的选项集合
            choice: 玩家选择（A/B/C/D/E）
            free_text: 如果选E，玩家的自由输入

        Returns:
            回合结果（同process_turn）
        """
        choice = choice.upper().strip()

        if choice == "E":
            # 自由选项
            if not free_text:
                return {"error": "选择E时需要提供自由输入"}
            action = free_text
        elif choice in ["A", "B", "C", "D"]:
            # 预定义选项
            option = options.get_option(choice)
            if not option:
                return {"error": f"无效的选项: {choice}"}
            action = option.action
        else:
            return {"error": f"无效的选择: {choice}，请选择A/B/C/D/E"}

        # 执行回合
        return self.process_turn(action)

    def _apply_consequences(self, consequences: Dict):
        """应用状态变更"""
        # 属性变化（带reason）
        for attr, delta in consequences.get("attribute_changes", {}).items():
            reason = consequences.get("attribute_change_reasons", {}).get(attr, "")
            self.state.update_attribute(attr, delta, reason)

        # 物品变化
        for item in consequences.get("items_gained", []):
            self.state.add_item(item)
        for item in consequences.get("items_lost", []):
            self.state.remove_item(item)

        # HP 变化
        hp_delta = consequences.get("hp_change", 0)
        if hp_delta != 0:
            self.state.update_hp(hp_delta)

        # 资源变化（通用）
        for res_name, delta in consequences.get("resource_changes", {}).items():
            self.state.update_resource(res_name, delta)

        # 金钱变化（单次行动消耗/获得）
        money_delta = consequences.get("money_change", 0)
        if money_delta != 0:
            self.state.update_resource("金币", money_delta)

        # 状态效果变化
        for effect in consequences.get("status_effects_added", []):
            self.state.add_status_effect(effect)
        for effect_id in consequences.get("status_effects_removed", []):
            self.state.remove_status_effect(effect_id)

        # 关系变化（向后兼容：旧版扁平结构）
        for npc, delta in consequences.get("relationship_changes", {}).items():
            current = self.state.npcs.get(npc, {}).get("relationship", 0)
            self.state.update_npc(npc, relationship=current + delta)
            # 自动更新互动计数
            ic = self.state.npcs[npc].get("interaction_count", 0) + 1
            self.state.npcs[npc]["interaction_count"] = ic
            self.state.npcs[npc]["last_interaction_turn"] = self.state.turn_count

        # 完整NPC关系变化（新版多维结构）
        for npc, changes in consequences.get("npc_relationship_changes", {}).items():
            if not isinstance(changes, dict):
                continue
            self.state.update_npc(npc)  # 确保NPC存在
            npc_data = self.state.npcs[npc]
            # 更新各维度（变化量累加，限制在-100~100）
            for dim in ["relationship", "trust", "fear", "loyalty", "affection", "reputation"]:
                if dim in changes:
                    new_val = max(-100, min(100, npc_data.get(dim, 0) + changes[dim]))
                    npc_data[dim] = new_val
            # 添加记忆
            for mem in changes.get("memories", []):
                if isinstance(mem, dict):
                    mem.setdefault("turn", self.state.turn_count)
                    npc_data["memories"].append(mem)
            # 更新其他可选字段
            for field in ["attitude", "faction", "location", "status", "role", "description"]:
                if field in changes:
                    npc_data[field] = changes[field]
            for field in ["tags", "known_secrets"]:
                if field in changes and isinstance(changes[field], list):
                    # 合并列表，去重
                    existing = set(npc_data.get(field, []))
                    existing.update(changes[field])
                    npc_data[field] = list(existing)
            # 自动更新互动计数
            npc_data["interaction_count"] = npc_data.get("interaction_count", 0) + 1
            npc_data["last_interaction_turn"] = self.state.turn_count
            # 记忆数量限制
            if len(npc_data["memories"]) > 20:
                npc_data["memories"] = npc_data["memories"][-20:]

        # 标志
        for flag, value in consequences.get("flags_set", {}).items():
            self.state.flags[flag] = value

        # 场景变化
        scene_change = consequences.get("scene_change", "")
        if scene_change:
            self.state.current_scene = scene_change

    def settle_turn(self) -> Dict:
        """
        回合结算（程序化，不受LLM影响）
        五阶段：自动修正 -> tick衰减 -> 体质联动HP -> 金钱结算 -> 死亡检测
        """
        warnings = []

        # 阶段1: 自动修正计算（先应用当前所有效果，再tick）
        auto_modifiers = {"attributes": {}, "hp": 0}
        effective_attributes = dict(self.state.player["attributes"])

        pause_hp_decay = False
        for se in self.state.status_effects:
            effects = se.get("effects", {})
            # 属性修正
            for attr, delta in effects.get("attributes", {}).items():
                auto_modifiers["attributes"][attr] = auto_modifiers["attributes"].get(attr, 0) + delta
                if attr in effective_attributes:
                    effective_attributes[attr] = max(1, min(50, effective_attributes[attr] + delta))
            # HP修正
            hp_delta = effects.get("hp", 0)
            if hp_delta:
                auto_modifiers["hp"] += hp_delta
                self.state.update_hp(hp_delta)
            # 暂停HP衰减
            if se.get("pause_hp_decay"):
                pause_hp_decay = True

        # 装备品修正（仅计算effective_attributes，不修改存档）
        for item in self.state.player["inventory"].get("items", []):
            if item.get("type") == "equipment":
                eq_effects = item.get("effects", {})
                for attr, delta in eq_effects.get("attributes", {}).items():
                    auto_modifiers["attributes"][attr] = auto_modifiers["attributes"].get(attr, 0) + delta
                    if attr in effective_attributes:
                        effective_attributes[attr] = max(1, min(50, effective_attributes[attr] + delta))

        # 阶段2: 状态Tick衰减
        tick_result = self.state.tick_status_effects()
        ticked_ids = tick_result.get("ticked", [])

        # 阶段3: 体质联动HP规则
        auto_hp_change = 0
        if not pause_hp_decay:
            res_val = self.state.player["attributes"].get("RESILIENCE", 10)
            if res_val >= 15:
                auto_hp_change = 1
                self.state.update_hp(1)
            elif res_val <= 5:
                auto_hp_change = -1
                self.state.update_hp(-1)

        # 阶段4: 金钱结算（每回合强制执行）
        money_before = self.state.resources.get("金币", 0)
        money_change = self.state.money_per_turn
        if money_change != 0:
            self.state.update_resource("金币", money_change)
        money_after = self.state.resources.get("金币", 0)

        # 阶段5: 死亡检测
        death_triggered = False
        if self.state.hp <= 0:
            self.state.hp = 0
            self.state.death_triggered = True
            death_triggered = True
            warnings.append("生命值归零，角色已死亡")

        return {
            "ticked_effects": ticked_ids,
            "auto_modifiers": auto_modifiers,
            "auto_hp_change": auto_hp_change,
            "effective_attributes": effective_attributes,
            "money_change": money_change,
            "money_before": money_before,
            "money_after": money_after,
            "death_triggered": death_triggered,
            "warnings": warnings
        }

    # ------------------------------------------------------------------
    # 战术增强系统（v4.3.0）
    # 整合方案1（前置准备）+ 方案3（NPC协作）+ 方案4（环境互动）
    # ------------------------------------------------------------------

    def set_scene_objects(self, objects: List[Dict]) -> Dict:
        """设置当前场景中的可互动物体。"""
        self.state.scene_objects = objects
        return {
            "set_count": len(objects),
            "objects": [{"id": o.get("id"), "name": o.get("name")} for o in objects]
        }

    def interact_with_scene_object(self, object_id: str, player_input: str) -> Dict:
        """
        玩家与场景物体互动。
        成功后会将该物体对应的 benefit 加入 active_benefits。
        """
        obj = None
        for o in self.state.scene_objects:
            if o.get("id") == object_id:
                obj = o
                break

        if not obj:
            return {"error": f"场景中不存在物体: {object_id}"}

        if obj.get("activated"):
            return {"error": f"该物体已被互动过: {obj.get('name')}"}

        # 调用标准回合流程处理互动本身
        result = self.process_turn(player_input)

        if "error" in result:
            return result

        # 若互动成功（成功或勉强成功），激活 benefit
        if result.get("check", {}).get("success") or result.get("success"):
            obj["activated"] = True
            benefit = obj.get("benefit")
            if benefit:
                benefit["source"] = f"scene_object:{object_id}"
                benefit["source_name"] = obj.get("name")
                self.state.active_benefits.append(benefit)
                result["activated_benefit"] = benefit

        result["interacted_object"] = {"id": object_id, "name": obj.get("name")}
        return result

    def execute_npc_check(self, npc_name: str, action: str, attribute: str, dc: int) -> Dict:
        """
        为 NPC 执行一次 d20 检定，模拟 NPC 执行协任务的结果。
        成功后自动为玩家添加一个 active_benefit。
        """
        # NPC 默认属性取 8-14（平凡人），关系好的 NPC 视为 +2
        base_attr = 10
        rel = self.state.npcs.get(npc_name, {}).get("relationship", 0)
        rel_bonus = max(-2, min(4, rel // 20))  # -2 ~ +4
        attr_value = max(1, min(20, base_attr + rel_bonus))

        check_result = self.d20.execute_check(
            attribute_value=attr_value,
            dc=dc
        )

        log_entry = {
            "turn": self.state.turn_count,
            "npc": npc_name,
            "action": action,
            "attribute": attribute,
            "dc": dc,
            "check": check_result.to_dict()
        }
        self.state.npc_assist_log.append(log_entry)

        result = {
            "npc": npc_name,
            "action": action,
            "check": check_result.to_dict(),
            "relationship_bonus": rel_bonus
        }

        # 大成功或成功：添加 benefit
        if check_result.success:
            benefit = {
                "type": "npc_assist",
                "name": f"{npc_name}的协助",
                "description": f"{npc_name}成功执行了'{action}'，你接下来的相关行动获得加成",
                "dc_modifier": -3 if check_result.degree in ["大成功", "成功"] else -1,
                "advantage": check_result.degree == "大成功",
                "applies_to": [attribute] if attribute else [],
                "remaining_uses": 1,
                "source": f"npc:{npc_name}"
            }
            self.state.active_benefits.append(benefit)
            result["granted_benefit"] = benefit
        else:
            # 失败可能带来负面暗示
            if check_result.degree in ["失败", "大失败"]:
                result["warning"] = f"{npc_name}任务失败，敌方可能已警觉"

        return result

    def add_active_benefit(self, name: str, description: str, dc_modifier: int = 0,
                           advantage: bool = False, applies_to: Optional[List[str]] = None,
                           remaining_uses: int = 1) -> Dict:
        """主持人手动添加一个战术加成（通常用于记录玩家的前置准备）。"""
        benefit = {
            "type": "manual",
            "name": name,
            "description": description,
            "dc_modifier": dc_modifier,
            "advantage": advantage,
            "applies_to": applies_to or [],
            "remaining_uses": remaining_uses,
            "source": "host"
        }
        self.state.active_benefits.append(benefit)
        return {"added": True, "benefit": benefit}

    def consume_active_benefit(self, name: str) -> Optional[Dict]:
        """按名称消耗一个 active_benefit。"""
        for i, b in enumerate(self.state.active_benefits):
            if b.get("name") == name:
                b["remaining_uses"] -= 1
                consumed = b.copy()
                if b["remaining_uses"] <= 0:
                    self.state.active_benefits.pop(i)
                return {"consumed": consumed, "remaining": b.get("remaining_uses", 0)}
        return None

    def get_active_benefits(self, filter_attribute: Optional[str] = None) -> List[Dict]:
        """获取当前所有可用的战术加成，可选按属性过滤。"""
        self._clear_expired_benefits()
        if not filter_attribute:
            return [b.copy() for b in self.state.active_benefits]
        return [
            b.copy() for b in self.state.active_benefits
            if not b.get("applies_to") or filter_attribute in b.get("applies_to", [])
        ]

    def calculate_effective_dc(self, base_dc: int, attribute: str) -> Dict:
        """
        计算经过所有可用加成后的最终 DC，以及是否获得 advantage。
        """
        self._clear_expired_benefits()
        applicable = self.get_active_benefits(filter_attribute=attribute)

        total_modifier = 0
        has_advantage = False
        applied_benefits = []

        for b in applicable:
            # 只计算未用完且有 DC 修正或 advantage 的 benefit
            if b.get("remaining_uses", 0) > 0:
                mod = b.get("dc_modifier", 0)
                if mod:
                    total_modifier += mod
                    applied_benefits.append({"name": b["name"], "modifier": mod})
                if b.get("advantage"):
                    has_advantage = True
                    applied_benefits.append({"name": b["name"], "effect": "advantage"})

        effective_dc = max(1, base_dc + total_modifier)
        return {
            "base_dc": base_dc,
            "attribute": attribute,
            "applied_benefits": applied_benefits,
            "total_modifier": total_modifier,
            "effective_dc": effective_dc,
            "advantage": has_advantage
        }

    def _clear_expired_benefits(self):
        """清理已超过使用次数或来源不存在的过期 benefit。"""
        # 简单的 TTL 机制：可以按回合数过期（未来扩展）
        self.state.active_benefits = [
            b for b in self.state.active_benefits
            if b.get("remaining_uses", 0) > 0
        ]

    def _get_world_money_rate(self, world_setting: str) -> int:
        """
        根据世界观返回每回合基础金钱变化。
        正数 = 收入（工资、补贴、租金等）
        负数 = 开销（生活费、住宿费、维护费等）
        """
        setting_lower = world_setting.lower()
        if any(w in setting_lower for w in ["赛博", "科幻", "现代", "都市", "未来", "cyber", "sci-fi", "modern"]):
            return 5
        if any(w in setting_lower for w in ["太空", "space", "星际", "歌剧"]):
            return 8
        if any(w in setting_lower for w in ["谍战", "特工", "间谍", "spy"]):
            return 6
        if any(w in setting_lower for w in ["武侠", "古风", "古代", "江湖", "wuxia", "kungfu"]):
            return -2
        if any(w in setting_lower for w in ["黑帮", "mafia", "gang", "黑手"]):
            return -3
        if any(w in setting_lower for w in ["克苏鲁", "cthulhu", "调查"]):
            return -1
        if any(w in setting_lower for w in ["奇幻", "魔法", "fantasy", "magic"]):
            return -1
        if any(w in setting_lower for w in ["末日", "废土", "post-apocalyptic", "wasteland"]):
            return -4
        return 0

    def _get_world_start_gold(self, world_setting: str) -> int:
        """根据世界观返回初始金币数量"""
        setting_lower = world_setting.lower()
        if any(w in setting_lower for w in ["赛博", "科幻", "现代", "都市", "cyber", "sci-fi", "modern"]):
            return 200
        if any(w in setting_lower for w in ["太空", "space", "星际"]):
            return 500
        if any(w in setting_lower for w in ["谍战", "特工", "spy"]):
            return 300
        if any(w in setting_lower for w in ["武侠", "古风", "wuxia", "kungfu"]):
            return 50
        if any(w in setting_lower for w in ["黑帮", "mafia", "gang", "黑手"]):
            return 100
        if any(w in setting_lower for w in ["克苏鲁", "cthulhu", "调查"]):
            return 80
        if any(w in setting_lower for w in ["奇幻", "魔法", "fantasy", "magic"]):
            return 60
        if any(w in setting_lower for w in ["末日", "废土", "post-apocalyptic", "wasteland"]):
            return 20
        return 50

    def save_game(self, save_id: str = None) -> str:
        """保存游戏（更新game.json，包含事件历史和NPC记忆）"""
        game_dir = self._get_game_save_dir()
        os.makedirs(game_dir, exist_ok=True)
        
        # 如果传入了旧式save_id，仍然兼容旧行为（保存到指定文件名）
        if save_id:
            filepath = os.path.join(game_dir, f"{save_id}.json")
            data = self.state.to_dict()
            data["game_id"] = self.game_id
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return filepath
        
        # 新格式：统一保存到game.json
        filepath = os.path.join(game_dir, "game.json")
        
        # 构建存档内容
        state_data = self.state.to_dict()
        state_data["game_id"] = self.game_id
        
        save_data = {
            "game_id": self.game_id,
            "version": self.state.VERSION,
            "state": state_data,
            "events": self._build_event_history(),
            "npc_memories": self._build_npc_memory_snapshot(),
            "saved_at": datetime.now().isoformat()
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
        return filepath

    def _build_event_history(self) -> List[Dict]:
        """构建事件历史（最近10条详细 + 压缩的旧事件）"""
        history = self.state.history
        
        if len(history) <= 10:
            # 全部保持详细
            return [self._event_to_detailed(h) for h in history]
        
        # 最近10条详细
        recent = history[-10:]
        detailed = [self._event_to_detailed(h) for h in recent]
        
        # 更早的事件压缩（每5条压缩成1条）
        older = history[:-10]
        compressed = []
        for i in range(0, len(older), 5):
            batch = older[i:i+5]
            compressed.append(self._compress_event_batch(batch))
        
        return compressed + detailed

    def _event_to_detailed(self, h: Dict) -> Dict:
        """将history条目转换为详细事件格式"""
        result = h.get("result", {})
        degree = ""
        if self.show_dice:
            check = result.get("check", {})
            degree = check.get("degree", "") if isinstance(check, dict) else ""
        else:
            degree = result.get("degree", "")
        
        return {
            "type": "detailed",
            "turn": h["turn"],
            "action": h["action"],
            "summary": result.get("narrative", "")[:100],
            "degree": degree
        }

    def _compress_event_batch(self, batch: List[Dict]) -> Dict:
        """将一批事件压缩为摘要"""
        turns = [h["turn"] for h in batch]
        actions = [h["action"] for h in batch]
        
        # 回退压缩：生成基础摘要
        action_summary = ", ".join(actions[:3])
        if len(actions) > 3:
            action_summary += f" 等{len(actions)}次行动"
        
        summary = f"回合{min(turns)}-{max(turns)}：{action_summary}"
        
        return {
            "type": "compressed",
            "turns_covered": turns,
            "summary": summary
        }

    def _build_npc_memory_snapshot(self) -> Dict:
        """构建NPC记忆快照"""
        snapshot = {}
        for name, npc in self.state.npcs.items():
            snapshot[name] = {
                "memories": npc.get("memories", []),
                "last_updated_turn": self.state.turn_count
            }
        return snapshot

    def load_game(self, save_id: str = None) -> bool:
        """加载游戏（支持旧版save_id和新版game.json）"""
        game_dir = self._get_game_save_dir()
        
        # 先尝试新格式：game.json
        filepath = os.path.join(game_dir, "game.json")
        if not os.path.exists(filepath):
            # 回退到旧格式：按save_id加载
            if save_id:
                filepath = os.path.join(game_dir, f"{save_id}.json")
                if not os.path.exists(filepath):
                    return False
            else:
                return False
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 新格式：包含 state / events / npc_memories
        if "state" in data:
            self.state = GameState.from_dict(data["state"])
            if "game_id" in data:
                self.game_id = data["game_id"]
            # 恢复NPC记忆（如果state中缺失，从npc_memories补回）
            if "npc_memories" in data:
                self._restore_npc_memories(data["npc_memories"])
            return True
        
        # 旧格式：直接是 GameState.to_dict()
        self.state = GameState.from_dict(data)
        if "game_id" in data:
            self.game_id = data["game_id"]
        return True

    def _restore_npc_memories(self, npc_memories: Dict):
        """从存档快照恢复NPC记忆（如果state中缺失）"""
        for name, mem_data in npc_memories.items():
            if name in self.state.npcs:
                npc = self.state.npcs[name]
                # 如果state中记忆为空但快照中有，补回
                if not npc.get("memories") and mem_data.get("memories"):
                    npc["memories"] = mem_data["memories"]
            else:
                # NPC完全缺失，创建一个基础结构（保留记忆）
                self.state.update_npc(name)
                self.state.npcs[name]["memories"] = mem_data.get("memories", [])

    @staticmethod
    def list_games(save_dir: str = "./saves") -> List[Dict]:
        """列出所有游戏目录"""
        games = []
        if not os.path.exists(save_dir):
            return games
        for name in os.listdir(save_dir):
            path = os.path.join(save_dir, name)
            if os.path.isdir(path):
                game_json = os.path.join(path, "game.json")
                if os.path.exists(game_json):
                    try:
                        with open(game_json, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        games.append({
                            "game_id": name,
                            "world_setting": data.get("world_setting", ""),
                            "player_name": data.get("player", {}).get("name", ""),
                            "turn_count": data.get("turn_count", 0),
                            "path": path
                        })
                    except Exception:
                        pass
        return games

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
    """CLI模式入口 - 带ABCDE选项"""
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
    print(f"游戏ID: {result['game_id']}")
    print(f"属性: {result['player']['attributes']}")

    previous_result = None

    # 游戏循环
    while not skill.state.ending_triggered and not skill.state.death_triggered:
        print(f"\n{'='*50}")
        print(f"场景: {skill.state.current_scene}")
        print(f"回合 {skill.state.turn_count + 1}")
        print(f"HP: {skill.state.hp}/{skill.state.max_hp}")
        print("-"*50)

        # 生成选项
        print("\n正在生成本回合选项...")
        options = skill.generate_turn_options(previous_result)

        # 显示情境
        print(f"\n【情境】{options.context}")

        # 显示选项
        print("\n【可选行动】")
        for opt in options.options:
            attr_str = f"[{opt.attr_hint}]" if opt.attr_hint else ""
            dc_str = f"(DC{opt.dc_hint})" if opt.dc_hint else ""
            print(f"  {opt.letter}. {opt.description} {attr_str} {dc_str}")
        print(f"  E. {options.free_text.description}")

        # 获取玩家选择
        print("-"*50)
        choice = input("你的选择 (A/B/C/D/E): ").strip().upper()

        if choice == "E":
            free_input = input("描述你的行动: ").strip()
            if not free_input:
                print("[错误] 选择E时需要描述行动")
                continue
        elif choice in ["A", "B", "C", "D"]:
            option = options.get_option(choice)
            if not option:
                print(f"[错误] 无效选项: {choice}")
                continue
            free_input = None
            print(f"你选择了: {option.description}")
        elif choice.lower() in ["save", "保存"]:
            save_id = input("存档ID: ") or "auto"
            path = skill.save_game(save_id)
            print(f"已保存到: {path}")
            continue
        elif choice.lower() in ["quit", "退出"]:
            break
        else:
            print(f"[错误] 无效输入: {choice}，请输入A/B/C/D/E")
            continue

        # 处理回合
        print("\n处理中...")
        result = skill.process_option(options, choice, free_input)

        if "error" in result:
            print(f"[错误] {result['error']}")
            continue

        # 显示结果
        if skill.show_dice:
            # 显示详细骰子结果
            check = result['check']
            print(f"\n【检定】{check['degree']}")
            print(f"骰子: {check['roll']} + 修正{check['modifier']:+d} = {check['total']} vs DC{check['dc']}")
        else:
            # 只显示结果程度，不显示骰子细节
            print(f"\n【结果】{result.get('degree', '未知')}")
        print(f"\n【剧情】")
        print(result['narrative'])

        # 显示结算信息
        settlement = result.get('settlement', {})
        if settlement.get('auto_hp_change') != 0:
            print(f"\n【结算】HP自动变化: {settlement['auto_hp_change']:+d} (当前: {skill.state.hp}/{skill.state.max_hp})")
        if settlement.get('money_change') != 0:
            print(f"【结算】金钱结算: {settlement['money_change']:+d} 金币 (当前: {skill.state.resources.get('金币', 0)})")
        if settlement.get('ticked_effects'):
            print(f"【结算】状态效果消退: {', '.join(settlement['ticked_effects'])}")
        if settlement.get('death_triggered'):
            print(f"\n{'='*50}")
            print("角色已死亡。")
            break

        # 保存结果供下回合使用
        previous_result = result

        if result.get('ending_triggered'):
            print(f"\n{'='*50}")
            print(f"游戏结束: {result.get('ending_type', '结局')}")
            break


if __name__ == "__main__":
    cli_main()

