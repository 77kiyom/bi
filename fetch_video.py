# -*- coding: utf-8 -*-
"""抓取「视频号」「小红书」两个渠道数据（按天，支持任意日期区间）。

数据源：BI 报告 37523「视频号&小红书明细(1)」
  视频号：页面 dashboardId=92179 → 商品粒度 c-1-35255-92179-mct1ooqr
          日期筛选器 c-1-35255-92179-mcsrje0l
  小红书：页面 dashboardId=101173 → 商品粒度 c-1-35255-101173-msrad235
          日期筛选器 c-1-35255-101173-msrad236

产出 video_data.json：
  {"meta": {...}, "channels": {"视频号": {...}, "小红书": {...}}}
  每个渠道：{"meta":{...}, "daily":{date:{组:[销售额,含税,销量]}}, "items":[[date,id,name,组,amt,qty]]}

用法：python fetch_video.py [--from 2026-10-01] [--to 2026-10-18] [--channel 小红书]
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
Q4_START = datetime.date(2026, 10, 1)
BJ_TZ = datetime.timezone(datetime.timedelta(hours=8))

CHANNELS = {
    '视频号': {
        'component': 'c-1-35255-92179-mct1ooqr',
        'filter': 'c-1-35255-92179-mcsrje0l',
        'group_map': {
            '床品床垫组': '家纺',
            '家具组': '家具百货组', '家居餐厨组': '家具百货组', '电器周边组': '家具百货组',
            '服配组': '服配',
            '羽绒组': '服配-羽绒',
        },
        'order': ['家纺', '家具百货组', '服配', '服配-羽绒'],
    },
    '小红书': {
        'component': 'c-1-35255-101173-msrad235',
        'filter': 'c-1-35255-101173-msrad236',
        'group_map': {   # 小红书只有家具百货组
            '家具组': '家具百货组', '家居餐厨组': '家具百货组', '电器周边组': '家具百货组',
        },
        'order': ['家具百货组'],
    },
}


def _num(v):
    s = str(v).replace(',', '').replace('%', '').strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def fetch_day(channel, day):
    cfg = CHANNELS[channel]
    d0 = day.isoformat()
    r = yc.api_post('/api/dash/report/getData', {
        'reportId': REPORT_ID, 'type': 'report', 'limit': 20000,
        'defaultFilters': {cfg['filter']: {
            'type': 'StaticTime',
            'minBound': d0 + ' 00:00:00',
            'maxBound': d0 + ' 24:00:00'}},   # 必须 24:00:00；23:59:59 单天返回空
    }, timeout=180)
    if r.get('code') != 200:
        raise RuntimeError('%s getData 失败 %s: %s'
                           % (channel, d0, json.dumps(r, ensure_ascii=False)[:200]))
    comp = None
    for c in (r.get('result') or []):
        if c.get('componentId') == cfg['component']:
            comp = c
            break
    if comp is None:
        return channel, d0, {}, []
    ns = comp.get('normalSheetData') or []
    if not ns:
        return channel, d0, {}, []
    hdr = ns[0]
    ix = {k: i for i, k in enumerate(hdr)}
    agg, items = {}, []
    for row in ns[1:]:
        if not row or row[0] == '总计':
            continue
        g = cfg['group_map'].get(row[ix['group_name']])
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
    return channel, d0, agg, items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--from', dest='dfrom', default=Q4_START.isoformat())
    ap.add_argument('--to', dest='dto', default=None)
    ap.add_argument('--out', default=os.path.join(BASE, 'video_data.json'))
    ap.add_argument('--channel', default=None, help='只抓某个渠道（视频号/小红书）')
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

    channels = [args.channel] if args.channel else list(CHANNELS.keys())
    yc.get_token()

    out_channels = {}
    for ch in channels:
        print('%s：抓取 %s ~ %s，共 %d 天' % (ch, d_from, d_to, len(days)), flush=True)
        daily, items = {}, []
        ok = fail = 0
        with cf.ThreadPoolExecutor(max_workers=4) as ex:
            futs = {ex.submit(fetch_day, ch, day): day for day in days}
            for fu in cf.as_completed(futs):
                day = futs[fu]
                try:
                    _, d0, agg, its = fu.result()
                    if agg:
                        daily[d0] = {g: [round(v[0], 2), round(v[1], 2), round(v[2])]
                                     for g, v in agg.items()}
                    items.extend(its)
                    ok += 1
                except Exception as e:
                    fail += 1
                    print('  [失败] %s %s: %s' % (day, type(e).__name__, str(e)[:120]), flush=True)
        print('  完成：成功 %d 天，失败 %d 天，商品行 %d' % (ok, fail, len(items)), flush=True)
        out_channels[ch] = {
            'meta': {
                'updated_at': datetime.datetime.now(BJ_TZ).strftime('%Y-%m-%d %H:%M'),
                'data_from': min(daily) if daily else None,
                'data_to': max(daily) if daily else None,
                'channel': ch,
                'groups': CHANNELS[ch]['order'],
            },
            'daily': daily,
            'items': items,
        }

    out = {'meta': {'updated_at': datetime.datetime.now(BJ_TZ).strftime('%Y-%m-%d %H:%M')},
           'channels': out_channels}
    json.dump(out, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False)
    print('已写入:', args.out, '(%.1f KB)' % (os.path.getsize(args.out) / 1024))


if __name__ == '__main__':
    main()
