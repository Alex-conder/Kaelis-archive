"""
通路串扰分析模块 - Pathway Crosstalk Analysis Module

功能：
1. 通路富集分析
2. 通路间串扰识别
3. 跨组学通路整合
4. 网络拓扑分析
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple, Set
from collections import defaultdict
from scipy import stats
from scipy.stats import hypergeom, fisher_exact
import warnings


@dataclass
class PathwayResult:
    """通路分析结果"""
    pathway_id: str
    pathway_name: str
    p_value: float
    q_value: Optional[float] = None
    overlap_genes: List[str] = None
    overlap_size: int = 0
    pathway_size: int = 0
    gene_set_size: int = 0
    enrichment_ratio: float = 0.0
    
    @property
    def is_significant(self, threshold: float = 0.05) -> bool:
        """判断是否显著"""
        p = self.q_value if self.q_value is not None else self.p_value
        return p < threshold


@dataclass
class CrosstalkResult:
    """通路串扰结果"""
    pathway1: str
    pathway2: str
    shared_genes: List[str]
    jaccard_index: float
    overlap_coefficient: float
    p_value: float


class PathwayDatabase:
    """通路数据库"""
    
    # KEGG通路示例（简化版）
    KEGG_PATHWAYS = {
        'hsa00010': {'name': 'Glycolysis / Gluconeogenesis', 
                    'genes': ['HK1', 'HK2', 'HK3', 'GPI', 'PFK', 'ALDOA', 'GAPDH', 
                             'PGK1', 'PGAM', 'ENO1', 'PKM', 'LDHA']},
        'hsa00020': {'name': 'Citrate cycle (TCA cycle)',
                    'genes': ['CS', 'ACO1', 'ACO2', 'IDH1', 'IDH2', 'IDH3', 
                             'OGDH', 'SUCLG', 'SDHA', 'FH', 'MDH1', 'MDH2']},
        'hsa00030': {'name': 'Pentose phosphate pathway',
                    'genes': ['G6PD', 'PGD', 'TKT', 'RPIA', 'RPE', 'TKTL1', 'TKTL2']},
        'hsa00040': {'name': 'Pentose and glucuronate interconversions',
                    'genes': ['UGP2', 'GUSB', 'XYLB', 'DCXR', 'AKR1B']},
        'hsa00051': {'name': 'Fructose and mannose metabolism',
                    'genes': ['HK1', 'HK2', 'PFK', 'FBP1', 'MPI', 'PMM2']},
        'hsa00052': {'name': 'Galactose metabolism',
                    'genes': ['GALK1', 'GALT', 'GALE', 'GMPPB']},
        'hsa00500': {'name': 'Starch and sucrose metabolism',
                    'genes': ['AMY1', 'AMY2', 'MGAM', 'SI', 'UGP2']},
        'hsa00520': {'name': 'Amino sugar and nucleotide sugar metabolism',
                    'genes': ['GFPT1', 'GNA1', 'UAP1', 'OGT', 'OGT', 'HEXA']},
        'hsa00620': {'name': 'Pyruvate metabolism',
                    'genes': ['PDHA1', 'PDHB', 'LDHA', 'LDHB', 'PC', 'PCK1', 'PCK2']},
        'hsa00630': {'name': 'Glyoxylate and dicarboxylate metabolism',
                    'genes': ['AGXT', 'AGXT2', 'GRHPR', 'HAO1', 'HAO2']},
        'hsa00640': {'name': 'Propanoate metabolism',
                    'genes': ['ACSS2', 'PCCA', 'PCCB', 'MUT', 'MCEE']},
        'hsa00650': {'name': 'Butanoate metabolism',
                    'genes': ['ACAT1', 'ACAT2', 'HMGCL', 'HMGCS2', 'BDH1']},
        'hsa00660': {'name': 'C5-Branched dibasic acid metabolism',
                    'genes': ['ACLY', 'ACSS2', 'HMGC', 'HMGCL']},
        'hsa00970': {'name': 'Aminoacyl-tRNA biosynthesis',
                    'genes': ['AARS', 'CARS', 'DARS', 'EARS', 'FARS', 'GARS', 
                             'HARS', 'IARS', 'KARS', 'LARS', 'MARS', 'NARS']},
        'hsa01100': {'name': 'Metabolic pathways',
                    'genes': []},  # 这是一个大汇总通路
        'hsa01110': {'name': 'Biosynthesis of secondary metabolites',
                    'genes': []},
        'hsa01120': {'name': 'Microbial metabolism in diverse environments',
                    'genes': []},
        'hsa01200': {'name': 'Carbon metabolism',
                    'genes': ['HK1', 'HK2', 'PFK', 'ALDOA', 'GAPDH', 'PGK1', 
                             'ENO1', 'PKM', 'LDHA', 'CS', 'ACO2', 'IDH1']},
        'hsa01210': {'name': '2-Oxocarboxylic acid metabolism',
                    'genes': ['OGDH', 'PC', 'PCK1', 'GPT', 'GPT2']},
        'hsa01212': {'name': 'Fatty acid metabolism',
                    'genes': ['ACACA', 'ACACB', 'FASN', 'SCD', 'ELOVL', 'ACOX1']},
        'hsa01230': {'name': 'Biosynthesis of amino acids',
                    'genes': ['GPT', 'GPT2', 'BCAT1', 'BCAT2', 'ASNS', 'GLUL']},
        
        # 信号通路
        'hsa04010': {'name': 'MAPK signaling pathway',
                    'genes': ['MAPK1', 'MAPK3', 'MAP2K1', 'MAP2K2', 'MAP3K1', 
                             'EGFR', 'FGFR1', 'PDGFRB', 'RAS', 'RAF1']},
        'hsa04014': {'name': 'Ras signaling pathway',
                    'genes': ['KRAS', 'NRAS', 'HRAS', 'RAF1', 'MAP2K1', 'MAPK1']},
        'hsa04015': {'name': 'Rap1 signaling pathway',
                    'genes': ['RAP1A', 'RAP1B', 'CTNNB1', 'ADCY', 'PIK3CA']},
        'hsa04020': {'name': 'Calcium signaling pathway',
                    'genes': ['CACNA1A', 'CACNA1B', 'CACNA1C', 'RYR1', 'RYR2', 'IP3R']},
        'hsa04022': {'name': 'cGMP-PKG signaling pathway',
                    'genes': ['GUCY1A2', 'GUCY1A3', 'PRKG1', 'PRKG2', 'PLN']},
        'hsa04024': {'name': 'cAMP signaling pathway',
                    'genes': ['ADCY1', 'ADCY2', 'PRKACA', 'PRKACB', 'CREB1']},
        'hsa04060': {'name': 'Cytokine-cytokine receptor interaction',
                    'genes': ['IL1B', 'IL6', 'TNF', 'IFNG', 'IL10', 'TGFB1']},
        'hsa04061': {'name': 'Viral protein interaction with cytokine and cytokine receptor',
                    'genes': ['IL1B', 'IL6', 'TNF', 'IFNG']},
        'hsa04064': {'name': 'NF-kappa B signaling pathway',
                    'genes': ['NFKB1', 'NFKB2', 'RELA', 'RELB', 'IKBKB', 'IKBKE']},
        'hsa04066': {'name': 'HIF-1 signaling pathway',
                    'genes': ['HIF1A', 'EPAS1', 'ARNT', 'VEGFA', 'SLC2A1', 'PGK1']},
        'hsa04068': {'name': 'FoxO signaling pathway',
                    'genes': ['FOXO1', 'FOXO3', 'AKT1', 'AKT2', 'GSK3B']},
        'hsa04070': {'name': 'Phosphatidylinositol signaling system',
                    'genes': ['PIK3CA', 'PIK3CB', 'PTEN', 'PIP5K', 'PLC']},
        'hsa04071': {'name': 'Sphingolipid signaling pathway',
                    'genes': ['SPTLC1', 'CERS1', 'SMPD1', 'SMPD2', 'S1PR1']},
        'hsa04072': {'name': 'Phospholipase D signaling pathway',
                    'genes': ['PLD1', 'PLD2', 'MTOR', 'RHEB', 'TSC1', 'TSC2']},
        'hsa04110': {'name': 'Cell cycle',
                    'genes': ['CDK1', 'CDK2', 'CDK4', 'CDK6', 'CCNA2', 'CCNB1', 
                             'CCND1', 'CCNE1', 'TP53', 'RB1']},
        'hsa04115': {'name': 'p53 signaling pathway',
                    'genes': ['TP53', 'MDM2', 'CDKN1A', 'GADD45A', 'BAX']},
        'hsa04120': {'name': 'Ubiquitin mediated proteolysis',
                    'genes': ['UBE2D1', 'UBE2E1', 'UBB', 'UBC', 'MDM2']},
        'hsa04122': {'name': 'Sulfur relay system',
                    'genes': ['MOCS1', 'MOCS2', 'MOCS3']},
        'hsa04130': {'name': 'SNARE interactions in vesicular transport',
                    'genes': ['VAMP1', 'VAMP2', 'STX1A', 'STX2', 'SNAP25']},
        'hsa04136': {'name': 'Autophagy - animal',
                    'genes': ['ATG3', 'ATG5', 'ATG7', 'ATG12', 'LC3', 'mTOR']},
        'hsa04137': {'name': 'Mitophagy - animal',
                    'genes': ['PINK1', 'PRKN', 'ATG7', 'SQSTM1']},
        'hsa04140': {'name': 'Autophagy - organism',
                    'genes': ['ATG1', 'ATG13', 'ULK1', 'ULK2']},
        'hsa04141': {'name': 'Protein processing in endoplasmic reticulum',
                    'genes': ['HSPA5', 'HSP90B1', 'PDIA3', 'CANX', 'CALR']},
        'hsa04142': {'name': 'Lysosome',
                    'genes': ['CTSB', 'CTSD', 'CTSL', 'HEXA', 'HEXB', 'LAMP1']},
        'hsa04144': {'name': 'Endocytosis',
                    'genes': ['CLTC', 'CLTA', 'AP2A1', 'AP2B1', 'DNM1']},
        'hsa04145': {'name': 'Phagosome',
                    'genes': ['TUBA', 'TUBB', 'ACTB', 'ACTG1', 'RAB5A']},
        'hsa04146': {'name': 'Peroxisome',
                    'genes': ['CAT', 'SOD1', 'ACOX1', 'HMGCL', 'PEX1', 'PEX5']},
        'hsa04150': {'name': 'mTOR signaling pathway',
                    'genes': ['MTOR', 'RPTOR', 'RICTOR', 'RHEB', 'TSC1', 'TSC2', 'AKT1']},
        'hsa04151': {'name': 'PI3K-Akt signaling pathway',
                    'genes': ['PIK3CA', 'PIK3CB', 'AKT1', 'AKT2', 'PTEN', 'MTOR']},
        'hsa04152': {'name': 'AMPK signaling pathway',
                    'genes': ['PRKAA1', 'PRKAA2', 'PRKAB1', 'PRKAG1', 'MTOR', 'ACACA']},
        
        # 代谢疾病相关
        'hsa04910': {'name': 'Insulin signaling pathway',
                    'genes': ['INSR', 'IRS1', 'IRS2', 'PIK3CA', 'AKT1', 'AKT2', 'GSK3B']},
        'hsa04920': {'name': 'Adipocytokine signaling pathway',
                    'genes': ['LEP', 'ADIPOQ', 'PPARG', 'NFKB1', 'JAK2', 'STAT3']},
        'hsa04922': {'name': 'Glucagon signaling pathway',
                    'genes': ['GCGR', 'GCG', 'PKA', 'CREB1', 'G6PC', 'PCK1']},
        'hsa04923': {'name': 'Regulation of lipolysis in adipocytes',
                    'genes': ['PNPLA2', 'LIPE', 'ABHD5', 'PLIN1', 'INS']},
        'hsa04930': {'name': 'Type II diabetes mellitus',
                    'genes': ['INS', 'INSR', 'IRS1', 'IRS2', 'SLC2A4', 'MAFA']},
        'hsa04931': {'name': 'Insulin resistance',
                    'genes': ['INSR', 'IRS1', 'SOCS3', 'PPARG', 'MTOR']},
        'hsa04932': {'name': 'Non-alcoholic fatty liver disease (NAFLD)',
                    'genes': ['PPARG', 'PNPLA3', 'TM6SF2', 'MBOAT7', 'HNF1A']},
        'hsa04940': {'name': 'Type I diabetes mellitus',
                    'genes': ['INS', 'HLA-A', 'HLA-B', 'HLA-DRB1', 'GAD']},
        
        # 脂质代谢
        'hsa00561': {'name': 'Glycerolipid metabolism',
                    'genes': ['GPAT1', 'GPAM', 'DGAT1', 'DGAT2', 'LIPE', 'MGLL']},
        'hsa00561': {'name': 'Glycerophospholipid metabolism',
                    'genes': ['GPAT', 'AGPAT', 'LPIN', 'DGAT', 'PLD', 'PLA2']},
        'hsa00590': {'name': 'Arachidonic acid metabolism',
                    'genes': ['PLA2G4A', 'PTGS1', 'PTGS2', 'ALOX5', 'CYP2C']},
        'hsa00591': {'name': 'Linoleic acid metabolism',
                    'genes': ['PLA2', 'CYP2C', 'CYP2J']},
        'hsa00592': {'name': 'alpha-Linolenic acid metabolism',
                    'genes': ['FADS1', 'FADS2', 'ALOX5', 'ALOX15']},
        'hsa00593': {'name': 'Sphingolipid metabolism',
                    'genes': ['SPTLC1', 'CERS1', 'SMPD1', 'GALC', 'HEXA']},
        'hsa00600': {'name': 'Sphingolipid signaling',
                    'genes': ['S1PR1', 'S1PR2', 'S1PR3', 'CERK', 'SPHK1', 'SPHK2']},
        'hsa00120': {'name': 'Primary bile acid biosynthesis',
                    'genes': ['CYP7A1', 'CYP7B1', 'CYP27A1', 'CYP8B1']},
        'hsa00121': {'name': 'Secondary bile acid biosynthesis',
                    'genes': ['BAAT', 'SLC27A5', 'AMACR']},
        'hsa00140': {'name': 'Steroid hormone biosynthesis',
                    'genes': ['CYP11A1', 'CYP17A1', 'CYP19A1', 'HSD3B', 'HSD17B']},
        
        # 氨基酸代谢
        'hsa00220': {'name': 'Arginine biosynthesis',
                    'genes': ['ASS1', 'ASL', 'ARG1', 'ARG2', 'NOS1', 'NOS2', 'NOS3']},
        'hsa00230': {'name': 'Purine metabolism',
                    'genes': ['ADA', 'PNP', 'HPRT1', 'XDH', 'AMPD']},
        'hsa00240': {'name': 'Pyrimidine metabolism',
                    'genes': ['CAD', 'CTPS', 'RRM1', 'RRM2', 'TYMS']},
        'hsa00250': {'name': 'Alanine, aspartate and glutamate metabolism',
                    'genes': ['GPT', 'GPT2', 'GOT1', 'GOT2', 'GLUD1', 'GLS']},
        'hsa00260': {'name': 'Glycine, serine and threonine metabolism',
                    'genes': ['SHMT1', 'SHMT2', 'GATM', 'GAMT', 'DMGDH']},
        'hsa00270': {'name': 'Cysteine and methionine metabolism',
                    'genes': ['MAT1A', 'MAT2A', 'AHCY', 'CBS', 'CSE', 'DNMT1']},
        'hsa00280': {'name': 'Valine, leucine and isoleucine degradation',
                    'genes': ['BCKDHA', 'BCKDHB', 'ACADS', 'ACADM', 'ACADVL']},
        'hsa00290': {'name': 'Valine, leucine and isoleucine biosynthesis',
                    'genes': ['BCAT1', 'BCAT2', 'ILV']},
        'hsa00300': {'name': 'Lysine degradation',
                    'genes': ['AASS', 'GCDH', 'ECHS1', 'HADHA']},
        'hsa00310': {'name': 'Lysine biosynthesis',
                    'genes': ['DAP', 'LYS']},
        'hsa00330': {'name': 'Arginine and proline metabolism',
                    'genes': ['ARG1', 'ARG2', 'OAT', 'P5CS', 'P5CR']},
        'hsa00340': {'name': 'Histidine metabolism',
                    'genes': ['HAL', 'UROC', 'HDC']},
        'hsa00350': {'name': 'Tyrosine metabolism',
                    'genes': ['TH', 'DDC', 'DBH', 'COMT', 'MAOA', 'MAOB']},
        'hsa00360': {'name': 'Phenylalanine metabolism',
                    'genes': ['PAH', 'TH', 'MAOA', 'MAOB']},
        'hsa00380': {'name': 'Tryptophan metabolism',
                    'genes': ['IDO1', 'IDO2', 'TDO2', 'KMO', 'KYNU', 'KYAT']},
        'hsa00400': {'name': 'Phenylalanine, tyrosine and tryptophan biosynthesis',
                    'genes': ['PAH', 'TH', 'TPH']},
    }
    
    def __init__(self, organism: str = 'hsa'):
        """
        初始化通路数据库
        
        Args:
            organism: 物种代码 ('hsa' = human)
        """
        self.organism = organism
        self.pathways = self.KEGG_PATHWAYS
    
    def get_pathway_genes(self, pathway_id: str) -> List[str]:
        """获取通路中的基因"""
        if pathway_id in self.pathways:
            return self.pathways[pathway_id]['genes']
        return []
    
    def get_pathway_name(self, pathway_id: str) -> str:
        """获取通路名称"""
        if pathway_id in self.pathways:
            return self.pathways[pathway_id]['name']
        return pathway_id
    
    def search_pathways(self, query: str) -> List[str]:
        """搜索通路"""
        results = []
        for pid, pdata in self.pathways.items():
            if query.lower() in pdata['name'].lower():
                results.append(pid)
        return results


class EnrichmentAnalyzer:
    """富集分析器"""
    
    def __init__(self, pathway_db: Optional[PathwayDatabase] = None):
        """
        初始化
        
        Args:
            pathway_db: 通路数据库
        """
        self.pathway_db = pathway_db or PathwayDatabase()
        self.background_genes: Set[str] = set()
    
    def set_background(self, genes: List[str]):
        """设置背景基因集"""
        self.background_genes = set(genes)
    
    def enrich(self, gene_list: List[str],
               method: str = 'hypergeometric') -> pd.DataFrame:
        """
        通路富集分析
        
        Args:
            gene_list: 感兴趣的基因列表
            method: 检验方法 ('hypergeometric', 'fisher')
        
        Returns:
            富集结果DataFrame
        """
        if not self.background_genes:
            # 使用所有通路基因作为背景
            for pid in self.pathway_db.pathways:
                self.background_genes.update(
                    self.pathway_db.get_pathway_genes(pid)
                )
        
        gene_set = set(gene_list)
        results = []
        
        for pathway_id in self.pathway_db.pathways:
            pathway_genes = set(self.pathway_db.get_pathway_genes(pathway_id))
            
            if not pathway_genes:
                continue
            
            # 计算重叠
            overlap = gene_set & pathway_genes
            overlap_size = len(overlap)
            
            if overlap_size == 0:
                continue
            
            # 统计检验
            if method == 'hypergeometric':
                p_value = self._hypergeometric_test(
                    len(self.background_genes),
                    len(pathway_genes),
                    len(gene_set),
                    overlap_size
                )
            else:
                p_value = self._fisher_test(
                    self.background_genes, pathway_genes, gene_set
                )
            
            # 计算富集比
            expected = len(pathway_genes) * len(gene_set) / len(self.background_genes)
            enrichment_ratio = overlap_size / expected if expected > 0 else 0
            
            results.append(PathwayResult(
                pathway_id=pathway_id,
                pathway_name=self.pathway_db.get_pathway_name(pathway_id),
                p_value=p_value,
                overlap_genes=list(overlap),
                overlap_size=overlap_size,
                pathway_size=len(pathway_genes),
                gene_set_size=len(gene_set),
                enrichment_ratio=enrichment_ratio
            ))
        
        # 转换为DataFrame
        df = pd.DataFrame([
            {
                'pathway_id': r.pathway_id,
                'pathway_name': r.pathway_name,
                'p_value': r.p_value,
                'overlap_size': r.overlap_size,
                'pathway_size': r.pathway_size,
                'enrichment_ratio': r.enrichment_ratio,
                'overlap_genes': ';'.join(r.overlap_genes)
            }
            for r in results
        ])
        
        # FDR校正
        if len(df) > 0:
            df['q_value'] = self._fdr_correction(df['p_value'].values)
            df = df.sort_values('p_value')
        
        return df
    
    def _hypergeometric_test(self, N: int, K: int, n: int, k: int) -> float:
        """
        超几何检验
        
        Args:
            N: 总体大小
            K: 成功项数量
            n: 抽样数量
            k: 抽样中的成功项数量
        """
        return hypergeom.sf(k - 1, N, K, n)
    
    def _fisher_test(self, background: Set[str], pathway: Set[str],
                    gene_set: Set[str]) -> float:
        """Fisher精确检验"""
        a = len(pathway & gene_set)
        b = len(pathway - gene_set)
        c = len(gene_set - pathway)
        d = len(background - pathway - gene_set)
        
        table = [[a, b], [c, d]]
        _, p_value = fisher_exact(table, alternative='greater')
        
        return p_value
    
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


class CrosstalkAnalyzer:
    """通路串扰分析器"""
    
    def __init__(self, pathway_db: Optional[PathwayDatabase] = None):
        self.pathway_db = pathway_db or PathwayDatabase()
    
    def analyze_crosstalk(self, pathway_ids: Optional[List[str]] = None) -> pd.DataFrame:
        """
        分析通路间的串扰
        
        Args:
            pathway_ids: 要分析的通路ID列表（None则分析所有）
        
        Returns:
            串扰结果DataFrame
        """
        if pathway_ids is None:
            pathway_ids = list(self.pathway_db.pathways.keys())
        
        results = []
        
        for i, pid1 in enumerate(pathway_ids):
            for pid2 in pathway_ids[i+1:]:
                genes1 = set(self.pathway_db.get_pathway_genes(pid1))
                genes2 = set(self.pathway_db.get_pathway_genes(pid2))
                
                if not genes1 or not genes2:
                    continue
                
                shared = genes1 & genes2
                
                if not shared:
                    continue
                
                # 计算Jaccard指数
                jaccard = len(shared) / len(genes1 | genes2)
                
                # 计算重叠系数
                overlap_coef = len(shared) / min(len(genes1), len(genes2))
                
                # 简单的p值估计（基于超几何分布）
                # 这里简化为基于重叠大小的启发式
                p_value = np.exp(-len(shared))
                
                results.append({
                    'pathway1': pid1,
                    'pathway1_name': self.pathway_db.get_pathway_name(pid1),
                    'pathway2': pid2,
                    'pathway2_name': self.pathway_db.get_pathway_name(pid2),
                    'shared_genes': ';'.join(shared),
                    'shared_count': len(shared),
                    'jaccard_index': jaccard,
                    'overlap_coefficient': overlap_coef,
                    'p_value': p_value
                })
        
        df = pd.DataFrame(results)
        if len(df) > 0:
            df = df.sort_values('jaccard_index', ascending=False)
        
        return df
    
    def find_crosstalk_hubs(self, crosstalk_results: pd.DataFrame,
                           top_n: int = 10) -> pd.DataFrame:
        """
        查找串扰枢纽通路
        
        Args:
            crosstalk_results: 串扰结果
            top_n: 返回前N个
        
        Returns:
            枢纽通路
        """
        # 统计每个通路的连接数
        pathway_connections = defaultdict(int)
        pathway_shared_genes = defaultdict(set)
        
        for _, row in crosstalk_results.iterrows():
            pid1 = row['pathway1']
            pid2 = row['pathway2']
            pathway_connections[pid1] += 1
            pathway_connections[pid2] += 1
            
            shared = set(row['shared_genes'].split(';')) if pd.notna(row['shared_genes']) else set()
            pathway_shared_genes[pid1].update(shared)
            pathway_shared_genes[pid2].update(shared)
        
        # 创建结果
        results = []
        for pid, connections in pathway_connections.items():
            results.append({
                'pathway_id': pid,
                'pathway_name': self.pathway_db.get_pathway_name(pid),
                'connections': connections,
                'unique_shared_genes': len(pathway_shared_genes[pid])
            })
        
        df = pd.DataFrame(results)
        if len(df) > 0:
            df = df.sort_values('connections', ascending=False).head(top_n)
        
        return df
    
    def build_crosstalk_network(self, crosstalk_results: pd.DataFrame,
                               threshold: float = 0.1) -> Dict:
        """
        构建串扰网络
        
        Args:
            crosstalk_results: 串扰结果
            threshold: Jaccard阈值
        
        Returns:
            网络数据
        """
        # 筛选边
        edges_df = crosstalk_results[crosstalk_results['jaccard_index'] >= threshold]
        
        nodes = set()
        edges = []
        
        for _, row in edges_df.iterrows():
            pid1 = row['pathway1']
            pid2 = row['pathway2']
            
            nodes.add(pid1)
            nodes.add(pid2)
            
            edges.append({
                'source': pid1,
                'target': pid2,
                'weight': row['jaccard_index'],
                'shared_genes': row['shared_genes']
            })
        
        # 节点信息
        node_data = [
            {
                'id': pid,
                'name': self.pathway_db.get_pathway_name(pid),
                'size': len(self.pathway_db.get_pathway_genes(pid))
            }
            for pid in nodes
        ]
        
        return {'nodes': node_data, 'edges': edges}


class MultiOmicsPathwayIntegration:
    """跨组学通路整合分析"""
    
    def __init__(self, pathway_db: Optional[PathwayDatabase] = None):
        self.pathway_db = pathway_db or PathwayDatabase()
        self.enrichment_analyzer = EnrichmentAnalyzer(self.pathway_db)
    
    def integrate_pathways(self,
                          genomics_hits: List[str],
                          proteomics_hits: List[str],
                          metabolomics_hits: List[str]) -> pd.DataFrame:
        """
        整合多组学数据的通路分析
        
        Args:
            genomics_hits: 基因组学显著基因
            proteomics_hits: 蛋白质组学显著蛋白
            metabolomics_hits: 代谢组学显著代谢物（映射到基因）
        
        Returns:
            整合结果
        """
        # 代谢物到基因的映射（简化示例）
        metabolite_to_gene = self._map_metabolites_to_genes(metabolomics_hits)
        
        # 合并所有基因
        all_genes = list(set(genomics_hits) | set(proteomics_hits) | set(metabolite_to_gene))
        
        # 分别进行富集分析
        genomics_enrich = self.enrichment_analyzer.enrich(genomics_hits)
        proteomics_enrich = self.enrichment_analyzer.enrich(proteomics_hits)
        metabolomics_enrich = self.enrichment_analyzer.enrich(metabolite_to_gene)
        
        # 整合结果
        pathway_scores = defaultdict(lambda: {'genomics': 1, 'proteomics': 1, 
                                              'metabolomics': 1, 'combined': 0})
        
        for df, source in [(genomics_enrich, 'genomics'),
                          (proteomics_enrich, 'proteomics'),
                          (metabolomics_enrich, 'metabolomics')]:
            for _, row in df.iterrows():
                pid = row['pathway_id']
                pval = row['p_value']
                pathway_scores[pid][source] = pval
        
        # 使用Fisher方法合并p值
        results = []
        for pid, scores in pathway_scores.items():
            # Fisher's method
            pvals = [scores['genomics'], scores['proteomics'], scores['metabolomics']]
            pvals = [p for p in pvals if p < 1]
            
            if pvals:
                chi2_stat = -2 * sum(np.log(p) for p in pvals)
                combined_p = 1 - stats.chi2.cdf(chi2_stat, df=2*len(pvals))
            else:
                combined_p = 1
            
            results.append({
                'pathway_id': pid,
                'pathway_name': self.pathway_db.get_pathway_name(pid),
                'genomics_p': scores['genomics'],
                'proteomics_p': scores['proteomics'],
                'metabolomics_p': scores['metabolomics'],
                'combined_p': combined_p
            })
        
        df = pd.DataFrame(results)
        if len(df) > 0:
            df = df.sort_values('combined_p')
        
        return df
    
    def _map_metabolites_to_genes(self, metabolites: List[str]) -> List[str]:
        """将代谢物映射到基因（简化版本）"""
        # 示例映射
        mapping = {
            'glucose': ['HK1', 'HK2', 'GPI', 'PFK'],
            'lactate': ['LDHA', 'LDHB'],
            'citrate': ['CS', 'ACO1', 'ACO2'],
            'acetyl-CoA': ['ACSS2', 'ACACA', 'ACACB'],
            'cholesterol': ['HMGCR', 'CYP51A1', 'DHCR7'],
            'palmitate': ['FASN', 'SCD'],
            'oleate': ['FADS1', 'FADS2', 'SCD'],
            'PC': ['CHKA', 'CHKB', 'PCYT1A'],
            'PE': ['PCYT2', 'PSD', 'PISD'],
        }
        
        genes = []
        for met in metabolites:
            met_lower = met.lower()
            if met_lower in mapping:
                genes.extend(mapping[met_lower])
        
        return list(set(genes))


# 便捷函数
def run_pathway_enrichment(gene_list: List[str],
                          background_genes: Optional[List[str]] = None,
                          method: str = 'hypergeometric') -> pd.DataFrame:
    """
    运行通路富集分析
    
    Args:
        gene_list: 基因列表
        background_genes: 背景基因
        method: 检验方法
    
    Returns:
        富集结果
    """
    analyzer = EnrichmentAnalyzer()
    if background_genes:
        analyzer.set_background(background_genes)
    return analyzer.enrich(gene_list, method)


def analyze_pathway_crosstalk(pathway_ids: Optional[List[str]] = None) -> pd.DataFrame:
    """
    分析通路串扰
    
    Args:
        pathway_ids: 通路ID列表
    
    Returns:
        串扰结果
    """
    analyzer = CrosstalkAnalyzer()
    return analyzer.analyze_crosstalk(pathway_ids)
