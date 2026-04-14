"""
多组学通路数据库模块 - Multi-Omics Pathway Database Module

支持：
1. 本地数据库 (SQLite)
   - KEGG PATHWAY
   - Reactome
   - GO (Gene Ontology)
   - MSigDB
   
2. 在线API
   - KEGG API
   - Reactome Content Service
   - GO API
   - Ensembl Pathways
"""

import sqlite3
import json
import time
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field
from urllib.parse import quote
import urllib.request
import urllib.error


@dataclass
class PathwayRecord:
    """通路记录"""
    pathway_id: str
    name: str
    source_db: str  # KEGG, Reactome, etc.
    description: Optional[str] = None
    category: Optional[str] = None
    organism: str = "hsa"
    
    # 通路成员
    genes: List[str] = field(default_factory=list)
    proteins: List[str] = field(default_factory=list)
    metabolites: List[str] = field(default_factory=list)
    
    # 拓扑信息
    parent_pathways: List[str] = field(default_factory=list)
    child_pathways: List[str] = field(default_factory=list)
    
    # 统计
    gene_count: int = 0
    disease_count: int = 0
    
    def to_dict(self) -> Dict:
        return {
            'pathway_id': self.pathway_id,
            'name': self.name,
            'source_db': self.source_db,
            'description': self.description,
            'category': self.category,
            'organism': self.organism,
            'genes': self.genes,
            'proteins': self.proteins,
            'metabolites': self.metabolites,
            'parent_pathways': self.parent_pathways,
            'child_pathways': self.child_pathways,
            'gene_count': len(self.genes),
            'disease_count': self.disease_count
        }


@dataclass
class GOTerm:
    """GO条目"""
    go_id: str
    name: str
    namespace: str  # BP, MF, CC
    definition: Optional[str] = None
    synonyms: List[str] = field(default_factory=list)
    parents: List[str] = field(default_factory=list)
    genes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            'go_id': self.go_id,
            'name': self.name,
            'namespace': self.namespace,
            'definition': self.definition,
            'synonyms': self.synonyms,
            'parents': self.parents,
            'genes': self.genes
        }


class LocalPathwayDatabase:
    """本地通路数据库"""
    
    def __init__(self, db_path: str = "data/pathways.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 通路表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pathways (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pathway_id TEXT,
                    name TEXT,
                    source_db TEXT,
                    description TEXT,
                    category TEXT,
                    organism TEXT,
                    genes TEXT,  -- JSON list
                    proteins TEXT,  -- JSON list
                    metabolites TEXT,  -- JSON list
                    parent_pathways TEXT,  -- JSON list
                    child_pathways TEXT,  -- JSON list
                    disease_count INTEGER DEFAULT 0,
                    UNIQUE(pathway_id, source_db)
                )
            ''')
            
            # GO表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS go_terms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    go_id TEXT UNIQUE,
                    name TEXT,
                    namespace TEXT,
                    definition TEXT,
                    synonyms TEXT,  -- JSON
                    parents TEXT,  -- JSON
                    genes TEXT  -- JSON
                )
            ''')
            
            # 基因-通路关联表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS gene_pathway (
                    gene_symbol TEXT,
                    pathway_id TEXT,
                    source_db TEXT,
                    PRIMARY KEY (gene_symbol, pathway_id, source_db)
                )
            ''')
            
            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_pw_id ON pathways(pathway_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_pw_source ON pathways(source_db)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_go_id ON go_terms(go_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_gene_pw ON gene_pathway(gene_symbol)')
            
            conn.commit()
    
    def add_pathway(self, record: PathwayRecord) -> bool:
        """添加通路"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO pathways 
                    (pathway_id, name, source_db, description, category, organism,
                     genes, proteins, metabolites, parent_pathways, child_pathways,
                     disease_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    record.pathway_id, record.name, record.source_db,
                    record.description, record.category, record.organism,
                    json.dumps(record.genes), json.dumps(record.proteins),
                    json.dumps(record.metabolites),
                    json.dumps(record.parent_pathways),
                    json.dumps(record.child_pathways),
                    record.disease_count
                ))
                
                # 更新基因-通路关联
                for gene in record.genes:
                    cursor.execute('''
                        INSERT OR IGNORE INTO gene_pathway 
                        (gene_symbol, pathway_id, source_db)
                        VALUES (?, ?, ?)
                    ''', (gene, record.pathway_id, record.source_db))
                
                conn.commit()
                return True
        except Exception as e:
            print(f"Error adding pathway: {e}")
            return False
    
    def add_go_term(self, term: GOTerm) -> bool:
        """添加GO条目"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO go_terms 
                    (go_id, name, namespace, definition, synonyms, parents, genes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    term.go_id, term.name, term.namespace,
                    term.definition, json.dumps(term.synonyms),
                    json.dumps(term.parents), json.dumps(term.genes)
                ))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error adding GO term: {e}")
            return False
    
    def get_pathway(self, pathway_id: str, 
                   source_db: str = "KEGG") -> Optional[PathwayRecord]:
        """获取通路"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM pathways 
                WHERE pathway_id = ? AND source_db = ?
            ''', (pathway_id, source_db))
            row = cursor.fetchone()
            return self._row_to_pathway(row) if row else None
    
    def search_pathways(self, query: str, 
                       source_db: Optional[str] = None) -> List[PathwayRecord]:
        """搜索通路"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if source_db:
                cursor.execute('''
                    SELECT * FROM pathways 
                    WHERE (name LIKE ? OR description LIKE ?) AND source_db = ?
                ''', (f'%{query}%', f'%{query}%', source_db))
            else:
                cursor.execute('''
                    SELECT * FROM pathways 
                    WHERE name LIKE ? OR description LIKE ?
                ''', (f'%{query}%', f'%{query}%'))
            
            rows = cursor.fetchall()
            return [self._row_to_pathway(row) for row in rows]
    
    def get_pathways_by_gene(self, gene_symbol: str) -> List[PathwayRecord]:
        """获取基因相关的通路"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT p.* FROM pathways p
                JOIN gene_pathway gp ON p.pathway_id = gp.pathway_id
                WHERE gp.gene_symbol = ?
            ''', (gene_symbol,))
            rows = cursor.fetchall()
            return [self._row_to_pathway(row) for row in rows]
    
    def get_go_term(self, go_id: str) -> Optional[GOTerm]:
        """获取GO条目"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM go_terms WHERE go_id = ?', (go_id,))
            row = cursor.fetchone()
            return self._row_to_go(row) if row else None
    
    def _row_to_pathway(self, row) -> PathwayRecord:
        """转换通路行"""
        return PathwayRecord(
            pathway_id=row[1],
            name=row[2],
            source_db=row[3],
            description=row[4],
            category=row[5],
            organism=row[6] or "hsa",
            genes=json.loads(row[7]) if row[7] else [],
            proteins=json.loads(row[8]) if row[8] else [],
            metabolites=json.loads(row[9]) if row[9] else [],
            parent_pathways=json.loads(row[10]) if row[10] else [],
            child_pathways=json.loads(row[11]) if row[11] else [],
            disease_count=row[12] or 0
        )
    
    def _row_to_go(self, row) -> GOTerm:
        """转换GO行"""
        return GOTerm(
            go_id=row[1],
            name=row[2],
            namespace=row[3],
            definition=row[4],
            synonyms=json.loads(row[5]) if row[5] else [],
            parents=json.loads(row[6]) if row[6] else [],
            genes=json.loads(row[7]) if row[7] else []
        )


class KEGGPathwayAPI:
    """KEGG通路API客户端"""
    
    BASE_URL = "https://rest.kegg.jp"
    
    def __init__(self, cache_dir: str = "data/cache"):
        self.cache = PathwayAPICache(cache_dir)
        self.timeout = 10
    
    def _request(self, url: str) -> Optional[str]:
        """发送请求"""
        cached = self.cache.get(url)
        if cached:
            return cached.get('text')
        
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                text = response.read().decode('utf-8')
                self.cache.set(url, {'text': text})
                return text
        except Exception as e:
            print(f"KEGG API error: {e}")
            return None
    
    def list_pathways(self, organism: str = "hsa") -> List[Dict]:
        """列出所有通路"""
        url = f"{self.BASE_URL}/list/pathway/{organism}"
        text = self._request(url)
        
        if not text:
            return []
        
        results = []
        for line in text.strip().split('\n'):
            if '\t' in line:
                pid, name = line.split('\t', 1)
                results.append({
                    'pathway_id': pid,
                    'name': name,
                    'source': 'KEGG'
                })
        
        return results
    
    def get_pathway(self, pathway_id: str) -> Optional[PathwayRecord]:
        """获取通路详情"""
        url = f"{self.BASE_URL}/get/{pathway_id}"
        text = self._request(url)
        
        if not text:
            return None
        
        record = PathwayRecord(
            pathway_id=pathway_id,
            name='',
            source_db='KEGG',
            description='',
            genes=[],
            metabolites=[],
            parent_pathways=[],
            child_pathways=[]
        )
        
        section = None
        for line in text.split('\n'):
            if line.startswith('NAME'):
                record.name = line.split(maxsplit=1)[1] if len(line.split()) > 1 else ''
            elif line.startswith('DESCRIPTION'):
                section = 'description'
            elif line.startswith('CLASS'):
                record.category = line.split(maxsplit=1)[1] if len(line.split()) > 1 else ''
            elif line.startswith('GENE'):
                section = 'gene'
                parts = line.split()
                if len(parts) >= 2:
                    gene = parts[1]
                    record.genes.append(gene)
            elif line.startswith('COMPOUND'):
                section = 'compound'
                compound = line.split()[1] if len(line.split()) > 1 else ''
                if compound:
                    record.metabolites.append(compound)
            elif line.startswith('PATHWAY_MAP'):
                section = 'pathway'
            elif line.startswith('DISEASE'):
                section = 'disease'
                record.disease_count += 1
            elif line.startswith(' ') and section == 'description':
                record.description += line.strip() + ' '
            elif line.startswith(' ') and section == 'gene':
                gene = line.split()[0] if line.split() else ''
                if gene and gene not in record.genes:
                    record.genes.append(gene)
        
        return record
    
    def get_genes_by_pathway(self, pathway_id: str) -> List[str]:
        """获取通路中的基因"""
        url = f"{self.BASE_URL}/link/genes/{pathway_id}"
        text = self._request(url)
        
        if not text:
            return []
        
        genes = []
        for line in text.strip().split('\n'):
            if '\t' in line:
                parts = line.split('\t')
                if len(parts) >= 2:
                    gene = parts[1].split(':')[1] if ':' in parts[1] else parts[1]
                    genes.append(gene)
        
        return genes
    
    def get_pathways_by_gene(self, gene: str, organism: str = "hsa") -> List[str]:
        """获取基因相关的通路"""
        url = f"{self.BASE_URL}/link/pathway/{organism}:{gene}"
        text = self._request(url)
        
        if not text:
            return []
        
        pathways = []
        for line in text.strip().split('\n'):
            if '\t' in line:
                parts = line.split('\t')
                if len(parts) >= 2:
                    pathways.append(parts[1])
        
        return pathways


class ReactomeAPI:
    """Reactome Content Service API"""
    
    BASE_URL = "https://reactome.org/ContentService"
    
    def __init__(self, cache_dir: str = "data/cache"):
        self.cache = PathwayAPICache(cache_dir)
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
            print(f"Reactome API error: {e}")
            return None
    
    def search(self, query: str, species: str = "Homo sapiens") -> List[Dict]:
        """搜索Reactome"""
        url = f"{self.BASE_URL}/search/query?query={quote(query)}&species={quote(species)}&rows=20"
        data = self._request(url)
        
        if not data:
            return []
        
        return data.get('results', [])
    
    def get_pathway(self, pathway_id: str) -> Optional[Dict]:
        """获取通路详情"""
        url = f"{self.BASE_URL}/data/query/{pathway_id}"
        return self._request(url)
    
    def get_participants(self, pathway_id: str) -> List[Dict]:
        """获取通路参与者"""
        url = f"{self.BASE_URL}/data/participants/{pathway_id}"
        data = self._request(url)
        return data if data else []
    
    def get_pathways_by_gene(self, gene_symbol: str) -> List[Dict]:
        """获取基因相关的通路"""
        # Reactome没有直接的gene-pathway API，需要通过搜索
        results = self.search(gene_symbol)
        pathways = [r for r in results if r.get('type') == 'Pathway']
        return pathways


class GOAPI:
    """Gene Ontology API (QuickGO)"""
    
    BASE_URL = "https://www.ebi.ac.uk/QuickGO/services"
    
    def __init__(self, cache_dir: str = "data/cache"):
        self.cache = PathwayAPICache(cache_dir)
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
            print(f"GO API error: {e}")
            return None
    
    def get_term(self, go_id: str) -> Optional[GOTerm]:
        """获取GO条目"""
        url = f"{self.BASE_URL}/ontology/go/terms/{go_id}"
        data = self._request(url)
        
        if not data or 'results' not in data:
            return None
        
        result = data['results'][0]
        
        return GOTerm(
            go_id=result.get('id', ''),
            name=result.get('name', ''),
            namespace=result.get('aspect', ''),
            definition=result.get('definition', {}).get('text', ''),
            synonyms=[s.get('name', '') for s in result.get('synonyms', [])],
            parents=[p.get('id', '') for p in result.get('parents', [])]
        )
    
    def get_annotations(self, go_id: str, 
                       taxon_id: int = 9606) -> List[Dict]:
        """获取GO注释"""
        url = f"{self.BASE_URL}/annotation/search?goId={go_id}&taxonId={taxon_id}&limit=100"
        data = self._request(url)
        
        if not data:
            return []
        
        return data.get('results', [])
    
    def search(self, query: str) -> List[Dict]:
        """搜索GO条目"""
        url = f"{self.BASE_URL}/ontology/go/search?query={quote(query)}&limit=20"
        data = self._request(url)
        
        if not data:
            return []
        
        return data.get('results', [])


class PathwayAPICache:
    """通路API缓存"""
    
    def __init__(self, cache_dir: str):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = 86400 * 30  # 通路数据相对稳定
    
    def _get_cache_key(self, url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()
    
    def get(self, url: str) -> Optional[Dict]:
        cache_file = self.cache_dir / f"pw_{self._get_cache_key(url)}.json"
        
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
        cache_file = self.cache_dir / f"pw_{self._get_cache_key(url)}.json"
        try:
            with open(cache_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Cache write error: {e}")


class PathwayDatabase:
    """通路数据库统一接口"""
    
    def __init__(self, 
                 local_db_path: str = "data/pathways.db",
                 use_api: bool = True):
        self.local_db = LocalPathwayDatabase(local_db_path)
        self.use_api = use_api
        
        if use_api:
            self.kegg = KEGGPathwayAPI()
            self.reactome = ReactomeAPI()
            self.go = GOAPI()
    
    def search_pathways(self, query: str, 
                       source: Optional[str] = None) -> List[Dict]:
        """
        搜索通路
        
        Args:
            query: 搜索词
            source: 数据库来源 ('KEGG', 'Reactome', None表示所有)
        """
        results = []
        
        # 本地搜索
        local_results = self.local_db.search_pathways(query, source)
        for r in local_results:
            results.append(r.to_dict())
        
        # API搜索
        if self.use_api:
            if source is None or source == 'KEGG':
                kegg_pw = self.kegg.get_pathway(query)
                if kegg_pw:
                    results.append(kegg_pw.to_dict())
            
            if source is None or source == 'Reactome':
                reactome_results = self.reactome.search(query)
                for r in reactome_results:
                    results.append({
                        'pathway_id': r.get('stId', ''),
                        'name': r.get('name', ''),
                        'source': 'Reactome',
                        'species': r.get('species', [])
                    })
        
        return results
    
    def get_pathway_genes(self, pathway_id: str, 
                         source_db: str = "KEGG") -> List[str]:
        """获取通路中的基因"""
        # 先查本地
        local = self.local_db.get_pathway(pathway_id, source_db)
        if local and local.genes:
            return local.genes
        
        # API查询
        if self.use_api and source_db == "KEGG":
            return self.kegg.get_genes_by_pathway(pathway_id)
        
        return []
    
    def get_gene_pathways(self, gene_symbol: str) -> List[Dict]:
        """获取基因相关的所有通路"""
        results = []
        
        # 本地查询
        local_pws = self.local_db.get_pathways_by_gene(gene_symbol)
        for pw in local_pws:
            results.append(pw.to_dict())
        
        # API查询
        if self.use_api:
            kegg_pws = self.kegg.get_pathways_by_gene(gene_symbol)
            for pid in kegg_pws:
                pw = self.kegg.get_pathway(pid)
                if pw:
                    results.append(pw.to_dict())
            
            reactome_pws = self.reactome.get_pathways_by_gene(gene_symbol)
            results.extend(reactome_pws)
        
        return results
    
    def get_go_annotation(self, gene_symbols: List[str]) -> Dict[str, List[Dict]]:
        """
        获取基因的GO注释
        
        Returns:
            {gene: [GO_terms], ...}
        """
        annotations = {}
        
        for gene in gene_symbols:
            # 这里简化处理，实际应该调用专门的GO注释服务
            annotations[gene] = []
        
        return annotations
    
    def enrich_pathways(self, gene_list: List[str], 
                       background: Optional[List[str]] = None) -> List[Dict]:
        """
        通路富集分析
        
        Args:
            gene_list: 感兴趣的基因列表
            background: 背景基因列表
        
        Returns:
            富集结果
        """
        # 获取所有通路
        all_pathways = []
        if self.use_api:
            kegg_list = self.kegg.list_pathways()
            for pw in kegg_list:
                pw_genes = self.kegg.get_genes_by_pathway(pw['pathway_id'])
                all_pathways.append({
                    'pathway_id': pw['pathway_id'],
                    'name': pw['name'],
                    'genes': pw_genes
                })
        
        # 计算富集
        results = []
        gene_set = set(gene_list)
        bg_set = set(background) if background else set()
        
        for pw in all_pathways:
            pw_genes = set(pw['genes'])
            overlap = gene_set & pw_genes
            
            if len(overlap) > 0:
                # 简化的富集计算
                results.append({
                    'pathway_id': pw['pathway_id'],
                    'name': pw['name'],
                    'overlap_genes': list(overlap),
                    'overlap_count': len(overlap),
                    'pathway_gene_count': len(pw_genes)
                })
        
        # 按重叠基因数排序
        results.sort(key=lambda x: x['overlap_count'], reverse=True)
        return results
    
    def save_to_local(self, record: PathwayRecord):
        """保存到本地"""
        return self.local_db.add_pathway(record)


# 便捷函数
def search_pathways(query: str, source: Optional[str] = None) -> List[Dict]:
    """搜索通路"""
    db = PathwayDatabase()
    return db.search_pathways(query, source)


def get_pathway_genes(pathway_id: str, source_db: str = "KEGG") -> List[str]:
    """获取通路基因"""
    db = PathwayDatabase()
    return db.get_pathway_genes(pathway_id, source_db)


def enrich_pathways(gene_list: List[str]) -> List[Dict]:
    """通路富集分析"""
    db = PathwayDatabase()
    return db.enrich_pathways(gene_list)
