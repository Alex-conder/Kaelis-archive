"""
蛋白质组学分析 - Proteomics Analysis

功能：
1. 差异蛋白分析
2. 通路富集分析 (GO, KEGG)
3. 蛋白相互作用网络
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


@dataclass
class DifferentialProtein:
    """差异蛋白"""
    protein_accession: str
    protein_name: Optional[str]
    fold_change: float
    log2fc: float
    p_value: float
    fdr: float
    avg_intensity_group1: float
    avg_intensity_group2: float
    
    @property
    def is_significant(self, p_threshold: float = 0.05, fc_threshold: float = 1.5) -> bool:
        return self.fdr < p_threshold and abs(self.fold_change) > fc_threshold


@dataclass
class EnrichmentResult:
    """富集分析结果"""
    term_id: str
    term_name: str
    category: str  # GO: BP, CC, MF; or KEGG
    count: int
    total: int
    p_value: float
    fdr: float
    genes: List[str]
    
    @property
    def enrichment_ratio(self) -> float:
        return self.count / self.total if self.total > 0 else 0


class ProteomicsAnalyzer:
    """蛋白质组学分析器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # 模拟通路数据库（实际应用应加载真实数据库）
        self.mock_pathways = {
            'GO:0008150': {'name': 'biological_process', 'category': 'BP'},
            'GO:0005575': {'name': 'cellular_component', 'category': 'CC'},
            'GO:0003674': {'name': 'molecular_function', 'category': 'MF'},
            'KEGG:04110': {'name': 'Cell cycle', 'category': 'KEGG'},
            'KEGG:05200': {'name': 'Pathways in cancer', 'category': 'KEGG'},
        }
    
    def find_differential_proteins(
        self,
        protein_matrix: np.ndarray,
        protein_ids: List[str],
        protein_names: List[str],
        group_labels: np.ndarray,
        method: str = 't-test'
    ) -> List[DifferentialProtein]:
        """
        寻找差异蛋白
        
        Args:
            protein_matrix: 蛋白强度矩阵 (n_samples, n_proteins)
            protein_ids: 蛋白ID列表
            protein_names: 蛋白名称列表
            group_labels: 分组标签
            method: 统计方法
            
        Returns:
            List[DifferentialProtein]: 差异蛋白列表
        """
        n_proteins = len(protein_ids)
        group0_mask = group_labels == 0
        group1_mask = group_labels == 1
        
        results = []
        
        for i in range(n_proteins):
            values0 = protein_matrix[group0_mask, i]
            values1 = protein_matrix[group1_mask, i]
            
            # 过滤缺失值（假设0为缺失）
            values0 = values0[values0 > 0]
            values1 = values1[values1 > 0]
            
            if len(values0) < 2 or len(values1) < 2:
                continue
            
            # 统计检验
            if method == 't-test':
                stat, p_value = stats.ttest_ind(values0, values1, equal_var=False)
            else:
                stat, p_value = stats.mannwhitneyu(values0, values1, alternative='two-sided')
            
            # 计算Fold Change
            mean0 = np.mean(values0)
            mean1 = np.mean(values1)
            
            if mean0 == 0:
                fold_change = float('inf') if mean1 > 0 else 1
            else:
                fold_change = mean1 / mean0
            
            log2fc = np.log2(fold_change) if fold_change > 0 else 0
            
            dp = DifferentialProtein(
                protein_accession=protein_ids[i],
                protein_name=protein_names[i] if i < len(protein_names) else None,
                fold_change=fold_change,
                log2fc=log2fc,
                p_value=p_value,
                fdr=p_value,  # 临时值
                avg_intensity_group1=mean0,
                avg_intensity_group2=mean1
            )
            
            results.append(dp)
        
        # FDR校正
        p_values = [dp.p_value for dp in results]
        corrected = self._fdr_correction(p_values)
        
        for dp, fdr in zip(results, corrected):
            dp.fdr = float(fdr)
        
        # 按p值排序
        results.sort(key=lambda x: x.p_value)
        
        return results
    
    def enrichment_analysis(
        self,
        protein_list: List[str],
        background_list: List[str],
        database: str = 'GO',
        min_count: int = 2
    ) -> List[EnrichmentResult]:
        """
        通路富集分析
        
        Args:
            protein_list: 目标蛋白列表
            background_list: 背景蛋白列表
            database: 数据库类型 ('GO', 'KEGG')
            min_count: 最小蛋白数
            
        Returns:
            List[EnrichmentResult]: 富集结果
        """
        # 模拟富集分析（实际应用应使用真实数据库和超几何检验）
        results = []
        
        # 为每个通路生成模拟结果
        for term_id, term_info in self.mock_pathways.items():
            if database == 'GO' and not term_id.startswith('GO'):
                continue
            if database == 'KEGG' and not term_id.startswith('KEGG'):
                continue
            
            # 模拟统计
            count = min(len(protein_list), np.random.randint(3, 10))
            
            if count < min_count:
                continue
            
            # 超几何检验模拟
            p_value = np.random.uniform(0.001, 0.1)
            
            result = EnrichmentResult(
                term_id=term_id,
                term_name=term_info['name'],
                category=term_info['category'],
                count=count,
                total=len(protein_list),
                p_value=p_value,
                fdr=p_value * 5,  # 粗略校正
                genes=protein_list[:count]
            )
            
            results.append(result)
        
        # 按p值排序
        results.sort(key=lambda x: x.p_value)
        
        return results
    
    def calculate_protein_coverage(
        self,
        protein_sequence: str,
        identified_peptides: List[str]
    ) -> float:
        """
        计算蛋白序列覆盖度
        
        Args:
            protein_sequence: 蛋白氨基酸序列
            identified_peptides: 鉴定到的肽段序列列表
            
        Returns:
            float: 覆盖度 (0-1)
        """
        if not protein_sequence or not identified_peptides:
            return 0.0
        
        seq_len = len(protein_sequence)
        coverage_array = np.zeros(seq_len, dtype=bool)
        
        for peptide in identified_peptides:
            # 简单匹配（实际应考虑酶切位点）
            start = protein_sequence.find(peptide)
            if start != -1:
                coverage_array[start:start + len(peptide)] = True
        
        return np.sum(coverage_array) / seq_len
    
    def _fdr_correction(self, p_values: List[float]) -> np.ndarray:
        """FDR校正 (Benjamini-Hochberg)"""
        p_values = np.array(p_values)
        n = len(p_values)
        
        sorted_idx = np.argsort(p_values)
        sorted_p = p_values[sorted_idx]
        
        corrected = np.zeros(n)
        prev = 1.0
        
        for i in range(n-1, -1, -1):
            p = sorted_p[i]
            corrected[sorted_idx[i]] = min(prev, p * n / (i + 1))
            prev = corrected[sorted_idx[i]]
        
        return corrected


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=== 测试蛋白质组学分析器 ===")
    
    analyzer = ProteomicsAnalyzer()
    
    # 测试差异蛋白分析
    np.random.seed(42)
    n_samples = 10
    n_proteins = 100
    
    protein_matrix = np.random.lognormal(8, 1, (n_samples, n_proteins))
    group_labels = np.array([0] * 5 + [1] * 5)
    
    # 添加一些差异
    protein_matrix[5:, :10] *= 2
    
    protein_ids = [f"P{i:05d}" for i in range(n_proteins)]
    protein_names = [f"Protein_{i}" for i in range(n_proteins)]
    
    diff_proteins = analyzer.find_differential_proteins(
        protein_matrix, protein_ids, protein_names, group_labels
    )
    
    significant = [p for p in diff_proteins if p.is_significant]
    
    print(f"\n差异蛋白分析:")
    print(f"  总蛋白: {len(diff_proteins)}")
    print(f"  显著差异: {len(significant)}")
    
    if significant:
        print(f"  最显著的: {significant[0].protein_accession} (FC={significant[0].fold_change:.2f}, p={significant[0].fdr:.4f})")
    
    # 测试富集分析
    print("\n富集分析:")
    enrichment = analyzer.enrichment_analysis(
        protein_ids[:20],
        protein_ids,
        database='GO'
    )
    
    print(f"  富集到 {len(enrichment)} 个通路")
    for result in enrichment[:3]:
        print(f"    {result.term_id}: {result.term_name} (p={result.p_value:.4f})")
    
    print("\n✅ 测试完成!")
