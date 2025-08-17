import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from MetricsClasses.HalsteadMetricsClass import HalsteadMetrics
from MetricsClasses.TraditionalMetricsClass import TraditionalMetrics
from MetricsClasses.OOMetricsClass import OOMetrics
from multiprocessing.pool import ThreadPool

supported_metrics=["Halstead","Traditional","OO"]

class MetricsController:
    def __init__(self, tree):
        self.metrics_obj_list = [HalsteadMetrics(tree), TraditionalMetrics(tree), OOMetrics(tree)]
        
    def calculate_metrics(self):
        with ThreadPool(processes=len(self.metrics_obj_list)) as pool:
            results = []
            for metrics_obj in self.metrics_obj_list:
                results.append(pool.apply_async(metrics_obj.calculate_metrics))
            pool.close()
            pool.join()
            return [r.get() for r in results]