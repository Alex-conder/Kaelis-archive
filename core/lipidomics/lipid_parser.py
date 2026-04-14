"""
脂质解析模块 - Lipid Parser Module

支持多种脂质命名法的解析：
1. LIPID MAPS 命名法
2. Shorthand notation (e.g., PC(16:0/18:1))
3. Common names (e.g., Phosphatidylcholine)
4. Systematic names (IUPAC)
"""

import re
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
from enum import Enum


class LipidClass(Enum):
    """脂质分类"""
    # 甘油脂类
    TG = "Triacylglycerol"
    DG = "Diacylglycerol"
    MG = "Monoacylglycerol"
    
    # 甘油磷脂类
    PC = "Phosphatidylcholine"
    PE = "Phosphatidylethanolamine"
    PS = "Phosphatidylserine"
    PI = "Phosphatidylinositol"
    PG = "Phosphatidylglycerol"
    PA = "Phosphatidic acid"
    CL = "Cardiolipin"
    
    # 鞘脂类
    SM = "Sphingomyelin"
    CER = "Ceramide"
    HEX_CER = "Hexosylceramide"
    GANG = "Ganglioside"
    
    # 固醇脂类
    ST = "Sterol"
    SE = "Steryl ester"
    
    # 脂肪酸
    FA = "Fatty acid"
    
    # 其他
    LPC = "Lysophosphatidylcholine"
    LPE = "Lysophosphatidylethanolamine"
    OXPC = "Oxidized phosphatidylcholine"
    OXPE = "Oxidized phosphatidylethanolamine"
    UNKNOWN = "Unknown"


@dataclass
class FattyAcidChain:
    """脂肪酸链信息"""
    carbon_count: int
    double_bonds: int
    position: Optional[str] = None  # sn1, sn2, etc.
    hydroxyl_groups: int = 0
    oxidized: bool = False
    
    @property
    def shorthand(self) -> str:
        """简写形式 (e.g., 16:0, 18:1)"""
        return f"{self.carbon_count}:{self.double_bonds}"
    
    @property
    def mass(self) -> float:
        """计算脂肪酸质量"""
        # CH3-(CH2)n-COOH = C_n H_(2n+1) COOH
        # 减去水 (形成酯键时)
        c = self.carbon_count
        db = self.double_bonds
        return c * 12.0 + (2 * c - 2 * db - 1) * 1.00783 + 2 * 15.99491


@dataclass
class Lipid:
    """脂质分子信息"""
    lipid_class: LipidClass
    chains: List[FattyAcidChain]
    adduct: Optional[str] = None  # 加合物类型 [M+H]+, [M-H]-
    
    @property
    def total_carbons(self) -> int:
        """总碳数"""
        return sum(chain.carbon_count for chain in self.chains)
    
    @property
    def total_double_bonds(self) -> int:
        """总双键数"""
        return sum(chain.double_bonds for chain in self.chains)
    
    @property
    def shorthand(self) -> str:
        """简写表示 (e.g., PC(16:0/18:1))"""
        class_name = self.lipid_class.name
        chains_str = '/'.join(chain.shorthand for chain in self.chains)
        return f"{class_name}({chains_str})"
    
    @property
    def molecular_formula(self) -> str:
        """分子式"""
        # 基于脂质类别和链计算
        base_formula = self._get_base_formula()
        chain_formula = self._calculate_chain_formula()
        
        # 合并
        return self._merge_formulas(base_formula, chain_formula)
    
    def _get_base_formula(self) -> Dict[str, int]:
        """获取脂质类别的基本分子式"""
        formulas = {
            LipidClass.TG: {'C': 3, 'H': 5, 'O': 3},  # 甘油骨架
            LipidClass.DG: {'C': 3, 'H': 6, 'O': 3},
            LipidClass.MG: {'C': 3, 'H': 8, 'O': 3},
            LipidClass.PC: {'C': 5, 'H': 14, 'N': 1, 'O': 4, 'P': 1},
            LipidClass.PE: {'C': 3, 'H': 9, 'N': 1, 'O': 4, 'P': 1},
            LipidClass.PS: {'C': 3, 'H': 8, 'N': 1, 'O': 6, 'P': 1},
            LipidClass.PI: {'C': 3, 'H': 9, 'O': 6, 'P': 1},
            LipidClass.PG: {'C': 3, 'H': 9, 'O': 5, 'P': 1},
            LipidClass.PA: {'C': 3, 'H': 9, 'O': 4, 'P': 1},
            LipidClass.SM: {'C': 5, 'H': 13, 'N': 2, 'O': 2, 'P': 1},
            LipidClass.CER: {'C': 0, 'H': 3, 'N': 1, 'O': 1},
        }
        return formulas.get(self.lipid_class, {'C': 0, 'H': 0, 'O': 0})
    
    def _calculate_chain_formula(self) -> Dict[str, int]:
        """计算脂肪酸链的分子式"""
        total = {'C': 0, 'H': 0, 'O': 0}
        
        for chain in self.chains:
            c = chain.carbon_count
            db = chain.double_bonds
            # 脂肪酸链: C_n H_(2n-2db-1) (酯化后)
            total['C'] += c
            total['H'] += 2 * c - 2 * db - 1
            total['O'] += 1  # 酯键氧
        
        return total
    
    def _merge_formulas(self, base: Dict[str, int], 
                        chains: Dict[str, int]) -> str:
        """合并分子式"""
        merged = {}
        for k in set(base.keys()) | set(chains.keys()):
            merged[k] = base.get(k, 0) + chains.get(k, 0)
        
        # 减去形成酯键时失去的水
        n_esters = len(self.chains)
        merged['H'] -= n_esters
        merged['O'] -= n_esters
        
        # 格式化
        order = ['C', 'H', 'N', 'O', 'P', 'S']
        parts = [f"{k}{merged[k]}" for k in order if k in merged and merged[k] > 0]
        return ''.join(parts)
    
    @property
    def theoretical_mz(self) -> float:
        """理论m/z值"""
        formula = self.molecular_formula
        mass = self._formula_to_mass(formula)
        
        # 根据加合物调整
        if self.adduct == '[M+H]+':
            mass += 1.00728
        elif self.adduct == '[M+Na]+':
            mass += 22.98977
        elif self.adduct == '[M-H]-':
            mass -= 1.00728
        elif self.adduct == '[M+NH4]+':
            mass += 18.03383
        
        return mass
    
    def _formula_to_mass(self, formula: str) -> float:
        """从分子式计算质量"""
        # 元素质量
        masses = {'C': 12.0, 'H': 1.00783, 'N': 14.00307, 
                 'O': 15.99491, 'P': 30.97376, 'S': 31.97207}
        
        total = 0
        for element, count in re.findall(r'([A-Z][a-z]*)(\d*)', formula):
            count = int(count) if count else 1
            total += masses.get(element, 0) * count
        
        return total


class LipidParser:
    """脂质名称解析器"""
    
    # 脂质类别缩写映射
    CLASS_ABBREVIATIONS = {
        'TG': LipidClass.TG, 'TAG': LipidClass.TG,
        'DG': LipidClass.DG, 'DAG': LipidClass.DG,
        'MG': LipidClass.MG, 'MAG': LipidClass.MG,
        'PC': LipidClass.PC, 'GPCho': LipidClass.PC,
        'PE': LipidClass.PE, 'GPEtn': LipidClass.PE,
        'PS': LipidClass.PS, 'GPSer': LipidClass.PS,
        'PI': LipidClass.PI, 'GPIns': LipidClass.PI,
        'PG': LipidClass.PG, 'GPGro': LipidClass.PG,
        'PA': LipidClass.PA, 'GP': LipidClass.PA,
        'CL': LipidClass.CL, 'CDP-DG': LipidClass.CL,
        'SM': LipidClass.SM, 'CerPCho': LipidClass.SM,
        'Cer': LipidClass.CER, 'Ceramide': LipidClass.CER,
        'HexCer': LipidClass.HEX_CER, 'Hex2Cer': LipidClass.HEX_CER,
        'LPC': LipidClass.LPC, 'LysoPC': LipidClass.LPC,
        'LPE': LipidClass.LPE, 'LysoPE': LipidClass.LPE,
        'ST': LipidClass.ST, 'SE': LipidClass.SE,
        'FA': LipidClass.FA,
    }
    
    def __init__(self):
        self.chain_pattern = re.compile(
            r'(\d+):(\d+)(?:\s*\(\s*(\d+[EZ]?)\s*\))?'  # 18:1(9Z)
        )
    
    def parse(self, name: str) -> Optional[Lipid]:
        """
        解析脂质名称
        
        Args:
            name: 脂质名称 (e.g., "PC(16:0/18:1(9Z))", "TG 52:3")
        
        Returns:
            Lipid对象或None
        """
        name = name.strip()
        
        # 尝试解析 shorthand notation
        if '(' in name and ')' in name:
            return self._parse_shorthand(name)
        
        # 尝试解析总组成表示法 (e.g., PC 34:1)
        if ':' in name and '/' not in name:
            return self._parse_total_composition(name)
        
        # 尝试解析LIPID MAPS ID
        if name.startswith('LM'):
            return self._parse_lipid_maps_id(name)
        
        return None
    
    def _parse_shorthand(self, name: str) -> Optional[Lipid]:
        """解析简写表示法 (e.g., PC(16:0/18:1))"""
        match = re.match(r'([A-Za-z]+)\s*\(\s*([^)]+)\s*\)', name)
        if not match:
            return None
        
        class_abbr = match.group(1).upper()
        chains_str = match.group(2)
        
        lipid_class = self.CLASS_ABBREVIATIONS.get(class_abbr, LipidClass.UNKNOWN)
        
        # 解析链
        chains = self._parse_chains(chains_str)
        
        return Lipid(lipid_class=lipid_class, chains=chains)
    
    def _parse_total_composition(self, name: str) -> Optional[Lipid]:
        """解析总组成表示法 (e.g., PC 34:1)"""
        parts = name.split()
        if len(parts) != 2:
            return None
        
        class_abbr = parts[0].upper()
        composition = parts[1]
        
        lipid_class = self.CLASS_ABBREVIATIONS.get(class_abbr, LipidClass.UNKNOWN)
        
        # 解析总组成
        match = re.match(r'(\d+):(\d+)', composition)
        if not match:
            return None
        
        total_c = int(match.group(1))
        total_db = int(match.group(2))
        
        # 创建简化的链（不区分具体链）
        # 假设平均分配
        if lipid_class in [LipidClass.TG]:
            n_chains = 3
        elif lipid_class in [LipidClass.PC, LipidClass.PE, LipidClass.PS, 
                            LipidClass.PI, LipidClass.PG, LipidClass.DG, LipidClass.SM]:
            n_chains = 2
        elif lipid_class in [LipidClass.LPC, LipidClass.LPE, LipidClass.MG]:
            n_chains = 1
        else:
            n_chains = 2
        
        avg_c = total_c // n_chains
        avg_db = total_db // n_chains
        
        chains = [
            FattyAcidChain(carbon_count=avg_c, double_bonds=avg_db, position=f'sn{i+1}')
            for i in range(n_chains)
        ]
        
        return Lipid(lipid_class=lipid_class, chains=chains)
    
    def _parse_lipid_maps_id(self, lm_id: str) -> Optional[Lipid]:
        """解析LIPID MAPS ID"""
        # 简化的解析，实际需要从数据库查询
        # LMGP01010001 -> PC class
        if lm_id.startswith('LMGP01'):
            return Lipid(lipid_class=LipidClass.PC, chains=[])
        elif lm_id.startswith('LMGP02'):
            return Lipid(lipid_class=LipidClass.PE, chains=[])
        # ... 更多类别
        return Lipid(lipid_class=LipidClass.UNKNOWN, chains=[])
    
    def _parse_chains(self, chains_str: str) -> List[FattyAcidChain]:
        """解析脂肪酸链"""
        chains = []
        
        # 分割多个链
        chain_parts = re.split(r'[/;_]', chains_str)
        
        for i, part in enumerate(chain_parts):
            match = self.chain_pattern.match(part.strip())
            if match:
                c_count = int(match.group(1))
                db_count = int(match.group(2))
                position = f'sn{i+1}'
                
                chains.append(FattyAcidChain(
                    carbon_count=c_count,
                    double_bonds=db_count,
                    position=position
                ))
        
        return chains
    
    def get_lipid_class(self, name: str) -> LipidClass:
        """从名称获取脂质类别"""
        lipid = self.parse(name)
        return lipid.lipid_class if lipid else LipidClass.UNKNOWN
    
    def validate_name(self, name: str) -> bool:
        """验证脂质名称是否有效"""
        return self.parse(name) is not None


class LipidNameConverter:
    """脂质名称转换器"""
    
    def __init__(self):
        self.parser = LipidParser()
    
    def to_shorthand(self, name: str) -> Optional[str]:
        """转换为简写表示法"""
        lipid = self.parser.parse(name)
        return lipid.shorthand if lipid else None
    
    def to_systematic_name(self, name: str) -> Optional[str]:
        """转换为系统命名法"""
        lipid = self.parser.parse(name)
        if not lipid:
            return None
        
        # 构建系统名称
        class_name = lipid.lipid_class.value
        chains_desc = ', '.join(
            f"{chain.shorthand} at {chain.position}" 
            for chain in lipid.chains
        )
        
        return f"{class_name} with {chains_desc}"
    
    def to_lipid_maps_id(self, name: str) -> Optional[str]:
        """转换为LIPID MAPS ID格式"""
        lipid = self.parser.parse(name)
        if not lipid:
            return None
        
        # 简化的转换
        class_codes = {
            LipidClass.PC: 'LMGP0101',
            LipidClass.PE: 'LMGP0201',
            LipidClass.PS: 'LMGP0301',
            LipidClass.PI: 'LMGP0401',
            LipidClass.PG: 'LMGP0501',
            LipidClass.PA: 'LMGP0601',
            LipidClass.TG: 'LMGL0301',
            LipidClass.DG: 'LMGL0201',
            LipidClass.SM: 'LMSP0201',
            LipidClass.CER: 'LMSP0202',
        }
        
        base_code = class_codes.get(lipid.lipid_class, 'LMXX')
        return f"{base_code}{lipid.total_carbons:04d}"


# 便捷函数
def parse_lipid_name(name: str) -> Optional[Lipid]:
    """
    解析脂质名称
    
    Args:
        name: 脂质名称
    
    Returns:
        Lipid对象
    """
    parser = LipidParser()
    return parser.parse(name)


def get_lipid_shorthand(name: str) -> Optional[str]:
    """
    获取脂质简写
    
    Args:
        name: 脂质名称
    
    Returns:
        简写表示
    """
    converter = LipidNameConverter()
    return converter.to_shorthand(name)


def classify_lipid_by_name(name: str) -> str:
    """
    根据名称分类脂质
    
    Args:
        name: 脂质名称
    
    Returns:
        类别名称
    """
    lipid = parse_lipid_name(name)
    if lipid:
        return lipid.lipid_class.value
    return "Unknown"
