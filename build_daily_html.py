# -*- coding: utf-8 -*-
"""生成「抖音居家商务组 · 日报」独立页面 daily.html。

数据来源：
  dashboard_data.json  → 抖音 5 个组的 daily / item_daily + 达成率目标
  daily_extra.json     → 按日订单量 + 达人/直播间日明细

日报日期 = 数据里最新的那一天（meta.data_to）。
纯静态 HTML，趋势图用内联 SVG（不依赖 CDN），样式参考用户提供的样板日报。

用法：python build_daily_html.py [--out daily.html]
"""
import argparse
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))

TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>抖音居家商务组 · 日报</title>
<style>
  :root{
    --bg:#f5f6fa; --card-bg:#fff; --primary:#4f46e5; --success:#10b981;
    --warning:#f59e0b; --danger:#ef4444; --text:#1e293b; --text-secondary:#64748b;
    --border:#e2e8f0; --shadow:0 1px 3px rgba(0,0,0,.06),0 1px 2px rgba(0,0,0,.04);
    --shadow-lg:0 4px 6px rgba(0,0,0,.04),0 10px 15px rgba(0,0,0,.05); --radius:12px;
  }
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
    background:var(--bg);color:var(--text);line-height:1.6;padding:24px}
  .container{max-width:1280px;margin:0 auto}
  .report-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:28px;flex-wrap:wrap;gap:16px}
  .report-header h1{font-size:26px;font-weight:700;letter-spacing:-.5px}
  .report-header h1 span{color:var(--primary)}
  .report-meta{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
  .report-meta .badge{background:var(--card-bg);border:1px solid var(--border);border-radius:8px;
    padding:6px 14px;font-size:13px;color:var(--text-secondary);white-space:nowrap}
  .report-meta .badge strong{color:var(--text);margin-left:4px}
  .kpi-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px;margin-bottom:24px}
  .kpi-card{background:var(--card-bg);border-radius:var(--radius);padding:20px 24px;
    box-shadow:var(--shadow);border:1px solid var(--border);transition:box-shadow .2s}
  .kpi-card:hover{box-shadow:var(--shadow-lg)}
  .kpi-card .kpi-label{font-size:13px;color:var(--text-secondary);margin-bottom:8px;font-weight:500}
  .kpi-card .kpi-value{font-size:30px;font-weight:700;letter-spacing:-1px;margin-bottom:6px}
  .kpi-card .kpi-sub{font-size:13px;display:flex;align-items:center;gap:6px}
  .kpi-up{color:var(--success)} .kpi-down{color:var(--danger)} .kpi-flat{color:var(--text-secondary)}
  .kpi-card.accent-blue{border-left:4px solid #3b82f6}
  .kpi-card.accent-green{border-left:4px solid var(--success)}
  .kpi-card.accent-purple{border-left:4px solid #8b5cf6}
  .kpi-card.accent-orange{border-left:4px solid #f97316}
  .kpi-card.accent-teal{border-left:4px solid #14b8a6}
  .progress-wrap{margin-top:10px}
  .progress-label{display:flex;justify-content:space-between;font-size:12px;color:var(--text-secondary);margin-bottom:4px}
  .progress-bar{height:6px;background:#e2e8f0;border-radius:3px;overflow:hidden}
  .progress-fill{height:100%;border-radius:3px;transition:width .6s ease}
  .progress-fill.green{background:var(--success)} .progress-fill.blue{background:#3b82f6}
  .progress-fill.purple{background:#8b5cf6} .progress-fill.orange{background:#f97316}
  .progress-fill.teal{background:#14b8a6}
  .charts-row{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px}
  .chart-card{background:var(--card-bg);border-radius:var(--radius);padding:20px 24px;
    box-shadow:var(--shadow);border:1px solid var(--border)}
  .chart-card h3{font-size:15px;font-weight:600;margin-bottom:16px}
  .table-card{background:var(--card-bg);border-radius:var(--radius);padding:20px 24px;
    box-shadow:var(--shadow);border:1px solid var(--border);margin-bottom:24px;overflow-x:auto}
  .table-card h3{font-size:15px;font-weight:600;margin-bottom:14px}
  table{width:100%;border-collapse:collapse;font-size:14px}
  th{text-align:left;padding:10px 12px;background:#f8fafc;color:var(--text-secondary);
    font-weight:600;font-size:12px;letter-spacing:.3px;border-bottom:2px solid var(--border);white-space:nowrap}
  td{padding:12px;border-bottom:1px solid #f1f5f9;white-space:nowrap}
  tr:last-child td{border-bottom:none}
  td.num{text-align:right;font-variant-numeric:tabular-nums}
  th.num{text-align:right}
  .tag{display:inline-block;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:600}
  .tag-green{background:#d1fae5;color:#065f46}
  .tag-yellow{background:#fef3c7;color:#92400e}
  .tag-red{background:#fee2e2;color:#991b1b}
  .report-footer{text-align:center;font-size:12px;color:var(--text-secondary);margin-top:8px}
  .nav-link{display:inline-block;margin-top:10px;font-size:13px;color:var(--primary);text-decoration:none}
  .nav-link:hover{text-decoration:underline}
  @media(max-width:768px){.charts-row{grid-template-columns:1fr}.report-header{flex-direction:column;align-items:flex-start}}
  @media print{body{background:#fff;padding:0}.kpi-card,.chart-card,.table-card{box-shadow:none;break-inside:avoid}}
</style>
</head>
<body>
<div class="container">
  <div class="report-header">
    <div>
      <h1>抖音<span>居家商务组</span> · 日报</h1>
      <a class="nav-link" href="./index.html">← 返回总看板</a>
    </div>
    <div class="report-meta" id="metaBadges"></div>
  </div>

  <div class="kpi-grid" id="kpiGrid"></div>

  <div class="charts-row">
    <div class="chart-card">
      <h3>📉 近 7 天销售额趋势（万元）</h3>
      <div id="trendChart"></div>
    </div>
    <div class="table-card" style="margin-bottom:0">
      <h3>🎯 各品线周达成率</h3>
      <div id="weekTable"></div>
    </div>
  </div>

  <div class="table-card">
    <h3>🏷️ Top 达人 / 直播间（按当日销售额）</h3>
    <div id="anchorTable"></div>
  </div>

  <div class="table-card">
    <h3>🔥 Top 商品（按当日销售额）</h3>
    <div id="itemTable"></div>
  </div>

  <div class="report-footer" id="footer"></div>
</div>

<script>
const DATA = /*__DATA__*/;

const GROUPS4 = ['家纺','家具百货组','服配','服配-羽绒'];
const COLORS = {'家纺':'#4f46e5','家具百货组':'#10b981','服配':'#f59e0b','服配-羽绒':'#8b5cf6'};
const MAIN = (DATA.groups||[]).filter(g=>GROUPS4.indexOf(g.name)>=0);
const ACH4 = (DATA.ach||[]).filter(a=>GROUPS4.indexOf(a.name)>=0);
const EXTRA = DATA.extra||{};
const LATEST = (EXTRA.meta&&EXTRA.meta.data_to) || (DATA.meta&&DATA.meta.data_to);

const iso = d => d.toISOString().slice(0,10);
const parse = s => new Date(s+'T00:00:00');
const addDays = (s,n) => { const d=parse(s); d.setDate(d.getDate()+n); return iso(d); };
const fmtInt = n => (n==null?'-':Math.round(n).toLocaleString('zh-CN'));
const wan = n => (n==null?'-':(n/10000).toFixed(2)+'万');
const money = n => (n==null?'-':'¥'+Math.round(n).toLocaleString('zh-CN'));
const pct = (a,b) => (b? (a/b*100) : null);

function sumRange(daily,d0,d1){
  let a=0,q=0;
  for(const k in daily){ if(k<d0||k>d1) continue; a+=daily[k][0]; q+=daily[k][2]; }
  return [a,q];
}
function groupSum(d0,d1){
  let a=0,q=0;
  MAIN.forEach(g=>{ const v=sumRange(g.daily,d0,d1); a+=v[0]; q+=v[1]; });
  return [a,q];
}
function targetSum(k){
  let t=0; ACH4.forEach(a=>{ const v=(a.target||{})[k]; if(v) t+=v; });
  return t;
}
function momText(cur, prev){
  if(!prev) return '<span class="kpi-flat">—</span>';
  const r=(cur-prev)/prev*100;
  if(Math.abs(r)<0.05) return '<span class="kpi-flat">→ 持平</span>';
  const cls=r>0?'kpi-up':'kpi-down';
  return '<span class="'+cls+'"><span class="arrow">'+(r>0?'▲':'▼')+'</span> '+Math.abs(r).toFixed(1)+'%</span>';
}
function tagOf(rate){
  if(rate==null) return '<span class="tag tag-yellow">待填</span>';
  if(rate>=100) return '<span class="tag tag-green">优秀</span>';
  if(rate>=80) return '<span class="tag tag-yellow">良好</span>';
  return '<span class="tag tag-red">关注</span>';
}

// ── 时间边界 ──
const D_DAY0 = LATEST, D_DAY1 = LATEST;
const D_PREV = addDays(LATEST,-1);
const wStart = addDays(LATEST, -parse(LATEST).getDay());
const wPrevStart = addDays(wStart,-7), wPrevEnd = addDays(LATEST,-7);
const mStart = LATEST.slice(0,7)+'-01';
const pmD = new Date(parse(mStart)); pmD.setMonth(pmD.getMonth()-1);
const pmStart = iso(pmD), pmEnd = iso(new Date(pmD.getFullYear(), pmD.getMonth()+1, 0));
const qStart = '2026-10-01', qPrevStart='2026-07-01', qPrevEnd='2026-09-30';

function renderMeta(){
  const up = (EXTRA.meta&&EXTRA.meta.updated_at)||(DATA.meta&&DATA.meta.updated_at)||'';
  document.getElementById('metaBadges').innerHTML =
    '<div class="badge">📅 日报日期<strong>'+LATEST+'</strong></div>'+
    '<div class="badge">🕐 数据更新<strong>'+up+'</strong></div>'+
    '<div class="badge">👤 范围<strong>居家商务组（4 品线）</strong></div>';
}

function renderKpi(){
  const day = groupSum(D_DAY0,D_DAY1);
  const dayPrev = groupSum(D_PREV,D_PREV);
  const wk = groupSum(wStart,LATEST);
  const wkPrev = groupSum(wPrevStart,wPrevEnd);
  const mo = groupSum(mStart,LATEST);
  const moPrev = groupSum(pmStart,pmEnd);
  const qt = groupSum(qStart,LATEST);
  const qtPrev = groupSum(qPrevStart,qPrevEnd);
  const orders = (EXTRA.order_daily||{})[LATEST]||0;
  const ordersPrev = (EXTRA.order_daily||{})[D_PREV]||0;

  const tW = targetSum('week'), tM = targetSum('month'), tQ = targetSum('quarter');
  const tD = tW/7;

  const cards = [
    {label:'📦 日总销售额', val:money(day[0]), mom:momText(day[0],dayPrev[0]),
     rate:pct(day[0],tD), accent:'blue', fill:'blue', tname:'日目标（周目标/7）'},
    {label:'📋 日订单量', val:fmtInt(orders), mom:momText(orders,ordersPrev),
     rate:null, accent:'green', fill:'green', tname:''},
    {label:'📊 周累计销售额', val:money(wk[0]), mom:momText(wk[0],wkPrev[0]),
     rate:pct(wk[0],tW), accent:'purple', fill:'purple', tname:'周目标'},
    {label:'📈 月累计销售额', val:money(mo[0]), mom:momText(mo[0],moPrev[0]),
     rate:pct(mo[0],tM), accent:'orange', fill:'orange', tname:'月目标'},
    {label:'📆 季度累计销售额', val:money(qt[0]), mom:momText(qt[0],qtPrev[0]),
     rate:pct(qt[0],tQ), accent:'teal', fill:'teal', tname:'季度目标'}
  ];
  document.getElementById('kpiGrid').innerHTML = cards.map(c=>{
    let prog='';
    if(c.rate!=null){
      const w=Math.min(c.rate,100);
      prog='<div class="progress-wrap"><div class="progress-label"><span>'+c.tname+'完成率</span><span>'+
        c.rate.toFixed(1)+'%</span></div><div class="progress-bar"><div class="progress-fill '+c.fill+
        '" style="width:'+w+'%"></div></div></div>';
    }
    return '<div class="kpi-card accent-'+c.accent+'"><div class="kpi-label">'+c.label+
      '</div><div class="kpi-value">'+c.val+'</div><div class="kpi-sub"><span>环比</span>'+c.mom+
      '</div>'+prog+'</div>';
  }).join('');
}

function renderTrend(){
  const days=[]; for(let i=6;i>=0;i--) days.push(addDays(LATEST,-i));
  const series = MAIN.map(g=>({name:g.name, color:COLORS[g.name]||'#94a3b8',
    data: days.map(d=>{ const v=g.daily[d]; return v? v[0]/10000 : 0; })}));
  const W=560,H=250,PL=46,PR=12,PT=16,PB=34;
  const iw=W-PL-PR, ih=H-PT-PB;
  let maxV=0; series.forEach(s=>s.data.forEach(v=>{ if(v>maxV) maxV=v; }));
  maxV = maxV>0? maxV*1.15 : 1;
  const x = i => PL + (days.length===1? iw/2 : iw*i/(days.length-1));
  const y = v => PT + ih - ih*(v/maxV);
  let svg='<svg viewBox="0 0 '+W+' '+H+'" style="width:100%;height:auto">';
  // 网格 + y 轴
  for(let k=0;k<=4;k++){
    const v=maxV*k/4, yy=y(v);
    svg+='<line x1="'+PL+'" y1="'+yy+'" x2="'+(W-PR)+'" y2="'+yy+'" stroke="#f1f5f9"/>';
    svg+='<text x="'+(PL-8)+'" y="'+(yy+4)+'" text-anchor="end" font-size="11" fill="#94a3b8">'+v.toFixed(0)+'</text>';
  }
  // x 轴标签
  days.forEach((d,i)=>{
    svg+='<text x="'+x(i)+'" y="'+(H-12)+'" text-anchor="middle" font-size="11" fill="#94a3b8">'+d.slice(5)+'</text>';
  });
  // 折线
  series.forEach(s=>{
    const pts=s.data.map((v,i)=>x(i)+','+y(v)).join(' ');
    svg+='<polyline points="'+pts+'" fill="none" stroke="'+s.color+'" stroke-width="2.5" stroke-linejoin="round"/>';
    s.data.forEach((v,i)=>{ svg+='<circle cx="'+x(i)+'" cy="'+y(v)+'" r="3" fill="'+s.color+'"/>'; });
  });
  svg+='</svg>';
  let legend='<div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:10px;font-size:12px;color:#64748b">';
  series.forEach(s=>{ legend+='<span><i style="display:inline-block;width:8px;height:8px;border-radius:50%;background:'+
    s.color+';margin-right:5px"></i>'+s.name+'</span>'; });
  legend+='</div>';
  document.getElementById('trendChart').innerHTML = svg + legend;
}

function renderWeekTable(){
  // 最近 4 周（含当前周）
  const weeks=[];
  let ws = wStart;
  for(let i=0;i<4;i++){ weeks.unshift(ws); ws = addDays(ws,-7); }
  let head='<table><thead><tr><th>品线</th>';
  weeks.forEach(w=>{ head+='<th class="num">'+w.slice(5)+'起</th>'; });
  head+='<th class="num">周环比</th></tr></thead><tbody>';
  let body='';
  MAIN.forEach(g=>{
    const tgt = (ACH4.find(a=>a.name===g.name)||{}).target||{};
    const wt = tgt.week||0;
    body+='<tr><td><strong>'+g.name+'</strong></td>';
    let last=null, prev=null;
    weeks.forEach((w,idx)=>{
      const we = addDays(w,6);
      const v = sumRange(g.daily, w, we)[0];
      const r = wt? v/wt*100 : null;
      if(idx===weeks.length-1) last=v;
      if(idx===weeks.length-2) prev=v;
      body+='<td class="num">'+(r==null?'-':r.toFixed(1)+'%')+'</td>';
    });
    body+='<td class="num">'+momText(last, prev)+'</td></tr>';
  });
  body+='</tbody></table>';
  document.getElementById('weekTable').innerHTML = head+body;
}

function renderAnchors(){
  const list=(EXTRA.anchors||[]).map(a=>{
    const day=(a.daily||{})[LATEST]||[0,0];
    const prev=(a.daily||{})[D_PREV]||[0,0];
    const wk=sumRange(a.daily||{},wStart,LATEST)[0];
    const mo=sumRange(a.daily||{},mStart,LATEST)[0];
    return {name:a.name, day:day[0], prev:prev[0], wk:wk, mo:mo};
  }).filter(x=>x.day>0).sort((a,b)=>b.day-a.day).slice(0,10);

  const totalDay = groupSum(D_DAY0,D_DAY1)[0];
  let html='<table><thead><tr><th>#</th><th>达人 / 直播间</th><th class="num">日销售额</th>'+
    '<th class="num">日环比</th><th class="num">占当日</th><th class="num">周累计</th>'+
    '<th class="num">月累计</th><th>趋势</th></tr></thead><tbody>';
  list.forEach((x,i)=>{
    const share = totalDay? x.day/totalDay*100 : 0;
    html+='<tr><td>'+(i+1)+'</td><td><strong>'+x.name+'</strong></td>'+
      '<td class="num">'+money(x.day)+'</td><td class="num">'+momText(x.day,x.prev)+'</td>'+
      '<td class="num">'+share.toFixed(1)+'%</td><td class="num">'+money(x.wk)+'</td>'+
      '<td class="num">'+money(x.mo)+'</td><td>'+tagOf(share>=5?100:(share>=2?85:60))+'</td></tr>';
  });
  html+='</tbody></table>';
  document.getElementById('anchorTable').innerHTML = html;
}

function renderItems(){
  // 汇总每个商品 日/周/月
  const map={};
  MAIN.forEach(g=>{
    const ids=g.item_daily||{};
    for(const iid in ids){
      const dv=ids[iid];
      const info=(g.top_items||[]).find(t=>t.item_id===iid)||{};
      let d=0,w=0,m=0;
      for(const k in dv){
        if(k===LATEST) d+=dv[k][0];
        if(k>=wStart && k<=LATEST) w+=dv[k][0];
        if(k>=mStart && k<=LATEST) m+=dv[k][0];
      }
      if(d<=0) continue;
      const key=g.name+'|'+iid;
      map[key]={name:info.name||iid, group:g.name, day:d, wk:w, mo:m};
    }
  });
  const list=Object.values(map).sort((a,b)=>b.day-a.day).slice(0,10);
  const totalDay = groupSum(D_DAY0,D_DAY1)[0];
  let html='<table><thead><tr><th>排名</th><th>商品名称</th><th>品线</th><th class="num">日销售额</th>'+
    '<th class="num">占当日</th><th class="num">周累计</th><th class="num">月累计</th></tr></thead><tbody>';
  const medal=['🥇','🥈','🥉'];
  list.forEach((x,i)=>{
    const share = totalDay? x.day/totalDay*100 : 0;
    html+='<tr><td>'+(medal[i]||(i+1))+'</td><td><strong>'+x.name+'</strong></td><td>'+x.group+'</td>'+
      '<td class="num">'+money(x.day)+'</td><td class="num">'+share.toFixed(1)+'%</td>'+
      '<td class="num">'+money(x.wk)+'</td><td class="num">'+money(x.mo)+'</td></tr>';
  });
  html+='</tbody></table>';
  document.getElementById('itemTable').innerHTML = html;
}

renderMeta(); renderKpi(); renderTrend(); renderWeekTable(); renderAnchors(); renderItems();
document.getElementById('footer').textContent =
  '抖音居家商务组 · 数据来源：网易有数 BI · 日报日期 '+LATEST+
  ' · 生成于 '+((EXTRA.meta&&EXTRA.meta.updated_at)||'')+' · 仅供内部参考';
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(BASE, 'daily.html'))
    args = ap.parse_args()

    data_path = os.path.join(BASE, 'dashboard_data.json')
    extra_path = os.path.join(BASE, 'daily_extra.json')
    if not os.path.exists(data_path):
        raise SystemExit('缺少 dashboard_data.json')
    data = json.load(open(data_path, encoding='utf-8'))
    extra = json.load(open(extra_path, encoding='utf-8')) if os.path.exists(extra_path) else {}

    # 只保留四个主组，减小体积
    groups4 = ['家纺', '家具百货组', '服配', '服配-羽绒']
    data['groups'] = [g for g in (data.get('groups') or []) if g.get('name') in groups4]
    data['ach'] = [a for a in (data.get('ach') or []) if a.get('name') in groups4]

    # 达人只保留累计 Top 100，控制体积
    anchors = extra.get('anchors') or []
    anchors.sort(key=lambda a: -sum(v[0] for v in (a.get('daily') or {}).values()))
    extra['anchors'] = anchors[:100]

    payload = {
        'meta': data.get('meta'),
        'groups': data.get('groups'),
        'ach': data.get('ach'),
        'extra': extra,
    }
    html = TEMPLATE.replace('/*__DATA__*/', json.dumps(payload, ensure_ascii=False))
    open(args.out, 'w', encoding='utf-8').write(html)
    print('已生成日报:', args.out, '(%.1f KB)' % (len(html.encode('utf-8')) / 1024))


if __name__ == '__main__':
    main()
