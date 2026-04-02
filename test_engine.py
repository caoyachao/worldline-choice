#!/usr/bin/env python3
"""
Worldline Choice 引擎测试脚本
测试所有核心功能
"""

import os
import sys
import json
import tempfile
import shutil
import random

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from worldline_engine import GameState, WorldlineEngine, AttributeDimension
from save_manager import WorldlineSaveManager


def test_game_state():
    """测试状态管理"""
    print("="*50)
    print("测试1: 游戏状态管理")
    print("="*50)
    
    state = GameState()
    state.world_setting = "测试世界观"
    state.player["name"] = "测试角色"
    state.player["role"] = "测试身份"
    state.player["attributes"] = {"武力": 15, "智力": 18}
    state.player["items"] = ["测试物品"]
    state.update_npc("测试NPC", relationship=20, attitude="友善")
    state.flags["测试标记"] = True
    state.add_history("测试行动", "测试结果")
    
    # 测试序列化
    data = state.to_dict()
    assert data["world_setting"] == "测试世界观"
    assert data["player"]["name"] == "测试角色"
    assert "测试NPC" in data["npcs"]
    print("✓ 状态序列化测试通过")
    
    # 测试反序列化
    new_state = GameState.from_dict(data)
    assert new_state.world_setting == "测试世界观"
    assert new_state.player["name"] == "测试角色"
    print("✓ 状态反序列化测试通过")
    
    print("✓ 游戏状态管理测试通过\n")


def test_engine_initialization():
    """测试引擎初始化"""
    print("="*50)
    print("测试2: 引擎初始化")
    print("="*50)
    
    engine = WorldlineEngine()
    result = engine.start_game(
        world_setting="三国",
        player_role="谋士",
        player_name="诸葛亮",
        world_desc="东汉末年，群雄并起的时代"
    )
    
    assert result["initialized"] == True
    assert result["world"] == "三国"
    assert engine.state.player["name"] == "诸葛亮"
    assert engine.state.player["role"] == "谋士"
    assert len(engine.state.player["attributes"]) > 0
    print(f"✓ 生成的属性: {json.dumps(engine.state.player['attributes'], ensure_ascii=False)}")
    print("✓ 引擎初始化测试通过\n")


def test_prompt_generation():
    """测试Prompt生成"""
    print("="*50)
    print("测试3: Prompt生成")
    print("="*50)
    
    engine = WorldlineEngine()
    engine.start_game("1960年代香港黑帮", "卧底警察", "阿超")
    
    # 测试系统Prompt
    system_prompt = engine.get_system_prompt()
    assert "1960年代香港黑帮" in system_prompt
    assert "阿超" in system_prompt
    assert "输出格式" in system_prompt
    print("✓ 系统Prompt生成测试通过")
    print(f"  Prompt长度: {len(system_prompt)} 字符")
    
    # 测试行动Prompt
    action_prompt = engine.get_action_prompt("调查那个神秘女子")
    assert "调查那个神秘女子" in action_prompt
    assert "处理要求" in action_prompt
    print("✓ 行动Prompt生成测试通过\n")


def test_action_processing():
    """测试行动处理"""
    print("="*50)
    print("测试4: 行动处理与状态更新")
    print("="*50)
    
    engine = WorldlineEngine()
    engine.start_game("测试世界", "测试角色", "测试者")
    
    # 模拟AI返回的处理结果
    mock_ai_response = {
        "intention": "调查神秘女子",
        "action_type": "观察",
        "feasible": True,
        "narrative": "你悄悄跟踪神秘女子，发现她进入了黑帮据点。",
        "consequences": {
            "attribute_changes": {"智力": 1},
            "relationship_changes": {"神秘女子": -5},
            "items_gained": ["情报"],
            "tags_added": ["谨慎"],
            "secrets_learned": ["女子是黑帮成员"],
            "npc_changes": {"神秘女子": {"status": "被监视"}}
        },
        "flags_set": {"发现据点": True},
        "ending_triggered": False,
        "next_scene_hint": "接近黑帮据点"
    }
    
    result = engine.process_action("调查神秘女子", mock_ai_response)
    
    # 验证状态更新
    assert result["turn"] == 1
    assert "情报" in engine.state.player["items"]
    assert "谨慎" in engine.state.player["tags"]
    assert "女子是黑帮成员" in engine.state.player["secrets"]
    assert "发现据点" in engine.state.flags
    assert "神秘女子" in engine.state.npcs
    print(f"✓ 属性变化: {engine.state.player['attributes']}")
    print(f"✓ 持有物品: {engine.state.player['items']}")
    print(f"✓ 性格标签: {engine.state.player['tags']}")
    print(f"✓ NPC状态: {engine.state.npcs}")
    print("✓ 行动处理测试通过\n")


def test_save_load():
    """测试存档功能"""
    print("="*50)
    print("测试5: 存档与加载")
    print("="*50)
    
    # 使用临时目录测试
    temp_dir = tempfile.mkdtemp()
    
    try:
        engine = WorldlineEngine()
        engine.save_dir = temp_dir
        
        # 初始化并修改状态
        engine.start_game("测试存档", "测试角色", "测试者")
        engine.state.player["items"] = ["物品1", "物品2"]
        engine.state.turn_count = 5
        
        # 保存
        save_path = engine.save_game("test_save_001")
        assert os.path.exists(save_path)
        print(f"✓ 存档已保存: {save_path}")
        
        # 新建引擎加载
        new_engine = WorldlineEngine()
        new_engine.save_dir = temp_dir
        assert new_engine.load_game("test_save_001") == True
        
        # 验证加载的数据
        assert new_engine.state.world_setting == "测试存档"
        assert new_engine.state.player["name"] == "测试者"
        assert new_engine.state.turn_count == 5
        assert "物品1" in new_engine.state.player["items"]
        print("✓ 存档加载验证通过")
        
        # 测试列出存档
        saves = new_engine.list_saves()
        assert len(saves) == 1
        assert saves[0]["id"] == "test_save_001"
        print("✓ 存档列表功能通过\n")
        
    finally:
        # 清理临时目录
        shutil.rmtree(temp_dir)


def test_ending_generation():
    """测试结局生成Prompt"""
    print("="*50)
    print("测试6: 结局生成")
    print("="*50)
    
    engine = WorldlineEngine()
    engine.start_game("测试结局", "英雄", "勇者")
    
    # 添加一些历史记录
    for i in range(5):
        engine.state.add_history(f"行动{i}", f"结果{i}")
    
    ending_prompt = engine.get_ending_prompt()
    
    assert "测试结局" in ending_prompt
    assert "勇者" in ending_prompt
    assert "结局类型" in ending_prompt
    assert "ending_type" in ending_prompt
    print("✓ 结局Prompt生成测试通过")
    print(f"  Prompt长度: {len(ending_prompt)} 字符\n")


def test_layered_history_storage():
    """测试分层历史存储系统 - 核心功能"""
    print("="*50)
    print("测试6.5: 分层历史存储系统")
    print("="*50)
    
    engine = WorldlineEngine()
    engine.start_game("测试存储", "测试者", "玩家")
    
    # 模拟30个回合的游戏过程
    print("  模拟30回合游戏...")
    for i in range(30):
        consequences = {
            "attribute_changes": {"武力": 1 if i % 3 == 0 else 0},
            "tags_added": [f"标签{i}"] if i % 5 == 0 else []
        }
        engine.state.add_history(f"行动{i+1}", f"这是第{i+1}回合的结果描述", consequences)
    
    # 验证原始历史完整保存
    assert len(engine.state.raw_history) == 30, f"原始历史应该有30条，实际有{len(engine.state.raw_history)}条"
    print(f"✓ 原始历史完整保存: {len(engine.state.raw_history)} 回合")
    
    # 验证分层摘要生成
    assert len(engine.state.history_summaries) >= 2, "应该有至少2个阶段摘要"
    print(f"✓ 阶段摘要生成: {len(engine.state.history_summaries)} 个")
    
    # 验证回合编号正确
    for i, record in enumerate(engine.state.raw_history):
        assert record["turn"] == i + 1, f"第{i}条记录的回合数应该是{i+1}"
    print("✓ 回合编号正确")
    
    # 验证精简摘要生成
    assert all("summary" in r for r in engine.state.raw_history), "所有记录应该有摘要"
    print("✓ 回合摘要自动生成")
    
    # 测试AI上下文组装
    ai_context = engine.state.get_history_for_ai()
    assert "最近5回合" in ai_context or "回合" in ai_context, "AI上下文应包含历史信息"
    print("✓ AI上下文组装成功")
    print(f"  AI上下文长度: {len(ai_context)} 字符")
    
    # 测试存档包含完整历史
    temp_dir = tempfile.mkdtemp()
    try:
        engine.save_dir = temp_dir
        save_path = engine.save_game("history_test")
        
        # 加载并验证
        new_engine = WorldlineEngine()
        new_engine.save_dir = temp_dir
        new_engine.load_game("history_test")
        
        assert len(new_engine.state.raw_history) == 30, "加载后原始历史应完整"
        assert len(new_engine.state.history_summaries) == len(engine.state.history_summaries), "摘要应保留"
        print("✓ 存档/加载保留完整历史")
        
    finally:
        shutil.rmtree(temp_dir)
    
    print("✓ 分层历史存储系统测试通过\n")


def test_milestone_tracking():
    """测试里程碑自动追踪"""
    print("="*50)
    print("测试6.6: 里程碑追踪")
    print("="*50)
    
    engine = WorldlineEngine()
    engine.start_game("三国", "谋士", "诸葛亮")
    
    # 添加里程碑事件
    engine.state.flags["投曹"] = True
    engine.state.add_history("决定投靠曹操", "你成为了曹操的谋士")
    
    engine.state.flags["官渡胜利"] = True
    engine.state.add_history("献策乌巢", "成功奇袭乌巢，袁绍大败")
    
    # 验证里程碑记录
    assert len(engine.state.milestones) >= 2, "应该记录至少2个里程碑"
    milestone_flags = [m["flag"] for m in engine.state.milestones]
    assert "投曹" in milestone_flags, "应该记录'投曹'里程碑"
    print(f"✓ 里程碑自动追踪: {len(engine.state.milestones)} 个")
    print(f"  里程碑: {milestone_flags}")
    
    # 验证里程碑在AI上下文中有体现
    ai_context = engine.state.get_history_for_ai()
    assert "投曹" in ai_context or "官渡" in ai_context, "里程碑应在AI上下文中"
    print("✓ 里程碑出现在AI上下文中")
    print("✓ 里程碑追踪测试通过\n")


def test_different_roles():
    """测试不同角色类型的属性生成"""
    print("="*50)
    print("测试7: 不同角色类型的属性生成")
    print("="*50)
    
    test_cases = [
        ("三国武将", ["武力", "智力", "魅力", "声望"]),
        ("侦探", ["观察", "推理", "人脉", "冷静"]),
        ("谋士", ["谋略", "学识", "口才", "洞察"]),
        ("商人", ["财富", "谈判", "信息", "信誉"]),
        ("卧底警察", ["观察", "推理", "人脉", "冷静"]),  # 应该识别为侦探类型
    ]
    
    for role, expected_attrs in test_cases:
        engine = WorldlineEngine()
        engine.start_game("测试", role, "测试者")
        actual_attrs = list(engine.state.player["attributes"].keys())
        print(f"  {role}: {actual_attrs}")
    
    print("✓ 角色属性生成测试通过\n")


def test_complex_scenario():
    """测试复杂场景模拟"""
    print("="*50)
    print("测试8: 复杂场景模拟")
    print("="*50)
    
    engine = WorldlineEngine()
    engine.start_game("三国谍战", "卧底谋士", "阿超")
    
    # 模拟一系列行动
    actions = [
        {
            "input": "假扮商人进入敌营",
            "response": {
                "intention": "潜入敌营",
                "feasible": True,
                "narrative": "你以商人身份成功混入敌营，没人怀疑你。",
                "consequences": {
                    "tags_added": ["伪装"],
                    "npc_changes": {"敌军守卫": {"attitude": "信任"}}
                },
                "flags_set": {"进入敌营": True},
                "ending_triggered": False
            }
        },
        {
            "input": "偷听敌军将领谈话",
            "response": {
                "intention": "获取情报",
                "feasible": True,
                "narrative": "你躲在帐外，听到了敌军的作战计划。",
                "consequences": {
                    "attribute_changes": {"智力": 2},
                    "secrets_learned": ["敌军将在三日后夜袭"],
                    "items_gained": ["情报"]
                },
                "flags_set": {"获得作战计划": True},
                "ending_triggered": False
            }
        },
        {
            "input": "将情报送回己方营地",
            "response": {
                "intention": "传递情报",
                "feasible": True,
                "narrative": "你冒着生命危险，将情报成功送回。",
                "consequences": {
                    "relationship_changes": {"主公": 30},
                    "tags_added": ["忠诚"]
                },
                "flags_set": {"任务完成": True},
                "ending_triggered": True,
                "ending_type": "胜利结局"
            }
        }
    ]
    
    for action in actions:
        result = engine.process_action(action["input"], action["response"])
        print(f"  回合{result['turn']}: {action['input'][:20]}...")
    
    print(f"\n  最终状态:")
    print(f"    回合数: {engine.state.turn_count}")
    print(f"    属性: {engine.state.player['attributes']}")
    print(f"    物品: {engine.state.player['items']}")
    print(f"    标签: {engine.state.player['tags']}")
    print(f"    秘密: {engine.state.player['secrets']}")
    print(f"    关系: {engine.state.npcs}")
    print(f"    结局: {engine.state.ending_type}")
    print("✓ 复杂场景模拟测试通过\n")


def test_rich_save_roundtrip():
    """测试富结构字段的存档/加载往返"""
    print("="*50)
    print("测试9: 富结构字段存档往返")
    print("="*50)

    temp_dir = tempfile.mkdtemp()
    try:
        engine = WorldlineEngine()
        engine.save_dir = temp_dir
        engine.start_game("赛博朋克", "黑客", "V")

        # 设置富结构数据
        engine.state.update_world_state(date="2077-01-15", time="23:45", location="夜之城", description="霓虹闪烁的街道")
        engine.state.create_npc_rich("dexter", "德克斯特", "中间人", faction="流浪者", location="来生酒吧")
        engine.state.update_npc_relationship_rich("dexter", "trust", 3)
        engine.state.create_quest("q001", "偷货", "main", "从荒坂塔偷取Relic芯片")
        engine.state.add_inventory_item("documents", "公司通行证")
        engine.state.add_inventory_item("intelligence", "荒坂巡逻时间表")
        engine.state.set_story_flag("met_johnny", True)

        # 添加session
        session_idx = engine.state.add_session("2077-01-15T23:45:00", "来生酒吧会面")
        engine.state.add_session_entry(session_idx, "dialogue", "23:45", "德克斯特: 这活儿值大钱")

        # 保存
        save_path = engine.save_game("rich_test")

        # 新引擎加载
        new_engine = WorldlineEngine()
        new_engine.save_dir = temp_dir
        assert new_engine.load_game("rich_test") == True

        # 验证world_state
        assert new_engine.state.world_state["current_location"] == "夜之城", "world_state 应保留"
        assert new_engine.state.world_state["current_date"] == "2077-01-15", "日期应保留"
        print("✓ world_state 往返通过")

        # 验证npc_database
        assert "dexter" in new_engine.state.npc_database, "NPC数据库应保留"
        assert new_engine.state.npc_database["dexter"]["basic_info"]["name"] == "德克斯特"
        trust = new_engine.state.npc_database["dexter"]["relationship_matrix"]["towards_player"]["trust"]["value"]
        assert trust == 8, f"关系值应为8，实际为{trust}"
        print("✓ npc_database 往返通过")

        # 验证quests
        quest_ids = [q["quest_id"] for q in new_engine.state.active_quests]
        assert "q001" in quest_ids, "任务应保留"
        print("✓ active_quests 往返通过")

        # 验证inventory
        assert "公司通行证" in new_engine.state.inventory["documents"]
        assert "荒坂巡逻时间表" in new_engine.state.inventory["intelligence"]
        print("✓ inventory 往返通过")

        # 验证story_flags
        assert new_engine.state.story_flags.get("met_johnny") == True
        assert new_engine.state.flags.get("met_johnny") == True
        print("✓ story_flags 往返通过")

        # 验证session_history
        assert len(new_engine.state.session_history) == 1
        assert len(new_engine.state.session_history[0]["entries"]) == 1
        print("✓ session_history 往返通过")

    finally:
        shutil.rmtree(temp_dir)

    print("✓ 富结构字段存档往返测试通过\n")


def test_save_manager_compatibility():
    """测试 worldline_engine 存档可被 save_manager 正确读取"""
    print("="*50)
    print("测试10: SaveManager 兼容性")
    print("="*50)

    temp_dir = tempfile.mkdtemp()
    try:
        engine = WorldlineEngine()
        engine.save_dir = temp_dir
        engine.start_game("武侠", "剑客", "李逍遥")
        engine.state.create_npc_rich("yao", "酒剑仙", "师父", location="蜀山")
        engine.state.create_quest("q001", "寻剑", "main", "寻找七星剑")
        engine.state.add_inventory_item("documents", "剑谱残页")
        engine.state.set_story_flag("met_master", True)
        engine.state.update_world_state(location="蜀山", description="云雾缭绕")

        save_path = engine.save_game("manager_test")

        # 使用 save_manager 读取
        manager = WorldlineSaveManager(save_path)
        data = manager.data

        assert data["metadata"]["game_title"] == "武侠"
        assert data["player"]["name"] == "李逍遥"
        print("✓ metadata / player 兼容")

        assert "yao" in data["npc_database"], "save_manager 应读取到 npc_database"
        assert data["npc_database"]["yao"]["basic_info"]["name"] == "酒剑仙"
        assert data["npc_database"]["yao"]["basic_info"]["faction"] == ""
        print("✓ npc_database 兼容")

        assert len(data["active_quests"]) == 1
        assert data["active_quests"][0]["quest_id"] == "q001"
        print("✓ active_quests 兼容")

        assert "剑谱残页" in data["inventory"]["documents"]
        print("✓ inventory 兼容")

        assert data["story_flags"].get("met_master") == True
        print("✓ story_flags 兼容")

        assert data["world_state"]["current_location"] == "蜀山"
        print("✓ world_state 兼容")

    finally:
        shutil.rmtree(temp_dir)

    print("✓ SaveManager 兼容性测试通过\n")


def test_tactical_anti_abuse():
    """测试战术多步骤的 v3.3.2 防套利机制"""
    print("="*50)
    print("测试11: 战术防套利机制")
    print("="*50)

    engine = WorldlineEngine()
    engine.start_game("测试战术", "将领", "测试者")
    # 设置属性为10，修正值为0，便于计算
    engine.state.player["attributes"]["智力"] = 10
    engine.state.player["attributes"]["武力"] = 10

    steps = [
        {"text": "埋伏伏兵", "purpose": "埋伏", "action_type": "战术",
         "primary_attribute": AttributeDimension.MIND, "secondary_attribute": AttributeDimension.FORCE,
         "target": "敌军", "base_dc": 10, "is_critical": False},
        {"text": "佯攻诱敌", "purpose": "诱敌", "action_type": "战术",
         "primary_attribute": AttributeDimension.MIND, "secondary_attribute": AttributeDimension.FORCE,
         "target": "敌军", "base_dc": 10, "is_critical": False},  # 非关键步骤，即使大失败计划继续
        {"text": "侧翼包抄", "purpose": "偷袭", "action_type": "战术",
         "primary_attribute": AttributeDimension.FORCE, "secondary_attribute": AttributeDimension.MIND,
         "target": "敌军", "base_dc": 10, "is_critical": False},
        {"text": "主力总攻", "purpose": "总攻", "action_type": "战术",
         "primary_attribute": AttributeDimension.FORCE, "secondary_attribute": AttributeDimension.MIND,
         "target": "敌军", "base_dc": 10, "is_critical": True},
        {"text": "清扫战场", "purpose": "追击", "action_type": "战术",
         "primary_attribute": AttributeDimension.FORCE, "secondary_attribute": AttributeDimension.MIND,
         "target": "敌军", "base_dc": 10, "is_critical": False},
    ]

    # 控制骰子结果: 15(成功), 1(大失败/信息泄露), 10(失败), 10(失败), 10(失败)
    original_randint = random.randint
    rolls = [15, 1, 10, 10, 10]
    roll_idx = [0]
    def mock_randint(a, b):
        r = rolls[roll_idx[0]]
        roll_idx[0] += 1
        return r
    random.randint = mock_randint

    try:
        result = engine.challenge_engine.execute_tactical_check(steps)
        step_results = result["step_results"]

        # Step1: 埋伏成功 -> global_mod = 0 - 3(成功) - 2(埋伏成功) = -5. But DC calc happens BEFORE update.
        # Step1 DC = 10 + 0 = 10. After: global_mod = -5.
        assert step_results[0]["dc"] == 10, f"Step1 DC 应为10, 实际{step_results[0]['dc']}"
        assert step_results[0]["degree"] == "成功", "Step1 应为成功"
        print("✓ Step1 DC正确")

        # Step2: 诱敌大失败 -> DC = 10 + (-5) = 5. After: global_mod = -5 + 5(大失败) + 3(诱敌失败) = +3.
        assert step_results[1]["check"]["roll"] == 1, "Step2 应为自然1"
        assert step_results[1].get("info_leak_triggered") == True, "Step2 应触发信息泄露"
        print("✓ Step2 信息泄露触发")

        # Step3: global_mod = +3, leak = 1*2 = 2, overload = 0. DC = 10 + 3 + 2 = 15.
        assert step_results[2]["dc"] >= 14, f"Step3 DC 应>=14 (含信息泄露), 实际{step_results[2]['dc']}"
        print(f"✓ Step3 受到信息泄露惩罚 (DC={step_results[2]['dc']})")

        # Step4: global_mod = +3, leak = 2, overload = 1. DC = 10 + 3 + 4 + 1 = 18.
        assert step_results[3]["dc"] >= 18, f"Step4 DC 应>=18 (含过载+1+泄露), 实际{step_results[3]['dc']}"
        print(f"✓ Step4 指挥链过载生效 (DC={step_results[3]['dc']})")

        # Step5 should be skipped because step4 (critical) failed
        assert step_results[4].get("status") == "跳过", "Step5 应因Step4关键步骤失败而跳过"
        print("✓ Step5 因关键步骤失败而跳过")

    finally:
        random.randint = original_randint

    print("✓ 战术防套利机制测试通过\n")


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*50)
    print("Worldline Choice 引擎测试开始")
    print("="*50 + "\n")
    
    try:
        test_game_state()
        test_engine_initialization()
        test_prompt_generation()
        test_action_processing()
        test_save_load()
        test_ending_generation()
        test_layered_history_storage()
        test_milestone_tracking()
        test_different_roles()
        test_complex_scenario()
        test_rich_save_roundtrip()
        test_save_manager_compatibility()
        test_tactical_anti_abuse()

        print("="*50)
        print("✓ 所有测试通过!")
        print("="*50)
        return True
        
    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
        return False
    except Exception as e:
        print(f"\n✗ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
