# -*- coding: utf-8 -*-
"""抓取「视频号」「小红书」「快手」三个渠道数据（按天，支持任意日期区间）。

两种抓取模式：
  A. 按天抓「商品粒度/商品明细」汇总表（视频号、小红书）
     - 每天调一次 getData，用 defaultFilters 控制日期
  B. 订单级抓取（快手，更快、销量准确）
     - 先拉「商品明细」建 item_id -> 组 对照表
     - 再一次 asyncExportExcel 导出「快手明细」（订单级，带日期）
     - 本地按 日期 × 组 汇总

数据源：
  报告 37523「视频号&小红书明细(1)」
    视频号：c-1-35255-92179-mct1ooqr，日期筛选器 c-1-35255-92179-mcsrje0l
    小红书：c-1-35255-101173-msrad235，日期筛选器 c-1-35255-101173-msrad236
  报告 36928「抖快渠道销售大盘(1)」
    快手：商品明细 c-1-18047-49252-li83fids（对照表）
          快手明细 c-1-18047-45005-ktayxmbp（订单级）

产出 video_data.json：
  {"meta": {...}, "channels": {"视频号": {...}, "小红书": {...}, "快手": {...}}}
  每个渠道：{"meta":{...}, "daily":{date:{组:[销售额,含税,销量]}}, "items":[[date,id,name,组,amt,qty]]}

用法：python fetch_video.py [--from 2026-10-01] [--to 2026-10-18] [--channel 快手]
"""
import argparse
import concurrent.futures as cf
import csv
import datetime
import io
import json
import os
import sys
import time
import urllib.request
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import youdata_client as yc

BASE = os.path.dirname(os.path.abspath(__file__))
Q4_START = datetime.date(2026, 10, 1)
BJ_TZ = datetime.timezone(datetime.timedelta(hours=8))

STANDARD_GROUP_MAP = {
    '床品床垫组': '家纺',
    '家具组': '家具百货组', '家居餐厨组': '家具百货组', '电器周边组': '家具百货组',
    '服配组': '服配',
    '羽绒组': '服配-羽绒',
}
FOUR_GROUPS = ['家纺', '家具百货组', '服配', '服配-羽绒']

CHANNELS = {
    '视频号': {
        'mode': 'daily',
        'report': 37523,
        'component': 'c-1-35255-92179-mct1ooqr',
        'filter': 'c-1-35255-92179-mcsrje0l',
        'limit': 20000,
        'group_map': STANDARD_GROUP_MAP,
        'order': FOUR_GROUPS,
    },
    '小红书': {
        'mode': 'daily',
        'report': 37523,
        'component': 'c-1-35255-101173-msrad235',
        'filter': 'c-1-35255-101173-msrad236',
        'limit': 20000,
        'group_map': {   # 小红书只有家具百货组
            '家具组': '家具百货组', '家居餐厨组': '家具百货组', '电器周边组': '家具百货组',
        },
        'order': ['家具百货组'],
    },
    '快手': {
        'mode': 'order',
        'report': 36928,
        'map_component': 'c-1-18047-49252-li83fids',    # 快手分组·商品明细（item_id + group_name）
        'order_component': 'c-1-18047-45005-ktayxmbp',  # 快手明细（订单级）
        'map_limit': 600,
        'date_col': '日期', 'item_col': 'item_id', 'name_col': '商品名称',
        'amt_col': '销售额', 'tax_col': '含税收入-财务', 'qty_col': '销量',
        'group_map': STANDARD_GROUP_MAP,
        'order': FOUR_GROUPS,
    },
}


def _num(v):
    s = str(v).replace(',', '').replace('%', '').strip()
    mult = 1.0
    if s.endswith('万'):
        mult = 10000.0
        s = s[:-1]
    try:
        return float(s) * mult
    except ValueError:
        return 0.0


def fetch_day(channel, day):
    """模式 A：抓某一天的商品粒度汇总表。"""
    cfg = CHANNELS[channel]
    d0 = day.isoformat()
    last_err = None
    r = None
    for attempt in range(1, 4):   # 大报表偶发 IncompleteRead，重试 3 次
        try:
            r = yc.api_post('/api/dash/report/getData', {
                'reportId': cfg['report'], 'type': 'report', 'limit': cfg.get('limit', 20000),
                'defaultFilters': {cfg['filter']: {
                    'type': 'StaticTime',
                    'minBound': d0 + ' 00:00:00',
                    'maxBound': d0 + ' 24:00:00'}},   # 必须 24:00:00；23:59:59 单天返回空
            }, timeout=180)
            break
        except Exception as e:
            last_err = e
            r = None
            time.sleep(2 * attempt)
    if r is None:
        raise last_err if last_err else RuntimeError('getData 无响应')
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
        qty = _num(row[ix.get('qty_col', '销量')])
        a = agg.setdefault(g, [0.0, 0.0, 0.0])
        a[0] += amt; a[1] += tax; a[2] += qty
        if amt > 0:
            items.append([d0, str(row[ix['item_id']]),
                          str(row[ix[cfg.get('name_col', 'item_name')]]),
                          g, round(amt, 2), round(qty)])
    return channel, d0, agg, items


def _export_component(report, component):
    """异步导出组件，返回 CSV 文本。"""
    res = yc.api_post('/api/dash/report/asyncExportExcel', {
        'reportId': report, 'componentId': component,
        'exportType': 'csv', 'excelSplitLimit': 1000000})
    if res.get('code') != 200:
        raise RuntimeError('创建导出任务失败: %s' % json.dumps(res, ensure_ascii=False)[:200])
    tid = res['result']
    for _ in range(90):
        rr = yc.api_get('/api/dash/exportExcelTask/get', {'id': tid})
        st = (rr.get('result') or {}).get('status')
        if st == 'success':
            break
        if st in ('fail', 'expired'):
            raise RuntimeError('导出任务失败: %s' % st)
        time.sleep(5)
    else:
        raise RuntimeError('导出任务轮询超时')
    url = '%s/api/dash/exportExcelTask/download?id=%s&token=%s' % (
        yc.BASE_URL, tid, yc.get_token())
    data = urllib.request.urlopen(url, timeout=900).read()
    tmp = os.path.join(BASE, '_tmp_export.zip')
    open(tmp, 'wb').write(data)
    try:
        zf = zipfile.ZipFile(tmp)
        return zf.read(zf.namelist()[0]).decode('utf-8-sig', errors='replace')
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def fetch_order_channel(channel, d_from, d_to):
    """模式 B：订单级抓取（快手）。"""
    cfg = CHANNELS[channel]
    # 1) 商品明细 → item_id -> 组 对照表
    r = yc.api_post('/api/dash/report/getData', {
        'reportId': cfg['report'], 'type': 'report',
        'limit': cfg.get('map_limit', 600)}, timeout=240)
    ns = None
    for c in (r.get('result') or []):
        if c.get('componentId') == cfg['map_component']:
            ns = c.get('normalSheetData') or []
            break
    if not ns:
        raise RuntimeError('未取到商品明细（对照表）')
    h = ns[0]
    ix = {k: i for i, k in enumerate(h)}
    imap = {}
    for row in ns[1:]:
        if not row or row[0] == '总计':
            continue
        g = cfg['group_map'].get(row[ix['group_name']])
        if g:
            imap[str(row[ix['item_id']])] = g
    print('   对照表 item 数: %d' % len(imap), flush=True)

    # 2) 导出订单明细
    raw = _export_component(cfg['report'], cfg['order_component'])
    rd = csv.reader(io.StringIO(raw))
    h2 = next(rd)
    ix2 = {k: i for i, k in enumerate(h2)}

    # 3) 按 日期 × 组 汇总
    daily = {}
    items = {}
    n = 0
    lo, hi = d_from.isoformat(), d_to.isoformat()
    for row in rd:
        d = row[ix2[cfg['date_col']]].strip()
        if len(d) != 10 or d[4] != '-' or not (lo <= d <= hi):
            continue
        iid = str(row[ix2[cfg['item_col']]]).strip()
        g = imap.get(iid)
        if not g:
            continue
        n += 1
        amt = _num(row[ix2[cfg['amt_col']]])
        tax = _num(row[ix2[cfg['tax_col']]])
        qty = _num(row[ix2[cfg['qty_col']]])
        a = daily.setdefault(d, {}).setdefault(g, [0.0, 0.0, 0.0])
        a[0] += amt; a[1] += tax; a[2] += qty
        k = (d, iid)
        it = items.get(k)
        if it is None:
            it = items[k] = [d, iid, str(row[ix2[cfg['name_col']]]), g, 0.0, 0.0]
        it[4] += amt
        it[5] += qty

    print('   有效订单行: %d | 覆盖日期: %d' % (n, len(daily)), flush=True)
    daily = {d: {g: [round(v[0], 2), round(v[1], 2), round(v[2])] for g, v in gs.items()}
             for d, gs in daily.items()}
    items_out = [[v[0], v[1], v[2], v[3], round(v[4], 2), round(v[5])]
                 for v in items.values()]
    return daily, items_out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--from', dest='dfrom', default=Q4_START.isoformat())
    ap.add_argument('--to', dest='dto', default=None)
    ap.add_argument('--out', default=os.path.join(BASE, 'video_data.json'))
    ap.add_argument('--channel', default=None, help='只抓某个渠道（视频号/小红书/快手）')
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
    # 只抓单个渠道时，合并进已有文件（不覆盖其他渠道）
    if args.channel and os.path.exists(args.out):
        try:
            old = json.load(open(args.out, encoding='utf-8'))
            out_channels = old.get('channels') or {}
        except Exception:
            out_channels = {}

    for ch in channels:
        cfg = CHANNELS[ch]
        if cfg.get('mode') == 'order':
            print('%s：订单级抓取 %s ~ %s' % (ch, d_from, d_to), flush=True)
            try:
                daily, items = fetch_order_channel(ch, d_from, d_to)
            except Exception as e:
                print('  [失败] %s: %s' % (type(e).__name__, str(e)[:150]), flush=True)
                daily, items = {}, []
        else:
            print('%s：按天抓取 %s ~ %s，共 %d 天' % (ch, d_from, d_to, len(days)), flush=True)
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
                        print('  [失败] %s %s: %s'
                              % (day, type(e).__name__, str(e)[:120]), flush=True)
            print('  完成：成功 %d 天，失败 %d 天，商品行 %d' % (ok, fail, len(items)), flush=True)

        out_channels[ch] = {
            'meta': {
                'updated_at': datetime.datetime.now(BJ_TZ).strftime('%Y-%m-%d %H:%M'),
                'data_from': min(daily) if daily else None,
                'data_to': max(daily) if daily else None,
                'channel': ch,
                'groups': cfg['order'],
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
