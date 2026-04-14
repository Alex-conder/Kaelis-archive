"""
基因组变异数据库查询模块 - Genomics Database Module

支持：
1. 本地数据库 (SQLite)
   - dbSNP (SNP信息)
   - ClinVar (临床变异)
   - gnomAD (人群频率)
   
2. 在线API
   - Ensembl REST API
   - NCBI Variation Services
   - MyVariant.info
   - ExAC/gnomAD API
"""

import sqlite3
import json
import time
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Union, Tuple
from dataclasses import dataclass, field
from urllib.parse import quote
import urllib.request
import urllib.error


@dataclass
class VariantRecord:
    """变异记录"""
    chrom: str
    pos: int
    ref: str
    alt: str
    rs_id: Optional[str] = None
    gene: Optional[str] = None
    consequence: Optional[str] = None
    clinvar_sig: Optional[str] = None  # Pathogenic, Benign, etc.
    clinvar_disease: Optional[str] = None
    gnomad_af: Optional[float] = None
    exac_af: Optional[float] = None
    cadd_score: Optional[float] = None
    sift_pred: Optional[str] = None
    polyphen_pred: Optional[str] = None
    gwas_traits: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            'chrom': self.chrom,
            'pos': self.pos,
            'ref': self.ref,
            'alt': self.alt,
            'rs_id': self.rs_id,
            'gene': self.gene,
            'consequence': self.consequence,
            'clinvar_sig': self.clinvar_sig,
            'clinvar_disease': self.clinvar_disease,
            'gnomad_af': self.gnomad_af,
            'exac_af': self.exac_af,
            'cadd_score': self.cadd_score,
            'sift_pred': self.sift_pred,
            'polyphen_pred': self.polyphen_pred,
            'gwas_traits': self.gwas_traits
        }
    
    @property
    def variant_id(self) -> str:
        """生成变异ID"""
        return f"{self.chrom}-{self.pos}-{self.ref}-{self.alt}"


@dataclass
class GeneRecord:
    """基因记录"""
    gene_symbol: str
    gene_id: Optional[str] = None
    chrom: Optional[str] = None
    start: int = 0
    end: int = 0
    strand: str = "+"
    description: Optional[str] = None
    biotype: Optional[str] = None
    omim_id: Optional[str] = None
    hgnc_id: Optional[str] = None
    go_terms: List[str] = field(default_factory=list)
    pathways: List[str] = field(default_factory=list)
    diseases: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            'gene_symbol': self.gene_symbol,
            'gene_id': self.gene_id,
            'chrom': self.chrom,
            'start': self.start,
            'end': self.end,
            'strand': self.strand,
            'description': self.description,
            'biotype': self.biotype,
            'omim_id': self.omim_id,
            'hgnc_id': self.hgnc_id,
            'go_terms': self.go_terms,
            'pathways': self.pathways,
            'diseases': self.diseases
        }


class LocalGenomicsDatabase:
    """本地基因组数据库"""
    
    def __init__(self, db_path: str = "data/genomics.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 变异表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS variants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chrom TEXT,
                    pos INTEGER,
                    ref TEXT,
                    alt TEXT,
                    rs_id TEXT UNIQUE,
                    gene TEXT,
                    consequence TEXT,
                    clinvar_sig TEXT,
                    clinvar_disease TEXT,
                    gnomad_af REAL,
                    exac_af REAL,
                    cadd_score REAL,
                    sift_pred TEXT,
                    polyphen_pred TEXT,
                    gwas_traits TEXT,  -- JSON
                    UNIQUE(chrom, pos, ref, alt)
                )
            ''')
            
            # 基因表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS genes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    gene_symbol TEXT UNIQUE,
                    gene_id TEXT,
                    chrom TEXT,
                    start INTEGER,
                    end INTEGER,
                    strand TEXT,
                    description TEXT,
                    biotype TEXT,
                    omim_id TEXT,
                    hgnc_id TEXT,
                    go_terms TEXT,  -- JSON
                    pathways TEXT,  -- JSON
                    diseases TEXT   -- JSON
                )
            ''')
            
            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_var_pos ON variants(chrom, pos)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_var_rs ON variants(rs_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_var_gene ON variants(gene)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_gene_symbol ON genes(gene_symbol)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_gene_pos ON genes(chrom, start, end)')
            
            conn.commit()
    
    def add_variant(self, record: VariantRecord) -> bool:
        """添加变异记录"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO variants 
                    (chrom, pos, ref, alt, rs_id, gene, consequence,
                     clinvar_sig, clinvar_disease, gnomad_af, exac_af,
                     cadd_score, sift_pred, polyphen_pred, gwas_traits)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    record.chrom, record.pos, record.ref, record.alt,
                    record.rs_id, record.gene, record.consequence,
                    record.clinvar_sig, record.clinvar_disease,
                    record.gnomad_af, record.exac_af, record.cadd_score,
                    record.sift_pred, record.polyphen_pred,
                    json.dumps(record.gwas_traits)
                ))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error adding variant: {e}")
            return False
    
    def get_variant(self, chrom: str, pos: int, ref: str, alt: str) -> Optional[VariantRecord]:
        """获取特定变异"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM variants 
                WHERE chrom = ? AND pos = ? AND ref = ? AND alt = ?
            ''', (chrom, pos, ref, alt))
            row = cursor.fetchone()
            return self._row_to_variant(row) if row else None
    
    def get_variant_by_rs(self, rs_id: str) -> Optional[VariantRecord]:
        """通过rs ID获取变异"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM variants WHERE rs_id = ?', (rs_id,))
            row = cursor.fetchone()
            return self._row_to_variant(row) if row else None
    
    def search_region(self, chrom: str, start: int, end: int) -> List[VariantRecord]:
        """搜索区域内的变异"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM variants 
                WHERE chrom = ? AND pos BETWEEN ? AND ?
            ''', (chrom, start, end))
            rows = cursor.fetchall()
            return [self._row_to_variant(row) for row in rows]
    
    def search_by_gene(self, gene: str) -> List[VariantRecord]:
        """按基因搜索变异"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM variants WHERE gene = ?', (gene,))
            rows = cursor.fetchall()
            return [self._row_to_variant(row) for row in rows]
    
    def get_gene(self, gene_symbol: str) -> Optional[GeneRecord]:
        """获取基因信息"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM genes WHERE gene_symbol = ?', (gene_symbol,))
            row = cursor.fetchone()
            return self._row_to_gene(row) if row else None
    
    def _row_to_variant(self, row) -> VariantRecord:
        """转换变异行"""
        return VariantRecord(
            chrom=row[1],
            pos=row[2],
            ref=row[3],
            alt=row[4],
            rs_id=row[5],
            gene=row[6],
            consequence=row[7],
            clinvar_sig=row[8],
            clinvar_disease=row[9],
            gnomad_af=row[10],
            exac_af=row[11],
            cadd_score=row[12],
            sift_pred=row[13],
            polyphen_pred=row[14],
            gwas_traits=json.loads(row[15]) if row[15] else []
        )
    
    def _row_to_gene(self, row) -> GeneRecord:
        """转换基因行"""
        return GeneRecord(
            gene_symbol=row[1],
            gene_id=row[2],
            chrom=row[3],
            start=row[4] or 0,
            end=row[5] or 0,
            strand=row[6] or "+",
            description=row[7],
            biotype=row[8],
            omim_id=row[9],
            hgnc_id=row[10],
            go_terms=json.loads(row[11]) if row[11] else [],
            pathways=json.loads(row[12]) if row[12] else [],
            diseases=json.loads(row[13]) if row[13] else []
        )


class EnsemblAPI:
    """Ensembl REST API客户端"""
    
    BASE_URL = "https://rest.ensembl.org"
    
    def __init__(self, cache_dir: str = "data/cache"):
        self.cache = GenomicsAPICache(cache_dir)
        self.timeout = 10
    
    def _request(self, url: str) -> Optional[Dict]:
        """发送请求"""
        cached = self.cache.get(url)
        if cached:
            return cached
        
        try:
            req = urllib.request.Request(
                url,
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = json.loads(response.read().decode('utf-8'))
                self.cache.set(url, data)
                return data
        except Exception as e:
            print(f"Ensembl API error: {e}")
            return None
    
    def get_variant(self, variant_id: str) -> Optional[Dict]:
        """获取变异信息"""
        url = f"{self.BASE_URL}/variation/human/{variant_id}?content-type=application/json"
        return self._request(url)
    
    def vep_hgvs(self, hgvs_notation: str) -> Optional[List[Dict]]:
        """
        使用VEP进行变异注释
        
        Args:
            hgvs_notation: HGVS格式 (e.g., "ENST00000366667.4:c.803C>T")
        """
        url = f"{self.BASE_URL}/vep/human/hgvs/{quote(hgvs_notation)}?content-type=application/json"
        return self._request(url)
    
    def vep_region(self, chrom: str, pos: int, allele: str) -> Optional[List[Dict]]:
        """使用VEP区域端点注释变异"""
        url = f"{self.BASE_URL}/vep/human/region/{chrom}:{pos}:{pos}/{allele}?content-type=application/json"
        return self._request(url)
    
    def get_gene(self, gene_id: str) -> Optional[Dict]:
        """获取基因信息"""
        url = f"{self.BASE_URL}/lookup/id/{gene_id}?content-type=application/json"
        return self._request(url)
    
    def get_gene_by_symbol(self, symbol: str) -> Optional[Dict]:
        """通过symbol获取基因"""
        url = f"{self.BASE_URL}/lookup/symbol/homo_sapiens/{quote(symbol)}?content-type=application/json"
        return self._request(url)
    
    def get_sequence(self, id: str, 
                    variant: Optional[str] = None) -> Optional[Dict]:
        """获取序列"""
        url = f"{self.BASE_URL}/sequence/id/{id}?content-type=application/json"
        if variant:
            url += f"&variant={variant}"
        return self._request(url)


class MyVariantAPI:
    """MyVariant.info API客户端"""
    
    BASE_URL = "https://myvariant.info/v1"
    
    def __init__(self, cache_dir: str = "data/cache"):
        self.cache = GenomicsAPICache(cache_dir)
        self.timeout = 10
    
    def _request(self, url: str) -> Optional[Dict]:
        """发送请求"""
        cached = self.cache.get(url)
        if cached:
            return cached
        
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = json.loads(response.read().decode('utf-8'))
                self.cache.set(url, data)
                return data
        except Exception as e:
            print(f"MyVariant API error: {e}")
            return None
    
    def get_variant(self, variant_id: str, 
                   fields: Optional[str] = None) -> Optional[Dict]:
        """
        获取变异详细信息
        
        Args:
            variant_id: rs ID 或 HGVS (e.g., "rs4343", "chr1:g.12345A>G")
            fields: 指定返回字段
        """
        url = f"{self.BASE_URL}/variant/{quote(variant_id)}"
        if fields:
            url += f"?fields={fields}"
        return self._request(url)
    
    def query(self, q: str, 
             fields: Optional[str] = None,
             size: int = 10) -> List[Dict]:
        """
        查询变异
        
        Args:
            q: 查询语句 (e.g., "dbnsfp.polyphen2.hdiv.score:>0.9")
            fields: 返回字段
            size: 结果数量
        """
        url = f"{self.BASE_URL}/query?q={quote(q)}&size={size}"
        if fields:
            url += f"&fields={fields}"
        
        data = self._request(url)
        if data:
            return data.get('hits', [])
        return []
    
    def annotate(self, variants: List[str]) -> List[Dict]:
        """批量注释变异"""
        # MyVariant支持POST批量查询
        results = []
        for variant in variants:
            result = self.get_variant(variant)
            if result:
                results.append(result)
        return results


class NCBIVariationAPI:
    """NCBI Variation Services API"""
    
    BASE_URL = "https://api.ncbi.nlm.nih.gov/variation/v0"
    
    def __init__(self, cache_dir: str = "data/cache"):
        self.cache = GenomicsAPICache(cache_dir)
        self.timeout = 10
    
    def _request(self, url: str) -> Optional[Dict]:
        """发送请求"""
        cached = self.cache.get(url)
        if cached:
            return cached
        
        try:
            req = urllib.request.Request(
                url,
                headers={'Accept': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = json.loads(response.read().decode('utf-8'))
                self.cache.set(url, data)
                return data
        except Exception as e:
            print(f"NCBI Variation API error: {e}")
            return None
    
    def get_spdi(self, spdi: str) -> Optional[Dict]:
        """
        通过SPDI表示获取变异
        
        Args:
            spdi: SPDI格式 (e.g., "NC_000001.11:12345:A:G")
        """
        url = f"{self.BASE_URL}/spdi/{quote(spdi)}/"
        return self._request(url)
    
    def get_variants_in_region(self, accession: str, 
                               start: int, end: int) -> List[Dict]:
        """获取区域内的变异"""
        url = f"{self.BASE_URL}/refs/{accession}/regions/{start}:{end}/"
        data = self._request(url)
        return data.get('results', []) if data else []


class GenomicsAPICache:
    """基因组API缓存"""
    
    def __init__(self, cache_dir: str):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = 86400 * 7
    
    def _get_cache_key(self, url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()
    
    def get(self, url: str) -> Optional[Dict]:
        cache_file = self.cache_dir / f"geno_{self._get_cache_key(url)}.json"
        
        if not cache_file.exists():
            return None
        
        if time.time() - cache_file.stat().st_mtime > self.ttl:
            cache_file.unlink()
            return None
        
        try:
            with open(cache_file, 'r') as f:
                return json.load(f)
        except Exception:
            return None
    
    def set(self, url: str, data: Dict):
        cache_file = self.cache_dir / f"geno_{self._get_cache_key(url)}.json"
        try:
            with open(cache_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Cache write error: {e}")


class GenomicsDatabase:
    """基因组数据库统一接口"""
    
    def __init__(self, 
                 local_db_path: str = "data/genomics.db",
                 use_api: bool = True):
        self.local_db = LocalGenomicsDatabase(local_db_path)
        self.use_api = use_api
        
        if use_api:
            self.ensembl = EnsemblAPI()
            self.myvariant = MyVariantAPI()
            self.ncbi_var = NCBIVariationAPI()
    
    def annotate_variant(self, chrom: str, pos: int, ref: str, 
                        alt: str) -> Dict:
        """
        注释单个变异
        
        Returns:
            注释结果字典
        """
        result = {
            'variant_id': f"{chrom}-{pos}-{ref}-{alt}",
            'chrom': chrom,
            'pos': pos,
            'ref': ref,
            'alt': alt,
            'annotations': {}
        }
        
        # 1. 查本地数据库
        local = self.local_db.get_variant(chrom, pos, ref, alt)
        if local:
            result['annotations']['local'] = local.to_dict()
        
        # 2. 查MyVariant
        if self.use_api:
            hgvs = f"chr{chrom}:g.{pos}{ref}>{alt}"
            mv_data = self.myvariant.get_variant(hgvs)
            if mv_data:
                result['annotations']['myvariant'] = self._parse_myvariant(mv_data)
            
            # 3. 查Ensembl VEP
            vep_data = self.ensembl.vep_region(chrom, pos, alt)
            if vep_data:
                result['annotations']['vep'] = vep_data
        
        return result
    
    def _parse_myvariant(self, data: Dict) -> Dict:
        """解析MyVariant数据"""
        result = {}
        
        # dbSNP
        if 'dbsnp' in data:
            result['rsid'] = data['dbsnp'].get('rsid')
        
        # ClinVar
        if 'clinvar' in data:
            result['clinvar'] = {
                'significance': data['clinvar'].get('rcv', [{}])[0].get('clinical_significance'),
                'disease': data['clinvar'].get('rcv', [{}])[0].get('disease_names', [])
            }
        
        # gnomAD
        if 'gnomad_genome' in data:
            result['gnomad_af'] = data['gnomad_genome'].get('af', {}).get('af')
        elif 'gnomad_exome' in data:
            result['gnomad_af'] = data['gnomad_exome'].get('af', {}).get('af')
        
        # CADD
        if 'cadd' in data:
            result['cadd_score'] = data['cadd'].get('phred')
        
        # SIFT/PolyPhen
        if 'dbnsfp' in data:
            result['sift'] = data['dbnsfp'].get('sift', {}).get('pred')
            result['polyphen'] = data['dbnsfp'].get('polyphen2', {}).get('hdiv', {}).get('pred')
        
        # 基因
        if 'snpeff' in data:
            ann = data['snpeff'].get('ann', [])
            if ann:
                result['gene'] = ann[0].get('gene_name')
                result['consequence'] = ann[0].get('effect')
        
        return result
    
    def get_gene_info(self, gene_symbol: str) -> Optional[Dict]:
        """获取基因信息"""
        # 先查本地
        local = self.local_db.get_gene(gene_symbol)
        if local:
            return local.to_dict()
        
        # 查Ensembl
        if self.use_api:
            return self.ensembl.get_gene_by_symbol(gene_symbol)
        
        return None
    
    def search_clinvar(self, gene: str, 
                      significance: Optional[str] = None) -> List[Dict]:
        """
        搜索ClinVar变异
        
        Args:
            gene: 基因名
            significance: 临床意义筛选 (Pathogenic, Likely pathogenic, etc.)
        """
        # 使用MyVariant查询
        if self.use_api:
            query = f"clinvar.gene.symbol:{gene}"
            if significance:
                query += f" AND clinvar.rcv.clinical_significance:{significance}"
            
            return self.myvariant.query(query, size=100)
        
        return []
    
    def save_to_local(self, record: VariantRecord):
        """保存变异到本地"""
        return self.local_db.add_variant(record)


# 便捷函数
def annotate_variant(chrom: str, pos: int, ref: str, 
                    alt: str, use_api: bool = True) -> Dict:
    """注释变异"""
    db = GenomicsDatabase(use_api=use_api)
    return db.annotate_variant(chrom, pos, ref, alt)


def get_variant_frequency(variant_id: str) -> Optional[float]:
    """获取变异人群频率"""
    db = GenomicsDatabase()
    
    # 解析variant_id
    data = db.myvariant.get_variant(variant_id, fields='gnomad_genome.af.af,gnomad_exome.af.af')
    if data:
        gnomad = data.get('gnomad_genome', {}).get('af', {}).get('af')
        if gnomad:
            return gnomad
        return data.get('gnomad_exome', {}).get('af', {}).get('af')
    
    return None


def check_pathogenicity(variant_id: str) -> Optional[str]:
    """检查变异致病性"""
    db = GenomicsDatabase()
    data = db.myvariant.get_variant(variant_id, fields='clinvar.rcv.clinical_significance')
    
    if data and 'clinvar' in data:
        rcv = data['clinvar'].get('rcv', [])
        if rcv:
            return rcv[0].get('clinical_significance')
    
    return None
