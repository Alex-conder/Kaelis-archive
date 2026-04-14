"""
蛋白质定量模块 - Protein Quantification Module

支持多种定量方法：
1. LFQ (Label-Free Quantification) - 无标记定量
2. iBAQ (intensity Based Absolute Quantification)
3. TMT/iTRAQ (同位素标记)
4. SILAC (氨基酸稳定同位素标记)
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from scipy import stats
from scipy.optimize import minimize
import warnings


@dataclass
class QuantificationResult:
    """定量结果"""
    protein_id: str
    intensity: float
    log2_intensity: float
    normalized_intensity: Optional[float] = None
    ibaq: Optional[float] = None
    peptides_count: int = 0
    razor_peptides: int = 0
    unique_peptides: int = 0
    cv: Optional[float] = None  # 变异系数
    p_value: Optional[float] = None
    q_value: Optional[float] = None


class LFQQuantifier:
    """无标记定量 (LFQ)"""
    
    def __init__(self, min_peptides: int = 2, normalize: bool = True):
        """
        初始化LFQ定量器
        
        Args:
            min_peptides: 每个蛋白质最少肽段数
            normalize: 是否进行归一化
        """
        self.min_peptides = min_peptides
        self.normalize = normalize
        self.normalization_factors: Optional[np.ndarray] = None
        
    def quantify(self, peptide_intensities: pd.DataFrame) -> pd.DataFrame:
        """
        LFQ定量分析
        
        Args:
            peptide_intensities: DataFrame with columns:
                - protein_id: 蛋白质ID
                - peptide: 肽段序列
                - sample_1, sample_2, ...: 各样本强度
        
        Returns:
            蛋白质定量结果
        """
        sample_cols = [c for c in peptide_intensities.columns 
                      if c not in ['protein_id', 'peptide']]
        
        # 对数转换
        log_data = peptide_intensities.copy()
        for col in sample_cols:
            log_data[col] = np.log2(log_data[col].replace(0, np.nan))
        
        # 计算归一化因子
        if self.normalize:
            self.normalization_factors = self._calculate_norm_factors(log_data, sample_cols)
            for i, col in enumerate(sample_cols):
                log_data[col] = log_data[col] - self.normalization_factors[i]
        
        # 蛋白质水平汇总
        results = []
        for protein_id, group in log_data.groupby('protein_id'):
            if len(group) < self.min_peptides:
                continue
            
            # MaxLFQ算法: 使用中位数比值
            intensities = []
            for col in sample_cols:
                valid = group[col].dropna()
                if len(valid) > 0:
                    intensities.append(2 ** valid.median())
                else:
                    intensities.append(0)
            
            results.append({
                'protein_id': protein_id,
                'peptides_count': len(group),
                **{col: intensities[i] for i, col in enumerate(sample_cols)}
            })
        
        return pd.DataFrame(results)
    
    def _calculate_norm_factors(self, data: pd.DataFrame, 
                                sample_cols: List[str]) -> np.ndarray:
        """计算归一化因子（使用所有蛋白质的中位数）"""
        medians = []
        for col in sample_cols:
            valid = data[col].dropna()
            if len(valid) > 0:
                medians.append(valid.median())
            else:
                medians.append(0)
        
        median_of_medians = np.median([m for m in medians if m != 0])
        factors = np.array([m - median_of_medians if m != 0 else 0 for m in medians])
        return factors


class IBAQQuantifier:
    """
    iBAQ定量 (基于强度的绝对定量)
    
    iBAQ = 蛋白质强度 / 可观察肽段数量
    """
    
    def __init__(self):
        self.simulator = None
    
    def calculate_ibaq(self, protein_intensities: pd.DataFrame,
                       protein_sequences: Dict[str, str],
                       enzyme: str = 'trypsin') -> pd.DataFrame:
        """
        计算iBAQ值
        
        Args:
            protein_intensities: 蛋白质强度DataFrame
            protein_sequences: 蛋白质序列字典
            enzyme: 酶切类型
        
        Returns:
            添加iBAQ列的DataFrame
        """
        result = protein_intensities.copy()
        ibaq_values = []
        
        for _, row in result.iterrows():
            prot_id = row['protein_id']
            intensity = row.get('intensity', 0)
            
            if prot_id in protein_sequences:
                # 计算理论肽段数
                n_theoretical = self._count_theoretical_peptides(
                    protein_sequences[prot_id], enzyme
                )
                if n_theoretical > 0:
                    ibaq = intensity / n_theoretical
                else:
                    ibaq = 0
            else:
                ibaq = np.nan
            
            ibaq_values.append(ibaq)
        
        result['ibaq'] = ibaq_values
        return result
    
    def _count_theoretical_peptides(self, sequence: str, enzyme: str) -> int:
        """计算理论可观察肽段数"""
        # 简化的酶切计算
        if enzyme == 'trypsin':
            # 计算KR残基数（潜在切割位点）
            cleavage_sites = sum(1 for aa in sequence if aa in 'KR')
            # 估计肽段数
            return min(cleavage_sites + 1, len(sequence) // 7)
        return len(sequence) // 7


class TMTQuantifier:
    """
    TMT标记定量 (Tandem Mass Tag)
    
    支持TMT 6-plex, 10-plex, 11-plex, 16-plex
    """
    
    TMT_CHANNELS = {
        6: ['126', '127', '128', '129', '130', '131'],
        10: ['126', '127N', '127C', '128N', '128C', '129N', '129C', 
             '130N', '130C', '131'],
        11: ['126', '127N', '127C', '128N', '128C', '129N', '129C',
             '130N', '130C', '131N', '131C'],
        16: ['126', '127N', '127C', '128N', '128C', '129N', '129C',
             '130N', '130C', '131N', '131C', '132N', '132C', 
             '133N', '133C', '134N']
    }
    
    def __init__(self, plex: int = 10):
        """
        初始化TMT定量器
        
        Args:
            plex: TMT plex数 (6, 10, 11, 16)
        """
        if plex not in self.TMT_CHANNELS:
            raise ValueError(f"Unsupported plex: {plex}")
        
        self.plex = plex
        self.channels = self.TMT_CHANNELS[plex]
        
    def quantify(self, reporter_intensities: pd.DataFrame,
                 reference_channel: Optional[str] = None) -> pd.DataFrame:
        """
        TMT定量分析
        
        Args:
            reporter_intensities: DataFrame with reporter ion intensities
            reference_channel: 参考通道 (用于计算ratio)
        
        Returns:
            定量结果
        """
        # 提取通道列
        channel_cols = [c for c in reporter_intensities.columns 
                       if any(ch in c for ch in self.channels)]
        
        # 计算ratio
        if reference_channel:
            ref_col = [c for c in channel_cols if reference_channel in c][0]
            for col in channel_cols:
                if col != ref_col:
                    reporter_intensities[f'{col}_ratio'] = (
                        reporter_intensities[col] / reporter_intensities[ref_col]
                    )
        
        # 归一化（使用总强度）
        total_intensity = reporter_intensities[channel_cols].sum(axis=1)
        for col in channel_cols:
            reporter_intensities[f'{col}_norm'] = (
                reporter_intensities[col] / total_intensity * 100
            )
        
        return reporter_intensities
    
    def correct_isotopic_impurity(self, intensities: np.ndarray,
                                   correction_matrix: np.ndarray) -> np.ndarray:
        """
        校正同位素杂质
        
        Args:
            intensities: 原始强度
            correction_matrix: 校正矩阵
        
        Returns:
            校正后的强度
        """
        # 解线性方程组
        corrected = np.linalg.solve(correction_matrix, intensities)
        return np.maximum(corrected, 0)  # 确保非负


class SILACQuantifier:
    """
    SILAC定量 (Stable Isotope Labeling by Amino acids in Cell culture)
    
    支持Light/Heavy配对
    """
    
    def __init__(self, heavy_lysine_mass: float = 8.014199,
                 heavy_arginine_mass: float = 10.008269):
        """
        初始化SILAC定量器
        
        Args:
            heavy_lysine_mass: 重标记赖氨酸质量偏移
            heavy_arginine_mass: 重标记精氨酸质量偏移
        """
        self.heavy_lysine_mass = heavy_lysine_mass
        self.heavy_arginine_mass = heavy_arginine_mass
    
    def quantify(self, peptide_pairs: List[Dict]) -> pd.DataFrame:
        """
        SILAC定量分析
        
        Args:
            peptide_pairs: 肽段对列表
                [{'light': {'mz': ..., 'intensity': ...},
                  'heavy': {'mz': ..., 'intensity': ...}}, ...]
        
        Returns:
            定量结果
        """
        results = []
        
        for pair in peptide_pairs:
            light = pair.get('light', {})
            heavy = pair.get('heavy', {})
            
            light_int = light.get('intensity', 0)
            heavy_int = heavy.get('intensity', 0)
            
            if light_int > 0 and heavy_int > 0:
                ratio = heavy_int / light_int
                log2_ratio = np.log2(ratio)
            else:
                ratio = np.nan
                log2_ratio = np.nan
            
            results.append({
                'peptide': pair.get('sequence', ''),
                'light_intensity': light_int,
                'heavy_intensity': heavy_int,
                'ratio': ratio,
                'log2_ratio': log2_ratio,
                'rt': pair.get('rt', 0)
            })
        
        return pd.DataFrame(results)
    
    def calculate_protein_ratio(self, peptide_ratios: pd.DataFrame,
                                 method: str = 'median') -> float:
        """
        计算蛋白质水平的SILAC比值
        
        Args:
            peptide_ratios: 肽段比值DataFrame
            method: 汇总方法 ('mean', 'median', 'weighted')
        
        Returns:
            蛋白质比值
        """
        valid_ratios = peptide_ratios['log2_ratio'].dropna()
        
        if len(valid_ratios) == 0:
            return np.nan
        
        if method == 'median':
            return 2 ** valid_ratios.median()
        elif method == 'mean':
            return 2 ** valid_ratios.mean()
        elif method == 'weighted':
            # 按强度加权
            weights = (peptide_ratios['light_intensity'] + 
                      peptide_ratios['heavy_intensity'])
            return 2 ** np.average(valid_ratios, weights=weights)
        
        return 2 ** valid_ratios.median()


class ProteinQuantifier:
    """统一蛋白质定量接口"""
    
    QUANT_METHODS = ['lfq', 'ibaq', 'tmt', 'silac', 'direct']
    
    def __init__(self, method: str = 'lfq', **kwargs):
        """
        初始化定量器
        
        Args:
            method: 定量方法
            **kwargs: 方法特定参数
        """
        if method not in self.QUANT_METHODS:
            raise ValueError(f"Unknown method: {method}")
        
        self.method = method
        self.quantifier = self._create_quantifier(method, **kwargs)
    
    def _create_quantifier(self, method: str, **kwargs):
        """创建具体的定量器"""
        if method == 'lfq':
            return LFQQuantifier(**kwargs)
        elif method == 'ibaq':
            return IBAQQuantifier()
        elif method == 'tmt':
            return TMTQuantifier(**kwargs)
        elif method == 'silac':
            return SILACQuantifier(**kwargs)
        return None
    
    def quantify(self, data: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """
        执行定量
        
        Args:
            data: 输入数据
            **kwargs: 额外参数
        
        Returns:
            定量结果
        """
        if self.method == 'lfq':
            return self.quantifier.quantify(data)
        elif self.method == 'ibaq':
            return self.quantifier.calculate_ibaq(data, **kwargs)
        elif self.method == 'tmt':
            return self.quantifier.quantify(data, **kwargs)
        elif self.method == 'silac':
            return self.quantifier.quantify(data)
        else:  # direct
            return data


# 便捷函数
def run_lfq_analysis(peptide_data: pd.DataFrame,
                     sample_cols: List[str],
                     min_peptides: int = 2) -> pd.DataFrame:
    """
    运行LFQ分析
    
    Args:
        peptide_data: 肽段强度数据
        sample_cols: 样本列名
        min_peptides: 最小肽段数
    
    Returns:
        蛋白质定量结果
    """
    quantifier = LFQQuantifier(min_peptides=min_peptides)
    return quantifier.quantify(peptide_data)


def calculate_fold_change(control: np.ndarray, 
                          treatment: np.ndarray,
                          log2: bool = True) -> Tuple[np.ndarray, np.ndarray]:
    """
    计算倍数变化
    
    Args:
        control: 对照组强度
        treatment: 处理组强度
        log2: 是否返回log2 fold change
    
    Returns:
        (fold_change, p_values)
    """
    # t-test
    _, p_values = stats.ttest_ind(control, treatment, axis=0)
    
    # fold change
    mean_control = np.mean(control, axis=0)
    mean_treatment = np.mean(treatment, axis=0)
    
    # 避免除零
    mean_control = np.maximum(mean_control, 1e-10)
    
    fc = mean_treatment / mean_control
    
    if log2:
        fc = np.log2(fc)
    
    return fc, p_values
