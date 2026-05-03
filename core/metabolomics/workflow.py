"""
代谢组学工作流 - Metabolomics Workflow

集成自进化引擎，自动优化分析参数。
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import numpy as np

# 代谢组学子模块采用延迟导入，避免 scipy/matplotlib 等重型库在启动时阻塞

def _import_mzml_parser():
    try:
        from core.metabolomics.mzml_parser import MZMLParser, get_file_summary
        return MZMLParser, get_file_summary
    except ImportError:
        from .mzml_parser import MZMLParser, get_file_summary
        return MZMLParser, get_file_summary

def _import_feature_detection():
    try:
        from core.metabolomics.feature_detection import FeatureDetector
        return FeatureDetector
    except ImportError:
        from .feature_detection import FeatureDetector
        return FeatureDetector

def _import_statistical_analysis():
    try:
        from core.metabolomics.statistical_analysis import MetabolomicsAnalyzer, DifferentialMetabolite
        return MetabolomicsAnalyzer, DifferentialMetabolite
    except ImportError:
        from .statistical_analysis import MetabolomicsAnalyzer, DifferentialMetabolite
        return MetabolomicsAnalyzer, DifferentialMetabolite

def _import_visualization():
    try:
        from core.metabolomics.visualization import MetabolomicsVisualizer
        return MetabolomicsVisualizer
    except ImportError:
        from .visualization import MetabolomicsVisualizer
        return MetabolomicsVisualizer

# 导入自进化引擎
try:
    from core.self_evolving import SelfEvolvingEngine, TaskExpectation
    EVOLUTION_AVAILABLE = True
except ImportError:
    EVOLUTION_AVAILABLE = False

logger = logging.getLogger(__name__)


class MetabolomicsWorkflow:
    """
    代谢组学分析工作流
    
    支持自进化优化的完整代谢组学分析流程。
    """
    
    def __init__(
        self,
        use_evolution: bool = True,
        min_peak_height: float = 1000,
        rt_tolerance: float = 0.2,
        mz_tolerance: float = 0.01
    ):
        self.parser = None
        self.detector = None
        self.analyzer = None
        self.visualizer = None
        self._min_peak_height = min_peak_height
        
        self.rt_tolerance = rt_tolerance
        self.mz_tolerance = mz_tolerance
        self.use_evolution = use_evolution and EVOLUTION_AVAILABLE
        
        # 结果存储
        self.results = {}
        
        logger.info(f"MetabolomicsWorkflow initialized (evolution={self.use_evolution})")
    
    def _ensure_detector(self):
        if self.detector is None:
            FeatureDetector = _import_feature_detection()
            self.detector = FeatureDetector(min_peak_height=self._min_peak_height)
        return self.detector
    
    def _ensure_analyzer(self):
        if self.analyzer is None:
            MetabolomicsAnalyzer, _ = _import_statistical_analysis()
            self.analyzer = MetabolomicsAnalyzer()
        return self.analyzer
    
    def _ensure_visualizer(self):
        if self.visualizer is None:
            MetabolomicsVisualizer = _import_visualization()
            self.visualizer = MetabolomicsVisualizer()
        return self.visualizer
    
    def analyze_file(
        self,
        filepath: str,
        sample_name: Optional[str] = None,
        detect_peaks: bool = True,
        max_spectra: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        分析单个mzML文件
        
        Args:
            filepath: mzML文件路径
            sample_name: 样本名称
            detect_peaks: 是否检测峰
            max_spectra: 最大解析谱图数
            
        Returns:
            Dict: 分析结果
        """
        sample_name = sample_name or Path(filepath).stem
        
        logger.info(f"Analyzing file: {filepath}")
        
        # 解析文件
        MZMLParser, _ = _import_mzml_parser()
        self.parser = MZMLParser(filepath)
        
        # 获取文件信息
        file_info = self.parser.get_file_info()
        
        # 提取色谱图
        tic = self.parser.get_tic_chromatogram()
        bpc = self.parser.get_bpc_chromatogram()
        
        result = {
            'sample_name': sample_name,
            'file_info': file_info,
            'tic': tic,
            'bpc': bpc,
            'peaks': []
        }
        
        # 峰检测
        if detect_peaks:
            peaks = self._ensure_detector().detect_peaks(tic.time, tic.intensity)
            result['peaks'] = [p.to_dict() for p in peaks]
            
            # 可视化
            result['chromatogram_plot'] = self._ensure_visualizer().plot_chromatogram(
                tic.time, tic.intensity, peaks=[p.to_dict() for p in peaks[:20]],
                title=f"TIC - {sample_name}"
            )
        
        self.results[sample_name] = result
        
        return result
    
    def compare_groups(
        self,
        feature_matrix: np.ndarray,
        feature_ids: List[str],
        group_labels: np.ndarray,
        group_names: List[str],
        mz_values: List[float],
        rt_values: List[float],
        use_self_evolution: bool = True
    ) -> Dict[str, Any]:
        """
        组间比较分析
        
        Args:
            feature_matrix: 特征矩阵 (n_samples, n_features)
            feature_ids: 特征ID列表
            group_labels: 分组标签
            group_names: 组名
            mz_values: m/z值
            rt_values: RT值
            use_self_evolution: 使用自进化优化参数
            
        Returns:
            Dict: 分析结果
        """
        logger.info(f"Comparing groups: {group_names}")
        
        results = {
            'group_names': group_names,
            'n_samples': len(group_labels),
            'n_features': len(feature_ids)
        }
        
        # PCA分析
        logger.info("Running PCA...")
        pca_result = self.analyzer.pca(feature_matrix, n_components=2)
        
        results['pca'] = {
            'r2x': pca_result.r2x,
            'explained_variance': pca_result.explained_variance_ratio.tolist(),
            'scores': pca_result.scores.tolist(),
            'plot': self.visualizer.plot_score(
                pca_result.scores, group_labels, group_names,
                explained_var=pca_result.explained_variance_ratio,
                title="PCA Score Plot"
            )
        }
        
        # PLS-DA分析（使用自进化优化）
        logger.info("Running PLS-DA...")
        
        if use_self_evolution and self.use_evolution:
            pls_result = self._optimize_plsda(feature_matrix, group_labels)
        else:
            pls_result = self.analyzer.pls_da(feature_matrix, group_labels, n_components=2)
        
        results['plsda'] = {
            'r2x': pls_result.r2x,
            'r2y': pls_result.r2y,
            'q2': pls_result.q2,
            'vip_scores': pls_result.vip_scores.tolist(),
            'scores': pls_result.scores.tolist(),
            'plot': self.visualizer.plot_score(
                pls_result.scores, group_labels, group_names,
                title=f"PLS-DA Score Plot (Q2={pls_result.q2:.3f})"
            ),
            'loading_plot': self.visualizer.plot_loading(
                pls_result.loadings, feature_ids[:20],
                title="PLS-DA Loading Plot"
            )
        }
        
        # 差异代谢物分析
        logger.info("Finding differential metabolites...")
        diff_mets = self.analyzer.find_differential_metabolites(
            feature_matrix, feature_ids, group_labels,
            mz_values=mz_values, rt_values=rt_values
        )
        
        significant = [dm for dm in diff_mets if dm.is_significant]
        
        # 火山图
        log2fc = np.array([dm.log2fc for dm in diff_mets])
        p_values = np.array([dm.p_value for dm in diff_mets])
        
        results['differential'] = {
            'total': len(diff_mets),
            'significant': len(significant),
            'up_regulated': len([dm for dm in significant if dm.fold_change > 1]),
            'down_regulated': len([dm for dm in significant if dm.fold_change < 1]),
            'metabolites': [dm.to_dict() for dm in significant[:50]],
            'volcano_plot': self.visualizer.plot_volcano(
                log2fc, p_values, 
                feature_names=[dm.feature_id for dm in diff_mets],
                title="Volcano Plot"
            )
        }
        
        # 置换检验
        logger.info("Running permutation test...")
        perm_result = self.analyzer.permutation_test(
            feature_matrix, group_labels, n_permutations=100
        )
        results['permutation'] = perm_result
        
        logger.info(f"Analysis complete: {len(significant)} significant metabolites found")
        
        return results
    
    def _optimize_plsda(
        self,
        X: np.ndarray,
        y: np.ndarray
    ):
        """
        使用自进化引擎优化PLS-DA参数
        """
        if not EVOLUTION_AVAILABLE:
            return self.analyzer.pls_da(X, y)
        
        logger.info("Using Self-Evolving Engine to optimize PLS-DA parameters")
        
        engine = SelfEvolvingEngine()
        
        # 定义执行函数
        def run_plsda(params):
            try:
                n_components = int(params.get('n_components', 2))
                scale = params.get('scale', True)
                
                result = self.analyzer.pls_da(X, y, n_components=n_components, scale=scale)
                
                return {
                    'Q2': result.q2,
                    'R2Y': result.r2y,
                    'R2X': result.r2x
                }
            except Exception as e:
                return {'Q2': 0, 'R2Y': 0, 'R2X': 0}
        
        # 定义预期
        expectation = TaskExpectation(
            criteria="Q2 > 0.5 and R2Y > 0.7",
            evaluation_method="rule",
            target_confidence=0.8,
            max_iterations=5
        )
        
        # 执行进化
        record = engine.evolve(
            execution_id=f"plsda_opt_{id(X)}",
            task_type="metabolomics_pls_da",
            initial_params={'n_components': 2, 'scale': True},
            expectation=expectation,
            execution_func=run_plsda
        )
        
        logger.info(f"Optimization complete: Q2={record.best_result.get('Q2', 0):.3f}")
        
        # 使用最优参数运行最终分析
        return self.analyzer.pls_da(
            X, y, 
            n_components=int(record.best_params.get('n_components', 2)),
            scale=record.best_params.get('scale', True)
        )
    
    def export_results(self, output_dir: str):
        """
        导出分析结果
        
        Args:
            output_dir: 输出目录
        """
        import json
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 保存结果（排除图片数据）
        export_data = {}
        for key, value in self.results.items():
            export_data[key] = {
                k: v for k, v in value.items() 
                if not k.endswith('_plot')
            }
        
        with open(output_path / 'results.json', 'w') as f:
            json.dump(export_data, f, indent=2)
        
        logger.info(f"Results exported to {output_path}")


# 便捷函数
def quick_analyze(
    filepath: str,
    group_labels: Optional[np.ndarray] = None,
    use_evolution: bool = True
) -> Dict[str, Any]:
    """
    快速分析mzML文件
    
    Args:
        filepath: mzML文件路径
        group_labels: 分组标签（用于比较）
        use_evolution: 使用自进化
        
    Returns:
        Dict: 分析结果
    """
    workflow = MetabolomicsWorkflow(use_evolution=use_evolution)
    
    # 基础分析
    result = workflow.analyze_file(filepath)
    
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("=== 测试代谢组学工作流 ===")
    
    # 测试文件路径
    test_file = r"D:\1250205_NEG_B44 (4).mzML"
    
    if not Path(test_file).exists():
        print(f"❌ 测试文件不存在: {test_file}")
        exit(0)
    
    print(f"\n分析文件: {test_file}")
    
    workflow = MetabolomicsWorkflow(use_evolution=False)
    
    # 分析（只解析前100个谱图，用于测试）
    result = workflow.analyze_file(test_file, max_spectra=100)
    
    print("\n分析结果:")
    print(f"  样本名称: {result['sample_name']}")
    print(f"  文件大小: {result['file_info']['file_size_mb']} MB")
    print(f"  MS1谱图: {result['file_info']['ms1_count']}")
    print(f"  保留时间范围: {result['file_info']['rt_start']:.2f} - {result['file_info']['rt_end']:.2f} min")
    print(f"  m/z范围: {result['file_info']['mz_range'][0]:.2f} - {result['file_info']['mz_range'][1]:.2f}")
    print(f"  检测到的峰: {len(result['peaks'])}")
    
    if result['peaks']:
        print("\n  前5个峰:")
        for peak in result['peaks'][:5]:
            print(f"    RT: {peak['rt']:.2f} min, 面积: {peak['intensity']:.2e}")
    
    print("\n✅ 分析完成!")
