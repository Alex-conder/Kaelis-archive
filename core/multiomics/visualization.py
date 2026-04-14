"""
多组学可视化 - Multi-Omics Visualization

功能：
1. 多组学热图
2. 相关性网络图
3. Sankey 图（组学流向）
4. 整合气泡图
"""

import base64
import io
import logging
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.patches import FancyBboxPatch
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

logger = logging.getLogger(__name__)


class MultiOmicsVisualizer:
    """多组学可视化器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def plot_multi_omics_heatmap(
        self,
        data_dict: Dict[str, np.ndarray],
        feature_names_dict: Dict[str, List[str]],
        sample_names: List[str],
        title: str = "Multi-Omics Heatmap",
        figsize: Tuple[int, int] = (14, 10)
    ) -> str:
        """
        绘制多组学热图
        
        Args:
            data_dict: {组学类型: 数据矩阵}
            feature_names_dict: {组学类型: 特征名列表}
            sample_names: 样本名
            title: 标题
            figsize: 图大小
            
        Returns:
            str: Base64图片
        """
        if not MATPLOTLIB_AVAILABLE:
            return ""
        
        n_omics = len(data_dict)
        fig, axes = plt.subplots(n_omics, 1, figsize=figsize)
        
        if n_omics == 1:
            axes = [axes]
        
        for idx, (omics_type, data) in enumerate(data_dict.items()):
            ax = axes[idx]
            
            # Z-score 标准化
            data_norm = (data - np.mean(data, axis=0)) / (np.std(data, axis=0) + 1e-10)
            
            # 绘制热图
            im = ax.imshow(data_norm.T, cmap='RdYlBu_r', aspect='auto', vmin=-2, vmax=2)
            
            ax.set_title(f"{omics_type}", fontsize=12, fontweight='bold')
            ax.set_xlabel('Samples')
            ax.set_ylabel('Features')
            
            # 设置刻度
            if idx == n_omics - 1:
                ax.set_xticks(range(len(sample_names)))
                ax.set_xticklabels(sample_names, rotation=90, fontsize=8)
            else:
                ax.set_xticks([])
            
            feature_names = feature_names_dict.get(omics_type, [])
            ax.set_yticks(range(len(feature_names)))
            ax.set_yticklabels(feature_names, fontsize=8)
            
            # 颜色条
            cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
            cbar.set_label('Z-score', fontsize=10)
        
        plt.suptitle(title, fontsize=14, fontweight='bold')
        plt.tight_layout()
        
        return self._fig_to_base64(fig)
    
    def plot_correlation_network(
        self,
        correlations: List[Dict],
        min_correlation: float = 0.5,
        title: str = "Cross-Omics Correlation Network",
        figsize: Tuple[int, int] = (12, 12)
    ) -> str:
        """
        绘制相关性网络图
        
        Args:
            correlations: 相关性列表
            min_correlation: 最小相关系数
            title: 标题
            figsize: 图大小
            
        Returns:
            str: Base64图片
        """
        if not MATPLOTLIB_AVAILABLE:
            return ""
        
        # 筛选强相关性
        strong_corr = [c for c in correlations if abs(c.get('correlation', 0)) >= min_correlation]
        
        if not strong_corr:
            return ""
        
        fig, ax = plt.subplots(figsize=figsize)
        
        # 收集节点
        nodes = {}
        omics_colors = {
            'metabolomics': '#3b82f6',
            'proteomics': '#ef4444',
            'genomics': '#10b981',
            'lipidomics': '#f59e0b'
        }
        
        for corr in strong_corr:
            source = corr.get('source', '')
            target = corr.get('target', '')
            omics_source = corr.get('omics_source', 'unknown')
            omics_target = corr.get('omics_target', 'unknown')
            
            if source not in nodes:
                nodes[source] = {'omics': omics_source, 'connections': 0}
            if target not in nodes:
                nodes[target] = {'omics': omics_target, 'connections': 0}
            
            nodes[source]['connections'] += 1
            nodes[target]['connections'] += 1
        
        # 计算节点位置（圆形布局）
        n_nodes = len(nodes)
        angles = np.linspace(0, 2*np.pi, n_nodes, endpoint=False)
        radius = 1
        
        positions = {}
        for i, (node, info) in enumerate(nodes.items()):
            x = radius * np.cos(angles[i])
            y = radius * np.sin(angles[i])
            positions[node] = (x, y)
        
        # 绘制边
        for corr in strong_corr:
            source = corr.get('source', '')
            target = corr.get('target', '')
            correlation = corr.get('correlation', 0)
            
            if source in positions and target in positions:
                x1, y1 = positions[source]
                x2, y2 = positions[target]
                
                # 颜色根据相关性正负
                color = '#ef4444' if correlation > 0 else '#3b82f6'
                
                # 线宽根据相关性强度
                lw = abs(correlation) * 3
                
                ax.plot([x1, x2], [y1, y2], color=color, alpha=0.6, linewidth=lw)
        
        # 绘制节点
        for node, (x, y) in positions.items():
            info = nodes[node]
            color = omics_colors.get(info['omics'], '#888888')
            size = 100 + info['connections'] * 50
            
            ax.scatter(x, y, s=size, c=color, alpha=0.8, edgecolors='white', linewidth=2)
            
            # 标签
            label_x = x * 1.15
            label_y = y * 1.15
            ax.annotate(node, (label_x, label_y), fontsize=8, ha='center')
        
        ax.set_xlim(-1.5, 1.5)
        ax.set_ylim(-1.5, 1.5)
        ax.set_aspect('equal')
        ax.axis('off')
        ax.set_title(title, fontsize=14, fontweight='bold')
        
        # 图例
        legend_elements = [
            mpatches.Patch(color=color, label=omics)
            for omics, color in omics_colors.items()
        ]
        ax.legend(handles=legend_elements, loc='upper right')
        
        return self._fig_to_base64(fig)
    
    def plot_omics_circos(
        self,
        correlations: List[Dict],
        omics_order: List[str],
        figsize: Tuple[int, int] = (10, 10)
    ) -> str:
        """
        绘制 Circos 风格的多组学关联图
        
        Args:
            correlations: 相关性数据
            omics_order: 组学类型顺序
            figsize: 图大小
            
        Returns:
            str: Base64图片
        """
        if not MATPLOTLIB_AVAILABLE:
            return ""
        
        fig, ax = plt.subplots(figsize=figsize)
        
        # 简化的 Circos 实现
        n_omics = len(omics_order)
        omics_colors = {
            'metabolomics': '#3b82f6',
            'proteomics': '#ef4444',
            'genomics': '#10b981',
            'lipidomics': '#f59e0b'
        }
        
        # 绘制扇形区域
        angles = np.linspace(0, 2*np.pi, n_omics + 1)
        
        for i, omics in enumerate(omics_order):
            theta1 = np.degrees(angles[i])
            theta2 = np.degrees(angles[i+1])
            
            wedge = mpatches.Wedge(
                (0, 0), 1, theta1, theta2,
                width=0.3,
                facecolor=omics_colors.get(omics, '#888888'),
                alpha=0.7,
                edgecolor='white',
                linewidth=2
            )
            ax.add_patch(wedge)
            
            # 标签
            mid_angle = (angles[i] + angles[i+1]) / 2
            label_x = 1.3 * np.cos(mid_angle)
            label_y = 1.3 * np.sin(mid_angle)
            ax.text(label_x, label_y, omics, fontsize=10, ha='center', fontweight='bold')
        
        ax.set_xlim(-1.5, 1.5)
        ax.set_ylim(-1.5, 1.5)
        ax.set_aspect('equal')
        ax.axis('off')
        ax.set_title('Multi-Omics Circos View', fontsize=14, fontweight='bold')
        
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
    
    print("=== 测试多组学可视化 ===")
    
    if not MATPLOTLIB_AVAILABLE:
        print("❌ matplotlib not available")
        exit(0)
    
    viz = MultiOmicsVisualizer()
    
    # 测试数据
    np.random.seed(42)
    n_samples = 10
    
    data_dict = {
        'metabolomics': np.random.randn(n_samples, 5),
        'proteomics': np.random.randn(n_samples, 3)
    }
    
    feature_names = {
        'metabolomics': [f"M{i}" for i in range(5)],
        'proteomics': [f"P{i}" for i in range(3)]
    }
    
    sample_names = [f"S{i}" for i in range(n_samples)]
    
    # 测试热图
    print("\n1. 生成多组学热图...")
    img = viz.plot_multi_omics_heatmap(data_dict, feature_names, sample_names)
    print(f"   图片大小: {len(img)} bytes")
    
    # 测试相关性网络
    print("\n2. 生成相关性网络...")
    correlations = [
        {'source': 'M0', 'target': 'P0', 'omics_source': 'metabolomics', 'omics_target': 'proteomics', 'correlation': 0.8},
        {'source': 'M1', 'target': 'P1', 'omics_source': 'metabolomics', 'omics_target': 'proteomics', 'correlation': -0.7},
        {'source': 'M2', 'target': 'P0', 'omics_source': 'metabolomics', 'omics_target': 'proteomics', 'correlation': 0.6},
    ]
    
    img = viz.plot_correlation_network(correlations, min_correlation=0.5)
    print(f"   图片大小: {len(img)} bytes")
    
    print("\n✅ 测试完成!")
