"""
基因组学分析模块 - Genomics Module

功能：
1. VCF 文件解析
2. 变异检测与注释
3. GWAS 分析
4. 突变谱分析
5. 数据库查询（dbSNP, ClinVar, Ensembl, gnomAD）
"""

# VCF parser (minimal deps)
from .vcf_parser import VCFParser, Variant

# Variant analysis (requires pandas, numpy, scipy)
try:
    from .variant_analysis import (
        VariantFilter,
        VariantAnnotator,
        VariantStatistics,
        VariantPrioritizer,
        VariantAnnotation,
        filter_variants,
        annotate_variants,
        find_deleterious_variants
    )
except ImportError:
    VariantFilter = None
    VariantAnnotator = None
    VariantStatistics = None
    VariantPrioritizer = None
    VariantAnnotation = None
    filter_variants = None
    annotate_variants = None
    find_deleterious_variants = None

# GWAS analysis (requires pandas, numpy, scipy, sklearn)
try:
    from .gwas_analysis import (
        AssociationTester,
        MultipleTestingCorrection,
        GWASAnalyzer,
        LDAnalyzer,
        PRSCalculator,
        GWASResult,
        run_association_test,
        correct_gwas_results
    )
except ImportError:
    AssociationTester = None
    MultipleTestingCorrection = None
    GWASAnalyzer = None
    LDAnalyzer = None
    PRSCalculator = None
    GWASResult = None
    run_association_test = None
    correct_gwas_results = None

# Database module (optional)
try:
    from .database import (
        GenomicsDatabase,
        VariantRecord,
        GeneRecord,
        EnsemblAPI,
        MyVariantAPI,
        NCBIVariationAPI,
        annotate_variant,
        get_variant_frequency,
        check_pathogenicity
    )
except ImportError:
    GenomicsDatabase = None
    VariantRecord = None
    GeneRecord = None
    EnsemblAPI = None
    MyVariantAPI = None
    NCBIVariationAPI = None
    annotate_variant = None
    get_variant_frequency = None
    check_pathogenicity = None

__all__ = [
    # VCF
    'VCFParser',
    'Variant',
    # Variant analysis
    'VariantFilter',
    'VariantAnnotator',
    'VariantStatistics',
    'VariantPrioritizer',
    'VariantAnnotation',
    'filter_variants',
    'annotate_variants',
    'find_deleterious_variants',
    # GWAS
    'AssociationTester',
    'MultipleTestingCorrection',
    'GWASAnalyzer',
    'LDAnalyzer',
    'PRSCalculator',
    'GWASResult',
    'run_association_test',
    'correct_gwas_results',
    # Database
    'GenomicsDatabase',
    'VariantRecord',
    'GeneRecord',
    'EnsemblAPI',
    'MyVariantAPI',
    'NCBIVariationAPI',
    'annotate_variant',
    'get_variant_frequency',
    'check_pathogenicity',
]
