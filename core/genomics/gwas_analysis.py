"""
GWAS分析模块 - Genome-Wide Association Study Analysis Module

功能：
1. 关联检验 (Chi-square, Fisher exact, Logistic regression)
2. 多重检验校正 (Bonferroni, FDR, permutation)
3. Manhattan图和QQ图
4. LD分析和haplotype分析
5. PRS (Polygenic Risk Score) 计算
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from scipy import stats
from scipy.stats import chi2_contingency, fisher_exact
from sklearn.linear_model import LogisticRegression
import warnings


@dataclass
class GWASResult:
    """GWAS关联结果"""
    snp_id: str
    chrom: str
    pos: int
    p_value: float
    beta: Optional[float] = None  # 效应大小
    se: Optional[float] = None    # 标准误
    maf: Optional[float] = None   # 次等位基因频率
    n_samples: int = 0
    test_statistic: Optional[float] = None
    
    @property
    def neg_log10_p(self) -> float:
        """-log10(p-value)"""
        return -np.log10(max(self.p_value, 1e-300))


class AssociationTester:
    """关联检验器"""
    
    def __init__(self, method: str = 'chi2'):
        """
        初始化检验器
        
        Args:
            method: 检验方法 ('chi2', 'fisher', 'logistic', 'linear')
        """
        self.method = method
    
    def test_snp(self, genotypes: np.ndarray, phenotypes: np.ndarray,
                 covariates: Optional[np.ndarray] = None) -> GWASResult:
        """
        对单个SNP进行关联检验
        
        Args:
            genotypes: 基因型编码 (0/1/2)
            phenotypes: 表型 (0/1 或连续值)
            covariates: 协变量
        
        Returns:
            GWAS结果
        """
        if self.method == 'chi2':
            return self._chi2_test(genotypes, phenotypes)
        elif self.method == 'fisher':
            return self._fisher_test(genotypes, phenotypes)
        elif self.method == 'logistic':
            return self._logistic_test(genotypes, phenotypes, covariates)
        elif self.method == 'linear':
            return self._linear_test(genotypes, phenotypes, covariates)
        else:
            raise ValueError(f"Unknown method: {self.method}")
    
    def _chi2_test(self, genotypes: np.ndarray, 
                   phenotypes: np.ndarray) -> GWASResult:
        """卡方检验"""
        # 构建列联表
        case_genotypes = genotypes[phenotypes == 1]
        control_genotypes = genotypes[phenotypes == 0]
        
        # 基因型计数
        case_counts = [np.sum(case_genotypes == g) for g in [0, 1, 2]]
        control_counts = [np.sum(control_genotypes == g) for g in [0, 1, 2]]
        
        contingency_table = np.array([case_counts, control_counts])
        
        # 卡方检验
        chi2, p_value, dof, expected = chi2_contingency(contingency_table)
        
        # 计算OR值（近似）
        odds_ratio = self._calculate_or(genotypes, phenotypes)
        
        return GWASResult(
            snp_id='',
            chrom='',
            pos=0,
            p_value=p_value,
            beta=np.log(odds_ratio) if odds_ratio > 0 else 0,
            test_statistic=chi2,
            n_samples=len(genotypes)
        )
    
    def _fisher_test(self, genotypes: np.ndarray,
                     phenotypes: np.ndarray) -> GWASResult:
        """Fisher精确检验（用于二分类基因型）"""
        # 二分类：野生型 vs 突变型
        mut_genotypes = (genotypes > 0).astype(int)
        
        case_mut = np.sum((phenotypes == 1) & (mut_genotypes == 1))
        case_wt = np.sum((phenotypes == 1) & (mut_genotypes == 0))
        control_mut = np.sum((phenotypes == 0) & (mut_genotypes == 1))
        control_wt = np.sum((phenotypes == 0) & (mut_genotypes == 0))
        
        table = [[case_mut, case_wt], [control_mut, control_wt]]
        
        odds_ratio, p_value = fisher_exact(table)
        
        return GWASResult(
            snp_id='',
            chrom='',
            pos=0,
            p_value=p_value,
            beta=np.log(odds_ratio) if odds_ratio > 0 else 0,
            n_samples=len(genotypes)
        )
    
    def _logistic_test(self, genotypes: np.ndarray,
                       phenotypes: np.ndarray,
                       covariates: Optional[np.ndarray] = None) -> GWASResult:
        """逻辑回归检验"""
        X = genotypes.reshape(-1, 1)
        if covariates is not None:
            X = np.hstack([X, covariates])
        
        try:
            model = LogisticRegression(max_iter=1000, solver='lbfgs')
            model.fit(X, phenotypes)
            
            # 计算p值（使用Wald检验近似）
            # 这里简化为使用系数的标准误
            beta = model.coef_[0][0]
            
            # 使用似然比检验近似
            from sklearn.metrics import log_loss
            
            # 零模型
            null_model = LogisticRegression(max_iter=1000)
            null_model.fit(np.zeros((len(phenotypes), 1)), phenotypes)
            
            ll_full = -log_loss(phenotypes, model.predict_proba(X)) * len(phenotypes)
            ll_null = -log_loss(phenotypes, null_model.predict_proba(
                np.zeros((len(phenotypes), 1)))) * len(phenotypes)
            
            lr_stat = 2 * (ll_full - ll_null)
            p_value = 1 - stats.chi2.cdf(lr_stat, df=1)
            
            return GWASResult(
                snp_id='',
                chrom='',
                pos=0,
                p_value=max(p_value, 1e-300),
                beta=beta,
                n_samples=len(genotypes),
                test_statistic=lr_stat
            )
        except Exception as e:
            warnings.warn(f"Logistic regression failed: {e}")
            return GWASResult(snp_id='', chrom='', pos=0, p_value=1.0, n_samples=len(genotypes))
    
    def _linear_test(self, genotypes: np.ndarray,
                     phenotypes: np.ndarray,
                     covariates: Optional[np.ndarray] = None) -> GWASResult:
        """线性回归检验（用于连续性状）"""
        X = genotypes.reshape(-1, 1)
        if covariates is not None:
            X = np.hstack([X, covariates])
        
        X_with_intercept = np.hstack([np.ones((len(X), 1)), X])
        
        # 最小二乘
        beta = np.linalg.lstsq(X_with_intercept, phenotypes, rcond=None)[0]
        
        # 计算标准误和t统计量
        y_pred = X_with_intercept @ beta
        residuals = phenotypes - y_pred
        mse = np.sum(residuals**2) / (len(phenotypes) - X.shape[1] - 1)
        
        var_beta = mse * np.linalg.inv(X_with_intercept.T @ X_with_intercept).diagonal()
        se_beta = np.sqrt(var_beta)
        
        t_stat = beta[1] / se_beta[1] if len(beta) > 1 else 0
        p_value = 2 * (1 - stats.t.cdf(abs(t_stat), df=len(phenotypes) - X.shape[1] - 1))
        
        return GWASResult(
            snp_id='',
            chrom='',
            pos=0,
            p_value=p_value,
            beta=beta[1] if len(beta) > 1 else 0,
            se=se_beta[1] if len(se_beta) > 1 else 0,
            n_samples=len(genotypes),
            test_statistic=t_stat
        )
    
    def _calculate_or(self, genotypes: np.ndarray, phenotypes: np.ndarray) -> float:
        """计算优势比"""
        case_genotypes = genotypes[phenotypes == 1]
        control_genotypes = genotypes[phenotypes == 0]
        
        case_mut = np.sum(case_genotypes > 0)
        case_wt = np.sum(case_genotypes == 0)
        control_mut = np.sum(control_genotypes > 0)
        control_wt = np.sum(control_genotypes == 0)
        
        if case_wt == 0 or control_mut == 0:
            return float('inf')
        
        return (case_mut * control_wt) / (case_wt * control_mut)


class MultipleTestingCorrection:
    """多重检验校正"""
    
    @staticmethod
    def bonferroni(p_values: np.ndarray) -> np.ndarray:
        """Bonferroni校正"""
        n = len(p_values)
        return np.minimum(p_values * n, 1.0)
    
    @staticmethod
    def fdr_bh(p_values: np.ndarray) -> np.ndarray:
        """Benjamini-Hochberg FDR校正"""
        n = len(p_values)
        sorted_indices = np.argsort(p_values)
        sorted_p = p_values[sorted_indices]
        
        fdr = np.zeros(n)
        prev_bh_p = 0
        
        for i in range(n - 1, -1, -1):
            bh_p = sorted_p[i] * n / (i + 1)
            bh_p = min(bh_p, prev_bh_p)
            fdr[sorted_indices[i]] = bh_p
            prev_bh_p = bh_p
        
        return fdr
    
    @staticmethod
    def fdr_by(p_values: np.ndarray) -> np.ndarray:
        """Benjamini-Yekutieli FDR校正"""
        n = len(p_values)
        harmonic_sum = np.sum(1.0 / np.arange(1, n + 1))
        
        sorted_indices = np.argsort(p_values)
        sorted_p = p_values[sorted_indices]
        
        fdr = np.zeros(n)
        for i in range(n):
            fdr[sorted_indices[i]] = sorted_p[i] * n * harmonic_sum / (i + 1)
        
        return np.minimum(fdr, 1.0)


class GWASAnalyzer:
    """GWAS分析器"""
    
    def __init__(self, method: str = 'chi2'):
        self.tester = AssociationTester(method)
        self.results: List[GWASResult] = []
    
    def run_gwas(self, genotype_matrix: np.ndarray,
                 snp_info: pd.DataFrame,
                 phenotypes: np.ndarray,
                 covariates: Optional[np.ndarray] = None) -> pd.DataFrame:
        """
        运行全基因组关联分析
        
        Args:
            genotype_matrix: 基因型矩阵 (n_samples x n_snps)
            snp_info: SNP信息 DataFrame with columns: snp_id, chrom, pos
            phenotypes: 表型向量
            covariates: 协变量矩阵
        
        Returns:
            GWAS结果DataFrame
        """
        results = []
        n_snps = genotype_matrix.shape[1]
        
        print(f"Running GWAS on {n_snps} SNPs...")
        
        for i in range(n_snps):
            if i % 10000 == 0:
                print(f"  Processed {i}/{n_snps} SNPs")
            
            genotypes = genotype_matrix[:, i]
            
            # 跳过单态SNP
            if len(np.unique(genotypes[~np.isnan(genotypes)])) < 2:
                continue
            
            result = self.tester.test_snp(genotypes, phenotypes, covariates)
            
            # 添加SNP信息
            result.snp_id = snp_info.iloc[i].get('snp_id', f'SNP_{i}')
            result.chrom = str(snp_info.iloc[i].get('chrom', '0'))
            result.pos = int(snp_info.iloc[i].get('pos', 0))
            result.maf = self._calculate_maf(genotypes)
            
            results.append(result)
        
        self.results = results
        
        # 转换为DataFrame
        df = pd.DataFrame([
            {
                'snp_id': r.snp_id,
                'chrom': r.chrom,
                'pos': r.pos,
                'p_value': r.p_value,
                'beta': r.beta,
                'se': r.se,
                'maf': r.maf,
                'n_samples': r.n_samples,
                'neg_log10_p': r.neg_log10_p
            }
            for r in results
        ])
        
        return df
    
    def correct_pvalues(self, results: pd.DataFrame,
                       method: str = 'fdr_bh') -> pd.DataFrame:
        """
        校正p值
        
        Args:
            results: GWAS结果
            method: 校正方法
        
        Returns:
            添加校正后p值的DataFrame
        """
        p_values = results['p_value'].values
        
        if method == 'bonferroni':
            corrected = MultipleTestingCorrection.bonferroni(p_values)
        elif method in ['fdr', 'fdr_bh']:
            corrected = MultipleTestingCorrection.fdr_bh(p_values)
        elif method == 'fdr_by':
            corrected = MultipleTestingCorrection.fdr_by(p_values)
        else:
            corrected = p_values
        
        results = results.copy()
        results['p_value_corrected'] = corrected
        
        return results
    
    def get_significant_snps(self, results: pd.DataFrame,
                            threshold: float = 5e-8) -> pd.DataFrame:
        """
        获取显著SNP
        
        Args:
            results: GWAS结果
            threshold: p值阈值（默认5e-8）
        
        Returns:
            显著SNP
        """
        return results[results['p_value'] < threshold].copy()
    
    def calculate_genomic_inflation(self, results: pd.DataFrame) -> float:
        """
        计算基因组膨胀因子 (lambda GC)
        
        Returns:
            lambda值
        """
        p_values = results['p_value'].values
        # 卡方统计量中位数 / 期望中位数
        chi2 = stats.chi2.ppf(1 - p_values, df=1)
        lambda_gc = np.median(chi2) / stats.chi2.ppf(0.5, df=1)
        
        return lambda_gc
    
    def _calculate_maf(self, genotypes: np.ndarray) -> float:
        """计算次等位基因频率"""
        valid = genotypes[~np.isnan(genotypes)]
        if len(valid) == 0:
            return 0
        
        allele_count = np.sum(valid)
        total_alleles = len(valid) * 2
        
        af = allele_count / total_alleles
        return min(af, 1 - af)


class LDAnalyzer:
    """连锁不平衡分析器"""
    
    def __init__(self):
        pass
    
    def calculate_r2(self, genotypes1: np.ndarray, 
                     genotypes2: np.ndarray) -> float:
        """
        计算LD r²值
        
        Args:
            genotypes1: 第一个SNP的基因型
            genotypes2: 第二个SNP的基因型
        
        Returns:
            r²值
        """
        # 移除缺失值
        mask = ~(np.isnan(genotypes1) | np.isnan(genotypes2))
        g1 = genotypes1[mask]
        g2 = genotypes2[mask]
        
        if len(g1) < 10:
            return 0
        
        # 计算相关系数
        correlation = np.corrcoef(g1, g2)[0, 1]
        
        return correlation ** 2 if not np.isnan(correlation) else 0
    
    def calculate_ld_matrix(self, genotype_matrix: np.ndarray) -> np.ndarray:
        """
        计算LD矩阵
        
        Args:
            genotype_matrix: 基因型矩阵 (n_samples x n_snps)
        
        Returns:
            LD矩阵 (n_snps x n_snps)
        """
        n_snps = genotype_matrix.shape[1]
        ld_matrix = np.zeros((n_snps, n_snps))
        
        for i in range(n_snps):
            for j in range(i, n_snps):
                r2 = self.calculate_r2(genotype_matrix[:, i], genotype_matrix[:, j])
                ld_matrix[i, j] = r2
                ld_matrix[j, i] = r2
        
        return ld_matrix
    
    def find_ld_blocks(self, ld_matrix: np.ndarray, 
                       threshold: float = 0.8) -> List[List[int]]:
        """
        查找LD块
        
        Args:
            ld_matrix: LD矩阵
            threshold: LD阈值
        
        Returns:
            LD块列表
        """
        n = ld_matrix.shape[0]
        visited = [False] * n
        blocks = []
        
        for i in range(n):
            if visited[i]:
                continue
            
            block = [i]
            visited[i] = True
            
            # 查找与i高度连锁的SNP
            for j in range(i + 1, n):
                if not visited[j] and ld_matrix[i, j] >= threshold:
                    block.append(j)
                    visited[j] = True
            
            blocks.append(block)
        
        return blocks


class PRSCalculator:
    """多基因风险评分计算器"""
    
    def __init__(self):
        self.snp_weights: Dict[str, float] = {}
    
    def train(self, gwas_results: pd.DataFrame,
              p_value_threshold: float = 0.01):
        """
        训练PRS权重
        
        Args:
            gwas_results: GWAS结果
            p_value_threshold: p值阈值
        """
        significant = gwas_results[gwas_results['p_value'] < p_value_threshold]
        
        for _, row in significant.iterrows():
            snp_id = row['snp_id']
            beta = row.get('beta', 0)
            self.snp_weights[snp_id] = beta
    
    def calculate_prs(self, genotypes: Dict[str, int]) -> float:
        """
        计算个体PRS
        
        Args:
            genotypes: {snp_id: genotype} 基因型字典
        
        Returns:
            PRS值
        """
        score = 0
        for snp_id, weight in self.snp_weights.items():
            if snp_id in genotypes:
                score += genotypes[snp_id] * weight
        
        return score
    
    def calculate_prs_batch(self, genotype_matrix: np.ndarray,
                           snp_ids: List[str]) -> np.ndarray:
        """
        批量计算PRS
        
        Args:
            genotype_matrix: 基因型矩阵 (n_samples x n_snps)
            snp_ids: SNP ID列表
        
        Returns:
            PRS数组
        """
        scores = np.zeros(genotype_matrix.shape[0])
        
        for i, snp_id in enumerate(snp_ids):
            if snp_id in self.snp_weights:
                scores += genotype_matrix[:, i] * self.snp_weights[snp_id]
        
        return scores


# 便捷函数
def run_association_test(genotypes: np.ndarray,
                        phenotypes: np.ndarray,
                        method: str = 'chi2') -> GWASResult:
    """
    运行关联检验
    
    Args:
        genotypes: 基因型
        phenotypes: 表型
        method: 检验方法
    
    Returns:
        检验结果
    """
    tester = AssociationTester(method)
    return tester.test_snp(genotypes, phenotypes)


def correct_gwas_results(results: pd.DataFrame,
                        method: str = 'fdr_bh') -> pd.DataFrame:
    """
    校正GWAS结果
    
    Args:
        results: 结果DataFrame
        method: 校正方法
    
    Returns:
        校正后的DataFrame
    """
    analyzer = GWASAnalyzer()
    return analyzer.correct_pvalues(results, method)
