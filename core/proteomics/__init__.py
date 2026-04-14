"""
蛋白质组学分析模块 - Proteomics Module

功能：
1. mzIdentML/pepXML 文件解析
2. 蛋白鉴定与定量
3. 差异蛋白分析
4. 通路富集分析
5. 蛋白相互作用网络
6. 数据库查询（UniProt, NCBI, STRING）
"""

# mzIdentML parser (no external deps)
from .mzidentml_parser import MZIdentMLParser, ProteinIdentification

# Peptide identification (requires pandas, numpy)
try:
    from .peptide_identification import (
        PeptideIdentifier, 
        PeptideMatch, 
        PeptideSpectrumMatch,
        SpectrumSimulator,
        PeptideIndexer
    )
except ImportError:
    PeptideIdentifier = None
    PeptideMatch = None
    PeptideSpectrumMatch = None
    SpectrumSimulator = None
    PeptideIndexer = None

# Protein quantification (requires pandas, numpy, scipy, sklearn)
try:
    from .protein_quantification import (
        LFQQuantifier,
        IBAQQuantifier,
        TMTQuantifier,
        SILACQuantifier,
        ProteinQuantifier,
        QuantificationResult,
        calculate_fold_change
    )
except ImportError:
    LFQQuantifier = None
    IBAQQuantifier = None
    TMTQuantifier = None
    SILACQuantifier = None
    ProteinQuantifier = None
    QuantificationResult = None
    calculate_fold_change = None

# Protein analysis
try:
    from .protein_analysis import (
        ProteomicsAnalyzer,
        DifferentialProtein,
        EnrichmentResult
    )
except ImportError:
    ProteomicsAnalyzer = None
    DifferentialProtein = None
    EnrichmentResult = None

# Database module (optional)
try:
    from .database import (
        ProteinDatabase,
        ProteinRecord,
        PeptideRecord,
        UniProtAPI,
        NCBIProteinAPI,
        STRINGAPI,
        search_protein,
        get_protein_function,
        get_protein_interactions
    )
except ImportError:
    ProteinDatabase = None
    ProteinRecord = None
    PeptideRecord = None
    UniProtAPI = None
    NCBIProteinAPI = None
    STRINGAPI = None
    search_protein = None
    get_protein_function = None
    get_protein_interactions = None

__all__ = [
    # mzIdentML
    'MZIdentMLParser',
    'ProteinIdentification',
    # Peptide identification
    'PeptideIdentifier',
    'PeptideMatch',
    'PeptideSpectrumMatch',
    'SpectrumSimulator',
    'PeptideIndexer',
    # Protein quantification
    'LFQQuantifier',
    'IBAQQuantifier',
    'TMTQuantifier',
    'SILACQuantifier',
    'ProteinQuantifier',
    'QuantificationResult',
    'calculate_fold_change',
    # Protein analysis
    'ProteomicsAnalyzer',
    'DifferentialProtein',
    'EnrichmentResult',
    # Database
    'ProteinDatabase',
    'ProteinRecord',
    'PeptideRecord',
    'UniProtAPI',
    'NCBIProteinAPI',
    'STRINGAPI',
    'search_protein',
    'get_protein_function',
    'get_protein_interactions',
]
