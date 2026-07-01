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

    # 测试属性更新（v4.5.0：上限50，带历史审计）
    state.player["attributes"]["FORCE"] = 15
    state.update_attribute("FORCE", 3)
    assert state.player["attributes"]["FORCE"] == 18
    state.update_attribute("FORCE", 5)
    assert state.player["attributes"]["FORCE"] == 23
    # 测试上限50
    state.player["attributes"]["FORCE"] = 48
    state.update_attribute("FORCE", 5)
    assert state.player["attributes"]["FORCE"] == 50  # 上限截断
    state.update_attribute("FORCE", 5)
    assert state.player["attributes"]["FORCE"] == 50  # 保持上限
    # 测试下限1
    state.player["attributes"]["FORCE"] = 2
    state.update_attribute("FORCE", -5)
    assert state.player["attributes"]["FORCE"] == 1  # 下限截断
    state.update_attribute("FORCE", -5)
    assert state.player["attributes"]["FORCE"] == 1  # 保持下限
    print("✓ 属性更新正确（上限50，有边界限制）")

    # 测试属性历史审计
    state.update_attribute("MIND", 2, reason="灵光一闪")
    history = state.get_attribute_history("MIND")
    assert len(history) > 0
    assert history[-1]["change"] == 2
    assert history[-1]["reason"] == "灵光一闪"
    print("✓ 属性成长审计正确")

    # 测试物品管理（新版inventory）
    state.add_item("测试剑")
    assert any(it.get("name") == "测试剑" for it in state.player["inventory"]["items"])
    state.remove_item("测试剑")
    assert not any(it.get("name") == "测试剑" for it in state.player["inventory"]["items"])
    print("✓ 物品管理正确")

    # 测试背包容量和字典物品
    state.add_inventory_item({"id": "药草", "name": "药草", "type": "consumable", "quantity": 2})
    assert state.use_inventory_item("药草") is not None
    print("✓ 背包系统正确")

    # 测试HP
    state.update_hp(-20)
    assert state.hp == 80
    state.update_hp(200)
    assert state.hp == 100  # 上限截断
    print("✓ HP管理正确")

    # 测试资源
    state.update_resource("金币", 50)
    assert state.resources["金币"] == 50
    state.update_resource("金币", -100)
    assert state.resources["金币"] == 0  # 不允许负值
    print("✓ 资源管理正确")

    # 测试状态效果
    state.add_status_effect({"id": "中毒", "name": "中毒", "duration": 2, "effects": {"hp": -5}})
    assert len(state.status_effects) == 1
    tick = state.tick_status_effects()
    assert len(state.status_effects) == 1  # 还剩1轮
    tick2 = state.tick_status_effects()
    assert len(state.status_effects) == 0  # 已消退
    assert "中毒" in tick2.get("ticked", [])
    print("✓ 状态效果管理正确")

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
    assert new_state.hp == 100  # 因为之前 update_hp(200) 被截断到上限
    assert new_state.resources.get("金币") == 0
    assert len(new_state.player["inventory"]["items"]) == 1
    print("✓ 序列化/反序列化正确")

    # 测试旧版存档兼容迁移
    legacy_data = {
        "version": "4.4.1",
        "world_setting": "武侠",
        "player": {
            "name": "李逍遥",
            "role": "剑客",
            "attributes": {"FORCE": 12, "MIND": 14},
            "items": ["长剑", "酒壶"],
            "tags": [],
            "secrets": []
        },
        "history": [],
        "turn_count": 0,
        "flags": {}
    }
    migrated = GameState.from_dict(legacy_data)
    assert migrated.player["inventory"]["items"][0]["name"] == "长剑"
    assert migrated.hp == 100  # 补全默认值
    print("✓ 旧版存档兼容迁移正确")

    print("✓ 游戏状态管理测试通过\n")


def test_skill_integration():
    """测试Skill集成"""
    print("="*60)
    print("测试3: Skill集成（无LLM模式）")
    print("="*60)

    skill = WorldlineSkill(show_dice=True)

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

    # 测试存档（v4.5.0：游戏目录隔离，新格式game.json）
    save_path = skill.save_game()
    assert os.path.exists(save_path)
    assert skill.game_id in save_path
    assert save_path.endswith("game.json")
    print(f"✓ 存档功能正确（路径: {save_path}）")

    # 测试读档
    new_skill = WorldlineSkill()
    # 需要手动设置 game_id 才能加载
    new_skill.game_id = skill.game_id
    assert new_skill.load_game()
    assert new_skill.state.world_setting == "赛博朋克"
    assert new_skill.state.turn_count == 4
    print("✓ 读档功能正确")

    # 清理
    import shutil
    game_dir = os.path.join(skill.save_dir, skill.game_id)
    if os.path.exists(game_dir):
        shutil.rmtree(game_dir)
    print("✓ 存档隔离正确")

    print("✓ Skill集成测试通过\n")


def test_openclaw_adapter():
    """测试OpenClaw适配器"""
    print("="*60)
    print("测试4: OpenClaw适配器")
    print("="*60)

    adapter = create_skill(mock_llm_call, show_dice=True)

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

    adapter = create_skill(mock_llm_call, show_dice=True)
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
        failure_keywords = ["失败", "灾难", "差一点", "差点", "没成功", "没能"]
        assert any(kw in narrative for kw in failure_keywords), \
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
        adapter = create_skill(mock_llm_call, show_dice=True)
        adapter.start_game(world, role, "测试者")
        turn = adapter.process_turn(action)

        assert "check" in turn
        assert "narrative" in turn
        print(f"✓ {world}: {action[:20]}... -> {turn['check']['degree']}")

    print("✓ 多世界观通用性测试通过\n")


def test_turn_options():
    """测试ABCD预定义选项 + E自由选项"""
    print("="*60)
    print("测试7: 回合选项系统")
    print("="*60)

    skill = WorldlineSkill(show_dice=True)
    skill.start_game("武侠", "剑客", "测试者")

    # 测试选项生成
    options = skill.generate_turn_options()
    assert options is not None
    assert len(options.options) == 4  # A/B/C/D

    # 检查选项结构
    for opt in options.options:
        assert opt.letter in ["A", "B", "C", "D"]
        assert opt.description
        assert opt.action
        print(f"  {opt.letter}. {opt.description} [{opt.attr_hint}] (DC{opt.dc_hint})")

    # 检查E选项
    assert options.free_text.letter == "E"
    assert options.free_text.description
    print(f"  E. {options.free_text.description}")

    print("✓ 选项生成正确")

    # 测试选择A选项
    result = skill.process_option(options, "A")
    assert "check" in result
    assert "narrative" in result
    print(f"✓ 选择A处理正确 (结果: {result['check']['degree']})")

    # 测试选择E选项（自由输入）
    options2 = skill.generate_turn_options()
    result2 = skill.process_option(options2, "E", "我尝试用轻功飞上屋顶")
    assert "check" in result2
    assert "narrative" in result2
    print(f"✓ 选择E（自由输入）处理正确 (结果: {result2['check']['degree']})")

    # 测试无效选项
    result3 = skill.process_option(options, "Z")
    assert "error" in result3
    print("✓ 无效选项处理正确")

    # 测试选择E但不提供输入
    result4 = skill.process_option(options, "E")
    assert "error" in result4
    print("✓ 选择E无输入时错误提示正确")

    print("✓ 回合选项系统测试通过\n")


def test_openclaw_options():
    """测试OpenClaw适配器的选项接口"""
    print("="*60)
    print("测试8: OpenClaw选项接口")
    print("="*60)

    adapter = create_skill(mock_llm_call, show_dice=True)
    adapter.start_game("奇幻", "法师", "测试者")

    # 测试生成选项
    options_dict = adapter.generate_turn_options()
    assert "options" in options_dict
    assert "free_text" in options_dict
    assert len(options_dict["options"]) == 4
    print("✓ OpenClaw generate_turn_options 正确")

    # 测试处理选项
    result = adapter.process_option("B")
    assert "check" in result
    print(f"✓ OpenClaw process_option 正确 (选择B: {result['check']['degree']})")

    # 测试处理E选项
    result2 = adapter.process_option("E", "我施放火球术")
    assert "check" in result2
    print(f"✓ OpenClaw process_option E 正确 (结果: {result2['check']['degree']})")

    print("✓ OpenClaw选项接口测试通过\n")


def test_growth_system():
    """测试角色成长系统（v4.5.0）"""
    print("="*60)
    print("测试9: 角色成长系统")
    print("="*60)

    skill = WorldlineSkill(show_dice=True)
    skill.start_game("武侠", "剑客", "李逍遥")

    # 测试初始状态
    assert skill.state.hp == 100
    assert skill.state.max_hp == 100
    # 金钱系统初始化后 resources 可能包含世界观启动资金
    assert "金币" in skill.state.resources or skill.state.resources == {}
    assert skill.state.attribute_history == {}
    print("✓ 初始状态正确")

    # 测试属性升级（带截断）
    base_force = skill.state.player["attributes"]["FORCE"]
    skill.state.update_attribute("FORCE", 3, "战斗训练")
    assert skill.state.player["attributes"]["FORCE"] == base_force + 3
    assert len(skill.state.get_attribute_history("FORCE")) == 1
    print("✓ 属性升级正确")

    # 测试单轮上限截断
    base_mind = skill.state.player["attributes"]["MIND"]
    skill.state.update_attribute("MIND", 10, "过度升级")
    # 实际只增加5（上限截断）
    assert skill.state.player["attributes"]["MIND"] == base_mind + 5
    print("✓ 单轮变化上限截断正确")

    # 测试上限50
    skill.state.player["attributes"]["LUCK"] = 10
    for _ in range(20):
        skill.state.update_attribute("LUCK", 5, "刷属性")
    assert skill.state.player["attributes"]["LUCK"] == 50
    print("✓ 属性上限50正确")

    # 测试死亡检测
    skill.state.hp = 5
    skill.state.death_triggered = False
    # 施加一个致命状态（暂停HP衰减，避免体质恢复导致测试不稳定）
    skill.state.add_status_effect({
        "id": "致命伤", "duration": 1,
        "effects": {"hp": -10},
        "pause_hp_decay": True
    })
    settlement = skill.settle_turn()
    assert settlement["death_triggered"] == True
    assert skill.state.death_triggered == True
    assert skill.state.hp == 0
    print("✓ 死亡检测正确")

    print("✓ 角色成长系统测试通过\n")


def test_settlement():
    """测试回合结算机制（v4.5.0）"""
    print("="*60)
    print("测试10: 回合结算机制")
    print("="*60)

    skill = WorldlineSkill(show_dice=True)
    skill.start_game("武侠", "剑客", "测试者")

    # 测试状态效果tick
    skill.state.add_status_effect({"id": "疲惫", "duration": 2, "effects": {"attributes": {"FORCE": -2}}})
    skill.state.add_status_effect({"id": "激励", "duration": 1, "effects": {"attributes": {"MIND": 3}}})
    settlement1 = skill.settle_turn()
    assert "激励" in settlement1.get("ticked_effects", [])
    assert "疲惫" not in settlement1.get("ticked_effects", [])
    assert len(skill.state.status_effects) == 1
    print("✓ 状态效果tick正确")

    # 测试第二回合：疲惫消退
    settlement2 = skill.settle_turn()
    assert "疲惫" in settlement2.get("ticked_effects", [])
    assert len(skill.state.status_effects) == 0
    print("✓ 状态效果完全消退正确")

    # 测试体质联动HP
    skill.state.hp = 50
    skill.state.player["attributes"]["RESILIENCE"] = 16
    settlement3 = skill.settle_turn()
    assert settlement3["auto_hp_change"] == 1
    assert skill.state.hp == 51
    print("✓ 高体质HP恢复正确")

    skill.state.player["attributes"]["RESILIENCE"] = 4
    settlement4 = skill.settle_turn()
    assert settlement4["auto_hp_change"] == -1
    assert skill.state.hp == 50
    print("✓ 低体质HP衰减正确")

    # 测试暂停HP衰减
    skill.state.add_status_effect({"id": "护盾", "duration": 1, "effects": {}, "pause_hp_decay": True})
    settlement5 = skill.settle_turn()
    assert settlement5["auto_hp_change"] == 0
    print("✓ 暂停HP衰减正确")

    # 测试effective_attributes
    skill.state.player["attributes"]["FORCE"] = 10
    skill.state.add_status_effect({"id": "狂暴", "duration": 1, "effects": {"attributes": {"FORCE": 5}}})
    settlement6 = skill.settle_turn()
    assert settlement6["effective_attributes"]["FORCE"] == 15
    print("✓ 有效属性计算正确")

    print("✓ 回合结算机制测试通过\n")


def test_directory_isolation():
    """测试游戏目录隔离（v4.5.0）"""
    print("="*60)
    print("测试11: 游戏目录隔离")
    print("="*60)

    import shutil

    # 创建两个游戏
    skill1 = WorldlineSkill()
    skill1.start_game("武侠", "剑客", "玩家1")
    skill1.save_game()
    skill1.process_turn("测试行动")

    skill2 = WorldlineSkill()
    skill2.start_game("科幻", "宇航员", "玩家2")
    skill2.save_game()
    skill2.process_turn("探索星球")

    # 验证目录存在
    assert skill1.game_id is not None
    assert skill2.game_id is not None
    assert skill1.game_id != skill2.game_id
    print(f"✓ 游戏ID生成正确: {skill1.game_id}, {skill2.game_id}")

    # 验证目录结构
    dir1 = os.path.join(skill1.save_dir, skill1.game_id)
    dir2 = os.path.join(skill2.save_dir, skill2.game_id)
    assert os.path.isdir(dir1)
    assert os.path.isdir(dir2)
    assert os.path.exists(os.path.join(dir1, "game.json"))
    assert os.path.exists(os.path.join(dir2, "game.json"))
    print("✓ 游戏目录结构正确")

    # 验证 list_games
    games = WorldlineSkill.list_games(skill1.save_dir)
    game_ids = [g["game_id"] for g in games]
    assert skill1.game_id in game_ids
    assert skill2.game_id in game_ids
    print("✓ list_games 正确")

    # 验证隔离性：读取 skill1 的存档不应影响 skill2
    new_skill = WorldlineSkill()
    new_skill.game_id = skill1.game_id
    new_skill.load_game("game")
    assert new_skill.state.world_setting == "武侠"
    assert new_skill.state.player["name"] == "玩家1"
    print("✓ 存档隔离正确")

    # 清理
    for skill in [skill1, skill2]:
        d = os.path.join(skill.save_dir, skill.game_id)
        if os.path.exists(d):
            shutil.rmtree(d)

    print("✓ 游戏目录隔离测试通过\n")


def test_npc_relationship_system():
    """测试完整NPC关系系统（v4.5.0）"""
    print("="*60)
    print("测试12: NPC关系系统")
    print("="*60)

    skill = WorldlineSkill(show_dice=True)
    skill.start_game("武侠", "剑客", "李逍遥")

    # 测试1: 初始化完整NPC结构
    skill.state.update_npc("店小二", relationship=10, attitude="友善", role="客栈伙计")
    npc = skill.state.npcs["店小二"]
    assert npc["relationship"] == 10
    assert npc["attitude"] == "友善"
    assert npc["role"] == "客栈伙计"
    # 检查所有新字段自动初始化
    assert npc["trust"] == 0
    assert npc["fear"] == 0
    assert npc["loyalty"] == 0
    assert npc["affection"] == 0
    assert npc["reputation"] == 0
    assert npc["interaction_count"] == 0
    assert npc["memories"] == []
    assert npc["tags"] == []
    assert npc["faction"] == ""
    assert npc["location"] == ""
    assert npc["status"] == "alive"
    assert npc["description"] == ""
    print("✓ 完整NPC结构初始化正确")

    # 测试2: 通过 update_npc 更新多个维度
    skill.state.update_npc("店小二", trust=15, fear=5, loyalty=10, affection=8, reputation=12)
    npc = skill.state.npcs["店小二"]
    assert npc["trust"] == 15
    assert npc["fear"] == 5
    assert npc["loyalty"] == 10
    print("✓ 多维度情感更新正确")

    # 测试3: 添加记忆
    skill.state.add_npc_memory("店小二", "玩家给了小费", "positive")
    assert len(skill.state.npcs["店小二"]["memories"]) == 1
    assert skill.state.npcs["店小二"]["memories"][0]["event"] == "玩家给了小费"
    assert skill.state.npcs["店小二"]["memories"][0]["type"] == "positive"
    print("✓ 记忆添加正确")

    # 测试4: get_npc_summary
    summary = skill.state.get_npc_summary("店小二")
    assert summary["name"] == "店小二"
    assert summary["trust"] == 15
    assert summary["recent_memories"][0]["event"] == "玩家给了小费"
    print("✓ NPC摘要正确")

    # 测试5: 通过 consequences 应用完整关系变化
    skill.state.turn_count = 5
    skill._apply_consequences({
        "npc_relationship_changes": {
            "店小二": {
                "relationship": 5,
                "trust": 3,
                "fear": -2,
                "memories": [{"event": "玩家出手相助", "type": "positive"}]
            }
        }
    })
    npc = skill.state.npcs["店小二"]
    assert npc["relationship"] == 15  # 10+5
    assert npc["trust"] == 18  # 15+3
    assert npc["fear"] == 3  # 5-2
    assert npc["interaction_count"] == 1
    assert npc["last_interaction_turn"] == 5
    assert len(npc["memories"]) == 2
    print("✓ consequences 完整关系变化正确")

    # 测试6: 旧版 relationship_changes 向后兼容
    skill._apply_consequences({
        "relationship_changes": {"店小二": 3}
    })
    assert skill.state.npcs["店小二"]["relationship"] == 18  # 15+3
    assert skill.state.npcs["店小二"]["interaction_count"] == 2
    print("✓ 旧版 relationship_changes 向后兼容")

    # 测试7: 边界限制（-100~100）
    skill.state.npcs["店小二"]["trust"] = 95
    skill._apply_consequences({
        "npc_relationship_changes": {"店小二": {"trust": 10}}
    })
    assert skill.state.npcs["店小二"]["trust"] == 100  # 被截断
    print("✓ 边界限制正确")

    # 测试8: 旧存档加载自动补全NPC字段
    old_save = {
        "version": "4.5.0",
        "world_setting": "测试",
        "player": {"name": "", "role": "", "attributes": {}, "tags": [], "secrets": []},
        "npcs": {
            "老王": {"relationship": 5, "attitude": "中立"}
        }
    }
    old_state = GameState.from_dict(old_save)
    assert old_state.npcs["老王"]["trust"] == 0
    assert old_state.npcs["老王"]["fear"] == 0
    assert old_state.npcs["老王"]["memories"] == []
    assert old_state.npcs["老王"]["status"] == "alive"
    print("✓ 旧存档NPC字段自动补全正确")

    # 测试9: 记忆压缩（超过10条后，最早5条压缩为1条）
    skill2 = WorldlineSkill(show_dice=True)
    skill2.start_game("武侠", "剑客", "李逍遥")
    # 添加12条记忆，触发压缩（>10，最早5条→1条摘要）
    for i in range(12):
        mtype = "positive" if i % 3 == 0 else "negative" if i % 3 == 1 else "neutral"
        skill2.state.add_npc_memory("掌柜", f"事件{i+1}", mtype)
    mems = skill2.state.npcs["掌柜"]["memories"]
    assert len(mems) == 8, f"压缩后应为8条(1摘要+7详细)，实际{len(mems)}"
    assert mems[0]["type"] == "compressed", f"第1条应为摘要，实际是{mems[0]['type']}"
    assert mems[0].get("compressed_count") == 5, f"摘要应压缩5条，实际{mems[0].get('compressed_count')}"
    assert "事件6" in mems[1]["event"], f"第2条应为事件6，实际是{mems[1]['event']}"
    print("✓ 记忆压缩正确（12条→1摘要+7详细=8条）")

    # 再添加10条，总计22条，应再次触发压缩
    for i in range(10):
        skill2.state.add_npc_memory("掌柜", f"额外事件{i+1}", "positive")
    mems = skill2.state.npcs["掌柜"]["memories"]
    assert len(mems) == 10, f"最终应为10条，实际{len(mems)}"
    compressed_count = sum(1 for m in mems if m.get("type") == "compressed")
    assert compressed_count >= 1, f"应至少有1条摘要，实际{compressed_count}"
    print(f"✓ 多次记忆压缩正确（22条→{compressed_count}摘要+{10-compressed_count}详细=10条）")

    print("✓ NPC关系系统测试通过\n")


def test_dc_calibration():
    """测试DC重新校准（2-7简单/8-12中等/13-17困难）"""
    print("="*60)
    print("测试13: DC校准")
    print("="*60)

    skill = WorldlineSkill(show_dice=True)
    skill.start_game("武侠", "剑客", "李逍遥")

    # 测试回退分析DC值
    result = skill.llm._default_analysis("走路去市场", skill.state)
    assert 2 <= result["base_dc"] <= 7, f"通用行动DC={result['base_dc']} 不在简单范围(2-7)"
    print(f"✓ 通用行动DC={result['base_dc']}（简单范围）")

    result = skill.llm._default_analysis("talk to someone", skill.state)
    assert 2 <= result["base_dc"] <= 7, f"简单社交DC={result['base_dc']} 不在简单范围(2-7)"
    print(f"✓ 简单社交DC={result['base_dc']}（简单范围）")

    result = skill.llm._default_analysis("persuade the guard", skill.state)
    assert 8 <= result["base_dc"] <= 12, f"说服陌生人DC={result['base_dc']} 不在中等范围(8-12)"
    print(f"✓ 说服陌生人DC={result['base_dc']}（中等范围）")

    result = skill.llm._default_analysis("fight enemy", skill.state)
    assert 8 <= result["base_dc"] <= 12, f"战斗DC={result['base_dc']} 不在中等范围(8-12)"
    print(f"✓ 战斗DC={result['base_dc']}（中等范围）")

    result = skill.llm._default_analysis("hide from guards", skill.state)
    assert 8 <= result["base_dc"] <= 12, f"潜行DC={result['base_dc']} 不在中等范围(8-12)"
    print(f"✓ 潜行DC={result['base_dc']}（中等范围）")

    # 测试默认选项DC范围
    options = skill.llm._default_options(skill.state)
    dc_values = [opt.get("dc_hint", 0) for opt in options.get("options", [])]
    assert all(2 <= dc <= 17 for dc in dc_values), f"有选项DC超出范围: {dc_values}"
    # 至少一个简单选项
    assert any(dc <= 7 for dc in dc_values), f"没有简单选项(DC≤7): {dc_values}"
    # 至少一个中等选项
    assert any(8 <= dc <= 10 for dc in dc_values), f"没有中等选项(DC 8-10): {dc_values}"
    print(f"✓ 默认选项DC范围正确: {dc_values}，含简单选项和中等选项")

    print("✓ DC校准测试通过\n")


def test_save_load_format():
    """测试新存档格式（game.json + events + npc_memories）"""
    print("="*60)
    print("测试14: 新存档格式")
    print("="*60)

    import json
    import os

    skill = WorldlineSkill(show_dice=True)
    skill.start_game("武侠", "剑客", "李逍遥")

    # 添加一些NPC和事件
    skill.state.update_npc("店小二", relationship=10, trust=15)
    skill.state.add_npc_memory("店小二", "给了小费", "positive")
    
    # 执行几个回合产生事件
    for i in range(3):
        skill.process_turn(f"测试行动{i+1}")

    # 保存
    save_path = skill.save_game()
    assert save_path.endswith("game.json"), f"存档路径不以game.json结尾: {save_path}"
    print(f"✓ 保存路径正确: {save_path}")

    # 检查存档内容
    with open(save_path, 'r', encoding='utf-8') as f:
        save_data = json.load(f)

    assert "state" in save_data, "新存档缺少state字段"
    assert "events" not in save_data, "新存档不应包含冗余events字段"
    assert "npc_memories" not in save_data, "新存档不应包含冗余npc_memories字段"
    assert "saved_at" in save_data, "新存档缺少saved_at字段"
    print("✓ 新存档格式字段完整（无冗余）")

    # 检查state.history（事件存储在state内部）
    history = save_data["state"]["history"]
    assert len(history) >= 3, f"历史记录数量不足: {len(history)}"
    print(f"✓ 历史记录正确: {len(history)}条")

    # 检查state.npcs（NPC记忆存储在state内部）
    npcs = save_data["state"]["npcs"]
    assert "店小二" in npcs, "NPC数据中缺少店小二"
    assert len(npcs["店小二"]["memories"]) == 1, "NPC记忆数量不对"
    print("✓ NPC记忆存储正确")

    # 加载
    new_skill = WorldlineSkill()
    new_skill.game_id = skill.game_id
    assert new_skill.load_game(), "加载失败"
    assert new_skill.state.world_setting == "武侠"
    assert "店小二" in new_skill.state.npcs
    assert new_skill.state.npcs["店小二"]["trust"] == 15
    print("✓ 加载恢复正确")

    print("✓ 新存档格式测试通过\n")


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
        test_turn_options()
        test_openclaw_options()
        test_growth_system()
        test_settlement()
        test_directory_isolation()
        test_npc_relationship_system()
        test_dc_calibration()
        test_save_load_format()

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
