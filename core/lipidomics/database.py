"""
脂质数据库查询模块 - Lipid Database Module

支持：
1. 本地数据库 (SQLite)
   - LIPID MAPS
   - HMDB Lipids
   - LMSD (LIPID MAPS Structure Database)
   
2. 在线API
   - LIPID MAPS REST API
   - SwissLipids API
   - Lipidomics Gateway
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
class LipidRecord:
    """脂质记录"""
    lm_id: Optional[str] = None  # LIPID MAPS ID
    name: str = ""
    systematic_name: Optional[str] = None
    synonyms: List[str] = field(default_factory=list)
    lipid_class: Optional[str] = None
    category: Optional[str] = None  # Main class
    main_class: Optional[str] = None
    sub_class: Optional[str] = None
    
    # 分子信息
    formula: Optional[str] = None
    exact_mass: float = 0.0
    smiles: Optional[str] = None
    inchi: Optional[str] = None
    inchikey: Optional[str] = None
    
    # 链信息
    num_chains: int = 0
    total_carbons: int = 0
    total_double_bonds: int = 0
    chains: List[Dict] = field(default_factory=list)
    
    # 数据库交叉引用
    kegg_id: Optional[str] = None
    hmdb_id: Optional[str] = None
    chebi_id: Optional[str] = None
    pubchem_cid: Optional[str] = None
    swisslipids_id: Optional[str] = None
    
    # 生物信息
    pathway: List[str] = field(default_factory=list)
    function: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            'lm_id': self.lm_id,
            'name': self.name,
            'systematic_name': self.systematic_name,
            'synonyms': self.synonyms,
            'lipid_class': self.lipid_class,
            'category': self.category,
            'main_class': self.main_class,
            'sub_class': self.sub_class,
            'formula': self.formula,
            'exact_mass': self.exact_mass,
            'smiles': self.smiles,
            'inchi': self.inchi,
            'inchikey': self.inchikey,
            'num_chains': self.num_chains,
            'total_carbons': self.total_carbons,
            'total_double_bonds': self.total_double_bonds,
            'chains': self.chains,
            'kegg_id': self.kegg_id,
            'hmdb_id': self.hmdb_id,
            'chebi_id': self.chebi_id,
            'pubchem_cid': self.pubchem_cid,
            'swisslipids_id': self.swisslipids_id,
            'pathway': self.pathway,
            'function': self.function
        }


class LocalLipidDatabase:
    """本地脂质数据库"""
    
    def __init__(self, db_path: str = "data/lipids.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS lipids (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lm_id TEXT UNIQUE,
                    name TEXT,
                    systematic_name TEXT,
                    synonyms TEXT,  -- JSON list
                    lipid_class TEXT,
                    category TEXT,
                    main_class TEXT,
                    sub_class TEXT,
                    formula TEXT,
                    exact_mass REAL,
                    smiles TEXT,
                    inchi TEXT,
                    inchikey TEXT UNIQUE,
                    num_chains INTEGER,
                    total_carbons INTEGER,
                    total_double_bonds INTEGER,
                    chains TEXT,  -- JSON
                    kegg_id TEXT,
                    hmdb_id TEXT,
                    chebi_id TEXT,
                    pubchem_cid TEXT,
                    swisslipids_id TEXT,
                    pathway TEXT,  -- JSON
                    function TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建索引
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_lm_id ON lipids(lm_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_mass ON lipids(exact_mass)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_formula ON lipids(formula)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_class ON lipids(lipid_class)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_inchikey ON lipids(inchikey)')
            
            conn.commit()
    
    def add_lipid(self, record: LipidRecord) -> bool:
        """添加脂质记录"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO lipids 
                    (lm_id, name, systematic_name, synonyms, lipid_class, category,
                     main_class, sub_class, formula, exact_mass, smiles, inchi,
                     inchikey, num_chains, total_carbons, total_double_bonds,
                     chains, kegg_id, hmdb_id, chebi_id, pubchem_cid,
                     swisslipids_id, pathway, function)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    record.lm_id, record.name, record.systematic_name,
                    json.dumps(record.synonyms), record.lipid_class,
                    record.category, record.main_class, record.sub_class,
                    record.formula, record.exact_mass, record.smiles,
                    record.inchi, record.inchikey, record.num_chains,
                    record.total_carbons, record.total_double_bonds,
                    json.dumps(record.chains), record.kegg_id, record.hmdb_id,
                    record.chebi_id, record.pubchem_cid, record.swisslipids_id,
                    json.dumps(record.pathway), record.function
                ))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error adding lipid: {e}")
            return False
    
    def get_by_lm_id(self, lm_id: str) -> Optional[LipidRecord]:
        """通过LIPID MAPS ID获取"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM lipids WHERE lm_id = ?', (lm_id,))
            row = cursor.fetchone()
            return self._row_to_record(row) if row else None
    
    def search_by_mass(self, mass: float, tolerance: float = 0.01) -> List[LipidRecord]:
        """按质量搜索"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM lipids 
                WHERE exact_mass BETWEEN ? AND ?
            ''', (mass - tolerance, mass + tolerance))
            rows = cursor.fetchall()
            return [self._row_to_record(row) for row in rows]
    
    def search_by_formula(self, formula: str) -> List[LipidRecord]:
        """按分子式搜索"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM lipids WHERE formula = ?', (formula,))
            rows = cursor.fetchall()
            return [self._row_to_record(row) for row in rows]
    
    def search_by_class(self, lipid_class: str) -> List[LipidRecord]:
        """按类别搜索"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM lipids 
                WHERE lipid_class = ? OR category = ? OR main_class = ?
            ''', (lipid_class, lipid_class, lipid_class))
            rows = cursor.fetchall()
            return [self._row_to_record(row) for row in rows]
    
    def search_by_name(self, name: str) -> List[LipidRecord]:
        """按名称搜索"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM lipids 
                WHERE name LIKE ? OR systematic_name LIKE ? OR synonyms LIKE ?
            ''', (f'%{name}%', f'%{name}%', f'%{name}%'))
            rows = cursor.fetchall()
            return [self._row_to_record(row) for row in rows]
    
    def _row_to_record(self, row) -> LipidRecord:
        """转换行为记录"""
        return LipidRecord(
            lm_id=row[1],
            name=row[2],
            systematic_name=row[3],
            synonyms=json.loads(row[4]) if row[4] else [],
            lipid_class=row[5],
            category=row[6],
            main_class=row[7],
            sub_class=row[8],
            formula=row[9],
            exact_mass=row[10] or 0.0,
            smiles=row[11],
            inchi=row[12],
            inchikey=row[13],
            num_chains=row[14] or 0,
            total_carbons=row[15] or 0,
            total_double_bonds=row[16] or 0,
            chains=json.loads(row[17]) if row[17] else [],
            kegg_id=row[18],
            hmdb_id=row[19],
            chebi_id=row[20],
            pubchem_cid=row[21],
            swisslipids_id=row[22],
            pathway=json.loads(row[23]) if row[23] else [],
            function=row[24]
        )


class LIPIDMAPSAPI:
    """LIPID MAPS REST API客户端"""
    
    BASE_URL = "https://www.lipidmaps.org/rest/compound"
    
    def __init__(self, cache_dir: str = "data/cache"):
        self.cache = LipidAPICache(cache_dir)
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
            print(f"LIPID MAPS API error: {e}")
            return None
    
    def get_by_lm_id(self, lm_id: str) -> Optional[Dict]:
        """通过LM ID获取脂质"""
        url = f"{self.BASE_URL}/lm_id/{lm_id}/all/"
        return self._request(url)
    
    def search_by_name(self, name: str) -> List[Dict]:
        """按名称搜索"""
        url = f"{self.BASE_URL}/name/{quote(name)}/all/"
        data = self._request(url)
        return data if data else []
    
    def search_by_formula(self, formula: str) -> List[Dict]:
        """按分子式搜索"""
        url = f"{self.BASE_URL}/formula/{quote(formula)}/all/"
        data = self._request(url)
        return data if data else []
    
    def search_by_mass(self, mass: float, tolerance: float = 0.5) -> List[Dict]:
        """按质量搜索"""
        url = f"{self.BASE_URL}/mass/{mass}/{tolerance}/all/"
        data = self._request(url)
        return data if data else []
    
    def search_by_smiles(self, smiles: str) -> List[Dict]:
        """按SMILES搜索"""
        url = f"{self.BASE_URL}/smiles/{quote(smiles)}/all/"
        data = self._request(url)
        return data if data else []
    
    def get_classification(self, lm_id: str) -> Optional[Dict]:
        """获取脂质分类信息"""
        url = f"{self.BASE_URL}/lm_id/{lm_id}/classification/"
        return self._request(url)
    
    def get_structure(self, lm_id: str, format: str = 'smiles') -> Optional[str]:
        """获取结构信息"""
        url = f"{self.BASE_URL}/lm_id/{lm_id}/{format}/"
        data = self._request(url)
        if data and len(data) > 0:
            return data[0].get(format.upper())
        return None
    
    def parse_record(self, data: Dict) -> LipidRecord:
        """解析API返回数据为记录对象"""
        return LipidRecord(
            lm_id=data.get('LM_ID'),
            name=data.get('NAME', ''),
            systematic_name=data.get('SYSTEMATIC_NAME'),
            synonyms=data.get('SYNONYMS', '').split(';') if data.get('SYNONYMS') else [],
            lipid_class=data.get('CATEGORY'),
            category=data.get('MAIN_CLASS'),
            main_class=data.get('SUB_CLASS'),
            formula=data.get('FORMULA'),
            exact_mass=float(data.get('EXACT_MASS', 0)) if data.get('EXACT_MASS') else 0,
            smiles=data.get('SMILES'),
            inchi=data.get('INCHI'),
            inchikey=data.get('INCHI_KEY'),
            kegg_id=data.get('KEGG_ID'),
            hmdb_id=data.get('HMDB_ID'),
            pubchem_cid=str(data.get('PUBCHEM_CID')) if data.get('PUBCHEM_CID') else None
        )


class SwissLipidsAPI:
    """SwissLipids API客户端"""
    
    BASE_URL = "https://www.swisslipids.org/api"
    
    def __init__(self, cache_dir: str = "data/cache"):
        self.cache = LipidAPICache(cache_dir)
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
            print(f"SwissLipids API error: {e}")
            return None
    
    def search(self, query: str) -> List[Dict]:
        """搜索脂质"""
        url = f"{self.BASE_URL}/search?term={quote(query)}"
        data = self._request(url)
        return data.get('results', []) if data else []
    
    def get_lipid(self, sl_id: str) -> Optional[Dict]:
        """获取脂质详情"""
        url = f"{self.BASE_URL}/lipids/{sl_id}"
        return self._request(url)
    
    def get_classification(self, sl_id: str) -> Optional[Dict]:
        """获取分类信息"""
        url = f"{self.BASE_URL}/lipids/{sl_id}/classification"
        return self._request(url)
    
    def get_mass(self, sl_id: str) -> Optional[float]:
        """获取精确质量"""
        url = f"{self.BASE_URL}/lipids/{sl_id}/mass"
        data = self._request(url)
        return data.get('mass') if data else None


class LipidAPICache:
    """脂质API缓存"""
    
    def __init__(self, cache_dir: str):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = 86400 * 30  # 脂质数据相对稳定，缓存30天
    
    def _get_cache_key(self, url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()
    
    def get(self, url: str) -> Optional[Dict]:
        cache_file = self.cache_dir / f"lipid_{self._get_cache_key(url)}.json"
        
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
        cache_file = self.cache_dir / f"lipid_{self._get_cache_key(url)}.json"
        try:
            with open(cache_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Cache write error: {e}")


class LipidDatabase:
    """脂质数据库统一接口"""
    
    def __init__(self, 
                 local_db_path: str = "data/lipids.db",
                 use_api: bool = True):
        self.local_db = LocalLipidDatabase(local_db_path)
        self.use_api = use_api
        
        if use_api:
            self.lipidmaps = LIPIDMAPSAPI()
            self.swisslipids = SwissLipidsAPI()
    
    def search(self, query: str, search_type: str = 'name') -> List[Dict]:
        """
        综合搜索脂质
        
        Args:
            query: 搜索词
            search_type: 搜索类型 ('name', 'mass', 'formula', 'lm_id', 'smiles')
        """
        results = []
        seen_ids = set()
        
        # 本地搜索
        if search_type == 'name':
            local_results = self.local_db.search_by_name(query)
        elif search_type == 'mass':
            mass = float(query)
            local_results = self.local_db.search_by_mass(mass)
        elif search_type == 'formula':
            local_results = self.local_db.search_by_formula(query)
        elif search_type == 'lm_id':
            record = self.local_db.get_by_lm_id(query)
            local_results = [record] if record else []
        else:
            local_results = []
        
        for r in local_results:
            results.append(r.to_dict())
            if r.lm_id:
                seen_ids.add(r.lm_id)
        
        # API搜索
        if self.use_api:
            if search_type == 'name':
                api_results = self.lipidmaps.search_by_name(query)
            elif search_type == 'mass':
                api_results = self.lipidmaps.search_by_mass(float(query))
            elif search_type == 'formula':
                api_results = self.lipidmaps.search_by_formula(query)
            else:
                api_results = []
            
            for data in api_results:
                record = self.lipidmaps.parse_record(data)
                if record.lm_id not in seen_ids:
                    results.append(record.to_dict())
                    seen_ids.add(record.lm_id)
            
            # SwissLipids搜索
            if search_type == 'name':
                swiss_results = self.swisslipids.search(query)
                for r in swiss_results:
                    if r.get('id') not in seen_ids:
                        results.append({
                            'swisslipids_id': r.get('id'),
                            'name': r.get('name'),
                            'formula': r.get('formula'),
                            'mass': r.get('mass'),
                            'source': 'SwissLipids'
                        })
        
        return results
    
    def annotate_lipid(self, lm_id: str) -> Dict:
        """
        详细注释脂质
        
        Returns:
            详细注释信息
        """
        result = {'lm_id': lm_id, 'annotations': {}}
        
        # 本地查询
        local = self.local_db.get_by_lm_id(lm_id)
        if local:
            result['annotations']['local'] = local.to_dict()
        
        # API查询
        if self.use_api:
            lipid_data = self.lipidmaps.get_by_lm_id(lm_id)
            if lipid_data:
                result['annotations']['lipidmaps'] = lipid_data
            
            classification = self.lipidmaps.get_classification(lm_id)
            if classification:
                result['annotations']['classification'] = classification
        
        return result
    
    def identify_by_mass(self, mass: float, 
                        adduct: str = '[M+H]+',
                        tolerance: float = 0.01) -> List[Dict]:
        """
        通过质荷比鉴定脂质
        
        Args:
            mass: 观测到的m/z
            adduct: 加合物类型
            tolerance: 质量容差
        
        Returns:
            可能的脂质列表
        """
        # 计算中性质量
        neutral_mass = self._calculate_neutral_mass(mass, adduct)
        
        # 搜索
        candidates = self.local_db.search_by_mass(neutral_mass, tolerance)
        
        if self.use_api and len(candidates) < 5:
            api_candidates = self.lipidmaps.search_by_mass(neutral_mass, tolerance)
            for data in api_candidates:
                candidates.append(self.lipidmaps.parse_record(data))
        
        # 格式化结果
        results = []
        for c in candidates:
            results.append({
                'lm_id': c.lm_id,
                'name': c.name,
                'formula': c.formula,
                'theoretical_mass': c.exact_mass,
                'observed_mass': mass,
                'mass_error_ppm': abs(c.exact_mass - neutral_mass) / c.exact_mass * 1e6,
                'lipid_class': c.lipid_class,
                'chains': c.chains
            })
        
        # 按质量误差排序
        results.sort(key=lambda x: x['mass_error_ppm'])
        return results
    
    def _calculate_neutral_mass(self, mz: float, adduct: str) -> float:
        """从中性质量计算m/z"""
        proton_mass = 1.00728
        
        adduct_adjustments = {
            '[M+H]+': -proton_mass,
            '[M+Na]+': -22.98977,
            '[M+NH4]+': -18.03383,
            '[M+K]+': -38.96371,
            '[M-H]-': proton_mass,
            '[M+HCOO]-': -44.99765,
            '[M+CH3COO]-': -59.01385,
        }
        
        adjustment = adduct_adjustments.get(adduct, 0)
        return mz + adjustment
    
    def classify_lipid(self, lm_id: str) -> Optional[Dict]:
        """获取脂质分类信息"""
        if self.use_api:
            return self.lipidmaps.get_classification(lm_id)
        return None
    
    def save_to_local(self, record: LipidRecord):
        """保存到本地数据库"""
        return self.local_db.add_lipid(record)
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        with sqlite3.connect(self.local_db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM lipids')
            total = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(DISTINCT lipid_class) FROM lipids')
            classes = cursor.fetchone()[0]
            
            return {
                'total_lipids': total,
                'lipid_classes': classes
            }


# 便捷函数
def search_lipid(query: str, search_type: str = 'name', use_api: bool = True) -> List[Dict]:
    """搜索脂质"""
    db = LipidDatabase(use_api=use_api)
    return db.search(query, search_type)


def identify_lipid_by_mass(mass: float, adduct: str = '[M+H]+', tolerance: float = 0.01) -> List[Dict]:
    """通过质量鉴定脂质"""
    db = LipidDatabase()
    return db.identify_by_mass(mass, adduct, tolerance)


def get_lipid_classification(lm_id: str) -> Optional[Dict]:
    """获取脂质分类"""
    db = LipidDatabase()
    return db.classify_lipid(lm_id)
