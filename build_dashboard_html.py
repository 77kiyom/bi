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
    --brand:#4f46e5; --brand2:#6366f1; --bg:#f4f6fa; --card:#ffffff;
    --line:#e3e8f0; --txt:#1f2733; --muted:#7b8794; --up:#c0392b; --down:#1e8e5a;
    --amber:#c77c00;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--txt);
    font-family:"Microsoft YaHei","PingFang SC","Helvetica Neue",Arial,sans-serif;
    -webkit-font-smoothing:antialiased}
  .wrap{max-width:1280px;margin:0 auto;padding:22px 20px 60px}
  header{display:flex;flex-wrap:wrap;align-items:baseline;gap:14px;margin-bottom:16px}
  header h1{margin:0;font-size:22px;letter-spacing:.5px;color:var(--txt)}
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
  .panel h2{margin:0 0 12px;font-size:15px;color:var(--txt);font-weight:700;
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
  th{background:#f6f7fd;color:#4a5160;font-weight:700;font-size:12.5px;white-space:nowrap;
    border-bottom:2px solid #e7e9f2;letter-spacing:.2px}
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
<style>
  /* ── 日报视图 ── */
  .cards5{display:grid;grid-template-columns:repeat(auto-fit,minmax(178px,1fr));gap:14px}
  .kpi{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px;box-shadow:var(--shadow)}
  .kpi .kl{font-size:12.5px;color:var(--muted);margin-bottom:6px}
  .kpi .kv{font-size:25px;font-weight:800;letter-spacing:-.5px}
  .kpi .ks{font-size:12.5px;color:var(--muted);margin-top:4px;display:flex;gap:6px;align-items:center}
  .pbar{height:6px;background:#e2e8f0;border-radius:3px;overflow:hidden;margin-top:8px}
  .pbar>i{display:block;height:100%;border-radius:3px;background:var(--brand)}
  .tag2{display:inline-block;padding:1px 7px;border-radius:4px;font-size:11.5px;font-weight:600}
  .tag2.g{background:#d1fae5;color:#065f46}
  .tag2.y{background:#fef3c7;color:#92400e}
  .tag2.r{background:#fee2e2;color:#991b1b}
  .d-row2{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}
  .pbar-label{display:flex;justify-content:space-between;font-size:12px;color:var(--muted);margin-top:9px;margin-bottom:4px}
  .kpi .kv{font-variant-numeric:tabular-nums}
  @media(max-width:900px){ .d-row2{grid-template-columns:1fr} }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1 id="h1">抖音居家商务组</h1>
    <div class="sub" id="subline"></div>
  </header>

  <div class="toolbar">
    <div class="seg" id="channelSeg">
      <button data-v="daily" id="btnDaily">日报</button>
      <button data-v="channel" data-c="抖音" class="on ch-btn">抖音</button>
      <button data-v="channel" data-c="快手" class="ch-btn">快手</button>
      <button data-v="channel" data-c="视频号" class="ch-btn">视频号</button>
    </div>
  </div>

  <div class="panel">
    <h2>⏱️ 时间进度 <small id="progNote"></small></h2>
    <div class="prog-grid" id="progGrid"></div>
  </div>

  <div id="viewChannel">
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
    <h2>📋 销售额明细 <small id="salesNote"></small></h2>
    <div id="dailyTable"></div>
  </div>

  <div class="panel">
    <h2>🔥 Top 单品 <small id="topNote">销售额 ≥ 1 万</small></h2>
    <div class="filterbar" style="margin-bottom:12px">
      <span class="lb">渠道组</span>
      <div class="seg" id="topGroupSeg"></div>
      <span class="lb">所属小组</span>
      <select id="topSubSel" style="border:1px solid var(--line);border-radius:7px;padding:6px 8px;
        font-size:12.5px;font-family:inherit;background:#fff;color:var(--txt)"></select>
      <span class="lb" style="margin-left:auto">排序</span>
      <div class="seg" id="topSortSeg">
        <button data-s="amt" class="on">销售额</button>
        <button data-s="qty">销量</button>
      </div>
    </div>
    <div id="topItems"></div>
  </div>

  <div class="panel">
    <h2>🎯 达成率 <small id="targetNote">抖音渠道</small></h2>
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
  </div><!-- /#viewChannel -->

  <!-- ════ 日报视图 ════ -->
  <div id="viewDaily" style="display:none">
    <div class="cards5" id="kpiGrid" style="margin-bottom:16px"></div>
    <div class="d-row2">
      <div class="panel" style="margin:0">
        <h2>📉 近 7 天销售额趋势 <small>（万元）</small></h2>
        <div id="trendChart"></div>
      </div>
      <div class="panel" style="margin:0">
        <h2>🔥 爆品周完成率 <small>（分品线）</small></h2>
        <div id="boomTable"></div>
      </div>
    </div>
    <div class="panel" style="margin-top:16px">
      <h2>🏷️ Top 达人 / 直播间 <small>按当日销售额</small></h2>
      <div id="anchorTable"></div>
    </div>
    <div class="panel">
      <h2>🎯 Top 商品 <small>按当日销售额</small></h2>
      <div id="itemTable"></div>
    </div>
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
  const gsAll = groupsData();
  let grand = 0;
  gsAll.forEach(g=>{ grand += sumRange(g,d0,d1)[0]; });
  const ACC = ['#3b82f6','#10b981','#8b5cf6','#f97316','#14b8a6'];
  let cards='', rows='', tAll=[0,0,0];
  gsAll.forEach((g,gi)=>{
    const v=sumRange(g,d0,d1); tAll[0]+=v[0]; tAll[1]+=v[1]; tAll[2]+=v[2];
    const pv=sumRange(g,pv0,pv1);
    const mom = pv[0]>0? ((v[0]-pv[0])/pv[0]*100) : null;
    const momTxt = mom==null? '<span class="muted">-</span>' :
      `<b style="color:${mom>=0?'var(--up)':'var(--down)'}">${mom>=0?'▲':'▼'} ${Math.abs(mom).toFixed(1)}%</b>`;
    const share = grand>0? v[0]/grand*100 : 0;
    const ac = ACC[gi%ACC.length];
    cards += `<div class="kpi" style="border-left:4px solid ${ac}"><div class="kl">${g.name}</div>
      <div class="kv" title="${exact(v[0])} 元">${wan(v[0])}</div>
      <div class="ks" style="justify-content:space-between"><span>销量 ${fmt(v[2])}</span><span>环比 ${momTxt}</span></div>
      <div class="pbar"><i style="width:${Math.min(share,100).toFixed(1)}%;background:${ac}"></i></div>
      <div class="ks" style="margin-top:5px;justify-content:space-between"><span>占比</span><b>${share.toFixed(1)}%</b></div></div>`;
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

  renderTop();
}

let topGroup='all', topSort='amt', topSub='all';
function renderTop(){
  const d0=salesRange[0], d1=salesRange[1];
  const all = groupsData();
  const names = all.map(g=>g.name);
  if(topGroup!=='all' && names.indexOf(topGroup)<0) topGroup='all';
  const gseg=document.getElementById('topGroupSeg');
  if(gseg){
    gseg.innerHTML = ['all'].concat(names).map(n=>
      '<button data-g="'+n+'"'+(n===topGroup?' class="on"':'')+'>'+(n==='all'?'全部':n)+'</button>').join('');
  }
  const gs = topGroup==='all' ? all : all.filter(g=>g.name===topGroup);
  let rows=[];
  gs.forEach(g=>{
    topInRange(g,d0,d1).forEach(it=>{
      rows.push({name:it.name, group:it.group_name||'-', gname:g.name, amt:it.amt, qty:it.qty});
    });
  });
  // 所属小组筛选（按当前渠道组下的实际 group_name 生成）
  const subs = Array.from(new Set(rows.map(r=>r.group))).sort();
  if(topSub!=='all' && subs.indexOf(topSub)<0) topSub='all';
  const ssel=document.getElementById('topSubSel');
  if(ssel){
    ssel.innerHTML = ['all'].concat(subs).map(s=>
      '<option value="'+s+'"'+(s===topSub?' selected':'')+'>'+(s==='all'?'全部小组':s)+'</option>').join('');
  }
  if(topSub!=='all') rows = rows.filter(r=>r.group===topSub);
  rows.sort((a,b)=> topSort==='qty' ? (b.qty-a.qty) : (b.amt-a.amt));
  const el=document.getElementById('topItems');
  if(!rows.length){
    el.innerHTML = '<div class="empty">该区间内没有符合条件的单品（销售额 ≥ '+(topThreshold()>=10000?'1 万':'1000')+'）</div>';
    return;
  }
  let html='<table><thead><tr><th>#</th><th>商品名称</th><th>所属小组</th><th>渠道组</th>'+
    '<th style="text-align:right">销售额</th><th style="text-align:right">销量</th></tr></thead><tbody>';
  rows.forEach((it,i)=>{
    html+='<tr><td>'+(i+1)+'</td><td>'+it.name+'</td><td><span class="tag">'+it.group+'</span></td>'+
      '<td>'+it.gname+'</td><td style="text-align:right">'+money(it.amt)+'</td>'+
      '<td style="text-align:right">'+fmt(it.qty)+'</td></tr>';
  });
  el.innerHTML = html+'</tbody></table>';
}
document.getElementById('topGroupSeg').addEventListener('click', e=>{
  const b=e.target.closest('button'); if(!b) return;
  topGroup=b.dataset.g; renderTop();
});
document.getElementById('topSortSeg').addEventListener('click', e=>{
  const b=e.target.closest('button'); if(!b) return;
  [...e.currentTarget.children].forEach(x=>x.classList.toggle('on', x===b));
  topSort=b.dataset.s; renderTop();
});
document.getElementById('topSubSel').addEventListener('change', e=>{
  topSub=e.target.value; renderTop();
});

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
  const v = b.dataset.v || 'channel';
  const seg = e.currentTarget;
  if(v==='daily'){
    if(!DATA.extra) return;
    VIEW = 'daily';
  } else {
    if(b.dataset.c==='视频号' && !DATA.video) return;
    VIEW = 'channel'; CH = b.dataset.c;
  }
  [...seg.children].forEach(x=>{
    if(x.dataset.v==='daily') x.classList.toggle('on', VIEW==='daily');
    else x.classList.toggle('on', VIEW==='channel' && x.dataset.c===CH);
  });
  document.getElementById('viewChannel').style.display = VIEW==='channel'?'':'none';
  document.getElementById('viewDaily').style.display = VIEW==='daily'?'':'none';
  if(VIEW==='daily') renderDaily();
  else { renderHeader(); renderSales(); renderAch(); }
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

// ════════ 日报视图 ════════
let VIEW = 'channel';
const DGROUPS = ['家纺','家具百货组','服配','服配-羽绒'];
const DCOLOR = {'家纺':'#2F5597','家具百货组':'#1e8e5a','服配':'#c77c00','服配-羽绒':'#8b5cf6'};

function dSum(daily,d0,d1){ let a=0,q=0; for(const k in daily){ if(k<d0||k>d1) continue; a+=daily[k][0]; q+=daily[k][2]; } return [a,q]; }
function dGroupSum(d0,d1){ let a=0,q=0; (DATA.groups||[]).forEach(g=>{ if(DGROUPS.indexOf(g.name)<0) return; const v=dSum(g.daily,d0,d1); a+=v[0]; q+=v[1]; }); return [a,q]; }
function dTargetSum(k){ let t=0; (DATA.ach||[]).forEach(a=>{ if(DGROUPS.indexOf(a.name)<0) return; const v=(a.target||{})[k]; if(v) t+=v; }); return t; }
function dMom(cur,prev){
  if(!prev) return '<span style="color:var(--muted)">—</span>';
  const r=(cur-prev)/prev*100;
  if(Math.abs(r)<0.05) return '<span style="color:var(--muted)">→ 持平</span>';
  const c=r>0?'var(--up)':'var(--down)';
  return '<span style="color:'+c+'">'+(r>0?'▲':'▼')+' '+Math.abs(r).toFixed(1)+'%</span>';
}
function dTag(rate){
  if(rate==null) return '<span class="tag2 y">待填</span>';
  if(rate>=100) return '<span class="tag2 g">优秀</span>';
  if(rate>=80) return '<span class="tag2 y">良好</span>';
  return '<span class="tag2 r">关注</span>';
}
function prevMonthStart(s){
  let y=Number(s.slice(0,4)), m=Number(s.slice(5,7))-1;
  if(m===0){ m=12; y--; }
  return y+'-'+String(m).padStart(2,'0')+'-01';
}
function monthLastDay(ym){
  const y=Number(ym.slice(0,4)), m=Number(ym.slice(5,7));
  return iso(new Date(Date.UTC(y, m, 0)));
}

function renderDaily(){
  const ex = DATA.extra || {};
  const LATEST = (ex.meta && ex.meta.data_to) || (DATA.meta && DATA.meta.data_to);
  const grid = document.getElementById('kpiGrid');
  if(!LATEST){ grid.innerHTML='<div class="muted" style="padding:20px">暂无日报数据</div>'; return; }
  document.getElementById('subline').textContent =
    '日报 · 日报日期 '+LATEST+' · 更新于 '+((ex.meta&&ex.meta.updated_at)||(DATA.meta&&DATA.meta.updated_at)||'');

  const PREV = addDays(LATEST,-1);
  const wStart = addDays(LATEST, -new Date(LATEST).getUTCDay());
  const wPrevStart = addDays(wStart,-7), wPrevEnd = addDays(LATEST,-7);
  const mStart = LATEST.slice(0,7)+'-01';
  const pmStart = prevMonthStart(LATEST);
  const pmEnd = monthLastDay(pmStart.slice(0,7));
  const qStart = (DATA.meta.quarter||{}).start || '2026-10-01';
  const qPrevStart = '2026-07-01', qPrevEnd = '2026-09-30';

  const day = dGroupSum(LATEST,LATEST), dayP = dGroupSum(PREV,PREV);
  const wk = dGroupSum(wStart,LATEST), wkP = dGroupSum(wPrevStart,wPrevEnd);
  const mo = dGroupSum(mStart,LATEST), moP = dGroupSum(pmStart,pmEnd);
  const qt = dGroupSum(qStart,LATEST), qtP = dGroupSum(qPrevStart,qPrevEnd);
  const orders = (ex.order_daily||{})[LATEST]||0;
  const ordersP = (ex.order_daily||{})[PREV]||0;

  const tW = dTargetSum('week'), tM = dTargetSum('month'), tQ = dTargetSum('quarter');
  const tD = tW/7;

  const cards = [
    {l:'📦 日总销售额',   v:'¥'+fmt(day[0]),  ml:'环比昨日',     m:dMom(day[0],dayP[0]), r:tD?day[0]/tD*100:null, tn:'日目标完成率'},
    {l:'📋 日订单量',     v:fmt(orders),      ml:'环比昨日',     m:dMom(orders,ordersP), r:null, tn:'日订单目标完成率'},
    {l:'📊 周累计销售额', v:'¥'+fmt(wk[0]),   ml:'环比上周同期', m:dMom(wk[0],wkP[0]),   r:tW?wk[0]/tW*100:null, tn:'周目标完成率'},
    {l:'📈 月累计销售额', v:'¥'+fmt(mo[0]),   ml:'环比上月同期', m:dMom(mo[0],moP[0]),   r:tM?mo[0]/tM*100:null, tn:'月目标完成率'},
    {l:'📆 季度累计销售额', v:'¥'+fmt(qt[0]), ml:'环比上季度同期', m:dMom(qt[0],qtP[0]), r:tQ?qt[0]/tQ*100:null, tn:'季度目标完成率'}
  ];
  const ACC5 = ['#3b82f6','#10b981','#8b5cf6','#f97316','#14b8a6'];
  grid.innerHTML = cards.map((c,i)=>{
    const ac = ACC5[i%ACC5.length];
    const rv = c.r==null? 0 : Math.min(c.r,100);
    const rt = c.r==null? '—' : c.r.toFixed(1)+'%';
    return '<div class="kpi" style="border-left:4px solid '+ac+'">'+
      '<div class="kl">'+c.l+'</div>'+
      '<div class="kv">'+c.v+'</div>'+
      '<div class="ks"><span>'+c.ml+'</span>'+c.m+'</div>'+
      '<div class="pbar-label"><span>'+c.tn+'</span><span>'+rt+'</span></div>'+
      '<div class="pbar"><i style="width:'+rv.toFixed(1)+'%;background:'+ac+'"></i></div>'+
      '</div>';
  }).join('');

  // 趋势（近7天，4品线，内联 SVG）
  const days=[]; for(let i=6;i>=0;i--) days.push(addDays(LATEST,-i));
  const series = DGROUPS.map(nm=>{
    const g=(DATA.groups||[]).find(x=>x.name===nm);
    return {name:nm, color:DCOLOR[nm]||'#94a3b8',
      data: days.map(d=>{ const v=g&&g.daily?g.daily[d]:null; return v? v[0]/10000 : 0; })};
  });
  const W=640,H=250,PL=44,PR=12,PT=14,PB=32, iw=W-PL-PR, ih=H-PT-PB;
  let maxV=0; series.forEach(s=>s.data.forEach(v=>{ if(v>maxV) maxV=v; }));
  maxV = maxV>0? maxV*1.15 : 1;
  const xf = i => PL + iw*i/(days.length-1);
  const yf = v => PT + ih - ih*(v/maxV);
  let svg='<svg viewBox="0 0 '+W+' '+H+'" style="width:100%;height:auto"><defs>';
  series.forEach((s,si)=>{
    svg+='<linearGradient id="tg'+si+'" x1="0" y1="0" x2="0" y2="1">'+
      '<stop offset="0%" stop-color="'+s.color+'" stop-opacity=".20"/>'+
      '<stop offset="100%" stop-color="'+s.color+'" stop-opacity="0"/></linearGradient>';
  });
  svg+='</defs>';
  for(let k=0;k<=4;k++){
    const v=maxV*k/4, yy=yf(v);
    svg+='<line x1="'+PL+'" y1="'+yy+'" x2="'+(W-PR)+'" y2="'+yy+'" stroke="#eef2f7"/>';
    svg+='<text x="'+(PL-8)+'" y="'+(yy+4)+'" text-anchor="end" font-size="11" fill="#94a3b8">'+v.toFixed(0)+'w</text>';
  }
  days.forEach((d,i)=>{ svg+='<text x="'+xf(i)+'" y="'+(H-10)+'" text-anchor="middle" font-size="11" fill="#94a3b8">'+d.slice(5)+'</text>'; });
  series.forEach((s,si)=>{
    const pts = s.data.map((v,i)=>xf(i)+','+yf(v));
    svg+='<polygon points="'+PL+','+(PT+ih)+' '+pts.join(' ')+' '+(W-PR)+','+(PT+ih)+'" fill="url(#tg'+si+')"/>';
    svg+='<polyline points="'+pts.join(' ')+'" fill="none" stroke="'+s.color+'" stroke-width="2.5" stroke-linejoin="round"/>';
    s.data.forEach((v,i)=>{ svg+='<circle cx="'+xf(i)+'" cy="'+yf(v)+'" r="3" fill="'+s.color+'"/>'; });
  });
  // 悬停：整列显示当天各品线具体销售额
  const bw = iw/Math.max(days.length-1,1);
  const fmtY = v => (v*10000).toLocaleString('zh-CN',{maximumFractionDigits:0});
  days.forEach((d,i)=>{
    const x0 = Math.max(PL, xf(i)-bw/2);
    const w0 = Math.min(bw, W-PR-x0);
    const tip = d+' 销售额 ｜ '+series.map(s=>s.name+' '+fmtY(s.data[i])+' 元').join(' ｜ ');
    svg+='<rect x="'+x0+'" y="'+PT+'" width="'+w0+'" height="'+ih+'" fill="transparent"><title>'+tip+'</title></rect>';
  });
  series.forEach(s=>{
    s.data.forEach((v,i)=>{
      svg+='<circle cx="'+xf(i)+'" cy="'+yf(v)+'" r="9" fill="transparent"><title>'+
        days[i]+' · '+s.name+'：'+fmtY(v)+' 元</title></circle>';
    });
  });
  svg+='</svg>';
  let legend='<div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:8px;font-size:12px;color:var(--muted)">';
  series.forEach(s=>{ legend+='<span><i style="display:inline-block;width:8px;height:8px;border-radius:50%;background:'+s.color+';margin-right:5px"></i>'+s.name+'</span>'; });
  legend+='</div>';
  document.getElementById('trendChart').innerHTML = svg+legend;

  // 爆品周完成率（分品线）—— 数据待接入，保留表格位置
  const weeks=[]; let ws=wStart;
  for(let i=0;i<4;i++){ weeks.unshift(ws); ws=addDays(ws,-7); }
  const weekNo = s => {
    const d = new Date(s+'T00:00:00Z');
    const jan1 = new Date(Date.UTC(d.getUTCFullYear(),0,1));
    return Math.floor((d-jan1)/604800000)+1;
  };
  let bh='<table><thead><tr><th>品线</th>';
  weeks.forEach(w=>{ bh+='<th style="text-align:right">第'+weekNo(w)+'周</th>'; });
  bh+='<th style="text-align:right">周环比</th></tr></thead><tbody>';
  ['家纺','家具百货组','服配','服配-羽绒'].forEach(nm=>{
    bh+='<tr><td class="name">'+nm+'</td>';
    for(let i=0;i<4;i++) bh+='<td style="text-align:right"><span class="muted">—</span></td>';
    bh+='<td style="text-align:right"><span class="muted">—</span></td></tr>';
  });
  bh+='</tbody></table><div class="empty" style="margin-top:6px">爆品周完成率数据待接入（表格位置已保留）</div>';
  document.getElementById('boomTable').innerHTML = bh;

  // Top 达人 / 直播间
  const totalDay = day[0];
  const alist = (ex.anchors||[]).map(a=>{
    const dv=a.daily||{};
    return {name:a.name, day:(dv[LATEST]||[0])[0], prev:(dv[PREV]||[0])[0],
            wk:dSum(dv,wStart,LATEST)[0], mo:dSum(dv,mStart,LATEST)[0]};
  }).filter(x=>x.day>0).sort((a,b)=>b.day-a.day).slice(0,10);
  let ah='<table><thead><tr><th>#</th><th>达人 / 直播间</th><th style="text-align:right">日销售额</th>'+
    '<th style="text-align:right">日环比</th><th style="text-align:right">占当日</th>'+
    '<th style="text-align:right">周累计</th><th style="text-align:right">月累计</th><th>趋势</th></tr></thead><tbody>';
  alist.forEach((x,i)=>{
    const sh = totalDay? x.day/totalDay*100 : 0;
    ah+='<tr><td>'+(i+1)+'</td><td class="name">'+x.name+'</td>'+
      '<td style="text-align:right">'+money(x.day)+'</td>'+
      '<td style="text-align:right">'+dMom(x.day,x.prev)+'</td>'+
      '<td style="text-align:right">'+sh.toFixed(1)+'%</td>'+
      '<td style="text-align:right">'+money(x.wk)+'</td>'+
      '<td style="text-align:right">'+money(x.mo)+'</td>'+
      '<td>'+dTag(sh>=5?100:(sh>=2?85:60))+'</td></tr>';
  });
  document.getElementById('anchorTable').innerHTML = ah+'</tbody></table>';

  // Top 商品
  const imap={};
  (DATA.groups||[]).forEach(g=>{
    if(DGROUPS.indexOf(g.name)<0) return;
    const ids=g.item_daily||{};
    for(const iid in ids){
      const dv=ids[iid];
      let d=0,w=0,m=0;
      for(const k in dv){
        if(k===LATEST) d+=dv[k][0];
        if(k>=wStart && k<=LATEST) w+=dv[k][0];
        if(k>=mStart && k<=LATEST) m+=dv[k][0];
      }
      if(d<=0) continue;
      const info=(g.top_items||[]).find(t=>t.item_id===iid)||{};
      imap[g.name+'|'+iid]={name:info.name||iid, group:g.name, day:d, wk:w, mo:m};
    }
  });
  const ilist=Object.keys(imap).map(k=>imap[k]).sort((a,b)=>b.day-a.day).slice(0,10);
  const medal=['🥇','🥈','🥉'];
  let ih2='<table><thead><tr><th>排名</th><th>商品名称</th><th>品线</th>'+
    '<th style="text-align:right">日销售额</th><th style="text-align:right">占当日</th>'+
    '<th style="text-align:right">周累计</th><th style="text-align:right">月累计</th></tr></thead><tbody>';
  ilist.forEach((x,i)=>{
    const sh = totalDay? x.day/totalDay*100 : 0;
    ih2+='<tr><td>'+(medal[i]||(i+1))+'</td><td class="name">'+x.name+'</td><td>'+x.group+'</td>'+
      '<td style="text-align:right">'+money(x.day)+'</td>'+
      '<td style="text-align:right">'+sh.toFixed(1)+'%</td>'+
      '<td style="text-align:right">'+money(x.wk)+'</td>'+
      '<td style="text-align:right">'+money(x.mo)+'</td></tr>';
  });
  document.getElementById('itemTable').innerHTML = ih2+'</tbody></table>';
}

renderHeader();
setRangeInputs();
renderSales();
renderAch();
if(!DATA.video){ const vb=document.querySelector('#channelSeg button[data-c="视频号"]'); if(vb){ vb.disabled=true; vb.title='暂无视频号数据'; } }
if(!DATA.extra){ const db=document.getElementById('btnDaily'); if(db){ db.disabled=true; db.title='暂无日报数据'; } }
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
    # 日报视图需要的数据（订单量 + 达人日明细），来自 build_dashboard_data.py 的 daily_extra.json
    extra_path = os.path.join(BASE, 'daily_extra.json')
    if os.path.exists(extra_path):
        try:
            extra = json.load(open(extra_path, encoding='utf-8'))
            anchors = extra.get('anchors') or []
            anchors.sort(key=lambda a: -sum(v[0] for v in (a.get('daily') or {}).values()))
            extra['anchors'] = anchors[:80]
            data['extra'] = extra
        except Exception as e:
            print('  [警告] daily_extra.json 读取失败:', type(e).__name__)
    html = TEMPLATE.replace('/*__DATA__*/', json.dumps(data, ensure_ascii=False))
    open(out_path, 'w', encoding='utf-8').write(html)
    print('已生成:', out_path, '(%.1f KB)' % (len(html.encode('utf-8')) / 1024))


if __name__ == '__main__':
    main()
