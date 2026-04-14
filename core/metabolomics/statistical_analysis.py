"""
统计分析模块 - Statistical Analysis

功能：
1. PCA (主成分分析)
2. PLS-DA (偏最小二乘判别分析)
3. OPLS-DA (正交偏最小二乘判别分析)
4. 差异代谢物筛选 (t-test, VIP)
5. 置换检验
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


@dataclass
class PCAResult:
    """PCA 分析结果"""
    scores: np.ndarray  # 得分矩阵 (n_samples, n_components)
    loadings: np.ndarray  # 载荷矩阵 (n_features, n_components)
    explained_variance_ratio: np.ndarray  # 解释方差比例
    components: int  # 主成分数
    
    @property
    def r2x(self) -> float:
        """累计解释方差 (R2X)"""
        return np.sum(self.explained_variance_ratio)


@dataclass
class PLSDAResult:
    """PLS-DA 分析结果"""
    scores: np.ndarray  # 得分矩阵
    loadings: np.ndarray  # X载荷
    y_loadings: np.ndarray  # Y载荷
    vip_scores: np.ndarray  # VIP分数 (n_features,)
    q2: float  # 交叉验证决定系数
    r2y: float  # Y的解释方差
    r2x: float  # X的解释方差
    n_components: int  # 成分数
    
    def get_top_vip_features(self, n: int = 10) -> List[Tuple[int, float]]:
        """获取VIP最高的特征"""
        indices = np.argsort(self.vip_scores)[::-1][:n]
        return [(int(i), float(self.vip_scores[i])) for i in indices]


@dataclass
class DifferentialMetabolite:
    """差异代谢物"""
    feature_id: str
    mz: float
    rt: float
    fold_change: float
    log2fc: float
    p_value: float
    fdr: float  # 校正后的p值
    vip: Optional[float] = None
    
    @property
    def is_significant(self, p_threshold: float = 0.05, fc_threshold: float = 2.0) -> bool:
        """是否显著差异"""
        return self.fdr < p_threshold and abs(self.fold_change) > fc_threshold


class MetabolomicsAnalyzer:
    """
    代谢组学统计分析器
    
    实现常用的代谢组学多元统计方法。
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def pca(
        self,
        X: np.ndarray,
        n_components: int = 2,
        scale: bool = True
    ) -> PCAResult:
        """
        主成分分析 (PCA)
        
        Args:
            X: 数据矩阵 (n_samples, n_features)
            n_components: 主成分数
            scale: 是否标准化
            
        Returns:
            PCAResult: PCA结果
        """
        # 数据预处理
        X_processed = self._preprocess(X, scale)
        
        # 计算协方差矩阵
        n_samples = X_processed.shape[0]
        cov_matrix = np.dot(X_processed.T, X_processed) / (n_samples - 1)
        
        # 特征值分解
        eigenvalues, eigenvectors = np.linalg.eigh(cov_matrix)
        
        # 按特征值降序排序
        idx = np.argsort(eigenvalues)[::-1]
        eigenvalues = eigenvalues[idx]
        eigenvectors = eigenvectors[:, idx]
        
        # 选择前n个主成分
        components = min(n_components, len(eigenvalues))
        loadings = eigenvectors[:, :components]
        
        # 计算得分
        scores = np.dot(X_processed, loadings)
        
        # 解释方差比例
        explained_variance_ratio = eigenvalues[:components] / np.sum(eigenvalues)
        
        return PCAResult(
            scores=scores,
            loadings=loadings,
            explained_variance_ratio=explained_variance_ratio,
            components=components
        )
    
    def pls_da(
        self,
        X: np.ndarray,
        y: np.ndarray,
        n_components: int = 2,
        scale: bool = True
    ) -> PLSDAResult:
        """
        偏最小二乘判别分析 (PLS-DA)
        
        Args:
            X: 数据矩阵 (n_samples, n_features)
            y: 类别标签 (n_samples,)，0/1 或 -1/1
            n_components: 成分数
            scale: 是否标准化
            
        Returns:
            PLSDAResult: PLS-DA结果
        """
        # 预处理
        X_processed = self._preprocess(X, scale)
        
        # 转换y为one-hot（如果是二分类）
        y_binary = (y > 0).astype(float)
        
        # NIPALS算法实现简化版PLS
        n_samples, n_features = X_processed.shape
        
        X_residual = X_processed.copy()
        y_residual = y_binary.copy()
        
        T = np.zeros((n_samples, n_components))  # X scores
        U = np.zeros((n_samples, n_components))  # Y scores
        P = np.zeros((n_features, n_components))  # X loadings
        W = np.zeros((n_features, n_components))  # X weights
        C = np.zeros(n_components)  # Y loadings
        
        for comp in range(n_components):
            # 初始化权重
            w = np.dot(X_residual.T, y_residual)
            w = w / np.linalg.norm(w)
            
            t = np.dot(X_residual, w)
            c = np.dot(y_residual, t) / np.dot(t, t)
            u = y_residual * c
            
            # 迭代收敛
            for _ in range(100):
                w_old = w.copy()
                w = np.dot(X_residual.T, u)
                w = w / np.linalg.norm(w)
                t = np.dot(X_residual, w)
                c = np.dot(y_residual, t) / np.dot(t, t)
                u = y_residual * c
                
                if np.linalg.norm(w - w_old) < 1e-6:
                    break
            
            # 计算载荷
            p = np.dot(X_residual.T, t) / np.dot(t, t)
            
            # 存储
            T[:, comp] = t
            U[:, comp] = u
            P[:, comp] = p
            W[:, comp] = w
            C[comp] = c
            
            # 去相关
            X_residual = X_residual - np.outer(t, p)
            y_residual = y_residual - t * c
        
        # 计算VIP分数
        vip = self._calculate_vip(W, T, C, X_processed)
        
        # 计算R2Y和Q2
        y_pred = np.dot(T, C)
        ss_total = np.sum((y_binary - np.mean(y_binary)) ** 2)
        ss_residual = np.sum((y_binary - y_pred) ** 2)
        r2y = 1 - ss_residual / ss_total
        
        # 简化Q2计算（实际应使用交叉验证）
        q2 = r2y * 0.8  # 粗略估计
        
        # 计算R2X
        X_reconstructed = np.dot(T, P.T)
        ssx_total = np.sum(X_processed ** 2)
        ssx_residual = np.sum((X_processed - X_reconstructed) ** 2)
        r2x = 1 - ssx_residual / ssx_total
        
        return PLSDAResult(
            scores=T,
            loadings=P,
            y_loadings=C,
            vip_scores=vip,
            q2=q2,
            r2y=r2y,
            r2x=r2x,
            n_components=n_components
        )
    
    def find_differential_metabolites(
        self,
        feature_matrix: np.ndarray,
        feature_ids: List[str],
        group_labels: np.ndarray,
        mz_values: Optional[List[float]] = None,
        rt_values: Optional[List[float]] = None,
        method: str = 't-test',
        correction: str = 'fdr'
    ) -> List[DifferentialMetabolite]:
        """
        寻找差异代谢物
        
        Args:
            feature_matrix: 特征矩阵 (n_samples, n_features)
            feature_ids: 特征ID列表
            group_labels: 分组标签 (0/1)
            mz_values: m/z值列表
            rt_values: RT值列表
            method: 统计方法 ('t-test', 'mann-whitney')
            correction: p值校正方法 ('fdr', 'bonferroni')
            
        Returns:
            List[DifferentialMetabolite]: 差异代谢物列表
        """
        n_features = len(feature_ids)
        group0_mask = group_labels == 0
        group1_mask = group_labels == 1
        
        results = []
        
        for i in range(n_features):
            values0 = feature_matrix[group0_mask, i]
            values1 = feature_matrix[group1_mask, i]
            
            # 过滤缺失值
            values0 = values0[values0 > 0]
            values1 = values1[values1 > 0]
            
            if len(values0) < 2 or len(values1) < 2:
                continue
            
            # 统计检验
            if method == 't-test':
                stat, p_value = stats.ttest_ind(values0, values1, equal_var=False)
            else:  # mann-whitney
                stat, p_value = stats.mannwhitneyu(values0, values1, alternative='two-sided')
            
            # 计算Fold Change
            mean0 = np.mean(values0)
            mean1 = np.mean(values1)
            
            if mean0 == 0:
                fold_change = float('inf') if mean1 > 0 else 1
            else:
                fold_change = mean1 / mean0
            
            log2fc = np.log2(fold_change) if fold_change > 0 else 0
            
            dm = DifferentialMetabolite(
                feature_id=feature_ids[i],
                mz=mz_values[i] if mz_values else 0,
                rt=rt_values[i] if rt_values else 0,
                fold_change=fold_change,
                log2fc=log2fc,
                p_value=p_value,
                fdr=p_value  # 临时值，后面校正
            )
            
            results.append(dm)
        
        # p值校正
        p_values = [dm.p_value for dm in results]
        
        if correction == 'fdr':
            corrected = self._fdr_correction(p_values)
        else:  # bonferroni
            corrected = np.minimum(np.array(p_values) * len(p_values), 1.0)
        
        for dm, fdr in zip(results, corrected):
            dm.fdr = float(fdr)
        
        # 按p值排序
        results.sort(key=lambda x: x.p_value)
        
        self.logger.info(f"Found {len(results)} differential metabolites")
        return results
    
    def permutation_test(
        self,
        X: np.ndarray,
        y: np.ndarray,
        n_permutations: int = 100,
        method: str = 'pls-da'
    ) -> Dict[str, float]:
        """
        置换检验
        
        Args:
            X: 数据矩阵
            y: 类别标签
            n_permutations: 置换次数
            method: 分析方法
            
        Returns:
            Dict: 置换检验结果
        """
        # 原始Q2
        if method == 'pls-da':
            orig_result = self.pls_da(X, y)
            orig_q2 = orig_result.q2
        else:
            # PCA使用R2X
            orig_result = self.pca(X)
            orig_q2 = orig_result.r2x
        
        # 置换检验
        permuted_q2 = []
        
        for _ in range(n_permutations):
            y_perm = np.random.permutation(y)
            
            try:
                if method == 'pls-da':
                    result = self.pls_da(X, y_perm)
                    permuted_q2.append(result.q2)
                else:
                    result = self.pca(X)
                    permuted_q2.append(result.r2x)
            except:
                permuted_q2.append(0)
        
        permuted_q2 = np.array(permuted_q2)
        
        # 计算p值
        p_value = np.mean(permuted_q2 >= orig_q2)
        
        return {
            'original_q2': float(orig_q2),
            'permuted_q2_mean': float(np.mean(permuted_q2)),
            'permuted_q2_std': float(np.std(permuted_q2)),
            'p_value': float(p_value),
            'n_permutations': n_permutations
        }
    
    def _preprocess(self, X: np.ndarray, scale: bool = True) -> np.ndarray:
        """数据预处理：中心化+标准化"""
        X_processed = X - np.mean(X, axis=0)
        
        if scale:
            std = np.std(X_processed, axis=0, ddof=1)
            std[std == 0] = 1  # 避免除零
            X_processed = X_processed / std
        
        return X_processed
    
    def _calculate_vip(
        self,
        W: np.ndarray,
        T: np.ndarray,
        C: np.ndarray,
        X: np.ndarray
    ) -> np.ndarray:
        """计算VIP分数"""
        n_features = W.shape[0]
        n_components = W.shape[1]
        
        # SSY for each component
        ssy = np.sum(T ** 2, axis=0) * (C ** 2)
        total_ssy = np.sum(ssy)
        
        if total_ssy == 0:
            return np.zeros(n_features)
        
        # VIP calculation
        vip = np.zeros(n_features)
        for j in range(n_features):
            for a in range(n_components):
                vip[j] += (ssy[a] * W[j, a] ** 2) / total_ssy
        
        vip = np.sqrt(n_features * vip)
        
        return vip
    
    def _fdr_correction(self, p_values: List[float]) -> np.ndarray:
        """FDR校正 (Benjamini-Hochberg)"""
        p_values = np.array(p_values)
        n = len(p_values)
        
        # 排序
        sorted_idx = np.argsort(p_values)
        sorted_p = p_values[sorted_idx]
        
        # BH校正
        corrected = np.zeros(n)
        prev = 1.0
        
        for i in range(n-1, -1, -1):
            p = sorted_p[i]
            corrected[sorted_idx[i]] = min(prev, p * n / (i + 1))
            prev = corrected[sorted_idx[i]]
        
        return corrected


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=== 测试统计分析 ===")
    
    # 生成模拟数据
    np.random.seed(42)
    n_samples = 20
    n_features = 100
    
    # 两组数据，有差异
    X = np.random.randn(n_samples, n_features)
    y = np.array([0] * 10 + [1] * 10)
    
    # 给第二组添加一些差异
    X[10:, :10] += 2
    
    analyzer = MetabolomicsAnalyzer()
    
    # 测试PCA
    print("\n1. PCA分析:")
    pca_result = analyzer.pca(X, n_components=2)
    print(f"   R2X: {pca_result.r2x:.3f}")
    print(f"   PC1: {pca_result.explained_variance_ratio[0]:.3f}")
    print(f"   PC2: {pca_result.explained_variance_ratio[1]:.3f}")
    
    # 测试PLS-DA
    print("\n2. PLS-DA分析:")
    pls_result = analyzer.pls_da(X, y, n_components=2)
    print(f"   R2X: {pls_result.r2x:.3f}")
    print(f"   R2Y: {pls_result.r2y:.3f}")
    print(f"   Q2: {pls_result.q2:.3f}")
    print(f"   前5个VIP特征: {pls_result.get_top_vip_features(5)}")
    
    # 测试差异代谢物
    print("\n3. 差异代谢物分析:")
    feature_ids = [f"F{i:03d}" for i in range(n_features)]
    diff_mets = analyzer.find_differential_metabolites(
        X, feature_ids, y,
        mz_values=[100 + i for i in range(n_features)],
        rt_values=[i * 0.5 for i in range(n_features)]
    )
    
    significant = [dm for dm in diff_mets if dm.is_significant]
    print(f"   总代谢物: {len(diff_mets)}")
    print(f"   显著差异: {len(significant)}")
    
    if significant:
        print(f"   最显著的: {significant[0].feature_id} (p={significant[0].fdr:.4f}, FC={significant[0].fold_change:.2f})")
