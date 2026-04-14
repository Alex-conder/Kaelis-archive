# 🧬 Kaelis 智流 - 代谢组学模块

## 模块概述

代谢组学专用模块，支持 mzML 格式质谱数据的完整分析流程，并与自进化引擎深度集成。

## 📁 文件结构

```
core/metabolomics/
├── __init__.py              # 模块初始化
├── mzml_parser.py           # mzML 文件解析（13.7KB）
├── feature_detection.py     # 峰检测与对齐（9.2KB）
├── statistical_analysis.py  # 统计分析（15.2KB）
├── visualization.py         # 可视化（15.3KB）
└── workflow.py              # 工作流集成（11.9KB）

api/routes/
└── metabolomics.py          # API 路由（7.9KB）

api/static/
└── metabolomics.html        # 前端界面（17.3KB）
```

## 🎯 核心功能

### 1. mzML 文件解析
- **流式解析**: 支持大文件（GB级别）
- **多线程安全**: 迭代器模式处理
- **信息提取**: TIC、BPC、XIC、MS1/MS2 谱图

```python
from core.metabolomics.mzml_parser import MZMLParser

parser = MZMLParser("data.mzML")

# 获取文件信息
info = parser.get_file_info()

# 提取总离子流色谱图
tic = parser.get_tic_chromatogram()

# 遍历所有谱图
for spectrum in parser.parse():
    print(f"RT: {spectrum.rt}, m/z: {len(spectrum.mz)}")
```

### 2. 峰检测
- **高斯平滑**: 噪声抑制
- **基线校正**: 自动基线估计
- **峰识别**: 基于二阶导数
- **峰参数**: RT、面积、高度、宽度

```python
from core.metabolomics.feature_detection import FeatureDetector

detector = FeatureDetector(min_peak_height=1000)
peaks = detector.detect_peaks(time, intensity)
```

### 3. 统计分析

#### PCA (主成分分析)
```python
from core.metabolomics.statistical_analysis import MetabolomicsAnalyzer

analyzer = MetabolomicsAnalyzer()
pca_result = analyzer.pca(feature_matrix, n_components=2)
print(f"R2X: {pca_result.r2x}")
```

#### PLS-DA (偏最小二乘判别分析)
```python
pls_result = analyzer.pls_da(X, y, n_components=2)
print(f"Q2: {pls_result.q2}, R2Y: {pls_result.r2y}")
print(f"VIP scores: {pls_result.vip_scores}")
```

#### 差异代谢物筛选
```python
diff_mets = analyzer.find_differential_metabolites(
    feature_matrix, feature_ids, group_labels,
    mz_values=mz_list, rt_values=rt_list
)

significant = [dm for dm in diff_mets if dm.is_significant]
```

#### 置换检验
```python
perm_result = analyzer.permutation_test(X, y, n_permutations=100)
print(f"P-value: {perm_result['p_value']}")
```

### 4. 可视化
- **得分图**: PCA/PLS-DA Score Plot
- **载荷图**: Loading Plot
- **火山图**: Volcano Plot
- **热图**: Heatmap
- **色谱图**: Chromatogram with peaks

```python
from core.metabolomics.visualization import MetabolomicsVisualizer

viz = MetabolomicsVisualizer()

# 得分图
img_base64 = viz.plot_score(scores, labels, groups=['Control', 'Treatment'])

# 火山图
img_base64 = viz.plot_volcano(log2fc, p_values)

# 色谱图
img_base64 = viz.plot_chromatogram(time, intensity, peaks)
```

### 5. 自进化集成

自动优化 PLS-DA 参数：

```python
from core.metabolomics.workflow import MetabolomicsWorkflow

workflow = MetabolomicsWorkflow(use_evolution=True)

# 将自动优化 n_components 和 scale 参数
results = workflow.compare_groups(
    feature_matrix, feature_ids, group_labels,
    group_names, mz_values, rt_values,
    use_self_evolution=True
)
```

## 📡 API 接口

### 基础接口

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/metabolomics/status` | GET | 模块状态 |
| `/api/metabolomics/files` | GET | 已上传文件列表 |
| `/api/metabolomics/upload` | POST | 上传 mzML 文件 |
| `/api/metabolomics/analyze` | POST | 分析文件 |
| `/api/metabolomics/quick-test` | GET | 快速测试 |

### 使用示例

```bash
# 快速测试（使用本地测试文件）
curl http://localhost:5000/api/metabolomics/quick-test

# 上传文件
curl -X POST -F "file=@sample.mzML" http://localhost:5000/api/metabolomics/upload

# 分析文件
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"filepath": "data/uploads/sample.mzML", "detect_peaks": true}' \
  http://localhost:5000/api/metabolomics/analyze
```

## 🖥️ 前端界面

访问 `http://localhost:5000/metabolomics.html`

功能：
- 文件拖拽上传
- 快速测试按钮（使用本地 mzML 文件）
- 色谱图展示
- 峰列表展示
- 文件信息统计

## 🧪 本地测试

测试文件已发现：`D:​​1250205_NEG_B44 (4).mzML` (1.27GB)

运行测试：
```bash
cd c:\Users\11526\OneDrive\Desktop
python -m pytest tests/test_metabolomics.py -v
```

或直接通过 Web 界面的"快速测试"按钮测试。

## 📊 分析流程

```
mzML 文件
    ↓
解析谱图 → TIC/BPC/XIC
    ↓
峰检测 → 峰列表
    ↓
峰对齐 → 特征矩阵
    ↓
统计分析
    ├── PCA
    ├── PLS-DA (自进化优化)
    ├── 差异代谢物
    └── 置换检验
    ↓
可视化
    ├── 得分图
    ├── 载荷图
    ├── 火山图
    └── 色谱图
    ↓
结果导出
```

## 🔧 依赖安装

```bash
pip install scipy matplotlib numpy
```

可选（用于高级功能）：
```bash
pip install pyopenms  # 更完整的质谱支持
```

## 🎯 与自进化引擎的集成

代谢组学模块与自进化引擎深度集成：

1. **参数优化**: PLS-DA 的 n_components 和 scale 参数自动优化
2. **评估标准**: Q2 > 0.5 and R2Y > 0.7
3. **策略选择**: 根据模型性能选择参数调整策略
4. **技能沉淀**: 优化的参数自动保存为技能

```python
# 在 workflow.py 中的集成示例
def _optimize_plsda(self, X, y):
    engine = SelfEvolvingEngine()
    
    def run_plsda(params):
        result = self.analyzer.pls_da(X, y, 
            n_components=int(params['n_components']),
            scale=params['scale']
        )
        return {'Q2': result.q2, 'R2Y': result.r2y}
    
    expectation = TaskExpectation(
        criteria="Q2 > 0.5 and R2Y > 0.7",
        evaluation_method="rule",
        target_confidence=0.8,
        max_iterations=5
    )
    
    record = engine.evolve(...)
    return self.analyzer.pls_da(X, y, **record.best_params)
```

---

**版本**: v1.0.0  
**状态**: ✅ 可用  
**最后更新**: 2026-04-06
