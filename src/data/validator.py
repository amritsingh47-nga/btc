"""
数据质量验证模块
检测和处理异常K线数据
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from src.utils.logger import log


class DataValidator:
    """数据质量验证器 - 专为合约市场设计"""
    
    # 配置参数 - 使用更稳健的方法
    MAD_THRESHOLD = 5.0  # MAD (Median Absolute Deviation) 阈值
    RETURNS_THRESHOLD = 0.15  # 单根K线涨跌幅阈值（15%）
    HL_RANGE_THRESHOLD = 0.20  # High-Low 相对 Close 的比例阈值（20%）
    NEIGHBOR_WINDOW = 5  # 邻近窗口大小（增大以提高稳健性）
    MAX_PRICE = 1e7  # 最大合理价格
    MIN_PRICE = 0.01  # 最小合理价格
    
    def __init__(self):
        # 详细的异常统计
        self.raw_anomaly_count = 0  # 原始检测到的异常数
        self.cleaned_anomaly_count = 0  # 清洗后剩余的异常数
        self.clipped_count = 0  # 被 clip 的点数
        self.dropped_count = 0  # 被删除的K线数
        self.anomaly_details: List[Dict] = []
    
    def validate_and_clean_klines(
        self, 
        klines: List[Dict],
        symbol: str,
        action: str = 'clip'  # 'clip', 'drop', 'none'
    ) -> Tuple[List[Dict], Dict]:
        """
        验证并清洗K线数据 - 专为合约市场优化
        
        Args:
            klines: 原始K线数据
            symbol: 交易对
            action: 处理异常的方式
                - 'clip': clip 到邻近最大/最小值（推荐，不制造虚假路径）
                - 'drop': 删除异常K线（超阈值时）
                - 'none': 仅检测不处理
        
        Returns:
            (清洗后的K线, 详细验证报告)
        """
        if not klines or len(klines) < 5:
            log.warning(f"[{symbol}] K线数据不足，无法验证（需至少5根）")
            return klines, {'status': 'insufficient_data', 'anomalies': []}
        
        # 转换为DataFrame便于处理
        df = pd.DataFrame(klines)
        n_original = len(df)
        
        # 1. 基础合理性检查
        basic_issues = self._check_basic_sanity(df, symbol)
        
        # 2. 异常值检测（使用 MAD + Returns）
        anomalies = self._detect_anomalies_robust(df, symbol)
        self.raw_anomaly_count = len(anomalies)
        
        # 3. 处理异常
        if anomalies:
            log.warning(f"[{symbol}] 检测到 {len(anomalies)} 个异常K线")
            df_cleaned = self._handle_anomalies_safe(df, anomalies, action, symbol)
        else:
            df_cleaned = df
        
        # 4. 再次检测（验证清洗效果）
        remaining_anomalies = self._detect_anomalies_robust(df_cleaned, symbol)
        self.cleaned_anomaly_count = len(remaining_anomalies)
        
        # 5. 生成详细验证报告
        report = {
            'status': 'cleaned' if anomalies else 'clean',
            'n_original': n_original,
            'n_cleaned': len(df_cleaned),
            'raw_anomaly_count': len(anomalies),  # 原始检测数
            'cleaned_anomaly_count': len(remaining_anomalies),  # 清洗后剩余数
            'clipped_count': self.clipped_count,
            'dropped_count': self.dropped_count,
            'anomalies': anomalies,
            'remaining_anomalies': remaining_anomalies,
            'basic_issues': basic_issues,
            'action_taken': action if anomalies else 'none',
            'method': 'MAD + Returns-based'  # 明确检测方法
        }
        
        # 6. 转换回字典列表
        cleaned_klines = df_cleaned.to_dict('records')
        
        # 记录到类变量
        self.anomaly_details.extend(anomalies)
        
        # 详细日志记录
        if anomalies:
            log.warning(
                f"[{symbol}] 数据清洗报告: "
                f"原始={n_original}, 清洗后={len(df_cleaned)}, "
                f"原始异常={len(anomalies)}, 清洗后异常={len(remaining_anomalies)}, "
                f"处理方式={action}, "
                f"clipped={self.clipped_count}, dropped={self.dropped_count}"
            )
            for anomaly in anomalies[:3]:  # 只显示前3个
                log.warning(f"  异常详情: {anomaly}")
            
            if remaining_anomalies:
                log.warning(f"  ⚠️ 警告: 清洗后仍有 {len(remaining_anomalies)} 个异常未完全修复")
        
        return cleaned_klines, report
    
    def _check_basic_sanity(self, df: pd.DataFrame, symbol: str) -> List[str]:
        """基础合理性检查"""
        issues = []
        
        # 检查必要字段
        required_fields = ['open', 'high', 'low', 'close', 'volume']
        missing_fields = [f for f in required_fields if f not in df.columns]
        if missing_fields:
            issues.append(f"缺失字段: {missing_fields}")
        
        # 检查价格范围
        for field in ['open', 'high', 'low', 'close']:
            if field in df.columns:
                if (df[field] < self.MIN_PRICE).any():
                    count = (df[field] < self.MIN_PRICE).sum()
                    issues.append(f"{field} 存在 {count} 个过低值（< {self.MIN_PRICE}）")
                if (df[field] > self.MAX_PRICE).any():
                    count = (df[field] > self.MAX_PRICE).sum()
                    issues.append(f"{field} 存在 {count} 个过高值（> {self.MAX_PRICE}）")
        
        # 检查 OHLC 逻辑关系
        if all(f in df.columns for f in ['open', 'high', 'low', 'close']):
            invalid_ohlc = (
                (df['high'] < df['low']) |
                (df['high'] < df['open']) |
                (df['high'] < df['close']) |
                (df['low'] > df['open']) |
                (df['low'] > df['close'])
            )
            if invalid_ohlc.any():
                count = invalid_ohlc.sum()
                issues.append(f"存在 {count} 个违反OHLC逻辑的K线")
        
        # 检查成交量
        if 'volume' in df.columns:
            if (df['volume'] < 0).any():
                count = (df['volume'] < 0).sum()
                issues.append(f"存在 {count} 个负成交量")
        
        return issues
    
    def _detect_anomalies_robust(self, df: pd.DataFrame, symbol: str) -> List[Dict]:
        """
        使用更稳健的方法检测异常K线
        
        方法组合：
        1. MAD (Median Absolute Deviation) - 比 Z-score 更稳健
        2. Returns-based filter - 检测异常涨跌幅
        3. High-Low 相对 Close 的比例 - 检测异常波动
        """
        anomalies = []
        
        # 计算收益率（用于检测异常跳跃）
        if 'close' in df.columns:
            df['returns'] = df['close'].pct_change()
        
        for i in range(len(df)):
            # 获取邻近窗口（更大的窗口提高稳健性）
            start_idx = max(0, i - self.NEIGHBOR_WINDOW)
            end_idx = min(len(df), i + self.NEIGHBOR_WINDOW + 1)
            
            # 排除当前行
            neighbor_indices = [j for j in range(start_idx, end_idx) if j != i]
            
            if len(neighbor_indices) < 3:
                continue  # 窗口太小，跳过
            
            current = df.iloc[i]
            neighbors = df.iloc[neighbor_indices]
            
            # === 方法 1: MAD 检测 high 异常 ===
            if 'high' in df.columns:
                high_median = neighbors['high'].median()
                high_mad = np.median(np.abs(neighbors['high'] - high_median))
                
                if high_mad > 0:
                    mad_score = abs(current['high'] - high_median) / high_mad
                else:
                    mad_score = 0
                
                # 相对变化
                if high_median > 0:
                    relative_change = abs(current['high'] - high_median) / high_median
                else:
                    relative_change = 0
                
                # 判断异常
                is_anomaly_mad = mad_score > self.MAD_THRESHOLD
                
                if is_anomaly_mad and relative_change > 0.01:  # 至少 1% 的变化才记录
                    anomaly_info = {
                        'index': i,
                        'timestamp': current.get('timestamp', i),
                        'field': 'high',
                        'value': float(current['high']),
                        'neighbor_median': float(high_median),
                        'mad_score': float(mad_score),
                        'relative_change': float(relative_change),
                        'reason': [],
                        'method': 'MAD'
                    }
                    
                    anomaly_info['reason'].append(f'MAD={mad_score:.2f} > {self.MAD_THRESHOLD}')
                    if relative_change > 0.05:
                        anomaly_info['reason'].append(f'change={relative_change:.1%}')
                    
                    anomalies.append(anomaly_info)
                    continue  # 已检测到异常，不再检查其他字段
            
            # === 方法 2: MAD 检测 low 异常 ===
            if 'low' in df.columns:
                low_median = neighbors['low'].median()
                low_mad = np.median(np.abs(neighbors['low'] - low_median))
                
                if low_mad > 0:
                    mad_score = abs(current['low'] - low_median) / low_mad
                else:
                    mad_score = 0
                
                if low_median > 0:
                    relative_change = abs(current['low'] - low_median) / low_median
                else:
                    relative_change = 0
                
                is_anomaly_mad = mad_score > self.MAD_THRESHOLD
                
                if is_anomaly_mad and relative_change > 0.01:
                    anomaly_info = {
                        'index': i,
                        'timestamp': current.get('timestamp', i),
                        'field': 'low',
                        'value': float(current['low']),
                        'neighbor_median': float(low_median),
                        'mad_score': float(mad_score),
                        'relative_change': float(relative_change),
                        'reason': [],
                        'method': 'MAD'
                    }
                    
                    anomaly_info['reason'].append(f'MAD={mad_score:.2f} > {self.MAD_THRESHOLD}')
                    if relative_change > 0.05:
                        anomaly_info['reason'].append(f'change={relative_change:.1%}')
                    
                    anomalies.append(anomaly_info)
                    continue
            
            # === 方法 3: Returns-based 检测 ===
            if 'returns' in df.columns and i > 0:
                if pd.notna(current['returns']) and abs(current['returns']) > self.RETURNS_THRESHOLD:
                    anomaly_info = {
                        'index': i,
                        'timestamp': current.get('timestamp', i),
                        'field': 'close',
                        'value': float(current['close']),
                        'prev_close': float(df.iloc[i-1]['close']),
                        'returns': float(current['returns']),
                        'reason': [f'异常涨跌幅={current["returns"]:.2%}'],
                        'method': 'Returns'
                    }
                    anomalies.append(anomaly_info)
                    continue
            
            # === 方法 4: High-Low Range 检测 ===
            if all(f in df.columns for f in ['high', 'low', 'close']):
                if current['close'] > 0:
                    hl_range = (current['high'] - current['low']) / current['close']
                    
                    if hl_range > self.HL_RANGE_THRESHOLD:
                        anomaly_info = {
                            'index': i,
                            'timestamp': current.get('timestamp', i),
                            'field': 'high_low_range',
                            'high': float(current['high']),
                            'low': float(current['low']),
                            'close': float(current['close']),
                            'hl_range_pct': float(hl_range * 100),
                            'reason': [f'High-Low波动={hl_range:.1%} > {self.HL_RANGE_THRESHOLD:.1%}'],
                            'method': 'HL-Range'
                        }
                        anomalies.append(anomaly_info)
        
        return anomalies
    
    def _handle_anomalies_safe(
        self, 
        df: pd.DataFrame, 
        anomalies: List[Dict],
        action: str,
        symbol: str
    ) -> pd.DataFrame:
        """
        安全处理异常值 - 专为合约市场设计
        
        原则：
        1. 永不使用 interpolate（不制造虚假价格路径）
        2. high/low 异常 → clip 到邻近最大/最小值
        3. 超阈值异常 → 整根 K 线 drop
        4. 成交量异常 → 保留（不影响价格）
        """
        df_cleaned = df.copy()
        drop_indices = set()
        
        for anomaly in anomalies:
            idx = anomaly['index']
            
            # 跳过已标记删除的行
            if idx in drop_indices:
                continue
            
            field = anomaly.get('field')
            method = anomaly.get('method', 'unknown')
            
            # === 处理 high 异常 ===
            if field == 'high':
                if action == 'clip':
                    # Clip 到邻近窗口的最大值
                    start_idx = max(0, idx - self.NEIGHBOR_WINDOW)
                    end_idx = min(len(df), idx + self.NEIGHBOR_WINDOW + 1)
                    neighbor_indices = [j for j in range(start_idx, end_idx) if j != idx]
                    
                    if neighbor_indices:
                        neighbor_max = df.iloc[neighbor_indices]['high'].max()
                        df_cleaned.at[df_cleaned.index[idx], 'high'] = neighbor_max
                        self.clipped_count += 1
                        log.info(f"[{symbol}] Clipped high at idx={idx}: {anomaly['value']:.2f} → {neighbor_max:.2f}")
                
                elif action == 'drop':
                    # 如果异常太严重，删除整根 K 线
                    relative_change = anomaly.get('relative_change', 0)
                    if relative_change > 0.10:  # 超过 10% 就删除
                        drop_indices.add(idx)
                        self.dropped_count += 1
                        log.warning(f"[{symbol}] Dropped K-line at idx={idx} due to severe high anomaly: {relative_change:.1%}")
            
            # === 处理 low 异常 ===
            elif field == 'low':
                if action == 'clip':
                    # Clip 到邻近窗口的最小值
                    start_idx = max(0, idx - self.NEIGHBOR_WINDOW)
                    end_idx = min(len(df), idx + self.NEIGHBOR_WINDOW + 1)
                    neighbor_indices = [j for j in range(start_idx, end_idx) if j != idx]
                    
                    if neighbor_indices:
                        neighbor_min = df.iloc[neighbor_indices]['low'].min()
                        df_cleaned.at[df_cleaned.index[idx], 'low'] = neighbor_min
                        self.clipped_count += 1
                        log.info(f"[{symbol}] Clipped low at idx={idx}: {anomaly['value']:.2f} → {neighbor_min:.2f}")
                
                elif action == 'drop':
                    relative_change = anomaly.get('relative_change', 0)
                    if relative_change > 0.10:
                        drop_indices.add(idx)
                        self.dropped_count += 1
                        log.warning(f"[{symbol}] Dropped K-line at idx={idx} due to severe low anomaly: {relative_change:.1%}")
            
            # === 处理 close 异常（异常涨跌幅）===
            elif field == 'close':
                if action == 'drop':
                    # 异常涨跌幅直接删除整根 K 线
                    drop_indices.add(idx)
                    self.dropped_count += 1
                    returns = anomaly.get('returns', 0)
                    log.warning(f"[{symbol}] Dropped K-line at idx={idx} due to abnormal returns: {returns:.2%}")
            
            # === 处理 high-low range 异常 ===
            elif field == 'high_low_range':
                if action == 'drop':
                    # 异常波动直接删除
                    drop_indices.add(idx)
                    self.dropped_count += 1
                    hl_range = anomaly.get('hl_range_pct', 0)
                    log.warning(f"[{symbol}] Dropped K-line at idx={idx} due to abnormal HL range: {hl_range:.1f}%")
        
        # 执行删除
        if drop_indices:
            df_cleaned = df_cleaned.drop(df_cleaned.index[list(drop_indices)])
            df_cleaned = df_cleaned.reset_index(drop=True)
        
        return df_cleaned
    
    def get_validation_summary(self) -> Dict:
        """获取详细验证汇总"""
        return {
            'raw_anomalies_detected': self.raw_anomaly_count,
            'cleaned_anomalies_remaining': self.cleaned_anomaly_count,
            'clipped_count': self.clipped_count,
            'dropped_count': self.dropped_count,
            'anomaly_details': self.anomaly_details[-10:],  # 最近10个
            'detection_method': 'MAD + Returns + HL-Range'
        }

