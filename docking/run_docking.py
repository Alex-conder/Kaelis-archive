#!/usr/bin/env python3
"""
AutoDock Vina对接脚本，用于生成万古霉素和美罗培南与5种蛋白的结合数据。
假设已安装AutoDock Vina、MGLTools（用于准备受体）和Open Babel（用于准备配体）。
"""

import subprocess
import os
from pathlib import Path

# 配置
PROTEINS = {
    '3VVP': {'center': [15.2, 45.3, 32.1], 'size': [20, 20, 20]},
    '6UJN': {'center': [10.5, 20.3, 15.8], 'size': [20, 20, 20]},
    '8ET9': {'center': [12.0, 18.5, 22.0], 'size': [20, 20, 20]},
    '8RQ4': {'center': [25.1, 30.2, 40.3], 'size': [20, 20, 20]},
    '8SDY': {'center': [18.3, 22.7, 28.9], 'size': [20, 20, 20]},
}

LIGANDS = {
    'Vancomycin': {'smiles': 'C[C@H]1[C@H]([C@@](C[C@@H](O1)O[C@@H]2[C@H]([C@@H]([C@H](O[C@H]2OC3=C4C=C5C=C3OC6=C(C=C(C=C6)[C@H]([C@H](C(=O)N[C@H](C(=O)N[C@H]5C(=O)N[C@@H]7C8=CC(=C(C=C8)O)C9=C(C=C(C=C9)O)[C@H](NC(=O)[C@H]([C@@H](C1=CC(=C(O4)C=C1)Cl)O)NC7=O)C(=O)O)CC(=O)N)NC(=O)[C@@H](CC(C)C)NC)O)Cl)CO)O)O)(C)N)O'},
    'Meropenem': {'smiles': 'C[C@@H]1[C@@H]2[C@H](C(=O)N2C(=C1S[C@H]3C[C@H](NC3)C(=O)N(C)C)C(=O)O)[C@@H](C)O'},
}

def prepare_protein(pdb_file, output_pdbqt):
    """使用MGLTools的prepare_receptor将PDB转换为PDBQT"""
    # 如果已经存在则跳过
    if os.path.exists(output_pdbqt):
        print(f"受体PDBQT已存在: {output_pdbqt}")
        return True
    # 检查prepare_receptor是否可用
    try:
        cmd = ['prepare_receptor', '-r', pdb_file, '-o', output_pdbqt]
        subprocess.run(cmd, check=True)
        print(f"已准备受体: {output_pdbqt}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"警告: 无法准备受体 {pdb_file}，请手动运行:")
        print(f"  prepare_receptor -r {pdb_file} -o {output_pdbqt}")
        return False

def prepare_ligand(smiles, output_pdbqt):
    """使用Open Babel将SMILES转换为PDBQT"""
    if os.path.exists(output_pdbqt):
        print(f"配体PDBQT已存在: {output_pdbqt}")
        return True
    # 通过obabel转换
    try:
        cmd = ['obabel', '-ismiles', f'-:{smiles}', '-opdbqt', '-O', output_pdbqt, '--gen3d']
        subprocess.run(cmd, check=True)
        print(f"已准备配体: {output_pdbqt}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"警告: 无法准备配体 {output_pdbqt}，请手动运行:")
        print(f"  obabel -ismiles -:'{smiles}' -opdbqt -O {output_pdbqt} --gen3d")
        return False

def run_vina(receptor_pdbqt, ligand_pdbqt, center, size, output_dir, exhaustiveness=8):
    """运行AutoDock Vina对接"""
    out_pdbqt = os.path.join(output_dir, 'docked.pdbqt')
    log_file = os.path.join(output_dir, 'vina.log')
    cmd = [
        'vina',
        '--receptor', receptor_pdbqt,
        '--ligand', ligand_pdbqt,
        '--center_x', str(center[0]),
        '--center_y', str(center[1]),
        '--center_z', str(center[2]),
        '--size_x', str(size[0]),
        '--size_y', str(size[1]),
        '--size_z', str(size[2]),
        '--exhaustiveness', str(exhaustiveness),
        '--out', out_pdbqt,
        '--log', log_file
    ]
    try:
        subprocess.run(cmd, check=True)
        print(f"对接完成，结果保存至: {out_pdbqt}")
        return out_pdbqt, log_file
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"警告: Vina对接失败，请检查Vina安装和参数")
        return None, None

def extract_binding_energy(log_file):
    """从Vina日志文件中提取结合能（最低亲和力）"""
    if not os.path.exists(log_file):
        return None
    with open(log_file, 'r') as f:
        lines = f.readlines()
    for line in lines:
        if 'Affinity' in line:
            # 示例: "Affinity: -9.8 kcal/mol"
            parts = line.split()
            for i, part in enumerate(parts):
                if part == 'Affinity:':
                    affinity = float(parts[i+1])
                    return affinity
    return None

def main():
    base_dir = Path(__file__).parent
    # 创建目录
    protein_dir = base_dir / 'proteins_pdbqt'
    ligand_dir = base_dir / 'ligands_pdbqt'
    docking_dir = base_dir / 'docking_results'
    protein_dir.mkdir(exist_ok=True)
    ligand_dir.mkdir(exist_ok=True)
    docking_dir.mkdir(exist_ok=True)
    
    # 准备配体
    ligand_files = {}
    for lig_name, lig_info in LIGANDS.items():
        pdbqt = ligand_dir / f'{lig_name}.pdbqt'
        if not prepare_ligand(lig_info['smiles'], str(pdbqt)):
            # 如果失败，创建空文件作为占位符
            pdbqt.touch()
        ligand_files[lig_name] = pdbqt
    
    results = []
    
    # 对每个蛋白质-配体组合进行对接
    for prot_name, grid in PROTEINS.items():
        pdb_file = base_dir / f'{prot_name}.pdb'
        if not pdb_file.exists():
            print(f"蛋白质PDB文件不存在: {pdb_file}")
            continue
        receptor_pdbqt = protein_dir / f'{prot_name}.pdbqt'
        if not prepare_protein(str(pdb_file), str(receptor_pdbqt)):
            continue
        
        for lig_name, lig_pdbqt in ligand_files.items():
            print(f"对接 {prot_name} + {lig_name}")
            combo_dir = docking_dir / f'{prot_name}_{lig_name}'
            combo_dir.mkdir(exist_ok=True)
            
            # 运行Vina
            out_pdbqt, log_file = run_vina(
                str(receptor_pdbqt),
                str(lig_pdbqt),
                grid['center'],
                grid['size'],
                str(combo_dir)
            )
            if out_pdbqt:
                affinity = extract_binding_energy(log_file)
            else:
                affinity = None
            results.append({
                'Protein': prot_name,
                'Ligand': lig_name,
                'Affinity_kcal_mol': affinity,
                'Output': str(out_pdbqt) if out_pdbqt else None
            })
    
    # 保存结果到CSV
    import pandas as pd
    df = pd.DataFrame(results)
    df.to_csv(base_dir / 'docking_affinities.csv', index=False)
    print("对接完成！结果保存在 docking_affinities.csv")
    print(df)

if __name__ == '__main__':
    main()