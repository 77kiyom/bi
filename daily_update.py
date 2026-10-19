# -*- coding: utf-8 -*-
"""抖快渠道销售看板 · 每日更新一条龙。

步骤：
  1) 拉订单明细 douyin_detail（异步导出，含退货修正的近14天全量）
  2) 拉主播×分组汇总 sales_detail（异步导出，用于 26年分组映射）
  3) 拉商品表 product_table_full.csv（同步导出，含 group_name，需重试）
  4) 更新飞书「短视频产出达人uid」→ uid_sheet.json
  5) 生成 dashboard_data.json + dashboard.html
  6) 覆盖上传到资料库页面节点

用法：
  python daily_update.py                # 全流程
  python daily_update.py --skip-fetch   # 跳过拉数（用已有数据重算看板）
  python daily_update.py --skip-upload  # 不覆盖上传
"""
import argparse
import datetime
import io
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import youdata_client as yc

BASE = os.path.dirname(os.path.abspath(__file__))
REPORT_ID = 36928
PAGE_NODE_ID = '9Oqpq6pE93NcTKNiVBPdQW'          # 资料库「抖快渠道销售看板」页面节点
SKILL_DIR = ('C:/Users/wujie15/AppData/Local/Programs/WorkBuddyAI/resources/app.asar.unpacked'
             '/resources/plugins/workbuddy-builtin/skills/library')
PY = sys.executable
BJ_TZ = datetime.timezone(datetime.timedelta(hours=8))   # 北京时间，避免 CI(UTC) 下日期错位
FLYBOOK_TOKEN = os.environ.get('FLYBOOK_TOKEN', '')   # 飞书 wiki「短视频产出达人uid」obj_token

ASYNC_COMPONENTS = [
    ('c-1-18047-45005-kjmplaah', 45005, 'douyin_detail'),      # 抖音订单明细
    ('c-1-18047-45125-lgsou3u2', 45125, 'sales_detail'),       # 主播×26年分组汇总
]
SYNC_COMPONENTS = [
    ('c-1-18047-45125-ldo9jokk', 45125, 'product_table_full'),  # 商品表（带 group_name）
]


def _download(url, dest):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=1800) as resp:
        data = resp.read()
    open(dest, 'wb').write(data)
    return len(data)


def fetch_async(component_id, dashboard_id, name, date_dir):
    """异步导出（适合大表）。"""
    print('[异步] %s ...' % name, flush=True)
    # 创建导出任务偶发 733/未知异常，多次重试（不阻断整轮更新）
    r = None
    for attempt in range(1, 7):
        try:
            r = yc.api_post('/api/dash/report/asyncExportExcel', {
                'reportId': REPORT_ID, 'componentId': component_id,
                'exportType': 'csv', 'excelSplitLimit': 1000000})
        except Exception as e:
            print('  创建任务尝试%d 异常: %s' % (attempt, type(e).__name__), flush=True)
            r = None
        if r and r.get('code') == 200:
            break
        print('  创建任务尝试%d 失败: %s' % (attempt, (r or {}).get('message', '无响应')), flush=True)
        time.sleep(15)
    else:
        raise RuntimeError('%s 创建任务多次失败: %s' % (name, json.dumps(r, ensure_ascii=False)[:200]))
    task_id = r['result']
    for i in range(90):
        rr = yc.api_get('/api/dash/exportExcelTask/get', {'id': task_id})
        st = (rr.get('result') or {}).get('status')
        if st == 'success':
            break
        if st in ('fail', 'expired'):
            raise RuntimeError('%s 任务失败: %s' % (name, st))
        time.sleep(8)
    else:
        raise RuntimeError('%s 轮询超时' % name)
    token = yc.get_token()
    url = '%s/api/dash/exportExcelTask/download?id=%s&token=%s' % (yc.BASE_URL, task_id, token)
    tmp = os.path.join(date_dir, name + '.zip')
    size = _download(url, tmp)
    zf = zipfile.ZipFile(tmp)
    raw = zf.read(zf.namelist()[0])
    out = os.path.join(date_dir, name + '.zip')
    # 保持 zip 形态（下游脚本按 zip 读）
    print('  完成 %.1f MB' % (size / 1024 / 1024), flush=True)
    return out


def fetch_sync(component_id, dashboard_id, name, date_dir, retries=8):
    """同步导出（适合中小表，易 738，需重试）。"""
    print('[同步] %s ...' % name, flush=True)
    params = {
        'reportId': REPORT_ID, 'dashboardId': dashboard_id, 'pid': dashboard_id,
        'componentId': component_id, 'type': 'component', 'exportType': 'csv',
        'enhance': False, 'useOriginData': False, 'includeTitle': True,
        'rowsLimit': 1000000, 'excelSplitLimit': 1000000,
    }
    for i in range(1, retries + 1):
        try:
            r = yc.api_post('/api/dash/report/exportExcel', params, timeout=900)
        except Exception as e:
            print('  尝试%d 异常: %s' % (i, type(e).__name__), flush=True)
            continue
        if r.get('code') == 200:
            link = (r.get('result') or {}).get('link') or (r.get('result') or {}).get('url')
            if link:
                url = link if link.startswith('http') else yc.BASE_URL + link
                # 对象存储签名链接不能再加 token
                if '/dash/store/' not in url and 'token=' not in url:
                    url += ('&' if '?' in url else '?') + 'token=' + yc.get_token()
                dest = os.path.join(date_dir, name + '.csv')
                size = _download(url, dest)
                print('  完成 %.1f MB' % (size / 1024 / 1024), flush=True)
                return dest
        print('  尝试%d code=%s' % (i, r.get('code')), flush=True)
        time.sleep(5)
    raise RuntimeError('%s 多次重试仍失败' % name)


def _decode_bytes(b):
    if isinstance(b, str):
        return b
    for enc in ('utf-8', 'gbk', 'cp936', 'latin-1'):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode('utf-8', errors='replace')


def _run_lark_cli(args_list, timeout=180):
    """调用 lark-cli，返回 (returncode, stdout文本, stderr文本)。

    Windows 上 lark-cli 是 npm 风格的 .CMD 包装脚本，Python 直接
    subprocess(['lark-cli', ...]) 会抛 FileNotFoundError，走 cmd.exe 又会踩
    引号陷阱。这里直接定位真实的 node 入口 run.js 来执行，最稳。
    cmd.exe 输出为本地编码（GBK），故按字节捕获后多编码兜底解码。
    """
    exe = shutil.which('lark-cli')
    argv = None
    if exe:
        ext = os.path.splitext(exe)[1].lower()
        if ext in ('.cmd', '.bat'):
            basedir = os.path.dirname(exe)
            run_js = os.path.join(basedir, 'node_modules', '@larksuite',
                                  'cli', 'scripts', 'run.js')
            node = os.path.join(basedir, 'node.exe')
            if not os.path.exists(node):
                node = shutil.which('node')
            if os.path.exists(run_js) and node:
                argv = [node, run_js] + args_list
            else:
                argv = ['cmd', '/c', exe] + args_list
        else:
            argv = [exe] + args_list
    if argv is None:
        # 兜底：PATH 上是 sh 脚本时用 bash 执行
        cmd = 'lark-cli ' + ' '.join("'%s'" % a for a in args_list)
        for cand in (r'C:\Program Files\Git\bin\bash.exe',
                     r'C:\Program Files\Git\usr\bin\bash.exe',
                     r'C:\Program Files (x86)\Git\bin\bash.exe'):
            if os.path.exists(cand):
                argv = [cand, '-lc', cmd]
                break
        if argv is None:
            argv = cmd

    r = subprocess.run(argv, capture_output=True, timeout=timeout)
    return r.returncode, _decode_bytes(r.stdout), _decode_bytes(r.stderr)


def update_flybook(date_dir):
    """飞书表格 → uid_sheet.json。"""
    print('[飞书] 更新达人清单 ...', flush=True)
    try:
        rc, raw, err = _run_lark_cli(['sheets', '+csv-get', '--spreadsheet-token', FLYBOOK_TOKEN,
                                      '--range', 'Sheet1!A1:C245', '--as', 'user'])
        raw = (raw or '').strip()
        csv_txt = ''
        if raw:
            try:
                # lark-cli 默认返回 JSON 信封，真正的 CSV 在 data.annotated_csv
                j = json.loads(raw)
                csv_txt = ((j.get('data') or {}).get('annotated_csv') or '')
            except ValueError:
                csv_txt = raw   # 兼容直接输出裸 CSV 的旧版本
        if not csv_txt.strip():
            print('  [警告] 飞书返回为空(rc=%s)，保留原 uid_sheet.json。stderr=%s'
                  % (rc, (err or '').strip()[:200]), flush=True)
            return
        data = {'data': {'annotated_csv': csv_txt}}
        json.dump(data, open(os.path.join(BASE, 'uid_sheet.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False)
        print('  已更新 uid_sheet.json (%d 行)' % len(csv_txt.strip().split('\n')),
              flush=True)
    except Exception as e:
        print('  [警告] 飞书更新失败(%s: %s)，保留原清单'
              % (type(e).__name__, e), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--skip-fetch', action='store_true')
    ap.add_argument('--skip-upload', action='store_true')
    ap.add_argument('--data-dir', default=None)
    args = ap.parse_args()

    if args.data_dir:
        date_dir = args.data_dir if os.path.isabs(args.data_dir) else os.path.join(BASE, args.data_dir)
    else:
        date_dir = os.path.join(BASE, 'data', datetime.datetime.now(BJ_TZ).strftime('%Y-%m-%d'))
    # --skip-fetch 且今日目录无数据时，回退到最近一个含 douyin_detail.zip 的目录
    if args.skip_fetch and not os.path.exists(os.path.join(date_dir, 'douyin_detail.zip')):
        cand = sorted([d for d in os.listdir(os.path.join(BASE, 'data'))
                       if os.path.exists(os.path.join(BASE, 'data', d, 'douyin_detail.zip'))])
        if cand:
            date_dir = os.path.join(BASE, 'data', cand[-1])
            print('  [回退] 使用最近数据目录: %s' % date_dir)
    os.makedirs(date_dir, exist_ok=True)
    print('=== 数据目录: %s ===' % date_dir)

    if not args.skip_fetch:
        for cid, did, nm in ASYNC_COMPONENTS:
            fetch_async(cid, did, nm, date_dir)
        for cid, did, nm in SYNC_COMPONENTS:
            fetch_sync(cid, did, nm, date_dir)
        update_flybook(date_dir)
        # 视频号：独立报表(37523)，按天抓取（失败不阻断抖音主流程）
        print('\n=== 抓取视频号数据 ===')
        try:
            subprocess.run([PY, os.path.join(BASE, 'fetch_video.py')], check=True)
        except Exception as e:
            print('  [警告] 视频号抓取失败(%s)，沿用已有 video_data.json' % type(e).__name__)

    print('\n=== 生成看板数据 ===')
    subprocess.run([PY, os.path.join(BASE, 'build_dashboard_data.py'),
                    '--data-dir', date_dir], check=True)
    subprocess.run([PY, os.path.join(BASE, 'build_dashboard_html.py')], check=True)
    # 日报独立页面
    try:
        subprocess.run([PY, os.path.join(BASE, 'build_daily_html.py')], check=True)
    except Exception as e:
        print('  [警告] 日报页生成失败(%s)' % type(e).__name__)

    if not args.skip_upload:
        print('\n=== 覆盖上传云端 ===')
        subprocess.run([PY, os.path.join(SKILL_DIR, 'page', 'import_html.py'),
                        os.path.join(BASE, 'dashboard.html'),
                        '--node-block-id', PAGE_NODE_ID], check=True)
    print('\n全部完成。')


if __name__ == '__main__':
    main()
