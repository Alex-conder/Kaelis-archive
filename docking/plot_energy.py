#!/usr/bin/env python3
"""
绘制能量分布图：箱线图和热图。
使用现有结合能数据（binding_energy_summary.csv）和对接结果（docking_affinities.csv，如果存在）。
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from pathlib import Path

# 设置中文字体（可选）
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

def load_data():
    """加载现有数据和对接结果"""
    base = Path(__file__).parent
    existing = base / 'binding_energy_summary.csv'
    docking = base / 'docking_affinities.csv'
    
    df_exist = pd.read_csv(existing, encoding='utf-8-sig')
    # 重命名列以保持一致性
    if 'Binding_Energy_kcal_mol' in df_exist.columns:
        df_exist = df_exist.rename(columns={'Binding_Energy_kcal_mol': 'Affinity'})
    else:
        df_exist['Affinity'] = df_exist.get('结合能', np.nan)
    
    df_dock = None
    if docking.exists():
        df_dock = pd.read_csv(docking, encoding='utf-8-sig')
        if 'Affinity_kcal_mol' in df_dock.columns:
            df_dock = df_dock.rename(columns={'Affinity_kcal_mol': 'Affinity'})
    
    # 合并数据
    df = df_exist.copy()
    df['Data_Source'] = '现有报告'
    if df_dock is not None:
        df_dock['Data_Source'] = '对接模拟'
        # 只取另一种配体的数据（假设现有数据是万古霉素，对接数据是美罗培南）
        # 这里简单合并，实际可能需要根据配体名称区分
        df = pd.concat([df, df_dock], ignore_index=True)
    
    # 确保有配体列
    if 'Ligand' not in df.columns:
        df['Ligand'] = '未知'
    return df

def plot_boxplot(df):
    """绘制结合能箱线图（按蛋白质和配体分组）"""
    plt.figure(figsize=(10, 6))
    # 过滤掉缺失值
    df_plot = df.dropna(subset=['Affinity'])
    # 如果配体未知，可能有两种配体
    sns.boxplot(data=df_plot, x='Protein', y='Affinity', hue='Ligand')
    plt.title('结合能分布（万古霉素 vs 美罗培南）')
    plt.ylabel('结合能 (kcal/mol)')
    plt.xlabel('蛋白质')
    plt.legend(title='配体')
    plt.tight_layout()
    plt.savefig('energy_distribution_boxplot.png', dpi=300)
    plt.show()

def plot_heatmap(df):
    """绘制结合能热图（蛋白质 vs 配体）"""
    # 创建数据透视表
    pivot = df.pivot_table(index='Protein', columns='Ligand', values='Affinity', aggfunc='mean')
    plt.figure(figsize=(8, 6))
    sns.heatmap(pivot, annot=True, fmt='.2f', cmap='coolwarm', center=0, cbar_kws={'label': '结合能 (kcal/mol)'})
    plt.title('结合能热图（蛋白质‑配体）')
    plt.tight_layout()
    plt.savefig('energy_heatmap.png', dpi=300)
    plt.show()

def plot_binding_forces(df):
    """绘制结合作用力图（如果数据中有）"""
    # 检查是否有VDW、HBond等列
    force_cols = ['VDW_kcal_mol', 'HBond_kcal_mol', 'Electrostatic_kcal_mol', 'Hydrophobic_kcal_mol']
    available = [col for col in force_cols if col in df.columns]
    if len(available) == 0:
        print("没有找到作用力数据，跳过作用力图。")
        return
    # 取每个蛋白质的平均值（假设只有一种配体）
    force_data = df.groupby('Protein')[available].mean()
    force_data.plot(kind='bar', stacked=True, figsize=(10, 6))
    plt.title('结合作用力贡献（平均值）')
    plt.ylabel('能量 (kcal/mol)')
    plt.xlabel('蛋白质')
    plt.legend(title='作用力类型')
    plt.tight_layout()
    plt.savefig('binding_forces_bar.png', dpi=300)
    plt.show()

def main():
    print("加载数据...")
    df = load_data()
    print(df)
    
    print("绘制箱线图...")
    plot_boxplot(df)
    
    print("绘制热图...")
    plot_heatmap(df)
    
    print("绘制结合作用力图...")
    plot_binding_forces(df)
    
    print("图表已保存为PNG文件。")

if __name__ == '__main__':
    main()