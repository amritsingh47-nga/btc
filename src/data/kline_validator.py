"""
K线数据验证器 - 正确实现

核心原则：K线是市场事实，绝不修改价格数据！

只检测和处理真正的数据错误：
1. 数据完整性问题（缺失字段、NaN、Inf）
2. OHLC 逻辑违反（high < low 等）
3. 价格超出合理范围（< 0 或 > 10M）
4. 时间序列问题（重复、断档）

不处理的"异常"（这些都是正常市场行为）：
- 大幅跳空/涨跌幅
- 长影线（Pin Bar）
- MAD 偏离大
- 连续单边行情
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
from src.utils.logger import log


class KlineValidator:
    """K线数据验证器 - 仅检测真正的数据错误，不修改价格"""
    
    # 合理价格范围（用于检测 API 错误，不是市场波动）
    MIN_REASONABLE_PRICE = 0.001  # 0.1 美分
    MAX_REASONABLE_PRICE = 10_000_000  # 1000万 USDT
    
    def __init__(self):
        self.issues_found: List[Dict] = []
        self.removed_count = 0
    
    def validate_and_clean_klines(
        self, 
        klines: List[Dict],
        symbol: str,
        action: str = 'remove'  # 只支持 'remove' 或 'none'
    ) -> Tuple[List[Dict], Dict]:
        """
        验证K线数据质量
        
        Args:
            klines: 原始K线数据
            symbol: 交易对
            action: 处理方式
                - 'remove': 删除无效K线（默认）
                - 'none': 仅检测不处理
        
        Returns:
            (清洗后的K线, 验证报告)
        """
        if not klines or len(klines) < 1:
            log.warning(f"[{symbol}] K线数据为空")
            return klines, {
                'status': 'empty',
                'n_original': 0,
                'n_cleaned': 0
            }
        
        self.issues_found = []
        self.removed_count = 0
        n_original = len(klines)
        
        # 1. 检测所有问题
        log.debug(f"[{symbol}] 开始验证 {n_original} 根K线...")
        
        issues = []
        issues.extend(self._check_basic_validity(klines, symbol))
        issues.extend(self._check_ohlc_logic(klines, symbol))
        issues.extend(self._check_time_series(klines, symbol))
        
        self.issues_found = issues
        
        # 2. 处理问题
        if issues and action == 'remove':
            cleaned_klines = self._remove_invalid_klines(klines, issues)
            self.removed_count = n_original - len(cleaned_klines)
        else:
            cleaned_klines = klines
        
        # 3. 生成报告
        report = {
            'status': 'cleaned' if issues else 'clean',
            'n_original': n_original,
            'n_cleaned': len(cleaned_klines),
            'removed_count': self.removed_count,
            'issues': issues,
            'action_taken': action if issues else 'none',
            'method': 'Integrity-Check-Only'  # 明确说明：仅完整性检查
        }
        
        # 4. 日志
        if issues:
            log.warning(
                f"[{symbol}] 数据验证: "
                f"原始={n_original}, 清洗后={len(cleaned_klines)}, "
                f"问题数={len(issues)}, 删除={self.removed_count}"
            )
            
            # 按类型统计
            issue_types = {}
            for issue in issues:
                issue_type = issue.get('type', 'unknown')
                issue_types[issue_type] = issue_types.get(issue_type, 0) + 1
            
            for issue_type, count in issue_types.items():
                log.warning(f"  - {issue_type}: {count} 个")
            
            # 显示前3个问题详情
            for issue in issues[:3]:
                log.warning(f"  详情: {issue}")
        else:
            log.debug(f"[{symbol}] ✅ 数据验证通过，无问题发现")
        
        return cleaned_klines, report
    
    def _check_basic_validity(self, klines: List[Dict], symbol: str) -> List[Dict]:
        """检查基础数据完整性"""
        issues = []
        required_fields = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        
        for i, kline in enumerate(klines):
            # 1. 检查缺失字段
            missing = [f for f in required_fields if f not in kline]
            if missing:
                issues.append({
                    'index': i,
                    'type': 'missing_fields',
                    'fields': missing,
                    'timestamp': kline.get('timestamp', 'unknown'),
                    'severity': 'critical',
                    'action': 'remove'
                })
                continue  # 缺失字段的K线无法进一步检查
            
            # 2. 检查 NaN/Inf/None
            for field in ['open', 'high', 'low', 'close', 'volume']:
                value = kline.get(field)
                if value is None or (isinstance(value, float) and (np.isnan(value) or np.isinf(value))):
                    issues.append({
                        'index': i,
                        'type': 'invalid_value',
                        'field': field,
                        'value': str(value),
                        'timestamp': kline.get('timestamp'),
                        'severity': 'critical',
                        'action': 'remove'
                    })
                    break  # 有一个字段无效就跳出
            
            # 3. 检查价格范围（API 错误，不是市场波动）
            for field in ['open', 'high', 'low', 'close']:
                value = kline.get(field, 0)
                if not isinstance(value, (int, float)):
                    continue
                
                if value < self.MIN_REASONABLE_PRICE or value > self.MAX_REASONABLE_PRICE:
                    issues.append({
                        'index': i,
                        'type': 'price_out_of_range',
                        'field': field,
                        'value': value,
                        'range': f'{self.MIN_REASONABLE_PRICE} - {self.MAX_REASONABLE_PRICE}',
                        'timestamp': kline.get('timestamp'),
                        'severity': 'critical',
                        'action': 'remove'
                    })
                    break
            
            # 4. 检查负成交量
            volume = kline.get('volume', 0)
            if isinstance(volume, (int, float)) and volume < 0:
                issues.append({
                    'index': i,
                    'type': 'negative_volume',
                    'value': volume,
                    'timestamp': kline.get('timestamp'),
                    'severity': 'warning',  # 可能只是数据缺失
                    'action': 'remove'
                })
        
        return issues
    
    def _check_ohlc_logic(self, klines: List[Dict], symbol: str) -> List[Dict]:
        """
        检查 OHLC 逻辑关系
        
        这些是真正的数据错误（API 传输错误），不是市场行为：
        - high < low
        - high < open 或 high < close
        - low > open 或 low > close
        """
        issues = []
        
        for i, kline in enumerate(klines):
            # 确保所有字段都存在且有效
            if not all(k in kline for k in ['open', 'high', 'low', 'close']):
                continue  # 已在 basic_validity 检查中处理
            
            try:
                o = float(kline['open'])
                h = float(kline['high'])
                l = float(kline['low'])
                c = float(kline['close'])
            except (ValueError, TypeError):
                continue  # 无效数值，已在 basic_validity 检查中处理
            
            # OHLC 逻辑检查
            violations = []
            
            if h < l:
                violations.append(f'high({h}) < low({l})')
            
            if h < o:
                violations.append(f'high({h}) < open({o})')
            
            if h < c:
                violations.append(f'high({h}) < close({c})')
            
            if l > o:
                violations.append(f'low({l}) > open({o})')
            
            if l > c:
                violations.append(f'low({l}) > close({c})')
            
            if violations:
                issues.append({
                    'index': i,
                    'type': 'ohlc_logic_violation',
                    'violations': violations,
                    'ohlc': {'open': o, 'high': h, 'low': l, 'close': c},
                    'timestamp': kline.get('timestamp'),
                    'severity': 'critical',
                    'action': 'remove'
                })
        
        return issues
    
    def _check_time_series(self, klines: List[Dict], symbol: str) -> List[Dict]:
        """检查时间序列完整性"""
        issues = []
        
        if not klines:
            return issues
        
        timestamps = [(i, k.get('timestamp')) for i, k in enumerate(klines)]
        
        # 1. 检查重复时间戳
        seen = {}
        for i, ts in timestamps:
            if ts in seen:
                issues.append({
                    'index': i,
                    'type': 'duplicate_timestamp',
                    'timestamp': ts,
                    'first_occurrence': seen[ts],
                    'severity': 'warning',
                    'action': 'remove'
                })
            else:
                seen[ts] = i
        
        # 2. 检查时间序列单调性（可选，不强制删除）
        prev_ts = None
        for i, ts in timestamps:
            if prev_ts is not None and ts is not None:
                if isinstance(ts, str) and isinstance(prev_ts, str):
                    # 字符串时间戳比较
                    if ts < prev_ts:
                        issues.append({
                            'index': i,
                            'type': 'time_not_monotonic',
                            'timestamp': ts,
                            'prev_timestamp': prev_ts,
                            'severity': 'info',  # 仅记录，不删除
                            'action': 'none'
                        })
            prev_ts = ts
        
        return issues
    
    def _remove_invalid_klines(
        self, 
        klines: List[Dict], 
        issues: List[Dict]
    ) -> List[Dict]:
        """
        删除无效K线（只删除，不修改）
        
        Args:
            klines: 原始K线
            issues: 检测到的问题
        
        Returns:
            清洗后的K线（删除了无效数据）
        """
        # 收集需要删除的索引（只删除 action='remove' 的）
        remove_indices = set()
        for issue in issues:
            if issue.get('action') == 'remove':
                remove_indices.add(issue['index'])
        
        # 保留有效K线
        cleaned = [k for i, k in enumerate(klines) if i not in remove_indices]
        
        log.info(f"删除了 {len(remove_indices)} 根无效K线")
        
        return cleaned
    
    def get_validation_summary(self) -> Dict:
        """获取验证摘要"""
        if not self.issues_found:
            return {
                'total_issues': 0,
                'removed_count': 0,
                'status': 'clean'
            }
        
        # 按类型统计
        by_type = {}
        by_severity = {}
        
        for issue in self.issues_found:
            issue_type = issue.get('type', 'unknown')
            severity = issue.get('severity', 'unknown')
            
            by_type[issue_type] = by_type.get(issue_type, 0) + 1
            by_severity[severity] = by_severity.get(severity, 0) + 1
        
        return {
            'total_issues': len(self.issues_found),
            'removed_count': self.removed_count,
            'by_type': by_type,
            'by_severity': by_severity,
            'status': 'issues_found'
        }
