#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
修复配体并运行真正的对接
"""

from __future__ import print_function
import os
import sys
import subprocess
import shutil

BASE_DIR = r"C:\Users\11526\OneDrive\Desktop"
DOCKING_DIR = os.path.join(BASE_DIR, "docking")

# 万古霉素SMILES (完整)
VANCOMYCIN_SMILES = "C[C@H]1[C@H]([C@@](C[C@@H](O1)O[C@@H]2[C@H]([C@@H]([C@H](O[C@H]2OC3=C4C=C5C=C3OC6=C(C=C(C=C6)[C@H]([C@H](C(=O)N[C@H](C(=O)N[C@H]5C(=O)N[C@@H]7C8=CC(=C(C=C8)O)C9=C(C=C(C=C9)O)[C@H](NC(=O)[C@H]([C@@H](C1=CC(=C(O4)C=C1)Cl)O)NC7=O)C(=O)O)CC(=O)N)NC(=O)[C@@H](CC(C)C)NC)O)Cl)CO)O)O)(C)N)O"


def generate_3d_ligand_rdkit():
    """使用RDKit生成3D配体结构"""
    print("=" * 60)
    print("使用RDKit生成万古霉素3D结构...")
    print("=" * 60)
    
    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem
        
        # 从SMILES创建分子
        mol = Chem.MolFromSmiles(VANCOMYCIN_SMILES)
        if mol is None:
            print("错误: 无法解析SMILES")
            return False
        
        print("SMILES解析成功，添加氢原子...")
        mol = Chem.AddHs(mol)
        
        print("生成3D构象 (ETKDG算法)...")
        # 使用ETKDG算法生成3D坐标
        AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
        
        print("优化构象 (MMFF力场)...")
        AllChem.MMFFOptimizeMolecule(mol, maxIters=500)
        
        # 保存为PDB
        output_pdb = os.path.join(DOCKING_DIR, "Vancomycin_3D.pdb")
        Chem.MolToPDBFile(mol, output_pdb)
        print("3D结构已保存: {}".format(output_pdb))
        
        # 计算性质
        from rdkit.Chem import Descriptors, rdMolDescriptors
        print("\n分子性质:")
        print("  分子式: {}".format(rdMolDescriptors.CalcMolFormula(mol)))
        print("  分子量: {:.2f}".format(Descriptors.MolWt(mol)))
        print("  原子数: {}".format(mol.GetNumAtoms()))
        print("  可旋转键: {}".format(rdMolDescriptors.CalcNumRotatableBonds(mol)))
        
        return output_pdb
        
    except ImportError:
        print("错误: RDKit未安装")
        return False
    except Exception as e:
        print("错误: {}".format(e))
        return False


def convert_to_pdbqt(pdb_file, output_pdbqt):
    """使用MGLTools转换PDB为PDBQT"""
    print("\n转换为PDBQT格式...")
    
    try:
        # 尝试使用prepare_ligand
        cmd = ['prepare_ligand', '-l', pdb_file, '-o', output_pdbqt, '-A', 'hydrogens']
        subprocess.call(cmd)
        
        if os.path.exists(output_pdbqt):
            print("PDBQT转换成功: {}".format(output_pdbqt))
            return output_pdbqt
    except:
        pass
    
    # 如果MGLTools失败，使用Open Babel
    try:
        cmd = ['obabel', '-ipdb', pdb_file, '-opdbqt', '-O', output_pdbqt]
        subprocess.call(cmd)
        
        if os.path.exists(output_pdbqt):
            print("PDBQT转换成功 (Open Babel): {}".format(output_pdbqt))
            return output_pdbqt
    except:
        pass
    
    print("警告: 无法转换为PDBQT，请手动转换")
    return None


def verify_coordinates(pdbqt_file):
    """验证PDBQT文件坐标是否有效"""
    print("\n验证坐标...")
    
    if not os.path.exists(pdbqt_file):
        print("错误: 文件不存在")
        return False
    
    with open(pdbqt_file, 'r') as f:
        lines = f.readlines()
    
    atom_count = 0
    zero_count = 0
    
    for line in lines:
        if line.startswith('ATOM') or line.startswith('HETATM'):
            atom_count += 1
            try:
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
                if x == 0.0 and y == 0.0 and z == 0.0:
                    zero_count += 1
            except:
                pass
    
    print("  总原子数: {}".format(atom_count))
    print("  零坐标原子: {}".format(zero_count))
    
    if zero_count == atom_count:
        print("  ❌ 所有坐标为零，文件无效！")
        return False
    elif zero_count > 0:
        print("  ⚠️  部分坐标为零")
        return True
    else:
        print("  ✅ 坐标有效")
        return True


def run_vina_docking(ligand_pdbqt):
    """运行AutoDock Vina对接"""
    print("\n" + "=" * 60)
    print("运行AutoDock Vina对接...")
    print("=" * 60)
    
    receptor = os.path.join(BASE_DIR, "8SDY325", "rigidReceptor.pdbqt")
    if not os.path.exists(receptor):
        print("错误: 受体文件不存在 {}".format(receptor))
        return False
    
    output_dir = os.path.join(DOCKING_DIR, "real_docking_results")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    output_pdbqt = os.path.join(output_dir, "8SDY_Vancomycin_vina.pdbqt")
    log_file = os.path.join(output_dir, "vina.log")
    
    # Vina命令
    cmd = [
        'vina',
        '--receptor', receptor,
        '--ligand', ligand_pdbqt,
        '--center_x', '18.3',
        '--center_y', '22.7',
        '--center_z', '28.9',
        '--size_x', '20',
        '--size_y', '20',
        '--size_z', '20',
        '--exhaustiveness', '32',
        '--num_modes', '9',
        '--out', output_pdbqt,
        '--log', log_file
    ]
    
    print("\n对接参数:")
    print("  受体: {}".format(receptor))
    print("  配体: {}".format(ligand_pdbqt))
    print("  中心: (18.3, 22.7, 28.9)")
    print("  格点: 20x20x20 Å")
    print("  搜索深度: 32")
    
    print("\n运行命令:")
    print(" ".join(cmd))
    
    try:
        print("\n正在对接 (这可能需要10-30分钟)...")
        result = subprocess.call(cmd)
        
        if result == 0 and os.path.exists(output_pdbqt):
            print("\n✅ 对接完成！")
            print("结果文件: {}".format(output_pdbqt))
            print("日志文件: {}".format(log_file))
            return output_pdbqt
        else:
            print("\n❌ 对接失败")
            return None
            
    except OSError as e:
        print("\n错误: 无法运行Vina ({})".format(e))
        print("请确保Vina已安装并在PATH中")
        return None


def extract_binding_energy(log_file):
    """从Vina日志提取结合能"""
    if not os.path.exists(log_file):
        return None
    
    energies = []
    with open(log_file, 'r') as f:
        lines = f.readlines()
    
    in_table = False
    for line in lines:
        if '-----+' in line:
            in_table = True
            continue
        if in_table and line.strip() and line[0].isdigit():
            parts = line.split()
            if len(parts) >= 2:
                try:
                    mode = int(parts[0])
                    affinity = float(parts[1])
                    energies.append((mode, affinity))
                except:
                    pass
    
    return energies


def main():
    print("\n" + "=" * 60)
    print("修复配体并运行真正的对接")
    print("=" * 60)
    
    # 步骤1: 生成3D配体
    pdb_file = generate_3d_ligand_rdkit()
    if not pdb_file:
        print("\n错误: 无法生成3D配体")
        return
    
    # 步骤2: 转换为PDBQT
    ligand_pdbqt = os.path.join(DOCKING_DIR, "ligands_pdbqt", "Vancomycin_fixed.pdbqt")
    pdbqt_file = convert_to_pdbqt(pdb_file, ligand_pdbqt)
    
    # 步骤3: 验证坐标
    if pdbqt_file:
        is_valid = verify_coordinates(pdbqt_file)
        if not is_valid:
            print("\n错误: PDBQT文件无效")
            return
    
    # 步骤4: 运行对接
    result = run_vina_docking(ligand_pdbqt)
    
    if result:
        # 提取结合能
        log_file = os.path.join(DOCKING_DIR, "real_docking_results", "vina.log")
        energies = extract_binding_energy(log_file)
        
        print("\n" + "=" * 60)
        print("对接结果")
        print("=" * 60)
        if energies:
            print("\n模式 | 结合能 (kcal/mol)")
            print("-" * 30)
            for mode, energy in energies[:5]:  # 显示前5个
                print("  {}   | {:.2f}".format(mode, energy))
            print("\n最佳结合能: {:.2f} kcal/mol".format(energies[0][1]))
        
        print("\n✅ 真正的对接已完成！")
        print("请使用real_docking_results/中的结果进行分析")
    else:
        print("\n⚠️  对接未能完成")
        print("但3D配体文件已生成，可以手动运行对接")


if __name__ == "__main__":
    main()
