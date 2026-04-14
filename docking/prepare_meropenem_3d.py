#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
生成美罗培南3D结构
"""

from rdkit import Chem
from rdkit.Chem import AllChem

# 美罗培南SMILES
MEROPENEM_SMILES = "C[C@@H]1[C@@H]2[C@H](C(=O)N2C(=C1S[C@H]3C[C@H](NC3)C(=O)N(C)C)C(=O)O)[C@@H](C)O"

print("Generating Meropenem 3D structure...")

# 从SMILES创建分子
mol = Chem.MolFromSmiles(MEROPENEM_SMILES)
if mol is None:
    print("Error: Failed to parse SMILES")
    exit(1)

print("Adding hydrogens...")
mol = Chem.AddHs(mol)

print("Generating 3D conformer...")
AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())

print("Optimizing with MMFF...")
AllChem.MMFFOptimizeMolecule(mol, maxIters=500)

# 保存为PDB
output_pdb = r"C:\Users\11526\OneDrive\Desktop\docking\Meropenem_3D.pdb"
Chem.MolToPDBFile(mol, output_pdb)

print(f"3D structure saved: {output_pdb}")

# 计算性质
from rdkit.Chem import Descriptors, rdMolDescriptors
print(f"\nProperties:")
print(f"  Formula: {rdMolDescriptors.CalcMolFormula(mol)}")
print(f"  MW: {Descriptors.MolWt(mol):.2f}")
print(f"  Atoms: {mol.GetNumAtoms()}")
print(f"  Rotatable bonds: {rdMolDescriptors.CalcNumRotatableBonds(mol)}")
