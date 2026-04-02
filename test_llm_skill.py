#!/usr/bin/env python3
"""
Worldline Skill 测试套件
测试LLM驱动 + d20检定的混合架构
"""

import json
import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from worldline_skill import WorldlineSkill, D20Engine, GameState
from openclaw_adapter import create_skill, mock_llm_call


def test_d20_engine():
    """测试d20检定系统的客观性"""
    print("="*60)
    print("测试1: d20检定系统")
    print("="*60)

    engine = D20Engine()

    # 测试修正值计算
    assert engine.calculate_modifier(10) == 0
    assert engine.calculate_modifier(14) == 2
    assert engine.calculate_modifier(8) == -1
    print("✓ 修正值计算正确")

    # 测试检定执行（多次运行验证随机性）
    results = []
    for _ in range(100):
        result = engine.execute_check(attribute_value=12, dc=15)
        results.append(result.success)

    success_rate = sum(results) / len(results)
    print(f"✓ 100次检定成功率: {success_rate:.2%} (期望约45-55%)")

    # 测试优势/劣势
    adv_results = [engine.execute_check(12, 15, advantage=True).roll for _ in range(50)]
    dis_results = [engine.execute_check(12, 15, disadvantage=True).roll for _ in range(50)]
    print(f"✓ 优势平均骰子: {sum(adv_results)/len(adv_results):.1f}")
    print(f"✓ 劣势平均骰子: {sum(dis_results)/len(dis_results):.1f}")

    print("✓ d20检定系统测试通过\n")


def test_game_state():
    """测试游戏状态管理"""
    print("="*60)
    print("测试2: 游戏状态管理")
    print("="*60)

    state = GameState()
    state.world_setting = "测试世界"
    state.player["name"] = "测试者"
    state.player["attributes"]["FORCE"] = 15

    # 测试属性更新
    state.update_attribute("FORCE", 3)
    assert state.player["attributes"]["FORCE"] == 18
    state.update_attribute("FORCE", 5)  # 超过上限会被截断
    assert state.player["attributes"]["FORCE"] == 20
    print("✓ 属性更新正确（有边界限制）")

    # 测试物品管理
    state.add_item("测试剑")
    assert "测试剑" in state.player["items"]
    state.remove_item("测试剑")
    assert "测试剑" not in state.player["items"]
    print("✓ 物品管理正确")

    # 测试NPC关系
    state.update_npc("村长", relationship=20)
    assert state.npcs["村长"]["relationship"] == 20
    print("✓ NPC关系管理正确")

    # 测试历史记录
    state.add_history("测试行动", {"result": "success"})
    assert state.turn_count == 1
    print("✓ 历史记录正确")

    # 测试序列化
    data = state.to_dict()
    new_state = GameState.from_dict(data)
    assert new_state.world_setting == "测试世界"
    assert new_state.player["name"] == "测试者"
    print("✓ 序列化/反序列化正确")

    print("✓ 游戏状态管理测试通过\n")


def test_skill_integration():
    """测试Skill集成"""
    print("="*60)
    print("测试3: Skill集成（无LLM模式）")
    print("="*60)

    skill = WorldlineSkill()

    # 测试游戏初始化
    result = skill.start_game("赛博朋克", "黑客", "V")
    assert result["initialized"]
    assert skill.state.world_setting == "赛博朋克"
    print("✓ 游戏初始化正确")

    # 测试回合处理（使用默认回退逻辑）
    turn = skill.process_turn("我尝试入侵系统")
    assert "check" in turn
    assert "narrative" in turn
    assert turn["turn"] == 1
    print(f"✓ 回合处理正确 (检定: {turn['check']['degree']})")

    # 测试多个回合
    for i in range(3):
        turn = skill.process_turn("继续探索")
        assert turn["turn"] == i + 2
    print("✓ 多回合处理正确")

    # 测试存档
    save_path = skill.save_game("test_save")
    assert os.path.exists(save_path)
    print("✓ 存档功能正确")

    # 测试读档
    new_skill = WorldlineSkill()
    assert new_skill.load_game("test_save")
    assert new_skill.state.world_setting == "赛博朋克"
    assert new_skill.state.turn_count == 4
    print("✓ 读档功能正确")

    # 清理
    os.remove(save_path)

    print("✓ Skill集成测试通过\n")


def test_openclaw_adapter():
    """测试OpenClaw适配器"""
    print("="*60)
    print("测试4: OpenClaw适配器")
    print("="*60)

    adapter = create_skill(mock_llm_call)

    # 测试游戏开始
    result = adapter.start_game("奇幻", "法师", "甘道夫")
    assert result["initialized"]
    print("✓ 适配器游戏初始化正确")

    # 测试行动分析
    analysis = adapter.analyze_action("我释放火球术")
    assert "intention" in analysis
    assert "base_dc" in analysis
    print(f"✓ 行动分析正确 (DC: {analysis['base_dc']})")

    # 测试检定执行
    check = adapter.execute_check("MIND", 15)
    assert "roll" in check
    assert "degree" in check
    print(f"✓ 检定执行正确 (结果: {check['degree']})")

    # 测试叙事生成
    narrative = adapter.generate_narrative(
        action="释放火球术",
        intention="攻击敌人",
        check_result=check,
        world_setting="奇幻"
    )
    assert "narrative" in narrative
    assert "consequences" in narrative
    print("✓ 叙事生成正确")

    # 测试完整回合
    turn = adapter.process_turn("我尝试说服国王")
    assert "check" in turn
    assert "narrative" in turn
    print(f"✓ 完整回合处理正确 (检定: {turn['check']['degree']})")

    print("✓ OpenClaw适配器测试通过\n")


def test_llm_d20_separation():
    """
    测试关键架构要求：
    1. LLM不做判定，只提供配置
    2. d20做客观判定
    3. LLM基于骰子结果生成叙事
    """
    print("="*60)
    print("测试5: LLM与d20分离验证")
    print("="*60)

    adapter = create_skill(mock_llm_call)
    adapter.start_game("测试世界", "测试者", "玩家")

    # 运行多次回合，验证：
    # 1. 检定的随机性（不是固定的）
    # 2. 叙事与检定结果匹配

    degrees = set()
    for _ in range(10):
        turn = adapter.process_turn("测试行动")
        degrees.add(turn["check"]["degree"])

    print(f"✓ 10次回合产生的结果类型: {degrees}")
    assert len(degrees) > 1, "检定应该有随机性"

    # 验证叙事基于骰子结果
    turn = adapter.process_turn("另一个测试")
    check = turn["check"]
    narrative = turn["narrative"]

    # 如果骰子失败，叙事不应该描述成功
    if not check["success"]:
        assert "失败" in narrative or "灾难" in narrative or "问题" in narrative, \
            f"失败检定应该有失败叙事: {narrative}"
        print("✓ 失败检定的叙事正确反映失败")

    print("✓ LLM与d20分离验证通过\n")


def test_multi_world_settings():
    """测试多世界观支持（验证LLM驱动的通用性）"""
    print("="*60)
    print("测试6: 多世界观通用性")
    print("="*60)

    worlds = [
        ("武侠", "剑客", "一剑刺向敌人"),
        ("赛博朋克", "黑客", "hack the system"),
        ("克苏鲁", "调查员", "调查神秘符号"),
        ("现代都市", "侦探", "分析监控录像"),
    ]

    for world, role, action in worlds:
        adapter = create_skill(mock_llm_call)
        adapter.start_game(world, role, "测试者")
        turn = adapter.process_turn(action)

        assert "check" in turn
        assert "narrative" in turn
        print(f"✓ {world}: {action[:20]}... -> {turn['check']['degree']}")

    print("✓ 多世界观通用性测试通过\n")


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*60)
    print("Worldline Skill 完整测试套件")
    print("="*60 + "\n")

    try:
        test_d20_engine()
        test_game_state()
        test_skill_integration()
        test_openclaw_adapter()
        test_llm_d20_separation()
        test_multi_world_settings()

        print("="*60)
        print("✓ 所有测试通过!")
        print("="*60)
        return True

    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n✗ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
