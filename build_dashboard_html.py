# -*- coding: utf-8 -*-
"""由 dashboard_data.json 生成自包含 HTML 看板（数据内嵌，便于每日覆盖更新）。

用法：python build_dashboard_html.py [--data dashboard_data.json] [--out dashboard.html]
"""
import argparse
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))

TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>抖快渠道销售看板 · Q4</title>
<style>
  :root{
    --brand:#2F5597; --brand2:#4A7BC8; --bg:#f4f6fa; --card:#ffffff;
    --line:#e3e8f0; --txt:#1f2733; --muted:#7b8794; --up:#c0392b; --down:#1e8e5a;
    --amber:#c77c00;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--txt);
    font-family:"Microsoft YaHei","PingFang SC","Helvetica Neue",Arial,sans-serif;
    -webkit-font-smoothing:antialiased}
  .wrap{max-width:1280px;margin:0 auto;padding:22px 20px 60px}
  header{display:flex;flex-wrap:wrap;align-items:baseline;gap:14px;margin-bottom:16px}
  header h1{margin:0;font-size:22px;letter-spacing:.5px;color:var(--brand)}
  header .sub{font-size:12.5px;color:var(--muted)}
  .toolbar{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin-bottom:16px}
  .seg{display:inline-flex;background:#fff;border:1px solid var(--line);border-radius:9px;overflow:hidden}
  .seg button{border:0;background:transparent;padding:7px 14px;font-size:13px;color:#54606e;cursor:pointer;
    font-family:inherit;border-right:1px solid var(--line)}
  .seg button:last-child{border-right:0}
  .seg button.on{background:var(--brand);color:#fff;font-weight:600}
  .seg button:disabled{color:#c3cad4;cursor:not-allowed}
  .filterbar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;
    background:#fff;border:1px solid var(--line);border-radius:12px;padding:10px 14px;margin-bottom:16px}
  .filterbar .lb{font-size:13px;color:var(--muted)}
  .custom{display:inline-flex;align-items:center;gap:6px;font-size:13px;color:var(--muted)}
  .custom input{border:1px solid var(--line);border-radius:7px;padding:6px 8px;font-size:12.5px;
    font-family:inherit;color:var(--txt);background:#fff}
  .panel{background:var(--card);border:1px solid var(--line);border-radius:12px;
    padding:16px 18px;margin-bottom:16px;box-shadow:0 1px 2px rgba(31,39,51,.04)}
  .panel h2{margin:0 0 12px;font-size:15px;color:var(--brand);font-weight:700;
    display:flex;align-items:center;gap:8px;flex-wrap:wrap}
  .panel h2 small{font-weight:400;color:var(--muted);font-size:12px}
  .prog-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
  .prog-item .pt{display:flex;justify-content:space-between;font-size:13px;margin-bottom:6px}
  .prog-item .pt b{color:var(--txt)}
  .prog-item .pt span{color:var(--muted)}
  .bar{height:9px;background:#eef1f6;border-radius:6px;overflow:hidden}
  .bar i{display:block;height:100%;background:linear-gradient(90deg,var(--brand2),var(--brand));border-radius:6px}
  .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:14px;margin-bottom:16px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;
    box-shadow:0 1px 2px rgba(31,39,51,.04);position:relative;overflow:hidden}
  .card::before{content:"";position:absolute;left:0;top:0;width:4px;height:100%;background:var(--brand)}
  .card .nm{font-size:13px;color:var(--muted);margin-bottom:6px}
  .card .val{font-size:23px;font-weight:700;color:var(--txt);font-variant-numeric:tabular-nums;letter-spacing:.3px}
  .card .extra{margin-top:7px;font-size:12px;color:var(--muted);display:flex;justify-content:space-between}
  .card .extra b{font-weight:600}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th,td{padding:8px 10px;text-align:right;border-bottom:1px solid var(--line);font-variant-numeric:tabular-nums}
  th{background:#f7f9fc;color:#54606e;font-weight:600;font-size:12.5px;white-space:nowrap}
  th:first-child,td:first-child{text-align:left}
  tbody tr:hover{background:#fafcff}
  td.name{font-weight:600;color:var(--txt)}
  .tot-row td{background:#f2f6fd;font-weight:700;color:var(--brand)}
  .muted{color:var(--muted)}
  .tag{display:inline-block;padding:1px 7px;border-radius:20px;font-size:11px;background:#eef3fb;color:var(--brand)}
  .empty{color:var(--muted);font-size:13px;padding:10px 2px}
  /* 达成率图表 */
  .chart{margin:2px 0 14px}
  .chart .row{display:flex;align-items:center;gap:10px;margin:8px 0}
  .chart .lbl{width:96px;font-size:13px;color:var(--txt);text-align:right;flex:none}
  .chart .track{position:relative;flex:1;height:20px;background:#eef1f6;border-radius:6px;overflow:hidden}
  .chart .fill{position:absolute;left:0;top:0;height:100%;border-radius:6px;transition:width .3s}
  .chart .goal{position:absolute;top:-2px;bottom:-2px;width:2px;background:#8a94a3;opacity:.75}
  .chart .pct{width:66px;font-size:12.5px;text-align:right;flex:none;font-variant-numeric:tabular-nums}
  @media(max-width:900px){
    .cards{grid-template-columns:repeat(2,1fr)}
    .prog-grid{grid-template-columns:1fr}
  }
  @media(max-width:560px){
    .cards{grid-template-columns:1fr}
    .wrap{padding:14px 12px 40px}
  }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>抖快渠道销售看板</h1>
    <div class="sub" id="subline"></div>
  </header>

  <div class="toolbar">
    <div class="seg" id="channelSeg">
      <button data-c="抖音" class="on">抖音</button>
      <button data-c="快手">快手</button>
      <button data-c="视频号">视频号</button>
    </div>
  </div>

  <div class="panel">
    <h2>时间进度 <small id="progNote"></small></h2>
    <div class="prog-grid" id="progGrid"></div>
  </div>

  <div class="filterbar">
    <span class="lb">日期区间</span>
    <div class="seg" id="salesSeg">
      <button data-p="week_cur">本周</button>
      <button data-p="week_prev">上周</button>
      <button data-p="month">本月</button>
      <button data-p="quarter">Q4 季度</button>
    </div>
    <div class="custom">
      <input type="date" id="sFrom"> <span>至</span> <input type="date" id="sTo">
    </div>
    <span class="lb" style="font-size:12px">（作用于 卡片 / 销售额明细 / Top 单品）</span>
  </div>

  <div class="cards" id="cards"></div>

  <div class="panel">
    <h2>销售额明细 <small id="salesNote"></small></h2>
    <div id="dailyTable"></div>
  </div>

  <div class="panel">
    <h2>Top 单品 <small id="topNote">销售额 ≥ 1 万</small></h2>
    <div id="topItems"></div>
  </div>

  <div class="panel">
    <h2>达成率 <small id="targetNote">抖音渠道</small></h2>
    <div class="filterbar" style="margin-bottom:14px">
      <div class="seg" id="achSeg">
        <button data-p="week_cur" class="on">本周</button>
        <button data-p="week_prev">上周</button>
        <button data-p="month">本月</button>
        <button data-p="quarter">Q4 季度</button>
      </div>
      <span class="lb" id="achRange"></span>
      <span class="lb" style="margin-left:auto">排序</span>
      <div class="seg" id="achSortSeg">
        <button data-s="default" class="on">默认</button>
        <button data-s="desc">降序</button>
        <button data-s="asc">升序</button>
      </div>
    </div>
    <div class="chart" id="achChart"></div>
    <div id="targetTable"></div>
  </div>
</div>

<script>
const DATA = /*__DATA__*/;

const fmt = n => (n==null? '-' : Number(n).toLocaleString('zh-CN',{maximumFractionDigits:0}));
const exact = n => (n==null? '-' : Number(n).toLocaleString('zh-CN',{minimumFractionDigits:2,maximumFractionDigits:2}));
const wan = n => (n==null? '-' : (Number(n)/10000).toFixed(2)+'万');
// 金额：显示 xx.xx万，鼠标悬停显示真实金额
const money = n => `<span title="${exact(n)} 元">${wan(n)}</span>`;
const iso = d => d.toISOString().slice(0,10);
const addDays = (s,n) => { const d=new Date(s); d.setDate(d.getDate()+n); return iso(d); };

function presetRange(p){
  const m = DATA.meta;
  if(p==='week_cur') return [m.week.start, m.week.end];
  if(p==='week_prev') return [addDays(m.week.start,-7), addDays(m.week.end,-7)];
  if(p==='month') return [m.month.start, m.month.end];
  if(p==='quarter') return [m.quarter.start, m.quarter.end];
  return [m.data_from, m.data_to];
}

let salesRange = presetRange('week_cur');
let achPeriod = 'week_cur';
let achSort = 'default';
let CH = '抖音';
function groupsData(){
  if(CH==='视频号'){
    const v=(DATA.video&&DATA.video.groups)||[];
    const out=[];
    v.forEach(g=>{
      if(g.name==='家具百货组'){
        out.push(Object.assign({}, g, {name:'家具百货组（视频号）'}));
        if(DATA.video.xhs) out.push(Object.assign({}, DATA.video.xhs, {name:'家具百货组（小红书）'}));
      } else {
        out.push(g);
      }
    });
    return out;
  }
  if(CH==='快手') return (DATA.kuaishou&&DATA.kuaishou.groups)||[];
  return DATA.groups||[];
}
function achData(){
  if(CH==='视频号') return (DATA.video&&DATA.video.ach)||[];
  if(CH==='快手') return (DATA.kuaishou&&DATA.kuaishou.ach)||[];
  return DATA.ach||[];
}
function topThreshold(){ return CH==='抖音' ? 10000 : 1000; }

function sumRange(g,d0,d1){
  let a=0,t=0,q=0;
  for(const k in g.daily){
    if(d0 && k<d0) continue;
    if(d1 && k>d1) continue;
    a+=g.daily[k][0]; t+=g.daily[k][1]; q+=g.daily[k][2];
  }
  return [a,t,q];
}
function topInRange(g,d0,d1){
  const out=[];
  for(const iid in g.item_daily){
    let a=0,q=0; const dv=g.item_daily[iid];
    for(const k in dv){
      if(d0 && k<d0) continue;
      if(d1 && k>d1) continue;
      a+=dv[k][0]; q+=dv[k][2];
    }
    if(a>=topThreshold()){
      const info=(g.top_items.find(x=>x.item_id===iid))||{};
      out.push({item_id:iid, name:info.name||iid, group_name:info.group_name||'', amt:a, qty:q});
    }
  }
  out.sort((x,y)=>y.amt-x.amt);
  return out;
}

function renderHeader(){
  const m=DATA.meta;
  const vm=(CH==='视频号'&&DATA.video&&DATA.video.meta)?DATA.video.meta
          :(CH==='快手'&&DATA.kuaishou&&DATA.kuaishou.meta)?DATA.kuaishou.meta:null;
  const rng=vm?`${vm.data_from} ~ ${vm.data_to}`:`${m.data_from} ~ ${m.data_to}`;
  const upd=vm?vm.updated_at:m.updated_at;
  document.getElementById('subline').textContent =
    `${CH}渠道 · Q4（${m.quarter.start} 起） · 数据区间 ${rng} · 更新于 ${upd}`;
  const items=[
    ['本周', m.week.start+' ~ '+m.week.end, m.week.elapsed, m.week.total],
    [m.month.label, m.month.start+' ~ '+m.month.end, m.month.elapsed, m.month.total],
    ['Q4 季度', m.quarter.start+' ~ '+m.quarter.end, m.quarter.elapsed, m.quarter.total],
  ];
  document.getElementById('progGrid').innerHTML = items.map(([nm,rg,el,tot])=>{
    const p=(el/tot*100).toFixed(1);
    return `<div class="prog-item"><div class="pt"><b>${nm}</b><span>${rg} · 第 ${el}/${tot} 天</span></div>
      <div class="bar"><i style="width:${p}%"></i></div>
      <div class="pt" style="margin-top:5px"><span>时间进度</span><b>${p}%</b></div></div>`;
  }).join('');
}

function renderSales(){
  const d0=salesRange[0], d1=salesRange[1];
  document.getElementById('salesNote').textContent = `（${d0} ~ ${d1}）`;
  document.getElementById('topNote').textContent = `销售额 ≥ ${topThreshold()>=10000?'1 万':'1000'}（${d0} ~ ${d1}）`;
  const len = Math.round((new Date(d1)-new Date(d0))/86400000)+1;
  const pv0 = addDays(d0,-len), pv1 = addDays(d0,-1);
  let cards='', rows='', tAll=[0,0,0];
  groupsData().forEach(g=>{
    const v=sumRange(g,d0,d1); tAll[0]+=v[0]; tAll[1]+=v[1]; tAll[2]+=v[2];
    const pv=sumRange(g,pv0,pv1);
    const mom = pv[0]>0? ((v[0]-pv[0])/pv[0]*100) : null;
    const momTxt = mom==null? '<span class="muted">-</span>' :
      `<b style="color:${mom>=0?'var(--up)':'var(--down)'}">${mom>=0?'▲':'▼'} ${Math.abs(mom).toFixed(1)}%</b>`;
    cards += `<div class="card"><div class="nm">${g.name}</div>
      <div class="val" title="${exact(v[0])} 元">${wan(v[0])}</div>
      <div class="extra"><span>销量 ${fmt(v[2])}</span><span>环比 ${momTxt}</span></div></div>`;
    rows += `<tr><td class="name">${g.name}</td>
      <td>${money(v[0])}</td><td>${money(v[1])}</td><td>${fmt(v[2])}</td>
      <td>${money(g.week_cur[0])}</td><td>${money(g.week_prev[0])}</td>
      <td>${money(g.month[0])}</td><td>${money(g.quarter[0])}</td></tr>`;
  });
  document.getElementById('cards').innerHTML = cards;
  document.getElementById('dailyTable').innerHTML =
    `<table><thead><tr><th>组</th><th>销售额</th><th>含税收入</th><th>销量</th>
      <th>本周</th><th>上周</th><th>本月</th><th>Q4 季度</th></tr></thead>
     <tbody>${rows}
     <tr class="tot-row"><td>合计</td><td>${money(tAll[0])}</td><td>${money(tAll[1])}</td><td>${fmt(tAll[2])}</td>
      <td colspan="4" class="muted">—</td></tr></tbody></table>`;

  let html='';
  groupsData().forEach(g=>{
    const items=topInRange(g,d0,d1);
    html += `<div style="margin-bottom:14px"><div style="font-size:13px;font-weight:700;color:var(--brand);margin-bottom:6px">
      ${g.name} <span class="tag">${items.length} 个品</span></div>`;
    if(!items.length){ html += `<div class="empty">该区间内无销售额 ≥ 1 万的单品</div></div>`; return; }
    html += `<table><thead><tr><th>商品名称</th><th>BU小组</th><th>销售额</th><th>销量</th></tr></thead><tbody>`;
    items.forEach(it=>{
      html += `<tr><td>${it.name}</td><td><span class="tag">${it.group_name||'-'}</span></td>
        <td>${money(it.amt)}</td><td>${fmt(it.qty)}</td></tr>`;
    });
    html += `</tbody></table></div>`;
  });
  document.getElementById('topItems').innerHTML = html;
}

function achRange(p){
  const m=DATA.meta;
  if(p==='week_cur') return [m.week.start, m.week.end];
  if(p==='week_prev') return [addDays(m.week.start,-7), addDays(m.week.end,-7)];
  if(p==='month') return [m.month.start, m.month.end];
  if(p==='quarter') return [m.quarter.start, m.quarter.end];
  return ['', ''];
}
function renderAch(){
  const p=achPeriod;
  const label={week_cur:'本周',week_prev:'上周',month:'本月',quarter:'Q4 季度'}[p];
  document.getElementById('targetNote').textContent=CH+'渠道 · '+label;
  const rg=achRange(p);
  document.getElementById('achRange').textContent='（'+rg[0]+' ~ '+rg[1]+'）';
  const tkey=(p==='week_cur'||p==='week_prev')?'week':(p==='month'?'month':'quarter');
  let rows=achData().map(a=>{
    const act=a.actual[p]||0;
    const tg=(a.target||{})[tkey];
    const r=(tg&&tg>0)? act/tg*100 : null;
    return {a:a, act:act, tg:tg, r:r};
  });
  if(achSort==='desc') rows.sort((x,y)=>((y.r==null?-1:y.r)-(x.r==null?-1:x.r)));
  else if(achSort==='asc') rows.sort((x,y)=>((x.r==null?1e9:x.r)-(y.r==null?1e9:y.r)));
  let trows='', chart='';
  rows.forEach(o=>{
    const a=o.a, act=o.act, tg=o.tg, r=o.r;
    let cell;
    if(tg==null||tg===0){ cell='<td class="muted">待填</td>'; }
    else { cell=`<td><b style="color:${r>=100?'var(--down)':(r>=80?'var(--amber)':'var(--up)')}">${r.toFixed(1)}%</b></td>`; }
    trows += `<tr><td class="name">${a.name}</td>${cell}<td>${tg==null?'-':money(tg)}</td><td>${money(act)}</td></tr>`;
    const rv=(tg&&tg>0)? r : 0;
    const w=Math.min(rv,150)/150*100;
    const col=rv>=100?'var(--down)':(rv>=80?'var(--amber)':'var(--up)');
    const sp=(a.split&&a.split['视频号']&&a.split['小红书'])
      ? `（视频号 ${exact(a.split['视频号'][p])} + 小红书 ${exact(a.split['小红书'][p])}）` : '';
    const tip=(tg&&tg>0)
      ? `${a.name} · 达成率 ${r.toFixed(1)}%${sp}（达成 ${exact(act)} 元 / 目标 ${exact(tg)} 元）`
      : `${a.name} · 未设目标`;
    chart += `<div class="row" title="${tip}"><div class="lbl">${a.name}</div>
      <div class="track"><div class="fill" style="width:${w}%;background:${col}"></div>
        <div class="goal" style="left:66.667%"></div></div>
      <div class="pct">${(tg&&tg>0)?r.toFixed(1)+'%':'-'}</div></div>`;
  });
  document.getElementById('targetTable').innerHTML =
    `<table><thead><tr><th>组</th><th>达成率</th><th>目标</th><th>达成</th></tr></thead><tbody>${trows}</tbody></table>
     <div class="empty">目标为${CH}渠道；各组分设目标（服配 / 服配-羽绒 各自独立）；「待填」表示尚未设目标。</div>`;
  document.getElementById('achChart').innerHTML = chart +
    `<div class="muted" style="font-size:11.5px;margin-top:2px">灰线 = 100% 目标线（进度条满格为 150%）；鼠标悬停可看具体达成率</div>`;
}

function setRangeInputs(){
  document.getElementById('sFrom').value = salesRange[0];
  document.getElementById('sTo').value = salesRange[1];
}

document.getElementById('channelSeg').addEventListener('click', e=>{
  const b=e.target.closest('button'); if(!b || b.disabled) return;
  if(b.dataset.c==='视频号' && !DATA.video) return;
  [...e.currentTarget.children].forEach(x=>x.classList.toggle('on', x===b));
  CH=b.dataset.c;
  renderHeader(); renderSales(); renderAch();
});
document.getElementById('salesSeg').addEventListener('click', e=>{
  const b=e.target.closest('button'); if(!b) return;
  [...e.currentTarget.children].forEach(x=>x.classList.toggle('on', x===b));
  salesRange = presetRange(b.dataset.p);
  setRangeInputs(); renderSales();
});
['sFrom','sTo'].forEach(id=>document.getElementById(id).addEventListener('change', ()=>{
  const a=document.getElementById('sFrom').value, b=document.getElementById('sTo').value;
  if(a && b){
    salesRange=[a,b];
    document.querySelectorAll('#salesSeg button').forEach(x=>x.classList.remove('on'));
    renderSales();
  }
}));
document.getElementById('achSeg').addEventListener('click', e=>{
  const b=e.target.closest('button'); if(!b) return;
  [...e.currentTarget.children].forEach(x=>x.classList.toggle('on', x===b));
  achPeriod=b.dataset.p; renderAch();
});
document.getElementById('achSortSeg').addEventListener('click', e=>{
  const b=e.target.closest('button'); if(!b) return;
  [...e.currentTarget.children].forEach(x=>x.classList.toggle('on', x===b));
  achSort=b.dataset.s; renderAch();
});

renderHeader();
setRangeInputs();
renderSales();
renderAch();
if(!DATA.video){ const vb=document.querySelector('#channelSeg button[data-c="视频号"]'); if(vb){ vb.disabled=true; vb.title='暂无视频号数据'; } }
if(!DATA.kuaishou){ const kb=document.querySelector('#channelSeg button[data-c="快手"]'); if(kb){ kb.disabled=true; kb.title='暂无快手数据'; } }
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default=None)
    ap.add_argument('--out', default=None)
    args = ap.parse_args()
    data_path = args.data or os.path.join(BASE, 'dashboard_data.json')
    out_path = args.out or os.path.join(BASE, 'dashboard.html')
    data = json.load(open(data_path, encoding='utf-8'))
    html = TEMPLATE.replace('/*__DATA__*/', json.dumps(data, ensure_ascii=False))
    open(out_path, 'w', encoding='utf-8').write(html)
    print('已生成:', out_path, '(%.1f KB)' % (len(html.encode('utf-8')) / 1024))


if __name__ == '__main__':
    main()
