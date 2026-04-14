#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
运行8SDY-万古霉素柔性受体对接 (AutoDockFR)
使用预先生成的flexRec柔性受体和网格文件
Python 2.7兼容版本
"""

from __future__ import print_function
import os
import sys
import subprocess
import shutil
from glob import glob

# 配置
BASE_DIR = r"C:\Users\11526\OneDrive\Desktop"
FLEXREC_DIR = os.path.join(BASE_DIR, "flexRec")
SDY325_DIR = os.path.join(BASE_DIR, "8SDY325")
SDY324_DIR = os.path.join(BASE_DIR, "8SDY324")
LIGAND_PDBQT = os.path.join(BASE_DIR, "docking", "ligands_pdbqt", "Vancomycin.pdbqt")

# AutoDockFR参数
ADFR_CONFIG = {
    'flex_receptor': os.path.join(FLEXREC_DIR, "flexRec.pdbqt"),
    'rigid_receptor': os.path.join(SDY325_DIR, "rigidReceptor.pdbqt"),
    'maps_dir': SDY325_DIR,
    'ligand': LIGAND_PDBQT,
    'output_dir': os.path.join(FLEXREC_DIR, "docking_result"),
}


def check_adfr_installation():
    """检查ADFR是否安装"""
    try:
        result = subprocess.call(['adfr'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("ADFR已安装")
        return True
    except OSError:
        print("ADFR未安装或不在PATH中")
        print("请从 http://adfr.scripps.edu 下载并安装ADFR")
        return False


def prepare_ligand_if_needed():
    """准备配体文件（如果尚未转换为PDBQT）"""
    if os.path.exists(LIGAND_PDBQT):
        print("配体PDBQT已存在: {}".format(LIGAND_PDBQT))
        return LIGAND_PDBQT
    
    # 尝试使用MGLTools转换
    ligand_mol = os.path.join(BASE_DIR, "万古霉素.mol")
    if os.path.exists(ligand_mol):
        print("从MOL文件转换配体...")
        output_pdbqt = os.path.join(BASE_DIR, "docking", "ligands_pdbqt", "Vancomycin.pdbqt")
        try:
            cmd = ['prepare_ligand', '-l', ligand_mol, '-o', output_pdbqt]
            subprocess.run(cmd, check=True)
            print("配体转换成功")
            return output_pdbqt
        except (subprocess.CalledProcessError, OSError) as e:
            print("配体转换失败: {}".format(e))
            return None
    
    print("未找到配体文件")
    return None


def run_flexible_docking():
    """运行柔性受体对接"""
    print("\n" + "=" * 60)
    print("运行8SDY-万古霉素柔性受体对接")
    print("=" * 60)
    
    # 创建输出目录
    output_dir = ADFR_CONFIG['output_dir']
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 检查必要文件
    flex_rec = ADFR_CONFIG['flex_receptor']
    if not os.path.exists(flex_rec):
        print("错误: 柔性受体文件不存在 {}".format(flex_rec))
        return False
    
    ligand = prepare_ligand_if_needed()
    if not ligand:
        return False
    
    # 构建ADFR命令
    # 注意: 这需要ADFR已安装
    output_dlg = os.path.join(output_dir, "8SDY_Vancomycin_flex.dlg")
    
    print("\n对接参数:")
    print("  柔性受体: {}".format(flex_rec))
    print("  配体: {}".format(ligand))
    print("  输出: {}".format(output_dlg))
    
    # 构建命令行
    # 使用AutoDockFR进行柔性对接
    cmd = [
        'adfr',
        '-r', flex_rec,           # 柔性受体
        '-l', ligand,             # 配体
        '-o', output_dlg,         # 输出文件
        '--nbRuns', '50',         # 运行次数
        '--maxEvals', '2500000',  # 最大评估次数
        '--clusteringRMSDCutoff', '2.0',  # 聚类RMSD cutoff
    ]
    
    print("\n运行命令:")
    print(" ".join(cmd))
    print("\n注意: 这需要ADFR已正确安装")
    print("预计运行时间: 30-60分钟 (取决于CPU性能)")
    
    # 由于ADFR可能未安装，这里生成一个批处理脚本供用户手动运行
    batch_file = os.path.join(FLEXREC_DIR, "run_flex_docking.bat")
    with open(batch_file, 'w') as f:
        f.write("@echo off\n")
        f.write("echo Running 8SDY-Vancomycin Flexible Docking...\n")
        f.write("echo.\n")
        f.write(" ".join(cmd))
        f.write("\n")
        f.write("echo.\n")
        f.write("echo Docking completed!\n")
        f.write("pause\n")
    
    print("\n已生成批处理脚本: {}".format(batch_file))
    print("请确保ADFR已安装后运行此脚本")
    
    return True


def create_summary():
    """创建柔性对接摘要"""
    summary = """
# 8SDY-万古霉素柔性对接设置摘要

## 文件位置
| 文件类型 | 路径 |
|---------|------|
| 柔性受体 | {} |
| 刚性受体 | {} |
| 网格文件 | {} |
| 配体 | {} |
| 输出目录 | {} |

## 柔性残基
共50个柔性残基，包括:
- PHE152, ARG162, LYS163, VAL164, LEU165
- ILE166, LEU167, ASN168, TYR169, LEU170
- GLN171, VAL174, SER175, PHE191, LEU194
- MET197, SER201, LEU209, TRP213, PHE259
- ... (及其他30个残基)

## 运行命令
```bash
adfr -r flexRec.pdbqt -l Vancomycin.pdbqt \\
     -o docking_result/8SDY_Vancomycin_flex.dlg \\
     --nbRuns 50 --maxEvals 2500000 \\
     --clusteringRMSDCutoff 2.0
```

## 预期结果
- 对接日志: 8SDY_Vancomycin_flex.dlg
- 最佳构象: 8SDY_Vancomycin_flex_BEST.pdbqt
- 所有构象: 8SDY_Vancomycin_flex_ALL.pdbqt
- 聚类结果: 聚类后的多个代表性构象

## 下一步
1. 确保ADFR已安装
2. 运行批处理脚本: run_flex_docking.bat
3. 等待对接完成 (30-60分钟)
4. 分析结果dlg文件提取结合能和构象
""".format(
        ADFR_CONFIG['flex_receptor'],
        ADFR_CONFIG['rigid_receptor'],
        ADFR_CONFIG['maps_dir'],
        ADFR_CONFIG['ligand'],
        ADFR_CONFIG['output_dir']
    )
    
    summary_file = os.path.join(FLEXREC_DIR, "flexible_docking_setup.md")
    with open(summary_file, 'w') as f:
        f.write(summary)
    
    print("\n设置摘要已保存: {}".format(summary_file))


def main():
    """主函数"""
    print("=" * 60)
    print("8SDY-Vancomycin 柔性受体对接设置")
    print("=" * 60)
    
    # 检查ADFR
    has_adfr = check_adfr_installation()
    
    # 设置柔性对接
    run_flexible_docking()
    
    # 创建摘要
    create_summary()
    
    print("\n" + "=" * 60)
    if has_adfr:
        print("可以直接运行柔性对接")
    else:
        print("请安装ADFR后运行批处理脚本")
    print("=" * 60)


if __name__ == "__main__":
    main()
