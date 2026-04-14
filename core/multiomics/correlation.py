"""
跨组学相关性分析模块 - Cross-Omics Correlation Module

功能：
1. 配对样本相关性分析
2. 偏相关分析（控制协变量）
3. 典型相关分析 (CCA)
4. 稀疏CCA (sCCA)
5. 相关性网络构建
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from scipy import stats
from scipy.stats import pearsonr, spearmanr, kendalltau
from sklearn.cross_decomposition import CCA
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Lasso, LassoCV
import warnings


@dataclass
class CorrelationResult:
    """相关性分析结果"""
    feature_x: str
    feature_y: str
    correlation: float
    p_value: float
    method: str
    n_samples: int
    q_value: Optional[float] = None
    
    @property
    def is_significant(self, alpha: float = 0.05) -> bool:
        """判断是否显著"""
        p = self.q_value if self.q_value is not None else self.p_value
        return p < alpha


class CrossOmicsCorrelation:
    """跨组学相关性分析器"""
    
    def __init__(self, method: str = 'pearson'):
        """
        初始化
        
        Args:
            method: 相关方法 ('pearson', 'spearman', 'kendall')
        """
        self.method = method
        self.results: List[CorrelationResult] = []
    
    def correlate(self, data_x: pd.DataFrame, data_y: pd.DataFrame,
                  samples_x: Optional[List[str]] = None,
                  samples_y: Optional[List[str]] = None) -> pd.DataFrame:
        """
        计算两组学数据的相关性
        
        Args:
            data_x: 第一组学数据 (features x samples)
            data_y: 第二组学数据 (features x samples)
            samples_x: X的样本子集
            samples_y: Y的样本子集
        
        Returns:
            相关性结果DataFrame
        """
        # 对齐样本
        if samples_x is None:
            samples_x = list(data_x.columns)
        if samples_y is None:
            samples_y = list(data_y.columns)
        
        common_samples = list(set(samples_x) & set(samples_y))
        print(f"Common samples: {len(common_samples)}")
        
        if len(common_samples) < 3:
            raise ValueError("Need at least 3 common samples")
        
        # 提取数据
        x_data = data_x[common_samples].values
        y_data = data_y[common_samples].values
        
        features_x = data_x.index.tolist()
        features_y = data_y.index.tolist()
        
        results = []
        
        print(f"Computing correlations between {len(features_x)} and {len(features_y)} features...")
        
        for i, feat_x in enumerate(features_x):
            if i % 100 == 0:
                print(f"  Processed {i}/{len(features_x)} features")
            
            for j, feat_y in enumerate(features_y):
                corr, pval = self._compute_correlation(x_data[i], y_data[j])
                
                result = CorrelationResult(
                    feature_x=feat_x,
                    feature_y=feat_y,
                    correlation=corr,
                    p_value=pval,
                    method=self.method,
                    n_samples=len(common_samples)
                )
                results.append(result)
        
        self.results = results
        
        # 转换为DataFrame
        df = pd.DataFrame([
            {
                'feature_x': r.feature_x,
                'feature_y': r.feature_y,
                'correlation': r.correlation,
                'p_value': r.p_value,
                'n_samples': r.n_samples
            }
            for r in results
        ])
        
        # FDR校正
        df['q_value'] = self._fdr_correction(df['p_value'].values)
        
        return df
    
    def _compute_correlation(self, x: np.ndarray, 
                            y: np.ndarray) -> Tuple[float, float]:
        """计算两个向量的相关性"""
        # 处理缺失值
        mask = ~(np.isnan(x) | np.isnan(y))
        x_clean = x[mask]
        y_clean = y[mask]
        
        if len(x_clean) < 3:
            return 0, 1.0
        
        if self.method == 'pearson':
            return pearsonr(x_clean, y_clean)
        elif self.method == 'spearman':
            return spearmanr(x_clean, y_clean)
        elif self.method == 'kendall':
            return kendalltau(x_clean, y_clean)
        else:
            return pearsonr(x_clean, y_clean)
    
    def _fdr_correction(self, p_values: np.ndarray) -> np.ndarray:
        """Benjamini-Hochberg FDR校正"""
        n = len(p_values)
        sorted_idx = np.argsort(p_values)
        sorted_p = p_values[sorted_idx]
        
        fdr = np.zeros(n)
        prev_bh = 0
        
        for i in range(n - 1, -1, -1):
            bh_p = sorted_p[i] * n / (i + 1)
            bh_p = min(bh_p, prev_bh)
            fdr[sorted_idx[i]] = bh_p
            prev_bh = bh_p
        
        return fdr
    
    def get_significant_pairs(self, threshold: float = 0.05,
                              min_correlation: float = 0) -> pd.DataFrame:
        """
        获取显著相关对
        
        Args:
            threshold: q值阈值
            min_correlation: 最小相关系数
        
        Returns:
            显著相关对
        """
        df = pd.DataFrame([
            {
                'feature_x': r.feature_x,
                'feature_y': r.feature_y,
                'correlation': r.correlation,
                'p_value': r.p_value,
                'q_value': r.q_value,
            }
            for r in self.results
        ])
        
        sig = df[df['q_value'] < threshold]
        sig = sig[abs(sig['correlation']) >= min_correlation]
        
        return sig.sort_values('q_value')


class PartialCorrelation:
    """偏相关分析"""
    
    def __init__(self):
        pass
    
    def compute(self, x: np.ndarray, y: np.ndarray, 
                z: np.ndarray) -> Tuple[float, float]:
        """
        计算偏相关（控制z的影响）
        
        Args:
            x: 变量X
            y: 变量Y
            z: 控制变量（可以是多维）
        
        Returns:
            (偏相关系数, p值)
        """
        # 残差化X和Y
        x_resid = self._residualize(x, z)
        y_resid = self._residualize(y, z)
        
        # 计算残差的相关性
        return pearsonr(x_resid, y_resid)
    
    def _residualize(self, y: np.ndarray, x: np.ndarray) -> np.ndarray:
        """通过线性回归获取残差"""
        # 确保x是二维的
        if x.ndim == 1:
            x = x.reshape(-1, 1)
        
        # 添加截距
        x_with_intercept = np.hstack([np.ones((len(x), 1)), x])
        
        # 最小二乘
        beta = np.linalg.lstsq(x_with_intercept, y, rcond=None)[0]
        y_pred = x_with_intercept @ beta
        
        return y - y_pred


class CanonicalCorrelationAnalysis:
    """典型相关分析 (CCA)"""
    
    def __init__(self, n_components: int = 2):
        """
        初始化
        
        Args:
            n_components: 典型变量对数
        """
        self.n_components = n_components
        self.cca = CCA(n_components=n_components)
        self.scaler_x = StandardScaler()
        self.scaler_y = StandardScaler()
    
    def fit(self, X: np.ndarray, Y: np.ndarray):
        """
        拟合CCA模型
        
        Args:
            X: 第一组学数据 (n_samples x n_features_x)
            Y: 第二组学数据 (n_samples x n_features_y)
        """
        # 标准化
        X_scaled = self.scaler_x.fit_transform(X)
        Y_scaled = self.scaler_y.fit_transform(Y)
        
        # 拟合
        self.cca.fit(X_scaled, Y_scaled)
        
        return self
    
    def transform(self, X: np.ndarray, Y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """转换数据到典型变量空间"""
        X_scaled = self.scaler_x.transform(X)
        Y_scaled = self.scaler_y.transform(Y)
        
        return self.cca.transform(X_scaled, Y_scaled)
    
    def fit_transform(self, X: np.ndarray, 
                     Y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """拟合并转换"""
        self.fit(X, Y)
        return self.transform(X, Y)
    
    def canonical_correlations(self) -> np.ndarray:
        """获取典型相关系数"""
        return np.corrcoef(self.cca.x_scores_.T, self.cca.y_scores_.T).diagonal(
            offset=self.n_components
        )[:self.n_components]
    
    def get_loadings(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        获取载荷矩阵
        
        Returns:
            (X载荷, Y载荷)
        """
        x_loadings = pd.DataFrame(
            self.cca.x_loadings_,
            columns=[f'CC{i+1}' for i in range(self.n_components)]
        )
        y_loadings = pd.DataFrame(
            self.cca.y_loadings_,
            columns=[f'CC{i+1}' for i in range(self.n_components)]
        )
        
        return x_loadings, y_loadings


class SparseCCA:
    """稀疏CCA (使用L1正则化)"""
    
    def __init__(self, n_components: int = 2, alpha: float = 0.1):
        """
        初始化
        
        Args:
            n_components: 组件数
            alpha: L1正则化参数
        """
        self.n_components = n_components
        self.alpha = alpha
        self.x_weights = None
        self.y_weights = None
        self.scaler_x = StandardScaler()
        self.scaler_y = StandardScaler()
    
    def fit(self, X: np.ndarray, Y: np.ndarray):
        """拟合稀疏CCA"""
        # 标准化
        X_scaled = self.scaler_x.fit_transform(X)
        Y_scaled = self.scaler_y.fit_transform(Y)
        
        n = X.shape[0]
        
        # 迭代估计权重
        self.x_weights = np.zeros((X.shape[1], self.n_components))
        self.y_weights = np.zeros((Y.shape[1], self.n_components))
        
        for i in range(self.n_components):
            # 初始化
            u = np.random.randn(X.shape[1])
            v = np.random.randn(Y.shape[1])
            
            # 迭代
            for _ in range(100):
                # 固定v，更新u
                y_v = Y_scaled @ v
                u_new = self._sparse_regression(X_scaled, y_v)
                
                # 固定u，更新v
                x_u = X_scaled @ u_new
                v_new = self._sparse_regression(Y_scaled, x_u)
                
                # 检查收敛
                if np.allclose(u, u_new, atol=1e-6) and np.allclose(v, v_new, atol=1e-6):
                    break
                
                u, v = u_new, v_new
            
            self.x_weights[:, i] = u
            self.y_weights[:, i] = v
            
            # 去相关化以获取下一组件
            X_scaled = self._deflate(X_scaled, u)
            Y_scaled = self._deflate(Y_scaled, v)
        
        return self
    
    def _sparse_regression(self, X: np.ndarray, y: np.ndarray) -> np.ndarray:
        """使用Lasso进行稀疏回归"""
        lasso = Lasso(alpha=self.alpha, max_iter=2000, fit_intercept=False)
        lasso.fit(X, y)
        return lasso.coef_
    
    def _deflate(self, X: np.ndarray, w: np.ndarray) -> np.ndarray:
        """去相关化"""
        t = X @ w
        return X - np.outer(t, t) @ X / (t @ t)
    
    def transform(self, X: np.ndarray, Y: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """转换数据"""
        X_scaled = self.scaler_x.transform(X)
        Y_scaled = self.scaler_y.transform(Y)
        
        return X_scaled @ self.x_weights, Y_scaled @ self.y_weights


class CorrelationNetwork:
    """相关性网络构建"""
    
    def __init__(self, threshold: float = 0.5, p_threshold: float = 0.05):
        """
        初始化
        
        Args:
            threshold: 相关系数阈值
            p_threshold: p值阈值
        """
        self.threshold = threshold
        self.p_threshold = p_threshold
        self.edges: List[Dict] = []
        self.nodes: set = set()
    
    def build(self, correlations: pd.DataFrame):
        """
        构建网络
        
        Args:
            correlations: 相关性结果DataFrame
        """
        self.edges = []
        self.nodes = set()
        
        # 筛选边
        sig = correlations[
            (abs(correlations['correlation']) >= self.threshold) &
            (correlations['p_value'] < self.p_threshold)
        ]
        
        for _, row in sig.iterrows():
            self.edges.append({
                'source': row['feature_x'],
                'target': row['feature_y'],
                'weight': abs(row['correlation']),
                'correlation': row['correlation'],
                'p_value': row['p_value']
            })
            self.nodes.add(row['feature_x'])
            self.nodes.add(row['feature_y'])
    
    def get_network_stats(self) -> Dict:
        """获取网络统计"""
        from collections import defaultdict
        
        degree = defaultdict(int)
        for edge in self.edges:
            degree[edge['source']] += 1
            degree[edge['target']] += 1
        
        degrees = list(degree.values())
        
        return {
            'n_nodes': len(self.nodes),
            'n_edges': len(self.edges),
            'avg_degree': np.mean(degrees) if degrees else 0,
            'max_degree': max(degrees) if degrees else 0,
            'density': len(self.edges) / (len(self.nodes) * (len(self.nodes) - 1) / 2) 
                      if len(self.nodes) > 1 else 0
        }
    
    def to_cytoscape_format(self) -> Dict:
        """转换为Cytoscape格式"""
        nodes = [{'data': {'id': n, 'name': n}} for n in self.nodes]
        edges = [
            {
                'data': {
                    'source': e['source'],
                    'target': e['target'],
                    'weight': e['weight'],
                    'correlation': e['correlation']
                }
            }
            for e in self.edges
        ]
        
        return {'nodes': nodes, 'edges': edges}


# 便捷函数
def compute_cross_omics_correlation(data_x: pd.DataFrame,
                                    data_y: pd.DataFrame,
                                    method: str = 'pearson') -> pd.DataFrame:
    """
    计算跨组学相关性
    
    Args:
        data_x: 第一组学数据
        data_y: 第二组学数据
        method: 相关方法
    
    Returns:
        相关性结果
    """
    analyzer = CrossOmicsCorrelation(method=method)
    return analyzer.correlate(data_x, data_y)


def run_cca_analysis(X: np.ndarray, Y: np.ndarray,
                     n_components: int = 2) -> Dict:
    """
    运行CCA分析
    
    Args:
        X: 第一组学数据
        Y: 第二组学数据
        n_components: 组件数
    
    Returns:
        分析结果
    """
    cca = CanonicalCorrelationAnalysis(n_components=n_components)
    x_scores, y_scores = cca.fit_transform(X, Y)
    
    return {
        'x_scores': x_scores,
        'y_scores': y_scores,
        'canonical_correlations': cca.canonical_correlations(),
        'x_loadings': cca.get_loadings()[0],
        'y_loadings': cca.get_loadings()[1]
    }
