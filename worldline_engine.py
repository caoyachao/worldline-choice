#!/usr/bin/env python3
"""
Worldline Choice - AI驱动互动叙事游戏引擎
完全开放式，不预设固定剧情，所有内容由AI实时生成
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Any
import random

# 游戏状态管理
class GameState:
    """管理游戏的所有状态数据"""
    
    def __init__(self):
        self.world_setting = ""  # 世界观设定
        self.world_description = ""  # 世界观详细描述
        self.current_scene = ""  # 当前场景描述
        self.scene_context = ""  # 场景上下文
        self.turn_count = 0  # 回合数
        
        # 玩家状态
        self.player = {
            "name": "",
            "role": "",  # 角色身份
            "backstory": "",  # 背景故事
            "attributes": {},  # 属性
            "items": [],  # 持有物品
            "tags": [],  # 性格/状态标签
            "secrets": []  # 玩家知道的秘密
        }
        
        # NPC状态
        self.npcs = {}  # {名字: {relationship, attitude, secrets, status}}
        
        # 游戏标记
        self.flags = {}  # 关键事件标记
        self.history = []  # 行动历史
        
        # 结局相关
        self.ending_triggered = False
        self.ending_type = None
        
        # 代价追踪（用于记录使用特殊选项的代价）
        self.costs_paid = []  # 已支付的代价列表
        self.moral_corruption = 0  # 道德腐化值（0-100）
        self.broken_trust = []  # 被破坏信任的关系列表
        
    def to_dict(self) -> Dict:
        """序列化为字典"""
        return {
            "world_setting": self.world_setting,
            "world_description": self.world_description,
            "current_scene": self.current_scene,
            "scene_context": self.scene_context,
            "turn_count": self.turn_count,
            "player": self.player,
            "npcs": self.npcs,
            "flags": self.flags,
            "history": self.history,
            "ending_triggered": self.ending_triggered,
            "ending_type": self.ending_type,
            "costs_paid": self.costs_paid,
            "moral_corruption": self.moral_corruption,
            "broken_trust": self.broken_trust
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'GameState':
        """从字典反序列化"""
        state = cls()
        state.world_setting = data.get("world_setting", "")
        state.world_description = data.get("world_description", "")
        state.current_scene = data.get("current_scene", "")
        state.scene_context = data.get("scene_context", "")
        state.turn_count = data.get("turn_count", 0)
        state.player = data.get("player", state.player)
        state.npcs = data.get("npcs", {})
        state.flags = data.get("flags", {})
        state.history = data.get("history", [])
        state.ending_triggered = data.get("ending_triggered", False)
        state.ending_type = data.get("ending_type", None)
        state.costs_paid = data.get("costs_paid", [])
        state.moral_corruption = data.get("moral_corruption", 0)
        state.broken_trust = data.get("broken_trust", [])
        return state
    
    def update_npc(self, name: str, **kwargs):
        """更新NPC状态"""
        if name not in self.npcs:
            self.npcs[name] = {
                "relationship": 0,  # -100到100
                "attitude": "中立",
                "secrets": [],
                "status": "正常"
            }
        self.npcs[name].update(kwargs)
    
    def add_history(self, action: str, result: str):
        """添加历史记录"""
        self.history.append({
            "turn": self.turn_count,
            "action": action,
            "result": result,
            "timestamp": datetime.now().isoformat()
        })
        # 只保留最近20条记录
        if len(self.history) > 20:
            self.history = self.history[-20:]


class WorldlineEngine:
    """
    世界线抉择游戏引擎
    完全开放式，AI生成所有内容
    """
    
    def __init__(self, model: str = "default"):
        self.state = GameState()
        self.model = model
        self.save_dir = os.path.expanduser("~/.claude/skills/worldline_choice/saves")
        os.makedirs(self.save_dir, exist_ok=True)
        
    def initialize_world(self, world_setting: str, player_role: str = "", 
                         player_name: str = "", world_desc: str = ""):
        """
        初始化游戏世界
        不预设任何固定剧情，完全由AI生成世界观
        """
        self.state.world_setting = world_setting
        self.state.world_description = world_desc
        self.state.player["name"] = player_name or "主角"
        self.state.player["role"] = player_role or "参与者"
        self.state.turn_count = 0
        
        # 生成初始属性（根据角色类型）
        self._generate_initial_attributes(player_role)
        
    def _generate_initial_attributes(self, role: str):
        """根据角色生成初始属性"""
        # 通用属性模板
        attribute_templates = {
            "default": ["武力", "智力", "魅力", "声望"],
            "侦探": ["观察", "推理", "人脉", "冷静"],
            "战士": ["力量", "敏捷", "体质", "意志"],
            "谋士": ["谋略", "学识", "口才", "洞察"],
            "商人": ["财富", "谈判", "信息", "信誉"]
        }
        
        # 检测角色类型
        role_type = "default"
        role_lower = role.lower()
        for key in attribute_templates:
            if key in role_lower or any(word in role_lower for word in self._get_role_keywords(key)):
                role_type = key
                break
        
        attrs = attribute_templates.get(role_type, attribute_templates["default"])
        self.state.player["attributes"] = {attr: random.randint(10, 20) for attr in attrs}
        
    def _get_role_keywords(self, role_type: str) -> List[str]:
        """获取角色类型的关键词"""
        keywords = {
            "侦探": ["侦探", "调查", "记者", "警察", "卧底", "探员"],
            "战士": ["战士", "武士", "武将", "军人", "保镖", "猎人"],
            "谋士": ["谋士", "军师", "策士", "学者", "法师", "智者"],
            "商人": ["商人", " trader", "商人", "掌柜", "老板", "中介"]
        }
        return keywords.get(role_type, [])
    
    def get_system_prompt(self) -> str:
        """
        生成系统Prompt，让AI理解游戏规则和当前状态
        不预设任何剧情，完全由AI根据状态生成
        """
        history_text = "\n".join([
            f"回合{h['turn']}: {h['action']} -> {h['result'][:100]}..."
            for h in self.state.history[-5:]  # 最近5条
        ]) if self.state.history else "游戏刚开始"
        
        npcs_text = "\n".join([
            f"- {name}: 关系{info.get('relationship', 0)}, 态度{info.get('attitude', '中立')}, 状态{info.get('status', '正常')}"
            for name, info in self.state.npcs.items()
        ]) if self.state.npcs else "暂无重要NPC"
        
        return f"""你是《世界线·抉择》的叙事AI。这是一个基于"{self.state.world_setting}"世界观的互动叙事游戏。

【世界观背景】
{self.state.world_description or '请根据世界设定自行构建合理的背景'}

【当前游戏状态】
- 回合数: {self.state.turn_count}
- 玩家角色: {self.state.player['name']} ({self.state.player['role']})
- 玩家属性: {json.dumps(self.state.player['attributes'], ensure_ascii=False)}
- 持有物品: {', '.join(self.state.player['items']) or '无'}
- 性格标签: {', '.join(self.state.player['tags']) or '暂无'}
- 知道的秘密: {', '.join(self.state.player['secrets']) or '暂无'}

【重要NPC】
{npcs_text}

【历史记录】
{history_text}

【你的任务】
1. 根据当前状态生成一个引人入胜的场景（100-200字），包含冲突或抉择点
2. 分析场景中的核心矛盾
3. 生成4个不同方向的预设选项，每个代表不同的剧情走向
4. 等待玩家选择或自由输入
5. 根据玩家行动推演后果，更新状态

【选项设计原则】
- 不按性格分类，按剧情方向设计
- 每个选项代表实质不同的分支（支持某方/选择方法/道德立场）
- A/B/C选项必须有真实的权衡，没有"完美"选择，每个都有代价
- D选项（特殊路线）设计规则：
  * 只有在玩家拥有特定标签/物品/关系时才显示
  * 不应该是"完美解决方案"，而是有代价的双刃剑
  * 可能比常规选项更高效，但会牺牲某些东西（道德、关系、未来选项、永久属性）
  * 可能带来隐藏风险或意想不到的负面后果
  * 示例：用黑魔法快速解决问题但获得【腐化】标签；背叛盟友获得短期利益但永久损失信任；使用禁忌力量拯救现在但失去未来某种可能性
  * D选项的hint应该暗示这种代价或风险

【输出格式】
返回JSON格式：
{{
  "scene_title": "场景标题",
  "scene_description": "场景描述",
  "conflict": "核心冲突",
  "options": {{
    "A": {{"direction": "方向描述", "text": "选项文本", "hint": "暗示性后果"}},
    "B": {{"direction": "方向描述", "text": "选项文本", "hint": "暗示性后果"}},
    "C": {{"direction": "方向描述", "text": "选项文本", "hint": "暗示性后果"}},
    "D": {{"direction": "方向描述", "text": "选项文本", "hint": "暗示性后果", "condition": "触发条件(如有)"}}
  }},
  "present_npcs": ["当前在场的NPC"],
  "atmosphere": "氛围关键词",
  "secrets_hint": ["可能的隐藏线索"]
}}
"""
    
    def get_action_prompt(self, player_input: str) -> str:
        """
        生成处理玩家行动的Prompt
        """
        return f"""玩家在当前场景中做出了选择/行动。

【当前场景】
{self.state.current_scene}

【玩家行动】
{player_input}

【可行性评估原则 - 严格客观】
评估可行性时必须完全基于客观事实，不刻意迎合也不刻意刁难：

1. **客观能力检查**
   - 玩家是否有执行此行动所需的技能/能力？
   - 玩家属性是否达到行动要求？（如武力15以上才能单挑精英守卫）
   - 玩家是否拥有必要物品？（如开锁需要工具，飞行需要坐骑）

2. **情境限制检查**
   - 当前环境是否允许此行动？（如在密闭空间无法召唤大型生物）
   - 时间是否充裕？（如3分钟内无法完成需要1小时的仪式）
   - 是否有物理限制？（如无绳索无法攀爬光滑岩壁）

3. **信息掌握检查**
   - 玩家是否知道执行此行动所需的信息？
   - 不能假设玩家知道未发现的秘密或NPC的真实身份
   - 尝试利用未知信息应失败或产生意外后果

4. **合理性评估**
   - 行动是否符合游戏世界的基本逻辑和物理法则？
   - 新手不可能瞬间击败大师，凡人不能随意撼动神祇
   - 社会关系不能瞬间逆转（敌视→信任需要时间）

5. **难度分级**
   - 简单：玩家能力明显足够，高成功率
   - 困难：玩家能力勉强，需要检定或有失败风险
   - 极难：玩家能力不足，几乎不可能成功
   - 不可能：完全超出玩家能力范围，明确拒绝

【重要原则】
- 不刻意迎合：不能因为玩家想这么做就让其轻易成功
- 不刻意刁难：不能因为玩家想这么做就故意使其失败
- 客观公正：基于事实判断，让玩家为自己的选择承担真实后果
- 失败也有趣：失败应该产生有意义的后果，而非简单的"你失败了"

【处理方式】
- 可行：正常执行，根据难度决定成功程度
- 困难但可行：执行但伴随高风险或负面后果
- 不可行：明确告知为什么不可行，并提供合理化的替代方案
- 部分可行：行动部分成功，但效果打折或有意外代价

【处理要求】
1. 解析玩家意图（行动类型：战斗/对话/观察/物品/移动/其他）
2. 基于上述原则严格评估可行性
3. 推演行动的直接后果和长期影响（成功或失败都有后果）
4. 更新相关状态（属性变化、关系变化、获得物品、触发事件）
5. 判断是否触发结局条件

【状态更新规则】
- 成功行动可能提升相关属性或关系
- 失败或鲁莽行动会带来真实的负面后果
- 超出能力的尝试可能导致受伤、损失物品或关系恶化
- 关键行动会添加剧情标记(flags)
- 每次行动推进回合数

【输出格式】
返回JSON格式：
{{
  "intention": "解析的玩家意图",
  "action_type": "行动类型",
  "feasible": true/false,
  "narrative": "剧情描述（150-250字），描述发生了什么",
  "consequences": {{
    "attribute_changes": {{}},
    "relationship_changes": {{}},
    "items_gained": [],
    "items_lost": [],
    "tags_added": [],
    "secrets_learned": [],
    "npc_changes": {{}}
  }},
  "flags_set": {{}},
  "ending_triggered": false,
  "ending_type": null,
  "next_scene_hint": "下一场景的建议方向"
}}
"""
    
    def get_ending_prompt(self) -> str:
        """生成结局的Prompt"""
        return f"""游戏已达到结局条件，请生成结局剧情。

【完整游戏回顾】
- 世界观: {self.state.world_setting}
- 玩家: {self.state.player['name']} ({self.state.player['role']})
- 回合数: {self.state.turn_count}
- 最终属性: {json.dumps(self.state.player['attributes'], ensure_ascii=False)}
- 重要关系: {json.dumps({k: v.get('relationship', 0) for k, v in self.state.npcs.items()}, ensure_ascii=False)}
- 关键选择: {[h['action'] for h in self.state.history]}
- 持有物品: {self.state.player['items']}
- 性格标签: {self.state.player['tags']}
- 已支付的代价: {self.state.costs_paid}
- 道德腐化值: {self.state.moral_corruption}/100
- 被破坏的信任: {self.state.broken_trust}

【结局判定】
根据玩家的整体行为和选择，判断最符合的结局类型：
- 正义结局：坚持正义，完成使命
- 悲剧结局：牺牲或失败
- 灰色结局：达成目标但付出代价
- 反转结局：出乎意料的转折
- 隐藏结局：特殊条件触发的独特结局

【输出格式】
{{
  "ending_type": "结局类型",
  "ending_title": "结局标题",
  "ending_text": "结局剧情（200-300字）",
  "ending_summary": "一句话总结",
  "player_evaluation": "对玩家表现的评价",
  "unlocked_secrets": ["揭露的秘密"],
  "statistics": {{
    "total_turns": {self.state.turn_count},
    "key_choices": 0,
    "npcs_encountered": 0
  }}
}}
"""
    
    def start_game(self, world_setting: str, player_role: str = "", 
                   player_name: str = "", world_desc: str = "") -> Dict:
        """
        开始新游戏
        返回初始场景
        """
        self.initialize_world(world_setting, player_role, player_name, world_desc)
        
        # 返回初始化信息，实际场景由AI生成
        return {
            "initialized": True,
            "world": world_setting,
            "player": self.state.player,
            "message": "游戏初始化完成。请AI根据世界观生成开场场景。",
            "system_prompt": self.get_system_prompt()
        }
    
    def process_action(self, player_input: str, ai_response: Dict) -> Dict:
        """
        处理玩家行动并更新状态
        ai_response: AI返回的JSON解析结果
        """
        # 更新回合数
        self.state.turn_count += 1
        
        # 解析AI返回的状态变化
        consequences = ai_response.get("consequences", {})
        
        # 更新属性
        attr_changes = consequences.get("attribute_changes", {})
        for attr, delta in attr_changes.items():
            if attr in self.state.player["attributes"]:
                self.state.player["attributes"][attr] += delta
        
        # 更新关系
        rel_changes = consequences.get("relationship_changes", {})
        for npc_name, delta in rel_changes.items():
            current_rel = self.state.npcs.get(npc_name, {}).get("relationship", 0)
            self.state.update_npc(npc_name, relationship=current_rel + delta)
        
        # 更新物品
        items_gained = consequences.get("items_gained", [])
        items_lost = consequences.get("items_lost", [])
        self.state.player["items"].extend(items_gained)
        for item in items_lost:
            if item in self.state.player["items"]:
                self.state.player["items"].remove(item)
        
        # 更新标签
        tags_added = consequences.get("tags_added", [])
        self.state.player["tags"].extend(tags_added)
        
        # 更新秘密
        secrets_learned = consequences.get("secrets_learned", [])
        self.state.player["secrets"].extend(secrets_learned)
        
        # 更新NPC状态
        npc_changes = consequences.get("npc_changes", {})
        for npc_name, changes in npc_changes.items():
            self.state.update_npc(npc_name, **changes)
        
        # 更新flags
        flags_set = ai_response.get("flags_set", {})
        self.state.flags.update(flags_set)
        
        # 处理D选项（特殊路线）的代价
        # 如果这次行动是D选项，记录其代价
        if "使用了D选项" in player_input or "特殊路线" in player_input:
            cost = consequences.get("special_cost")
            if cost:
                self.state.costs_paid.append({
                    "turn": self.state.turn_count,
                    "cost": cost,
                    "action": player_input
                })
                # 如果是道德代价，增加腐化值
                if isinstance(cost, dict):
                    if "腐化" in cost or "道德" in cost:
                        self.state.moral_corruption += cost.get("value", 10)
                    if "背叛" in cost or "信任" in cost:
                        npc = cost.get("npc", "未知")
                        self.state.broken_trust.append(npc)
        
        # 检查结局
        if ai_response.get("ending_triggered"):
            self.state.ending_triggered = True
            self.state.ending_type = ai_response.get("ending_type")
        
        # 记录历史
        narrative = ai_response.get("narrative", "")
        self.state.add_history(player_input, narrative)
        
        # 更新当前场景
        if "next_scene_hint" in ai_response:
            self.state.scene_context = ai_response["next_scene_hint"]
        
        return {
            "turn": self.state.turn_count,
            "narrative": narrative,
            "consequences": consequences,
            "state_changed": True,
            "ending_triggered": self.state.ending_triggered,
            "current_state": self.get_current_state()
        }
    
    def get_current_state(self) -> Dict:
        """获取当前游戏状态"""
        return {
            "turn": self.state.turn_count,
            "player": self.state.player,
            "npcs": self.state.npcs,
            "flags": self.state.flags,
            "items": self.state.player["items"],
            "tags": self.state.player["tags"],
            "costs_paid": self.state.costs_paid,
            "moral_corruption": self.state.moral_corruption,
            "broken_trust": self.state.broken_trust
        }
    
    def check_feasibility(self, action: Dict) -> Dict:
        """
        客观可行性检查辅助方法
        返回可行性评估结果
        """
        result = {
            "feasible": True,
            "difficulty": "简单",  # 简单/困难/极难/不可能
            "requirements": [],
            "missing": [],
            "warnings": []
        }
        
        # 检查属性要求
        attr_requirements = action.get("required_attributes", {})
        for attr, min_value in attr_requirements.items():
            current = self.state.player["attributes"].get(attr, 0)
            if current < min_value:
                result["missing"].append(f"{attr}需要{min_value}，当前{current}")
                result["feasible"] = False
        
        # 检查物品要求
        required_items = action.get("required_items", [])
        for item in required_items:
            if item not in self.state.player["items"]:
                result["missing"].append(f"需要物品：{item}")
                result["feasible"] = False
        
        # 检查标签要求
        required_tags = action.get("required_tags", [])
        for tag in required_tags:
            if tag not in self.state.player["tags"]:
                result["missing"].append(f"需要标签：{tag}")
                result["feasible"] = False
        
        # 检查关系要求
        required_relationships = action.get("required_relationships", {})
        for npc, min_rel in required_relationships.items():
            current = self.state.npcs.get(npc, {}).get("relationship", 0)
            if current < min_rel:
                result["missing"].append(f"与{npc}的关系需要{min_rel}，当前{current}")
                result["feasible"] = False
        
        # 检查知识要求
        required_secrets = action.get("required_secrets", [])
        for secret in required_secrets:
            if secret not in self.state.player["secrets"]:
                result["missing"].append(f"需要知道：{secret}")
                result["warnings"].append("尝试使用未知信息")
        
        # 确定难度
        if result["missing"]:
            missing_count = len(result["missing"])
            if missing_count >= 3:
                result["difficulty"] = "不可能"
            elif missing_count == 2:
                result["difficulty"] = "极难"
            elif missing_count == 1:
                result["difficulty"] = "困难"
        
        return result
    
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
    
    def list_saves(self) -> List[Dict]:
        """列出所有存档"""
        saves = []
        for filename in os.listdir(self.save_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.save_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    saves.append({
                        "id": filename[:-5],
                        "world": data.get("world_setting", "未知"),
                        "turn": data.get("turn_count", 0),
                        "player": data.get("player", {}).get("name", "未知"),
                        "last_modified": os.path.getmtime(filepath)
                    })
        return sorted(saves, key=lambda x: x["last_modified"], reverse=True)


# 命令行接口
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
        
        if command == "--new" or command == "-n":
            self.cmd_new(args[1:])
        elif command == "--load" or command == "-l":
            self.cmd_load(args[1:])
        elif command == "--list" or command == "-ls":
            self.cmd_list()
        elif command == "--delete" or command == "-d":
            self.cmd_delete(args[1:])
        elif command == "--help" or command == "-h":
            self.show_help()
        else:
            # 默认启动新游戏
            self.cmd_new(args)
    
    def cmd_new(self, args: List[str]):
        """开始新游戏"""
        world = args[0] if len(args) > 0 else input("请输入世界观设定: ")
        role = args[1] if len(args) > 1 else input("请输入你的角色身份: ")
        name = args[2] if len(args) > 2 else input("请输入角色名字: ")
        
        result = self.engine.start_game(world, role, name)
        print(f"\n{'='*50}")
        print(f"游戏开始: {world}")
        print(f"{'='*50}")
        print(f"\n角色: {name} ({role})")
        print(f"属性: {json.dumps(result['player']['attributes'], ensure_ascii=False)}")
        print(f"\n请AI根据以上设定生成开场场景...")
        print(f"\n系统Prompt已生成，请使用AI生成场景。")
        print(f"\n使用: get_system_prompt() 获取完整Prompt")
        
    def cmd_load(self, args: List[str]):
        """加载游戏"""
        if len(args) < 1:
            print("错误: 请指定存档ID")
            return
        save_id = args[0]
        if self.engine.load_game(save_id):
            print(f"已加载存档: {save_id}")
            print(f"当前回合: {self.engine.state.turn_count}")
            print(f"世界观: {self.engine.state.world_setting}")
        else:
            print(f"存档不存在: {save_id}")
    
    def cmd_list(self):
        """列出存档"""
        saves = self.engine.list_saves()
        if not saves:
            print("暂无存档")
            return
        print(f"\n{'存档ID':<20} {'世界观':<20} {'回合':<8} {'角色':<15}")
        print("-" * 70)
        for save in saves:
            print(f"{save['id']:<20} {save['world']:<20} {save['turn']:<8} {save['player']:<15}")
    
    def cmd_delete(self, args: List[str]):
        """删除存档"""
        if len(args) < 1:
            print("错误: 请指定存档ID")
            return
        save_id = args[0]
        filepath = os.path.join(self.engine.save_dir, f"{save_id}.json")
        if os.path.exists(filepath):
            os.remove(filepath)
            print(f"已删除存档: {save_id}")
        else:
            print(f"存档不存在: {save_id}")
    
    def show_help(self):
        """显示帮助"""
        print("""
Worldline Choice - AI驱动互动叙事游戏引擎

用法:
  worldline_choice [命令] [参数]

命令:
  --new, -n [世界观] [角色] [名字]  开始新游戏
  --load, -l <存档ID>              加载存档
  --list, -ls                      列出所有存档
  --delete, -d <存档ID>            删除存档
  --help, -h                       显示帮助

示例:
  worldline_choice --new "三国" "谋士" "诸葛亮"
  worldline_choice --load save_001

Python API:
  from worldline_engine import WorldlineEngine
  engine = WorldlineEngine()
  engine.start_game("1960年代香港", "卧底警察", "阿超")
  prompt = engine.get_system_prompt()
        """)


def main():
    """主入口"""
    cli = GameCLI()
    cli.run(sys.argv[1:])


if __name__ == "__main__":
    main()
