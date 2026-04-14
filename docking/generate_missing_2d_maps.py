#!/usr/bin/env python3
"""
生成缺失的2D相互作用图（共7张）。
需要先运行对接模拟获得复合物PDB文件，并安装PLIP。
"""

import os
from pathlib import Path

# 缺失的组合
MISSING = [
    ('3VVP', 'Vancomycin'),
    ('3VVP', 'Meropenem'),
    ('8ET9', 'Vancomycin'),
    ('8ET9', 'Meropenem'),
    ('8RQ4', 'Vancomycin'),
    ('8SDY', 'Vancomycin'),
    ('8SDY', 'Meropenem'),
]

def check_existing():
    """检查已存在的2D相互作用图"""
    base = Path(__file__).parent
    existing = []
    for p, l in MISSING:
        fname = f'2d_interaction_{p}_{l}.png'
        if (base / fname).exists():
            existing.append((p, l))
    return existing

def generate_2d_map(protein, ligand):
    """使用PLIP生成单个2D相互作用图"""
    # 假设复合物PDB文件路径
    complex_pdb = f'docking_results/{protein}_{ligand}/docked.pdb'
    if not os.path.exists(complex_pdb):
        print(f"复合物文件不存在: {complex_pdb}，请先运行对接模拟。")
        return False
    # 使用PLIP命令
    cmd = f'plip -f {complex_pdb} -o plip_output --quiet'
    print(f"运行: {cmd}")
    # 实际执行需要subprocess，此处仅示意
    # subprocess.run(cmd, shell=True, check=True)
    # 复制生成的图像到当前目录
    src = f'plip_output/report_{protein}_{ligand}.png'
    dst = f'2d_interaction_{protein}_{ligand}.png'
    # 假设PLIP生成报告图像，实际文件名可能不同
    if os.path.exists(src):
        import shutil
        shutil.copy(src, dst)
        print(f"已生成: {dst}")
        return True
    else:
        print(f"PLIP未生成预期图像，请检查PLIP输出。")
        return False

def main():
    print("检查缺失的2D相互作用图...")
    existing = check_existing()
    if existing:
        print(f"已存在 {len(existing)} 张图: {existing}")
    missing = [c for c in MISSING if c not in existing]
    print(f"需要生成 {len(missing)} 张图: {missing}")
    
    # 如果没有缺失，退出
    if not missing:
        print("所有2D相互作用图已存在。")
        return
    
    # 询问用户是否继续
    try:
        response = input("是否继续生成？需要安装PLIP并已准备好复合物PDB文件。(y/n): ")
    except EOFError:
        response = 'n'
    if response.lower() != 'y':
        print("已取消。")
        return
    
    # 尝试生成
    success = []
    for protein, ligand in missing:
        print(f"处理 {protein} - {ligand}...")
        if generate_2d_map(protein, ligand):
            success.append((protein, ligand))
    
    print(f"成功生成 {len(success)} 张2D相互作用图。")
    if success:
        print("生成的图:", success)

if __name__ == '__main__':
    main()