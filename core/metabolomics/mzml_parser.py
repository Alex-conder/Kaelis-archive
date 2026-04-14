"""
mzML 文件解析器 - MZML Parser

支持解析 mzML 格式的质谱数据文件，提取色谱图和质谱图信息。
"""

import gzip
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Spectrum:
    """质谱数据点"""
    mz: np.ndarray  # 质荷比
    intensity: np.ndarray  # 强度
    rt: float  # 保留时间（分钟）
    ms_level: int  # MS 级别（1 或 2）
    id: str  # 谱图 ID
    polarity: str = "positive"  # 离子模式
    
    @property
    def tic(self) -> float:
        """总离子流"""
        return np.sum(self.intensity)
    
    @property
    def base_peak(self) -> Tuple[float, float]:
        """基峰 (mz, intensity)"""
        idx = np.argmax(self.intensity)
        return self.mz[idx], self.intensity[idx]


@dataclass
class Chromatogram:
    """色谱图数据"""
    time: np.ndarray  # 时间（分钟）
    intensity: np.ndarray  # 强度
    mz: Optional[float] = None  # 提取的 m/z（如果是提取离子流）
    chromatogram_type: str = "tic"  # tic, xic, bpc


class MZMLParser:
    """
    mzML 文件解析器
    
    支持直接解析和迭代解析大文件。
    """
    
    # mzML 命名空间
    NAMESPACES = {
        'mzml': 'http://psi.hupo.org/ms/mzml',
        'cv': 'http://psi.hupo.org/ms/mzml'
    }
    
    def __init__(self, filepath: Union[str, Path]):
        self.filepath = Path(filepath)
        self.file_size = self.filepath.stat().st_size
        self.spectrum_count = 0
        self.chromatogram_count = 0
        
        logger.info(f"MZML Parser initialized: {self.filepath}")
    
    def parse(self, max_spectra: Optional[int] = None) -> Iterator[Spectrum]:
        """
        解析 mzML 文件
        
        Args:
            max_spectra: 最大解析谱图数（用于测试）
            
        Yields:
            Spectrum: 质谱数据对象
        """
        logger.info(f"Starting to parse {self.filepath}")
        
        # 检查是否是 gz 压缩文件
        open_func = gzip.open if str(self.filepath).endswith('.gz') else open
        
        try:
            with open_func(self.filepath, 'rb') as f:
                # 使用迭代解析处理大文件
                context = ET.iterparse(f, events=('start', 'end'))
                context = iter(context)
                event, root = next(context)
                
                spectrum_count = 0
                current_spectrum = None
                current_binary_data = {}
                
                for event, elem in context:
                    tag = self._strip_namespace(elem.tag)
                    
                    if event == 'start':
                        if tag == 'spectrum':
                            current_spectrum = self._parse_spectrum_header(elem)
                            current_binary_data = {}
                    
                    elif event == 'end':
                        if tag == 'binaryDataArray':
                            data = self._parse_binary_data(elem)
                            if data:
                                current_binary_data[data['type']] = data['array']
                        
                        elif tag == 'spectrum':
                            if current_spectrum and current_binary_data:
                                spectrum = self._create_spectrum(
                                    current_spectrum, 
                                    current_binary_data
                                )
                                if spectrum:
                                    spectrum_count += 1
                                    yield spectrum
                                    
                                    if max_spectra and spectrum_count >= max_spectra:
                                        logger.info(f"Reached max_spectra: {max_spectra}")
                                        break
                            
                            # 清理元素释放内存
                            elem.clear()
                            root.clear()
                
                logger.info(f"Parsed {spectrum_count} spectra")
                
        except Exception as e:
            logger.error(f"Failed to parse mzML: {e}")
            raise
    
    def get_tic_chromatogram(self) -> Chromatogram:
        """
        提取总离子流色谱图 (TIC)
        
        Returns:
            Chromatogram: TIC 色谱图
        """
        times = []
        intensities = []
        
        for spectrum in self.parse():
            if spectrum.ms_level == 1:  # 只取 MS1
                times.append(spectrum.rt)
                intensities.append(spectrum.tic)
        
        return Chromatogram(
            time=np.array(times),
            intensity=np.array(intensities),
            chromatogram_type="tic"
        )
    
    def get_bpc_chromatogram(self) -> Chromatogram:
        """
        提取基峰离子流色谱图 (BPC)
        
        Returns:
            Chromatogram: BPC 色谱图
        """
        times = []
        intensities = []
        
        for spectrum in self.parse():
            if spectrum.ms_level == 1:
                times.append(spectrum.rt)
                _, bp_intensity = spectrum.base_peak
                intensities.append(bp_intensity)
        
        return Chromatogram(
            time=np.array(times),
            intensity=np.array(intensities),
            chromatogram_type="bpc"
        )
    
    def get_xic_chromatogram(self, mz: float, tolerance: float = 0.01) -> Chromatogram:
        """
        提取离子流色谱图 (XIC)
        
        Args:
            mz: 目标 m/z
            tolerance: m/z 容差（Da）
            
        Returns:
            Chromatogram: XIC 色谱图
        """
        times = []
        intensities = []
        
        for spectrum in self.parse():
            if spectrum.ms_level == 1:
                # 在容差范围内查找离子
                mask = np.abs(spectrum.mz - mz) <= tolerance
                if np.any(mask):
                    times.append(spectrum.rt)
                    intensities.append(np.sum(spectrum.intensity[mask]))
        
        return Chromatogram(
            time=np.array(times),
            intensity=np.array(intensities),
            mz=mz,
            chromatogram_type="xic"
        )
    
    def get_ms1_spectra_count(self) -> int:
        """获取 MS1 谱图数量"""
        count = 0
        for spectrum in self.parse():
            if spectrum.ms_level == 1:
                count += 1
        return count
    
    def get_file_info(self) -> Dict[str, Any]:
        """获取文件基本信息"""
        # 解析文件获取基本信息
        info = {
            "filepath": str(self.filepath),
            "file_size_mb": round(self.file_size / (1024 * 1024), 2),
            "ms1_count": 0,
            "ms2_count": 0,
            "rt_start": float('inf'),
            "rt_end": 0,
            "mz_range": [float('inf'), 0]
        }
        
        for spectrum in self.parse():
            if spectrum.ms_level == 1:
                info["ms1_count"] += 1
            else:
                info["ms2_count"] += 1
            
            info["rt_start"] = min(info["rt_start"], spectrum.rt)
            info["rt_end"] = max(info["rt_end"], spectrum.rt)
            
            if len(spectrum.mz) > 0:
                info["mz_range"][0] = min(info["mz_range"][0], np.min(spectrum.mz))
                info["mz_range"][1] = max(info["mz_range"][1], np.max(spectrum.mz))
        
        return info
    
    def _strip_namespace(self, tag: str) -> str:
        """移除 XML 命名空间"""
        if '}' in tag:
            return tag.split('}', 1)[1]
        return tag
    
    def _parse_spectrum_header(self, elem: ET.Element) -> Dict[str, Any]:
        """解析谱图头部信息"""
        spectrum_info = {
            'id': elem.get('id', ''),
            'index': int(elem.get('index', 0)),
            'ms_level': 1,
            'rt': 0.0,
            'polarity': 'positive'
        }
        
        # 解析 cvParam
        for cv_param in elem.findall('.//cvParam'):
            accession = cv_param.get('accession', '')
            value = cv_param.get('value', '')
            
            # MS 级别
            if accession == 'MS:1000511':  # ms level
                spectrum_info['ms_level'] = int(value)
            
            # 保留时间
            elif accession in ['MS:1000016', 'MS:1000894']:  # scan start time
                try:
                    spectrum_info['rt'] = float(value)
                except:
                    pass
            
            # 极性
            elif accession == 'MS:1000129':  # positive scan
                spectrum_info['polarity'] = 'positive'
            elif accession == 'MS:1000130':  # negative scan
                spectrum_info['polarity'] = 'negative'
        
        return spectrum_info
    
    def _parse_binary_data(self, elem: ET.Element) -> Optional[Dict[str, Any]]:
        """解析二进制数据数组"""
        array_type = None
        precision = 32
        compression = None
        data = None
        
        # 查找 cvParam 确定数据类型
        for cv_param in elem.findall('.//cvParam'):
            accession = cv_param.get('accession', '')
            
            if accession == 'MS:1000514':  # m/z array
                array_type = 'mz'
            elif accession == 'MS:1000515':  # intensity array
                array_type = 'intensity'
            elif accession == 'MS:1000521':  # 32-bit float
                precision = 32
            elif accession == 'MS:1000523':  # 64-bit float
                precision = 64
            elif accession == 'MS:1000574':  # zlib compression
                compression = 'zlib'
            elif accession == 'MS:1000576':  # no compression
                compression = None
        
        # 解析二进制数据
        binary_elem = elem.find('.//binary')
        if binary_elem is not None and binary_elem.text and array_type:
            import base64
            
            try:
                # Base64 解码
                raw_data = base64.b64decode(binary_elem.text)
                
                # 解压（如果需要）
                if compression == 'zlib':
                    import zlib
                    raw_data = zlib.decompress(raw_data)
                
                # 转换为 numpy 数组
                dtype = np.float32 if precision == 32 else np.float64
                array = np.frombuffer(raw_data, dtype=dtype)
                
                return {
                    'type': array_type,
                    'array': array
                }
                
            except Exception as e:
                logger.warning(f"Failed to parse binary data: {e}")
                return None
        
        return None
    
    def _create_spectrum(
        self, 
        header: Dict[str, Any], 
        binary_data: Dict[str, np.ndarray]
    ) -> Optional[Spectrum]:
        """创建 Spectrum 对象"""
        if 'mz' not in binary_data or 'intensity' not in binary_data:
            return None
        
        mz = binary_data['mz']
        intensity = binary_data['intensity']
        
        # 确保长度一致
        min_len = min(len(mz), len(intensity))
        if min_len == 0:
            return None
        
        return Spectrum(
            mz=mz[:min_len],
            intensity=intensity[:min_len],
            rt=header['rt'],
            ms_level=header['ms_level'],
            id=header['id'],
            polarity=header['polarity']
        )


# 便捷函数
def parse_mzml(filepath: str, max_spectra: Optional[int] = None) -> Iterator[Spectrum]:
    """便捷函数：解析 mzML 文件"""
    parser = MZMLParser(filepath)
    return parser.parse(max_spectra)


def get_file_summary(filepath: str) -> Dict[str, Any]:
    """便捷函数：获取文件摘要"""
    parser = MZMLParser(filepath)
    return parser.get_file_info()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # 测试解析
    test_file = r"D:\1250205_NEG_B44 (4).mzML"
    
    print("=== 测试 mzML 解析器 ===")
    print(f"文件: {test_file}")
    
    try:
        parser = MZMLParser(test_file)
        
        # 获取文件信息（只解析前10个谱图）
        print("\n解析前10个谱图...")
        spectra = list(parser.parse(max_spectra=10))
        
        print(f"成功解析 {len(spectra)} 个谱图")
        
        for i, spec in enumerate(spectra[:3]):
            print(f"\n谱图 {i+1}:")
            print(f"  ID: {spec.id[:50]}...")
            print(f"  MS级别: {spec.ms_level}")
            print(f"  保留时间: {spec.rt:.2f} min")
            print(f"  数据点: {len(spec.mz)}")
            print(f"  总离子流: {spec.tic:.2e}")
            print(f"  基峰: m/z {spec.base_peak[0]:.4f}, intensity {spec.base_peak[1]:.2e}")
        
    except Exception as e:
        print(f"错误: {e}")
