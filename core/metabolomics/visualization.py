"""
可视化模块 - Metabolomics Visualization

功能：
1. 得分图 (Score Plot)
2. 载荷图 (Loading Plot)
3. 火山图 (Volcano Plot)
4. 热图 (Heatmap)
5. 色谱图 (Chromatogram)
"""

import base64
import io
import logging
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)

# 尝试导入 matplotlib
try:
    import matplotlib
    matplotlib.use('Agg')  # 无头模式
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.colors import LinearSegmentedColormap
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("matplotlib not available, visualization limited")


class MetabolomicsVisualizer:
    """
    代谢组学可视化器
    
    生成各种分析图表，支持导出为图片或Base64。
    """
    
    def __init__(self, style: str = 'seaborn-v0_8-whitegrid'):
        self.style = style
        
        if MATPLOTLIB_AVAILABLE:
            try:
                plt.style.use(style)
            except:
                pass
        
        logger.info("MetabolomicsVisualizer initialized")
    
    def plot_score(
        self,
        scores: np.ndarray,
        labels: Optional[np.ndarray] = None,
        groups: Optional[List[str]] = None,
        component_x: int = 0,
        component_y: int = 1,
        explained_var: Optional[np.ndarray] = None,
        title: str = "Score Plot",
        figsize: Tuple[int, int] = (8, 6)
    ) -> str:
        """
        绘制得分图
        
        Args:
            scores: 得分矩阵 (n_samples, n_components)
            labels: 样本标签 (0/1)
            groups: 组名列表
            component_x: X轴成分
            component_y: Y轴成分
            explained_var: 解释方差比例
            title: 图表标题
            figsize: 图大小
            
        Returns:
            str: Base64编码的PNG图片
        """
        if not MATPLOTLIB_AVAILABLE:
            return ""
        
        fig, ax = plt.subplots(figsize=figsize)
        
        # 颜色方案
        colors = ['#3b82f6', '#ef4444']  # 蓝、红
        markers = ['o', 's']
        
        if labels is not None:
            unique_labels = np.unique(labels)
            for i, label in enumerate(unique_labels):
                mask = labels == label
                group_name = groups[i] if groups and i < len(groups) else f'Group {label}'
                ax.scatter(
                    scores[mask, component_x],
                    scores[mask, component_y],
                    c=colors[i % len(colors)],
                    marker=markers[i % len(markers)],
                    s=100,
                    alpha=0.7,
                    edgecolors='white',
                    linewidth=1,
                    label=group_name
                )
            ax.legend()
        else:
            ax.scatter(
                scores[:, component_x],
                scores[:, component_y],
                c='#3b82f6',
                s=100,
                alpha=0.7
            )
        
        # 轴标签
        xlabel = f'Component {component_x + 1}'
        ylabel = f'Component {component_y + 1}'
        
        if explained_var is not None:
            xlabel += f' ({explained_var[component_x]*100:.1f}%)'
            ylabel += f' ({explained_var[component_y]*100:.1f}%)'
        
        ax.set_xlabel(xlabel, fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        
        # 添加网格
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.axhline(y=0, color='k', linestyle='-', linewidth=0.5)
        ax.axvline(x=0, color='k', linestyle='-', linewidth=0.5)
        
        return self._fig_to_base64(fig)
    
    def plot_volcano(
        self,
        log2fc: np.ndarray,
        p_values: np.ndarray,
        feature_names: Optional[List[str]] = None,
        fc_threshold: float = 1.0,
        p_threshold: float = 0.05,
        title: str = "Volcano Plot",
        figsize: Tuple[int, int] = (10, 8)
    ) -> str:
        """
        绘制火山图
        
        Args:
            log2fc: log2 Fold Change
            p_values: p值
            feature_names: 特征名称
            fc_threshold: FC阈值（log2）
            p_threshold: p值阈值
            title: 图表标题
            figsize: 图大小
            
        Returns:
            str: Base64编码的PNG图片
        """
        if not MATPLOTLIB_AVAILABLE:
            return ""
        
        fig, ax = plt.subplots(figsize=figsize)
        
        # -log10(p)
        log_p = -np.log10(p_values)
        log_p[np.isinf(log_p)] = 300  # 处理p=0的情况
        
        # 分类
        up = (log2fc > fc_threshold) & (p_values < p_threshold)
        down = (log2fc < -fc_threshold) & (p_values < p_threshold)
        not_sig = ~up & ~down
        
        # 绘制
        ax.scatter(log2fc[not_sig], log_p[not_sig], c='gray', s=20, alpha=0.5, label='Not significant')
        ax.scatter(log2fc[up], log_p[up], c='#ef4444', s=50, alpha=0.7, label='Up-regulated')
        ax.scatter(log2fc[down], log_p[down], c='#3b82f6', s=50, alpha=0.7, label='Down-regulated')
        
        # 阈值线
        ax.axhline(y=-np.log10(p_threshold), color='gray', linestyle='--', linewidth=1, alpha=0.5)
        ax.axvline(x=fc_threshold, color='gray', linestyle='--', linewidth=1, alpha=0.5)
        ax.axvline(x=-fc_threshold, color='gray', linestyle='--', linewidth=1, alpha=0.5)
        
        # 标签
        ax.set_xlabel('log2(Fold Change)', fontsize=12)
        ax.set_ylabel('-log10(p-value)', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3, linestyle='--')
        
        # 标注重要特征
        if feature_names:
            for i, name in enumerate(feature_names):
                if up[i] or down[i]:
                    if p_values[i] < 0.001:  # 只标注极显著的
                        ax.annotate(name, (log2fc[i], log_p[i]), fontsize=8, alpha=0.7)
        
        return self._fig_to_base64(fig)
    
    def plot_chromatogram(
        self,
        time: np.ndarray,
        intensity: np.ndarray,
        peaks: Optional[List[Dict]] = None,
        title: str = "Chromatogram",
        xlabel: str = "Retention Time (min)",
        ylabel: str = "Intensity",
        figsize: Tuple[int, int] = (12, 6)
    ) -> str:
        """
        绘制色谱图
        
        Args:
            time: 时间数组
            intensity: 强度数组
            peaks: 峰列表 [{'rt': x, 'rt_start': x, 'rt_end': x, 'height': x}]
            title: 图表标题
            xlabel: X轴标签
            ylabel: Y轴标签
            figsize: 图大小
            
        Returns:
            str: Base64编码的PNG图片
        """
        if not MATPLOTLIB_AVAILABLE:
            return ""
        
        fig, ax = plt.subplots(figsize=figsize)
        
        # 绘制色谱图
        ax.plot(time, intensity, color='#3b82f6', linewidth=1)
        ax.fill_between(time, intensity, alpha=0.3, color='#3b82f6')
        
        # 标记峰
        if peaks:
            for peak in peaks:
                rt = peak.get('rt', 0)
                height = peak.get('height', 0)
                
                # 峰顶点标记
                ax.plot(rt, height, 'r^', markersize=8)
                
                # 峰边界
                rt_start = peak.get('rt_start', rt)
                rt_end = peak.get('rt_end', rt)
                ax.axvspan(rt_start, rt_end, alpha=0.1, color='red')
        
        ax.set_xlabel(xlabel, fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, linestyle='--')
        
        # 科学计数法
        ax.ticklabel_format(style='sci', axis='y', scilimits=(0,0))
        
        return self._fig_to_base64(fig)
    
    def plot_heatmap(
        self,
        data: np.ndarray,
        row_labels: Optional[List[str]] = None,
        col_labels: Optional[List[str]] = None,
        title: str = "Heatmap",
        cmap: str = 'RdYlBu_r',
        figsize: Tuple[int, int] = (10, 8)
    ) -> str:
        """
        绘制热图
        
        Args:
            data: 数据矩阵
            row_labels: 行标签
            col_labels: 列标签
            title: 图表标题
            cmap: 颜色映射
            figsize: 图大小
            
        Returns:
            str: Base64编码的PNG图片
        """
        if not MATPLOTLIB_AVAILABLE:
            return ""
        
        fig, ax = plt.subplots(figsize=figsize)
        
        # Z-score标准化
        data_norm = (data - np.mean(data, axis=0)) / (np.std(data, axis=0) + 1e-10)
        
        im = ax.imshow(data_norm, cmap=cmap, aspect='auto')
        
        # 设置标签
        if row_labels:
            ax.set_yticks(range(len(row_labels)))
            ax.set_yticklabels(row_labels, fontsize=8)
        
        if col_labels:
            ax.set_xticks(range(len(col_labels)))
            ax.set_xticklabels(col_labels, fontsize=8, rotation=90)
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        
        # 颜色条
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Z-score', fontsize=10)
        
        return self._fig_to_base64(fig)
    
    def plot_loading(
        self,
        loadings: np.ndarray,
        feature_names: Optional[List[str]] = None,
        component_x: int = 0,
        component_y: int = 1,
        top_n: int = 10,
        title: str = "Loading Plot",
        figsize: Tuple[int, int] = (8, 8)
    ) -> str:
        """
        绘制载荷图
        
        Args:
            loadings: 载荷矩阵 (n_features, n_components)
            feature_names: 特征名称
            component_x: X轴成分
            component_y: Y轴成分
            top_n: 标注前N个特征
            title: 图表标题
            figsize: 图大小
            
        Returns:
            str: Base64编码的PNG图片
        """
        if not MATPLOTLIB_AVAILABLE:
            return ""
        
        fig, ax = plt.subplots(figsize=figsize)
        
        # 计算距离（用于选择重要特征）
        distances = np.sqrt(loadings[:, component_x]**2 + loadings[:, component_y]**2)
        top_indices = np.argsort(distances)[-top_n:]
        
        # 绘制所有载荷
        ax.scatter(loadings[:, component_x], loadings[:, component_y], 
                  c='gray', s=20, alpha=0.5)
        
        # 高亮重要特征
        ax.scatter(loadings[top_indices, component_x], 
                  loadings[top_indices, component_y],
                  c='red', s=50, alpha=0.7)
        
        # 标注
        if feature_names:
            for idx in top_indices:
                ax.annotate(feature_names[idx], 
                           (loadings[idx, component_x], loadings[idx, component_y]),
                           fontsize=8, alpha=0.7)
        
        # 参考线
        ax.axhline(y=0, color='k', linestyle='-', linewidth=0.5)
        ax.axvline(x=0, color='k', linestyle='-', linewidth=0.5)
        
        # 单位圆
        circle = plt.Circle((0, 0), 1, fill=False, color='gray', linestyle='--', alpha=0.5)
        ax.add_patch(circle)
        
        ax.set_xlabel(f'Loading {component_x + 1}', fontsize=12)
        ax.set_ylabel(f'Loading {component_y + 1}', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, linestyle='--')
        ax.set_aspect('equal')
        
        return self._fig_to_base64(fig)
    
    def plot_permutation_test(
        self,
        original_q2: float,
        permuted_q2: List[float],
        title: str = "Permutation Test",
        figsize: Tuple[int, int] = (8, 6)
    ) -> str:
        """
        绘制置换检验图
        
        Args:
            original_q2: 原始Q2
            permuted_q2: 置换Q2列表
            title: 图表标题
            figsize: 图大小
            
        Returns:
            str: Base64编码的PNG图片
        """
        if not MATPLOTLIB_AVAILABLE:
            return ""
        
        fig, ax = plt.subplots(figsize=figsize)
        
        # 直方图
        ax.hist(permuted_q2, bins=20, color='gray', alpha=0.5, edgecolor='black')
        
        # 原始值
        ax.axvline(original_q2, color='red', linestyle='--', linewidth=2, label=f'Original Q2: {original_q2:.3f}')
        
        ax.set_xlabel('Q2', fontsize=12)
        ax.set_ylabel('Frequency', fontsize=12)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3, linestyle='--')
        
        return self._fig_to_base64(fig)
    
    def _fig_to_base64(self, fig) -> str:
        """将Figure转换为Base64字符串"""
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)
        return img_base64


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=== 测试可视化模块 ===")
    
    if not MATPLOTLIB_AVAILABLE:
        print("❌ matplotlib not available")
        exit(0)
    
    visualizer = MetabolomicsVisualizer()
    
    # 测试数据
    np.random.seed(42)
    n_samples = 20
    
    # 得分图
    print("\n1. 生成得分图...")
    scores = np.random.randn(n_samples, 2)
    labels = np.array([0] * 10 + [1] * 10)
    score_img = visualizer.plot_score(
        scores, labels, groups=['Control', 'Treatment'],
        explained_var=np.array([0.45, 0.25]),
        title="PCA Score Plot"
    )
    print(f"   图片大小: {len(score_img)} bytes")
    
    # 火山图
    print("\n2. 生成火山图...")
    log2fc = np.random.randn(100) * 2
    p_values = np.random.uniform(0, 1, 100)
    p_values[:10] = 0.0001  # 一些显著的点
    volcano_img = visualizer.plot_volcano(log2fc, p_values)
    print(f"   图片大小: {len(volcano_img)} bytes")
    
    # 色谱图
    print("\n3. 生成色谱图...")
    time = np.linspace(0, 30, 3000)
    intensity = np.exp(-((time - 15) / 5) ** 2) * 1000 + np.random.randn(3000) * 50
    peaks = [
        {'rt': 10, 'rt_start': 9, 'rt_end': 11, 'height': 800},
        {'rt': 20, 'rt_start': 19, 'rt_end': 21, 'height': 600}
    ]
    chrom_img = visualizer.plot_chromatogram(time, intensity, peaks)
    print(f"   图片大小: {len(chrom_img)} bytes")
    
    print("\n✅ 所有图表生成成功!")
