"""
mzIdentML 文件解析器 - MZIdentML Parser

支持解析 mzIdentML 格式的蛋白质鉴定结果文件。
"""

import gzip
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Union
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PeptideEvidence:
    """肽段证据"""
    peptide_sequence: str
    modified_sequence: Optional[str]
    charge: int
    mz: float
    score: float
    q_value: Optional[float] = None
    pep: Optional[float] = None
    proteins: List[str] = field(default_factory=list)


@dataclass
class ProteinIdentification:
    """蛋白质鉴定结果"""
    protein_accession: str
    protein_name: Optional[str]
    description: Optional[str]
    peptide_evidences: List[PeptideEvidence] = field(default_factory=list)
    coverage: Optional[float] = None
    score: Optional[float] = None
    
    @property
    def unique_peptides(self) -> int:
        """唯一肽段数"""
        sequences = set()
        for ev in self.peptide_evidences:
            sequences.add(ev.peptide_sequence)
        return len(sequences)
    
    @property
    def total_psms(self) -> int:
        """总PSM数"""
        return len(self.peptide_evidences)


class MZIdentMLParser:
    """
    mzIdentML 文件解析器
    
    解析蛋白质组学鉴定结果。
    """
    
    NAMESPACES = {
        'mzid': 'http://psidev.info/psi/pi/mzIdentML/1.1'
    }
    
    def __init__(self, filepath: Union[str, Path]):
        self.filepath = Path(filepath)
        self.file_size = self.filepath.stat().st_size
        
        # 存储解析的数据
        self.peptides: Dict[str, Dict] = {}
        self.proteins: Dict[str, Dict] = {}
        self.spectrum_identifications: List[Dict] = []
        
        logger.info(f"MZIdentML Parser initialized: {self.filepath}")
    
    def parse(self) -> Iterator[ProteinIdentification]:
        """
        解析 mzIdentML 文件
        
        Yields:
            ProteinIdentification: 蛋白质鉴定结果
        """
        logger.info(f"Starting to parse {self.filepath}")
        
        open_func = gzip.open if str(self.filepath).endswith('.gz') else open
        
        try:
            with open_func(self.filepath, 'rb') as f:
                # 注册命名空间
                for prefix, uri in self.NAMESPACES.items():
                    ET.register_namespace(prefix, uri)
                
                tree = ET.parse(f)
                root = tree.getroot()
                
                # 解析序列集合
                self._parse_sequence_collection(root)
                
                # 解析分析数据
                self._parse_analysis_data(root)
                
                # 构建蛋白质鉴定结果
                for prot_id, prot_data in self.proteins.items():
                    protein = self._build_protein_identification(prot_id, prot_data)
                    if protein:
                        yield protein
                
        except Exception as e:
            logger.error(f"Failed to parse mzIdentML: {e}")
            raise
    
    def _parse_sequence_collection(self, root: ET.Element):
        """解析序列集合（肽段和蛋白）"""
        seq_collection = root.find('.//mzid:SequenceCollection', self.NAMESPACES)
        
        if seq_collection is None:
            return
        
        # 解析DBSequence（蛋白质序列）
        for db_seq in seq_collection.findall('.//mzid:DBSequence', self.NAMESPACES):
            accession = db_seq.get('accession', '')
            id_ref = db_seq.get('id', '')
            
            name = None
            description = None
            
            for cv_param in db_seq.findall('.//mzid:cvParam', self.NAMESPACES):
                acc = cv_param.get('accession', '')
                if acc == 'MS:1001088':  # protein description
                    description = cv_param.get('value', '')
                elif acc == 'MS:1001085':  # protein name
                    name = cv_param.get('value', '')
            
            self.proteins[id_ref] = {
                'accession': accession,
                'name': name,
                'description': description,
                'peptide_refs': []
            }
        
        # 解析Peptide（肽段序列）
        for peptide in seq_collection.findall('.//mzid:Peptide', self.NAMESPACES):
            pep_id = peptide.get('id', '')
            seq_elem = peptide.find('.//mzid:PeptideSequence', self.NAMESPACES)
            
            if seq_elem is not None:
                sequence = seq_elem.text or ''
                
                # 解析修饰
                modifications = []
                for mod in peptide.findall('.//mzid:Modification', self.NAMESPACES):
                    location = mod.get('location', '')
                    mass_delta = mod.get('monoisotopicMassDelta', '')
                    
                    for cv_param in mod.findall('.//mzid:cvParam', self.NAMESPACES):
                        mod_name = cv_param.get('name', '')
                        modifications.append({
                            'location': int(location) if location else None,
                            'name': mod_name,
                            'mass_delta': float(mass_delta) if mass_delta else 0
                        })
                
                self.peptides[pep_id] = {
                    'sequence': sequence,
                    'modifications': modifications
                }
        
        # 解析PeptideEvidence
        for pep_ev in seq_collection.findall('.//mzid:PeptideEvidence', self.NAMESPACES):
            pep_ev_id = pep_ev.get('id', '')
            peptide_ref = pep_ev.get('peptide_ref', '')
            db_seq_ref = pep_ev.get('dBSequence_ref', '')
            
            # 关联到蛋白质
            if db_seq_ref in self.proteins:
                self.proteins[db_seq_ref]['peptide_refs'].append({
                    'peptide_evidence_id': pep_ev_id,
                    'peptide_ref': peptide_ref
                })
    
    def _parse_analysis_data(self, root: ET.Element):
        """解析分析数据（鉴定结果）"""
        analysis_data = root.find('.//mzid:DataCollection/mzid:AnalysisData', self.NAMESPACES)
        
        if analysis_data is None:
            return
        
        # 解析SpectrumIdentificationList
        for spec_id_list in analysis_data.findall('.//mzid:SpectrumIdentificationList', self.NAMESPACES):
            for spec_id_item in spec_id_list.findall('.//mzid:SpectrumIdentificationResult', self.NAMESPACES):
                spectrum_id = spec_id_item.get('spectrumID', '')
                
                for ident_item in spec_id_item.findall('.//mzid:SpectrumIdentificationItem', self.NAMESPACES):
                    ident_data = self._parse_identification_item(ident_item)
                    if ident_data:
                        self.spectrum_identifications.append(ident_data)
    
    def _parse_identification_item(self, ident_item: ET.Element) -> Optional[Dict]:
        """解析单个鉴定项"""
        peptide_ref = ident_item.get('peptide_ref', '')
        peptide_evidence_ref = ident_item.get('peptideEvidence_ref', '')
        charge = int(ident_item.get('chargeState', 0))
        experimental_mz = float(ident_item.get('experimentalMassToCharge', 0))
        calculated_mz = float(ident_item.get('calculatedMassToCharge', 0))
        
        # 提取得分和统计值
        scores = {}
        q_value = None
        pep = None
        
        for cv_param in ident_item.findall('.//mzid:cvParam', self.NAMESPACES):
            acc = cv_param.get('accession', '')
            value = cv_param.get('value', '')
            name = cv_param.get('name', '')
            
            # 常见得分类型
            if 'score' in name.lower() or acc in ['MS:1001172', 'MS:1001155', 'MS:1002052']:
                try:
                    scores[name] = float(value)
                except:
                    pass
            
            # Q-value (FDR)
            elif acc == 'MS:1002354' or 'q-value' in name.lower():
                try:
                    q_value = float(value)
                except:
                    pass
            
            # Posterior Error Probability
            elif acc == 'MS:1002355' or 'pep' in name.lower():
                try:
                    pep = float(value)
                except:
                    pass
        
        # 获取主要得分
        main_score = scores.get('score', list(scores.values())[0] if scores else 0)
        
        return {
            'peptide_ref': peptide_ref,
            'peptide_evidence_ref': peptide_evidence_ref,
            'charge': charge,
            'experimental_mz': experimental_mz,
            'calculated_mz': calculated_mz,
            'score': main_score,
            'q_value': q_value,
            'pep': pep,
            'spectrum_id': ident_item.get('spectrumID', '')
        }
    
    def _build_protein_identification(
        self, 
        protein_id: str, 
        prot_data: Dict
    ) -> Optional[ProteinIdentification]:
        """构建蛋白质鉴定对象"""
        peptide_evidences = []
        
        for pep_ref_info in prot_data.get('peptide_refs', []):
            peptide_ref = pep_ref_info.get('peptide_ref', '')
            
            if peptide_ref not in self.peptides:
                continue
            
            peptide_data = self.peptides[peptide_ref]
            
            # 查找对应的鉴定结果
            for ident in self.spectrum_identifications:
                if ident['peptide_ref'] == peptide_ref:
                    # 构建修饰序列
                    mod_seq = self._build_modified_sequence(
                        peptide_data['sequence'],
                        peptide_data.get('modifications', [])
                    )
                    
                    evidence = PeptideEvidence(
                        peptide_sequence=peptide_data['sequence'],
                        modified_sequence=mod_seq,
                        charge=ident['charge'],
                        mz=ident['experimental_mz'],
                        score=ident['score'],
                        q_value=ident['q_value'],
                        pep=ident['pep'],
                        proteins=[prot_data['accession']]
                    )
                    
                    peptide_evidences.append(evidence)
                    break
        
        if not peptide_evidences:
            return None
        
        return ProteinIdentification(
            protein_accession=prot_data['accession'],
            protein_name=prot_data.get('name'),
            description=prot_data.get('description'),
            peptide_evidences=peptide_evidences,
            score=max([ev.score for ev in peptide_evidences]) if peptide_evidences else None
        )
    
    def _build_modified_sequence(
        self, 
        sequence: str, 
        modifications: List[Dict]
    ) -> str:
        """构建带修饰的序列表示"""
        if not modifications:
            return sequence
        
        seq_list = list(sequence)
        
        # 按位置排序（从后往前插入避免索引问题）
        sorted_mods = sorted(modifications, key=lambda x: x.get('location', 0) or 0, reverse=True)
        
        for mod in sorted_mods:
            loc = mod.get('location')
            name = mod.get('name', '')
            
            if loc and 1 <= loc <= len(sequence):
                # 在对应位置后插入修饰标记
                mod_str = f"[{name}]"
                seq_list.insert(loc, mod_str)
        
        return ''.join(seq_list)
    
    def get_protein_list(self, min_unique_peptides: int = 1) -> List[ProteinIdentification]:
        """
        获取蛋白质列表
        
        Args:
            min_unique_peptides: 最小唯一肽段数
            
        Returns:
            List[ProteinIdentification]: 蛋白质列表
        """
        proteins = list(self.parse())
        
        # 过滤
        filtered = [p for p in proteins if p.unique_peptides >= min_unique_peptides]
        
        # 按得分排序
        filtered.sort(key=lambda x: x.score or 0, reverse=True)
        
        return filtered
    
    def get_file_summary(self) -> Dict[str, Any]:
        """获取文件摘要"""
        proteins = list(self.parse())
        
        total_psms = sum(p.total_psms for p in proteins)
        
        # 统计修饰
        modifications = {}
        for p in proteins:
            for ev in p.peptide_evidences:
                if ev.modified_sequence:
                    # 简单统计修饰数量
                    mod_count = ev.modified_sequence.count('[')
                    modifications[ev.peptide_sequence] = modifications.get(ev.peptide_sequence, 0) + mod_count
        
        return {
            'file_size_mb': round(self.file_size / (1024 * 1024), 2),
            'protein_count': len(proteins),
            'total_psms': total_psms,
            'avg_peptides_per_protein': total_psms / len(proteins) if proteins else 0,
            'top_proteins': [p.protein_accession for p in proteins[:5]]
        }


# 便捷函数
def parse_mzidentml(filepath: str, min_unique_peptides: int = 1) -> List[ProteinIdentification]:
    """便捷函数：解析 mzIdentML 文件"""
    parser = MZIdentMLParser(filepath)
    return parser.get_protein_list(min_unique_peptides)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=== 测试 mzIdentML 解析器 ===")
    print("Module loaded successfully!")
    print("Supported features:")
    print("  - mzIdentML 1.1 format parsing")
    print("  - Peptide-spectrum matching (PSM) extraction")
    print("  - Protein identification with peptide evidences")
    print("  - Post-translational modification parsing")
