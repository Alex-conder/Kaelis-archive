"""
脂质组学分析模块 - Lipidomics Module

功能：
1. 脂质鉴定与解析
2. 脂质分类统计
3. 脂质定量分析
4. 脂质组比较
5. 脂质通路分析
6. 数据库查询（LIPID MAPS, SwissLipids）
"""

# Lipid parser (minimal deps)
from .lipid_parser import (
    LipidClass,
    Lipid,
    FattyAcidChain,
    LipidParser,
    LipidNameConverter,
    parse_lipid_name,
    get_lipid_shorthand,
    classify_lipid_by_name
)

# Lipid analysis (requires pandas, numpy, scipy, sklearn)
try:
    from .lipid_analysis import (
        LipidomicsAnalyzer,
        LipidMolecule,
        LipidClassification,
        LipidQuantification,
        LipidEnrichment
    )
except ImportError:
    LipidomicsAnalyzer = None
    LipidMolecule = None
    LipidClassification = None
    LipidQuantification = None
    LipidEnrichment = None

# Database module (optional)
try:
    from .database import (
        LipidDatabase,
        LipidRecord,
        LIPIDMAPSAPI,
        SwissLipidsAPI,
        search_lipid,
        identify_lipid_by_mass,
        get_lipid_classification
    )
except ImportError:
    LipidDatabase = None
    LipidRecord = None
    LIPIDMAPSAPI = None
    SwissLipidsAPI = None
    search_lipid = None
    identify_lipid_by_mass = None
    get_lipid_classification = None

__all__ = [
    # Lipid parser
    'LipidClass',
    'Lipid',
    'FattyAcidChain',
    'LipidParser',
    'LipidNameConverter',
    'parse_lipid_name',
    'get_lipid_shorthand',
    'classify_lipid_by_name',
    # Lipid analysis
    'LipidomicsAnalyzer',
    'LipidMolecule',
    'LipidClassification',
    'LipidQuantification',
    'LipidEnrichment',
    # Database
    'LipidDatabase',
    'LipidRecord',
    'LIPIDMAPSAPI',
    'SwissLipidsAPI',
    'search_lipid',
    'identify_lipid_by_mass',
    'get_lipid_classification',
]
