# -*- coding: utf-8 -*-
"""抓取「视频号」渠道数据（按天，支持任意日期区间）。

数据源：BI 报告 37523「视频号&小红书明细(1)」→ 页面「视频号分组」(dashboardId=92179)
       → 组件「商品粒度粒度」c-1-35255-92179-mct1ooqr（含 group_name）
日期控制：报告级日期筛选器 c-1-35255-92179-mcsrje0l（defaultFilters 传 StaticTime）

产出 video_data.json：
  {
    "meta": {"updated_at","data_from","data_to"},
    "daily": {"2026-10-01": {"家纺": [销售额,含税收入,销量], ...}, ...},
    "items": [["2026-10-01","item_id","item_name","组","销售额","销量"], ...]
  }

用法：python fetch_video.py [--from 2026-10-01] [--to 2026-10-18] [--out video_data.json]
"""
import argparse
import concurrent.futures as cf
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import youdata_client as yc

BASE = os.path.dirname(os.path.abspath(__file__))
REPORT_ID = 37523
COMPONENT_ID = 'c-1-35255-92179-mct1ooqr'     # 视频号分组 · 商品粒度粒度
DATE_FILTER_ID = 'c-1-35255-92179-mcsrje0l'  # 视频号分组的日期筛选器（实测唯一生效）
Q4_START = datetime.date(2026, 10, 1)
BJ_TZ = datetime.timezone(datetime.timedelta(hours=8))

GROUP_MAP = {
    '床品床垫组': '家纺',
    '家具组': '家具百货组', '家居餐厨组': '家具百货组', '电器周边组': '家具百货组',
    '服配组': '服配',
    '羽绒组': '服配-羽绒',
}
GROUP_ORDER = ['家纺', '家具百货组', '服配', '服配-羽绒']


def _num(v):
    s = str(v).replace(',', '').replace('%', '').strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def fetch_day(day):
    """抓某一天：返回 (日期, {组: [销售额,含税,销量]}, [item行])"""
    d0 = day.isoformat()
    r = yc.api_post('/api/dash/report/getData', {
        'reportId': REPORT_ID, 'type': 'report', 'limit': 20000,
        'defaultFilters': {DATE_FILTER_ID: {
            'type': 'StaticTime',
            'minBound': d0 + ' 00:00:00',
            'maxBound': d0 + ' 24:00:00'}},
    }, timeout=180)
    if r.get('code') != 200:
        raise RuntimeError('getData 失败 %s: %s' % (d0, json.dumps(r, ensure_ascii=False)[:200]))
    comp = None
    for c in (r.get('result') or []):
        if c.get('componentId') == COMPONENT_ID:
            comp = c
            break
    if comp is None:
        return d0, {}, []
    ns = comp.get('normalSheetData') or []
    if not ns:
        return d0, {}, []
    hdr = ns[0]
    ix = {k: i for i, k in enumerate(hdr)}
    agg, items = {}, []
    for row in ns[1:]:
        if not row or row[0] == '总计':
            continue
        g = GROUP_MAP.get(row[ix['group_name']])
        if not g:
            continue
        amt = _num(row[ix['销售额']])
        tax = _num(row[ix['含税收入']])
        qty = _num(row[ix['销量']])
        a = agg.setdefault(g, [0.0, 0.0, 0.0])
        a[0] += amt; a[1] += tax; a[2] += qty
        if amt > 0:
            items.append([d0, str(row[ix['item_id']]), str(row[ix['item_name']]),
                          g, round(amt, 2), round(qty)])
    return d0, agg, items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--from', dest='dfrom', default=Q4_START.isoformat())
    ap.add_argument('--to', dest='dto', default=None)
    ap.add_argument('--out', default=os.path.join(BASE, 'video_data.json'))
    args = ap.parse_args()

    today = datetime.datetime.now(BJ_TZ).date()
    d_from = datetime.date.fromisoformat(args.dfrom)
    d_to = datetime.date.fromisoformat(args.dto) if args.dto else today
    if d_to > today:
        d_to = today

    days = []
    d = d_from
    while d <= d_to:
        days.append(d)
        d += datetime.timedelta(days=1)
    print('视频号：抓取 %s ~ %s，共 %d 天' % (d_from, d_to, len(days)), flush=True)

    yc.get_token()  # 预热 token 缓存，避免多线程竞争

    daily, items = {}, []
    ok = fail = 0
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(fetch_day, day): day for day in days}
        for fu in cf.as_completed(futs):
            day = futs[fu]
            try:
                d0, agg, its = fu.result()
                if agg:
                    daily[d0] = {g: [round(v[0], 2), round(v[1], 2), round(v[2])]
                                 for g, v in agg.items()}
                items.extend(its)
                ok += 1
            except Exception as e:
                fail += 1
                print('  [失败] %s %s: %s' % (day, type(e).__name__, str(e)[:120]), flush=True)
    print('完成：成功 %d 天，失败 %d 天，商品行 %d' % (ok, fail, len(items)), flush=True)

    out = {
        'meta': {
            'updated_at': datetime.datetime.now(BJ_TZ).strftime('%Y-%m-%d %H:%M'),
            'data_from': min(daily) if daily else None,
            'data_to': max(daily) if daily else None,
            'channel': '视频号',
            'groups': GROUP_ORDER,
        },
        'daily': daily,
        'items': items,
    }
    json.dump(out, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False)
    print('已写入:', args.out, '(%.1f KB)' % (os.path.getsize(args.out) / 1024))


if __name__ == '__main__':
    main()
