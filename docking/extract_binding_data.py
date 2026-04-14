#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从分子对接分析报告Markdown文件中提取结合能数据。
报告位于：分子对接评价指南_同批次内容_20260319_150844/01_相关文档/分析文档/
"""

import pandas as pd
from pathlib import Path
import re

REPORT_DIR = Path(r"C:/Users/11526/OneDrive/Desktop/分子对接评价指南_同批次内容_20260319_150844/01_相关文档/分析文档")

PARAMS = {
    "结合能": "kcal/mol",
    "抑制常数(Ki)": "nM",
    "结合自由能(ΔG)": "kcal/mol",
    "范德华力": "kcal/mol",
    "氢键能": "kcal/mol",
    "静电能": "kcal/mol"
}

def extract_data_from_file(filepath):
    """从单个Markdown文件中提取数据"""
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        lines = f.readlines()
    
    data = {}
    in_scoring_section = False
    for line in lines:
        line = line.strip()
        if line.startswith('## 五、对接评分'):
            in_scoring_section = True
            continue
        if in_scoring_section and line.startswith('##'):
            # 进入下一节，停止
            break
        if in_scoring_section and line.startswith('|'):
            # 表格行
            # 跳过分隔行
            if '---' in line or '------' in line:
                continue
            # 解析单元格
            cells = [cell.strip() for cell in line.split('|') if cell.strip() != '']
            if len(cells) == 2:
                param, value = cells[0], cells[1]
                if param in PARAMS:
                    # 提取数值
                    # 使用正则匹配数字（可能为负数、小数）
                    num_match = re.search(r'[-+]?\d*\.?\d+', value)
                    if num_match:
                        num = float(num_match.group())
                        data[param] = num
                    else:
                        data[param] = value
    return data

def main():
    reports = list(REPORT_DIR.glob("【分子对接分析报告】*.md"))
    # 排除主索引
    reports = [r for r in reports if not r.name.endswith('主索引.md')]
    
    all_data = []
    for report in reports:
        print(f"处理: {report.name}")
        data = extract_data_from_file(report)
        # 从文件名提取蛋白质ID
        match = re.search(r'【分子对接分析报告】(.*?)_.*\.md', report.name)
        if match:
            protein = match.group(1)
        else:
            protein = report.name.split('_')[0].replace('【分子对接分析报告】', '')
        
        # 配体未知
        ligand = "未知"
        row = {
            'Protein': protein,
            'Ligand': ligand,
            '报告文件': report.name
        }
        for param in PARAMS:
            row[param] = data.get(param, None)
        all_data.append(row)
    
    df = pd.DataFrame(all_data)
    # 重命名列为英文
    df = df.rename(columns={
        '结合能': 'Binding_Energy_kcal_mol',
        '抑制常数(Ki)': 'Ki_nM',
        '结合自由能(ΔG)': 'DeltaG_kcal_mol',
        '范德华力': 'VDW_kcal_mol',
        '氢键能': 'HBond_kcal_mol',
        '静电能': 'Electrostatic_kcal_mol'
    })
    output_path = Path("binding_energy_summary.csv")
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"数据已保存至: {output_path}")
    print(df)

if __name__ == '__main__':
    main()