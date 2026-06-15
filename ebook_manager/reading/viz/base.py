import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import rcParams
import numpy as np
from pathlib import Path
from typing import Tuple, Optional

rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
rcParams['axes.unicode_minus'] = False


COLOR_PALETTE = [
    '#4a9eff', '#52c41a', '#faad14', '#f5222d',
    '#722ed1', '#13c2c2', '#eb2f96', '#fa8c16'
]


class ChartBase:
    def __init__(self, output_dir: Path, color_palette=None):
        self.output_dir = output_dir
        self.colors = color_palette or COLOR_PALETTE

    def _setup_figure(self, size: Tuple[int, int] = (12, 6)) -> Tuple[plt.Figure, plt.Axes]:
        fig, ax = plt.subplots(figsize=size, dpi=100)
        fig.patch.set_facecolor('#fafbfc')
        ax.set_facecolor('#ffffff')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        return fig, ax

    def _save_and_close(self, fig: plt.Figure, filename: str) -> str:
        filepath = self.output_dir / filename
        fig.tight_layout()
        fig.savefig(filepath, bbox_inches='tight', facecolor=fig.get_facecolor())
        plt.close(fig)
        return str(filepath)

    def _no_data_text(self, ax):
        ax.text(0.5, 0.5, '暂无数据', ha='center', va='center',
                transform=ax.transAxes, fontsize=16, color='#999')
