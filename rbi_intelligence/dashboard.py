"""A self-contained, offline research dashboard from validated analytical data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from .database import json_safe, validate_inputs


def build_dashboard(
    output_path: str | Path,
    events: pd.DataFrame,
    results: pd.DataFrame,
    forecasts: pd.DataFrame | None = None,
    *,
    manifest: Mapping[str, Any] | None = None,
) -> Path:
    """Render an offline HTML dashboard; no server, CDN, or account required.

    The interface distinguishes announcements from bank-event records and daily
    conditional volatility from realised multi-day abnormal returns. Validation
    covers internal integrity, not independent authentication of data providers.
    """
    data = validate_inputs(events, results, forecasts)
    payload = {
        "events": data.events.sort_values("event_date").to_dict(orient="records"),
        "results": data.results.sort_values(["event_date", "bank_symbol", "benchmark", "window"]).to_dict(orient="records"),
        "forecasts": data.forecasts.to_dict(orient="records"),
        "banks": data.banks.to_dict(orient="records"),
        "manifest": dict(manifest or {}),
        "validation": {
            "event_count": len(data.events),
            "bank_count": len(data.banks),
            "result_rows": len(data.results),
            "forecast_rows": len(data.forecasts),
            "checks": ["Unique event, bank, and result keys", "Finite CAR values", "Consistent event dates and decisions", "Forecast origin precedes event-date target", "Convergence and variance/volatility consistency"],
        },
    }
    # Escaping '<' prevents a data value containing '</script>' from escaping the
    # JSON script element. User-sourced strings are also escaped at DOM insertion.
    serialized = json.dumps(json_safe(payload), ensure_ascii=False, allow_nan=False).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(HTML.replace("__PAYLOAD__", serialized), encoding="utf-8")
    return output_path


HTML = r'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="An offline research dashboard of Indian banking-stock abnormal returns around RBI policy announcements.">
<title>RBI Banking Market Intelligence · Research dashboard</title>
<style>
:root{--ink:#182a37;--muted:#66777f;--teal:#087f75;--teal-soft:#e5f3ef;--purple:#7664a3;--coral:#c8664f;--amber:#9a6a22;--line:#dfe5e2;--paper:#f5f5ef;--white:#fff;--navy:#193d4d;--shadow:0 8px 26px #18303b05}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}button,select{font:inherit}button,select,a{touch-action:manipulation}button{cursor:pointer}button:focus-visible,select:focus-visible,a:focus-visible,summary:focus-visible,[tabindex]:focus-visible{outline:3px solid #19a598;outline-offset:3px}a{color:var(--teal)}.shell{max-width:1440px;margin:0 auto;padding:0 44px}.topbar{height:76px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line);gap:20px}.brand{display:flex;align-items:center;gap:12px;font-size:12px;font-weight:750;letter-spacing:.14em;text-transform:uppercase}.brandmark{width:33px;height:33px;background:var(--navy);color:white;border-radius:9px;display:grid;place-items:center;font-size:18px;letter-spacing:0}.toplinks{display:flex;gap:25px;font-size:12px}.toplinks a{color:var(--muted);text-decoration:none}.hero{padding:42px 0 30px;display:flex;align-items:flex-end;justify-content:space-between;gap:30px}.eyebrow{color:var(--teal);font-size:11px;font-weight:750;text-transform:uppercase;letter-spacing:.17em;margin:0 0 12px}.hero h1{font-size:clamp(28px,3.8vw,47px);line-height:1.13;letter-spacing:-.04em;font-weight:680;margin:0;max-width:820px}.hero p{color:var(--muted);max-width:720px;margin:16px 0 0;font-size:14px}.badge{display:inline-flex;align-items:center;gap:7px;padding:7px 12px;background:var(--teal-soft);border:1px solid #cce4db;border-radius:30px;color:#276c58;font-size:11px;font-weight:650;white-space:nowrap}.dot{height:6px;width:6px;border-radius:50%;background:currentColor}.snapshot{display:flex;gap:22px;align-items:center;color:var(--muted);font-size:12px;margin-bottom:24px;flex-wrap:wrap}.snapshot b{color:var(--ink);font-weight:600}.filters{background:var(--white);border:1px solid var(--line);border-radius:14px;padding:17px 20px;display:grid;grid-template-columns:1.1fr 1.2fr .8fr .9fr 1.45fr auto;gap:14px;align-items:end;box-shadow:var(--shadow)}.filter label{display:block;font-size:10px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px}.filter select{width:100%;height:38px;border:1px solid #dce3df;border-radius:7px;background:#fafbf8;color:var(--ink);padding:0 9px;font-size:12px}.quiet{height:38px;padding:0 12px;border:1px solid var(--line);border-radius:7px;background:white;color:var(--muted);font-size:12px}.quiet:hover{border-color:var(--teal);color:var(--teal)}.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:22px 0 12px}.kpi{background:var(--white);padding:21px 23px 18px;border:1px solid var(--line);border-radius:13px;box-shadow:var(--shadow)}.kpi-label{font-size:11px;color:var(--muted);font-weight:550}.kpi-value{font-size:34px;font-weight:650;line-height:1.2;letter-spacing:-.035em;margin:9px 0 5px;font-variant-numeric:tabular-nums}.kpi-foot{font-size:10px;color:var(--muted)}.kpi-value.accent{color:var(--teal)}.selection-note{font-size:11px;color:var(--muted);margin:0 2px 20px}.caution{margin-bottom:23px;border-left:3px solid #d0a56c;padding:11px 15px;background:#f4eddf;color:#785a31;font-size:12px;border-radius:0 8px 8px 0}.caution strong{font-weight:650}.grid{display:grid;grid-template-columns:1.7fr 1fr;gap:20px;margin-bottom:20px}.panel{background:white;border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow);overflow:hidden;min-width:0}.panel-head{padding:21px 24px 0;display:flex;justify-content:space-between;gap:20px;align-items:flex-start}.panel h2{font-size:15px;font-weight:650;line-height:1.35;margin:0}.sub{font-size:11px;color:var(--muted);margin:5px 0 0}.legend{display:flex;gap:13px;font-size:10px;color:var(--muted);white-space:nowrap;flex-wrap:wrap}.legend span{display:inline-flex;align-items:center;gap:5px}.legend i{display:inline-block;width:7px;height:7px;border-radius:2px}.chart{padding:5px 14px 0;min-height:120px}.chart svg{display:block;width:100%;height:auto}.chart-note{padding:0 24px 19px;font-size:10px;color:var(--muted);margin:0}.chart svg text{font-family:inherit;fill:var(--muted);font-size:10px}.chart svg .axis-label{font-size:11px}.chart svg .gridline{stroke:#e9eeea;stroke-width:1}.chart svg .baseline{stroke:#9aa9a8;stroke-width:1}.chart svg .eventbar:hover{opacity:.75}.chart svg .point:hover{stroke:var(--ink);stroke-width:1.5;opacity:1}.empty{padding:62px 20px;text-align:center;color:var(--muted);font-size:13px}.explain{padding:23px 26px}.explain h2{font-size:15px;margin:0 0 16px}.explain h3{font-size:12px;margin:18px 0 6px}.explain p{font-size:12px;color:var(--muted);margin:0}.mini-metric{display:flex;justify-content:space-between;gap:20px;padding:12px 0;border-bottom:1px solid var(--line);font-size:12px}.mini-metric strong{font-variant-numeric:tabular-nums}.method-tag{display:inline-block;margin-top:19px;background:#eff3f3;border:1px solid #e3e8e6;border-radius:6px;padding:6px 9px;font-size:10px;color:#506572}.table-panel{margin:0 0 22px}.table-head{padding-bottom:18px;align-items:center}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;white-space:nowrap}th{text-align:left;font-size:10px;font-weight:650;letter-spacing:.025em;color:var(--muted);background:#f8faf7;padding:11px 22px;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}td{padding:12px 22px;border-bottom:1px solid #edf0ec;font-size:12px;font-variant-numeric:tabular-nums}tr:last-child td{border-bottom:0}tbody tr:hover{background:#fafbf8}.num{text-align:right}.positive{color:var(--teal)}.negative{color:var(--coral)}.pill{display:inline-block;padding:3px 8px;font-size:10px;border-radius:5px;font-weight:600}.pill.cut{background:#e7f3ef;color:#267666}.pill.hold{background:#edf0f3;color:#526a7b}.pill.hike{background:#f6eddc;color:#987136}.source-link{font-size:9px;margin-left:6px;text-decoration:none;color:#8c9d9c}.provenance{margin-bottom:24px}.provenance summary{cursor:pointer;padding:19px 24px;font-size:13px;font-weight:600}.provenance-body{border-top:1px solid var(--line);padding:20px 24px;color:var(--muted);font-size:12px}.checks{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 18px}.check{padding:4px 9px;background:var(--teal-soft);border-radius:4px;color:#396d60;font-size:10px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:11px/1.7 ui-monospace,SFMono-Regular,Consolas,monospace;background:#f6f8f5;padding:16px;border-radius:8px;max-height:420px;overflow:auto;color:#425b60}.footer{padding:4px 0 30px;display:flex;justify-content:space-between;gap:20px;font-size:10px;color:var(--muted)}.noscript{padding:20px;background:#fff0da;border:1px solid #d6ab68}.sr-only{position:absolute;width:1px;height:1px;margin:-1px;padding:0;overflow:hidden;clip:rect(0,0,0,0);border:0}
@media(min-width:1250px){.chart.large{padding-top:13px}.chart.large svg{min-height:270px}}
@media(max-width:1050px){.shell{padding:0 25px}.filters{grid-template-columns:repeat(3,1fr)}.grid{grid-template-columns:1.4fr 1fr}.hero h1{font-size:35px}.toplinks{gap:14px}.panel-head{padding-left:18px;padding-right:18px}.legend{gap:8px}.kpi{padding:18px}.kpi-value{font-size:29px}}
@media(max-width:760px){.shell{padding:0 17px}.topbar{height:62px}.brand{font-size:10px;letter-spacing:.09em}.toplinks{display:none}.hero{padding-top:28px;display:block}.hero h1{font-size:32px}.hero .badge{margin-top:18px}.snapshot{gap:10px 20px}.filters{grid-template-columns:repeat(2,1fr);gap:12px;padding:15px}.kpis{grid-template-columns:repeat(2,1fr);gap:12px;margin-top:17px}.kpi{padding:16px}.kpi-value{font-size:29px}.grid{grid-template-columns:1fr;gap:17px;margin-bottom:17px}.panel-head{gap:10px;flex-wrap:wrap}.chart-note{padding-left:18px;padding-right:18px}.footer{display:block}.footer span{display:block;margin-bottom:5px}th,td{padding-left:16px;padding-right:16px}}
@media print{.filters,.quiet,.toplinks{display:none}.shell{padding:0}.hero{padding-top:18px}.panel,.kpi{break-inside:avoid;box-shadow:none}.provenance{display:none}.grid{grid-template-columns:1.5fr 1fr}body{background:white}.table-wrap{overflow:visible}table{font-size:10px}th,td{padding:7px}.footer{padding-bottom:0}}
</style>
</head>
<body>
<div class="shell">
<header class="topbar"><div class="brand"><span class="brandmark" aria-hidden="true">↗</span>RBI · Banking intelligence</div><nav class="toplinks" aria-label="Sections"><a href="#overview">Overview</a><a href="#announcements">Announcements</a><a href="#provenance">Data &amp; methods</a></nav></header>
<main>
<section class="hero" id="overview"><div><div class="eyebrow">Monetary policy · Indian banking stocks</div><h1>Policy announcements.<br>Measured market reactions.</h1><p>Explore abnormal stock returns around RBI announcements, with clear sample counts and past-only volatility forecasts.</p></div><span class="badge" title="Structural and numerical input checks passed. This is not independent authentication of the market-price source."><span class="dot"></span>Inputs validated</span></section>
<div class="snapshot"><span>Study period <b id="coverage">—</b></span><span>Market benchmarks <b id="benchmarkCount">—</b></span><span>Perspective <b>Historical, observational research</b></span></div>
<noscript><p class="noscript">Enable JavaScript to explore the embedded data. This file works offline and makes no data requests. The equivalent CSV tables are supplied with the project.</p></noscript>
<section class="filters" aria-label="Filter the study">
<div class="filter"><label for="benchmark">Benchmark</label><select id="benchmark"></select></div>
<div class="filter"><label for="window">Event window</label><select id="window"></select></div>
<div class="filter"><label for="decision">Policy decision</label><select id="decision"><option value="all">All decisions</option></select></div>
<div class="filter"><label for="bankType">Bank group</label><select id="bankType"><option value="all">All banks</option></select></div>
<div class="filter"><label for="event">Announcement date</label><select id="event"><option value="all">All announcements</option></select></div>
<button class="quiet" id="reset" type="button">Reset filters</button>
</section>
<section class="kpis" aria-label="Selected sample summary" aria-live="polite">
<div class="kpi"><div class="kpi-label">Policy announcements</div><div class="kpi-value" id="kpiEvents" data-testid="kpi-events">—</div><div class="kpi-foot">Distinct announcement dates</div></div>
<div class="kpi"><div class="kpi-label">Banks represented</div><div class="kpi-value" id="kpiBanks" data-testid="kpi-banks">—</div><div class="kpi-foot" id="recordCount">— bank–event records</div></div>
<div class="kpi"><div class="kpi-label">Mean CAR</div><div class="kpi-value accent" id="kpiCar" data-testid="kpi-car">—</div><div class="kpi-foot">Signed, across selected bank–event records</div></div>
<div class="kpi"><div class="kpi-label">Mean absolute CAR</div><div class="kpi-value" id="kpiAbsCar" data-testid="kpi-absolute-car">—</div><div class="kpi-foot">Movement magnitude, regardless of direction</div></div>
</section>
<p class="selection-note" id="selectionNote"></p>
<div class="caution" id="sampleWarning" role="status"></div>
<div class="grid">
<section class="panel"><div class="panel-head"><div><h2>Market reaction by announcement</h2><p class="sub">Mean CAR across the selected banks; each bar is one policy event.</p></div><div class="legend"><span><i style="background:var(--teal)"></i>Positive</span><span><i style="background:var(--coral)"></i>Negative</span></div></div><div class="chart large" id="chartEvents"></div><p class="chart-note">Select a bar to inspect an announcement. These are descriptive averages, not estimates of a causal policy effect.</p></section>
<section class="panel"><div class="panel-head"><div><h2>Event movement by bank</h2><p class="sub">Mean absolute CAR · selected event window</p></div></div><div class="chart" id="chartBanks"></div><p class="chart-note"><span class="legend"><span><i style="background:var(--purple)"></i>Private banks</span><span><i style="background:var(--teal)"></i>Public banks</span></span>Greater movement does not necessarily mean a negative return.</p></section>
</div>
<div class="grid">
<section class="panel"><div class="panel-head"><div><h2>Volatility and observed event movement</h2><p class="sub">One dot per bank–event record with a converged GARCH forecast.</p></div><div class="legend"><span><i style="background:var(--purple)"></i>Private</span><span><i style="background:var(--teal)"></i>Public</span></div></div><div class="chart" id="chartRisk"></div><p class="chart-note" id="riskNote"></p></section>
<aside class="panel explain"><div class="eyebrow">Read the evidence carefully</div><h2>What this view measures</h2><div class="mini-metric"><span>Event window</span><strong id="windowDescription">—</strong></div><div class="mini-metric"><span>Converged GARCH forecasts</span><strong id="forecastCount">—</strong></div><div class="mini-metric"><span>Forecast target</span><strong>Announcement trading day</strong></div><h3>CAR is a benchmark-relative movement</h3><p>Cumulative abnormal return adds daily bank returns after subtracting the market-model expected return. It is not the stock’s raw return or a trading profit.</p><h3>Different horizons, different questions</h3><p>GARCH estimates one-day conditional volatility using earlier observations. Absolute CAR describes the realised event-window movement. Their association does not establish forecasting skill.</p><h3>Volatility categories are relative</h3><p>Where supplied, Low/Medium/High/Very High refer to training-period volatility thresholds. They are not loss probabilities, credit ratings, or investment recommendations.</p><span class="method-tag">Bank observations share the same policy announcement.</span></aside>
</div>
<section class="panel table-panel" id="announcements"><div class="panel-head table-head"><div><h2>Announcement explorer</h2><p class="sub" id="tableSubtitle">Actual announcement dates, with the currently selected banks and window.</p></div><button type="button" class="quiet" id="download">Download selected records ↓</button></div><div class="table-wrap"><table><caption class="sr-only">Selected RBI policy announcements and bank-averaged event results</caption><thead><tr><th scope="col">Announcement</th><th scope="col">Decision</th><th scope="col" class="num">Rate change</th><th scope="col" class="num">Banks</th><th scope="col" class="num">Mean CAR</th><th scope="col" class="num">Mean |CAR|</th><th scope="col" class="num">Mean 1-day GARCH</th></tr></thead><tbody id="eventRows"></tbody></table></div></section>
<details class="panel provenance" id="provenance"><summary>Data snapshot, validation &amp; reproducibility</summary><div class="provenance-body"><p id="provenanceSummary"></p><div class="checks" id="checks"></div><p>The checks below establish internal data consistency. Source verification, retrieval timestamps, price conventions, hashes, and runtime details are recorded in the run manifest when supplied. The dashboard does not add independent evidence to those records.</p><pre id="manifest"></pre></div></details>
</main><footer class="footer"><span>RBI Banking Market Intelligence · Research portfolio</span><span>Self-contained offline dashboard · Values are descriptive, sample-specific results</span></footer>
</div>
<script type="application/json" id="research-data">__PAYLOAD__</script>
<script>
'use strict';
const DATA=JSON.parse(document.getElementById('research-data').textContent);
const $=id=>document.getElementById(id);
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const finite=x=>typeof x==='number'&&Number.isFinite(x);
const mean=items=>items.length?items.reduce((a,b)=>a+b,0)/items.length:null;
const pct=(value,d=2)=>finite(value)?`${(100*value).toFixed(d)}%`:'—';
const signedPct=value=>finite(value)?`${value>0?'+':''}${pct(value)}`:'—';
const unique=items=>[...new Set(items)];
const fmtDate=value=>new Date(value+'T00:00:00Z').toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric',timeZone:'UTC'});
const shortDate=value=>new Date(value+'T00:00:00Z').toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'2-digit',timeZone:'UTC'});
const windowLabels={'[-1,+1]':'3 days · [−1, +1]','[-2,+2]':'5 days · [−2, +2]','[-5,+5]':'11 days · [−5, +5]','[0,+1]':'2 days · [0, +1]'};
const benchmarkLabels={'^NSEI':'Nifty 50','^NSEBANK':'Nifty Bank'};
const eventMap=new Map(DATA.events.map(e=>[e.event_id,e]));
const forecastMap=new Map(DATA.forecasts.map(f=>[`${f.event_id}|${f.bank_symbol}`,f]));
const group=(rows,key)=>{const m=new Map();for(const row of rows){const k=row[key];if(!m.has(k))m.set(k,[]);m.get(k).push(row);}return m;};
const options=(id,values,label)=>{for(const value of values){const el=document.createElement('option');el.value=value;el.textContent=label(value);$(id).append(el);}};
const benchmarks=unique(DATA.results.map(r=>r.benchmark));
const windows=unique(DATA.results.map(r=>r.window)).sort((a,b)=>Object.keys(windowLabels).indexOf(a)-Object.keys(windowLabels).indexOf(b));
options('benchmark',benchmarks,b=>benchmarkLabels[b]||b);
options('window',windows,w=>windowLabels[w]||w);
options('decision',['Cut','Hold','Hike'].filter(d=>DATA.events.some(e=>e.decision===d)),d=>d);
options('bankType',unique(DATA.banks.map(b=>b.bank_type)).sort(),b=>`${b} banks`);
options('event',DATA.events.map(e=>e.event_id),id=>`${fmtDate(eventMap.get(id).event_date)} · ${eventMap.get(id).decision}`);
const defaultBenchmark=benchmarks.includes('^NSEI')?'^NSEI':benchmarks[0];
const defaultWindow=windows.includes('[-1,+1]')?'[-1,+1]':windows[0];
$('benchmark').value=defaultBenchmark;$('window').value=defaultWindow;
$('coverage').textContent=`${DATA.events[0].event_date.slice(0,4)}–${DATA.events.at(-1).event_date.slice(0,4)}`;
$('benchmarkCount').textContent=benchmarks.map(b=>benchmarkLabels[b]||b).join(' / ');
$('provenanceSummary').textContent=`Embedded snapshot: ${DATA.validation.event_count} policy announcements, ${DATA.validation.bank_count} banks, ${DATA.validation.result_rows} result rows across benchmarks/windows, and ${DATA.validation.forecast_rows} event-date forecast records. Filtered policy counts use distinct event IDs.`;
for(const check of DATA.validation.checks){const span=document.createElement('span');span.className='check';span.textContent=check;$('checks').append(span);}
$('manifest').textContent=JSON.stringify(Object.keys(DATA.manifest).length?DATA.manifest:{status:'No external run manifest supplied',internal_validation:DATA.validation},null,2);
let selected=[];

function eventChart(rows){
 const values=[...group(rows,'event_id')].map(([id,rs])=>({...eventMap.get(id),car:mean(rs.map(r=>r.car)),n:rs.length})).sort((a,b)=>a.event_date.localeCompare(b.event_date));
 if(!values.length)return '<div class="empty">No announcements match these filters.</div>';
 const w=940,h=340,l=58,r=20,t=23,b=92,plotH=h-t-b,max=Math.max(.001,...values.map(d=>Math.abs(d.car)))*1.18;
 const y=v=>t+(max-v)/(2*max)*plotH,step=(w-l-r)/values.length,bw=Math.min(33,step*.57);
 let svg=`<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Mean cumulative abnormal return by announcement, in percent">`;
 for(let k=-2;k<=2;k++){const v=max*k/2;svg+=`<line class="${k===0?'baseline':'gridline'}" x1="${l}" y1="${y(v)}" x2="${w-r}" y2="${y(v)}"/><text x="${l-10}" y="${y(v)+3}" text-anchor="end">${pct(v,1)}</text>`;}
 const labelEvery=values.length>36?3:values.length>20?2:1;
 values.forEach((d,i)=>{const x=l+step*(i+.5),top=y(Math.max(d.car,0)),height=Math.max(1,Math.abs(y(d.car)-y(0))),color=d.car>=0?'#087f75':'#c8664f',label=(i%labelEvery===0||i===values.length-1)?`<text transform="translate(${x+2},${h-b+17}) rotate(-42)" text-anchor="end">${esc(shortDate(d.event_date))}</text>`:'';svg+=`<g data-event="${esc(d.event_id)}" tabindex="0" role="button" aria-label="Inspect ${esc(fmtDate(d.event_date))}"><title>${esc(fmtDate(d.event_date))} · ${esc(d.decision)}\nMean CAR ${signedPct(d.car)} · ${d.n} banks</title><rect class="eventbar" x="${x-bw/2}" y="${top}" width="${bw}" height="${height}" rx="3" fill="${color}"/>${label}</g>`;});
 return svg+'</svg>';
}

function bankChart(rows){
 const banks=[...group(rows,'bank_symbol')].map(([symbol,rs])=>({symbol,name:rs[0].bank_name,type:rs[0].bank_type,value:mean(rs.map(r=>Math.abs(r.car))),signed:mean(rs.map(r=>r.car)),n:rs.length})).sort((a,b)=>b.value-a.value);
 if(!banks.length)return '<div class="empty">No banks match these filters.</div>';
 const w=560,h=Math.max(230,banks.length*45+38),left=142,right=62,step=(h-35)/banks.length,max=Math.max(.001,...banks.map(d=>d.value))*1.13;
 let svg=`<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Mean absolute cumulative abnormal return by bank, in percent">`;
 banks.forEach((d,i)=>{const y=20+i*step,width=d.value/max*(w-left-right),color=d.type==='Public'?'#087f75':'#7664a3';svg+=`<g><title>${esc(d.name)}\nMean |CAR| ${pct(d.value)}\nMean signed CAR ${signedPct(d.signed)}\n${d.n} announcements</title><text x="${left-10}" y="${y+17}" text-anchor="end">${esc(d.name)}</text><rect x="${left}" y="${y+2}" width="${w-left-right}" height="23" fill="#f1f4f1" rx="4"/><rect x="${left}" y="${y+2}" width="${Math.max(1,width)}" height="23" fill="${color}" rx="4"/><text x="${left+width+8}" y="${y+18}">${pct(d.value)}</text></g>`;});
 return svg+'</svg>';
}

function riskChart(rows){
 const points=rows.map(r=>({r,f:forecastMap.get(`${r.event_id}|${r.bank_symbol}`)})).filter(d=>d.f&&d.f.converged&&finite(d.f.garch_volatility));
 $('forecastCount').textContent=`${points.length} / ${rows.length}`;
 $('riskNote').textContent=`${points.length} of ${rows.length} selected bank–event records have converged forecasts targeting the announcement date. Both axes are percentages; their horizons differ. Hover a point for its origin, target, and relative volatility category.`;
 if(!points.length)return '<div class="empty">No converged forecasts are available for this selection.</div>';
 const w=940,h=342,l=64,r=25,t=21,b=58,maxX=Math.max(.001,...points.map(d=>d.f.garch_volatility))*1.15,maxY=Math.max(.001,...points.map(d=>Math.abs(d.r.car)))*1.16;
 const x=v=>l+v/maxX*(w-l-r),y=v=>h-b-v/maxY*(h-t-b);
 let svg=`<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Event-day GARCH volatility against absolute event-window CAR">`;
 for(let i=0;i<=4;i++){let vx=maxX*i/4,vy=maxY*i/4;svg+=`<line class="gridline" x1="${l}" y1="${y(vy)}" x2="${w-r}" y2="${y(vy)}"/><text x="${l-10}" y="${y(vy)+3}" text-anchor="end">${pct(vy,1)}</text><text x="${x(vx)}" y="${h-b+20}" text-anchor="middle">${pct(vx,1)}</text>`;}
 svg+=`<text class="axis-label" x="${(w+l-r)/2}" y="${h-10}" text-anchor="middle">GARCH forecast volatility · one trading day</text><text class="axis-label" transform="translate(15,${(h-b+t)/2}) rotate(-90)" text-anchor="middle">Absolute CAR · selected event window</text>`;
 for(const {r:row,f} of points){svg+=`<circle class="point" cx="${x(f.garch_volatility)}" cy="${y(Math.abs(row.car))}" r="4.8" fill="${row.bank_type==='Public'?'#087f75':'#7664a3'}" opacity=".72"><title>${esc(row.bank_name)} · ${esc(fmtDate(row.event_date))}\nCAR ${signedPct(row.car)}\nOne-day GARCH volatility ${pct(f.garch_volatility)}\nOrigin ${esc(f.forecast_origin_date)} → target ${esc(f.forecast_target_date)}\nRelative category: ${esc(f.risk_level||'Unclassified')}</title></circle>`;}
 return svg+'</svg>';
}

function render(){
 selected=DATA.results.filter(r=>r.benchmark===$('benchmark').value&&r.window===$('window').value&&($('decision').value==='all'||r.decision===$('decision').value)&&($('bankType').value==='all'||r.bank_type===$('bankType').value)&&($('event').value==='all'||r.event_id===$('event').value));
 const ids=unique(selected.map(r=>r.event_id)),banks=unique(selected.map(r=>r.bank_symbol)),announcements=ids.map(id=>eventMap.get(id));
 const avg=mean(selected.map(r=>r.car)),avgAbs=mean(selected.map(r=>Math.abs(r.car)));
 $('kpiEvents').textContent=ids.length;$('kpiBanks').textContent=banks.length;$('kpiCar').textContent=signedPct(avg);$('kpiAbsCar').textContent=pct(avgAbs);$('recordCount').textContent=`${selected.length} bank–event records`;
 $('selectionNote').textContent=`${ids.length} distinct announcements · ${selected.length} bank–event records · ${benchmarkLabels[$('benchmark').value]||$('benchmark').value} benchmark. Bank records from one announcement are not independent policy events.`;
 const counts=['Cut','Hold','Hike'].map(d=>({decision:d,n:announcements.filter(e=>e.decision===d).length}));
 const countText=counts.filter(d=>d.n).map(d=>`${d.n} ${d.decision.toLowerCase()}${d.n===1?'':'s'}`).join(', ');
 const few=counts.filter(d=>d.n>0&&d.n<5).map(d=>d.decision.toLowerCase()).join('/');
 const cutYears=unique(announcements.filter(e=>e.decision==='Cut').map(e=>e.event_date.slice(0,4)));
 let warning=ids.length?`Selected sample: ${countText}. `:'No records match the current filters. ';
 warning+=few?`The ${few} group${few.includes('/')?'s have':' has'} fewer than five independent announcements; interpret group comparisons cautiously. `:'Group averages describe this sample and do not establish causality. ';
 if(cutYears.length===1)warning+=`All selected cuts occurred in ${cutYears[0]}, so decision and period effects cannot be cleanly separated. `;
 if($('window').value==='[0,+1]')warning+='The [0,+1] return interval is a separate post-announcement research target; it is not the primary event-study window.';
 $('sampleWarning').textContent=warning;$('windowDescription').textContent=windowLabels[$('window').value]||$('window').value;
 $('chartEvents').innerHTML=eventChart(selected);$('chartBanks').innerHTML=bankChart(selected);$('chartRisk').innerHTML=riskChart(selected);
 const groups=[...group(selected,'event_id')].sort((a,b)=>eventMap.get(a[0]).event_date.localeCompare(eventMap.get(b[0]).event_date));
 $('eventRows').innerHTML=groups.length?groups.map(([id,rs])=>{const e=eventMap.get(id),car=mean(rs.map(r=>r.car)),abs=mean(rs.map(r=>Math.abs(r.car))),fs=rs.map(r=>forecastMap.get(`${r.event_id}|${r.bank_symbol}`)).filter(f=>f&&f.converged&&finite(f.garch_volatility));const source=typeof e.source_url==='string'&&e.source_url.startsWith('https://')?`<a class="source-link" href="${esc(e.source_url)}" target="_blank" rel="noopener noreferrer" aria-label="Source for ${esc(fmtDate(e.event_date))}">source ↗</a>`:'';return `<tr data-event-id="${esc(id)}"><td>${esc(fmtDate(e.event_date))}${source}</td><td><span class="pill ${e.decision.toLowerCase()}">${esc(e.decision)}</span></td><td class="num">${finite(e.rate_change_bps)?`${e.rate_change_bps>0?'+':''}${e.rate_change_bps} bps`:'—'}</td><td class="num">${unique(rs.map(r=>r.bank_symbol)).length}</td><td class="num ${car>=0?'positive':'negative'}">${signedPct(car)}</td><td class="num">${pct(abs)}</td><td class="num">${pct(mean(fs.map(f=>f.garch_volatility)))}</td></tr>`;}).join(''):'<tr><td colspan="7">No announcements match these filters. Use Reset filters to return to the full sample.</td></tr>';
 $('tableSubtitle').textContent=`${ids.length} announcement${ids.length===1?'':'s'} · bank averages for ${windowLabels[$('window').value]||$('window').value}. Forecast averages exclude unavailable fits.`;
}
for(const id of ['benchmark','window','decision','bankType','event'])$(id).addEventListener('change',render);
$('reset').addEventListener('click',()=>{$('benchmark').value=defaultBenchmark;$('window').value=defaultWindow;for(const id of ['decision','bankType','event'])$(id).value='all';render();});
function selectChartEvent(event){const element=event.target.closest('[data-event]');if(element){$('event').value=element.dataset.event;render();}}
$('chartEvents').addEventListener('click',selectChartEvent);
$('chartEvents').addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();selectChartEvent(event);}});
$('download').addEventListener('click',()=>{const columns=['event_id','event_date','decision','bank_symbol','bank_name','bank_type','benchmark','window','car','absolute_car'];const quote=x=>'"'+String(x??'').replace(/"/g,'""')+'"';const csv=[columns.join(','),...selected.map(r=>columns.map(c=>quote(c==='absolute_car'?Math.abs(r.car):r[c])).join(','))].join('\r\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='rbi_selected_event_results.csv';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),500);});
render();
</script>
</body>
</html>
'''
