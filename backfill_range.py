# -*- coding: utf-8 -*-
"""按指定日期区间补拉「抖音明细」，用于修补跨月造成的数据缺口。

背景：
    BI 报表「抖音明细」组件的日期筛选器是「相对时间 = 本月」（dynamicMode=3,
    RelativeTime count=1 unit=month）。所以：
      - 10 月里导出的是 10-01 ~ 昨天
      - 11-01 起导出只剩 11-01 之后
    即每月 1 号起，上个月的数据会整段从导出里消失（10-31 就这样丢过）。

    异步导出（asyncExportExcel）不支持 defaultFilters，只能吃报表自带的筛选；
    同步导出（exportExcel）支持 defaultFilters，但单次最多返回 5 万行。
    单日全店约 7 万行，所以这里按「日期 × 店铺批次」拆开拉，再合并去重。

用法：
    python backfill_range.py --from 2026-10-31 --to 2026-10-31
    python backfill_range.py --from 2026-10-28 --to 2026-10-31 --data-dir data/2026-11-02
"""
import argparse
import csv
import datetime
import io
import os
import sys
import urllib.request
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import youdata_client as yc

BASE = os.path.dirname(os.path.abspath(__file__))
REPORT_ID = 36928
DASHBOARD_ID = 45005
COMPONENT_ID = 'c-1-18047-45005-kjmplaah'          # 抖音明细
DATE_FILTER_ID = 'c-1-18047-45005-kjw8xoyq'       # 该组件的日期筛选器
SHOP_FILTER_ID = 'c-1-18047-45005-l2h9hyjj'       # 该组件的店铺筛选器

# 单日行数最大的两家先单独拉，其余用 exclude 兜底，保证每批 < 5 万行
BATCHES = [
    ('big1', {'selected': ['今日头条放心购'], 'exclude': False}),
    ('big2', {'selected': ['今日头条家清放心购'], 'exclude': False}),
    ('rest', {'selected': ['今日头条放心购', '今日头条家清放心购'], 'exclude': True}),
]


def _post(params, timeout=900):
    return yc.api_post('/api/dash/report/exportExcel', params, timeout=timeout)


def export_day(day):
    """拉取某一天的全店明细，返回 (header, rows)。失败时抛异常。"""
    rows, header = [], None
    for tag, shop_filter in BATCHES:
        filters = {
            DATE_FILTER_ID: {'type': 'StaticTime',
                             'minBound': day + ' 00:00:00',
                             'maxBound': day + ' 24:00:00'},
            SHOP_FILTER_ID: shop_filter,
        }
        params = {
            'reportId': REPORT_ID, 'dashboardId': DASHBOARD_ID, 'pid': DASHBOARD_ID,
            'componentId': COMPONENT_ID, 'type': 'component', 'exportType': 'csv',
            'enhance': False, 'useOriginData': False, 'includeTitle': False,
            'rowsLimit': 2000000, 'excelSplitLimit': 1000000,
            'defaultFilters': filters,
        }
        last_err = None
        res = None
        for attempt in range(4):
            try:
                r = _post(params)
                res = r.get('result') or {}
                if res.get('link'):
                    break
                last_err = r.get('message') or ('code=%s' % r.get('code'))
            except Exception as e:
                last_err = '%s: %s' % (type(e).__name__, e)
            res = None
        if not res or not res.get('link'):
            raise RuntimeError('%s/%s 导出失败: %s' % (day, tag, last_err))

        link = res['link']
        if '/dash/store/' not in link and 'token=' not in link:
            link += ('&' if '?' in link else '?') + 'token=' + yc.get_token()
        with urllib.request.urlopen(urllib.request.Request(link), timeout=1800) as resp:
            body = resp.read().decode('utf-8-sig', errors='replace')

        rd = csv.reader(io.StringIO(body))
        h = next(rd)
        if header is None:
            header = h
        elif h != header:
            raise RuntimeError('%s/%s 表头与首批不一致' % (day, tag))
        si = [i for i, c in enumerate(h) if c == '店铺'][0]
        n = 0
        for row in rd:
            if len(row) < len(h):
                continue
            if row[si] == '':      # 末尾「总计」行
                continue
            rows.append(row)
            n += 1
        print('    %s %-5s %6d 行' % (day, tag, n), flush=True)
    return header, rows


def merge_into_zip(date_dir, header, rows):
    """把补拉的行合并进 date_dir/douyin_detail.zip（按整行去重）。"""
    dest = os.path.join(date_dir, 'douyin_detail.zip')
    old_rows = []
    if os.path.exists(dest):
        z = zipfile.ZipFile(dest)
        txt = z.read(z.namelist()[0]).decode('utf-8-sig', errors='replace')
        rd = csv.reader(io.StringIO(txt))
        old_header = next(rd)
        if old_header != header:
            raise RuntimeError('已有 douyin_detail.zip 表头与补拉结果不一致，停止合并')
        old_rows = list(rd)

    seen = set()
    merged = []
    for row in old_rows + rows:
        key = tuple(row)
        if key in seen:
            continue
        seen.add(key)
        merged.append(row)

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(merged)
    with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('1-抖快订单明细-抖音明细-merged.csv', buf.getvalue().encode('utf-8'))
    return len(old_rows), len(merged)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--from', dest='date_from', required=True)
    ap.add_argument('--to', dest='date_to', required=True)
    ap.add_argument('--data-dir', default=None,
                    help='合并进哪个数据目录的 douyin_detail.zip，默认 data/<今天>')
    args = ap.parse_args()

    d0 = datetime.date.fromisoformat(args.date_from)
    d1 = datetime.date.fromisoformat(args.date_to)
    date_dir = args.data_dir or os.path.join(
        BASE, 'data', datetime.datetime.now().strftime('%Y-%m-%d'))
    os.makedirs(date_dir, exist_ok=True)

    header, all_rows = None, []
    day = d0
    while day <= d1:
        ds = day.isoformat()
        print('  补拉 %s ...' % ds, flush=True)
        h, rows = export_day(ds)
        if header is None:
            header = h
        elif h != header:
            raise RuntimeError('不同日期的表头不一致')
        all_rows.extend(rows)
        day += datetime.timedelta(days=1)

    if not all_rows:
        print('没有补到任何数据')
        return
    old_n, new_n = merge_into_zip(date_dir, header, all_rows)
    print('\n补拉完成：原有 %d 行 + 补拉 %d 行 -> 合并后 %d 行'
          % (old_n, len(all_rows), new_n))
    print('数据目录: %s' % date_dir)


if __name__ == '__main__':
    main()
