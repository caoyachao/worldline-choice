#!/usr/bin/env python3
"""
Worldline Choice Dice Roller v3.3.2
严格d20检定系统 - 真实随机数生成
"""

import random
import json
import sys
from datetime import datetime

def roll_d20():
    """生成1-20的真实随机数"""
    return random.randint(1, 20)

def calculate_modifier(attribute_value):
    """计算属性加值: (属性-10)/2 向下取整"""
    return (attribute_value - 10) // 2

def determine_result(roll, total, dc):
    """
    判定结果等级
    自然20必成功，自然1必失败
    
    参数:
        roll: 原始d20骰值 (1-20)
        total: 总值 (roll + modifier)
        dc: 难度等级
    """
    if roll == 20:
        return "critical_success", "自然20大成功"
    if roll == 1:
        return "critical_failure", "自然1大失败"
    
    difference = total - dc
    
    if difference >= 10:
        return "great_success", "大成功"
    elif difference >= 5:
        return "success", "成功"
    elif difference >= 0:
        return "marginal_success", "勉强成功"
    elif difference >= -4:
        return "marginal_failure", "勉强失败"
    elif difference >= -9:
        return "failure", "失败"
    else:
        return "great_failure", "大失败"

def calculate_next_dc_modifier(result_type):
    """
    计算对后续步骤的DC影响 (v3.3.2 防套利机制)
    """
    modifiers = {
        "critical_success": -5,
        "great_success": -5,
        "success": -3,
        "marginal_success": -1,  # 勉强成功仅-1 (补丁A)
        "marginal_failure": 0,
        "failure": 5,
        "great_failure": 5,
        "critical_failure": 5  # 大失败可能触发信息泄露
    }
    return modifiers.get(result_type, 0)

def execute_check(attribute_value, dc, attribute_name="未知", context=""):
    """
    执行一次d20检定
    
    参数:
        attribute_value: 属性值 (如13)
        dc: 难度等级 (如15)
        attribute_name: 属性名称 (用于记录)
        context: 检定场景描述
    
    返回:
        JSON格式的检定结果
    """
    roll = roll_d20()
    modifier = calculate_modifier(attribute_value)
    total = roll + modifier
    
    result_type, result_desc = determine_result(roll, total, dc)
    
    # 重新计算以确定是否成功
    is_success = total >= dc
    
    # 计算对后续步骤的影响
    next_dc_modifier = calculate_next_dc_modifier(result_type)
    
    # 检查是否信息泄露 (大失败)
    info_leak = result_type in ["critical_failure", "great_failure"]
    
    result = {
        "timestamp": datetime.now().isoformat(),
        "check": {
            "attribute": attribute_name,
            "attribute_value": attribute_value,
            "modifier": modifier,
            "dc": dc
        },
        "roll": {
            "d20": roll,
            "modifier": modifier,
            "total": total
        },
        "result": {
            "type": result_type,
            "description": result_desc,
            "success": is_success,
            "margin": total - dc
        },
        "impact": {
            "next_dc_modifier": next_dc_modifier,
            "info_leak": info_leak
        },
        "context": context
    }
    
    return result

def execute_multi_step(steps, info_leak_count=0):
    """
    执行多步骤战术检定 (v3.3.2 指挥链过载机制)
    
    参数:
        steps: 步骤列表，每个步骤包含attribute_value, dc, name
        info_leak_count: 当前信息泄露次数
    
    返回:
        所有步骤的检定结果列表
    """
    results = []
    current_info_leak = info_leak_count
    
    for i, step in enumerate(steps):
        step_num = i + 1
        
        # 计算基础DC
        base_dc = step.get("dc", 10)
        
        # 应用前一步的DC修正
        if i > 0:
            prev_modifier = results[i-1]["impact"]["next_dc_modifier"]
            base_dc += prev_modifier
        
        # 应用信息泄露惩罚 (补丁C)
        if current_info_leak > 0:
            base_dc += current_info_leak * 2
        
        # 指挥链过载 (补丁B): 第4步起每步+1
        if step_num > 3:
            overload_penalty = step_num - 3
            base_dc += overload_penalty
        
        # 执行检定
        result = execute_check(
            attribute_value=step.get("attribute_value", 10),
            dc=base_dc,
            attribute_name=step.get("attribute", "未知"),
            context=step.get("name", f"步骤{step_num}")
        )
        
        # 更新信息泄露计数
        if result["impact"]["info_leak"]:
            current_info_leak += 1
            result["impact"]["info_leak_count"] = current_info_leak
        
        results.append(result)
    
    return results

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python3 dice_roller.py <attribute_value> <dc> [attribute_name] [context]")
        print("Example: python3 dice_roller.py 13 15 insight 'detect_lie'")
        print("Attributes will be automatically converted to modifiers using (value-10)/2")
        sys.exit(1)
    
    attribute_value = int(sys.argv[1])
    dc = int(sys.argv[2])
    attribute_name = sys.argv[3] if len(sys.argv) > 3 else "attribute"
    context = sys.argv[4] if len(sys.argv) > 4 else ""
    
    result = execute_check(attribute_value, dc, attribute_name, context)
    print(json.dumps(result, indent=2, ensure_ascii=False))
