"""
代谢物数据库查询模块 - Metabolite Database Module

支持：
1. 本地数据库 (SQLite)
   - HMDB (Human Metabolome Database)
   - KEGG COMPOUND
   - MassBank
   
2. 在线API
   - PubChem PUG-REST
   - ChemSpider
   - KEGG API
   - ChEBI
   - METLIN
"""

import sqlite3
import json
import time
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Union, Any
from dataclasses import dataclass
from urllib.parse import quote
import urllib.request
import urllib.error
import socket


@dataclass
class MetaboliteRecord:
    """代谢物记录"""
    name: str
    formula: str
    exact_mass: float
    inchi: Optional[str] = None
    inchikey: Optional[str] = None
    smiles: Optional[str] = None
    hmdb_id: Optional[str] = None
    kegg_id: Optional[str] = None
    pubchem_cid: Optional[str] = None
    chebi_id: Optional[str] = None
    synonyms: List[str] = None
    pathway: List[str] = None
    disease: List[str] = None
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'formula': self.formula,
            'exact_mass': self.exact_mass,
            'inchi': self.inchi,
            'inchikey': self.inchikey,
            'smiles': self.smiles,
            'hmdb_id': self.hmdb_id,
            'kegg_id': self.kegg_id,
            'pubchem_cid': self.pubchem_cid,
            'chebi_id': self.chebi_id,
            'synonyms': self.synonyms or [],
            'pathway': self.pathway or [],
            'disease': self.disease or []
        }


class LocalDatabase:
    """本地SQLite数据库管理"""
    
    def __init__(self, db_path: str = "data/metabolites.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 代谢物主表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS metabolites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    formula TEXT,
                    exact_mass REAL,
                    inchi TEXT,
                    inchikey TEXT UNIQUE,
                    smiles TEXT,
                    hmdb_id TEXT UNIQUE,
                    kegg_id TEXT UNIQUE,
                    pubchem_cid TEXT,
                    chebi_id TEXT,
                    synonyms TEXT,  -- JSON list
                    pathway TEXT,   -- JSON list
                    disease TEXT,   -- JSON list
                    source_db TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建索引
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_mass ON metabolites(exact_mass)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_formula ON metabolites(formula)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_inchikey ON metabolites(inchikey)
            ''')
            
            conn.commit()
    
    def add_metabolite(self, record: MetaboliteRecord) -> bool:
        """添加代谢物记录"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO metabolites 
                    (name, formula, exact_mass, inchi, inchikey, smiles,
                     hmdb_id, kegg_id, pubchem_cid, chebi_id,
                     synonyms, pathway, disease, source_db)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    record.name, record.formula, record.exact_mass,
                    record.inchi, record.inchikey, record.smiles,
                    record.hmdb_id, record.kegg_id, record.pubchem_cid,
                    record.chebi_id,
                    json.dumps(record.synonyms or []),
                    json.dumps(record.pathway or []),
                    json.dumps(record.disease or []),
                    'local'
                ))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error adding metabolite: {e}")
            return False
    
    def search_by_mass(self, mass: float, tolerance: float = 0.01) -> List[MetaboliteRecord]:
        """按质量搜索代谢物"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM metabolites 
                WHERE exact_mass BETWEEN ? AND ?
            ''', (mass - tolerance, mass + tolerance))
            
            rows = cursor.fetchall()
            return [self._row_to_record(row) for row in rows]
    
    def search_by_formula(self, formula: str) -> List[MetaboliteRecord]:
        """按分子式搜索"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM metabolites WHERE formula = ?
            ''', (formula,))
            
            rows = cursor.fetchall()
            return [self._row_to_record(row) for row in rows]
    
    def search_by_name(self, name: str) -> List[MetaboliteRecord]:
        """按名称搜索（支持模糊匹配）"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM metabolites 
                WHERE name LIKE ? OR synonyms LIKE ?
            ''', (f'%{name}%', f'%{name}%'))
            
            rows = cursor.fetchall()
            return [self._row_to_record(row) for row in rows]
    
    def search_by_inchikey(self, inchikey: str) -> Optional[MetaboliteRecord]:
        """按InChIKey搜索"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM metabolites WHERE inchikey = ?
            ''', (inchikey,))
            
            row = cursor.fetchone()
            return self._row_to_record(row) if row else None
    
    def _row_to_record(self, row) -> MetaboliteRecord:
        """将数据库行转换为记录对象"""
        return MetaboliteRecord(
            name=row[1],
            formula=row[2],
            exact_mass=row[3],
            inchi=row[4],
            inchikey=row[5],
            smiles=row[6],
            hmdb_id=row[7],
            kegg_id=row[8],
            pubchem_cid=row[9],
            chebi_id=row[10],
            synonyms=json.loads(row[11]) if row[11] else [],
            pathway=json.loads(row[12]) if row[12] else [],
            disease=json.loads(row[13]) if row[13] else []
        )
    
    def get_stats(self) -> Dict:
        """获取数据库统计信息"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM metabolites')
            count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(DISTINCT formula) FROM metabolites')
            formula_count = cursor.fetchone()[0]
            
            return {
                'total_metabolites': count,
                'unique_formulas': formula_count
            }


class APICache:
    """API响应缓存"""
    
    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = 86400 * 7  # 7天缓存
    
    def _get_cache_key(self, url: str) -> str:
        """生成缓存键"""
        return hashlib.md5(url.encode()).hexdigest()
    
    def get(self, url: str) -> Optional[Dict]:
        """获取缓存数据"""
        cache_file = self.cache_dir / f"{self._get_cache_key(url)}.json"
        
        if not cache_file.exists():
            return None
        
        # 检查过期
        if time.time() - cache_file.stat().st_mtime > self.ttl:
            cache_file.unlink()
            return None
        
        try:
            with open(cache_file, 'r') as f:
                return json.load(f)
        except Exception:
            return None
    
    def set(self, url: str, data: Dict):
        """设置缓存数据"""
        cache_file = self.cache_dir / f"{self._get_cache_key(url)}.json"
        try:
            with open(cache_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Cache write error: {e}")


class PubChemAPI:
    """PubChem PUG-REST API客户端"""
    
    BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
    
    def __init__(self, cache: Optional[APICache] = None):
        self.cache = cache or APICache()
        self.timeout = 10
    
    def _request(self, url: str) -> Optional[Dict]:
        """发送HTTP请求"""
        # 检查缓存
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
            print(f"PubChem API error: {e}")
            return None
    
    def search_by_name(self, name: str) -> List[Dict]:
        """按名称搜索化合物"""
        url = f"{self.BASE_URL}/compound/name/{quote(name)}/cids/JSON"
        data = self._request(url)
        
        if not data or 'IdentifierList' not in data:
            return []
        
        cids = data['IdentifierList'].get('CID', [])
        results = []
        
        for cid in cids[:5]:  # 限制结果数
            compound_info = self.get_compound_by_cid(cid)
            if compound_info:
                results.append(compound_info)
        
        return results
    
    def get_compound_by_cid(self, cid: Union[str, int]) -> Optional[Dict]:
        """通过CID获取化合物信息"""
        url = f"{self.BASE_URL}/compound/cid/{cid}/property/IsomericSMILES,InChI,InChIKey,MolecularFormula,MolecularWeight,IUPACName/JSON"
        data = self._request(url)
        
        if not data or 'PropertyTable' not in data:
            return None
        
        props = data['PropertyTable'].get('Properties', [{}])[0]
        
        return {
            'pubchem_cid': str(cid),
            'name': props.get('IUPACName', ''),
            'formula': props.get('MolecularFormula', ''),
            'molecular_weight': props.get('MolecularWeight', 0),
            'smiles': props.get('IsomericSMILES', ''),
            'inchi': props.get('InChI', ''),
            'inchikey': props.get('InChIKey', ''),
            'source': 'PubChem'
        }
    
    def search_by_mass(self, mass: float, tolerance: float = 0.01) -> List[Dict]:
        """按分子量搜索"""
        # PubChem支持质量范围查询
        min_mass = mass - tolerance
        max_mass = mass + tolerance
        url = f"{self.BASE_URL}/compound/fastformula/mass/{min_mass}/{max_mass}/cids/JSON"
        
        data = self._request(url)
        if not data or 'IdentifierList' not in data:
            return []
        
        cids = data['IdentifierList'].get('CID', [])
        results = []
        
        for cid in cids[:10]:
            compound_info = self.get_compound_by_cid(cid)
            if compound_info:
                results.append(compound_info)
        
        return results


class KEGGAPI:
    """KEGG API客户端"""
    
    BASE_URL = "https://rest.kegg.jp"
    
    def __init__(self, cache: Optional[APICache] = None):
        self.cache = cache or APICache()
        self.timeout = 10
    
    def _request(self, url: str) -> Optional[str]:
        """发送HTTP请求"""
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
    
    def search_compound(self, query: str) -> List[Dict]:
        """搜索化合物"""
        url = f"{self.BASE_URL}/find/compound/{quote(query)}"
        text = self._request(url)
        
        if not text:
            return []
        
        results = []
        for line in text.strip().split('\n'):
            if '\t' in line:
                kegg_id, name = line.split('\t', 1)
                results.append({
                    'kegg_id': kegg_id,
                    'name': name,
                    'source': 'KEGG'
                })
        
        return results
    
    def get_compound(self, kegg_id: str) -> Optional[Dict]:
        """获取化合物详细信息"""
        url = f"{self.BASE_URL}/get/{kegg_id}"
        text = self._request(url)
        
        if not text:
            return None
        
        result = {
            'kegg_id': kegg_id,
            'source': 'KEGG',
            'name': '',
            'formula': '',
            'exact_mass': 0,
            'pathway': [],
            'enzyme': []
        }
        
        for line in text.split('\n'):
            if line.startswith('NAME'):
                result['name'] = line.split(maxsplit=1)[1] if len(line.split()) > 1 else ''
            elif line.startswith('FORMULA'):
                result['formula'] = line.split(maxsplit=1)[1] if len(line.split()) > 1 else ''
            elif line.startswith('EXACT_MASS'):
                try:
                    result['exact_mass'] = float(line.split()[1])
                except (IndexError, ValueError):
                    pass
            elif line.startswith('PATHWAY'):
                pathway_id = line.split()[1] if len(line.split()) > 1 else ''
                if pathway_id:
                    result['pathway'].append(pathway_id)
            elif line.startswith('ENZYME'):
                enzyme = line.split()[1] if len(line.split()) > 1 else ''
                if enzyme:
                    result['enzyme'].append(enzyme)
        
        return result
    
    def get_pathway(self, pathway_id: str) -> Optional[Dict]:
        """获取通路信息"""
        url = f"{self.BASE_URL}/get/{pathway_id}"
        text = self._request(url)
        
        if not text:
            return None
        
        result = {
            'pathway_id': pathway_id,
            'name': '',
            'description': '',
            'compounds': [],
            'genes': []
        }
        
        section = None
        for line in text.split('\n'):
            if line.startswith('NAME'):
                result['name'] = line.split(maxsplit=1)[1] if len(line.split()) > 1 else ''
            elif line.startswith('DESCRIPTION'):
                section = 'description'
            elif line.startswith('COMPOUND'):
                section = 'compound'
                compound = line.split()[1] if len(line.split()) > 1 else ''
                if compound:
                    result['compounds'].append(compound)
            elif line.startswith('GENE'):
                section = 'gene'
            elif line.startswith(' ') and section == 'description':
                result['description'] += line.strip() + ' '
            elif line.startswith(' ') and section == 'compound':
                compound = line.split()[0] if line.split() else ''
                if compound and compound not in result['compounds']:
                    result['compounds'].append(compound)
        
        return result


class ChEBIAPI:
    """ChEBI API客户端"""
    
    BASE_URL = "https://www.ebi.ac.uk/chebi/webServices/rest"
    
    def __init__(self, cache: Optional[APICache] = None):
        self.cache = cache or APICache()
        self.timeout = 10
    
    def _request(self, url: str) -> Optional[Dict]:
        """发送HTTP请求"""
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
            print(f"ChEBI API error: {e}")
            return None
    
    def search_by_name(self, name: str) -> List[Dict]:
        """按名称搜索"""
        url = f"{self.BASE_URL}/lite/compound?name={quote(name)}&maxResults=10"
        data = self._request(url)
        
        if not data:
            return []
        
        results = []
        compounds = data.get('compounds', [])
        
        for compound in compounds:
            results.append({
                'chebi_id': compound.get('chebiId', ''),
                'name': compound.get('compoundName', ''),
                'definition': compound.get('definition', ''),
                'source': 'ChEBI'
            })
        
        return results


class MetaboliteDatabase:
    """代谢物数据库统一接口"""
    
    def __init__(self, 
                 local_db_path: str = "data/metabolites.db",
                 use_api: bool = True,
                 cache_dir: str = "data/cache"):
        """
        初始化代谢物数据库
        
        Args:
            local_db_path: 本地数据库路径
            use_api: 是否使用在线API
            cache_dir: 缓存目录
        """
        self.local_db = LocalDatabase(local_db_path)
        self.use_api = use_api
        self.cache = APICache(cache_dir)
        
        if use_api:
            self.pubchem = PubChemAPI(self.cache)
            self.kegg = KEGGAPI(self.cache)
            self.chebi = ChEBIAPI(self.cache)
    
    def search(self, query: str, search_type: str = 'name') -> List[Dict]:
        """
        综合搜索代谢物
        
        Args:
            query: 搜索查询
            search_type: 搜索类型 ('name', 'mass', 'formula', 'inchikey')
        
        Returns:
            搜索结果列表
        """
        results = []
        seen_inchikeys = set()
        
        # 1. 搜索本地数据库
        if search_type == 'name':
            local_results = self.local_db.search_by_name(query)
        elif search_type == 'mass':
            mass = float(query)
            local_results = self.local_db.search_by_mass(mass)
        elif search_type == 'formula':
            local_results = self.local_db.search_by_formula(query)
        elif search_type == 'inchikey':
            record = self.local_db.search_by_inchikey(query)
            local_results = [record] if record else []
        else:
            local_results = []
        
        for r in local_results:
            results.append(r.to_dict())
            if r.inchikey:
                seen_inchikeys.add(r.inchikey)
        
        # 2. 搜索在线API
        if self.use_api:
            # PubChem
            if search_type == 'name':
                api_results = self.pubchem.search_by_name(query)
            elif search_type == 'mass':
                api_results = self.pubchem.search_by_mass(float(query))
            else:
                api_results = []
            
            for r in api_results:
                if r.get('inchikey') not in seen_inchikeys:
                    results.append(r)
                    seen_inchikeys.add(r.get('inchikey'))
            
            # KEGG
            if search_type == 'name':
                kegg_results = self.kegg.search_compound(query)
                for r in kegg_results:
                    results.append(r)
            
            # ChEBI
            if search_type == 'name':
                chebi_results = self.chebi.search_by_name(query)
                for r in chebi_results:
                    results.append(r)
        
        return results
    
    def annotate_peaks(self, peaks: List[Dict], 
                       mass_tolerance: float = 0.01) -> List[Dict]:
        """
        注释质谱峰
        
        Args:
            peaks: 峰列表 [{'mz': float, 'intensity': float}, ...]
            mass_tolerance: 质量容差
        
        Returns:
            带注释的峰列表
        """
        annotated = []
        
        for peak in peaks:
            mz = peak['mz']
            annotations = self.local_db.search_by_mass(mz, mass_tolerance)
            
            if self.use_api and len(annotations) < 5:
                api_annotations = self.pubchem.search_by_mass(mz, mass_tolerance)
                annotations.extend([
                    MetaboliteRecord(
                        name=a.get('name', ''),
                        formula=a.get('formula', ''),
                        exact_mass=a.get('molecular_weight', 0),
                        inchikey=a.get('inchikey', ''),
                        pubchem_cid=a.get('pubchem_cid', '')
                    )
                    for a in api_annotations
                ])
            
            annotated_peak = peak.copy()
            annotated_peak['annotations'] = [
                {
                    'name': a.name,
                    'formula': a.formula,
                    'mass_error': abs(mz - a.exact_mass),
                    'database': a.hmdb_id or a.kegg_id or 'Unknown'
                }
                for a in annotations[:5]
            ]
            annotated.append(annotated_peak)
        
        return annotated
    
    def add_to_local(self, record: MetaboliteRecord):
        """添加记录到本地数据库"""
        return self.local_db.add_metabolite(record)
    
    def get_stats(self) -> Dict:
        """获取数据库统计"""
        return self.local_db.get_stats()


# 便捷函数
def search_metabolite(query: str, 
                     search_type: str = 'name',
                     use_api: bool = True) -> List[Dict]:
    """
    搜索代谢物
    
    Args:
        query: 搜索词
        search_type: 搜索类型
        use_api: 是否使用在线API
    
    Returns:
        搜索结果
    """
    db = MetaboliteDatabase(use_api=use_api)
    return db.search(query, search_type)


def annotate_mass_peaks(peaks: List[Dict], 
                       mass_tolerance: float = 0.01) -> List[Dict]:
    """
    注释质谱峰
    
    Args:
        peaks: 峰列表
        mass_tolerance: 质量容差
    
    Returns:
        带注释的峰
    """
    db = MetaboliteDatabase()
    return db.annotate_peaks(peaks, mass_tolerance)
