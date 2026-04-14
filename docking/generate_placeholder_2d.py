#!/usr/bin/env python3
"""
生成缺失的2D相互作用占位图（7张）。
使用matplotlib创建简单的文本图像。
"""
import matplotlib.pyplot as plt
import os

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

def create_placeholder(protein, ligand):
    """创建占位图"""
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.text(0.5, 0.5, f'2D Interaction\n{protein} + {ligand}\n(Placeholder)',
            ha='center', va='center', fontsize=14, wrap=True)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    filename = f'2d_interaction_{protein}_{ligand}.png'
    fig.savefig(filename, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f'已生成: {filename}')
    return filename

def main():
    for protein, ligand in MISSING:
        if os.path.exists(f'2d_interaction_{protein}_{ligand}.png'):
            print(f'已存在: 2d_interaction_{protein}_{ligand}.png')
            continue
        create_placeholder(protein, ligand)
    print('完成。')

if __name__ == '__main__':
    main()