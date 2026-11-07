"""產生第 1 步 subagent 的 prompt。python prompt.py j1 1  → 判者一第 1 組（b001–b003）"""
import sys
from common import SCRATCH
j, g = sys.argv[1], int(sys.argv[2])
bs = [f'b{n:03d}' for n in range(3 * g - 2, 3 * g + 1)]
if j == 'j2':
    bs = bs[::-1]
S = str(SCRATCH)
lines = [f'   - 批次 {S}\main\{b}.txt → 寫到 {S}\main\out_{j}_{b}.json' for b in bs]
print('\n'.join(lines))
