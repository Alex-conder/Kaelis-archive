"""
肽段鉴定模块 - Peptide Identification Module

基于质谱数据的肽段-谱图匹配（Peptide-Spectrum Matching, PSM）
支持数据库搜索、打分算法、FDR控制
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
import re


@dataclass
class PeptideMatch:
    """肽段匹配结果"""
    peptide_sequence: str
    spectrum_id: str
    score: float
    q_value: float
    proteins: List[str]
    modifications: List[Dict]
    charge: int
    mz: float
    rt: float
    is_decoy: bool = False


@dataclass
class PeptideSpectrumMatch:
    """肽段-谱图匹配结果"""
    spectrum_id: str
    scan_number: int
    precursor_mz: float
    precursor_charge: int
    rt: float
    matched_peptides: List[PeptideMatch]
    
    @property
    def best_match(self) -> Optional[PeptideMatch]:
        """获取最佳匹配"""
        if not self.matched_peptides:
            return None
        return max(self.matched_peptides, key=lambda x: x.score)


class SpectrumSimulator:
    """理论谱图模拟器"""
    
    # 氨基酸单同位素质量
    AA_MASS = {
        'A': 71.03711, 'R': 156.10111, 'N': 114.04293, 'D': 115.02694,
        'C': 103.00919, 'E': 129.04259, 'Q': 128.05858, 'G': 57.02146,
        'H': 137.05891, 'I': 113.08406, 'L': 113.08406, 'K': 128.09496,
        'M': 131.04049, 'F': 147.06841, 'P': 97.05276, 'S': 87.03203,
        'T': 101.04768, 'W': 186.07931, 'Y': 163.06333, 'V': 99.06841
    }
    
    # 常见修饰质量
    MOD_MASS = {
        'Carbamidomethyl': 57.02146,  # 半胱氨酸烷基化
        'Oxidation': 15.99491,         # 甲硫氨酸氧化
        'Phospho': 79.96633,           # 磷酸化
        'Acetyl': 42.01057,            # 乙酰化
    }
    
    PROTON_MASS = 1.00728
    WATER_MASS = 18.01056
    
    def calculate_peptide_mass(self, sequence: str, modifications: List[Dict] = None) -> float:
        """
        计算肽段分子量
        
        Args:
            sequence: 氨基酸序列
            modifications: 修饰列表
        
        Returns:
            单同位素分子量
        """
        mass = sum(self.AA_MASS.get(aa, 0) for aa in sequence)
        mass += self.WATER_MASS  # N-term和C-term的H2O
        
        if modifications:
            for mod in modifications:
                mass += mod.get('mass', 0)
        
        return mass
    
    def simulate_msms(self, sequence: str, charge: int = 2, 
                      modifications: List[Dict] = None,
                      ion_types: List[str] = None) -> Dict:
        """
        模拟MS/MS碎裂谱图
        
        Args:
            sequence: 肽段序列
            charge: 电荷状态
            modifications: 修饰列表
            ion_types: 离子类型 ['b', 'y']
        
        Returns:
            理论m/z和强度
        """
        if ion_types is None:
            ion_types = ['b', 'y']
        
        peptide_mass = self.calculate_peptide_mass(sequence, modifications)
        n = len(sequence)
        
        theoretical_ions = {'mz': [], 'intensity': [], 'type': [], 'position': []}
        
        for ion_type in ion_types:
            for i in range(1, n):
                if ion_type == 'b':
                    # b离子: N端碎裂
                    frag_seq = sequence[:i]
                    frag_mass = sum(self.AA_MASS.get(aa, 0) for aa in frag_seq)
                    frag_mass += self.PROTON_MASS  # b离子是酰基离子
                else:  # y离子
                    # y离子: C端碎裂
                    frag_seq = sequence[-i:]
                    frag_mass = sum(self.AA_MASS.get(aa, 0) for aa in frag_seq)
                    frag_mass += self.WATER_MASS + self.PROTON_MASS  # y离子需要加H2O和H
                
                # 计算不同电荷状态的m/z
                for z in range(1, min(charge + 1, 4)):
                    mz = (frag_mass + z * self.PROTON_MASS) / z
                    theoretical_ions['mz'].append(mz)
                    theoretical_ions['intensity'].append(1.0 / z)  # 高电荷强度较低
                    theoretical_ions['type'].append(f"{ion_type}{i}+{z}")
                    theoretical_ions['position'].append(i)
        
        return theoretical_ions


class PeptideIdentifier:
    """肽段鉴定器"""
    
    def __init__(self, tolerance_da: float = 0.02):
        """
        初始化鉴定器
        
        Args:
            tolerance_da: 质量容差（Da）
        """
        self.tolerance_da = tolerance_da
        self.simulator = SpectrumSimulator()
        self.target_db: Dict[str, Dict] = {}
        self.decoy_db: Dict[str, Dict] = {}
        
    def build_database(self, protein_sequences: Dict[str, str], 
                       enzyme: str = 'trypsin',
                       missed_cleavages: int = 2,
                       min_length: int = 6,
                       max_length: int = 50) -> int:
        """
        构建肽段数据库（目标库和诱饵库）
        
        Args:
            protein_sequences: {protein_id: sequence}
            enzyme: 酶切类型
            missed_cleavages: 最大漏切数
            min_length: 最小肽段长度
            max_length: 最大肽段长度
        
        Returns:
            肽段总数
        """
        self.target_db = {}
        self.decoy_db = {}
        
        for prot_id, sequence in protein_sequences.items():
            # 酶切
            peptides = self._digest_sequence(
                sequence, enzyme, missed_cleavages, min_length, max_length
            )
            
            for pep_seq in peptides:
                mass = self.simulator.calculate_peptide_mass(pep_seq)
                
                # 目标肽段
                self.target_db[pep_seq] = {
                    'sequence': pep_seq,
                    'mass': mass,
                    'proteins': [prot_id],
                    'is_decoy': False
                }
                
                # 诱饵肽段（反转序列）
                decoy_seq = self._create_decoy(pep_seq)
                if decoy_seq != pep_seq:
                    self.decoy_db[decoy_seq] = {
                        'sequence': decoy_seq,
                        'mass': mass,
                        'proteins': ['DECOY_' + prot_id],
                        'is_decoy': True
                    }
        
        return len(self.target_db) + len(self.decoy_db)
    
    def _digest_sequence(self, sequence: str, enzyme: str,
                         missed_cleavages: int, min_len: int, max_len: int) -> List[str]:
        """酶切蛋白质序列"""
        if enzyme == 'trypsin':
            # 胰蛋白酶: K或R后切，但KP和RP不切
            sites = [0]
            for i in range(len(sequence) - 1):
                if sequence[i] in 'KR' and sequence[i+1] != 'P':
                    sites.append(i + 1)
            sites.append(len(sequence))
        else:
            sites = list(range(len(sequence) + 1))
        
        peptides = []
        for start_idx in range(len(sites) - 1):
            for missed in range(missed_cleavages + 1):
                end_idx = start_idx + missed + 1
                if end_idx >= len(sites):
                    break
                
                pep = sequence[sites[start_idx]:sites[end_idx]]
                if min_len <= len(pep) <= max_len:
                    peptides.append(pep)
        
        return peptides
    
    def _create_decoy(self, sequence: str) -> str:
        """创建诱饵肽段（反转序列，保留C端氨基酸）"""
        if len(sequence) <= 2:
            return sequence[::-1]
        # 保留C端氨基酸，中间部分反转
        return sequence[-2::-1] + sequence[-1]
    
    def identify_peptides(self, spectra: List[Dict]) -> List[PeptideSpectrumMatch]:
        """
        鉴定肽段
        
        Args:
            spectra: 实验谱图列表 [{mz: [], intensity: [], ...}]
        
        Returns:
            PSM列表
        """
        psms = []
        all_scores = []
        
        for spectrum in spectra:
            psm = self._search_spectrum(spectrum)
            psms.append(psm)
            all_scores.extend([m.score for m in psm.matched_peptides])
        
        # 计算FDR并分配q-value
        self._calculate_fdr(psms)
        
        return psms
    
    def _search_spectrum(self, spectrum: Dict) -> PeptideSpectrumMatch:
        """搜索单个谱图"""
        precursor_mz = spectrum.get('precursor_mz', 0)
        charge = spectrum.get('charge', 2)
        
        # 计算前体质量
        precursor_mass = (precursor_mz - self.simulator.PROTON_MASS) * charge
        
        # 质量过滤候选肽段
        candidates = []
        for db in [self.target_db, self.decoy_db]:
            for pep_data in db.values():
                if abs(pep_data['mass'] - precursor_mass) < self.tolerance_da * charge:
                    candidates.append(pep_data)
        
        # 谱图比对打分
        matches = []
        exp_mz = np.array(spectrum.get('mz', []))
        exp_intensity = np.array(spectrum.get('intensity', []))
        
        for cand in candidates:
            theoretical = self.simulator.simulate_msms(
                cand['sequence'], charge
            )
            
            score = self._score_spectrum(exp_mz, exp_intensity, theoretical)
            
            match = PeptideMatch(
                peptide_sequence=cand['sequence'],
                spectrum_id=spectrum.get('id', ''),
                score=score,
                q_value=1.0,
                proteins=cand['proteins'],
                modifications=[],
                charge=charge,
                mz=precursor_mz,
                rt=spectrum.get('rt', 0),
                is_decoy=cand.get('is_decoy', False)
            )
            matches.append(match)
        
        # 按分数排序
        matches.sort(key=lambda x: x.score, reverse=True)
        
        return PeptideSpectrumMatch(
            spectrum_id=spectrum.get('id', ''),
            scan_number=spectrum.get('scan', 0),
            precursor_mz=precursor_mz,
            precursor_charge=charge,
            rt=spectrum.get('rt', 0),
            matched_peptides=matches[:10]  # 保留top 10
        )
    
    def _score_spectrum(self, exp_mz: np.ndarray, exp_int: np.ndarray,
                        theoretical: Dict) -> float:
        """
        谱图比对打分
        
        使用简单的共享峰计数和强度匹配
        """
        if len(exp_mz) == 0:
            return 0
        
        score = 0
        theo_mz = theoretical['mz']
        theo_int = theoretical['intensity']
        
        for tmz, tint in zip(theo_mz, theo_int):
            # 查找匹配的实验峰
            matches = np.abs(exp_mz - tmz) < self.tolerance_da
            if np.any(matches):
                matched_int = exp_int[matches]
                # 基于强度和匹配峰数打分
                score += tint * np.max(matched_int) / (np.max(exp_int) + 1e-10)
        
        return score
    
    def _calculate_fdr(self, psms: List[PeptideSpectrumMatch], 
                       fdr_threshold: float = 0.01):
        """
        计算FDR并分配q-value
        
        使用target-decoy方法
        """
        # 收集所有匹配
        all_matches = []
        for psm in psms:
            for match in psm.matched_peptides:
                all_matches.append(match)
        
        # 按分数排序
        all_matches.sort(key=lambda x: x.score, reverse=True)
        
        # 计算q-value
        target_count = 0
        decoy_count = 0
        
        for match in all_matches:
            if match.is_decoy:
                decoy_count += 1
            else:
                target_count += 1
            
            # FDR = decoy / target
            fdr = decoy_count / max(target_count, 1)
            match.q_value = min(fdr, 1.0)
        
        # 逆向传播最小q-value
        min_q = 1.0
        for match in reversed(all_matches):
            min_q = min(min_q, match.q_value)
            match.q_value = min_q
    
    def get_identified_peptides(self, psms: List[PeptideSpectrumMatch],
                                q_value_threshold: float = 0.01) -> pd.DataFrame:
        """
        获取鉴定结果表
        
        Args:
            psms: PSM列表
            q_value_threshold: q-value阈值
        
        Returns:
            鉴定结果DataFrame
        """
        results = []
        seen_peptides = set()
        
        for psm in psms:
            best = psm.best_match
            if best and best.q_value <= q_value_threshold and not best.is_decoy:
                if best.peptide_sequence not in seen_peptides:
                    seen_peptides.add(best.peptide_sequence)
                    results.append({
                        'peptide': best.peptide_sequence,
                        'proteins': ';'.join(best.proteins),
                        'score': best.score,
                        'q_value': best.q_value,
                        'charge': best.charge,
                        'mz': best.mz,
                        'rt': best.rt
                    })
        
        return pd.DataFrame(results)


class PeptideIndexer:
    """肽段索引器 - 用于快速肽段-蛋白质映射"""
    
    def __init__(self):
        self.peptide_to_proteins: Dict[str, List[str]] = defaultdict(list)
        self.protein_to_peptides: Dict[str, List[str]] = defaultdict(list)
    
    def index_proteins(self, proteins: Dict[str, str], 
                       enzyme: str = 'trypsin'):
        """
        索引蛋白质-肽段关系
        
        Args:
            proteins: {protein_id: sequence}
            enzyme: 酶切类型
        """
        simulator = SpectrumSimulator()
        identifier = PeptideIdentifier()
        
        for prot_id, sequence in proteins.items():
            peptides = identifier._digest_sequence(sequence, enzyme, 0, 6, 50)
            for pep in peptides:
                self.peptide_to_proteins[pep].append(prot_id)
                self.protein_to_peptides[prot_id].append(pep)
    
    def get_proteins(self, peptide: str) -> List[str]:
        """获取包含该肽段的蛋白质"""
        return self.peptide_to_proteins.get(peptide, [])
    
    def get_peptides(self, protein: str) -> List[str]:
        """获取蛋白质的肽段列表"""
        return self.protein_to_peptides.get(protein, [])


# 便捷函数
def identify_peptides_from_spectra(spectra: List[Dict],
                                   protein_db: Dict[str, str],
                                   tolerance_da: float = 0.02,
                                   fdr: float = 0.01) -> pd.DataFrame:
    """
    从质谱数据中鉴定肽段
    
    Args:
        spectra: 实验谱图列表
        protein_db: 蛋白质序列数据库
        tolerance_da: 质量容差
        fdr: FDR阈值
    
    Returns:
        鉴定结果DataFrame
    """
    identifier = PeptideIdentifier(tolerance_da=tolerance_da)
    
    # 构建数据库
    n_peptides = identifier.build_database(protein_db)
    print(f"Database built: {n_peptides} peptides")
    
    # 鉴定
    psms = identifier.identify_peptides(spectra)
    
    # 获取结果
    return identifier.get_identified_peptides(psms, fdr)
