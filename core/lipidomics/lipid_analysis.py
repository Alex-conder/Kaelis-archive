"""
脂质组学分析 - Lipidomics Analysis

功能：
1. 脂质分类统计
2. 脂质链长/不饱和度分析
3. 脂质组比较
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple
import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


@dataclass
class Lipid:
    """脂质分子"""
    name: str
    lipid_class: str  # PC, PE, TG, etc.
    total_carbons: int
    total_unsaturation: int
    fatty_acids: List[str]  # ["16:0", "18:1"]
    intensity: float


class LipidomicsAnalyzer:
    """脂质组学分析器"""
    
    # 脂质类别映射
    LIPID_CLASSES = {
        'PC': 'Phosphatidylcholine',
        'PE': 'Phosphatidylethanolamine',
        'PI': 'Phosphatidylinositol',
        'PS': 'Phosphatidylserine',
        'PG': 'Phosphatidylglycerol',
        'PA': 'Phosphatidic acid',
        'TG': 'Triacylglycerol',
        'DG': 'Diacylglycerol',
        'SM': 'Sphingomyelin',
        'Cer': 'Ceramide',
        'ChE': 'Cholesteryl ester',
        'FA': 'Fatty acid',
        'LPC': 'Lysophosphatidylcholine',
        'LPE': 'Lysophosphatidylethanolamine',
    }
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def parse_lipid_name(self, name: str) -> Dict[str, Any]:
        """
        解析脂质名称
        
        示例: PC(16:0/18:1(9Z)) -> 解析为结构化数据
        """
        # 简单解析（实际应用需要更复杂的正则）
        match = re.match(r'([A-Za-z]+)\(([^)]+)\)', name)
        
        if not match:
            return {'name': name, 'class': 'Unknown', 'chains': []}
        
        lipid_class = match.group(1)
        chains_str = match.group(2)
        
        # 解析链
        chains = []
        for chain in chains_str.split('/'):
            chain_match = re.match(r'(\d+):(\d+)', chain)
            if chain_match:
                carbons = int(chain_match.group(1))
                unsat = int(chain_match.group(2))
                chains.append({'carbons': carbons, 'unsaturation': unsat})
        
        total_c = sum(c['carbons'] for c in chains)
        total_u = sum(c['unsaturation'] for c in chains)
        
        return {
            'name': name,
            'class': lipid_class,
            'class_full': self.LIPID_CLASSES.get(lipid_class, 'Unknown'),
            'chains': chains,
            'total_carbons': total_c,
            'total_unsaturation': total_u
        }
    
    def classify_lipids(self, lipid_names: List[str]) -> Dict[str, List[str]]:
        """
        脂质分类统计
        
        Args:
            lipid_names: 脂质名称列表
            
        Returns:
            Dict: {类别: [脂质名称列表]}
        """
        classification = {}
        
        for name in lipid_names:
            parsed = self.parse_lipid_name(name)
            lipid_class = parsed['class']
            
            if lipid_class not in classification:
                classification[lipid_class] = []
            classification[lipid_class].append(name)
        
        return classification
    
    def analyze_chain_length_distribution(
        self,
        lipid_names: List[str],
        lipid_intensities: List[float]
    ) -> Dict[str, Any]:
        """
        分析链长分布
        """
        chain_lengths = []
        
        for name, intensity in zip(lipid_names, lipid_intensities):
            parsed = self.parse_lipid_name(name)
            for chain in parsed.get('chains', []):
                chain_lengths.append({
                    'length': chain['carbons'],
                    'unsaturation': chain['unsaturation'],
                    'intensity': intensity
                })
        
        if not chain_lengths:
            return {}
        
        # 统计
        lengths = [c['length'] for c in chain_lengths]
        unsats = [c['unsaturation'] for c in chain_lengths]
        
        return {
            'avg_chain_length': np.mean(lengths),
            'avg_unsaturation': np.mean(unsats),
            'chain_length_distribution': {l: lengths.count(l) for l in set(lengths)},
            'unsaturation_distribution': {u: unsats.count(u) for u in set(unsats)}
        }
    
    def differential_analysis(
        self,
        lipid_names: List[str],
        intensities_group1: np.ndarray,
        intensities_group2: np.ndarray
    ) -> List[Dict[str, Any]]:
        """
        差异脂质分析
        """
        results = []
        
        for i, name in enumerate(lipid_names):
            g1 = intensities_group1[i]
            g2 = intensities_group2[i]
            
            # 简单的倍数变化计算
            if g1 > 0:
                fc = g2 / g1
            else:
                fc = float('inf') if g2 > 0 else 1
            
            log2fc = np.log2(fc) if fc > 0 else 0
            
            results.append({
                'lipid': name,
                'class': self.parse_lipid_name(name)['class'],
                'fold_change': fc,
                'log2fc': log2fc,
                'group1_mean': g1,
                'group2_mean': g2
            })
        
        # 按倍数变化排序
        results.sort(key=lambda x: abs(x['log2fc']), reverse=True)
        
        return results
    
    def lipid_ontology_enrichment(
        self,
        differential_lipids: List[str],
        background_lipids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        脂质本体富集分析（简化版）
        """
        # 分类统计
        diff_classes = self.classify_lipids(differential_lipids)
        bg_classes = self.classify_lipids(background_lipids)
        
        results = []
        
        for lipid_class, lipids in diff_classes.items():
            count = len(lipids)
            bg_count = len(bg_classes.get(lipid_class, []))
            
            if bg_count > 0:
                enrichment = count / len(differential_lipids)
                bg_ratio = bg_count / len(background_lipids)
                fold = enrichment / bg_ratio if bg_ratio > 0 else 0
                
                results.append({
                    'lipid_class': lipid_class,
                    'description': self.LIPID_CLASSES.get(lipid_class, 'Unknown'),
                    'count': count,
                    'enrichment_ratio': fold,
                    'lipids': lipids
                })
        
        # 按富集倍数排序
        results.sort(key=lambda x: x['enrichment_ratio'], reverse=True)
        
        return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=== 测试脂质组学分析器 ===")
    
    analyzer = LipidomicsAnalyzer()
    
    # 测试解析
    test_lipids = [
        'PC(16:0/18:1)',
        'PC(16:0/18:2)',
        'PE(18:0/20:4)',
        'TG(16:0/18:1/18:1)',
        'SM(d18:1/16:0)'
    ]
    
    print("\n脂质解析:")
    for lipid in test_lipids:
        parsed = analyzer.parse_lipid_name(lipid)
        print(f"  {lipid} -> {parsed['class_full']}")
    
    # 分类统计
    classification = analyzer.classify_lipids(test_lipids)
    print("\n分类统计:")
    for cls, lipids in classification.items():
        print(f"  {cls}: {len(lipids)}")
    
    print("\n✅ 测试完成!")
