"""
代谢组学分析模块 - Metabolomics Module

功能：
1. mzML/mzXML 文件解析
2. 峰检测与对齐
3. 多元统计分析（PCA, PLS-DA, OPLS-DA）
4. 差异代谢物筛选
5. 可视化（火山图、得分图、载荷图）
6. 数据库查询（HMDB, PubChem, KEGG）
"""

from .mzml_parser import MZMLParser
from .feature_detection import FeatureDetector
from .statistical_analysis import MetabolomicsAnalyzer
from .visualization import MetabolomicsVisualizer
from .workflow import MetabolomicsWorkflow

# Database module (optional, requires pandas)
try:
    from .database import (
        MetaboliteDatabase,
        MetaboliteRecord,
        LocalDatabase,
        PubChemAPI,
        KEGGAPI,
        ChEBIAPI,
        search_metabolite,
        annotate_mass_peaks
    )
except ImportError:
    MetaboliteDatabase = None
    MetaboliteRecord = None
    LocalDatabase = None
    PubChemAPI = None
    KEGGAPI = None
    ChEBIAPI = None
    search_metabolite = None
    annotate_mass_peaks = None

__all__ = [
    'MZMLParser',
    'FeatureDetector', 
    'MetabolomicsAnalyzer',
    'MetabolomicsVisualizer',
    'MetabolomicsWorkflow',
    # Database
    'MetaboliteDatabase',
    'MetaboliteRecord',
    'LocalDatabase',
    'PubChemAPI',
    'KEGGAPI',
    'ChEBIAPI',
    'search_metabolite',
    'annotate_mass_peaks',
]
