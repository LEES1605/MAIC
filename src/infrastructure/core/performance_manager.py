# ============== [01] PerformanceManager 클래스 - 성능 최적화 관리 ==============
from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable, Union
from enum import Enum
from collections import deque
import gc

# psutil은 선택적 의존성으로 처리
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    psutil = None

# ============== [02] 성능 메트릭 타입 ==============
class PerformanceMetric(Enum):
    MEMORY_USAGE = "memory_usage"
    CPU_USAGE = "cpu_usage"
    STREAMING_LATENCY = "streaming_latency"
    CHUNK_SIZE = "chunk_size"
    CACHE_HIT_RATE = "cache_hit_rate"
    RESPONSE_TIME = "response_time"

@dataclass
class PerformanceStats:
    """성능 통계 데이터"""
    metric: PerformanceMetric
    value: float
    timestamp: float = field(default_factory=time.time)
    context: Optional[Dict[str, Any]] = None

@dataclass
class StreamingConfig:
    """스트리밍 성능 설정"""
    chunk_size: int = 10  # 기본 청크 크기 (문자 단위)
    max_chunk_size: int = 50  # 최대 청크 크기
    min_chunk_size: int = 5   # 최소 청크 크기
    latency_threshold_ms: int = 100  # 지연 임계값 (밀리초)
    memory_threshold_mb: int = 100   # 메모리 임계값 (MB)
    adaptive_chunking: bool = True   # 적응형 청킹 사용 여부

@dataclass
class MemoryConfig:
    """메모리 관리 설정"""
    max_cache_size_mb: int = 50      # 최대 캐시 크기 (MB)
    gc_threshold_mb: int = 200       # 가비지 컬렉션 임계값 (MB)
    cleanup_interval_sec: int = 30   # 정리 간격 (초)
    max_entries: int = 10000         # 최대 엔트리 수

# ============== [03] PerformanceManager 클래스 ==============
class PerformanceManager:
    """
    성능 최적화 관리 클래스
    
    기능:
    - 실시간 성능 모니터링
    - 적응형 스트리밍 청크 크기 조정
    - 메모리 사용량 최적화
    - 캐시 관리 및 정리
    - 성능 통계 수집 및 분석
    """
    
    def __init__(self):
        self._stats: deque = deque(maxlen=1000)  # 최근 1000개 통계만 유지
        self._streaming_config = StreamingConfig()
        self._memory_config = MemoryConfig()
        self._cache: Dict[str, Any] = {}
        self._cache_access_count: Dict[str, int] = {}
        self._cache_hit_count: Dict[str, int] = {}
        self._lock = threading.Lock()
        self._last_cleanup = time.time()
        self._process = None
        if PSUTIL_AVAILABLE:
            try:
                self._process = psutil.Process()
            except Exception:
                self._process = None
        
    def get_memory_usage_mb(self) -> float:
        """현재 메모리 사용량을 MB 단위로 반환"""
        if not PSUTIL_AVAILABLE or not self._process:
            return 0.0
        try:
            return self._process.memory_info().rss / 1024 / 1024
        except Exception:
            return 0.0
    
    def get_cpu_usage_percent(self) -> float:
        """현재 CPU 사용률을 퍼센트로 반환"""
        if not PSUTIL_AVAILABLE or not self._process:
            return 0.0
        try:
            return self._process.cpu_percent()
        except Exception:
            return 0.0
    
    def record_metric(self, metric: PerformanceMetric, value: float, context: Optional[Dict[str, Any]] = None) -> None:
        """성능 메트릭 기록"""
        with self._lock:
            stats = PerformanceStats(metric=metric, value=value, context=context)
            self._stats.append(stats)
    
    def get_adaptive_chunk_size(self, base_text_length: int, current_latency_ms: float) -> int:
        """
        적응형 청크 크기 계산
        
        Args:
            base_text_length: 기본 텍스트 길이
            current_latency_ms: 현재 지연 시간 (밀리초)
        
        Returns:
            최적화된 청크 크기
        """
        if not self._streaming_config.adaptive_chunking:
            return self._streaming_config.chunk_size
        
        # 메모리 사용량 기반 조정
        memory_usage = self.get_memory_usage_mb()
        if memory_usage > self._streaming_config.memory_threshold_mb:
            # 메모리 사용량이 높으면 청크 크기 감소
            chunk_size = max(self._streaming_config.min_chunk_size, 
                           self._streaming_config.chunk_size // 2)
        else:
            # 지연 시간 기반 조정
            if current_latency_ms > self._streaming_config.latency_threshold_ms:
                # 지연이 크면 청크 크기 감소
                chunk_size = max(self._streaming_config.min_chunk_size,
                               self._streaming_config.chunk_size - 2)
            else:
                # 지연이 적으면 청크 크기 증가 (성능 향상)
                chunk_size = min(self._streaming_config.max_chunk_size,
                               self._streaming_config.chunk_size + 1)
        
        # 텍스트 길이 기반 조정
        if base_text_length > 1000:
            chunk_size = min(chunk_size, self._streaming_config.chunk_size)
        elif base_text_length < 100:
            chunk_size = max(chunk_size, self._streaming_config.min_chunk_size)
        
        return chunk_size
    
    def optimize_streaming_chunk(self, text: str, callback: Callable[[str], None]) -> None:
        """
        최적화된 스트리밍 청크 처리
        
        Args:
            text: 스트리밍할 텍스트
            callback: 청크를 받을 콜백 함수
        """
        start_time = time.time()
        chunk_size = self.get_adaptive_chunk_size(len(text), 0)
        
        try:
            # 청크 단위로 처리
            for i in range(0, len(text), chunk_size):
                chunk = text[i:i + chunk_size]
                callback(chunk)
                
                # 지연 시간 측정
                current_time = time.time()
                latency_ms = (current_time - start_time) * 1000
                
                # 적응형 청크 크기 조정
                if i > 0:  # 첫 번째 청크 이후에만 조정
                    chunk_size = self.get_adaptive_chunk_size(len(text), latency_ms)
                
                # 성능 메트릭 기록
                self.record_metric(
                    PerformanceMetric.STREAMING_LATENCY,
                    latency_ms,
                    {"chunk_size": chunk_size, "text_length": len(text)}
                )
                
        except Exception as e:
            # 오류 발생 시 기본 청크 크기로 폴백
            chunk_size = self._streaming_config.chunk_size
            for i in range(0, len(text), chunk_size):
                chunk = text[i:i + chunk_size]
                callback(chunk)
    
    def cache_get(self, key: str, default: Any = None) -> Any:
        """캐시에서 값 조회 (히트율 추적)"""
        with self._lock:
            self._cache_access_count[key] = self._cache_access_count.get(key, 0) + 1
            
            if key in self._cache:
                self._cache_hit_count[key] = self._cache_hit_count.get(key, 0) + 1
                return self._cache[key]
            
            return default
    
    def cache_set(self, key: str, value: Any) -> None:
        """캐시에 값 저장 (크기 제한)"""
        with self._lock:
            self._cache[key] = value
            
            # 캐시 크기 제한 확인
            if len(self._cache) > self._memory_config.max_entries:
                self._cleanup_cache()
    
    def _cleanup_cache(self) -> None:
        """캐시 정리 (LRU 기반)"""
        if not self._cache:
            return
        
        # 접근 횟수가 적은 항목들 제거
        sorted_items = sorted(
            self._cache_access_count.items(),
            key=lambda x: x[1]
        )
        
        # 상위 20% 제거
        remove_count = max(1, len(sorted_items) // 5)
        for key, _ in sorted_items[:remove_count]:
            self._cache.pop(key, None)
            self._cache_access_count.pop(key, None)
            self._cache_hit_count.pop(key, None)
    
    def get_cache_hit_rate(self) -> float:
        """캐시 히트율 계산"""
        with self._lock:
            total_access = sum(self._cache_access_count.values())
            total_hits = sum(self._cache_hit_count.values())
            
            if total_access == 0:
                return 0.0
            
            return (total_hits / total_access) * 100
    
    def cleanup_memory(self) -> None:
        """메모리 정리"""
        current_time = time.time()
        
        # 정리 간격 확인
        if current_time - self._last_cleanup < self._memory_config.cleanup_interval_sec:
            return
        
        memory_usage = self.get_memory_usage_mb()
        
        if memory_usage > self._memory_config.gc_threshold_mb:
            # 가비지 컬렉션 실행
            gc.collect()
            
            # 캐시 정리
            self._cleanup_cache()
            
            # 통계 기록
            self.record_metric(
                PerformanceMetric.MEMORY_USAGE,
                memory_usage,
                {"action": "cleanup", "cache_size": len(self._cache)}
            )
            
            self._last_cleanup = current_time
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """성능 요약 정보 반환"""
        with self._lock:
            recent_stats = list(self._stats)[-100:]  # 최근 100개 통계
            
            summary = {
                "memory_usage_mb": self.get_memory_usage_mb(),
                "cpu_usage_percent": self.get_cpu_usage_percent(),
                "cache_hit_rate": self.get_cache_hit_rate(),
                "cache_size": len(self._cache),
                "stats_count": len(self._stats),
                "streaming_config": {
                    "chunk_size": self._streaming_config.chunk_size,
                    "adaptive_chunking": self._streaming_config.adaptive_chunking,
                },
                "recent_metrics": {}
            }
            
            # 최근 메트릭별 평균 계산
            for metric in PerformanceMetric:
                values = [s.value for s in recent_stats if s.metric == metric]
                if values:
                    summary["recent_metrics"][metric.value] = {
                        "avg": sum(values) / len(values),
                        "min": min(values),
                        "max": max(values),
                        "count": len(values)
                    }
            
            return summary
    
    def update_streaming_config(self, **kwargs) -> None:
        """스트리밍 설정 업데이트"""
        for key, value in kwargs.items():
            if hasattr(self._streaming_config, key):
                setattr(self._streaming_config, key, value)
    
    def update_memory_config(self, **kwargs) -> None:
        """메모리 설정 업데이트"""
        for key, value in kwargs.items():
            if hasattr(self._memory_config, key):
                setattr(self._memory_config, key, value)

# ============== [04] 싱글턴 인스턴스 ==============
_performance_manager_instance: Optional[PerformanceManager] = None

def get_performance_manager() -> PerformanceManager:
    """PerformanceManager 싱글턴 인스턴스 반환"""
    global _performance_manager_instance
    if _performance_manager_instance is None:
        _performance_manager_instance = PerformanceManager()
    return _performance_manager_instance

# ============== [05] 편의 함수들 ==============
def optimize_streaming(text: str, callback: Callable[[str], None]) -> None:
    """스트리밍 최적화 편의 함수"""
    get_performance_manager().optimize_streaming_chunk(text, callback)

def get_adaptive_chunk_size(text_length: int, latency_ms: float = 0) -> int:
    """적응형 청크 크기 조회 편의 함수"""
    return get_performance_manager().get_adaptive_chunk_size(text_length, latency_ms)

def cleanup_memory() -> None:
    """메모리 정리 편의 함수"""
    get_performance_manager().cleanup_memory()

def get_performance_summary() -> Dict[str, Any]:
    """성능 요약 조회 편의 함수"""
    return get_performance_manager().get_performance_summary()

# ============== [06] 내보내기 ==============
__all__ = [
    "PerformanceManager",
    "PerformanceMetric",
    "PerformanceStats",
    "StreamingConfig",
    "MemoryConfig",
    "get_performance_manager",
    "optimize_streaming",
    "get_adaptive_chunk_size",
    "cleanup_memory",
    "get_performance_summary",
]
