#!/usr/bin/env python3
"""
Worldline Choice - 兼容入口层 (v4.5.0)

本文件作为向后兼容的入口点，统一代理到 worldline_skill.py 的核心实现。
确保 agent / CLI / 旧代码都能使用到内建的 d20 检定系统。

修改要点：
1. WorldlineEngine 继承自 WorldlineSkill，默认 show_dice=True，透明暴露 d20 结果。
2. 兼容旧版 API 签名（如 get_system_prompt / process_action 等映射到新接口）。
3. 旧版存档格式可通过 _migrate_legacy_save() 自动迁移到新版 flat GameState。
4. v4.5.0 新增：角色成长系统、回合结算、游戏目录隔离。
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Any

# 从新版 skill 导入全部公开接口
from worldline_skill import (
    AttributeDimension,
    ActionAnalysis,
    CheckResult,
    NarrativeContext,
    TurnOption,
    TurnOptions,
    D20Engine,
    LLMDriver,
    GameState,
    WorldlineSkill,
    cli_main,
)


class WorldlineEngine(WorldlineSkill):
    """
    向后兼容的引擎类。

    默认启用骰子显示 (show_dice=True)，让 agent/CLI 都能直接看到 d20 检定过程。
    同时保留旧版 ``WorldlineEngine`` 类的使用习惯。
    """

    def __init__(self, llm_callback: Optional[Any] = None, auto_save: bool = True):
        super().__init__(
            llm_callback=llm_callback,
            auto_save=auto_save,
            show_dice=True,  # 默认开启：让 d20 检定可见
        )
        self.save_dir = os.path.expanduser("~/.claude/skills/worldline_choice/saves")
        os.makedirs(self.save_dir, exist_ok=True)

    def initialize_world(
        self,
        world_setting: str,
        player_role: str = "",
        player_name: str = "",
        world_desc: str = "",
    ):
        """旧版初始化签名兼容。"""
        self.state = GameState()
        self.state.world_setting = world_setting
        self.state.world_description = world_desc
        self.state.current_scene = world_desc or f"{world_setting}的世界"
        self.state.player["name"] = player_name or "主角"
        self.state.player["role"] = player_role or "参与者"

        # 使用新版随机属性生成逻辑
        for attr in self.state.player["attributes"]:
            self.state.player["attributes"][attr] = D20Engine.calculate_modifier(10) + 10

        # 初始化 v4.5.0 新字段
        self.state.hp = 100
        self.state.max_hp = 100
        self.state.resources = {}
        self.state.status_effects = []
        self.state.attribute_history = {}

        # 生成游戏ID
        timestamp = int(datetime.now().timestamp())
        safe_world = "".join(c for c in world_setting if c.isalnum() or c in "_-")
        self.game_id = f"game_{timestamp}_{safe_world}"
        game_dir = self._get_game_save_dir()
        os.makedirs(game_dir, exist_ok=True)

        return self.state

    def get_system_prompt(self) -> str:
        """
        旧版接口：生成 system prompt 用于外部 LLM。
        由于新版已经内置默认回退叙事，这里提供一份可直接扔给 LLM 的 prompt，
        其中明确声明 **必须使用 d20 检定结果**叙事，禁止推翻骰子。
        """
        recent_history = self.get_history_summary(limit=5)
        npcs_text = "\n".join(
            f"- {name}: 关系{info.get('relationship', 0)}, 态度{info.get('attitude', '中立')}, 信任{info.get('trust', 0)}, 恐惧{info.get('fear', 0)}, 忠诚{info.get('loyalty', 0)}"
            for name, info in self.state.npcs.items()
        ) if self.state.npcs else "暂无重要NPC"

        inv_names = [it.get("name", it.get("id", "未知")) for it in self.state.player["inventory"].get("items", [])]
        return f"""你是《世界线·抉择》的叙事AI。这是一个基于"{self.state.world_setting}"世界观的互动叙事游戏。

【核心规则 - 必须遵守】
1. 本游戏采用 **d20 客观检定** 决定行动成败。骰子结果由引擎自动生成，叙事必须严格服从骰子结果，禁止编造反结果。
2. 成功程度定义：
   - 大成功(≥10高出DC或骰出20)：超额完成，有额外收益
   - 成功(≥5高出DC)：顺利完成
   - 勉强成功(≥0)：完成但有代价或瑕疵
   - 勉强失败(-1~-4)：失败但有机会补救
   - 失败(-5~-9)：明确失败，承担后果
   - 大失败(≤-10或骰出1)：灾难性后果

【当前游戏状态】
- 回合数: {self.state.turn_count}
- 玩家角色: {self.state.player['name']} ({self.state.player['role']})
- 玩家属性: {json.dumps(self.state.player['attributes'], ensure_ascii=False)}
- 持有物品: {', '.join(inv_names) or '无'}
- HP: {self.state.hp}/{self.state.max_hp}
- 资源: {json.dumps(self.state.resources, ensure_ascii=False) or '无'}
- 性格标签: {', '.join(self.state.player['tags']) or '暂无'}
- 知道的秘密: {', '.join(self.state.player['secrets']) or '暂无'}

【重要NPC】
{npcs_text}

【最近历史】
{recent_history}

【你的任务】
1. 根据当前状态生成一个引人入胜的场景（100-200字），包含冲突或抉择点
2. 生成4个剧情方向的选项(A/B/C/D)和1个自由选项(E)
   - A/B/C 必须有真实权衡，没有完美选择
   - D 选项是特殊路线，需要条件时才出现，且必有代价
3. 当收到玩家行动后，基于给定的 d20 检定结果生成叙事和状态变更(JSON)
"""

    def get_action_prompt(self, player_input: str, check_result: Optional[CheckResult] = None) -> str:
        """旧版接口：生成处理玩家行动的 prompt（新版内部已自动完成）。"""
        # 直接返回系统 prompt 的扩展版本，供外部 LLM 使用
        cr_text = ""
        if check_result:
            cr_text = (
                f"骰子结果: d20={check_result.roll}, 修正={check_result.modifier:+d}, "
                f"总计={check_result.total}, DC={check_result.dc}, 程度={check_result.degree}"
            )
        return f"{self.get_system_prompt()}\n\n【玩家行动】\n{player_input}\n{cr_text}\n\n请生成叙事与状态变更(JSON)。"

    def process_action(self, player_input: str, ai_response: Optional[Dict] = None) -> Dict:
        """
        旧版接口：处理玩家行动。
        新版中已内建 intent分析 → d20检定 → 叙事生成 → 应用后果 的完整链路，
        因此这里直接调用 process_turn 即可。
        """
        return self.process_turn(player_input)

    def load_game(self, save_id: str = None) -> bool:
        """加载存档，自动兼容旧版格式。"""
        # 先尝试新版统一存档：game.json
        game_dir = self._get_game_save_dir()
        filepath = os.path.join(game_dir, "game.json")
        
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # 新格式：包含 state 字段
            if "state" in data:
                data = self._migrate_legacy_save(data["state"])
                self.state = GameState.from_dict(data)
                if "game_id" in data:
                    self.game_id = data["game_id"]
                # 恢复NPC记忆
                if "npc_memories" in data:
                    self._restore_npc_memories(data["npc_memories"])
                return True
            else:
                # 旧格式直接保存的game.json
                data = self._migrate_legacy_save(data)
                self.state = GameState.from_dict(data)
                if "game_id" in data:
                    self.game_id = data["game_id"]
                return True
        
        # 回退到旧版按save_id加载
        if save_id:
            filepath = os.path.join(game_dir, f"{save_id}.json")
            if not os.path.exists(filepath):
                filepath = os.path.join(self.save_dir, f"{save_id}.json")
            if not os.path.exists(filepath):
                return False
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            data = self._migrate_legacy_save(data)
            self.state = GameState.from_dict(data)
            if "game_id" in data:
                self.game_id = data["game_id"]
            return True
        
        return False

    @staticmethod
    def _migrate_legacy_save(data: Dict) -> Dict:
        """将旧版 v3.x 富结构存档转换为新版 v4.x 扁平结构。"""
        # 如果已经是新版格式，补全 v4.5.0 新增字段
        if data.get("version", "").startswith("4."):
            if "hp" not in data:
                data["hp"] = 100
            if "max_hp" not in data:
                data["max_hp"] = 100
            if "resources" not in data:
                data["resources"] = {}
            if "status_effects" not in data:
                data["status_effects"] = []
            if "attribute_history" not in data:
                data["attribute_history"] = {}
            if "death_triggered" not in data:
                data["death_triggered"] = False
            if "money_per_turn" not in data:
                data["money_per_turn"] = 0
            # 补全NPC缺失字段（v4.5.0+完整关系系统）
            npcs = data.get("npcs", {})
            for name, npc in npcs.items():
                if not isinstance(npc, dict):
                    npcs[name] = {"relationship": 0, "attitude": "中立", "known_secrets": []}
                    npc = npcs[name]
                defaults = {
                    "relationship": 0, "attitude": "中立", "known_secrets": [],
                    "trust": 0, "fear": 0, "loyalty": 0, "affection": 0, "reputation": 0,
                    "interaction_count": 0, "first_met_turn": 0, "last_interaction_turn": 0, "memories": [],
                    "tags": [], "faction": "", "location": "", "status": "alive", "role": "", "description": ""
                }
                for k, v in defaults.items():
                    if k not in npc:
                        npc[k] = v
            return data

        # 旧版 normally 在 "player" -> "attributes" 下可能是结构化 dict
        player = data.get("player", {})
        raw_attrs = player.get("attributes", {})
        flat_attrs = {}
        for k, v in raw_attrs.items():
            if isinstance(v, dict) and "value" in v:
                flat_attrs[k] = v["value"]
            else:
                flat_attrs[k] = v

        # 将旧版中文属性名映射到新版通用维度（若存在）
        attr_mapping = {
            "武力": "FORCE",
            "力量": "FORCE",
            "智力": "MIND",
            "智慧": "MIND",
            "魅力": "INFLUENCE",
            "口才": "INFLUENCE",
            "敏捷": "REFLEX",
            "潜行": "REFLEX",
            "体质": "RESILIENCE",
            "意志": "RESILIENCE",
            "运气": "LUCK",
        }
        migrated_attrs = {}
        for k, v in flat_attrs.items():
            mk = attr_mapping.get(k, k)
            migrated_attrs[mk] = v

        # 确保6大维度都存在
        for dim in ["FORCE", "MIND", "INFLUENCE", "REFLEX", "RESILIENCE", "LUCK"]:
            if dim not in migrated_attrs:
                migrated_attrs[dim] = 10

        # 限制在 1-50
        for k in migrated_attrs:
            migrated_attrs[k] = max(1, min(50, int(migrated_attrs[k])))

        player["attributes"] = migrated_attrs

        # 历史记录：旧版可能是 dict，新版要求是 list
        hist = data.get("history", [])
        if isinstance(hist, dict):
            hist = hist.get("raw", [])
        data["history"] = hist

        # NPCs：旧版富结构 npc_database 需要扁平化
        npcs = data.get("npcs", {})
        if not npcs and "npc_database" in data:
            npcs = {}
            for npc_id, info in data["npc_database"].items():
                name = info.get("basic_info", {}).get("name", npc_id)
                matrix = info.get("relationship_matrix", {}).get("towards_player", {})
                trust_val = matrix.get("trust", {}).get("value", 5)
                respect = matrix.get("respect", {}).get("value", 5)
                fear_val = matrix.get("fear", {}).get("value", 0)
                relationship = (trust_val - 5) * 10 + (respect - 5) * 5 - fear_val * 5
                npcs[name] = {
                    "relationship": relationship,
                    "attitude": info.get("current_state", {}).get("mood", "中立"),
                    "known_secrets": info.get("knowledge_state", {}).get("secrets_known_by_player", []),
                    # 多维度情感映射
                    "trust": (trust_val - 5) * 20,  # 5->0, 10->100, 0->-100
                    "fear": fear_val * 20,  # 0->0, 5->100
                    "loyalty": (respect - 5) * 20,
                    "affection": (trust_val - 5) * 15,
                    "reputation": (respect - 5) * 20,
                    "interaction_count": 0,
                    "first_met_turn": 0,
                    "last_interaction_turn": 0,
                    "memories": [],
                    "tags": info.get("basic_info", {}).get("tags", []),
                    "faction": info.get("basic_info", {}).get("faction", ""),
                    "location": info.get("current_state", {}).get("location", ""),
                    "status": "alive",
                    "role": info.get("basic_info", {}).get("role", ""),
                    "description": info.get("basic_info", {}).get("description", "")
                }
            data["npcs"] = npcs

        # flags / story_flags 统一
        flags = data.get("flags", {})
        if "story_flags" in data:
            flags.update(data["story_flags"])
        data["flags"] = flags

        # 补全 v4.5.0 新增字段
        data["hp"] = 100
        data["max_hp"] = 100
        data["resources"] = {}
        data["status_effects"] = []
        data["attribute_history"] = {}
        data["death_triggered"] = False
        data["money_per_turn"] = 0

        # 补全NPC缺失字段（v4.5.0+完整关系系统）
        npcs = data.get("npcs", {})
        for name, npc in npcs.items():
            if not isinstance(npc, dict):
                npcs[name] = {"relationship": 0, "attitude": "中立", "known_secrets": []}
                npc = npcs[name]
            defaults = {
                "relationship": 0, "attitude": "中立", "known_secrets": [],
                "trust": 0, "fear": 0, "loyalty": 0, "affection": 0, "reputation": 0,
                "interaction_count": 0, "first_met_turn": 0, "last_interaction_turn": 0, "memories": [],
                "tags": [], "faction": "", "location": "", "status": "alive", "role": "", "description": ""
            }
            for k, v in defaults.items():
                if k not in npc:
                    npc[k] = v

        # 版本升级标记
        data["version"] = "4.5.0"
        return data

    # ------------------------------------------------------------------
    # 便捷：直接暴露 d20 给旧代码或 agent 脚本
    # ------------------------------------------------------------------

    def roll_check(self, attribute: str, dc: int, advantage: bool = False, disadvantage: bool = False) -> CheckResult:
        """
        显式执行一次 d20 检定，方便 agent 在外部调用。
        """
        attr_value = self.state.player["attributes"].get(attribute, 10)
        return self.d20.execute_check(
            attribute_value=attr_value,
            dc=dc,
            advantage=advantage,
            disadvantage=disadvantage,
        )

    # ------------------------------------------------------------------
    # 战术增强系统代理（v4.3.0）
    # ------------------------------------------------------------------

    def set_scene_objects(self, objects: List[Dict]) -> Dict:
        """代理到 WorldlineSkill.set_scene_objects"""
        return super().set_scene_objects(objects)

    def interact_with_scene_object(self, object_id: str, player_input: str) -> Dict:
        """代理到 WorldlineSkill.interact_with_scene_object"""
        return super().interact_with_scene_object(object_id, player_input)

    def execute_npc_check(self, npc_name: str, action: str, attribute: str, dc: int) -> Dict:
        """代理到 WorldlineSkill.execute_npc_check"""
        return super().execute_npc_check(npc_name, action, attribute, dc)

    def add_active_benefit(self, name: str, description: str, dc_modifier: int = 0,
                           advantage: bool = False, applies_to: Optional[List[str]] = None,
                           remaining_uses: int = 1) -> Dict:
        """代理到 WorldlineSkill.add_active_benefit"""
        return super().add_active_benefit(name, description, dc_modifier, advantage, applies_to, remaining_uses)

    def consume_active_benefit(self, name: str) -> Optional[Dict]:
        """代理到 WorldlineSkill.consume_active_benefit"""
        return super().consume_active_benefit(name)

    def get_active_benefits(self, filter_attribute: Optional[str] = None) -> List[Dict]:
        """代理到 WorldlineSkill.get_active_benefits"""
        return super().get_active_benefits(filter_attribute)

    def calculate_effective_dc(self, base_dc: int, attribute: str) -> Dict:
        """代理到 WorldlineSkill.calculate_effective_dc"""
        return super().calculate_effective_dc(base_dc, attribute)


# ============ CLI 兼容层 ============

class GameCLI:
    """向后兼容的 CLI 包装，实际代理到新版 cli_main。"""

    def __init__(self):
        self.engine = WorldlineEngine()

    def run(self, args: List[str]):
        """兼容旧版参数解析，然后启动新版 CLI 或命令。"""
        if len(args) < 1:
            self.show_help()
            return

        command = args[0]

        if command in ("--new", "-n"):
            world = args[1] if len(args) > 1 else input("请输入世界观设定: ")
            role = args[2] if len(args) > 2 else input("请输入你的角色身份: ")
            name = args[3] if len(args) > 3 else input("请输入角色名字: ")
            result = self.engine.start_game(world, role, name)
            print(f"\n{'='*50}")
            print(f"游戏开始: {result['world']}")
            print(f"游戏ID: {result['game_id']}")
            print(f"角色: {name} ({role})")
            print(f"属性: {json.dumps(result['player']['attributes'], ensure_ascii=False)}")
            print(f"\n新版引擎已启用 d20 检定系统 + 角色成长系统(v4.5.0)。")
            print(f"现在可以使用 process_turn() 或 generate_turn_options() 继续游戏。")

        elif command in ("--load", "-l"):
            if len(args) < 2:
                print("错误: 请指定存档ID")
                return
            save_id = args[1]
            if self.engine.load_game(save_id):
                print(f"已加载存档: {save_id}")
                print(f"当前游戏ID: {self.engine.game_id}")
                print(f"当前回合: {self.engine.state.turn_count}")
            else:
                print(f"存档不存在: {save_id}")

        elif command in ("--list", "-ls"):
            games = self.engine.list_games(self.engine.save_dir)
            if not games:
                print("暂无存档")
                return
            for g in games:
                print(f"  {g['game_id']} | {g['world_setting']} | {g['player_name']} | 回合{g['turn_count']}")

        elif command in ("--delete", "-d"):
            if len(args) < 2:
                print("错误: 请指定存档ID或游戏ID")
                return
            target = args[1]
            # 尝试删除游戏目录
            game_dir = os.path.join(self.engine.save_dir, target)
            if os.path.isdir(game_dir):
                import shutil
                shutil.rmtree(game_dir)
                print(f"已删除游戏目录: {target}")
                return
            # 回退到删除单个文件
            filepath = os.path.join(self.engine.save_dir, f"{target}.json")
            if os.path.exists(filepath):
                os.remove(filepath)
                print(f"已删除存档: {target}")
            else:
                print(f"存档不存在: {target}")

        elif command in ("--help", "-h"):
            self.show_help()

        else:
            # 默认：直接启动新版交互式 CLI
            print("启动新版交互式 CLI...")
            cli_main()

    def show_help(self):
        print("""
Worldline Choice - d20 检定版游戏引擎

用法:
  python3 worldline_engine.py [命令] [参数]

命令:
  --new, -n [世界观] [角色] [名字]  开始新游戏
  --load, -l <存档ID>              加载存档
  --list, -ls                      列出所有游戏
  --delete, -d <游戏ID/存档ID>     删除游戏或存档
  (无命令)                         启动交互式 CLI (带ABCDE选项 + d20检定)
        """)


def main():
    """主入口"""
    cli = GameCLI()
    cli.run(sys.argv[1:])


if __name__ == "__main__":
    main()
