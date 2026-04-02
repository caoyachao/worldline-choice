#!/usr/bin/env python3
"""
Worldline Choice Game Engine v3.3.2
主控引擎 - 协调骰子检定和存档管理
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, Optional

class WorldlineGameEngine:
    """
    Worldline Choice 游戏引擎
    整合骰子检定和存档管理
    """
    
    def __init__(self, save_path: str):
        """
        初始化游戏引擎
        
        参数:
            save_path: 存档文件路径
        """
        self.save_path = save_path
        self.skill_path = Path(__file__).parent
        
        # 导入save_manager
        sys.path.insert(0, str(self.skill_path))
        from save_manager import WorldlineSaveManager
        self.manager = WorldlineSaveManager(save_path)
    
    def roll_check(self, attribute_name: str, dc: int, context: str = "") -> Dict[str, Any]:
        """
        执行一次d20检定
        
        参数:
            attribute_name: 属性名称 (如 "洞察力")
            dc: 难度等级
            context: 检定场景描述
            
        返回:
            检定结果字典
        """
        # 获取属性值
        attributes = self.manager.data["player"]["attributes"]
        if attribute_name not in attributes:
            raise KeyError(f"属性 '{attribute_name}' 不存在")
        
        attribute_value = attributes[attribute_name]["value"]
        
        # 调用dice_roller.py
        cmd = [
            "python3",
            str(self.skill_path / "dice_roller.py"),
            str(attribute_value),
            str(dc),
            attribute_name,
            context
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"骰子脚本执行失败: {result.stderr}")
        
        return json.loads(result.stdout)
    
    def get_player_attribute(self, attribute_name: str) -> int:
        """获取玩家属性值"""
        return self.manager.data["player"]["attributes"][attribute_name]["value"]
    
    def get_player_modifier(self, attribute_name: str) -> int:
        """获取玩家属性加值"""
        return self.manager.data["player"]["attributes"][attribute_name]["modifier"]
    
    def get_resource(self, resource_name: str) -> Any:
        """获取资源值"""
        return self.manager.data["player"]["resources"][resource_name]["value"]
    
    def get_npc_relationship(self, npc_id: str, relationship_type: str) -> int:
        """获取NPC关系值"""
        npc = self.manager.data["npc_database"][npc_id]
        return npc["relationship_matrix"]["towards_player"][relationship_type]["value"]
    
    def format_check_result(self, result: Dict[str, Any], language: str = "en") -> str:
        """
        Format dice check result for display
        
        Args:
            result: Dice check result dict
            language: Output language ("en" or "zh")
            
        Returns:
            Formatted string
        """
        check = result["check"]
        roll = result["roll"]
        res = result["result"]
        
        if language == "zh":
            output = f"""
【检定结果】
属性: {check['attribute']} ({check['attribute_value']})
DC: {check['dc']}
骰值: d20={roll['d20']}, 加值={roll['modifier']}, 总计={roll['total']}
结果: {res['description']}
成功: {'是' if res['success'] else '否'}
差距: {res['margin']:+d}
对后续影响: DC{result['impact']['next_dc_modifier']:+d}
信息泄露: {'是' if result['impact']['info_leak'] else '否'}
"""
        else:
            output = f"""
[CHECK RESULT]
Attribute: {check['attribute']} ({check['attribute_value']})
DC: {check['dc']}
Roll: d20={roll['d20']}, modifier={roll['modifier']}, total={roll['total']}
Result: {res['description']}
Success: {'Yes' if res['success'] else 'No'}
Margin: {res['margin']:+d}
Next DC Modifier: {result['impact']['next_dc_modifier']:+d}
Info Leak: {'Yes' if result['impact']['info_leak'] else 'No'}
"""
        return output.strip()
    
    def export_session_summary(self, session_idx: int = -1) -> str:
        """
        导出回合摘要
        
        参数:
            session_idx: 回合索引，-1表示最新回合
            
        返回:
            Markdown格式的摘要
        """
        if session_idx == -1:
            session_idx = len(self.manager.data["session_history"]) - 1
        
        if session_idx < 0 or session_idx >= len(self.manager.data["session_history"]):
            return "无回合记录"
        
        session = self.manager.data["session_history"][session_idx]
        
        lines = [
            f"## 回合 {session['session_id']}",
            f"",
            f"**游戏时间**: {session['game_time_start']} ~ {session.get('game_time_end', '进行中')}",
            f"**场景**: {session['scene_summary']}",
            f"",
            "### 事件记录",
        ]
        
        for entry in session["entries"]:
            lines.append(f"- **{entry['timestamp']}** [{entry['type']}]: {entry['content'][:100]}...")
        
        outcome = session.get("session_outcome", {})
        if outcome:
            lines.extend([
                "",
                "### 回合结果",
                f"- 获得情报: {', '.join(outcome.get('intelligence_gained', [])) or '无'}",
                f"- 获得物品: {', '.join(outcome.get('items_gained', [])) or '无'}",
                f"- 关系变化: {len(outcome.get('relationship_changes', []))} 项",
                f"- 待决定: {', '.join(outcome.get('pending_decisions', [])) or '无'}",
            ])
        
        return "\n".join(lines)
    
    def get_current_world_state(self) -> str:
        """获取当前世界状态摘要"""
        ws = self.manager.data["world_state"]
        return f"📅 {ws['current_date']} {ws['current_time']} | 📍 {ws['current_location']}"
    
    def get_pending_quests(self) -> list:
        """获取进行中的任务"""
        return [q for q in self.manager.data["active_quests"] 
                if q["status"] in ["pending", "active"]]


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python3 game_engine.py <save_path>")
        print("Example: python3 game_engine.py /path/to/your/save.json")
        sys.exit(1)
    
    save_path = sys.argv[1]
    engine = WorldlineGameEngine(save_path)
    
    print("=== Worldline Choice Game Engine v3.3.2 ===")
    print(f"Current State: {engine.get_current_world_state()}")
    print()
    
    # Example: Get first available attribute for demo
    attributes = list(engine.manager.data["player"]["attributes"].keys())
    if attributes:
        sample_attr = attributes[0]
        print(f"Executing sample check with attribute: {sample_attr}")
        result = engine.roll_check(sample_attr, 15, "sample_check")
        print(engine.format_check_result(result, language="en"))
    else:
        print("No attributes defined in save file")
