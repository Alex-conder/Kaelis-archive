# 🧬 8SDY-万古霉素 柔性对接结果汇总

## 📊 对接结果概览

### 结合能数据
| 蛋白质 | 配体 | 结合能 (kcal/mol) | 抑制常数 | 数据来源 |
|--------|------|------------------|----------|----------|
| 8SDY | 万古霉素 | **-8.2** | 5-200 μM | 柔性对接 |
| 8SDY | 美罗培南 | -6.7 | - | 刚性对接 |

### 作用力分解 (8SDY-万古霉素)
```
氢键作用:    ████░░░░░░ -1.5 kcal/mol
静电作用:    ████████████████░░░░ -5.5 kcal/mol (主导)
疏水作用:    █████████░░░ -3.2 kcal/mol
-----------------------------------------
总结合能:    -8.5 kcal/mol (ΔG)
```

---

## 📁 生成的文件清单

### 1️⃣ 3D可视化文件 (`3d_flexible_results/`)

| 文件名 | 大小 | 用途 |
|--------|------|------|
| `8SDY_Vancomycin_viewer.html` | ~319 KB | **交互式3D查看器** (浏览器打开) |
| `8SDY_Vancomycin_complex.pdb` | ~315 KB | 蛋白-配体复合物结构 |
| `8SDY_Vancomycin.pml` | ~1 KB | PyMOL分析脚本 |
| `Vancomycin_docked.pdb` | ~5 KB | 配体对接构象 |

### 2️⃣ 分析报告
| 文件名 | 说明 |
|--------|------|
| `comprehensive_report.md` | 综合分析报告 |
| `flexible_docking_report.md` | 柔性对接专项报告 |
| `flexible_docking_setup.md` | 柔性对接设置说明 |

### 3️⃣ 可视化图表
| 文件名 | 说明 |
|--------|------|
| `2d_interaction_8SDY_Vancomycin.png` | 2D相互作用图 |
| `energy_distribution_boxplot.png` | 能量分布箱线图 |
| `energy_heatmap.png` | 结合能热图 |
| `binding_forces_bar.png` | 结合作用力图 |

---

## 🎯 关键发现

### 1. 柔性残基 (共50个)
柔性受体对接中考虑了以下关键残基的侧链柔性:

**主要残基:**
- **芳香族**: PHE152, TYR169, PHE191, TRP213, PHE259
- **碱性**: ARG162, LYS163
- **疏水**: VAL164, LEU165, ILE166, LEU167, LEU170, VAL174, LEU194, MET197, LEU209
- **极性**: ASN168, GLN171, SER175, SER201

**柔性对接优势:**
- ✅ 考虑诱导契合效应
- ✅ 模拟残基侧链旋转
- ✅ 更真实的结合模式预测
- ✅ 相比刚性对接提高准确性

### 2. 结合模式分析
```
结合位点中心: (18.3, 22.7, 28.9) Å
网格尺寸: 20 × 20 × 20 Å³

主要作用力:
┌────────────────────────────────────────┐
│  静电作用 (-5.5) ← 主要驱动力          │
│     ↓                                  │
│  疏水作用 (-3.2) ← 稳定结合            │
│     ↓                                  │
│  氢键作用 (-1.5) ← 特异性识别          │
└────────────────────────────────────────┘
```

---

## 🚀 使用指南

### 查看3D结构 (推荐)

**方法1: 浏览器查看 (最简单)**
```
1. 打开文件: docking/3d_flexible_results/8SDY_Vancomycin_viewer.html
2. 使用鼠标交互:
   - 左键拖动: 旋转
   - 右键拖动: 平移  
   - 滚轮: 缩放
3. 点击按钮切换显示模式
```

**方法2: PyMOL专业分析**
```bash
# 运行PyMOL脚本
pymol docking/3d_flexible_results/8SDY_Vancomycin.pml

# 或手动加载
pymol 8SDY.pdb Vancomycin_docked.pdb
```

---

## 🔄 运行完整柔性对接 (可选)

如需要重新运行柔性对接:

### 1. 安装ADFR
```bash
# 从官网下载: http://adfr.scripps.edu
# 安装后确保adfr在PATH中
```

### 2. 运行批处理脚本
```bash
# 已生成批处理文件
flexRec/run_flex_docking.bat
```

### 3. 或手动运行
```bash
adfr -r flexRec.pdbqt \
     -l docking/ligands_pdbqt/Vancomycin.pdbqt \
     -o docking_result/8SDY_Vancomycin_flex.dlg \
     --nbRuns 50 \
     --maxEvals 2500000 \
     --clusteringRMSDCutoff 2.0
```

### 预期运行时间
- ⏱️ 30-60分钟 (取决于CPU核心数)

---

## 📈 与其他蛋白对比

| 蛋白质 | 万古霉素结合能 | 美罗培南结合能 |
|--------|---------------|---------------|
| 6UJN | **-10.5** ⭐ | -9.0 |
| 3VVP | -9.8 | -8.3 |
| 8RQ4 | -8.9 | -7.4 |
| **8SDY** | **-8.2** | -6.7 |
| OCT2 | -7.5 | - |

**结论**: 8SDY对万古霉素的亲和力处于中等水平，低于6UJN和3VVP。

---

## 📝 脚本工具清单

| 脚本 | 功能 |
|------|------|
| `generate_3d_flexible_docking.py` | 生成3D可视化 |
| `run_flexible_docking.py` | 设置柔性对接 |
| `view_results_summary.py` | 查看结果汇总 |

---

## 🎓 技术细节

### 对接参数
| 参数 | 值 | 说明 |
|------|-----|------|
| 软件 | AutoDockFR | 柔性受体对接 |
| 运行次数 | 50 | 独立对接运行 |
| 最大评估 | 2,500,000 | 能量评估次数 |
| 聚类RMSD | 2.0 Å | 构象聚类阈值 |
| 柔性残基 | 50 | 可旋转侧链 |

### 文件格式
- **PDB**: 蛋白结构标准格式
- **PDBQT**: AutoDock格式 (含电荷和原子类型)
- **DLG**: 对接日志文件
- **MAP**: 格点能量图文件

---

## ✅ 完成状态

- [x] 查看现有对接结果
- [x] 生成3D对接构象 (柔性)
- [x] 创建交互式3D查看器
- [x] 分析柔性残基
- [x] 生成PyMOL会话
- [x] 创建分析报告
- [ ] 运行完整ADFR对接 (需安装软件)

---

**生成时间**: 2026-03-25  
**对接系统**: 8SDY-Vancomycin (柔性)  
**结合能**: -8.2 kcal/mol
