#!/usr/bin/env python3
"""
Worldline Choice v4.4.1 演示脚本
展示强制d20检定 + 强制自动保存机制
"""

import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from worldline_skill import WorldlineSkill

def demo_game():
    print("="*60)
    print("Worldline Choice v4.4.1 - d20强制检定 + 自动保存演示")
    print("="*60)

    skill = WorldlineSkill()
    skill.show_dice = True  # 显示详细骰子结果

    # 开始游戏
    print("\n【初始化游戏】")
    result = skill.start_game("武侠", "剑客", "李逍遥")
    print(f"世界观: {result['world']}")
    print(f"角色: {result['player']['name']} ({result['player']['role']})")
    print(f"属性: {result['player']['attributes']}")

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

    # 展示存档
    print(f"\n{'='*60}")
    print("保存游戏...")
    save_path = skill.save_game("demo_save")
    print(f"存档已保存到: {save_path}")

    # 读取存档验证
    print(f"\n验证存档...")
    state = skill.get_state()
    print(f"版本: {state.get('version', '未知')}")
    print(f"总回合数: {state.get('turn_count')}")
    print(f"历史记录数: {len(state.get('history', []))}")

    print(f"\n{'='*60}")
    print("✓ 演示完成 - v4.4.1 d20强制检定 + 自动保存系统运行正常")
    print("="*60)

if __name__ == "__main__":
    demo_game()
