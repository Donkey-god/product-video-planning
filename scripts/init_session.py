#!/usr/bin/env python3
"""
会话目录初始化脚本
用法：
  python3 init_session.py --product "商品名称" --sku "sku编号" --root "~/freshVedioPlanning"

功能：
  1. 展开 ~/ 路径为绝对路径
  2. 在根目录下查找该商品（按商品名称+sku）的已有目录
  3. 自动递增 run_NNN（最多999次）
  4. 创建目录并返回本次 run 路径
"""

import argparse
import os
import re
from pathlib import Path


def sanitize_name(name: str) -> str:
    """去掉空格和特殊字符，保留中文/英文/数字"""
    # 保留中文、字母、数字，其他替换为下划线
    return re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff]+', '_', name).strip('_')


def find_existing_runs(base_path: Path) -> list[Path]:
    """查找该商品目录下所有 run_NNN 目录"""
    if not base_path.exists():
        return []
    runs = []
    for d in base_path.iterdir():
        if d.is_dir() and re.match(r'^run_\d{3}$', d.name):
            runs.append(d)
    runs.sort(key=lambda x: x.name)
    return runs


def get_next_run_num(runs: list[Path]) -> int:
    """根据已有 run 目录，计算下一个编号"""
    if not runs:
        return 1
    # 解析最后一项的编号
    last_name = runs[-1].name
    m = re.search(r'run_(\d+)$', last_name)
    if m:
        n = int(m.group(1))
        if n >= 999:
            raise ValueError("run 编号已达上限 999")
        return n + 1
    return 1


def main():
    parser = argparse.ArgumentParser(description="初始化商品视频策划会话目录")
    parser.add_argument("--product", required=True, help="商品名称")
    parser.add_argument("--sku", required=True, help="SKU编号")
    parser.add_argument("--root", required=True, help="根目录路径，支持 ~/")
    args = parser.parse_args()

    # 展开 ~/
    root = Path(os.path.expanduser(args.root))

    # 创建商品前缀：商品名缩写 + sku
    prefix = f"{sanitize_name(args.product)}_{args.sku}"

    # 查找/创建商品根目录
    product_dir = root / prefix
    product_dir.mkdir(parents=True, exist_ok=True)

    # 查找已有 run 目录
    runs = find_existing_runs(product_dir)
    next_num = get_next_run_num(runs)
    run_dir = product_dir / f"run_{next_num:03d}"
    run_dir.mkdir(exist_ok=True)

    print(run_dir.resolve().as_posix())


if __name__ == "__main__":
    main()
