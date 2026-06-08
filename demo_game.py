#!/usr/bin/env python3
"""
Worldline Choice v4.5.0 演示脚本
展示 d20强制检定 + 自动保存 + 回合结算（HP/金钱/状态效果）
"""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from worldline_skill import WorldlineSkill

def demo_game():
    print("="*60)
    print("Worldline Choice v4.5.0 - d20强制检定 + 自动保存 + 回合结算演示")
    print("="*60)

    skill = WorldlineSkill()
    skill.show_dice = True  # 显示详细骰子结果

    # 开始游戏
    print("\n【初始化游戏】")
    result = skill.start_game("武侠", "剑客", "李逍遥")
    print(f"世界观: {result['world']}")
    print(f"角色: {result['player']['name']} ({result['player']['role']})")
    print(f"属性: {result['player']['attributes']}")
    print(f"初始金币: {skill.state.resources.get('金币', 0)}")
    print(f"每回合金钱变化: {skill.state.money_per_turn:+d}")

    # 模拟几个回合
    actions = [
        "我握紧长剑，大步走向声音来源",
        "我躲进阴影中观察情况",
        "我尝试说服对方放我过去",
    ]

    for i, action in enumerate(actions, 1):
        print(f"\n{'='*60}")
        print(f"回合 {i}")
        print(f"行动: {action}")
        print("-"*60)

        # 执行回合 - 内部会自动调用execute_check
        result = skill.process_turn(action)

        if "error" in result:
            print(f"错误: {result['error']}")
            continue

        # 展示d20检定结果
        check = result.get('check', {})
        print(f"\n🎲 【d20检定结果】")
        print(f"   意图: {result.get('intention', '未知')}")
        print(f"   骰子: d20 = {check.get('roll')}")
        print(f"   修正: {check.get('modifier', 0):+d}")
        print(f"   总计: {check.get('total')} vs DC {check.get('dc')}")
        print(f"   结果: 【{check.get('degree')}】")

        # 展示叙事
        print(f"\n📖 【叙事】")
        print(f"{result.get('narrative', '无叙事')}")

        # 展示状态变更
        consequences = result.get('consequences', {})
        if any(consequences.values()):
            print(f"\n📝 【状态变更】")
            if consequences.get('attribute_changes'):
                print(f"   属性变化: {consequences['attribute_changes']}")
            if consequences.get('items_gained'):
                print(f"   获得物品: {consequences['items_gained']}")
            if consequences.get('tags_gained'):
                print(f"   获得标签: {consequences['tags_gained']}")

        # 展示结算信息
        settlement = result.get('settlement', {})
        if settlement.get('money_change') != 0:
            print(f"💰 金钱结算: {settlement['money_change']:+d} 金币 (当前: {skill.state.resources.get('金币', 0)})")
        if settlement.get('auto_hp_change') != 0:
            print(f"❤️ HP自动变化: {settlement['auto_hp_change']:+d} (当前: {skill.state.hp}/{skill.state.max_hp})")
        if settlement.get('ticked_effects'):
            print(f"🌡️ 状态效果消退: {', '.join(settlement['ticked_effects'])}")

    # 展示NPC关系系统
    print(f"\n{'='*60}")
    print("【NPC关系系统演示】")
    print("="*60)

    skill.state.update_npc("店小二", relationship=10, attitude="友善", role="客栈伙计",
                           trust=15, loyalty=5, faction="客栈联盟", location="悦来客栈")
    skill.state.add_npc_memory("店小二", "玩家慷慨给了赏钱", "positive")
    skill.state.add_npc_memory("店小二", "玩家帮他赶走闹事者", "positive")

    print(f"\n与店小二的关系：")
    summary = skill.state.get_npc_summary("店小二")
    print(f"  总体关系: {summary['relationship']}")
    print(f"  信任度: {summary['trust']}")
    print(f"  忠诚度: {summary['loyalty']}")
    print(f"  态度: {summary['attitude']}")
    print(f"  阵营: {summary['faction']}")
    print(f"  互动次数: {summary['interaction_count']}")
    print(f"  最近记忆:")
    for mem in summary['recent_memories']:
        print(f"    - [{mem['type']}] {mem['event']} (回合{mem['turn']})")

    # 保存并展示完整存档
    print(f"\n保存并展示存档...")
    save_path = skill.save_game("demo_save")
    print(f"存档已保存到: {save_path}")

    # 读取存档验证
    print(f"\n验证存档...")
    state = skill.get_state()
    print(f"版本: {state.get('version', '未知')}")
    print(f"总回合数: {state.get('turn_count')}")
    print(f"历史记录数: {len(state.get('history', []))}")
    print(f"当前金币: {state.get('resources', {}).get('金币', 0)}")
    print(f"每回合金钱变化: {state.get('money_per_turn', 0):+d}")
    print(f"NPC数量: {len(state.get('npcs', {}))}")
    if state.get('npcs'):
        for name, npc in state['npcs'].items():
            print(f"  - {name}: 关系{npc.get('relationship', 0)}, 信任{npc.get('trust', 0)}, 记忆{npc.get('memories', [])}")

    print(f"\n{'='*60}")
    print("✓ 演示完成 - v4.5.0 d20强制检定 + 自动保存 + 回合结算 + NPC关系系统运行正常")
    print("="*60)

if __name__ == "__main__":
    demo_game()
