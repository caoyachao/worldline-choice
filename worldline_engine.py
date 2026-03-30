#!/usr/bin/env python3
"""
Worldline Choice - AI驱动互动叙事游戏引擎 v3.3
通用挑战框架版 - 严格检定系统，适应任何世界观
新增：叙事取巧检测（编造资源、跳过检定）
新增：复合行动分步检定系统
新增：战术多步骤判定系统（完整版，无步骤限制）
"""

import json
import os
import sys
import re
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import random

# ============ 通用能力维度定义 ============
class AttributeDimension(Enum):
    """6个通用能力维度 - 适配任何世界观"""
    FORCE = "FORCE"           # 原始力量/战斗力
    MIND = "MIND"             # 心智/智慧
    INFLUENCE = "INFLUENCE"   # 影响力/魅力
    REFLEX = "REFLEX"         # 反应/敏捷
    RESILIENCE = "RESILIENCE" # 韧性/耐久
    LUCK = "LUCK"             # 运气/机遇

# 维度描述（用于AI理解）
ATTRIBUTE_DESCRIPTIONS = {
    AttributeDimension.FORCE: "物理力量、战斗能力、伤害输出",
    AttributeDimension.MIND: "智力、策略、推理、知识",
    AttributeDimension.INFLUENCE: "说服力、领导力、欺骗、社交",
    AttributeDimension.REFLEX: "反应速度、敏捷、闪避、潜行",
    AttributeDimension.RESILIENCE: "承受伤害、耐力、意志力、恢复",
    AttributeDimension.LUCK: "随机事件、意外发现、机缘、巧合"
}

# ============ 难度等级定义 ============
class DifficultyLevel(Enum):
    SIMPLE = (5, "简单", 0.9)
    NORMAL = (10, "普通", 0.7)
    HARD = (15, "困难", 0.5)
    VERY_HARD = (20, "极难", 0.3)
    IMPOSSIBLE = (25, "不可能", 0.1)
    
    def __init__(self, dc, label, base_rate):
        self.dc = dc
        self.label = label
        self.base_rate = base_rate

# ============ 检定结果定义 ============
@dataclass
class CheckResult:
    """检定结果"""
    success: bool
    roll: int
    modifier: int
    total: int
    difficulty: int
    margin: int
    degree: str
    attribute: str
    narrative: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "roll": self.roll,
            "modifier": self.modifier,
            "total": self.total,
            "difficulty": self.difficulty,
            "margin": self.margin,
            "degree": self.degree,
            "attribute": self.attribute
        }

# ============ 行动分析结果 ============
@dataclass
class ActionProfile:
    """标准化的行动档案"""
    raw_action: str
    action_type: str
    primary_attribute: AttributeDimension
    secondary_attribute: Optional[AttributeDimension]
    target: Optional[str]
    environment_factor: int  # -5到+5
    time_pressure: int       # 0到10
    required_items: List[str] = field(default_factory=list)
    required_tags: List[str] = field(default_factory=list)
    required_secrets: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "action": self.raw_action,
            "type": self.action_type,
            "primary_attr": self.primary_attribute.value,
            "secondary_attr": self.secondary_attribute.value if self.secondary_attribute else None,
            "target": self.target,
            "env_factor": self.environment_factor,
            "time_pressure": self.time_pressure,
            "requirements": {
                "items": self.required_items,
                "tags": self.required_tags,
                "secrets": self.required_secrets
            }
        }

# ============ 世界规则定义 ============
@dataclass
class WorldRules:
    """世界观规则 - AI在游戏初始化时生成"""
    world_setting: str
    attributes: Dict[AttributeDimension, str]  # 维度->本世界名称
    impossible_rules: List[str]                # 硬边界规则
    difficulty_baseline: Dict[str, int]        # 难度基准值
    action_templates: Dict[str, str]           # 行动类型模板
    resource_names: Dict[str, str]             # 资源名称映射
    
    @classmethod
    def generate_default(cls, world_setting: str) -> 'WorldRules':
        """生成默认规则（当AI未提供时使用）"""
        return cls(
            world_setting=world_setting,
            attributes={
                AttributeDimension.FORCE: "武力",
                AttributeDimension.MIND: "智力",
                AttributeDimension.INFLUENCE: "魅力",
                AttributeDimension.REFLEX: "敏捷",
                AttributeDimension.RESILIENCE: "体质",
                AttributeDimension.LUCK: "运气"
            },
            impossible_rules=[
                "凡人无法飞行",
                "新手无法击败大师",
                "没有钥匙无法开锁"
            ],
            difficulty_baseline={
                "简单": 5, "普通": 10, "困难": 15, "极难": 20, "不可能": 25
            },
            action_templates={
                "战斗": "FORCE vs 对方FORCE或RESILIENCE",
                "说服": "INFLUENCE vs 对方MIND",
                "潜行": "REFLEX vs 对方MIND",
                "解谜": "MIND",
                "承受": "RESILIENCE"
            },
            resource_names={
                "health": "生命值",
                "stamina": "体力",
                "money": "金钱",
                "time": "时间",
                "reputation": "声望"
            }
        )
    
    def to_dict(self) -> Dict:
        return {
            "world": self.world_setting,
            "attributes": {k.value: v for k, v in self.attributes.items()},
            "impossible_rules": self.impossible_rules,
            "difficulty": self.difficulty_baseline,
            "templates": self.action_templates
        }

# ============ 游戏状态管理 ============
class GameState:
    """管理游戏的所有状态数据"""
    
    VERSION = "3.0"
    
    def __init__(self):
        # 世界观
        self.world_setting = ""
        self.world_description = ""
        self.world_rules: Optional[WorldRules] = None
        
        # 场景
        self.current_scene = ""
        self.scene_context = ""
        self.turn_count = 0
        
        # 玩家状态
        self.player = {
            "name": "",
            "role": "",
            "backstory": "",
            "attributes": {},  # 使用世界规则中的属性名
            "items": [],
            "tags": [],
            "secrets": [],
            "resources": {}    # 通用资源
        }
        
        # NPC
        self.npcs: Dict[str, Dict] = {}
        
        # 游戏标记
        self.flags: Dict[str, Any] = {}
        
        # 历史系统
        self.raw_history: List[Dict] = []
        self.history_summaries: List[Dict] = []
        self.milestones: List[Dict] = []
        
        # 结局
        self.ending_triggered = False
        self.ending_type = None
        
        # 代价追踪
        self.costs_paid: List[Dict] = []
        self.moral_corruption = 0
        self.broken_trust: List[str] = []
        
        # 自适应难度
        self.difficulty_bias = 0
        self.edge_cases: List[Dict] = []
        
        # 元数据
        self.start_time = datetime.now().isoformat()
        self.total_play_time_minutes = 0
    
    def initialize_resources(self):
        """初始化通用资源"""
        if self.world_rules:
            resource_names = self.world_rules.resource_names
        else:
            resource_names = {
                "health": "生命值",
                "stamina": "体力",
                "money": "金钱",
                "time": "时间",
                "reputation": "声望"
            }
        
        self.player["resources"] = {
            "health": 100,
            "stamina": 100,
            "money": 50,
            "time": 10,
            "reputation": 0
        }
    
    def to_dict(self) -> Dict:
        return {
            "version": self.VERSION,
            "save_time": datetime.now().isoformat(),
            "world_setting": self.world_setting,
            "world_description": self.world_description,
            "world_rules": self.world_rules.to_dict() if self.world_rules else None,
            "current_scene": self.current_scene,
            "scene_context": self.scene_context,
            "turn_count": self.turn_count,
            "player": self.player,
            "npcs": self.npcs,
            "flags": self.flags,
            "history": {
                "raw": self.raw_history,
                "summaries": self.history_summaries,
                "milestones": self.milestones,
                "recent_summary": self._generate_recent_summary()
            },
            "ending_triggered": self.ending_triggered,
            "ending_type": self.ending_type,
            "costs_paid": self.costs_paid,
            "moral_corruption": self.moral_corruption,
            "broken_trust": self.broken_trust,
            "difficulty_bias": self.difficulty_bias,
            "edge_cases": self.edge_cases,
            "metadata": {
                "start_time": self.start_time,
                "total_play_time_minutes": self.total_play_time_minutes
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'GameState':
        state = cls()
        state.world_setting = data.get("world_setting", "")
        state.world_description = data.get("world_description", "")
        
        # 恢复世界规则
        rules_data = data.get("world_rules")
        if rules_data:
            attrs = {AttributeDimension(k): v for k, v in rules_data.get("attributes", {}).items()}
            state.world_rules = WorldRules(
                world_setting=rules_data.get("world", ""),
                attributes=attrs,
                impossible_rules=rules_data.get("impossible_rules", []),
                difficulty_baseline=rules_data.get("difficulty", {}),
                action_templates=rules_data.get("templates", {}),
                resource_names={
                    "health": "生命值",
                    "stamina": "体力",
                    "money": "金钱",
                    "time": "时间",
                    "reputation": "声望"
                }
            )
        
        state.current_scene = data.get("current_scene", "")
        state.scene_context = data.get("scene_context", "")
        state.turn_count = data.get("turn_count", 0)
        state.player = data.get("player", state.player)
        state.npcs = data.get("npcs", {})
        state.flags = data.get("flags", {})
        
        history_data = data.get("history", {})
        state.raw_history = history_data.get("raw", [])
        state.history_summaries = history_data.get("summaries", [])
        state.milestones = history_data.get("milestones", [])
        
        state.ending_triggered = data.get("ending_triggered", False)
        state.ending_type = data.get("ending_type")
        state.costs_paid = data.get("costs_paid", [])
        state.moral_corruption = data.get("moral_corruption", 0)
        state.broken_trust = data.get("broken_trust", [])
        state.difficulty_bias = data.get("difficulty_bias", 0)
        state.edge_cases = data.get("edge_cases", [])
        
        metadata = data.get("metadata", {})
        state.start_time = metadata.get("start_time", datetime.now().isoformat())
        state.total_play_time_minutes = metadata.get("total_play_time_minutes", 0)
        
        return state
    
    def update_npc(self, name: str, **kwargs):
        """更新NPC状态"""
        if name not in self.npcs:
            self.npcs[name] = {
                "relationship": 0,
                "attitude": "中立",
                "secrets": [],
                "status": "正常",
                "attributes": {}  # NPC也有属性
            }
        self.npcs[name].update(kwargs)
    
    def add_history(self, action: str, result: str, consequences: Dict = None, 
                    check_result: CheckResult = None):
        """添加历史记录"""
        self.turn_count += 1
        
        summary = self._generate_turn_summary(action, result, consequences)
        
        record = {
            "turn": self.turn_count,
            "action": action,
            "result": result,
            "summary": summary,
            "timestamp": datetime.now().isoformat(),
            "state_snapshot": {
                "attributes": self.player.get("attributes", {}).copy(),
                "resources": self.player.get("resources", {}).copy(),
                "tags": self.player.get("tags", []).copy(),
                "items_count": len(self.player.get("items", [])),
                "npc_relations": {name: info.get("relationship", 0) 
                                 for name, info in self.npcs.items()}
            },
            "consequences": consequences or {},
            "check_result": check_result.to_dict() if check_result else None
        }
        
        self.raw_history.append(record)
        self._check_milestones()
        self._update_summaries()
    
    def _generate_turn_summary(self, action: str, result: str, consequences: Dict) -> str:
        """生成回合摘要"""
        action_short = action[:30] + "..." if len(action) > 30 else action
        summary_parts = [f"回合{self.turn_count}: {action_short}"]
        
        if consequences:
            attr_changes = consequences.get("attribute_changes", {})
            if attr_changes:
                changes = [f"{k}{v:+d}" for k, v in attr_changes.items() if v != 0]
                if changes:
                    summary_parts.append(f"属性: {', '.join(changes)}")
            
            resource_changes = consequences.get("resource_changes", {})
            if resource_changes:
                res_changes = [f"{k}{v:+d}" for k, v in resource_changes.items() if v != 0]
                if res_changes:
                    summary_parts.append(f"资源: {', '.join(res_changes)}")
        
        return " | ".join(summary_parts)
    
    def _check_milestones(self):
        """检查里程碑"""
        important_flags = ["投曹", "投袁", "自立", "背叛", "结盟", "死亡", "胜利"]
        for flag in important_flags:
            if flag in self.flags and flag not in [m.get("flag") for m in self.milestones]:
                self.milestones.append({
                    "turn": self.turn_count,
                    "flag": flag,
                    "description": f"达成: {flag}",
                    "timestamp": datetime.now().isoformat()
                })
    
    def _update_summaries(self):
        """更新分层摘要"""
        if self.turn_count % 10 == 0 and self.turn_count > 0:
            start_turn = self.turn_count - 9
            end_turn = self.turn_count
            
            turn_records = [r for r in self.raw_history 
                          if start_turn <= r["turn"] <= end_turn]
            
            if turn_records:
                summary = self._create_period_summary(start_turn, end_turn, turn_records)
                self.history_summaries.append(summary)
    
    def _create_period_summary(self, start_turn: int, end_turn: int, 
                               records: List[Dict]) -> Dict:
        """创建阶段摘要"""
        key_decisions = [r["action"][:50] for r in records[:3]]
        
        total_attr_changes = {}
        for record in records:
            cons = record.get("consequences", {})
            attr_changes = cons.get("attribute_changes", {})
            for attr, delta in attr_changes.items():
                total_attr_changes[attr] = total_attr_changes.get(attr, 0) + delta
        
        return {
            "turn_range": f"{start_turn}-{end_turn}",
            "summary": f"第{start_turn}-{end_turn}回合",
            "key_decisions": key_decisions,
            "state_changes": total_attr_changes,
            "generated_at": datetime.now().isoformat()
        }
    
    def _generate_recent_summary(self) -> str:
        """生成最近摘要"""
        if not self.raw_history:
            return "游戏刚开始"
        recent = self.raw_history[-5:]
        return "\n".join([r["summary"] for r in recent])
    
    def get_history_for_ai(self) -> str:
        """为AI组装历史上下文"""
        parts = []
        
        if self.raw_history:
            recent = self.raw_history[-5:]
            recent_text = "\n".join([
                f"回合{r['turn']}: {r['action']}"
                for r in recent
            ])
            parts.append(f"【最近5回合】\n{recent_text}")
        
        if self.milestones:
            milestone_text = " -> ".join([m["flag"] for m in self.milestones[-5:]])
            parts.append(f"【里程碑】\n{milestone_text}")
        
        return "\n\n".join(parts) if parts else "游戏刚开始"
    
    def get_attribute_value(self, dimension: AttributeDimension) -> int:
        """获取属性值（通过世界规则映射）"""
        if not self.world_rules:
            return 10
        attr_name = self.world_rules.attributes.get(dimension, dimension.value)
        return self.player["attributes"].get(attr_name, 10)


# ============ 通用挑战引擎 ============
class UniversalChallengeEngine:
    """
    通用挑战判定引擎
    基于相对能力和客观规则，不依赖具体世界观
    """
    
    def __init__(self, game_state: GameState):
        self.state = game_state
        self.last_check_result: Optional[CheckResult] = None
    
    def analyze_action(self, action_text: str, context: Dict = None) -> ActionProfile:
        """
        解析玩家行动 - 标准化为系统可理解的格式
        使用启发式规则进行初步分析
        """
        action_lower = action_text.lower()
        context = context or {}
        
        # 识别行动类型（启发式）
        action_type = self._identify_action_type(action_text)
        
        # 确定主属性
        primary_attr = self._get_primary_attribute(action_type, action_text)
        
        # 确定副属性（如果有）
        secondary_attr = self._get_secondary_attribute(action_type)
        
        # 识别目标
        target = self._identify_target(action_text)
        
        # 环境因素
        env_factor = context.get("environment", 0)
        
        # 时间压力
        time_pressure = context.get("time_pressure", 0)
        
        # 识别可能的物品需求（启发式）
        required_items = self._identify_required_items(action_text)
        
        return ActionProfile(
            raw_action=action_text,
            action_type=action_type,
            primary_attribute=primary_attr,
            secondary_attribute=secondary_attr,
            target=target,
            environment_factor=env_factor,
            time_pressure=time_pressure,
            required_items=required_items
        )
    
    def _identify_action_type(self, action: str) -> str:
        """识别行动类型"""
        action_lower = action.lower()
        
        # 战斗相关
        if any(w in action_lower for w in ["打", "杀", "战", "斗", "攻", "击", "战斗", "杀", "砍", "刺", "射"]):
            return "战斗"
        
        # 说服相关
        if any(w in action_lower for w in ["说服", "劝", "骗", "诈", "哄", "忽悠", "谈", "聊", "请求"]):
            return "说服"
        
        # 潜行相关
        if any(w in action_lower for w in ["潜", "躲", "藏", "偷", "溜", "爬", "绕", "避", "隐"]):
            return "潜行"
        
        # 解谜相关
        if any(w in action_lower for w in ["解", "想", "分析", "推理", "思考", "研究", "查", "找线索"]):
            return "解谜"
        
        # 探索相关
        if any(w in action_lower for w in ["走", "去", "到", "探索", "调查", "搜索", "看", "观察"]):
            return "探索"
        
        # 制作相关
        if any(w in action_lower for w in ["做", "造", "制", "炼", "合成", "打造", "准备"]):
            return "制作"
        
        return "其他"
    
    def _get_primary_attribute(self, action_type: str, action_text: str) -> AttributeDimension:
        """确定主属性"""
        mapping = {
            "战斗": AttributeDimension.FORCE,
            "说服": AttributeDimension.INFLUENCE,
            "潜行": AttributeDimension.REFLEX,
            "解谜": AttributeDimension.MIND,
            "探索": AttributeDimension.REFLEX,
            "制作": AttributeDimension.MIND,
        }
        return mapping.get(action_type, AttributeDimension.MIND)
    
    def _get_secondary_attribute(self, action_type: str) -> Optional[AttributeDimension]:
        """确定副属性"""
        mapping = {
            "战斗": AttributeDimension.RESILIENCE,
            "说服": AttributeDimension.MIND,
            "潜行": AttributeDimension.LUCK,
            "解谜": AttributeDimension.LUCK,
        }
        return mapping.get(action_type)
    
    def _identify_target(self, action: str) -> Optional[str]:
        """识别目标（简化版）"""
        # 从action中提取可能的NPC或对象名
        # 这里使用简单启发式，实际可由AI提取
        return None
    
    def _identify_required_items(self, action: str) -> List[str]:
        """识别可能需要的物品"""
        items = []
        action_lower = action.lower()
        
        # 开锁
        if any(w in action_lower for w in ["开锁", "撬锁", "开门"]):
            items.append("开锁工具")
        
        # 攀爬
        if any(w in action_lower for w in ["爬", "攀"]):
            items.append("绳索")
        
        # 远程攻击
        if any(w in action_lower for w in ["射", "箭", "弓"]):
            items.append("弓箭")
        
        # 照明
        if any(w in action_lower for w in ["黑暗", "夜", "洞"]):
            items.append("光源")
        
        return items
    
    # ========== 复合行动（分步检定）支持 ==========
    
    # ========== 多步骤战术解析系统（完整版 v3.3）==========
    
    # 步骤依赖关系定义
    STEP_DEPENDENCIES = {
        "偷袭": {"boosts": ["埋伏", "合围", "总攻"], "requires": []},
        "埋伏": {"boosts": ["合围", "总攻", "伏击"], "requires": []},
        "诈败": {"boosts": ["合围", "伏击", "包围"], "requires": ["埋伏"]},
        "诱敌": {"boosts": ["合围", "伏击", "包围"], "requires": ["埋伏"]},
        "佯攻": {"boosts": ["主攻", "奇袭"], "requires": []},
        "粮草": {"boosts": ["总攻"], "requires": []},
        "侦察": {"boosts": ["偷袭", "埋伏", "奇袭"], "requires": []},
        "准备": {"boosts": ["攻击", "总攻", "奇袭"], "requires": []},
    }
    
    def is_tactical_multi_step(self, action_text: str) -> bool:
        """
        检测是否为战术多步骤行动
        识别列表式步骤描述（派X做Y，派Z做W...）
        """
        action_clean = action_text.lower().replace(' ', '').replace('，', ',')
        
        # 方法0: 检测数字标识模式（1. 2. 3. 或 1、2、3、）
        # 这是用户明确标记的多步骤格式，最可靠
        number_pattern = r'(?:^|\D)([1-9])\s*[\.、\)）]\s*'
        number_matches = list(re.finditer(number_pattern, action_text))
        if len(number_matches) >= 2:
            return True
        
        # 检测是否有多个"派..."或"安排..."结构
        dispatch_count = len(re.findall(r'(?:派|安排|命令|令)', action_clean))
        if dispatch_count >= 2:
            return True
        
        # 检测数字+人/兵力分配
        troop_patterns = len(re.findall(r'\d+(?:人|个|名|兵|卒|骑)', action_clean))
        if troop_patterns >= 2:
            return True
        
        # 检测明确的多步骤标记
        step_markers = ['第一步', '第二步', '第三步', '首先', '其次', '然后', '接着', '最后',
                       '先', '再', '又', '继而', '末了', '最终', '同时', '一边']
        marker_count = sum(1 for marker in step_markers if marker in action_clean)
        if marker_count >= 2:
            return True
        
        # 检测兵力分配词
        allocation_markers = ['剩下', '剩余', '其余', '另外', '主力', '亲卫', '精锐']
        allocation_count = sum(1 for marker in allocation_markers if marker in action_clean)
        if allocation_count >= 2:
            return True
        
        # 检测亲率/亲自
        if '亲率' in action_clean or '亲自' in action_clean or '本将' in action_clean:
            # 如果有亲率，并且有其他行动标记
            if any(m in action_clean for m in ['命令', '令', '派', '又']):
                return True
        
        return False
    
    def parse_tactical_steps(self, action_text: str) -> List[Dict]:
        """
        解析战术多步骤行动 - v3.3增强版
        支持任意数量的步骤，多种句式混合
        优先级：数字标识 > 综合模式 > 步骤标记 > 连接词
        """
        # 清理文本
        action_clean = action_text.lower().replace(' ', '').replace('，', ',').replace('。', ',').replace('\n', ',')
        
        steps = []
        
        # 方法0: 数字标识解析（优先级最高，用户明确标记）
        number_steps = self._parse_by_number_markers(action_text)
        if len(number_steps) >= 2:
            steps = number_steps
        
        # 方法1: 综合模式解析（支持多种句式混合）
        if not steps:
            steps = self._parse_comprehensive(action_clean)
        
        # 方法2: 如果综合解析步骤太少，尝试按步骤标记解析
        if len(steps) < 2:
            marker_steps = self._parse_by_step_markers(action_clean)
            if len(marker_steps) > len(steps):
                steps = marker_steps
        
        # 方法3: 如果还是没有，尝试按连接词分割
        if not steps:
            steps = self._parse_by_connectors(action_clean)
        
        # 建立步骤间依赖关系
        self._establish_step_dependencies(steps)
        
        return steps
    
    def _parse_comprehensive(self, action_text: str) -> List[Dict]:
        """
        综合解析方法 - 支持多种句式混合
        """
        steps = []
        step_index = 0
        
        # 定义所有可能的步骤模式（按优先级排序）
        patterns = [
            # 模式1: 派/安排/命令 X人做Y
            (r'(?:派|安排|命令|让|使)(\d+)?(?:人|个|名|支|队|兵|卒|骑|将士)?([^，,；;]+?)(?=，|,|；|;|$)', '派兵'),
            # 模式2: 剩下/剩余/其余 X人做Y
            (r'(?:剩下|剩余|其余|另外|再|又|另)(\d+)?(?:人|个|名|支|队|兵|卒|骑|将士)?([^，,；;]+?)(?=，|,|；|;|$)', '剩余'),
            # 模式3: 主力/亲卫/精锐做Y
            (r'(?:主力|亲卫|精锐|中军|前锋|后卫|左翼|右翼)([^，,；;]+?)(?=，|,|；|;|$)', '主力'),
            # 模式4: 我/吾/某亲率做Y
            (r'(?:我|吾|某|本将|本帅|本将军|亲自)([^，,；;]+?)(?=，|,|；|;|$)', '亲率'),
            # 模式5: 然后/接着/随后/再/又做Y
            (r'(?:然后|接着|随后|再|又|之后|继而)([^，,；;]+?)(?=，|,|；|;|$)', '后续'),
            # 模式6: 最后/最终/末了做Y
            (r'(?:最后|最终|末了|终|结局)([^，,；;]+?)(?=，|,|；|;|$)', '最终'),
            # 模式7: 第一步/首先做Y
            (r'(?:第一步|首先|起初|先)([^，,；;]+?)(?=，|,|；|;|$)', '首先'),
            # 模式8: 同时/一边...一边
            (r'(?:同时|与此同时|一边)([^，,；;]+?)(?=，|,|；|;|$)', '同时'),
        ]
        
        # 记录已匹配的文本位置，避免重复
        matched_positions = set()
        
        for pattern, pattern_type in patterns:
            for match in re.finditer(pattern, action_text):
                # 检查是否与已匹配区域重叠
                start, end = match.span()
                if any(start < pos < end or pos < start < end_pos for pos, end_pos in matched_positions):
                    continue
                
                # 提取信息
                groups = match.groups()
                if len(groups) >= 2 and groups[0]:  # 有兵力数字
                    troop_info = groups[0]
                    action_desc = groups[1].strip()
                elif len(groups) >= 1:  # 无兵力数字
                    troop_info = None
                    action_desc = groups[-1].strip()
                else:
                    continue
                
                if not action_desc or len(action_desc) < 3:
                    continue
                
                # 创建步骤
                step_info = self._analyze_tactical_step(action_desc, step_index, troop_info)
                step_info["pattern_type"] = pattern_type  # 记录匹配模式类型
                steps.append(step_info)
                step_index += 1
                
                # 记录匹配位置
                matched_positions.add((start, end))
        
        # 按原始文本中的顺序排序
        steps.sort(key=lambda x: x["index"])
        
        # 重新分配索引
        for i, step in enumerate(steps):
            step["index"] = i
        
        return steps
    
    def _analyze_tactical_step(self, step_text: str, step_index: int, 
                               troop_info: str = None) -> Dict:
        """
        分析战术步骤，提取更丰富的信息
        """
        profile = self.analyze_action(step_text)
        purpose = self._determine_tactical_purpose(step_text)
        
        # 提取目标
        target = self._extract_tactical_target(step_text)
        
        # 判断是否为关键步骤（失败会导致整体失败）
        is_critical = self._is_critical_step(purpose, step_text)
        
        # 计算基础DC（根据兵力、难度调整）
        base_dc = self._calculate_tactical_dc(profile, purpose, troop_info)
        
        return {
            "index": step_index,
            "text": step_text,
            "troop_info": troop_info,
            "action_type": profile.action_type,
            "primary_attribute": profile.primary_attribute,
            "secondary_attribute": profile.secondary_attribute,
            "purpose": purpose,
            "target": target,
            "is_critical": is_critical,
            "base_dc": base_dc,
            "dependencies": [],  # 依赖的前置步骤索引
            "boosts": [],        # 受益的后续步骤
            "result": None       # 执行结果（后填充）
        }
    
    def _determine_tactical_purpose(self, step_text: str) -> str:
        """
        确定战术步骤的目的（更细致的分类）
        """
        step_lower = step_text.lower()
        
        # 偷袭/奇袭
        if any(w in step_lower for w in ["偷袭", "奇袭", "夜袭", "劫营", "绕后", "迂回"]):
            return "偷袭"
        
        # 埋伏/伏击
        if any(w in step_lower for w in ["埋伏", "伏击", "设伏", "暗藏", "潜伏"]):
            return "埋伏"
        
        # 诱敌/诈败
        if any(w in step_lower for w in ["诱敌", "诈败", "佯败", "假逃", "引诱", "钓"]):
            return "诱敌"
        
        # 佯攻/牵制
        if any(w in step_lower for w in ["佯攻", "牵制", "吸引", "分散", "迷惑", "骚扰", "佯动"]):
            return "佯攻"
        
        # 粮草/后勤
        if any(w in step_lower for w in ["粮草", "粮道", "后勤", "补给", "焚粮", "劫粮", "烧粮"]):
            return "粮草"
        
        # 侦察/情报
        if any(w in step_lower for w in ["侦察", "探查", "打探", "侦查", "刺探", "探马", "哨探"]):
            return "侦察"
        
        # 合围/包围
        if any(w in step_lower for w in ["合围", "包围", "围困", "围剿", "围歼", "包饺子"]):
            return "合围"
        
        # 总攻/决战
        if any(w in step_lower for w in ["总攻", "决战", "猛攻", "强攻", "总攻击", "全力", "全歼"]):
            return "总攻"
        
        # 撤退/逃跑
        if any(w in step_lower for w in ["撤退", "撤离", "后退", "收兵", "鸣金"]):
            return "撤退"
        
        # 防守/固守
        if any(w in step_lower for w in ["防守", "固守", "坚守", "防御", "守阵", "稳守"]):
            return "防守"
        
        # 进攻/攻击（通用）
        if any(w in step_lower for w in ["进攻", "攻击", "攻打", "冲锋", "冲击", "交战", "出击"]):
            return "进攻"
        
        # 准备/部署
        if any(w in step_lower for w in ["准备", "部署", "安排", "布置", "整备", "待命"]):
            return "准备"
        
        return "其他"
    
    def _extract_tactical_target(self, step_text: str) -> Optional[str]:
        """
        提取战术目标
        """
        step_lower = step_text.lower()
        
        # 常见目标
        targets = [
            "粮草", "粮道", "敌军", "敌营", "敌阵", "主帅", "中军", "侧翼", "后方",
            "左翼", "右翼", "前锋", "后卫", "大营", "营寨", "城池", "关隘"
        ]
        
        for target in targets:
            if target in step_lower:
                return target
        
        return None
    
    def _is_critical_step(self, purpose: str, step_text: str) -> bool:
        """
        判断是否为关键步骤
        关键步骤失败会导致后续步骤无法执行或难度大增
        """
        critical_purposes = ["诱敌", "偷袭", "总攻", "合围"]
        return purpose in critical_purposes
    
    def _calculate_tactical_dc(self, profile: ActionProfile, purpose: str, 
                               troop_info: str) -> int:
        """
        计算战术步骤的DC
        考虑战术类型、兵力、属性等
        """
        base_dc = 10
        
        # 战术类型修正
        purpose_modifiers = {
            "侦察": -3,      # 侦察相对容易
            "准备": -2,      # 准备动作简单
            "佯攻": 0,       # 标准难度
            "偷袭": 2,       # 需要隐蔽
            "埋伏": 0,       # 标准难度
            "诱敌": 4,       # 需要演技和时机
            "粮草": 2,       # 需要突破防线
            "进攻": 0,       # 标准难度
            "防守": -1,      # 防守有优势
            "合围": 3,       # 需要协调
            "总攻": 5,       # 决战难度高
            "撤退": 2,       # 撤退也有风险
        }
        
        modifier = purpose_modifiers.get(purpose, 0)
        
        # 兵力影响（如果有具体数字）
        if troop_info and troop_info.isdigit():
            troop_num = int(troop_info)
            if troop_num < 50:
                modifier += 2  # 兵力太少，难度大
            elif troop_num > 500:
                modifier -= 1  # 兵力充足，略有优势
        
        return max(5, base_dc + modifier)
    
    def _parse_by_connectors(self, action_text: str) -> List[Dict]:
        """
        按连接词解析步骤
        """
        # 连接词列表
        connectors = ['，', ',', '；', ';', '。']
        
        # 分割文本
        parts = [action_text]
        for conn in connectors:
            new_parts = []
            for part in parts:
                new_parts.extend([p.strip() for p in part.split(conn) if p.strip()])
            parts = new_parts
        
        # 过滤太短的片段
        parts = [p for p in parts if len(p) >= 5]
        
        steps = []
        for i, part in enumerate(parts):
            step_info = self._analyze_tactical_step(part, i)
            steps.append(step_info)
        
        return steps
    
    def _parse_by_step_markers(self, action_text: str) -> List[Dict]:
        """
        按步骤标记解析（第一步...第二步...第三步...）
        增强版，支持更多标记和更灵活的匹配
        """
        steps = []
        
        # 定义步骤标记模式（按顺序）
        ordered_markers = [
            (r'(?:第一步|首先|起初|先)(.+?)(?=第二步|其次|然后|再|又|$)', '首先'),
            (r'(?:第二步|其次|然后|再)(.+?)(?=第三步|再次|然后|再|又|$)', '然后'),
            (r'(?:第三步|再次|然后|再)(.+?)(?=第四步|最后|最终|末了|$)', '再然后'),
            (r'(?:第四步|继而)(.+?)(?=第五步|最后|最终|末了|$)', '继而'),
            (r'(?:第五步|最后|最终|末了|终)(.+?)(?=$)', '最后'),
        ]
        
        for i, (pattern, marker_type) in enumerate(ordered_markers):
            match = re.search(pattern, action_text)
            if match:
                step_text = match.group(1).strip()
                # 去除开头的标点
                step_text = re.sub(r'^[，,；;。．\s]+', '', step_text)
                if step_text and len(step_text) >= 3:
                    step_info = self._analyze_tactical_step(step_text, len(steps))
                    step_info["pattern_type"] = marker_type
                    steps.append(step_info)
        
        return steps
    
    def _parse_by_number_markers(self, action_text: str) -> List[Dict]:
        """
        按数字标识解析步骤（用户明确标记的格式）
        格式: 1. 行动A，2. 行动B，3. 行动C
        或:   1、行动A，2、行动B
        或:   1) 行动A，2) 行动B
        
        相同数字 = 同时发生（复合行动）
        不同数字 = 顺序发生
        """
        steps = []
        
        # 数字标识模式: 数字 + [./、)] + 空格 + 内容
        # 捕获: 数字标记和对应的行动内容
        number_pattern = r'([1-9])\s*[\.、\)）]\s*([^\n,，；;。]+)'
        matches = list(re.finditer(number_pattern, action_text))
        
        if len(matches) < 2:
            return steps
        
        # 按数字分组
        number_groups = {}
        for match in matches:
            number = int(match.group(1))
            action_desc = match.group(2).strip()
            if action_desc and len(action_desc) >= 2:
                if number not in number_groups:
                    number_groups[number] = []
                number_groups[number].append(action_desc)
        
        # 按数字排序处理
        sorted_numbers = sorted(number_groups.keys())
        step_index = 0
        
        for number in sorted_numbers:
            actions = number_groups[number]
            
            if len(actions) == 1:
                # 单个行动
                step_info = self._analyze_tactical_step(actions[0], step_index)
                step_info["pattern_type"] = f"步骤{number}"
                step_info["step_number"] = number
                steps.append(step_info)
                step_index += 1
            else:
                # 多个行动共享同一数字 = 同时发生（复合行动）
                # 合并为一个复合步骤
                combined_action = "同时：" + "；".join(actions)
                step_info = self._analyze_tactical_step(combined_action, step_index)
                step_info["pattern_type"] = f"步骤{number}[同时]"
                step_info["step_number"] = number
                step_info["is_composite"] = True
                step_info["sub_actions"] = actions
                steps.append(step_info)
                step_index += 1
        
        return steps
    
    def _establish_step_dependencies(self, steps: List[Dict]):
        """
        建立步骤间的依赖关系
        """
        for i, step in enumerate(steps):
            purpose = step["purpose"]
            
            # 查找依赖定义
            dep_info = self.STEP_DEPENDENCIES.get(purpose, {})
            
            # 检查前置依赖
            for req in dep_info.get("requires", []):
                for j in range(i):
                    if steps[j]["purpose"] == req:
                        step["dependencies"].append(j)
                        steps[j]["boosts"].append(i)
                        break
            
            # 自动识别逻辑依赖（诱敌需要埋伏）
            if purpose in ["诱敌", "诈败"]:
                for j in range(i):
                    if steps[j]["purpose"] in ["埋伏", "偷袭"]:
                        if j not in step["dependencies"]:
                            step["dependencies"].append(j)
                            steps[j]["boosts"].append(i)
    
    def execute_tactical_check(self, steps: List[Dict]) -> Dict:
        """
        执行战术多步骤检定
        支持任意步骤数，建立完整的依赖链
        支持复合步骤（同时发生的多个行动）
        """
        step_results = []
        global_effects = {
            "dc_modifier": 0,
            "enemy_alert": 0,      # 敌人警觉度
            "troop_morale": 0,     # 士气变化
            "troop_losses": 0,     # 兵力损失
            "opportunities": []    # 创造的机会
        }
        
        # 标记是否继续执行（关键步骤失败可能中断）
        can_continue = True
        
        for i, step in enumerate(steps):
            if not can_continue:
                # 标记为跳过
                step_result = {
                    "step_index": i,
                    "step_text": step["text"],
                    "purpose": step["purpose"],
                    "status": "跳过",
                    "reason": "前置关键步骤失败，计划无法继续"
                }
                step_results.append(step_result)
                continue
            
            # 复合步骤处理（同时发生的多个行动）
            if step.get("is_composite") and step.get("sub_actions"):
                sub_results = []
                all_success = True
                any_critical_fail = False
                
                # 对每个子行动分别检定
                for sub_action in step["sub_actions"]:
                    sub_profile = ActionProfile(
                        raw_action=sub_action,
                        action_type=step["action_type"],
                        primary_attribute=step["primary_attribute"],
                        secondary_attribute=step["secondary_attribute"],
                        target=step["target"],
                        environment_factor=global_effects["enemy_alert"],
                        time_pressure=0
                    )
                    
                    # 复合步骤DC+2（同时执行更困难）
                    sub_dc = step["base_dc"] + global_effects["dc_modifier"] + 2
                    sub_dc = max(3, sub_dc)
                    
                    sub_check = self.execute_check(sub_profile, sub_dc)
                    sub_results.append({
                        "action": sub_action,
                        "check": sub_check.to_dict(),
                        "success": sub_check.success,
                        "degree": sub_check.degree
                    })
                    
                    if not sub_check.success:
                        all_success = False
                        if sub_check.degree in ["失败", "大失败"]:
                            any_critical_fail = True
                
                # 复合步骤整体结果
                composite_success = all_success or not any_critical_fail
                # 确定整体程度
                if all_success and all(r["check"]["margin"] >= 5 for r in sub_results):
                    composite_degree = "成功"
                elif all_success:
                    composite_degree = "勉强成功"
                elif not any_critical_fail:
                    composite_degree = "勉强失败"
                else:
                    composite_degree = "失败"
                
                step_result = {
                    "step_index": i,
                    "step_text": step["text"],
                    "troop_info": step.get("troop_info"),
                    "purpose": step["purpose"],
                    "target": step["target"],
                    "is_critical": step["is_critical"],
                    "is_composite": True,
                    "sub_results": sub_results,
                    "dc": step["base_dc"] + 2,
                    "base_dc": step["base_dc"],
                    "check": sub_results[0]["check"] if sub_results else {},  # 使用第一个作为代表
                    "success": composite_success,
                    "degree": composite_degree,
                    "dependencies": step.get("dependencies", []),
                    "boosts": step.get("boosts", [])
                }
                step_results.append(step_result)
                
                # 更新全局效果（基于复合结果）
                if composite_success:
                    global_effects["dc_modifier"] -= 2
                    global_effects["opportunities"].append(f"{step['purpose']}同步成功")
                else:
                    global_effects["enemy_alert"] += 1
                    global_effects["dc_modifier"] += 1
                
                # 检查是否关键步骤失败
                if step["is_critical"] and not composite_success and any_critical_fail:
                    can_continue = False
                
                continue
            
            # 普通步骤处理
            # 计算实际DC
            adjusted_dc = step["base_dc"] + global_effects["dc_modifier"]
            
            # 检查依赖步骤是否成功
            dep_bonus = 0
            for dep_idx in step.get("dependencies", []):
                if dep_idx < len(step_results):
                    dep_result = step_results[dep_idx]
                    if dep_result.get("success"):
                        dep_bonus -= 3  # 依赖成功，DC降低
                        global_effects["opportunities"].append(f"{step['purpose']}受益于{steps[dep_idx]['purpose']}")
                    else:
                        dep_bonus += 5  # 依赖失败，DC大增
            
            adjusted_dc += dep_bonus
            adjusted_dc = max(3, adjusted_dc)  # 最低DC为3
            
            # 执行检定
            profile = ActionProfile(
                raw_action=step["text"],
                action_type=step["action_type"],
                primary_attribute=step["primary_attribute"],
                secondary_attribute=step["secondary_attribute"],
                target=step["target"],
                environment_factor=global_effects["enemy_alert"],
                time_pressure=0
            )
            
            check_result = self.execute_check(profile, adjusted_dc)
            
            # 记录结果
            step_result = {
                "step_index": i,
                "step_text": step["text"],
                "troop_info": step.get("troop_info"),
                "purpose": step["purpose"],
                "target": step["target"],
                "is_critical": step["is_critical"],
                "dc": adjusted_dc,
                "base_dc": step["base_dc"],
                "check": check_result.to_dict(),
                "success": check_result.success,
                "degree": check_result.degree,
                "dependencies": step.get("dependencies", []),
                "boosts": step.get("boosts", [])
            }
            step_results.append(step_result)
            
            # 更新全局效果
            self._update_tactical_effects(global_effects, step, check_result)
            
            # 检查是否关键步骤失败
            if step["is_critical"] and not check_result.success:
                if check_result.degree in ["失败", "大失败"]:
                    can_continue = False
        
        # 计算整体结果
        return self._calculate_tactical_outcome(step_results, global_effects)
    
    def _update_tactical_effects(self, effects: Dict, step: Dict, 
                                  check_result: CheckResult):
        """
        更新战术效果
        """
        purpose = step["purpose"]
        
        # 偷袭成功
        if purpose == "偷袭":
            if check_result.success:
                effects["enemy_alert"] += 2
                effects["troop_morale"] += 5
                if check_result.degree == "大成功":
                    effects["dc_modifier"] -= 3  # 敌军混乱
            else:
                effects["troop_losses"] += 10
                effects["enemy_alert"] += 5
        
        # 埋伏成功
        elif purpose == "埋伏":
            if check_result.success:
                effects["dc_modifier"] -= 2
            else:
                effects["enemy_alert"] += 3
                effects["dc_modifier"] += 2
        
        # 诱敌成功
        elif purpose == "诱敌":
            if check_result.success:
                effects["dc_modifier"] -= 3
            else:
                effects["troop_morale"] -= 10
                effects["dc_modifier"] += 3
        
        # 总攻
        elif purpose == "总攻":
            if not check_result.success:
                effects["troop_losses"] += 20
                effects["troop_morale"] -= 15
        
        # 佯攻
        elif purpose == "佯攻":
            if check_result.success:
                effects["enemy_alert"] -= 1
    
    def _calculate_tactical_outcome(self, step_results: List[Dict], 
                                     global_effects: Dict) -> Dict:
        """
        计算战术整体结果
        """
        total_steps = len(step_results)
        successful_steps = sum(1 for r in step_results if r.get("success"))
        critical_steps = [r for r in step_results if r.get("is_critical")]
        failed_critical = [r for r in critical_steps if not r.get("success")]
        
        # 整体成功判断
        if failed_critical:
            overall_success = False
            overall_degree = "失败" if len(failed_critical) == 1 else "大失败"
        elif successful_steps == total_steps:
            overall_success = True
            overall_degree = "大成功"
        elif successful_steps >= total_steps * 0.7:
            overall_success = True
            overall_degree = "成功"
        elif successful_steps >= total_steps * 0.4:
            overall_success = True
            overall_degree = "勉强成功"
        else:
            overall_success = False
            overall_degree = "失败"
        
        # 生成详细叙述
        narrative = self._generate_tactical_narrative(step_results, global_effects)
        
        return {
            "is_tactical": True,
            "step_count": total_steps,
            "successful_steps": successful_steps,
            "step_results": step_results,
            "overall_success": overall_success,
            "overall_degree": overall_degree,
            "global_effects": global_effects,
            "narrative": narrative,
            "casualties": global_effects["troop_losses"],
            "morale_change": global_effects["troop_morale"]
        }
    
    def _generate_tactical_narrative(self, step_results: List[Dict], 
                                      global_effects: Dict) -> str:
        """
        生成战术执行叙述
        """
        parts = []
        
        for result in step_results:
            if result.get("status") == "跳过":
                parts.append(f"【{result['purpose']}】因前置步骤失败而取消")
                continue
            
            status_icon = "✓" if result["success"] else "✗"
            dep_info = ""
            if result.get("dependencies"):
                dep_info = f" (受益于步骤{[d+1 for d in result['dependencies']]}))"
            
            parts.append(f"【{result['purpose']}】{status_icon} {result['degree']}{dep_info}")
        
        return " | ".join(parts)
    
    # ========== 原复合行动方法（保留兼容性）==========
    
    # 复合行动关键词模式
    COMPOSITE_PATTERNS = [
        # 先...然后...
        r'先(.+?)(?:然后|接着|再|之后|随后)(.+?)(?:$|最后|最终)',
        # 一边...一边...
        r'(?:一边|一面)(.+?)(?:一边|一面)(.+?)$',
        # 用...来...
        r'用(.+?)来(.+?)(?:然后|接着|$)',
        # 先...再...
        r'先(.+?)再(.+?)$',
        # ...之后...
        r'(.+?)(?:之后|以后|随后|接着)(.+?)$',
    ]
    
    def is_composite_action(self, action_text: str) -> bool:
        """
        检测是否为复合行动（包含多个步骤）
        """
        action_clean = action_text.lower().replace(' ', '').replace('，', ',')
        
        for pattern in self.COMPOSITE_PATTERNS:
            if re.search(pattern, action_clean):
                return True
        
        # 检测明确的顺序连接词
        sequence_markers = ['先', '然后', '接着', '再', '之后', '随后', '最后', '最终', 
                           '先', '再', '又', '同时', '一边', '一面']
        marker_count = sum(1 for marker in sequence_markers if marker in action_clean)
        
        # 如果有2个及以上的顺序标记，认为是复合行动
        return marker_count >= 2
    
    def parse_composite_action(self, action_text: str) -> List[Dict]:
        """
        解析复合行动为多个步骤
        返回步骤列表，每个步骤包含行动描述、类型、属性等
        """
        action_clean = action_text.lower().replace(' ', '').replace('，', ',')
        steps = []
        
        # 尝试匹配各种复合模式
        for pattern in self.COMPOSITE_PATTERNS:
            match = re.search(pattern, action_clean)
            if match:
                groups = match.groups()
                for i, group in enumerate(groups):
                    if group and group.strip():
                        step_info = self._analyze_step(group.strip(), i)
                        steps.append(step_info)
                break
        
        # 如果没有匹配到模式，使用简单的分割
        if not steps:
            steps = self._simple_step_split(action_clean)
        
        return steps
    
    def _analyze_step(self, step_text: str, step_index: int) -> Dict:
        """
        分析单个步骤
        """
        profile = self.analyze_action(step_text)
        
        # 确定步骤类型和目的
        purpose = self._determine_step_purpose(step_text, step_index)
        
        return {
            "index": step_index,
            "text": step_text,
            "action_type": profile.action_type,
            "primary_attribute": profile.primary_attribute,
            "secondary_attribute": profile.secondary_attribute,
            "target": profile.target,
            "purpose": purpose,
            "base_dc": self._calculate_step_base_dc(profile, purpose)
        }
    
    def _determine_step_purpose(self, step_text: str, step_index: int) -> str:
        """
        确定步骤的目的（攻击、防御、干扰、逃跑等）
        """
        step_lower = step_text.lower()
        
        # 干扰/牵制
        if any(w in step_lower for w in ["干扰", "牵制", "吸引", "分散", "迷惑", "引开", "骚扰"]):
            return "干扰"
        
        # 逃跑/脱离
        if any(w in step_lower for w in ["逃", "跑", "离开", "脱离", "撤退", "撤离", "躲", "藏"]):
            return "逃跑"
        
        # 攻击
        if any(w in step_lower for w in ["打", "杀", "攻", "击", "射", "砍", "刺", "投", "扔"]):
            return "攻击"
        
        # 防御
        if any(w in step_lower for w in ["挡", "防", "格挡", "闪避", "躲", "护"]):
            return "防御"
        
        # 辅助/准备
        if any(w in step_lower for w in ["准备", "布置", "设置", "拿", "取", "掏"]):
            return "准备"
        
        # 探索/观察
        if any(w in step_lower for w in ["看", "观察", "寻找", "找", "探"]):
            return "探索"
        
        return "其他"
    
    def _calculate_step_base_dc(self, profile: ActionProfile, purpose: str) -> int:
        """
        计算步骤的基础DC
        根据步骤目的调整难度
        """
        base_dc = 10
        
        # 不同目的的基础难度
        purpose_modifiers = {
            "准备": -2,    # 准备动作相对简单
            "探索": 0,     # 探索标准难度
            "干扰": 2,     # 干扰需要技巧
            "攻击": 0,     # 攻击标准难度
            "防御": 0,     # 防御标准难度
            "逃跑": 2,     # 逃跑需要考虑时机
            "其他": 0
        }
        
        modifier = purpose_modifiers.get(purpose, 0)
        return max(5, base_dc + modifier)  # 最低DC为5
    
    def _simple_step_split(self, action_text: str) -> List[Dict]:
        """
        简单分割复合行动（当正则无法匹配时使用）
        """
        # 使用常见连接词分割
        separators = ['然后', '接着', '再', '之后', '随后', '最后', '同时']
        
        steps = []
        remaining = action_text
        
        for i, sep in enumerate(separators):
            if sep in remaining:
                parts = remaining.split(sep, 1)
                if len(parts) == 2:
                    step_info = self._analyze_step(parts[0].strip(), len(steps))
                    steps.append(step_info)
                    remaining = parts[1].strip()
        
        # 添加最后一步
        if remaining:
            step_info = self._analyze_step(remaining, len(steps))
            steps.append(step_info)
        
        return steps if steps else [self._analyze_step(action_text, 0)]
    
    def execute_composite_check(self, steps: List[Dict], target: str = None) -> Dict:
        """
        执行复合行动的分步检定
        
        策略逻辑：
        - 干扰成功 → 后续逃跑/攻击DC降低
        - 干扰失败 → 后续行动DC提高（敌人警觉）
        - 准备成功 → 后续攻击DC降低
        """
        step_results = []
        cumulative_effects = {
            "dc_modifier": 0,      # DC修正值（可累积）
            "alert_level": 0,      # 敌人警觉度
            "opportunity": False   # 是否创造机会
        }
        
        for step in steps:
            # 应用累积效果到当前步骤DC
            adjusted_dc = step["base_dc"] + cumulative_effects["dc_modifier"]
            
            # 执行检定
            profile = ActionProfile(
                raw_action=step["text"],
                action_type=step["action_type"],
                primary_attribute=step["primary_attribute"],
                secondary_attribute=step["secondary_attribute"],
                target=target,
                environment_factor=0,
                time_pressure=cumulative_effects["alert_level"]
            )
            
            check_result = self.execute_check(profile, adjusted_dc)
            
            # 记录结果
            step_result = {
                "step_index": step["index"],
                "step_text": step["text"],
                "purpose": step["purpose"],
                "check": check_result.to_dict(),
                "dc": adjusted_dc,
                "success": check_result.success,
                "degree": check_result.degree
            }
            step_results.append(step_result)
            
            # 更新累积效果
            self._update_cumulative_effects(cumulative_effects, step["purpose"], check_result)
        
        # 计算整体结果
        overall_success = all(r["success"] for r in step_results)
        overall_degree = self._calculate_composite_degree(step_results)
        
        return {
            "is_composite": True,
            "step_count": len(steps),
            "steps": step_results,
            "overall_success": overall_success,
            "overall_degree": overall_degree,
            "cumulative_effects": cumulative_effects,
            "narrative": self._generate_composite_narrative(step_results)
        }
    
    def _update_cumulative_effects(self, effects: Dict, purpose: str, check_result: CheckResult):
        """
        根据步骤结果更新累积效果
        """
        if purpose == "干扰":
            if check_result.success:
                # 干扰成功，敌人被牵制
                effects["dc_modifier"] -= 3  # 后续DC降低
                effects["opportunity"] = True
            else:
                # 干扰失败，敌人警觉
                effects["alert_level"] += 3
                effects["dc_modifier"] += 2  # 后续DC提高
        
        elif purpose == "准备":
            if check_result.success:
                # 准备充分
                effects["dc_modifier"] -= 2
            else:
                # 准备不足
                effects["dc_modifier"] += 1
        
        elif purpose == "探索":
            if check_result.success and check_result.degree in ["大成功", "成功"]:
                # 发现有利信息
                effects["dc_modifier"] -= 1
        
        elif purpose == "逃跑":
            if not check_result.success:
                # 逃跑失败会增加危险
                effects["alert_level"] += 5
    
    def _calculate_composite_degree(self, step_results: List[Dict]) -> str:
        """
        计算复合行动的整体成功程度
        """
        success_count = sum(1 for r in step_results if r["success"])
        total_count = len(step_results)
        
        # 有大失败直接整体大失败
        if any(r["degree"] == "大失败" for r in step_results):
            return "大失败"
        
        # 全成功
        if success_count == total_count:
            # 检查是否有大成功
            if any(r["degree"] == "大成功" for r in step_results):
                return "大成功"
            if all(r["degree"] == "成功" for r in step_results):
                return "成功"
            return "勉强成功"
        
        # 部分成功
        if success_count >= total_count / 2:
            return "部分成功"
        
        # 大部分失败
        if success_count == 0:
            if any(r["degree"] == "大失败" for r in step_results):
                return "大失败"
            return "失败"
        
        return "勉强失败"
    
    def _generate_composite_narrative(self, step_results: List[Dict]) -> str:
        """
        生成分步检定的叙述
        """
        narratives = []
        
        for i, result in enumerate(step_results):
            step_text = result["step_text"]
            degree = result["degree"]
            purpose = result["purpose"]
            
            # 根据目的和结果生成叙述
            if purpose == "干扰":
                if degree in ["大成功", "成功"]:
                    narratives.append(f"第{i+1}步（干扰）：你成功分散了敌人的注意力")
                elif degree == "勉强成功":
                    narratives.append(f"第{i+1}步（干扰）：干扰起效，但引起了警觉")
                else:
                    narratives.append(f"第{i+1}步（干扰）：干扰失败，敌人更加警惕")
            
            elif purpose == "逃跑":
                if degree in ["大成功", "成功"]:
                    narratives.append(f"第{i+1}步（逃跑）：你顺利逃脱")
                else:
                    narratives.append(f"第{i+1}步（逃跑）：逃跑受阻")
            
            else:
                narratives.append(f"第{i+1}步：{step_text} - {degree}")
        
        return " | ".join(narratives)
    
    def check_hard_limits(self, action_profile: ActionProfile) -> Dict:
        """
        检查是否违反硬边界
        返回是否被阻止及原因
        """
        if not self.state.world_rules:
            return {"blocked": False}
        
        rules = self.state.world_rules.impossible_rules
        action_text = action_profile.raw_action.lower()
        
        # 检查每条不可能规则
        for rule in rules:
            rule_lower = rule.lower()
            
            # 提取规则关键词
            if "无法" in rule_lower or "不能" in rule_lower:
                # 解析规则
                if self._action_violates_rule(action_profile, rule):
                    return {
                        "blocked": True,
                        "rule": rule,
                        "reason": f"违反世界规则: {rule}",
                        "suggestion": self._suggest_alternative(action_profile, rule)
                    }
        
        # 检查绝对不可能的情况
        if action_profile.target:
            npc = self.state.npcs.get(action_profile.target)
            if npc:
                npc_attrs = npc.get("attributes", {})
                player_attrs = self.state.player.get("attributes", {})
                
                # 属性差距检查 - 降低阈值到15
                for attr, npc_val in npc_attrs.items():
                    player_val = player_attrs.get(attr, 10)
                    if npc_val - player_val >= 15:
                        return {
                            "blocked": True,
                            "rule": f"{attr}差距过大",
                            "reason": f"你的{attr}({player_val})远低于{action_profile.target}({npc_val})，正面对抗不可能成功",
                            "suggestion": "考虑寻找帮手、使用计谋、或寻找其他方法"
                        }
        
        return {"blocked": False}
    
    def check_narrative_cheese(self, action_text: str) -> Dict:
        """
        检查叙事取巧（编造资源、跳过检定、声明结果）
        
        检测类型:
        1. 编造资源 - 提到不存在的NPC、帮手、物品
        2. 跳过过程 - 直接声明结果而不经过行动
        3. 获得新能力 - 凭空获得未习得的能力
        """
        action_lower = action_text.lower()
        
        # ========== 1. 编造资源检测 ==========
        fabricated_resources = self._extract_fabricated_resources(action_text)
        if fabricated_resources:
            return {
                "blocked": True,
                "type": "编造资源",
                "reason": f"世界中不存在: {', '.join(fabricated_resources)}",
                "suggestion": "这些资源需要通过游戏过程获得，不能凭空创造",
                "cheese_type": "fabricated_resources"
            }
        
        # ========== 2. 直接声明结果检测 ==========
        if self._declares_result_directly(action_text):
            return {
                "blocked": True,
                "type": "跳过检定",
                "reason": "不能直接声明结果，必须通过检定决定成败",
                "suggestion": "描述你的行动意图，而非直接声明结果",
                "cheese_type": "declared_result"
            }
        
        # ========== 3. 凭空获得能力检测 ==========
        new_abilities = self._extract_new_abilities(action_text)
        if new_abilities:
            for ability in new_abilities:
                if not self._ability_exists(ability):
                    return {
                        "blocked": True,
                        "type": "凭空获得能力",
                        "reason": f"你尚未习得: {ability}",
                        "suggestion": "新能力需要通过学习、修炼或剧情获得",
                        "cheese_type": "new_ability"
                    }
        
        return {"blocked": False}
    
    def _extract_fabricated_resources(self, action_text: str) -> List[str]:
        """
        提取行动中提到的可能编造的资源
        """
        action_lower = action_text.lower()
        fabricated = []
        
        # 检测模式：突然出现的帮手/援军
        helper_patterns = [
            r'(身后|突然|不知哪里|凭空)(出现|来了|冒出|冲出)(很多|一群|几个|一些)?(帮手|援军|朋友|同伴|高手)',
            r'(帮手|援军|朋友|同伴)(突然|不知哪里|凭空)(出现|来了|赶到)',
            r'(很多|一群|几个)帮手(一起|同时|突然)',
        ]
        
        for pattern in helper_patterns:
            if re.search(pattern, action_lower):
                # 检查是否真的有这样的NPC
                has_helper = False
                for npc_name in self.state.npcs.keys():
                    if any(kw in npc_name.lower() for kw in ['帮手', '援军', '朋友', '同伴', '师弟', '师兄', '同门']):
                        has_helper = True
                        break
                
                # 检查玩家标签
                has_helper_tag = any(tag in self.state.player.get("tags", []) 
                                    for tag in ["有援军", "有帮手", "有同伴"])
                
                if not has_helper and not has_helper_tag:
                    fabricated.append("帮手/援军")
                break
        
        # 检测模式：突然拥有的物品
        item_patterns = [
            r'(拿出|掏出|取出|使用)(一把|一个|一瓶|一柄|一张)?(神秘|突然|不知何时)(的)?(武器|丹药|符咒|秘籍)',
            r'发现(自己|身上)有(一把|一个|一瓶)?(从未见过|不知道|神秘)',
        ]
        
        for pattern in item_patterns:
            if re.search(pattern, action_lower):
                # 提取可能的物品名
                fabricated.append("未记录的物品")
                break
        
        return fabricated
    
    def _declares_result_directly(self, action_text: str) -> bool:
        """
        检测是否直接声明了结果
        """
        action_lower = action_text.lower()
        
        # 结果声明模式
        result_patterns = [
            r'(把|将|让|使).*(打跑|击败|杀死|干掉|制服|搞定|解决).*(了|掉)',
            r'(成功|顺利|轻松|毫不费力).*(击败|战胜|解决|完成|达成)',
            r'(一剑|一招|一下就).*(秒杀|击败|杀死|解决)',
            r'(敌人|对手|对方|目标).*(倒下|死亡|失败|被击败)',
            r'(然后|接着|最后).*(就).*(成功|完成|解决|达成)',
        ]
        
        for pattern in result_patterns:
            if re.search(pattern, action_lower):
                return True
        
        # 检测"就"字连接的结果声明
        # 如"帮手一来，就把山贼打跑了"
        if re.search(r'就.*(把|将|让).*(打|杀|击败|解决|搞定)', action_lower):
            return True
        
        return False
    
    def _extract_new_abilities(self, action_text: str) -> List[str]:
        """
        提取提到的可能的新能力
        """
        action_lower = action_text.lower()
        abilities = []
        
        # 能力获得模式
        ability_patterns = [
            r'(突然|瞬间|忽然)(领悟|觉醒|掌握|学会|获得)(了)?(绝世|强大|神秘|失传|终极)?(剑法|武功|能力|力量|秘籍|法术)',
            r'(其实|原来)(我|自己)(是|身为|乃)?(隐世|绝世|隐藏|秘密)(高手|传人|弟子|血脉)',
            r'(觉醒|激发|释放)(了)?(体内|隐藏|沉睡|潜在)(的)?(力量|能力|血脉|潜能)',
            r'(发现|察觉)(了)?(对方|敌人|目标)(的)?(致命|关键|重要)(弱点|破绽|缺陷)',
        ]
        
        for pattern in ability_patterns:
            match = re.search(pattern, action_lower)
            if match:
                # 提取能力描述
                abilities.append(match.group(0))
        
        return abilities
    
    def _ability_exists(self, ability_desc: str) -> bool:
        """
        检查能力是否已存在
        """
        # 检查玩家标签
        player_tags = self.state.player.get("tags", [])
        
        # 检查是否已学习的能力
        if "绝世剑法" in ability_desc and "绝世剑法" not in player_tags:
            return False
        if "隐世传人" in ability_desc and "隐世传人" not in player_tags:
            return False
        if "血脉觉醒" in ability_desc and "血脉觉醒" not in player_tags:
            return False
        
        # 检查是否通过游戏过程获得
        known_secrets = self.state.player.get("secrets", [])
        if "弱点" in ability_desc:
            # 弱点需要通过侦查发现
            has_discovered = any("弱点" in s for s in known_secrets)
            return has_discovered
        
        return True
    
    def _action_violates_rule(self, profile: ActionProfile, rule: str) -> bool:
        """检查行动是否违反规则"""
        # 简化实现 - 检查关键词匹配
        action = profile.raw_action.lower()
        
        # 示例："凡人无法飞行"
        if "飞" in rule and "飞" in action:
            if "凡人" in rule and "飞行" not in self.state.player.get("tags", []):
                return True
        
        # 示例："没有钥匙无法开锁"
        if "开锁" in action and "开锁" in rule:
            if "开锁工具" not in self.state.player.get("items", []):
                return True
        
        return False
    
    def _suggest_alternative(self, profile: ActionProfile, rule: str) -> str:
        """提供替代建议"""
        if "飞" in rule:
            return "寻找楼梯、绳索，或其他移动方式"
        if "开锁" in rule:
            return "寻找钥匙、破门、或寻找其他入口"
        if "击败" in rule or "差距" in rule:
            return "寻找帮手、使用计谋、或寻找其他方法"
        return "考虑其他方案"
    
    def calculate_difficulty(self, action_profile: ActionProfile) -> Dict:
        """
        计算难度 - 基于相对能力
        """
        # 基础难度
        base_dc = 10
        
        modifiers = []
        
        # 1. 目标难度修正
        if action_profile.target:
            target_npc = self.state.npcs.get(action_profile.target)
            if target_npc:
                target_attr = target_npc.get("attributes", {})
                player_attr = self.state.player.get("attributes", {})
                
                # 计算属性差距
                gap = 0
                for attr, val in target_attr.items():
                    player_val = player_attr.get(attr, 10)
                    gap += (val - player_val)
                
                if gap > 20:
                    modifiers.append(("目标过强", gap // 5))
                elif gap < -10:
                    modifiers.append(("目标较弱", gap // 10))
        
        # 2. 环境因素
        if action_profile.environment_factor != 0:
            env_mod = -action_profile.environment_factor  # 有利环境降低难度
            modifiers.append(("环境", env_mod))
        
        # 3. 时间压力
        if action_profile.time_pressure > 5:
            modifiers.append(("时间紧迫", action_profile.time_pressure // 2))
        
        # 4. 物品检查
        missing_items = []
        for item in action_profile.required_items:
            if item not in self.state.player.get("items", []):
                missing_items.append(item)
                modifiers.append((f"缺少{item}", 5))
        
        # 5. 自适应难度修正
        if self.state.difficulty_bias != 0:
            modifiers.append(("难度调整", self.state.difficulty_bias))
        
        # 计算总难度
        total_dc = base_dc + sum(m for _, m in modifiers)
        
        # 确定难度等级
        level = self._dc_to_level(total_dc)
        
        # 估算成功率
        player_attr = self.state.get_attribute_value(action_profile.primary_attribute)
        estimated_rate = self._estimate_success_rate(total_dc, player_attr)
        
        return {
            "base_dc": base_dc,
            "total_dc": total_dc,
            "modifiers": modifiers,
            "level": level,
            "missing_items": missing_items,
            "estimated_rate": estimated_rate,
            "risks": self._identify_risks(total_dc, action_profile)
        }
    
    def _dc_to_level(self, dc: int) -> str:
        """难度数值转等级"""
        if dc <= 5: return "简单"
        if dc <= 10: return "普通"
        if dc <= 15: return "困难"
        if dc <= 20: return "极难"
        return "不可能"
    
    def _estimate_success_rate(self, dc: int, attr: int) -> float:
        """估算成功率"""
        # d20 + (attr-10)/2 >= dc
        # 期望roll = 10.5
        modifier = (attr - 10) // 2
        needed_roll = dc - modifier
        
        if needed_roll <= 1:
            return 1.0
        if needed_roll >= 20:
            return 0.05  # 只有掷出20可能成功
        
        success_count = 21 - needed_roll  # 包括needed_roll到20
        return success_count / 20.0
    
    def _identify_risks(self, dc: int, profile: ActionProfile) -> List[str]:
        """识别风险"""
        risks = []
        
        if dc > 20:
            risks.append("可能遭受严重失败")
        elif dc > 15:
            risks.append("失败可能导致受伤或损失")
        
        if profile.action_type == "战斗":
            risks.append("可能受伤")
        
        if profile.time_pressure > 7:
            risks.append("时间耗尽将导致机会丧失")
        
        return risks
    
    def execute_check(self, action_profile: ActionProfile, 
                      difficulty_override: int = None) -> CheckResult:
        """
        执行检定 - 掷骰决定结果
        """
        # 获取难度
        if difficulty_override:
            dc = difficulty_override
        else:
            diff_calc = self.calculate_difficulty(action_profile)
            dc = diff_calc["total_dc"]
        
        # 获取属性值
        attr_value = self.state.get_attribute_value(action_profile.primary_attribute)
        
        # 掷骰 (d20)
        roll = random.randint(1, 20)
        
        # 计算修正值 (D&D风格: 每2点属性±1)
        modifier = (attr_value - 10) // 2
        
        # 总和
        total = roll + modifier
        
        # 判定成功
        success = total >= dc
        
        # 计算差值
        margin = total - dc
        
        # 确定程度
        degree = self._interpret_margin(margin, success, roll)
        
        # 创建结果
        result = CheckResult(
            success=success,
            roll=roll,
            modifier=modifier,
            total=total,
            difficulty=dc,
            margin=margin,
            degree=degree,
            attribute=action_profile.primary_attribute.value
        )
        
        self.last_check_result = result
        return result
    
    def _interpret_margin(self, margin: int, success: bool, roll: int) -> str:
        """解释差值"""
        # 自然20大成功
        if roll == 20:
            return "大成功"
        # 自然1大失败
        if roll == 1:
            return "大失败"
        
        if success:
            if margin >= 10:
                return "大成功"
            if margin >= 5:
                return "成功"
            return "勉强成功"
        else:
            if margin <= -10:
                return "大失败"
            if margin <= -5:
                return "失败"
            return "勉强失败"
    
    def process_resource_cost(self, action_profile: ActionProfile, 
                             check_result: CheckResult) -> Dict[str, int]:
        """
        计算资源消耗
        """
        costs = {}
        
        # 体力消耗
        stamina_cost = 5
        if action_profile.action_type == "战斗":
            stamina_cost = 10
            if not check_result.success:
                stamina_cost += 5
        elif action_profile.action_type == "潜行":
            stamina_cost = 8
        
        costs["stamina"] = -stamina_cost
        
        # 失败时的额外损失
        if not check_result.success:
            if action_profile.action_type == "战斗":
                damage = random.randint(5, 15)
                if check_result.degree == "大失败":
                    damage *= 2
                costs["health"] = -damage
        
        # 应用消耗
        for resource, change in costs.items():
            current = self.state.player["resources"].get(resource, 0)
            self.state.player["resources"][resource] = max(0, current + change)
        
        return costs
    
    def evaluate_action(self, action_text: str, context: Dict = None) -> Dict:
        """
        完整评估流程
        支持复合行动（分步检定）和战术多步骤行动
        """
        # 1. 检查是否为战术多步骤行动（优先）
        if self.is_tactical_multi_step(action_text):
            return self._evaluate_tactical_action(action_text, context)
        
        # 2. 检查是否为复合行动
        if self.is_composite_action(action_text):
            return self._evaluate_composite_action(action_text, context)
        
        # 3. 解析行动
        profile = self.analyze_action(action_text, context)
        
        # 4. 检查叙事取巧（编造资源、跳过检定）
        cheese_check = self.check_narrative_cheese(action_text)
        if cheese_check["blocked"]:
            return {
                "feasible": False,
                "blocked": True,
                "reason": cheese_check["reason"],
                "type": cheese_check.get("type"),
                "cheese_type": cheese_check.get("cheese_type"),
                "suggestion": cheese_check.get("suggestion"),
                "action_profile": profile.to_dict()
            }
        
        # 5. 检查硬边界
        hard_limit = self.check_hard_limits(profile)
        if hard_limit["blocked"]:
            return {
                "feasible": False,
                "blocked": True,
                "reason": hard_limit["reason"],
                "rule": hard_limit.get("rule"),
                "suggestion": hard_limit.get("suggestion"),
                "action_profile": profile.to_dict()
            }
        
        # 6. 计算难度
        difficulty = self.calculate_difficulty(profile)
        
        # 7. 执行检定
        check_result = self.execute_check(profile)
        
        # 8. 计算资源消耗
        resource_costs = self.process_resource_cost(profile, check_result)
        
        # 9. 生成结果
        return {
            "feasible": True,
            "action_profile": profile.to_dict(),
            "difficulty": difficulty,
            "check_result": check_result.to_dict(),
            "resource_costs": resource_costs,
            "success": check_result.success,
            "degree": check_result.degree,
            "narrative_template": self._get_narrative_template(check_result, profile),
            "is_composite": False,
            "is_tactical": False
        }
    
    def _evaluate_tactical_action(self, action_text: str, context: Dict = None) -> Dict:
        """
        评估战术多步骤行动
        """
        # 1. 检查叙事取巧
        cheese_check = self.check_narrative_cheese(action_text)
        if cheese_check["blocked"]:
            return {
                "feasible": False,
                "blocked": True,
                "reason": cheese_check["reason"],
                "type": cheese_check.get("type"),
                "cheese_type": cheese_check.get("cheese_type"),
                "suggestion": cheese_check.get("suggestion")
            }
        
        # 2. 解析战术步骤
        steps = self.parse_tactical_steps(action_text)
        
        if not steps:
            # 解析失败，回退到单一行动
            profile = self.analyze_action(action_text, context)
            check_result = self.execute_check(profile)
            return {
                "feasible": True,
                "is_tactical": False,
                "check_result": check_result.to_dict(),
                "success": check_result.success,
                "degree": check_result.degree
            }
        
        # 3. 执行战术多步骤检定
        tactical_result = self.execute_tactical_check(steps)
        
        # 4. 计算资源消耗
        resource_costs = {"stamina": -5 * len(steps)}  # 每步5点体力
        for resource, change in resource_costs.items():
            current = self.state.player["resources"].get(resource, 0)
            self.state.player["resources"][resource] = max(0, current + change)
        
        # 5. 组装结果
        return {
            "feasible": True,
            "is_tactical": True,
            "tactical_result": tactical_result,
            "step_count": tactical_result["step_count"],
            "step_results": tactical_result["step_results"],
            "overall_success": tactical_result["overall_success"],
            "overall_degree": tactical_result["overall_degree"],
            "check_result": {
                "success": tactical_result["overall_success"],
                "degree": tactical_result["overall_degree"],
                "roll": tactical_result["step_results"][0]["check"]["roll"] if tactical_result["step_results"] else 10,
                "modifier": 0,
                "total": tactical_result["step_results"][0]["check"]["total"] if tactical_result["step_results"] else 10,
                "difficulty": tactical_result["step_results"][0]["dc"] if tactical_result["step_results"] else 10,
                "margin": 0,
                "attribute": "TACTICAL"
            },
            "resource_costs": resource_costs,
            "narrative": tactical_result["narrative"],
            "casualties": tactical_result.get("casualties", 0),
            "morale_change": tactical_result.get("morale_change", 0)
        }
    
    def _evaluate_composite_action(self, action_text: str, context: Dict = None) -> Dict:
        """
        评估复合行动（分步检定）
        """
        # 1. 检查叙事取巧
        cheese_check = self.check_narrative_cheese(action_text)
        if cheese_check["blocked"]:
            return {
                "feasible": False,
                "blocked": True,
                "reason": cheese_check["reason"],
                "type": cheese_check.get("type"),
                "cheese_type": cheese_check.get("cheese_type"),
                "suggestion": cheese_check.get("suggestion")
            }
        
        # 2. 解析复合行动为多个步骤
        steps = self.parse_composite_action(action_text)
        
        # 3. 识别目标（用于所有步骤）
        profile = self.analyze_action(action_text, context)
        target = profile.target
        
        # 4. 执行分步检定
        composite_result = self.execute_composite_check(steps, target)
        
        # 5. 计算资源消耗（复合行动消耗更多）
        resource_costs = self._calculate_composite_resource_cost(composite_result)
        
        # 6. 组装结果
        return {
            "feasible": True,
            "is_composite": True,
            "composite_result": composite_result,
            "step_count": composite_result["step_count"],
            "steps": composite_result["steps"],
            "overall_success": composite_result["overall_success"],
            "overall_degree": composite_result["overall_degree"],
            "check_result": {
                "success": composite_result["overall_success"],
                "degree": composite_result["overall_degree"],
                # 使用第一步的掷骰作为代表
                "roll": composite_result["steps"][0]["check"]["roll"] if composite_result["steps"] else 10,
                "modifier": 0,
                "total": composite_result["steps"][0]["check"]["total"] if composite_result["steps"] else 10,
                "difficulty": composite_result["steps"][0]["dc"] if composite_result["steps"] else 10,
                "margin": 0,
                "attribute": "COMPOSITE"
            },
            "resource_costs": resource_costs,
            "narrative": composite_result["narrative"],
            "action_profile": profile.to_dict()
        }
    
    def _calculate_composite_resource_cost(self, composite_result: Dict) -> Dict[str, int]:
        """
        计算复合行动的资源消耗
        复合行动消耗更多资源
        """
        step_count = composite_result["step_count"]
        base_stamina_cost = 5 * step_count  # 每步5点体力
        
        # 根据结果调整
        if composite_result["overall_degree"] == "大失败":
            base_stamina_cost += 10
        elif not composite_result["overall_success"]:
            base_stamina_cost += 5
        
        costs = {"stamina": -base_stamina_cost}
        
        # 应用消耗
        for resource, change in costs.items():
            current = self.state.player["resources"].get(resource, 0)
            self.state.player["resources"][resource] = max(0, current + change)
        
        return costs
    
    def _get_narrative_template(self, result: CheckResult, 
                                profile: ActionProfile) -> str:
        """获取叙述模板"""
        templates = {
            ("战斗", "大成功"): "你以压倒性优势击败对手，毫发无伤",
            ("战斗", "成功"): "你成功击中对手，造成有效伤害",
            ("战斗", "勉强成功"): "你勉强击中对手，但自己也受了点伤",
            ("战斗", "失败"): "你的攻击被对手躲开，反而受了伤",
            ("战斗", "大失败"): "你的攻击完全落空，遭受重创",
            
            ("说服", "大成功"): "对方完全被你说服，甚至对你产生好感",
            ("说服", "成功"): "对方接受你的观点，态度软化",
            ("说服", "勉强成功"): "对方半信半疑，但暂时接受",
            ("说服", "失败"): "对方不为所动，甚至对你产生怀疑",
            ("说服", "大失败"): "对方识破你的意图，关系恶化",
            
            ("潜行", "大成功"): "你完美隐匿，没有人发现你的存在",
            ("潜行", "成功"): "你成功避开注意，没有引起怀疑",
            ("潜行", "勉强成功"): "你勉强躲过注意，但心跳加速",
            ("潜行", "失败"): "你发出声响，被人察觉",
            ("潜行", "大失败"): "你完全暴露，陷入危险",
        }
        
        key = (profile.action_type, result.degree)
        return templates.get(key, f"行动{result.degree}")
    
    def npc_take_action(self) -> Optional[Dict]:
        """
        NPC主动性 - 敌对NPC可能采取行动
        """
        hostile_npcs = [
            (name, info) for name, info in self.state.npcs.items()
            if info.get("relationship", 0) < -30
        ]
        
        if not hostile_npcs:
            return None
        
        # 随机选择一个敌对NPC行动
        npc_name, npc_info = random.choice(hostile_npcs)
        
        # 30%概率行动
        if random.random() > 0.3:
            return None
        
        # 生成NPC行动
        action_types = ["攻击", "追击", "设伏", "警告"]
        action = random.choice(action_types)
        
        return {
            "npc": npc_name,
            "action": action,
            "relationship": npc_info.get("relationship", 0),
            "description": f"{npc_name}对你采取了{action}行动"
        }
    
    def learn_from_outcome(self, action_text: str, result: Dict, 
                          player_feedback: str = None):
        """
        从结果学习，调整难度
        """
        check = result.get("check_result", {})
        
        # 记录边缘案例
        if check.get("success") and result.get("difficulty", {}).get("total_dc", 0) > 20:
            self.state.edge_cases.append({
                "turn": self.state.turn_count,
                "action": action_text,
                "difficulty": result["difficulty"]["total_dc"],
                "roll": check.get("roll"),
                "note": "侥幸成功"
            })
        
        # 根据反馈调整
        if player_feedback:
            if "简单" in player_feedback or "太简单" in player_feedback:
                self.state.difficulty_bias += 1
            elif "难" in player_feedback or "太难" in player_feedback:
                self.state.difficulty_bias -= 1


# ============ 游戏引擎主类 ============
class WorldlineEngine:
    """
    世界线抉择游戏引擎 v3.0
    通用挑战框架版
    """
    
    def __init__(self, model: str = "default"):
        self.state = GameState()
        self.model = model
        self.challenge_engine: Optional[UniversalChallengeEngine] = None
        self.save_dir = os.path.expanduser("~/.claude/skills/worldline_choice/saves")
        os.makedirs(self.save_dir, exist_ok=True)
    
    def initialize_world(self, world_setting: str, player_role: str = "", 
                         player_name: str = "", world_desc: str = ""):
        """初始化游戏世界"""
        self.state.world_setting = world_setting
        self.state.world_description = world_desc
        self.state.player["name"] = player_name or "主角"
        self.state.player["role"] = player_role or "参与者"
        self.state.turn_count = 0
        
        # 初始化世界规则（默认）
        self.state.world_rules = WorldRules.generate_default(world_setting)
        
        # 生成初始属性
        self._generate_initial_attributes()
        
        # 初始化资源
        self.state.initialize_resources()
        
        # 初始化挑战引擎
        self.challenge_engine = UniversalChallengeEngine(self.state)
    
    def _generate_initial_attributes(self):
        """生成初始属性 - 使用通用维度"""
        if not self.state.world_rules:
            return
        
        # 为每个维度生成属性值（10-18）
        for dim in AttributeDimension:
            attr_name = self.state.world_rules.attributes[dim]
            self.state.player["attributes"][attr_name] = random.randint(10, 18)
    
    def set_world_rules(self, rules: WorldRules):
        """设置世界规则（可由AI生成）"""
        self.state.world_rules = rules
        # 重新映射属性名称
        self._remap_attributes()
    
    def _remap_attributes(self):
        """重新映射属性到新规则"""
        if not self.state.world_rules:
            return
        
        old_attrs = self.state.player["attributes"].copy()
        new_attrs = {}
        
        for dim in AttributeDimension:
            new_name = self.state.world_rules.attributes[dim]
            # 尝试匹配旧属性
            matched = False
            for old_name, value in old_attrs.items():
                if self._attributes_similar(old_name, new_name):
                    new_attrs[new_name] = value
                    matched = True
                    break
            if not matched:
                new_attrs[new_name] = random.randint(10, 18)
        
        self.state.player["attributes"] = new_attrs
    
    def _attributes_similar(self, name1: str, name2: str) -> bool:
        """判断两个属性名是否相似"""
        # 简单的相似度检查
        synonyms = {
            "武力": ["力量", "武力", "战斗力", "攻击"],
            "智力": ["智力", "智慧", "谋略", "学识", "知识"],
            "魅力": ["魅力", "魅力", "说服", "话术", "社交"],
            "敏捷": ["敏捷", "身法", "反应", "速度"],
            "体质": ["体质", "耐力", "生命", "防御"],
            "运气": ["运气", "幸运", "机缘", "气运"]
        }
        
        for group in synonyms.values():
            if name1 in group and name2 in group:
                return True
        return False
    
    def process_player_action(self, action_text: str, context: Dict = None) -> Dict:
        """
        处理玩家行动 - 核心方法
        """
        if not self.challenge_engine:
            return {"error": "游戏未初始化"}
        
        # 执行挑战评估
        evaluation = self.challenge_engine.evaluate_action(action_text, context)
        
        # 如果被硬边界阻止
        if evaluation.get("blocked"):
            return {
                "success": False,
                "blocked": True,
                "reason": evaluation["reason"],
                "suggestion": evaluation.get("suggestion"),
                "can_retry": True,
                "turn": self.state.turn_count
            }
        
        # 获取检定结果
        check_result = evaluation.get("check_result", {})
        success = check_result.get("success", False)
        degree = check_result.get("degree", "失败")
        
        # 记录历史
        narrative = evaluation.get("narrative_template", "")
        consequences = {
            "resource_changes": evaluation.get("resource_costs", {}),
            "success": success,
            "degree": degree
        }
        
        # 创建检定结果对象用于存储
        check_obj = None
        if check_result:
            check_obj = CheckResult(
                success=check_result.get("success", False),
                roll=check_result.get("roll", 1),
                modifier=check_result.get("modifier", 0),
                total=check_result.get("total", 1),
                difficulty=check_result.get("difficulty", 10),
                margin=check_result.get("margin", -9),
                degree=degree,
                attribute=check_result.get("attribute", "MIND")
            )
        
        self.state.add_history(action_text, narrative, consequences, check_obj)
        
        # 检查NPC主动性
        npc_action = self.challenge_engine.npc_take_action()
        
        return {
            "success": success,
            "degree": degree,
            "evaluation": evaluation,
            "narrative": evaluation.get("narrative") or narrative,
            "resources": self.state.player["resources"].copy(),
            "npc_action": npc_action,
            "turn": self.state.turn_count,
            "can_retry": not success and degree != "大失败",
            "is_composite": evaluation.get("is_composite", False),
            "composite_result": evaluation.get("composite_result") if evaluation.get("is_composite") else None,
            "is_tactical": evaluation.get("is_tactical", False),
            "tactical_result": evaluation.get("tactical_result") if evaluation.get("is_tactical") else None
        }
    
    def get_system_prompt(self) -> str:
        """生成系统Prompt"""
        history_text = self.state.get_history_for_ai()
        
        npcs_text = "\n".join([
            f"- {name}: 关系{info.get('relationship', 0)}"
            for name, info in self.state.npcs.items()
        ]) if self.state.npcs else "暂无重要NPC"
        
        resources_text = json.dumps(self.state.player.get("resources", {}), ensure_ascii=False)
        
        # 世界规则信息
        rules_text = ""
        if self.state.world_rules:
            attrs_text = ", ".join([
                f"{k.value}->{v}" for k, v in self.state.world_rules.attributes.items()
            ])
            impossible_text = "\n".join([
                f"- {r}" for r in self.state.world_rules.impossible_rules
            ])
            rules_text = f"""
【世界规则】
属性映射: {attrs_text}
不可能规则:
{impossible_text}
"""
        
        return f"""你是《世界线·抉择》的叙事AI。这是一个基于"{self.state.world_setting}"世界观的互动叙事游戏。

{rules_text}

【当前游戏状态】
- 回合数: {self.state.turn_count}
- 玩家角色: {self.state.player['name']} ({self.state.player['role']})
- 玩家属性: {json.dumps(self.state.player['attributes'], ensure_ascii=False)}
- 玩家资源: {resources_text}
- 持有物品: {', '.join(self.state.player['items']) or '无'}
- 性格标签: {', '.join(self.state.player['tags']) or '暂无'}
- 道德腐化值: {self.state.moral_corruption}/100

【重要NPC】
{npcs_text}

【历史记录】
{history_text}

【核心机制：强制检定系统】
本游戏使用严格的d20检定系统：
1. 每个行动都有难度等级(DC)：简单(5)/普通(10)/困难(15)/极难(20)/不可能(25+)
2. 检定公式：d20 + 属性修正 >= DC
3. 修正值：(属性值-10)/2，向下取整
4. 结果等级：大成功(超10+)/成功(超5+)/勉强成功/勉强失败/失败/大失败(差10+)
5. 自然20必成功，自然1必失败

【你必须遵守的铁律】
❌ 绝对禁止：
- 让检定失败的行动"意外成功"
- 为玩家编造不存在的物品或能力
- 让玩家轻松完成明显超出能力的事
- 因为"剧情需要"而降低难度

✅ 必须执行：
- 严格按检定结果决定剧情走向
- 失败必须有真实后果（受伤、损失、关系恶化）
- 超出能力的尝试明确拒绝并提供替代方案
- 资源耗尽时限制行动（体力归零无法战斗）

【生成要求】
1. 生成场景描述（100-150字）
2. 识别核心冲突
3. 提供4个选项（A/B/C/D）
4. 对每个选项评估难度DC（让玩家知道有多难）
5. 等待玩家选择

【输出格式】
{{
  "scene_title": "场景标题",
  "scene_description": "场景描述",
  "conflict": "核心冲突",
  "options": {{
    "A": {{"text": "选项文本", "dc": 10, "attribute": "FORCE", "hint": "需要高武力"}},
    "B": {{"text": "选项文本", "dc": 15, "attribute": "MIND", "hint": "困难但可行"}},
    "C": {{"text": "选项文本", "dc": 12, "attribute": "INFLUENCE", "hint": "中等难度"}},
    "D": {{"text": "选项文本", "dc": 20, "attribute": "LUCK", "hint": "高风险高回报，失败后果严重"}}
  }}
}}
"""
    
    def get_action_prompt(self, player_input: str, evaluation: Dict = None) -> str:
        """生成处理玩家行动的Prompt"""
        
        check_info = ""
        if evaluation and evaluation.get("check_result"):
            cr = evaluation["check_result"]
            check_info = f"""
【强制检定结果】
- 检定属性: {cr.get('attribute')}
- 难度DC: {cr.get('difficulty')}
- 掷骰: d20={cr.get('roll')} + 修正{cr.get('modifier')} = {cr.get('total')}
- 结果: {cr.get('degree')} (差值: {cr.get('margin'):+d})
- {'成功' if cr.get('success') else '失败'}
"""
        
        return f"""玩家在当前场景中做出行动。

【当前场景】
{self.state.current_scene}

【玩家行动】
{player_input}

{check_info}

【处理要求】
1. 基于检定结果生成剧情叙述（150-250字）
2. 严格按照成功/失败/程度生成结果：
   - 大成功：超额完成，有额外收益
   - 成功：顺利完成
   - 勉强成功：完成但有代价
   - 勉强失败：失败但有机会补救
   - 失败：明确失败，承担后果
   - 大失败：灾难性后果

3. 更新状态（属性、资源、关系、物品）
4. 检查是否触发结局
5. 如果失败，提供替代建议

【输出格式】
{{
  "narrative": "剧情描述",
  "consequences": {{
    "attribute_changes": {{}},
    "resource_changes": {{}},
    "relationship_changes": {{}},
    "items_gained": [],
    "items_lost": [],
    "tags_added": [],
    "secrets_learned": []
  }},
  "flags_set": {{}},
  "ending_triggered": false,
  "alternative_suggestions": ["如果失败，建议这样做"]
}}
"""
    
    def start_game(self, world_setting: str, player_role: str = "", 
                   player_name: str = "", world_desc: str = "") -> Dict:
        """开始新游戏"""
        self.initialize_world(world_setting, player_role, player_name, world_desc)
        
        return {
            "initialized": True,
            "version": GameState.VERSION,
            "world": world_setting,
            "player": self.state.player,
            "world_rules": self.state.world_rules.to_dict() if self.state.world_rules else None,
            "system_prompt": self.get_system_prompt()
        }
    
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
            self.challenge_engine = UniversalChallengeEngine(self.state)
        return True
    
    def get_current_state(self) -> Dict:
        """获取当前状态"""
        return {
            "turn": self.state.turn_count,
            "player": self.state.player,
            "npcs": self.state.npcs,
            "flags": self.state.flags,
            "resources": self.state.player.get("resources", {}),
            "milestones": self.state.milestones
        }


# ============ 命令行接口 ============
class GameCLI:
    """命令行界面"""
    
    def __init__(self):
        self.engine = WorldlineEngine()
    
    def run(self, args: List[str]):
        """运行命令"""
        if len(args) < 1:
            self.show_help()
            return
        
        command = args[0]
        
        if command in ("--new", "-n"):
            self.cmd_new(args[1:])
        elif command in ("--load", "-l"):
            self.cmd_load(args[1:])
        elif command in ("--list", "-ls"):
            self.cmd_list()
        elif command in ("--test", "-t"):
            self.cmd_test()
        else:
            self.cmd_new(args)
    
    def cmd_new(self, args: List[str]):
        """开始新游戏"""
        world = args[0] if len(args) > 0 else input("世界观: ")
        role = args[1] if len(args) > 1 else input("角色: ")
        name = args[2] if len(args) > 2 else input("名字: ")
        
        result = self.engine.start_game(world, role, name)
        print(f"\n{'='*50}")
        print(f"游戏开始: {world}")
        print(f"{'='*50}")
        print(f"角色: {name} ({role})")
        print(f"属性: {json.dumps(result['player']['attributes'], ensure_ascii=False)}")
        print(f"\n使用: get_system_prompt() 获取AI Prompt")
    
    def cmd_load(self, args: List[str]):
        """加载游戏"""
        if len(args) < 1:
            print("错误: 请指定存档ID")
            return
        save_id = args[0]
        if self.engine.load_game(save_id):
            print(f"✅ 已加载: {save_id}")
            print(f"回合: {self.engine.state.turn_count}")
        else:
            print(f"❌ 存档不存在: {save_id}")
    
    def cmd_list(self):
        """列出存档"""
        saves = self.engine.list_saves()
        if not saves:
            print("暂无存档")
            return
        for save in saves:
            print(f"{save['id']}: {save['world']} - {save['turn']}回合")
    
    def cmd_test(self):
        """运行测试"""
        print("运行通用挑战框架测试...")
        test_challenge_framework()
    
    def show_help(self):
        """显示帮助"""
        print("""
Worldline Choice v3.0 - 通用挑战框架

用法:
  worldline_choice --new [世界观] [角色] [名字]
  worldline_choice --load <存档ID>
  worldline_choice --list
  worldline_choice --test
        """)


# ============ 测试函数 ============
def test_challenge_framework():
    """测试通用挑战框架"""
    print("="*60)
    print("通用挑战框架测试")
    print("="*60)
    
    # 创建引擎
    engine = WorldlineEngine()
    engine.initialize_world("武侠江湖", "剑客", "李逍遥")
    
    print(f"\n1. 世界观: {engine.state.world_setting}")
    print(f"2. 角色: {engine.state.player['name']} ({engine.state.player['role']})")
    print(f"3. 属性: {json.dumps(engine.state.player['attributes'], ensure_ascii=False)}")
    print(f"4. 资源: {json.dumps(engine.state.player['resources'], ensure_ascii=False)}")
    
    # 测试行动解析
    print("\n5. 行动解析测试:")
    test_actions = [
        "我要和山贼战斗",
        "尝试说服村长",
        "偷偷潜入城堡",
        "解开这个机关"
    ]
    
    for action in test_actions:
        profile = engine.challenge_engine.analyze_action(action)
        print(f"   '{action}' -> {profile.action_type} ({profile.primary_attribute.value})")
    
    # 测试难度计算
    print("\n6. 难度计算测试:")
    engine.state.npcs["山贼头目"] = {
        "relationship": -50,
        "attributes": {"武力": 20, "体质": 18}
    }
    
    profile = engine.challenge_engine.analyze_action("和山贼头目战斗")
    profile.target = "山贼头目"
    
    difficulty = engine.challenge_engine.calculate_difficulty(profile)
    print(f"   行动: {profile.raw_action}")
    print(f"   基础DC: {difficulty['base_dc']}")
    print(f"   总DC: {difficulty['total_dc']}")
    print(f"   难度: {difficulty['level']}")
    print(f"   估算成功率: {difficulty['estimated_rate']*100:.1f}%")
    
    # 测试检定执行
    print("\n7. 检定执行测试 (10次):")
    for i in range(10):
        result = engine.challenge_engine.execute_check(profile)
        status = "✓" if result.success else "✗"
        print(f"   第{i+1}次: d20={result.roll:2d} + {result.modifier:+d} = {result.total:2d} vs DC={result.difficulty} -> {status} {result.degree}")
    
    # 测试完整评估
    print("\n8. 完整评估测试:")
    evaluation = engine.challenge_engine.evaluate_action("和山贼头目战斗")
    print(f"   可行性: {evaluation['feasible']}")
    print(f"   结果: {evaluation['degree']}")
    print(f"   资源消耗: {evaluation['resource_costs']}")
    
    # 测试硬边界
    print("\n9. 硬边界测试:")
    engine.state.world_rules.impossible_rules.append("没有轻功无法飞檐走壁")
    
    eval_impossible = engine.challenge_engine.evaluate_action("飞上屋顶")
    if eval_impossible.get("blocked"):
        print(f"   ✓ 正确阻止: {eval_impossible['reason']}")
    else:
        print(f"   ✗ 未能阻止不可能的行动")
    
    # 测试NPC主动性
    print("\n10. NPC主动性测试:")
    engine.state.npcs["仇人"] = {"relationship": -60}
    for i in range(5):
        npc_action = engine.challenge_engine.npc_take_action()
        if npc_action:
            print(f"   NPC行动: {npc_action['description']}")
        else:
            print(f"   NPC未行动")
    
    print("\n" + "="*60)
    print("测试完成!")
    print("="*60)


def main():
    """主入口"""
    cli = GameCLI()
    cli.run(sys.argv[1:])


if __name__ == "__main__":
    main()
