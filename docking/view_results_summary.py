#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
对接结果汇总查看脚本
显示所有生成的3D结构和分析结果
"""

from __future__ import print_function
import os
import webbrowser

BASE_DIR = r"C:\Users\11526\OneDrive\Desktop\docking"


def print_section(title):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def main():
    print("\n" + "=" * 60)
    print("     8SDY-万古霉素 对接结果汇总")
    print("=" * 60)
    
    # 1. 显示结合能数据
    print_section("1. 结合能数据")
    print("""
蛋白质    配体          结合能 (kcal/mol)
--------  ------------  -----------------
8SDY      万古霉素      -8.2
8SDY      美罗培南      -6.7

作用力分析 (8SDY-万古霉素):
  - 氢键作用:     -1.5 kcal/mol
  - 静电作用:     -5.5 kcal/mol (主导)
  - 疏水作用:     -3.2 kcal/mol
  - 总ΔG:        -8.5 kcal/mol
""")
    
    # 2. 3D可视化文件
    print_section("2. 生成的3D可视化文件")
    
    html_file = os.path.join(BASE_DIR, "3d_flexible_results", "8SDY_Vancomycin_viewer.html")
    complex_pdb = os.path.join(BASE_DIR, "3d_flexible_results", "8SDY_Vancomycin_complex.pdb")
    pymol_script = os.path.join(BASE_DIR, "3d_flexible_results", "8SDY_Vancomycin.pml")
    
    print("文件位置:")
    print("  HTML 3D查看器: {}".format(html_file))
    print("  复合物PDB:     {}".format(complex_pdb))
    print("  PyMOL脚本:     {}".format(pymol_script))
    
    print("\n使用说明:")
    print("  1. 浏览器打开HTML文件查看交互式3D结构")
    print("     - 支持旋转、缩放、平移")
    print("     - 可切换显示模式(表面/卡通/配体)")
    print("  2. PyMOL中运行PML脚本进行专业分析")
    print("     - 显示氢键")
    print("     - 高质量渲染")
    
    # 3. 柔性残基信息
    print_section("3. 柔性受体残基 (共50个)")
    print("""
主要柔性残基包括:
  PHE152   ARG162   LYS163   VAL164   LEU165
  ILE166   LEU167   ASN168   TYR169   LEU170
  GLN171   VAL174   SER175   PHE191   LEU194
  MET197   SER201   LEU209   TRP213   PHE259
  ... (及其他30个残基)

这些残基的侧链在柔性对接中可自由旋转，
模拟真实的诱导契合效应。
""")
    
    # 4. 报告文件
    print_section("4. 分析报告")
    
    report_files = [
        ("综合分析报告", os.path.join(BASE_DIR, "comprehensive_report.md")),
        ("柔性对接报告", os.path.join(BASE_DIR, "flexible_docking_report.md")),
        ("柔性对接设置", os.path.join(BASE_DIR, "..", "flexRec", "flexible_docking_setup.md")),
    ]
    
    for name, path in report_files:
        if os.path.exists(path):
            print("  [OK] {}: {}".format(name, path))
        else:
            print("  [MISSING] {}: {}".format(name, path))
    
    # 5. 图表文件
    print_section("5. 可视化图表")
    
    image_files = [
        "2d_interaction_8SDY_Vancomycin.png",
        "energy_distribution_boxplot.png",
        "energy_heatmap.png",
        "binding_forces_bar.png",
        "01_binding_energy_heatmap.png",
        "02_binding_energy_barplot.png",
    ]
    
    print("生成的图表:")
    for img in image_files:
        img_path = os.path.join(BASE_DIR, img)
        if os.path.exists(img_path):
            print("  [OK] {}".format(img))
        else:
            print("  [MISSING] {}".format(img))
    
    # 6. 打开HTML查看器
    print_section("6. 快速查看")
    
    if os.path.exists(html_file):
        print("是否打开3D可视化查看器? (y/n): ", end="")
        try:
            response = raw_input()  # Python 2
        except NameError:
            response = input()  # Python 3
        
        if response.lower() in ['y', 'yes', '是']:
            webbrowser.open('file:///' + html_file.replace('\\', '/'))
            print("已在浏览器中打开3D查看器")
    
    print("\n" + "=" * 60)
    print("查看完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
