# -*- coding: utf-8 -*-
"""看板数据汇总：四组（家纺/家具百货/服配/短视频）× 日期 × 渠道（抖音）。

产出 dashboard_data.json，供 HTML 看板内嵌使用。
口径与 run_group.py 完全一致（26年分组用 (主播ID,店铺) 联合键；含税空白用 _num 安全转换）。

用法：
  python build_dashboard_data.py --data-dir data/2026-10-15 --out dashboard_data.json
"""
import argparse
import csv
import datetime
import io
import json
import os
import re
import zipfile
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATE = '2026-10-15'
Q4_START = datetime.date(2026, 10, 1)
Q4_END = datetime.date(2026, 12, 31)
# 统一按北京时间（UTC+8）取「今天/现在」：本地与 GitHub Actions(UTC 时钟) 下结果都正确
BJ_TZ = datetime.timezone(datetime.timedelta(hours=8))

# 四个组定义：name -> (group_names, mode, use_keep, extra_exclude_file)
GROUP_DEFS = [
    ('家纺', {'床品床垫组'}, 'exclude', True, None),
    ('家具百货组', {'家具组', '家居餐厨组', '电器周边组'}, 'exclude', True,
     'data/furniture_extra_exclude.json'),
    ('服配', {'服配组', '服装非羽绒组', '运动出行组'}, 'exclude', True, None),
    ('服配-羽绒', {'羽绒组'}, 'exclude', True, None),
    ('短视频', {'家具组', '家居餐厨组', '床品床垫组', '服装非羽绒组', '服配组',
             '未归类', '电器周边组', '羽绒组', '运动出行组'}, 'include', False, None),
]
KEEP_GROUPS = {'商务组', '其他', '待匹配'}

# 达成率分组（抖音渠道）：显示名 -> (成员组列表, 目标 {'week','month','quarter'})，单位元。
# 来源：用户提供的 Q4 时间进度表（2026年W41）。
# 服配与服配-羽绒【各有独立目标，不再合计】：
#   服配      = 图片原目标（周 73.2 / 月 324.3 / 季 972.9 万）
#   服配-羽绒 = 季度 753.94 万，月/周按季度目标平均折算（月=季/3，周=季/13）
_YURONG_Q = 7539400
ACH_GROUPS = [
    ('家纺',       ['家纺'],             {'week': 1005000, 'month': 4449000, 'quarter': 11012000}),
    ('家具百货组', ['家具百货组'],       {'week': 242000,  'month': 1072000, 'quarter': 2654000}),
    ('服配',       ['服配'],             {'week': 732000,  'month': 3243000, 'quarter': 9729000}),
    ('服配-羽绒',  ['服配-羽绒'],        {'week': round(_YURONG_Q / 13), 'month': round(_YURONG_Q / 3), 'quarter': _YURONG_Q}),
    ('短视频',     ['短视频'],           {'week': 180000,  'month': 799000,  'quarter': 2246000}),
]

# ===== 视频号渠道（数据来自 fetch_video.py 产出的 video_data.json）=====
# 目标（用户 2026-10-19 提供）：周/月/季；服配-羽绒暂空
VIDEO_TARGETS = {
    '家纺':       {'week': 56000,  'month': 247000, 'quarter': 612000},
    '家具百货组': {'week': 69000,  'month': 306000, 'quarter': 758000},
    '服配':       {'week': 92000,  'month': 405000, 'quarter': 1216000},
    '服配-羽绒':  {'week': None,   'month': None,   'quarter': None},
}
# 短视频组只有抖音渠道 → 视频号不含短视频
VIDEO_GROUPS = ['家纺', '家具百货组', '服配', '服配-羽绒']


def _num(v):
    if v is None:
        return 0.0
    s = str(v).strip().replace(',', '')
    if s == '':
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def load_flybook():
    d = json.load(open(os.path.join(BASE, 'uid_sheet.json'), encoding='utf-8'))
    uids, tuans = set(), set()
    for l in d['data']['annotated_csv'].split('\n')[1:]:
        l = re.sub(r'^\[row=\d+\]\s*', '', l)
        p = l.split(',')
        if len(p) > 1 and p[1].strip():
            uids.add(p[1].strip())
        if len(p) >= 3 and p[2].strip():
            tuans.add(p[2].strip())
    return uids, tuans


def load_combo_group(data_dir):
    z = zipfile.ZipFile(os.path.join(data_dir, 'sales_detail.zip'))
    t = z.read(z.namelist()[0]).decode('utf-8-sig', errors='replace')
    r = csv.reader(io.StringIO(t))
    h = next(r)
    ai, gi, si, am = h.index('主播ID'), h.index('26年分组'), h.index('店铺'), h.index('销售额')
    combo = defaultdict(lambda: defaultdict(float))
    for row in r:
        if not row[ai]:
            continue
        combo[(row[ai], row[si])][row[gi]] += _num(row[am])
    return {k: max(g.items(), key=lambda x: x[1])[0] for k, g in combo.items()}


def load_items(data_dir, all_groups):
    items = {}
    with open(os.path.join(data_dir, 'product_table_full.csv'), encoding='utf-8-sig') as f:
        r = csv.reader(f)
        h = next(r)
        pg, pi, pn = h.index('group'), h.index('item_id'), h.index('item_name')
        for row in r:
            if row[pg] in all_groups:
                try:
                    items[str(int(float(row[pi])))] = (row[pn], row[pg])
                except ValueError:
                    pass
    return items


def week_bounds(d):
    """返回 d 所在周（周日~周六）的周日/周六。"""
    sun = d - datetime.timedelta(days=(d.weekday() + 1) % 7)
    return sun, sun + datetime.timedelta(days=6)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data-dir', default=None)
    ap.add_argument('--out', default=None)
    ap.add_argument('--date-from', default='2026-10-01')
    ap.add_argument('--date-to', default=None)
    args = ap.parse_args()
    data_dir = args.data_dir or os.path.join(BASE, 'data', DEFAULT_DATE)
    out_path = args.out or os.path.join(BASE, 'dashboard_data.json')

    uids, _ = load_flybook()
    combo_group = load_combo_group(data_dir)
    all_groups = set()
    for _, gs, _, _, _ in GROUP_DEFS:
        all_groups |= gs
    items = load_items(data_dir, all_groups)

    # 额外排除
    extra_excl = {}
    for name, gs, mode, use_keep, exf in GROUP_DEFS:
        if exf:
            p = exf if os.path.isabs(exf) else os.path.join(BASE, exf)
            if os.path.exists(p):
                extra_excl[name] = set(str(x).strip() for x in json.load(open(p, encoding='utf-8')))

    z = zipfile.ZipFile(os.path.join(data_dir, 'douyin_detail.zip'))
    rr = csv.reader(io.StringIO(z.read(z.namelist()[0]).decode('utf-8-sig')))
    dh = next(rr)
    di, ii, ai = dh.index('下单日期'), dh.index('item_id'), dh.index('主播ID')
    si, ti, qi = dh.index('销售额'), dh.index('含税收入_财务'), dh.index('销量')
    shop_idx = [i for i, c in enumerate(dh) if c == '店铺'][0]

    # 结构: data[组名]['daily'][日期] = [amt, tax, qty]
    #       data[组名]['item'][item_id] = [amt, tax, qty]
    #       data[组名]['item_daily'][item_id][日期] = [amt, tax, qty]
    store = {name: {'daily': defaultdict(lambda: [0.0, 0.0, 0.0]),
                    'item': defaultdict(lambda: [0.0, 0.0, 0.0]),
                    'item_daily': defaultdict(lambda: defaultdict(lambda: [0.0, 0.0, 0.0]))}
             for name, *_ in GROUP_DEFS}
    all_dates = set()

    for row in rr:
        dt = row[di]
        if not (args.date_from <= dt <= (args.date_to or '9999-12-31')):
            continue
        if row[ii] not in items:
            continue
        a = row[ai]
        g = combo_group.get((a, row[shop_idx]), '')
        s = _num(row[si]); t = _num(row[ti]); q = _num(row[qi])
        all_dates.add(dt)
        for name, gs, mode, use_keep, _ in GROUP_DEFS:
            if items[row[ii]][1] not in gs:
                continue
            if use_keep and g not in KEEP_GROUPS:
                continue
            if mode == 'exclude':
                if a in uids or a in extra_excl.get(name, set()):
                    continue
            else:  # include
                if a not in uids:
                    continue
            st = store[name]
            st['daily'][dt][0] += s; st['daily'][dt][1] += t; st['daily'][dt][2] += q
            st['item'][row[ii]][0] += s; st['item'][row[ii]][1] += t; st['item'][row[ii]][2] += q
            st['item_daily'][row[ii]][dt][0] += s
            st['item_daily'][row[ii]][dt][1] += t
            st['item_daily'][row[ii]][dt][2] += q

    today = datetime.datetime.now(BJ_TZ).date()
    w_sun, w_sat = week_bounds(today)
    m_start = today.replace(day=1)
    if today.month == 12:
        m_end = today.replace(month=12, day=31)
    else:
        m_end = today.replace(month=today.month + 1, day=1) - datetime.timedelta(days=1)

    def rng_sum(daily, d0, d1):
        tot = [0.0, 0.0, 0.0]
        for k, v in daily.items():
            if d0 <= k <= d1:
                tot[0] += v[0]; tot[1] += v[1]; tot[2] += v[2]
        return tot

    groups_out = []
    for name, gs, mode, use_keep, _ in GROUP_DEFS:
        st = store[name]
        daily = {k: v for k, v in sorted(st['daily'].items())}
        top_items = []
        for iid, v in st['item'].items():
            if v[0] >= 10000:
                top_items.append({'item_id': iid, 'name': items[iid][0],
                                  'group_name': items[iid][1],
                                  'amt': round(v[0], 2), 'qty': round(v[2])})
        top_items.sort(key=lambda x: -x['amt'])
        # 供「按时间区间筛选 Top 单品」用：只保留全期 >=1000 的商品的每日明细，控制体积
        item_daily_out = {}
        for iid, dv in st['item_daily'].items():
            if st['item'][iid][0] >= 1000:
                item_daily_out[iid] = {
                    k: [round(v[0], 2), round(v[1], 2), round(v[2])] for k, v in sorted(dv.items())}
        groups_out.append({
            'name': name,
            'group_names': sorted(gs),
            'mode': '只勾选飞书达人' if mode == 'include' else '排除飞书达人',
            'daily': {k: [round(v[0], 2), round(v[1], 2), round(v[2])] for k, v in daily.items()},
            'week_cur': [round(x, 2) for x in rng_sum(st['daily'], w_sun.isoformat(), w_sat.isoformat())],
            'week_prev': [round(x, 2) for x in rng_sum(
                st['daily'],
                (w_sun - datetime.timedelta(days=7)).isoformat(),
                (w_sat - datetime.timedelta(days=7)).isoformat())],
            'month': [round(x, 2) for x in rng_sum(st['daily'], m_start.isoformat(), m_end.isoformat())],
            'quarter': [round(x, 2) for x in rng_sum(st['daily'], Q4_START.isoformat(), Q4_END.isoformat())],
            'top_items': top_items,
            'item_daily': item_daily_out,
            'target': {'week': None, 'month': None, 'quarter': None},
        })

    meta = {
        'updated_at': datetime.datetime.now(BJ_TZ).strftime('%Y-%m-%d %H:%M'),
        'today': today.isoformat(),
        'data_from': min(all_dates) if all_dates else None,
        'data_to': max(all_dates) if all_dates else None,
        'channels': ['抖音'],
        'active_channel': '抖音',
        'quarter': {'label': 'Q4', 'start': Q4_START.isoformat(), 'end': Q4_END.isoformat(),
                    'elapsed': (today - Q4_START).days + 1,
                    'total': (Q4_END - Q4_START).days + 1},
        'week': {'start': w_sun.isoformat(), 'end': w_sat.isoformat(),
                 'elapsed': (today - w_sun).days + 1, 'total': 7},
        'month': {'label': '%d月' % today.month, 'start': m_start.isoformat(), 'end': m_end.isoformat(),
                  'elapsed': today.day, 'total': (m_end - m_start).days + 1},
    }
    # 达成率分组：把成员组的业绩合计，对比图片目标
    by_name = {g['name']: g for g in groups_out}
    ach_out = []
    for disp, members, target in ACH_GROUPS:
        actual = {'week_cur': 0.0, 'week_prev': 0.0, 'month': 0.0, 'quarter': 0.0}
        for m in members:
            g = by_name.get(m)
            if not g:
                continue
            actual['week_cur'] += g['week_cur'][0]
            actual['week_prev'] += g['week_prev'][0]
            actual['month'] += g['month'][0]
            actual['quarter'] += g['quarter'][0]
        ach_out.append({'name': disp, 'members': members, 'target': target,
                        'actual': {k: round(v, 2) for k, v in actual.items()}})

    # ===== 视频号渠道 =====
    video_out = None
    vp = os.path.join(BASE, 'video_data.json')
    if os.path.exists(vp):
        v = json.load(open(vp, encoding='utf-8'))
        vgroups = []
        for gname in VIDEO_GROUPS:
            daily = {}
            for date, gs in (v.get('daily') or {}).items():
                if gname in gs:
                    daily[date] = gs[gname]
            item_daily = {}
            for row in (v.get('items') or []):
                date, iid, name, g, amt, qty = row
                if g != gname:
                    continue
                d = item_daily.setdefault(iid, {'name': name, 'daily': {}})
                d['daily'][date] = [amt, 0.0, qty]
            top = []
            for iid, d in item_daily.items():
                tot = sum(x[0] for x in d['daily'].values())
                if tot >= 1000:
                    top.append({'item_id': iid, 'name': d['name'], 'group_name': gname,
                                'amt': round(tot, 2),
                                'qty': round(sum(x[2] for x in d['daily'].values()))})
            top.sort(key=lambda x: -x['amt'])
            vgroups.append({
                'name': gname, 'group_names': [gname], 'mode': '视频号',
                'daily': {k: [round(x[0], 2), round(x[1], 2), round(x[2])]
                          for k, x in sorted(daily.items())},
                'week_cur': [round(x, 2) for x in rng_sum(daily, w_sun.isoformat(), w_sat.isoformat())],
                'week_prev': [round(x, 2) for x in rng_sum(
                    daily,
                    (w_sun - datetime.timedelta(days=7)).isoformat(),
                    (w_sat - datetime.timedelta(days=7)).isoformat())],
                'month': [round(x, 2) for x in rng_sum(daily, m_start.isoformat(), m_end.isoformat())],
                'quarter': [round(x, 2) for x in rng_sum(daily, Q4_START.isoformat(), Q4_END.isoformat())],
                'top_items': top,
                'item_daily': {iid: {k: [round(x[0], 2), 0.0, round(x[2])]
                                     for k, x in sorted(d['daily'].items())}
                               for iid, d in item_daily.items()},
                'target': VIDEO_TARGETS.get(gname, {'week': None, 'month': None, 'quarter': None}),
            })
        vach = []
        for g in vgroups:
            vach.append({'name': g['name'], 'members': [g['name']], 'target': g['target'],
                         'actual': {'week_cur': g['week_cur'][0], 'week_prev': g['week_prev'][0],
                                    'month': g['month'][0], 'quarter': g['quarter'][0]}})
        video_out = {'meta': v.get('meta'), 'groups': vgroups, 'ach': vach}

    out = {'meta': meta, 'groups': groups_out, 'ach': ach_out, 'video': video_out}
    json.dump(out, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('已生成:', out_path)
    print('  数据区间: %s ~ %s' % (meta['data_from'], meta['data_to']))
    for g in groups_out:
        print('  %-8s 周(本周) %10.0f | 上周 %10.0f | 月 %10.0f | 季 %10.0f | top品 %d' % (
            g['name'], g['week_cur'][0], g['week_prev'][0], g['month'][0],
            g['quarter'][0], len(g['top_items'])))


if __name__ == '__main__':
    main()
