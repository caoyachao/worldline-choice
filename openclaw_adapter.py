#!/usr/bin/env python3
"""
OpenClaw适配器
连接WorldlineSkill与OpenClaw的LLM调用机制
"""

import json
from typing import Dict, Callable, Optional
from worldline_skill import WorldlineSkill, GameState, NarrativeContext


class OpenClawAdapter:
    """
    OpenClaw适配器
    将WorldlineSkill封装为OpenClaw可调用的形式
    """

    def __init__(self, llm_call: Callable[[str, str], str], auto_save: bool = True, show_dice: bool = False):
        """
        Args:
            llm_call: OpenClaw提供的LLM调用函数
                     签名: fn(prompt: str, format: str) -> str
            auto_save: 是否每回合自动存档（默认True）
            show_dice: 是否显示骰子结果（默认False）
        """
        self.llm_call = llm_call
        self.skill = WorldlineSkill(llm_callback=self._llm_callback, auto_save=auto_save, show_dice=show_dice)

    def _llm_callback(self, prompt: str, response_format: str) -> Dict:
        """
        内部LLM回调，适配OpenClaw接口
        """
        try:
            # 调用OpenClaw提供的LLM
            response = self.llm_call(prompt, response_format)

            # 解析JSON响应
            if response_format == "json":
                # 处理可能的Markdown代码块
                if "```json" in response:
                    response = response.split("```json")[1].split("```")[0]
                elif "```" in response:
                    response = response.split("```")[1].split("```")[0]

                return json.loads(response.strip())
            else:
                return {"content": response}

        except Exception as e:
            # 回退到默认响应
            return {
                "error": str(e),
                "fallback": True,
                "intention": "未知意图",
                "action_type": "通用",
                "primary_attribute": "MIND",
                "base_dc": 10,
                "dc_reasoning": "使用默认配置",
                "risks": ["失败"],
                "required_items": [],
                "required_knowledge": []
            }

    # ============ OpenClaw工具接口 ============

    def start_game(self, world_setting: str, player_role: str,
                   player_name: str, world_description: str = "") -> Dict:
        """开始新游戏"""
        return self.skill.start_game(world_setting, player_role,
                                      player_name, world_description)

    def process_turn(self, player_input: str) -> Dict:
        """处理游戏回合"""
        return self.skill.process_turn(player_input)

    def analyze_action(self, action: str) -> Dict:
        """仅分析行动，不执行"""
        # 临时创建分析
        from worldline_skill import LLMDriver
        llm = LLMDriver(self._llm_callback)
        analysis = llm.analyze_action(action, self.skill.state)
        return analysis.to_dict()

    def execute_check(self, attribute: str, dc: int,
                      advantage: bool = False, disadvantage: bool = False) -> Dict:
        """执行d20检定"""
        from worldline_skill import D20Engine

        attr_value = self.skill.state.player["attributes"].get(attribute, 10)
        result = D20Engine.execute_check(
            attribute_value=attr_value,
            dc=dc,
            advantage=advantage,
            disadvantage=disadvantage
        )
        return result.to_dict()

    def generate_narrative(self, action: str, intention: str,
                          check_result: Dict, world_setting: str) -> Dict:
        """生成叙事"""
        from worldline_skill import NarrativeContext, CheckResult, LLMDriver

        # 重建CheckResult
        cr = CheckResult(**check_result)

        ctx = NarrativeContext(
            action=action,
            intention=intention,
            check_result=cr,
            world_setting=world_setting,
            scene_description=self.skill.state.current_scene,
            player_name=self.skill.state.player["name"]
        )

        llm = LLMDriver(self._llm_callback)
        return llm.generate_narrative(ctx)

    def generate_turn_options(self, previous_result: Optional[Dict] = None) -> Dict:
        """生成本回合的ABCD预定义选项 + E自由选项"""
        options = self.skill.generate_turn_options(previous_result)
        return options.to_dict()

    def process_option(self, choice: str, free_text: Optional[str] = None) -> Dict:
        """处理玩家选择的选项"""
        # 先获取当前选项
        options = self.skill.generate_turn_options()
        return self.skill.process_option(options, choice, free_text)

    def save_game(self, save_id: str) -> Dict:
        """保存游戏"""
        path = self.skill.save_game(save_id)
        return {"saved": True, "path": path}

    def load_game(self, save_id: str) -> Dict:
        """加载游戏"""
        success = self.skill.load_game(save_id)
        return {"loaded": success, "state": self.skill.get_state() if success else None}

    def get_game_state(self) -> Dict:
        """获取游戏状态"""
        return self.skill.get_state()


# ============ OpenClaw运行时入口 ============

def create_skill(llm_call: Callable[[str, str], str], auto_save: bool = True, show_dice: bool = False) -> OpenClawAdapter:
    """
    OpenClaw调用的工厂函数

    Usage:
        skill = create_skill(openclaw_llm_call)
        result = skill.process_turn("我尝试说服守卫")

    Args:
        llm_call: OpenClaw提供的LLM调用函数
        auto_save: 是否每回合自动存档（默认True）
        show_dice: 是否显示骰子结果（默认False，后台静默投骰）
    """
    return OpenClawAdapter(llm_call, auto_save=auto_save, show_dice=show_dice)


# ============ 测试用模拟LLM ============

def mock_llm_call(prompt: str, format: str) -> str:
    """
    模拟LLM调用，用于测试
    """
    # 根据prompt内容返回模拟响应
    if "分析玩家行动" in prompt or "分析这个行动" in prompt:
        return json.dumps({
            "intention": "尝试进行一般行动",
            "action_type": "通用",
            "primary_attribute": "MIND",
            "base_dc": 12,
            "dc_reasoning": "一般难度",
            "risks": ["失败"],
            "required_items": [],
            "required_knowledge": []
        }, ensure_ascii=False)

    elif "生成叙事" in prompt or "基于骰子结果" in prompt:
        # 从prompt中提取骰子结果 - 精确匹配
        degree = "成功"
        if "结果程度: 大成功" in prompt:
            degree = "大成功"
        elif "结果程度: 大失败" in prompt:
            degree = "大失败"
        elif "结果程度: 勉强成功" in prompt:
            degree = "勉强成功"
        elif "结果程度: 勉强失败" in prompt:
            degree = "勉强失败"
        elif "结果程度: 失败" in prompt:
            degree = "失败"

        templates = {
            "大成功": "你完美地完成了行动，效果超出预期！",
            "成功": "你顺利地完成了行动。",
            "勉强成功": "你完成了行动，但过程有些惊险。",
            "勉强失败": "你差一点就成功了。",
            "失败": "你的行动失败了。",
            "大失败": "灾难！你的行动彻底失败。"
        }

        return json.dumps({
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
        }, ensure_ascii=False)

    elif "生成本回合" in prompt or "预定义选项" in prompt or "回合选项" in prompt:
        # 返回剧情化的模拟选项
        return json.dumps({
            "context": "你站在岔路口，前方传来争吵声和金属碰撞的声音。空气中弥漫着紧张的气息...",
            "options": [
                {
                    "letter": "A",
                    "description": "握紧武器，大步走向声音来源",
                    "action": "毫不畏惧地走向声音来源，准备面对任何危险",
                    "dc_hint": 14,
                    "attr_hint": "FORCE"
                },
                {
                    "letter": "B",
                    "description": "躲进阴影，先观察情况",
                    "action": "悄悄躲进附近的阴影中，仔细观察声音来源和周围情况",
                    "dc_hint": 12,
                    "attr_hint": "REFLEX"
                },
                {
                    "letter": "C",
                    "description": "大声喊话，试图阻止冲突",
                    "action": "朝声音方向喊话，试图制止冲突并表明自己的存在",
                    "dc_hint": 16,
                    "attr_hint": "INFLUENCE"
                },
                {
                    "letter": "D",
                    "description": "绕路避开，不想惹麻烦",
                    "action": "悄悄绕行，避开声音来源，寻找其他安全的道路",
                    "dc_hint": 13,
                    "attr_hint": "MIND"
                }
            ],
            "free_text": {
                "description": "自定义行动（描述你想做的其他事情）"
            }
        }, ensure_ascii=False)

    return json.dumps({"content": "模拟响应"})


if __name__ == "__main__":
    # 测试运行
    print("测试OpenClaw适配器...")

    adapter = create_skill(mock_llm_call)

    # 开始游戏
    result = adapter.start_game("武侠", "剑客", "测试者")
    print(f"游戏初始化: {result}")

    # 处理回合
    turn = adapter.process_turn("我尝试与店小二交谈")
    print(f"回合结果:")
    print(f"  意图: {turn.get('intention')}")
    print(f"  检定: {turn.get('check')}")
    print(f"  叙事: {turn.get('narrative', '')[:50]}...")
