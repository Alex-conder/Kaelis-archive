"""
蛋白质数据库查询模块 - Protein Database Module

支持：
1. 本地数据库 (SQLite)
   - UniProt (蛋白质序列和功能)
   - NCBI Protein
   - PDB (结构)
   
2. 在线API
   - UniProt REST API
   - NCBI E-utilities
   - InterPro
   - STRING (PPI)
"""

import sqlite3
import json
import time
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Union
from dataclasses import dataclass, field
from urllib.parse import quote
import urllib.request
import urllib.error


@dataclass
class ProteinRecord:
    """蛋白质记录"""
    uniprot_id: str
    protein_name: str
    gene_name: Optional[str] = None
    sequence: Optional[str] = None
    length: int = 0
    molecular_weight: float = 0.0
    organism: str = ""
    function: Optional[str] = None
    go_terms: List[str] = field(default_factory=list)
    pathways: List[str] = field(default_factory=list)
    domains: List[Dict] = field(default_factory=list)
    pdb_ids: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            'uniprot_id': self.uniprot_id,
            'protein_name': self.protein_name,
            'gene_name': self.gene_name,
            'sequence': self.sequence,
            'length': self.length,
            'molecular_weight': self.molecular_weight,
            'organism': self.organism,
            'function': self.function,
            'go_terms': self.go_terms,
            'pathways': self.pathways,
            'domains': self.domains,
            'pdb_ids': self.pdb_ids
        }


@dataclass
class PeptideRecord:
    """肽段记录"""
    sequence: str
    modifications: List[str] = field(default_factory=list)
    theoretical_mz: float = 0.0
    charge: int = 2
    proteins: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            'sequence': self.sequence,
            'modifications': self.modifications,
            'theoretical_mz': self.theoretical_mz,
            'charge': self.charge,
            'proteins': self.proteins
        }


class LocalProteinDatabase:
    """本地蛋白质数据库"""
    
    def __init__(self, db_path: str = "data/proteins.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 蛋白质表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS proteins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uniprot_id TEXT UNIQUE,
                    protein_name TEXT,
                    gene_name TEXT,
                    sequence TEXT,
                    length INTEGER,
                    molecular_weight REAL,
                    organism TEXT,
                    function TEXT,
                    go_terms TEXT,  -- JSON
                    pathways TEXT,  -- JSON
                    domains TEXT,   -- JSON
                    pdb_ids TEXT,   -- JSON
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 肽段表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS peptides (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sequence TEXT UNIQUE,
                    modifications TEXT,  -- JSON
                    theoretical_mz REAL,
                    charge INTEGER,
                    proteins TEXT,  -- JSON list of UniProt IDs
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_uniprot ON proteins(uniprot_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_gene ON proteins(gene_name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_peptide_seq ON peptides(sequence)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_peptide_mz ON peptides(theoretical_mz)')
            
            conn.commit()
    
    def add_protein(self, record: ProteinRecord) -> bool:
        """添加蛋白质记录"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO proteins 
                    (uniprot_id, protein_name, gene_name, sequence, length,
                     molecular_weight, organism, function, go_terms, pathways,
                     domains, pdb_ids)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    record.uniprot_id,
                    record.protein_name,
                    record.gene_name,
                    record.sequence,
                    record.length,
                    record.molecular_weight,
                    record.organism,
                    record.function,
                    json.dumps(record.go_terms),
                    json.dumps(record.pathways),
                    json.dumps(record.domains),
                    json.dumps(record.pdb_ids)
                ))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error adding protein: {e}")
            return False
    
    def get_protein(self, uniprot_id: str) -> Optional[ProteinRecord]:
        """通过UniProt ID获取蛋白质"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM proteins WHERE uniprot_id = ?', (uniprot_id,))
            row = cursor.fetchone()
            return self._row_to_protein(row) if row else None
    
    def search_by_gene(self, gene_name: str) -> List[ProteinRecord]:
        """按基因名搜索"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM proteins WHERE gene_name LIKE ?
            ''', (f'%{gene_name}%',))
            rows = cursor.fetchall()
            return [self._row_to_protein(row) for row in rows]
    
    def search_by_name(self, name: str) -> List[ProteinRecord]:
        """按蛋白质名称搜索"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM proteins 
                WHERE protein_name LIKE ? OR uniprot_id LIKE ?
            ''', (f'%{name}%', f'%{name}%'))
            rows = cursor.fetchall()
            return [self._row_to_protein(row) for row in rows]
    
    def search_by_sequence(self, sequence: str) -> Optional[PeptideRecord]:
        """搜索肽段序列"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM peptides WHERE sequence = ?', (sequence,))
            row = cursor.fetchone()
            return self._row_to_peptide(row) if row else None
    
    def _row_to_protein(self, row) -> ProteinRecord:
        """转换行为记录"""
        return ProteinRecord(
            uniprot_id=row[1],
            protein_name=row[2],
            gene_name=row[3],
            sequence=row[4],
            length=row[5] or 0,
            molecular_weight=row[6] or 0.0,
            organism=row[7] or "",
            function=row[8],
            go_terms=json.loads(row[9]) if row[9] else [],
            pathways=json.loads(row[10]) if row[10] else [],
            domains=json.loads(row[11]) if row[11] else [],
            pdb_ids=json.loads(row[12]) if row[12] else []
        )
    
    def _row_to_peptide(self, row) -> PeptideRecord:
        """转换肽段行"""
        return PeptideRecord(
            sequence=row[1],
            modifications=json.loads(row[2]) if row[2] else [],
            theoretical_mz=row[3] or 0.0,
            charge=row[4] or 2,
            proteins=json.loads(row[5]) if row[5] else []
        )


class UniProtAPI:
    """UniProt REST API客户端"""
    
    BASE_URL = "https://rest.uniprot.org/uniprotkb"
    
    def __init__(self, cache_dir: str = "data/cache"):
        self.cache = ProteinAPICache(cache_dir)
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
            print(f"UniProt API error: {e}")
            return None
    
    def search(self, query: str, limit: int = 10) -> List[Dict]:
        """搜索蛋白质"""
        url = f"{self.BASE_URL}/search?query={quote(query)}&format=json&size={limit}"
        data = self._request(url)
        
        if not data:
            return []
        
        results = []
        for entry in data.get('results', []):
            protein_info = self._parse_entry(entry)
            if protein_info:
                results.append(protein_info)
        
        return results
    
    def get_protein(self, uniprot_id: str) -> Optional[Dict]:
        """获取蛋白质详情"""
        url = f"{self.BASE_URL}/{uniprot_id}.json"
        data = self._request(url)
        
        if not data:
            return None
        
        return self._parse_entry(data)
    
    def _parse_entry(self, entry: Dict) -> Optional[Dict]:
        """解析UniProt条目"""
        try:
            protein_info = {
                'uniprot_id': entry.get('primaryAccession', ''),
                'protein_name': '',
                'gene_name': '',
                'organism': '',
                'length': 0,
                'sequence': '',
                'function': '',
                'go_terms': [],
                'pathways': [],
                'domains': [],
                'pdb_ids': []
            }
            
            # 蛋白质名称
            if 'proteinDescription' in entry:
                rec_name = entry['proteinDescription'].get('recommendedName', {})
                protein_info['protein_name'] = rec_name.get('fullName', {}).get('value', '')
            
            # 基因名
            if 'genes' in entry and entry['genes']:
                gene = entry['genes'][0]
                protein_info['gene_name'] = gene.get('geneName', {}).get('value', '')
            
            # 物种
            if 'organism' in entry:
                protein_info['organism'] = entry['organism'].get('scientificName', '')
            
            # 序列
            if 'sequence' in entry:
                protein_info['sequence'] = entry['sequence'].get('sequence', '')
                protein_info['length'] = entry['sequence'].get('length', 0)
            
            # 功能注释
            if 'comments' in entry:
                for comment in entry['comments']:
                    if comment.get('commentType') == 'FUNCTION':
                        texts = comment.get('texts', [])
                        if texts:
                            protein_info['function'] = texts[0].get('value', '')
                    elif comment.get('commentType') == 'PATHWAY':
                        texts = comment.get('texts', [])
                        if texts:
                            protein_info['pathways'].append(texts[0].get('value', ''))
            
            # GO注释
            if 'uniProtKBCrossReferences' in entry:
                for xref in entry['uniProtKBCrossReferences']:
                    if xref.get('database') == 'GO':
                        go_id = xref.get('id', '')
                        go_term = xref.get('properties', [{}])[0].get('value', '')
                        protein_info['go_terms'].append(f"{go_id}:{go_term}")
                    elif xref.get('database') == 'PDB':
                        protein_info['pdb_ids'].append(xref.get('id', ''))
            
            # 结构域
            if 'features' in entry:
                for feature in entry['features']:
                    if feature.get('type') in ['DOMAIN', 'REPEAT']:
                        protein_info['domains'].append({
                            'name': feature.get('description', ''),
                            'start': feature.get('location', {}).get('start', {}).get('value', 0),
                            'end': feature.get('location', {}).get('end', {}).get('value', 0)
                        })
            
            return protein_info
            
        except Exception as e:
            print(f"Error parsing UniProt entry: {e}")
            return None
    
    def get_sequence(self, uniprot_id: str) -> Optional[str]:
        """获取蛋白质序列"""
        url = f"{self.BASE_URL}/{uniprot_id}.fasta"
        
        cached = self.cache.get(url)
        if cached:
            return cached.get('sequence')
        
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                lines = response.read().decode('utf-8').strip().split('\n')
                sequence = ''.join(lines[1:])  # 跳过标题行
                self.cache.set(url, {'sequence': sequence})
                return sequence
        except Exception as e:
            print(f"Error fetching sequence: {e}")
            return None


class NCBIProteinAPI:
    """NCBI E-utilities API"""
    
    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    
    def __init__(self, cache_dir: str = "data/cache"):
        self.cache = ProteinAPICache(cache_dir)
        self.timeout = 10
        self.api_key = None
        self.delay = 0.34  # NCBI要求每秒不超过3次请求
    
    def _request(self, url: str) -> Optional[str]:
        """发送请求"""
        cached = self.cache.get(url)
        if cached:
            return cached.get('text')
        
        try:
            time.sleep(self.delay)  # 遵守速率限制
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                text = response.read().decode('utf-8')
                self.cache.set(url, {'text': text})
                return text
        except Exception as e:
            print(f"NCBI API error: {e}")
            return None
    
    def search(self, query: str, db: str = "protein", limit: int = 10) -> List[str]:
        """搜索NCBI数据库"""
        url = f"{self.BASE_URL}/esearch.fcgi?db={db}&term={quote(query)}&retmax={limit}&retmode=json"
        
        if self.api_key:
            url += f"&api_key={self.api_key}"
        
        text = self._request(url)
        if not text:
            return []
        
        try:
            data = json.loads(text)
            return data.get('esearchresult', {}).get('idlist', [])
        except Exception:
            return []
    
    def fetch_summary(self, ids: List[str], db: str = "protein") -> List[Dict]:
        """获取条目摘要"""
        if not ids:
            return []
        
        id_str = ','.join(ids)
        url = f"{self.BASE_URL}/esummary.fcgi?db={db}&id={id_str}&retmode=json"
        
        if self.api_key:
            url += f"&api_key={self.api_key}"
        
        text = self._request(url)
        if not text:
            return []
        
        try:
            data = json.loads(text)
            results = []
            for uid, summary in data.get('result', {}).items():
                if uid != 'uids':
                    results.append({
                        'ncbi_id': uid,
                        'title': summary.get('title', ''),
                        'organism': summary.get('organism', ''),
                        'accession': summary.get('caption', ''),
                        'source': 'NCBI'
                    })
            return results
        except Exception as e:
            print(f"Error parsing NCBI response: {e}")
            return []


class STRINGAPI:
    """STRING PPI数据库API"""
    
    BASE_URL = "https://string-db.org/api/json"
    
    def __init__(self, cache_dir: str = "data/cache"):
        self.cache = ProteinAPICache(cache_dir)
        self.timeout = 10
    
    def get_interactions(self, proteins: List[str], 
                        species: int = 9606,  # Human
                        required_score: int = 400) -> List[Dict]:
        """
        获取蛋白质相互作用
        
        Args:
            proteins: UniProt ID列表
            species: 物种NCBI taxon ID
            required_score: 最小置信度分数 (0-1000)
        """
        protein_str = '%0d'.join(proteins)
        url = f"{self.BASE_URL}/network?identifiers={protein_str}&species={species}&required_score={required_score}"
        
        cached = self.cache.get(url)
        if cached:
            return cached.get('interactions', [])
        
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = json.loads(response.read().decode('utf-8'))
                self.cache.set(url, {'interactions': data})
                return data
        except Exception as e:
            print(f"STRING API error: {e}")
            return []


class ProteinAPICache:
    """蛋白质API缓存"""
    
    def __init__(self, cache_dir: str):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = 86400 * 7
    
    def _get_cache_key(self, url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()
    
    def get(self, url: str) -> Optional[Dict]:
        cache_file = self.cache_dir / f"prot_{self._get_cache_key(url)}.json"
        
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
        cache_file = self.cache_dir / f"prot_{self._get_cache_key(url)}.json"
        try:
            with open(cache_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Cache write error: {e}")


class ProteinDatabase:
    """蛋白质数据库统一接口"""
    
    def __init__(self, 
                 local_db_path: str = "data/proteins.db",
                 use_api: bool = True):
        self.local_db = LocalProteinDatabase(local_db_path)
        self.use_api = use_api
        
        if use_api:
            self.uniprot = UniProtAPI()
            self.ncbi = NCBIProteinAPI()
            self.string = STRINGAPI()
    
    def search_protein(self, query: str) -> List[Dict]:
        """搜索蛋白质"""
        results = []
        seen_ids = set()
        
        # 本地搜索
        local_results = self.local_db.search_by_name(query)
        for r in local_results:
            results.append(r.to_dict())
            seen_ids.add(r.uniprot_id)
        
        # API搜索
        if self.use_api:
            uniprot_results = self.uniprot.search(query)
            for r in uniprot_results:
                if r.get('uniprot_id') not in seen_ids:
                    results.append(r)
                    seen_ids.add(r.get('uniprot_id'))
            
            # NCBI搜索
            ncbi_ids = self.ncbi.search(query)
            ncbi_results = self.ncbi.fetch_summary(ncbi_ids)
            results.extend(ncbi_results)
        
        return results
    
    def get_protein_details(self, uniprot_id: str) -> Optional[Dict]:
        """获取蛋白质详细信息"""
        # 先查本地
        local = self.local_db.get_protein(uniprot_id)
        if local:
            return local.to_dict()
        
        # 查API
        if self.use_api:
            return self.uniprot.get_protein(uniprot_id)
        
        return None
    
    def get_interactions(self, uniprot_ids: List[str]) -> List[Dict]:
        """获取蛋白质相互作用"""
        if self.use_api:
            return self.string.get_interactions(uniprot_ids)
        return []
    
    def save_to_local(self, record: ProteinRecord):
        """保存到本地数据库"""
        return self.local_db.add_protein(record)


# 便捷函数
def search_protein(query: str, use_api: bool = True) -> List[Dict]:
    """搜索蛋白质"""
    db = ProteinDatabase(use_api=use_api)
    return db.search_protein(query)


def get_protein_function(uniprot_id: str) -> Optional[str]:
    """获取蛋白质功能"""
    db = ProteinDatabase()
    protein = db.get_protein_details(uniprot_id)
    return protein.get('function') if protein else None


def get_protein_interactions(uniprot_ids: List[str]) -> List[Dict]:
    """获取蛋白质相互作用"""
    db = ProteinDatabase()
    return db.get_interactions(uniprot_ids)
