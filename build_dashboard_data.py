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
    ('家纺', {'床品床垫组', '家纺组'}, 'exclude', True, None),
    ('家具百货组', {'家具组', '家居餐厨组', '电器周边组'}, 'exclude', True,
     'data/furniture_extra_exclude.json'),
    ('服配', {'服配组', '服装非羽绒组', '运动出行组'}, 'exclude', True, None),
    ('服配-羽绒', {'羽绒组'}, 'exclude', True, None),
    ('短视频', {'家具组', '家居餐厨组', '床品床垫组', '家纺组', '服装非羽绒组', '服配组',
             '未归类', '电器周边组', '羽绒组', '运动出行组'}, 'include', False, None),
]
KEEP_GROUPS = {'商务组', '其他', '待匹配'}

# 爆品榜：按商品名称关键词匹配（跨组统计，不受 GROUP_DEFS 限制）
# (展示用渠道组, 爆品展示名, 关键词列表)
BOOM_ITEMS = [
    ('家纺',      '热力被',        ['热力被']),
    ('家具百货组', 'C70 任意桌',     ['c70']),
    ('服配-羽绒',  '小胖子（泡芙）',  ['小胖子']),
    ('服配',      '保暖内衣',       ['保暖内衣', '保暖衣']),
]

# 爆品统计时沿用的目标组口径：(mode, use_keep)
BOOM_SPEC = {d[0]: (d[2], d[3]) for d in GROUP_DEFS}

# 商品表 group 名称别名（BI 侧改名时在此对齐，口径不变）
# 2026-10-21 起 BI 把「床品床垫组」改名为「家纺组」，商品 item_id 集合完全一致（67 个）
GROUP_ALIAS = {'家纺组': '床品床垫组'}

# 达成率分组（抖音渠道）：显示名 -> (成员组列表, 目标 {'week','month','quarter'})，单位元。
# 来源：用户提供的 Q4 时间进度表（2026年W41）。
# 服配与服配-羽绒【各有独立目标，不再合计】：
#   服配      = 图片原目标（周 73.2 / 月 324.3 / 季 972.9 万）
#   服配-羽绒 = 全渠道合计 7,312,313（731.23 万）= 抖音 300 万 + 快手 300 万 + 视频号 1,312,313
#               本看板「抖音」渠道取 300 万；月/周按季均摊（月=季/3，周=季/13）
_YURONG_Q = 3000000
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
    '服配-羽绒':  {'week': 100947, 'month': 437438, 'quarter': 1312313},
}
# 短视频组只有抖音渠道 → 视频号不含短视频
VIDEO_GROUPS = ['家纺', '家具百货组', '服配', '服配-羽绒']

# 快手渠道目标：仅服配-羽绒有（全渠道 753.94 万 = 抖音 300 + 快手 300 + 视频号 153.94）
KUAISHOU_TARGETS = {
    '家纺':       {'week': 56000,  'month': 247000, 'quarter': 612000},
    '家具百货组': {'week': 35000,  'month': 153000, 'quarter': 379000},
    '服配':       {'week': 92000,  'month': 405000, 'quarter': 1216000},
    '服配-羽绒':  {'week': 230769, 'month': 1000000, 'quarter': 3000000},
}


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
        if len(p) > 1 and p[1].strip() and p[0].strip():
            # 必须有账号名称：清单里曾混入一条空名记录（uid 818478288482676 =
            # 网易严选家纺官方旗舰店，官方自播号），会把直播成交算进短视频，故剔除
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


def load_boom_items(data_dir):
    """爆品：按商品名关键词匹配，**只取属于目标渠道组的链接**；
    若该组内一个链接都没有（BI 分组可能有误），回退到全部匹配链接并在日志里提示。"""
    p = os.path.join(data_dir, 'product_table_full.csv')
    if not os.path.exists(p):
        return {}
    members = {d[0]: set(d[1]) for d in GROUP_DEFS}
    cand = {}
    with open(p, encoding='utf-8-sig') as f:
        r = csv.reader(f); h = next(r)
        pi, pn, pg = h.index('item_id'), h.index('item_name'), h.index('group')
        for row in r:
            nm = row[pn] or ''
            grp = GROUP_ALIAS.get(row[pg].strip(), row[pg].strip())
            for bg, bl, kws in BOOM_ITEMS:
                if any(k.lower() in nm.lower() for k in kws):
                    try:
                        cand.setdefault((bg, bl), []).append((str(int(float(row[pi]))), grp))
                    except ValueError:
                        pass
                    break
    out = {}
    for (bg, bl), lst in cand.items():
        mem = members.get(bg, set())
        hit = [(iid, g) for iid, g in lst if g in mem]
        if hit:
            for iid, _ in hit:
                out[iid] = (bg, bl)
        else:
            print('  [提示] 爆品「%s」在「%s」组内没有链接，已回退统计全部链接（BI 归组=%s）'
                  % (bl, bg, '/'.join(sorted({g for _, g in lst})) or '无'))
            for iid, _ in lst:
                out[iid] = (bg, bl)
    return out


def load_items(data_dir, all_groups):
    items = {}
    with open(os.path.join(data_dir, 'product_table_full.csv'), encoding='utf-8-sig') as f:
        r = csv.reader(f)
        h = next(r)
        pg, pi, pn = h.index('group'), h.index('item_id'), h.index('item_name')
        for row in r:
            gname = GROUP_ALIAS.get(row[pg].strip(), row[pg].strip())
            if gname in all_groups:
                try:
                    items[str(int(float(row[pi])))] = (row[pn], gname)
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
    boom_by_item = load_boom_items(data_dir)
    # 改名预警：商品表里出现了 GROUP_DEFS 未覆盖的分组名（BI 侧改名会导致该组直接归零）
    _known = set()
    for _d in GROUP_DEFS:
        _known |= set(_d[1])
    _unknown = sorted({v[1] for v in items.values()} - _known)
    if _unknown:
        print('  [警告] 商品表里有未映射的分组名（可能导致该组数据为 0）:', _unknown)

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
    oi = dh.index('order_id')
    ani = dh.index('主播名称')
    shop_idx = [i for i, c in enumerate(dh) if c == '店铺'][0]

    # 结构: data[组名]['daily'][日期] = [amt, tax, qty]
    #       data[组名]['item'][item_id] = [amt, tax, qty]
    #       data[组名]['item_daily'][item_id][日期] = [amt, tax, qty]
    store = {name: {'daily': defaultdict(lambda: [0.0, 0.0, 0.0]),
                    'item': defaultdict(lambda: [0.0, 0.0, 0.0]),
                    'item_daily': defaultdict(lambda: defaultdict(lambda: [0.0, 0.0, 0.0]))}
             for name, *_ in GROUP_DEFS}
    all_dates = set()
    # 日报用：按日订单量（去重 order_id） + 达人日明细
    order_sets = defaultdict(set)
    anchors = {}   # 主播名称 -> {'id':..., 'daily': {date: [amt, qty]}}

    boom = {}
    for row in rr:
        dt = row[di]
        if not (args.date_from <= dt <= (args.date_to or '9999-12-31')):
            continue
        # 剔除小红书订单（抖音明细里 店铺='小红书' 的行属于小红书渠道，不计入抖音）
        if row[shop_idx] == '小红书':
            continue
        s = _num(row[si]); t = _num(row[ti]); q = _num(row[qi])
        a = row[ai]
        g = combo_group.get((a, row[shop_idx]), '')
        # 爆品榜：按商品名关键词统计，并沿用目标渠道组的业务口径（KEEP_GROUPS / uid 排除），
        # 否则会把非商务组主播（如直播组）也算进来，导致远超该组总量
        # 爆品榜：统一口径 —— 全渠道订单里按商品名关键词匹配，销量/含税直接相加
        bm = boom_by_item.get(row[ii])
        if bm:
            bd = boom.setdefault(bm, defaultdict(lambda: [0.0, 0.0, 0.0]))
            bd[dt][0] += s; bd[dt][1] += t; bd[dt][2] += q
        if row[ii] not in items:
            continue
        all_dates.add(dt)
        matched_main = False
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
            # 日报统计：只统计四个主组（短视频与其他组有重叠，排除）
            if name != '短视频' and not matched_main:
                matched_main = True
                order_sets[dt].add(row[oi])
                aname = row[ani].strip() or '（未知）'
                an = anchors.get(aname)
                if an is None:
                    an = anchors[aname] = {'id': a, 'daily': defaultdict(lambda: [0.0, 0.0, 0.0])}
                an['daily'][dt][0] += s
                an['daily'][dt][1] += t
                an['daily'][dt][2] += q

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
        tax = {'week_cur': 0.0, 'week_prev': 0.0, 'month': 0.0, 'quarter': 0.0}
        for m in members:
            g = by_name.get(m)
            if not g:
                continue
            actual['week_cur'] += g['week_cur'][0]
            actual['week_prev'] += g['week_prev'][0]
            actual['month'] += g['month'][0]
            actual['quarter'] += g['quarter'][0]
            tax['week_cur'] += g['week_cur'][1]
            tax['week_prev'] += g['week_prev'][1]
            tax['month'] += g['month'][1]
            tax['quarter'] += g['quarter'][1]
        ach_out.append({'name': disp, 'members': members, 'target': target,
                        'actual': {k: round(v, 2) for k, v in actual.items()},
                        'tax': {k: round(v, 2) for k, v in tax.items()}})

    # ===== 视频号 / 小红书渠道 =====
    video_out = None
    kuaishou_out = None
    vp = os.path.join(BASE, 'video_data.json')
    if os.path.exists(vp):
        v = json.load(open(vp, encoding='utf-8'))
        chs = v.get('channels') or {}
        # 爆品榜：补入 快手 / 视频号 / 小红书 的商品级数据，做成全渠道合计
        for _cd in chs.values():
            for _row in (_cd.get('items') or []):
                if len(_row) < 7:
                    continue
                _dt, _iid, _nm, _g, _amt, _tax, _qty = _row[:7]
                for _bg, _bl, _kws in BOOM_ITEMS:
                    if any(k.lower() in (_nm or '').lower() for k in _kws):
                        _bd = boom.setdefault((_bg, _bl), defaultdict(lambda: [0.0, 0.0, 0.0]))
                        _bd[_dt][0] += _amt
                        _bd[_dt][1] += _tax
                        _bd[_dt][2] += _qty
                        break

        def _build_channel(chdata, order, targets):
            res = []
            for gname in order:
                daily = {}
                for date, gs in (chdata.get('daily') or {}).items():
                    if gname in gs:
                        daily[date] = gs[gname]
                item_daily = {}
                for row in (chdata.get('items') or []):
                    date, iid, name, g, amt, tax, qty = row
                    if g != gname:
                        continue
                    d = item_daily.setdefault(iid, {'name': name, 'daily': {}})
                    d['daily'][date] = [amt, tax, qty]
                top = []
                for iid, d in item_daily.items():
                    tot = sum(x[0] for x in d['daily'].values())
                    if tot >= 1000:
                        top.append({'item_id': iid, 'name': d['name'], 'group_name': gname,
                                    'amt': round(tot, 2),
                                    'qty': round(sum(x[2] for x in d['daily'].values()))})
                top.sort(key=lambda x: -x['amt'])
                res.append({
                    'name': gname, 'group_names': [gname],
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
                    'item_daily': {iid: {k: [round(x[0], 2), round(x[1], 2), round(x[2])]
                                         for k, x in sorted(d['daily'].items())}
                                   for iid, d in item_daily.items()},
                    'target': (targets or {}).get(gname, {'week': None, 'month': None, 'quarter': None}),
                })
            return res

        vgroups = _build_channel(chs.get('视频号', {}), VIDEO_GROUPS, VIDEO_TARGETS)
        xhs_groups = _build_channel(chs.get('小红书', {}), ['家具百货组'], None)
        xhs_g = xhs_groups[0] if xhs_groups else None
        ks_groups = _build_channel(chs.get('快手', {}), VIDEO_GROUPS, KUAISHOU_TARGETS)

        # 达成率：家具百货组 = 视频号 + 小红书 合计（目标也是合计目标）
        vach = []
        for g in vgroups:
            act = {'week_cur': g['week_cur'][0], 'week_prev': g['week_prev'][0],
                   'month': g['month'][0], 'quarter': g['quarter'][0]}
            tax = {'week_cur': g['week_cur'][1], 'week_prev': g['week_prev'][1],
                   'month': g['month'][1], 'quarter': g['quarter'][1]}
            split = None
            if g['name'] == '家具百货组' and xhs_g:
                xact = {'week_cur': xhs_g['week_cur'][0], 'week_prev': xhs_g['week_prev'][0],
                        'month': xhs_g['month'][0], 'quarter': xhs_g['quarter'][0]}
                xtax = {'week_cur': xhs_g['week_cur'][1], 'week_prev': xhs_g['week_prev'][1],
                        'month': xhs_g['month'][1], 'quarter': xhs_g['quarter'][1]}
                split = {'视频号': {'amt': dict(act), 'tax': dict(tax)},
                         '小红书': {'amt': xact, 'tax': xtax}}
                for k in list(act.keys()):
                    act[k] = act[k] + xact[k]
                    tax[k] = tax[k] + xtax[k]
            vach.append({'name': g['name'], 'members': [g['name']], 'target': g['target'],
                         'actual': act, 'tax': tax, 'split': split})

        video_out = {'meta': chs.get('视频号', {}).get('meta'),
                     'groups': vgroups, 'xhs': xhs_g, 'ach': vach}

        ks_ach = []
        for g in ks_groups:
            ks_ach.append({'name': g['name'], 'members': [g['name']], 'target': g['target'],
                           'actual': {'week_cur': g['week_cur'][0], 'week_prev': g['week_prev'][0],
                                      'month': g['month'][0], 'quarter': g['quarter'][0]},
                           'tax': {'week_cur': g['week_cur'][1], 'week_prev': g['week_prev'][1],
                                   'month': g['month'][1], 'quarter': g['quarter'][1]},
                           'split': None})
        kuaishou_out = {'meta': chs.get('快手', {}).get('meta'),
                        'groups': ks_groups, 'ach': ks_ach}

    out = {'meta': meta, 'groups': groups_out, 'ach': ach_out,
           'video': video_out, 'kuaishou': kuaishou_out,
           'boom': [{'group': bg, 'label': bl,
                     'daily': {k: [round(x[0], 2), round(x[1], 2), round(x[2])]
                               for k, x in sorted(v.items())}}
                    for (bg, bl), v in boom.items()]}
    json.dump(out, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    # 日报附加数据：按日订单量（去重）+ 达人日明细
    extra = {
        'meta': {'data_from': meta['data_from'], 'data_to': meta['data_to'],
                 'updated_at': meta['updated_at'], 'today': meta['today']},
        'order_daily': {d: len(s) for d, s in sorted(order_sets.items())},
        'anchors': [{'name': n, 'id': v['id'],
                     'daily': {k: [round(x[0], 2), round(x[1], 2), round(x[2])]
                               for k, x in sorted(v['daily'].items())}}
                    for n, v in anchors.items()],
    }
    json.dump(extra, open(os.path.join(BASE, 'daily_extra.json'), 'w', encoding='utf-8'),
              ensure_ascii=False)
    print('已生成日报附加数据: daily_extra.json（%d 个达人/直播间）' % len(anchors))
    print('已生成:', out_path)
    print('  数据区间: %s ~ %s' % (meta['data_from'], meta['data_to']))
    for g in groups_out:
        print('  %-8s 周(本周) %10.0f | 上周 %10.0f | 月 %10.0f | 季 %10.0f | top品 %d' % (
            g['name'], g['week_cur'][0], g['week_prev'][0], g['month'][0],
            g['quarter'][0], len(g['top_items'])))


if __name__ == '__main__':
    main()
