#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
手动准备配体 - 使用Open Babel
"""

from __future__ import print_function
import os
import subprocess

BASE_DIR = r"C:\Users\11526\OneDrive\Desktop"
LIGAND_PDB = os.path.join(BASE_DIR, "docking", "Vancomycin_3D.pdb")
LIGAND_PDBQT = os.path.join(BASE_DIR, "docking", "ligands_pdbqt", "Vancomycin_ADFR.pdbqt")

def prepare_with_openbabel():
    """使用Open Babel转换"""
    print("=" * 60)
    print("使用Open Babel准备配体")
    print("=" * 60)
    
    if not os.path.exists(LIGAND_PDB):
        print("错误: 找不到PDB文件 {}".format(LIGAND_PDB))
        return False
    
    print("输入: {}".format(LIGAND_PDB))
    print("输出: {}".format(LIGAND_PDBQT))
    
    # 使用Open Babel转换
    cmd = [
        r'E:\OpenBabel-2.4.1\obabel.exe',
        '-ipdb', LIGAND_PDB,
        '-opdbqt',
        '-O', LIGAND_PDBQT,
        '-h'  # 添加氢原子
    ]
    
    print("\n命令: {}".format(' '.join(cmd)))
    print("\n运行中...")
    
    try:
        result = subprocess.call(cmd)
        
        if result == 0 and os.path.exists(LIGAND_PDBQT):
            print("\n成功！文件已生成: {}".format(LIGAND_PDBQT))
            
            # 检查文件大小
            size = os.path.getsize(LIGAND_PDBQT)
            print("文件大小: {} bytes".format(size))
            
            # 验证坐标
            with open(LIGAND_PDBQT, 'r') as f:
                lines = f.readlines()
            
            atom_count = 0
            for line in lines:
                if line.startswith('ATOM') or line.startswith('HETATM'):
                    atom_count += 1
            
            print("原子数量: {}".format(atom_count))
            return True
        else:
            print("\n错误: 转换失败")
            return False
            
    except Exception as e:
        print("\n错误: {}".format(e))
        return False


def main():
    if os.path.exists(LIGAND_PDBQT):
        print("配体PDBQT已存在: {}".format(LIGAND_PDBQT))
        response = raw_input("是否重新生成? (y/n): ")
        if response.lower() != 'y':
            return
    
    prepare_with_openbabel()
    
    print("\n按Enter键退出...")
    raw_input()


if __name__ == "__main__":
    main()
