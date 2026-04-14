"""
多组学数据整合 - Multi-Omics Integration

功能：
1. 数据标准化
2. 特征对齐
3. 联合降维
4. 整合分析
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

# 尝试导入 sklearn，失败时使用 numpy 实现
try:
    from sklearn.preprocessing import StandardScaler
    from sklearn.decomposition import PCA
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class OmicsDataset:
    """组学数据集"""
    name: str  # 'metabolomics', 'proteomics', 'genomics', 'lipidomics'
    data: np.ndarray  # 样本 x 特征
    features: List[str]  # 特征名称
    samples: List[str]  # 样本名称
    
    @property
    def n_samples(self) -> int:
        return len(self.samples)
    
    @property
    def n_features(self) -> int:
        return len(self.features)


class MultiOmicsIntegrator:
    """
    多组学数据整合器
    
    整合代谢组学、蛋白质组学、基因组学、脂质组学数据。
    """
    
    def __init__(self):
        self.datasets: Dict[str, OmicsDataset] = {}
        self.scalers: Dict[str, StandardScaler] = {}
        self.logger = logging.getLogger(__name__)
    
    def add_dataset(self, dataset: OmicsDataset):
        """添加组学数据集"""
        self.datasets[dataset.name] = dataset
        self.logger.info(f"Added dataset: {dataset.name} ({dataset.n_samples} samples, {dataset.n_features} features)")
    
    def normalize_data(self, method: str = 'standard') -> Dict[str, np.ndarray]:
        """
        数据标准化
        
        Args:
            method: 标准化方法 ('standard', 'minmax', 'none')
            
        Returns:
            Dict: 标准化后的数据
        """
        normalized = {}
        
        for name, dataset in self.datasets.items():
            if method == 'standard':
                # 手动实现标准化
                mean = np.mean(dataset.data, axis=0)
                std = np.std(dataset.data, axis=0, ddof=0)
                std[std == 0] = 1
                normalized[name] = (dataset.data - mean) / std
            elif method == 'minmax':
                min_val = np.min(dataset.data, axis=0)
                max_val = np.max(dataset.data, axis=0)
                range_val = max_val - min_val
                range_val[range_val == 0] = 1
                normalized[name] = (dataset.data - min_val) / range_val
            else:
                normalized[name] = dataset.data
        
        return normalized
    
    def integrate_pca(self, n_components: int = 2) -> Dict[str, Any]:
        """
        整合PCA分析
        
        将多个组学数据拼接后进行PCA。
        
        Args:
            n_components: 主成分数
            
        Returns:
            Dict: PCA结果
        """
        # 标准化
        normalized = self.normalize_data()
        
        # 拼接数据
        concatenated = np.hstack([normalized[name] for name in sorted(normalized.keys())])
        
        # PCA（使用 numpy 实现）
        # 中心化
        X_centered = concatenated - np.mean(concatenated, axis=0)
        
        # 计算协方差矩阵
        cov_matrix = np.cov(X_centered, rowvar=False)
        
        # 特征值分解
        eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)
        
        # 按特征值降序排序
        idx = np.argsort(eigenvalues)[::-1]
        eigenvalues = eigenvalues[idx]
        eigenvectors = eigenvectors[:, idx]
        
        # 选择前n个主成分
        components = eigenvectors[:, :n_components]
        
        # 计算得分
        scores = np.dot(X_centered, components)
        
        # 解释方差比例
        explained_variance_ratio = eigenvalues[:n_components] / np.sum(eigenvalues)
        
        # 记录特征来源
        feature_sources = []
        for name in sorted(normalized.keys()):
            feature_sources.extend([name] * normalized[name].shape[1])
        
        return {
            'scores': scores,
            'explained_variance_ratio': explained_variance_ratio,
            'components': components,
            'feature_sources': feature_sources,
            'n_components': n_components
        }
    
    def mofa_style_factorization(self, n_factors: int = 10) -> Dict[str, Any]:
        """
        MOFA风格的因子分解（简化版）
        
        学习跨组学的潜在因子。
        
        Args:
            n_factors: 因子数
            
        Returns:
            Dict: 因子分解结果
        """
        # 简化实现：对每个组学分别进行SVD
        factors = {}
        
        for name, dataset in self.datasets.items():
            # 标准化（手动实现）
            mean = np.mean(dataset.data, axis=0)
            std = np.std(dataset.data, axis=0, ddof=0)
            std[std == 0] = 1
            data_scaled = (dataset.data - mean) / std
            
            # SVD
            U, S, Vt = np.linalg.svd(data_scaled, full_matrices=False)
            
            factors[name] = {
                'sample_factors': U[:, :n_factors],
                'feature_factors': Vt[:n_factors, :].T,
                'variance_explained': (S[:n_factors] ** 2) / np.sum(S ** 2)
            }
        
        return factors
    
    def get_common_samples(self) -> List[str]:
        """获取各组学共有的样本"""
        if not self.datasets:
            return []
        
        common = set(self.datasets[list(self.datasets.keys())[0]].samples)
        
        for dataset in self.datasets.values():
            common &= set(dataset.samples)
        
        return list(common)
    
    def align_samples(self) -> Dict[str, OmicsDataset]:
        """对齐样本（保留共有样本）"""
        common_samples = self.get_common_samples()
        
        aligned = {}
        
        for name, dataset in self.datasets.items():
            # 获取共有样本的索引
            indices = [dataset.samples.index(s) for s in common_samples if s in dataset.samples]
            
            aligned[name] = OmicsDataset(
                name=dataset.name,
                data=dataset.data[indices],
                features=dataset.features,
                samples=common_samples
            )
        
        return aligned
    
    def calculate_data_completeness(self) -> Dict[str, Any]:
        """计算数据完整性"""
        if not self.datasets:
            return {}
        
        all_samples = set()
        for dataset in self.datasets.values():
            all_samples.update(dataset.samples)
        
        completeness = {}
        
        for sample in all_samples:
            available = []
            for name, dataset in self.datasets.items():
                if sample in dataset.samples:
                    available.append(name)
            
            completeness[sample] = available
        
        # 统计
        summary = {}
        for i in range(1, len(self.datasets) + 1):
            count = sum(1 for v in completeness.values() if len(v) == i)
            summary[f'{i}_omics'] = count
        
        return {
            'per_sample': completeness,
            'summary': summary
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=== 测试多组学整合器 ===")
    
    integrator = MultiOmicsIntegrator()
    
    # 创建模拟数据
    np.random.seed(42)
    n_samples = 10
    
    # 代谢组学数据
    integrator.add_dataset(OmicsDataset(
        name='metabolomics',
        data=np.random.randn(n_samples, 100),
        features=[f"M{i}" for i in range(100)],
        samples=[f"S{i}" for i in range(n_samples)]
    ))
    
    # 蛋白质组学数据
    integrator.add_dataset(OmicsDataset(
        name='proteomics',
        data=np.random.randn(n_samples, 50),
        features=[f"P{i}" for i in range(50)],
        samples=[f"S{i}" for i in range(n_samples)]
    ))
    
    # 整合PCA
    print("\n整合PCA:")
    pca_result = integrator.integrate_pca(n_components=2)
    print(f"  解释方差: {pca_result['explained_variance_ratio']}")
    print(f"  特征来源: {set(pca_result['feature_sources'])}")
    
    # 数据完整性
    print("\n数据完整性:")
    completeness = integrator.calculate_data_completeness()
    print(f"  汇总: {completeness['summary']}")
    
    print("\n✅ 测试完成!")
