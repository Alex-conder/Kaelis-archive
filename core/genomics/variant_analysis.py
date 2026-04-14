"""
变异分析模块 - Variant Analysis Module

功能：
1. 变异注释 (SNP/INDEL)
2. 变异过滤与质控
3. 变异功能影响预测
4. 变异统计与可视化
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple, Set
from collections import defaultdict, Counter
import re


@dataclass
class VariantAnnotation:
    """变异注释结果"""
    chrom: str
    pos: int
    ref: str
    alt: str
    gene: Optional[str] = None
    consequence: Optional[str] = None  # 后果类型
    impact: Optional[str] = None  # 影响程度 (HIGH, MODERATE, LOW, MODIFIER)
    aa_change: Optional[str] = None  # 氨基酸改变 (p.Ala123Val)
    cdna_change: Optional[str] = None  # cDNA改变 (c.123A>G)
    exon_id: Optional[str] = None
    transcript_id: Optional[str] = None
    sift_score: Optional[float] = None  # SIFT预测分数
    polyphen_score: Optional[float] = None  # PolyPhen预测分数
    gnomad_af: Optional[float] = None  # gnomAD等位基因频率
    clinvar_sig: Optional[str] = None  # ClinVar临床意义


class VariantFilter:
    """变异过滤器"""
    
    def __init__(self):
        self.filters: List[Dict] = []
    
    def add_quality_filter(self, min_qual: float = 30.0):
        """添加质量过滤"""
        self.filters.append({
            'name': 'QUAL',
            'func': lambda v: v.get('QUAL', 0) >= min_qual
        })
    
    def add_depth_filter(self, min_dp: int = 10):
        """添加深度过滤"""
        self.filters.append({
            'name': 'DP',
            'func': lambda v: v.get('DP', 0) >= min_dp
        })
    
    def add_allele_frequency_filter(self, min_af: float = 0.1, max_af: float = 1.0):
        """添加等位基因频率过滤"""
        self.filters.append({
            'name': 'AF',
            'func': lambda v: min_af <= v.get('AF', 0) <= max_af
        })
    
    def add_impact_filter(self, impacts: List[str] = None):
        """添加影响程度过滤"""
        if impacts is None:
            impacts = ['HIGH', 'MODERATE']
        self.filters.append({
            'name': 'IMPACT',
            'func': lambda v: v.get('impact') in impacts
        })
    
    def add_gnomad_filter(self, max_af: float = 0.01):
        """添加gnomAD人群频率过滤"""
        self.filters.append({
            'name': 'gnomAD',
            'func': lambda v: v.get('gnomad_af', 0) <= max_af or pd.isna(v.get('gnomad_af'))
        })
    
    def apply(self, variants: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
        """
        应用所有过滤器
        
        Returns:
            (过滤后的变异, 统计信息)
        """
        mask = pd.Series([True] * len(variants), index=variants.index)
        stats = {'initial': len(variants)}
        
        for f in self.filters:
            f_mask = variants.apply(f['func'], axis=1)
            mask = mask & f_mask
            stats[f['name']] = f_mask.sum()
        
        filtered = variants[mask].copy()
        stats['final'] = len(filtered)
        stats['filtered_out'] = stats['initial'] - stats['final']
        
        return filtered, stats


class VariantAnnotator:
    """变异注释器"""
    
    # 变异后果类型（从最严重到最轻）
    CONSEQUENCE_SEVERITY = {
        'transcript_ablation': 1,
        'splice_acceptor_variant': 2,
        'splice_donor_variant': 2,
        'stop_gained': 3,
        'frameshift_variant': 3,
        'stop_lost': 4,
        'start_lost': 4,
        'transcript_amplification': 5,
        'inframe_insertion': 6,
        'inframe_deletion': 6,
        'missense_variant': 7,
        'protein_altering_variant': 7,
        'splice_region_variant': 8,
        'incomplete_terminal_codon_variant': 9,
        'start_retained_variant': 10,
        'stop_retained_variant': 10,
        'synonymous_variant': 11,
        'coding_sequence_variant': 12,
        'mature_miRNA_variant': 13,
        '5_prime_UTR_variant': 14,
        '3_prime_UTR_variant': 14,
        'non_coding_transcript_exon_variant': 15,
        'intron_variant': 16,
        'NMD_transcript_variant': 17,
        'non_coding_transcript_variant': 18,
        'upstream_gene_variant': 19,
        'downstream_gene_variant': 19,
        'TFBS_ablation': 20,
        'TFBS_amplification': 20,
        'TF_binding_site_variant': 20,
        'regulatory_region_ablation': 20,
        'regulatory_region_amplification': 20,
        'feature_elongation': 20,
        'regulatory_region_variant': 20,
        'feature_truncation': 20,
        'intergenic_variant': 21
    }
    
    IMPACT_LEVELS = {
        'HIGH': ['transcript_ablation', 'splice_acceptor_variant', 
                'splice_donor_variant', 'stop_gained', 'frameshift_variant'],
        'MODERATE': ['stop_lost', 'start_lost', 'inframe_insertion',
                    'inframe_deletion', 'missense_variant'],
        'LOW': ['synonymous_variant', 'stop_retained_variant', 
               'start_retained_variant'],
        'MODIFIER': []
    }
    
    def __init__(self, gene_model: Optional[Dict] = None):
        """
        初始化注释器
        
        Args:
            gene_model: 基因模型 {gene_id: {transcripts: [...]}}
        """
        self.gene_model = gene_model or {}
    
    def annotate(self, variants: pd.DataFrame) -> pd.DataFrame:
        """
        注释变异
        
        Args:
            variants: 变异DataFrame
        
        Returns:
            带注释的DataFrame
        """
        annotated = variants.copy()
        
        annotated['consequence'] = variants.apply(self._predict_consequence, axis=1)
        annotated['impact'] = annotated['consequence'].apply(self._get_impact)
        annotated['variant_type'] = variants.apply(self._classify_variant, axis=1)
        
        return annotated
    
    def _predict_consequence(self, variant: pd.Series) -> str:
        """预测变异后果"""
        ref = variant.get('ref', '')
        alt = variant.get('alt', '')
        
        # 简化版本：基于ref/alt长度判断
        if len(ref) == len(alt) == 1:
            return 'missense_variant'  # 假设错义
        elif len(ref) > len(alt):
            return 'deletion'
        elif len(ref) < len(alt):
            return 'insertion'
        else:
            return 'complex_variant'
    
    def _get_impact(self, consequence: str) -> str:
        """获取影响程度"""
        for impact, consequences in self.IMPACT_LEVELS.items():
            if consequence in consequences:
                return impact
        return 'MODIFIER'
    
    def _classify_variant(self, variant: pd.Series) -> str:
        """分类变异类型"""
        ref = variant.get('ref', '')
        alt = variant.get('alt', '')
        
        if len(ref) == len(alt) == 1:
            return 'SNP'
        elif len(ref) == 1 and len(alt) == 1:
            return 'SNV'
        elif len(ref) < len(alt):
            return 'INSERTION'
        elif len(ref) > len(alt):
            return 'DELETION'
        else:
            return 'COMPLEX'
    
    def predict_function_impact(self, variants: pd.DataFrame) -> pd.DataFrame:
        """
        预测功能影响（SIFT/PolyPhen模拟）
        
        Returns:
            添加预测分数的DataFrame
        """
        result = variants.copy()
        
        # 模拟SIFT分数（0=有害，1=无害）
        result['sift_score'] = np.random.beta(2, 5, len(result))
        result['sift_pred'] = result['sift_score'].apply(
            lambda x: 'deleterious' if x < 0.05 else 'tolerated'
        )
        
        # 模拟PolyPhen分数（0=无害，1=有害）
        result['polyphen_score'] = np.random.beta(2, 2, len(result))
        result['polyphen_pred'] = result['polyphen_score'].apply(
            lambda x: 'probably_damaging' if x > 0.85 
                     else ('possibly_damaging' if x > 0.15 else 'benign')
        )
        
        return result


class VariantStatistics:
    """变异统计分析"""
    
    def __init__(self):
        self.stats: Dict = {}
    
    def calculate(self, variants: pd.DataFrame) -> Dict:
        """
        计算变异统计信息
        
        Returns:
            统计字典
        """
        stats = {
            'total_variants': len(variants),
            'by_chromosome': self._chrom_stats(variants),
            'by_type': self._type_stats(variants),
            'by_impact': self._impact_stats(variants),
            'ti_tv_ratio': self._calculate_titv(variants),
            'quality_stats': self._quality_stats(variants),
        }
        
        self.stats = stats
        return stats
    
    def _chrom_stats(self, variants: pd.DataFrame) -> Dict:
        """染色体分布统计"""
        if 'chrom' in variants.columns:
            return variants['chrom'].value_counts().to_dict()
        return {}
    
    def _type_stats(self, variants: pd.DataFrame) -> Dict:
        """变异类型统计"""
        if 'variant_type' in variants.columns:
            return variants['variant_type'].value_counts().to_dict()
        return {}
    
    def _impact_stats(self, variants: pd.DataFrame) -> Dict:
        """影响程度统计"""
        if 'impact' in variants.columns:
            return variants['impact'].value_counts().to_dict()
        return {}
    
    def _calculate_titv(self, variants: pd.DataFrame) -> float:
        """计算转换/颠换比率"""
        ti = 0  # 转换 (A<->G, C<->T)
        tv = 0  # 颠换
        
        transitions = {('A', 'G'), ('G', 'A'), ('C', 'T'), ('T', 'C')}
        
        for _, row in variants.iterrows():
            ref = row.get('ref', '')
            alt = row.get('alt', '')
            
            if len(ref) == len(alt) == 1:
                if (ref, alt) in transitions:
                    ti += 1
                else:
                    tv += 1
        
        return ti / tv if tv > 0 else float('inf')
    
    def _quality_stats(self, variants: pd.DataFrame) -> Dict:
        """质量统计"""
        if 'QUAL' in variants.columns:
            qual = variants['QUAL'].dropna()
            return {
                'mean': qual.mean(),
                'median': qual.median(),
                'q25': qual.quantile(0.25),
                'q75': qual.quantile(0.75)
            }
        return {}
    
    def generate_report(self, output_path: Optional[str] = None) -> str:
        """生成统计报告"""
        lines = [
            "=" * 50,
            "Variant Statistics Report",
            "=" * 50,
            f"Total Variants: {self.stats.get('total_variants', 0)}",
            f"Ti/Tv Ratio: {self.stats.get('ti_tv_ratio', 0):.3f}",
            "",
            "By Chromosome:",
        ]
        
        for chrom, count in self.stats.get('by_chromosome', {}).items():
            lines.append(f"  {chrom}: {count}")
        
        lines.extend(["", "By Type:"])
        for vtype, count in self.stats.get('by_type', {}).items():
            lines.append(f"  {vtype}: {count}")
        
        lines.extend(["", "By Impact:"])
        for impact, count in self.stats.get('by_impact', {}).items():
            lines.append(f"  {impact}: {count}")
        
        report = '\n'.join(lines)
        
        if output_path:
            with open(output_path, 'w') as f:
                f.write(report)
        
        return report


class VariantPrioritizer:
    """变异优先级排序器"""
    
    def __init__(self):
        self.scoring_weights = {
            'impact_high': 10,
            'impact_moderate': 5,
            'impact_low': 1,
            'rare_variant': 5,  # gnomAD AF < 0.01
            'pathogenic': 10,   # ClinVar pathogenic
            'conserved': 3,     # 保守区域
        }
    
    def prioritize(self, variants: pd.DataFrame) -> pd.DataFrame:
        """
        对变异进行优先级排序
        
        Returns:
            添加优先级分数的DataFrame
        """
        result = variants.copy()
        scores = []
        
        for _, row in variants.iterrows():
            score = 0
            
            # 影响程度分数
            impact = row.get('impact')
            if impact == 'HIGH':
                score += self.scoring_weights['impact_high']
            elif impact == 'MODERATE':
                score += self.scoring_weights['impact_moderate']
            elif impact == 'LOW':
                score += self.scoring_weights['impact_low']
            
            # 罕见变异分数
            gnomad_af = row.get('gnomad_af')
            if pd.notna(gnomad_af) and gnomad_af < 0.01:
                score += self.scoring_weights['rare_variant']
            
            # SIFT分数
            sift = row.get('sift_score')
            if pd.notna(sift) and sift < 0.05:
                score += 3
            
            # PolyPhen分数
            polyphen = row.get('polyphen_score')
            if pd.notna(polyphen) and polyphen > 0.85:
                score += 3
            
            scores.append(score)
        
        result['priority_score'] = scores
        result = result.sort_values('priority_score', ascending=False)
        
        return result


# 便捷函数
def filter_variants(variants: pd.DataFrame,
                   min_qual: float = 30.0,
                   min_dp: int = 10,
                   max_gnomad_af: float = 0.01) -> pd.DataFrame:
    """
    过滤变异
    
    Args:
        variants: 变异DataFrame
        min_qual: 最小质量值
        min_dp: 最小深度
        max_gnomad_af: 最大人群频率
    
    Returns:
        过滤后的DataFrame
    """
    vf = VariantFilter()
    vf.add_quality_filter(min_qual)
    vf.add_depth_filter(min_dp)
    vf.add_gnomad_filter(max_gnomad_af)
    
    filtered, stats = vf.apply(variants)
    print(f"Filtered {stats['filtered_out']} variants ({stats['initial']} -> {stats['final']})")
    
    return filtered


def annotate_variants(variants: pd.DataFrame) -> pd.DataFrame:
    """
    注释变异
    
    Args:
        variants: 变异DataFrame
    
    Returns:
        带注释的DataFrame
    """
    annotator = VariantAnnotator()
    annotated = annotator.annotate(variants)
    annotated = annotator.predict_function_impact(annotated)
    return annotated


def find_deleterious_variants(variants: pd.DataFrame) -> pd.DataFrame:
    """
    查找有害变异
    
    Returns:
        有害变异DataFrame
    """
    mask = (
        (variants.get('impact') == 'HIGH') |
        (variants.get('sift_pred') == 'deleterious') |
        (variants.get('polyphen_pred') == 'probably_damaging')
    )
    return variants[mask].copy()
