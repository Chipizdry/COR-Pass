"""
Prometheus multiprocess mode support for Gunicorn workers
"""
import os
import shutil
from prometheus_client import multiprocess, CollectorRegistry


def child_exit(server, worker):
    """
    Gunicorn hook вызываемый когда worker процесс завершается
    Очищает метрики для этого worker
    """
    multiprocess.mark_process_dead(worker.pid)


def setup_prometheus_multiprocess():
    """
    Настройка директории для multiprocess mode
    Вызывается при старте приложения
    
    Безопасно: если PROMETHEUS_MULTIPROC_DIR не установлен,
    функция ничего не делает и метрики работают в обычном режиме
    """
    prom_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if not prom_dir:
        # Если переменная не установлена - работаем без multiprocess mode
        # Это безопасный fallback для development/старых deployment
        return
    
    # Убеждаемся что директория существует
    os.makedirs(prom_dir, exist_ok=True)
    
    # Очищаем старые метрики при старте worker
    # (для hot reload / restart)
    if os.path.exists(prom_dir):
        for filename in os.listdir(prom_dir):
            filepath = os.path.join(prom_dir, filename)
            try:
                if os.path.isfile(filepath):
                    os.unlink(filepath)
            except Exception as e:
                print(f"Warning: Could not delete {filepath}: {e}")
