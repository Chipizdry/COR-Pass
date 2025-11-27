"""
Gunicorn configuration для поддержки Prometheus multiprocess mode
"""
from cor_pass.services.shared.prometheus_multiprocess import child_exit as cleanup_worker_metrics

# Hook вызываемый при завершении worker процесса
# Очищает метрики для завершившегося worker
def child_exit(server, worker):
    cleanup_worker_metrics(server, worker)
