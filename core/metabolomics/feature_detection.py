"""
特征检测模块 - Feature Detection

功能：
1. 峰检测（基于色谱图）
2. 峰对齐（多样本）
3. 特征矩阵构建
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Peak:
    """色谱峰"""
    rt: float  # 保留时间（分钟）
    rt_start: float  # 峰开始时间
    rt_end: float  # 峰结束时间
    intensity: float  # 峰强度（面积）
    height: float  # 峰高
    width: float  # 峰宽（分钟）
    mz: Optional[float] = None  # 质荷比（用于XIC）
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'rt': self.rt,
            'rt_start': self.rt_start,
            'rt_end': self.rt_end,
            'intensity': self.intensity,
            'height': self.height,
            'width': self.width,
            'mz': self.mz
        }


@dataclass
class Feature:
    """代谢特征（跨样本）"""
    feature_id: str
    mz: float
    rt: float
    intensity_matrix: np.ndarray  # 样本 x 强度
    sample_names: List[str]
    
    @property
    def mean_intensity(self) -> float:
        return np.mean(self.intensity_matrix)
    
    @property
    def cv(self) -> float:
        """变异系数"""
        if self.mean_intensity == 0:
            return 0
        return np.std(self.intensity_matrix) / self.mean_intensity


class FeatureDetector:
    """
    特征检测器
    
    从色谱图中检测峰并构建特征矩阵。
    """
    
    def __init__(
        self,
        min_peak_height: float = 1000,
        min_peak_width: float = 0.05,  # 分钟
        max_peak_width: float = 2.0,   # 分钟
        noise_threshold: float = 3.0
    ):
        self.min_peak_height = min_peak_height
        self.min_peak_width = min_peak_width
        self.max_peak_width = max_peak_width
        self.noise_threshold = noise_threshold
        
        logger.info("FeatureDetector initialized")
    
    def detect_peaks(
        self,
        time: np.ndarray,
        intensity: np.ndarray,
        mz: Optional[float] = None
    ) -> List[Peak]:
        """
        从色谱图中检测峰
        
        Args:
            time: 时间数组（分钟）
            intensity: 强度数组
            mz: 提取的m/z（可选）
            
        Returns:
            List[Peak]: 检测到的峰列表
        """
        from scipy.ndimage import gaussian_filter1d
        from scipy import signal
        
        # 平滑处理
        smoothed = gaussian_filter1d(intensity, sigma=2)
        
        # 估计基线噪声
        noise_level = self._estimate_noise(smoothed)
        
        # 峰检测参数
        min_height = max(self.min_peak_height, noise_level * self.noise_threshold)
        min_width_points = max(3, int(self.min_peak_width / np.mean(np.diff(time))))
        
        # 寻找峰
        peaks, properties = signal.find_peaks(
            smoothed,
            height=min_height,
            width=min_width_points,
            prominence=noise_level * 2
        )
        
        detected_peaks = []
        
        for i, peak_idx in enumerate(peaks):
            # 获取峰边界
            left_idx = int(properties['left_ips'][i])
            right_idx = int(properties['right_ips'][i])
            
            # 转换为时间
            rt = time[peak_idx]
            rt_start = time[max(0, left_idx)]
            rt_end = time[min(len(time)-1, right_idx)]
            
            # 计算峰面积
            peak_mask = (time >= rt_start) & (time <= rt_end)
            peak_area = np.trapz(intensity[peak_mask], time[peak_mask])
            
            # 峰宽检查
            width = rt_end - rt_start
            if width < self.min_peak_width or width > self.max_peak_width:
                continue
            
            peak = Peak(
                rt=rt,
                rt_start=rt_start,
                rt_end=rt_end,
                intensity=peak_area,
                height=smoothed[peak_idx],
                width=width,
                mz=mz
            )
            
            detected_peaks.append(peak)
        
        logger.info(f"Detected {len(detected_peaks)} peaks")
        return detected_peaks
    
    def build_feature_matrix(
        self,
        samples_data: Dict[str, List[Peak]],
        rt_tolerance: float = 0.2,  # 分钟
        mz_tolerance: float = 0.01  # Da
    ) -> List[Feature]:
        """
        构建特征矩阵（跨样本对齐）
        
        Args:
            samples_data: {样本名: 峰列表}
            rt_tolerance: RT容差
            mz_tolerance: m/z容差
            
        Returns:
            List[Feature]: 特征列表
        """
        sample_names = list(samples_data.keys())
        n_samples = len(sample_names)
        
        # 收集所有峰
        all_peaks = []
        for sample_name, peaks in samples_data.items():
            for peak in peaks:
                all_peaks.append((sample_name, peak))
        
        # 按RT排序
        all_peaks.sort(key=lambda x: x[1].rt)
        
        # 聚类对齐
        features = []
        feature_id = 0
        
        while all_peaks:
            # 取第一个峰作为种子
            seed_sample, seed_peak = all_peaks[0]
            
            # 找到所有匹配的峰
            cluster = []
            remaining = []
            
            for sample_name, peak in all_peaks:
                # RT匹配
                rt_match = abs(peak.rt - seed_peak.rt) <= rt_tolerance
                
                # m/z匹配（如果有）
                mz_match = True
                if seed_peak.mz is not None and peak.mz is not None:
                    mz_match = abs(peak.mz - seed_peak.mz) <= mz_tolerance
                
                if rt_match and mz_match:
                    cluster.append((sample_name, peak))
                else:
                    remaining.append((sample_name, peak))
            
            # 创建特征
            if len(cluster) >= max(1, n_samples * 0.5):  # 至少在50%样本中出现
                intensity_matrix = np.zeros(n_samples)
                
                for sample_name, peak in cluster:
                    idx = sample_names.index(sample_name)
                    intensity_matrix[idx] = peak.intensity
                
                feature = Feature(
                    feature_id=f"F{feature_id:05d}",
                    mz=seed_peak.mz or 0,
                    rt=seed_peak.rt,
                    intensity_matrix=intensity_matrix,
                    sample_names=sample_names
                )
                
                features.append(feature)
                feature_id += 1
            
            all_peaks = remaining
        
        logger.info(f"Built feature matrix: {len(features)} features")
        return features
    
    def _estimate_noise(self, intensity: np.ndarray) -> float:
        """估计噪声水平（使用较低百分位数）"""
        return np.percentile(intensity, 10)
    
    def filter_features(
        self,
        features: List[Feature],
        min_samples: int = 3,
        max_cv: float = 0.5,
        blank_ratio: Optional[float] = None
    ) -> List[Feature]:
        """
        过滤特征
        
        Args:
            features: 特征列表
            min_samples: 最小样本数
            max_cv: 最大变异系数
            blank_ratio: 空白样本比例阈值
            
        Returns:
            List[Feature]: 过滤后的特征
        """
        filtered = []
        
        for feature in features:
            # 检查样本数
            n_detected = np.sum(feature.intensity_matrix > 0)
            if n_detected < min_samples:
                continue
            
            # 检查变异系数
            if feature.cv > max_cv:
                continue
            
            filtered.append(feature)
        
        logger.info(f"Filtered features: {len(features)} -> {len(filtered)}")
        return filtered


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # 测试峰检测
    print("=== 测试特征检测 ===")
    
    # 生成模拟色谱图
    time = np.linspace(0, 30, 3000)  # 30分钟，每秒10个点
    
    # 添加3个峰
    intensity = np.zeros_like(time)
    intensity += 1000 * np.exp(-((time - 5) / 0.3) ** 2)  # 峰1
    intensity += 2000 * np.exp(-((time - 12) / 0.5) ** 2)  # 峰2
    intensity += 1500 * np.exp(-((time - 20) / 0.4) ** 2)  # 峰3
    intensity += np.random.normal(0, 50, len(time))  # 噪声
    
    detector = FeatureDetector()
    peaks = detector.detect_peaks(time, intensity)
    
    print(f"\n检测到 {len(peaks)} 个峰:")
    for peak in peaks:
        print(f"  RT: {peak.rt:.2f} min, 面积: {peak.intensity:.2e}, 高度: {peak.height:.2e}")
