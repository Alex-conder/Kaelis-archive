"""
多组学整合模块 - Multi-Omics Integration

功能：
1. 多组学数据整合
2. 跨组学相关性分析
3. 通路串扰分析
4. 多组学可视化
5. 通路数据库查询（KEGG, Reactome, GO）
"""

# Integration (requires pandas, numpy, scipy, sklearn)
try:
    from .integration import (
        MultiOmicsIntegrator,
        OmicsDataset,
        MOFAStyleIntegration
    )
except ImportError:
    MultiOmicsIntegrator = None
    OmicsDataset = None
    MOFAStyleIntegration = None

# Correlation analysis (requires pandas, numpy, scipy, sklearn)
try:
    from .correlation import (
        CrossOmicsCorrelation,
        CorrelationResult,
        PartialCorrelation,
        CanonicalCorrelationAnalysis,
        SparseCCA,
        CorrelationNetwork,
        compute_cross_omics_correlation,
        run_cca_analysis
    )
except ImportError:
    CrossOmicsCorrelation = None
    CorrelationResult = None
    PartialCorrelation = None
    CanonicalCorrelationAnalysis = None
    SparseCCA = None
    CorrelationNetwork = None
    compute_cross_omics_correlation = None
    run_cca_analysis = None

# Pathway crosstalk (requires pandas, numpy, scipy)
try:
    from .pathway_crosstalk import (
        PathwayDatabase,
        EnrichmentAnalyzer,
        CrosstalkAnalyzer,
        MultiOmicsPathwayIntegration,
        PathwayResult,
        CrosstalkResult,
        run_pathway_enrichment,
        analyze_pathway_crosstalk
    )
except ImportError:
    PathwayDatabase = None
    EnrichmentAnalyzer = None
    CrosstalkAnalyzer = None
    MultiOmicsPathwayIntegration = None
    PathwayResult = None
    CrosstalkResult = None
    run_pathway_enrichment = None
    analyze_pathway_crosstalk = None

# Visualization (requires matplotlib, seaborn)
try:
    from .visualization import MultiOmicsVisualizer
except ImportError:
    MultiOmicsVisualizer = None

# Database module (optional)
try:
    from .database import (
        PathwayDatabase as PathwayDB,
        PathwayRecord,
        GOTerm,
        KEGGPathwayAPI,
        ReactomeAPI,
        GOAPI,
        search_pathways,
        get_pathway_genes,
        enrich_pathways
    )
except ImportError:
    PathwayDB = None
    PathwayRecord = None
    GOTerm = None
    KEGGPathwayAPI = None
    ReactomeAPI = None
    GOAPI = None
    search_pathways = None
    get_pathway_genes = None
    enrich_pathways = None

__all__ = [
    # Integration
    'MultiOmicsIntegrator',
    'OmicsDataset',
    'MOFAStyleIntegration',
    # Correlation
    'CrossOmicsCorrelation',
    'CorrelationResult',
    'PartialCorrelation',
    'CanonicalCorrelationAnalysis',
    'SparseCCA',
    'CorrelationNetwork',
    'compute_cross_omics_correlation',
    'run_cca_analysis',
    # Pathway crosstalk
    'PathwayDatabase',
    'EnrichmentAnalyzer',
    'CrosstalkAnalyzer',
    'MultiOmicsPathwayIntegration',
    'PathwayResult',
    'CrosstalkResult',
    'run_pathway_enrichment',
    'analyze_pathway_crosstalk',
    # Visualization
    'MultiOmicsVisualizer',
    # Database
    'PathwayDB',
    'PathwayRecord',
    'GOTerm',
    'KEGGPathwayAPI',
    'ReactomeAPI',
    'GOAPI',
    'search_pathways',
    'get_pathway_genes',
    'enrich_pathways',
]
