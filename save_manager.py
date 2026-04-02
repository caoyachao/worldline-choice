#!/usr/bin/env python3
"""
Worldline Choice Save Manager v3.3.2
通用存档管理系统
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional

class WorldlineSaveManager:
    """
    Worldline Choice 存档管理器
    支持通用游戏存档的读取、更新和维护
    """
    
    def __init__(self, save_path: str):
        """
        初始化存档管理器
        
        参数:
            save_path: 存档文件路径
        """
        self.save_path = save_path
        self.data = self._load_save()
    
    def _load_save(self) -> Dict[str, Any]:
        """加载存档文件，如果不存在则创建新存档"""
        if os.path.exists(self.save_path):
            with open(self.save_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return self._create_new_save()
    
    def _create_new_save(self) -> Dict[str, Any]:
        """创建新的空存档结构"""
        return {
            "metadata": {
                "game_id": "",
                "game_title": "",
                "world_setting": "",
                "engine_version": "worldline-choice-v3.3.2",
                "created_at": datetime.now().isoformat(),
                "last_saved": datetime.now().isoformat(),
                "total_sessions": 0
            },
            "world_state": {
                "current_date": "",
                "current_time": "",
                "current_location": "",
                "scene_description": "",
                "global_events": []
            },
            "player": {
                "name": "",
                "role": "",
                "background": "",
                "attributes": {},
                "resources": {}
            },
            "session_history": [],
            "npc_database": {},
            "active_quests": [],
            "inventory": {
                "documents": [],
                "contacts": [],
                "intelligence": []
            },
            "story_flags": {}
        }
    
    def save(self):
        """保存当前状态到文件"""
        self.data["metadata"]["last_saved"] = datetime.now().isoformat()
        with open(self.save_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
    
    # ==================== Player 操作 ====================
    
    def set_player_info(self, name: str, role: str, background: str = ""):
        """设置玩家基本信息"""
        self.data["player"]["name"] = name
        self.data["player"]["role"] = role
        self.data["player"]["background"] = background
    
    def set_player_attributes(self, attributes: Dict[str, int]):
        """
        设置玩家属性
        
        参数:
            attributes: {"魄力": 12, "洞察力": 13, ...}
        """
        for name, value in attributes.items():
            modifier = (value - 10) // 2
            self.data["player"]["attributes"][name] = {
                "value": value,
                "modifier": modifier
            }
    
    def update_resource(self, resource_name: str, resource_type: str, 
                        value: Any, unit: str = "points", **extra):
        """
        更新或创建资源
        
        参数:
            resource_name: 资源名称
            resource_type: 资源类型 (currency/reputation/health/mana/material/custom)
            value: 资源值
            unit: 单位
            **extra: 额外字段 (如scope等)
        """
        resource = {
            "type": resource_type,
            "value": value,
            "unit": unit
        }
        resource.update(extra)
        self.data["player"]["resources"][resource_name] = resource
    
    def modify_resource(self, resource_name: str, delta: Any, reason: str = ""):
        """
        修改资源值
        
        参数:
            resource_name: 资源名称
            delta: 变化量 (+/-)
            reason: 变化原因
        """
        if resource_name not in self.data["player"]["resources"]:
            raise KeyError(f"资源 '{resource_name}' 不存在")
        
        current = self.data["player"]["resources"][resource_name]["value"]
        
        # 支持数值和字符串类型的变化
        if isinstance(current, (int, float)) and isinstance(delta, (int, float)):
            self.data["player"]["resources"][resource_name]["value"] = current + delta
        else:
            self.data["player"]["resources"][resource_name]["value"] = delta
    
    # ==================== NPC 操作 ====================
    
    def create_npc(self, npc_id: str, name: str, identity: str, 
                   faction: str = "", location: str = "", aliases: List[str] = None):
        """
        创建新NPC
        
        参数:
            npc_id: NPC唯一标识符
            name: NPC名称
            identity: NPC身份描述
            faction: 所属派系
            location: 所在地点
            aliases: 别名列表
        """
        self.data["npc_database"][npc_id] = {
            "basic_info": {
                "name": name,
                "aliases": aliases or [],
                "identity": identity,
                "faction": faction,
                "location": location
            },
            "relationship_matrix": {
                "towards_player": {
                    "trust": {"value": 5, "max": 10, "trend": "stable"},
                    "respect": {"value": 5, "max": 10, "trend": "stable"},
                    "fear": {"value": 0, "max": 10, "trend": "stable"},
                    "affection": {"value": 0, "max": 10, "trend": "stable"},
                    "interest": {"value": 5, "max": 10, "trend": "stable"},
                    "dislike": {"value": 0, "max": 10, "trend": "stable"},
                    "hatred": {"value": 0, "max": 10, "trend": "stable"},
                    "jealousy": {"value": 0, "max": 10, "trend": "stable"},
                    "contempt": {"value": 0, "max": 10, "trend": "stable"}
                },
                "player_towards": {
                    "trust": 5,
                    "respect": 5,
                    "fear": 0,
                    "interest": 5,
                    "dislike": 0,
                    "hatred": 0
                }
            },
            "knowledge_state": {
                "secrets_known_by_npc": [],
                "secrets_known_by_player": [],
                "misconceptions": []
            },
            "interaction_history": [],
            "current_state": {
                "mood": "neutral",
                "urgency": "normal",
                "goals": [],
                "pressure": "none",
                "available_actions": []
            },
            "social_network": {
                "allies": [],
                "enemies": [],
                "subordinates": [],
                "family": [],
                "business_partners": []
            }
        }
    
    def update_npc_relationship(self, npc_id: str, relationship_type: str, 
                                delta: int, reason: str = "",
                                auto_create: bool = False,
                                initial_value: int = 5,
                                max_value: int = 10):
        """
        更新NPC对玩家的关系
        
        参数:
            npc_id: NPC标识符
            relationship_type: 关系类型 (trust/respect/fear/affection/interest/dislike/hatred/jealousy/contempt/自定义)
            delta: 变化量 (+/-)
            reason: 变化原因
            auto_create: 如果关系类型不存在，是否自动创建
            initial_value: 自动创建时的初始值
            max_value: 自动创建时的最大值
        """
        if npc_id not in self.data["npc_database"]:
            raise KeyError(f"NPC '{npc_id}' 不存在")
        
        matrix = self.data["npc_database"][npc_id]["relationship_matrix"]["towards_player"]
        
        # 如果关系类型不存在且允许自动创建
        if relationship_type not in matrix and auto_create:
            matrix[relationship_type] = {
                "value": initial_value,
                "max": max_value,
                "trend": "stable"
            }
        
        if relationship_type in matrix:
            current = matrix[relationship_type]["value"]
            max_val = matrix[relationship_type].get("max", 10)
            new_value = max(0, min(max_val, current + delta))  # 限制在0-max范围
            matrix[relationship_type]["value"] = new_value
            
            # 更新趋势
            if delta > 0:
                matrix[relationship_type]["trend"] = "rising"
            elif delta < 0:
                matrix[relationship_type]["trend"] = "declining"
            else:
                matrix[relationship_type]["trend"] = "stable"
        else:
            raise KeyError(f"关系类型 '{relationship_type}' 不存在。使用 auto_create=True 自动创建新关系维度。")
    
    def add_npc_interaction(self, npc_id: str, date: str, interaction_type: str,
                           context: str, outcome: str, relationship_changes: Dict[str, int] = None):
        """
        添加NPC互动记录
        
        参数:
            npc_id: NPC标识符
            date: 游戏内日期
            interaction_type: 互动类型 (meeting/negotiation/social/conflict/etc)
            context: 场景描述
            outcome: 结果
            relationship_changes: 关系变化 {"trust": +1, ...}
        """
        if npc_id not in self.data["npc_database"]:
            raise KeyError(f"NPC '{npc_id}' 不存在")
        
        interaction = {
            "date": date,
            "type": interaction_type,
            "context": context,
            "outcome": outcome,
            "relationship_changes": relationship_changes or {}
        }
        
        self.data["npc_database"][npc_id]["interaction_history"].append(interaction)
        
        # 自动应用关系变化
        if relationship_changes:
            for rel_type, delta in relationship_changes.items():
                self.update_npc_relationship(npc_id, rel_type, delta)
    
    def add_npc_secret(self, npc_id: str, secret: str, known_by: str = "player"):
        """
        添加NPC相关秘密
        
        参数:
            npc_id: NPC标识符
            secret: 秘密内容
            known_by: "player" 或 "npc" (谁知道这个秘密)
        """
        if npc_id not in self.data["npc_database"]:
            raise KeyError(f"NPC '{npc_id}' 不存在")
        
        key = "secrets_known_by_player" if known_by == "player" else "secrets_known_by_npc"
        if secret not in self.data["npc_database"][npc_id]["knowledge_state"][key]:
            self.data["npc_database"][npc_id]["knowledge_state"][key].append(secret)
    
    # ==================== Session 操作 ====================
    
    def start_new_session(self, game_time_start: str, scene_summary: str = "") -> int:
        """
        开始新的游戏回合
        
        参数:
            game_time_start: 游戏内开始时间
            scene_summary: 场景摘要
            
        返回:
            session_id (序号)
        """
        session_id = len(self.data["session_history"]) + 1
        
        session = {
            "session_id": f"session_{session_id:03d}",
            "real_world_time": datetime.now().isoformat(),
            "game_time_start": game_time_start,
            "game_time_end": "",
            "scene_summary": scene_summary,
            "entries": [],
            "session_outcome": {
                "resources_gained": [],
                "resources_lost": [],
                "intelligence_gained": [],
                "items_gained": [],
                "relationship_changes": [],
                "quests_completed": [],
                "quests_started": [],
                "pending_decisions": []
            }
        }
        
        self.data["session_history"].append(session)
        self.data["metadata"]["total_sessions"] = session_id
        
        return session_id - 1  # 返回索引
    
    def add_session_entry(self, session_idx: int, entry_type: str, 
                         timestamp: str, content: str, **extra):
        """
        向当前回合添加条目
        
        参数:
            session_idx: session索引
            entry_type: 条目类型 (scene_opening/player_action/dialogue/narrative_event/reflection)
            timestamp: 游戏内时间戳
            content: 内容描述
            **extra: 额外字段
        """
        entry_id = f"e{len(self.data['session_history'][session_idx]['entries']) + 1:03d}"
        
        entry = {
            "entry_id": entry_id,
            "type": entry_type,
            "timestamp": timestamp,
            "content": content
        }
        entry.update(extra)
        
        self.data["session_history"][session_idx]["entries"].append(entry)
    
    def end_session(self, session_idx: int, game_time_end: str, 
                   outcome: Dict[str, Any]):
        """
        结束当前回合
        
        参数:
            session_idx: session索引
            game_time_end: 游戏内结束时间
            outcome: 回合结果
        """
        self.data["session_history"][session_idx]["game_time_end"] = game_time_end
        self.data["session_history"][session_idx]["session_outcome"].update(outcome)
    
    # ==================== Quest 操作 ====================
    
    def create_quest(self, quest_id: str, title: str, quest_type: str,
                    description: str, deadline: str = "", 
                    related_npcs: List[str] = None,
                    possible_approaches: List[str] = None):
        """
        创建新任务
        
        参数:
            quest_id: 任务唯一标识符
            title: 任务标题
            quest_type: 任务类型 (main/side/critical_decision)
            description: 任务描述
            deadline: 截止日期
            related_npcs: 相关NPC列表
            possible_approaches: 可能的做法
        """
        quest = {
            "quest_id": quest_id,
            "title": title,
            "type": quest_type,
            "description": description,
            "status": "pending",
            "deadline": deadline,
            "related_npcs": related_npcs or [],
            "possible_approaches": possible_approaches or [],
            "stakes": "normal",
            "failure_consequences": []
        }
        
        self.data["active_quests"].append(quest)
    
    def update_quest_status(self, quest_id: str, status: str):
        """
        更新任务状态
        
        参数:
            quest_id: 任务标识符
            status: 新状态 (pending/active/completed/failed)
        """
        for quest in self.data["active_quests"]:
            if quest["quest_id"] == quest_id:
                quest["status"] = status
                break
    
    # ==================== World State 操作 ====================
    
    def update_world_state(self, date: str = None, time: str = None,
                          location: str = None, description: str = None):
        """更新世界状态"""
        if date:
            self.data["world_state"]["current_date"] = date
        if time:
            self.data["world_state"]["current_time"] = time
        if location:
            self.data["world_state"]["current_location"] = location
        if description:
            self.data["world_state"]["scene_description"] = description
    
    def add_global_event(self, event: str, impact: str, duration: str):
        """添加全局事件"""
        self.data["world_state"]["global_events"].append({
            "event": event,
            "impact": impact,
            "duration": duration
        })
    
    # ==================== Inventory 操作 ====================
    
    def add_document(self, document: str):
        """添加文档"""
        if document not in self.data["inventory"]["documents"]:
            self.data["inventory"]["documents"].append(document)
    
    def add_contact(self, contact: str):
        """添加联系人"""
        if contact not in self.data["inventory"]["contacts"]:
            self.data["inventory"]["contacts"].append(contact)
    
    def add_intelligence(self, intelligence: str):
        """添加情报"""
        if intelligence not in self.data["inventory"]["intelligence"]:
            self.data["inventory"]["intelligence"].append(intelligence)
    
    # ==================== Story Flags 操作 ====================
    
    def set_story_flag(self, flag: str, value: Any = True):
        """设置剧情标志"""
        self.data["story_flags"][flag] = value
    
    def get_story_flag(self, flag: str) -> Any:
        """获取剧情标志"""
        return self.data["story_flags"].get(flag, False)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python3 save_manager.py <command> <save_path> [args...]")
        print("Commands:")
        print("  init <save_path> <player_name> <player_role>")
        print("  update_resource <save_path> <resource_name> <value>")
        sys.exit(1)
    
    command = sys.argv[1]
    save_path = sys.argv[2]
    manager = WorldlineSaveManager(save_path)
    
    if command == "init":
        if len(sys.argv) < 5:
            print("Usage: python3 save_manager.py init <save_path> <player_name> <player_role>")
            sys.exit(1)
        player_name = sys.argv[3]
        player_role = sys.argv[4]
        manager.set_player_info(player_name, player_role)
        manager.save()
        print(f"Save initialized for player: {player_name}")
    elif command == "update_resource":
        if len(sys.argv) < 5:
            print("Usage: python3 save_manager.py update_resource <save_path> <resource_name> <value>")
            sys.exit(1)
        resource_name = sys.argv[3]
        value = float(sys.argv[4])
        manager.modify_resource(resource_name, value)
        manager.save()
        print(f"Resource {resource_name} updated")
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
