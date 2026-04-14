"""
VCF 文件解析器 - VCF Parser

支持解析 VCF 格式的基因组变异数据。
"""

import gzip
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Union
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Variant:
    """基因组变异"""
    chrom: str
    pos: int
    id: str
    ref: str
    alt: str
    qual: Optional[float]
    filter_status: str
    info: Dict[str, Any]
    format_data: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_snp(self) -> bool:
        """是否为SNP"""
        return len(self.ref) == 1 and len(self.alt) == 1
    
    @property
    def is_indel(self) -> bool:
        """是否为INDEL"""
        return len(self.ref) != len(self.alt)
    
    @property
    def variant_type(self) -> str:
        """变异类型"""
        if self.is_snp:
            return 'SNP'
        elif self.is_indel:
            return 'INDEL' if len(self.ref) < len(self.alt) else 'DEL'
        return 'OTHER'


class VCFParser:
    """VCF 文件解析器"""
    
    def __init__(self, filepath: Union[str, Path]):
        self.filepath = Path(filepath)
        self.header_lines = []
        self.sample_names = []
        
        logger.info(f"VCF Parser initialized: {self.filepath}")
    
    def parse(self) -> Iterator[Variant]:
        """解析 VCF 文件"""
        open_func = gzip.open if str(self.filepath).endswith('.gz') else open
        
        with open_func(self.filepath, 'rt') as f:
            for line in f:
                line = line.strip()
                
                if not line:
                    continue
                
                # 解析头部
                if line.startswith('##'):
                    self.header_lines.append(line)
                    continue
                
                # 样本名行
                if line.startswith('#CHROM'):
                    cols = line.split('\t')
                    if len(cols) > 9:
                        self.sample_names = cols[9:]
                    continue
                
                # 解析变异
                yield self._parse_variant_line(line)
    
    def _parse_variant_line(self, line: str) -> Variant:
        """解析单行变异数据"""
        cols = line.split('\t')
        
        chrom = cols[0]
        pos = int(cols[1])
        var_id = cols[2] if cols[2] != '.' else None
        ref = cols[3]
        alt = cols[4]
        qual = float(cols[5]) if cols[5] != '.' else None
        filter_status = cols[6]
        
        # 解析 INFO
        info = {}
        for item in cols[7].split(';'):
            if '=' in item:
                key, value = item.split('=', 1)
                info[key] = value
            else:
                info[item] = True
        
        # 解析 FORMAT（如果有样本）
        format_data = {}
        if len(cols) > 8:
            format_keys = cols[8].split(':')
            
            for i, sample in enumerate(self.sample_names):
                if 9 + i < len(cols):
                    values = cols[9 + i].split(':')
                    sample_data = {}
                    for j, key in enumerate(format_keys):
                        if j < len(values):
                            sample_data[key] = values[j]
                    format_data[sample] = sample_data
        
        return Variant(
            chrom=chrom,
            pos=pos,
            id=var_id,
            ref=ref,
            alt=alt,
            qual=qual,
            filter_status=filter_status,
            info=info,
            format_data=format_data
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取变异统计信息"""
        stats = {
            'total_variants': 0,
            'snps': 0,
            'indels': 0,
            'pass_filter': 0,
            'chromosomes': {}
        }
        
        for variant in self.parse():
            stats['total_variants'] += 1
            
            if variant.is_snp:
                stats['snps'] += 1
            elif variant.is_indel:
                stats['indels'] += 1
            
            if variant.filter_status == 'PASS':
                stats['pass_filter'] += 1
            
            # 染色体分布
            chrom = variant.chrom
            stats['chromosomes'][chrom] = stats['chromosomes'].get(chrom, 0) + 1
        
        return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("VCF Parser loaded successfully!")
