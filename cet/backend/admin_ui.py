from __future__ import annotations

import json
from html import escape


CSS = r'''
:root{--bg:#FFFBF4;--panel:#FFFBF4;--ink:#11120D;--muted:#11120D;--line:#D8CFBC;--red:#11120D;--blue:#11120D;--green:#11120D;--amber:#D8CFBC;--purple:#11120D;--shadow:0 8px 28px rgba(17,18,13,.06);--sidebar:250px}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}a{color:inherit;text-decoration:none}button,input,select,textarea{font:inherit}button{cursor:pointer;border:0}.side{position:fixed;z-index:20;inset:0 auto 0 0;width:var(--sidebar);background:#FFFBF4;border-right:1px solid var(--line);padding:18px 14px}.brand{display:flex;gap:12px;align-items:center;padding:4px 10px 22px}.mark{width:30px;color:var(--red);font-size:31px;font-weight:900}.brand-tortoise{width:34px;height:auto;display:block;overflow:visible}.brand b{display:block;font-size:18px}.brand span{font-size:12px;color:var(--muted)}.nav{display:grid;gap:5px}.nav a{padding:11px 13px;border-radius:9px;color:#11120D;font-size:14px;transition:background .2s,transform .2s,color .2s}.nav a:hover{background:#D8CFBC;color:var(--red);transform:translateX(2px)}.nav a.active{background:#D8CFBC;color:var(--red);font-weight:700}.sidefoot{position:absolute;left:26px;bottom:22px;color:var(--muted);font-size:11px;line-height:1.7}.online{color:#11120D}.main{margin-left:var(--sidebar);min-height:100vh}.top{position:sticky;top:0;z-index:10;height:64px;background:rgba(255,255,255,.94);backdrop-filter:blur(12px);border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;padding:0 26px}.search{width:min(530px,52vw);height:36px;background:#D8CFBC;border:1px solid #D8CFBC;border-radius:9px;display:flex;align-items:center;gap:10px;padding:0 13px;color:var(--muted);font-size:13px}.user{display:flex;align-items:center;gap:12px;font-size:13px}.avatar{width:30px;height:30px;border-radius:50%;background:#11120D;color:#FFFBF4;display:grid;place-items:center;font-size:11px}.content{padding:27px 26px 40px;max-width:1550px}.title{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:23px}.title h1{margin:0;font-size:31px;letter-spacing:-1px}.title p{margin:5px 0;color:var(--muted);font-size:14px}.live{font-size:12px;color:#11120D;display:flex;align-items:center;gap:7px}.dot{width:7px;height:7px;border-radius:50%;background:#11120D;box-shadow:0 0 0 0 rgba(16,185,129,.5);animation:pulse 1.8s infinite}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:20px}.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;box-shadow:var(--shadow);transition:transform .2s,box-shadow .2s,border-color .2s}.card:hover{transform:translateY(-1px);box-shadow:0 12px 32px rgba(20,33,61,.08)}.kpi{padding:18px 19px;min-height:125px}.khead{display:flex;align-items:center;gap:12px;color:#11120D;font-size:13px}.ki{width:42px;height:42px;border-radius:50%;display:grid;place-items:center;font-size:19px}.sky{background:#D8CFBC;color:#11120D}.rose{background:#D8CFBC;color:#e11d2e}.mint{background:#D8CFBC;color:#0a9c70}.lav{background:#D8CFBC;color:#11120D}.num{font-size:28px;font-weight:800;margin:6px 0 0 55px;transition:color .25s}.trend{font-size:12px;margin-left:55px}.up{color:#11120D}.warn{color:#11120D}.layout{display:grid;grid-template-columns:minmax(0,2.2fr) minmax(300px,.8fr);gap:14px}.panel{padding:18px}.panel h2{font-size:15px;margin:0}.toolbar{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:14px}.muted{color:var(--muted)}.small{font-size:12px}.pipeline{display:flex;gap:3px;overflow:auto;padding:4px 0}.stage{min-width:85px;flex:1;text-align:center;position:relative}.stage:not(:last-child):after{content:'→';position:absolute;right:-4px;top:10px;color:#D8CFBC}.si{width:42px;height:42px;margin:auto;border-radius:50%;background:#D8CFBC;color:#11120D;display:grid;place-items:center;transition:transform .25s,box-shadow .25s}.stage.active .si{animation:floatPulse 1.5s infinite;box-shadow:0 0 0 5px rgba(37,99,235,.08)}.stage.done .si{background:#D8CFBC;color:#0a9c70}.stage.warn .si{background:#FFFBF44dc;color:#11120D}.stage.review .si{background:#D8CFBC;color:#e11d2e}.stage.publish .si{background:#D8CFBC;color:#0a9c70}.stage b{display:block;font-size:10px;margin-top:8px;color:#11120D;line-height:1.25}.stage small{font-size:10px;color:var(--muted)}.recent{margin-top:14px}.tablewrap{overflow:auto}.table{width:100%;border-collapse:collapse;font-size:12px}.table th{background:#FFFBF4;color:#11120D;text-align:left;padding:10px 9px;position:sticky;top:0}.table td{padding:11px 9px;border-bottom:1px solid var(--line);color:#11120D}.table tbody tr{transition:background .15s}.table tbody tr:hover{background:#FFFBF4}.status{display:inline-flex;align-items:center;gap:5px;padding:4px 9px;border-radius:999px;font-size:10px;font-weight:800;white-space:nowrap}.status:before{content:'';width:6px;height:6px;border-radius:50%;background:currentColor}.status.loading:before{animation:statusSpin .8s linear infinite;box-shadow:0 0 0 2px currentColor}.pdfspin{display:inline-block;width:11px;height:11px;margin-right:7px;border:2px solid #D8CFBC;border-top-color:#11120D;border-radius:50%;vertical-align:-1px;animation:pdfSpin .75s linear infinite}.processbtn{width:34px;height:34px;padding:0;border:1px solid #D8CFBC;background:#FFFBF4;color:#11120D;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;font-size:15px}.processbtn:hover{background:#D8CFBC}.processbtn.stop{border-color:#f1c8cd;background:#FFFBF47f8;color:#11120D}.processbtn.retry{border-color:#bfe5d5;background:#FFFBF4;color:#11120D}.activityspin{display:inline-block;width:15px;height:15px;border:2px solid #D8CFBC;border-top-color:#11120D;border-right-color:#11120D;border-radius:50%;animation:pdfSpin .8s linear infinite;vertical-align:-3px}.red{background:#D8CFBC;color:#11120D}.green{background:#e4f8ef;color:#11120D}.blue{background:#D8CFBC;color:#11120D}.purple{background:#D8CFBC;color:#11120D}.amber{background:#FFFBF44dc;color:#11120D}.gray{background:#D8CFBC;color:#11120D}.sidepanel{display:grid;gap:14px}.trendbox{height:220px;display:flex;flex-direction:column}.bars{flex:1;display:flex;align-items:flex-end;gap:9px;padding:15px 8px 4px;border-bottom:1px solid var(--line)}.barcol{flex:1;height:100%;display:flex;align-items:flex-end;gap:4px}.bar{width:50%;border-radius:5px 5px 0 0;background:#D8CFBC;transition:height .7s cubic-bezier(.2,.7,.2,1)}.bar.g{background:#11120D}.health{display:grid}.hr{display:grid;grid-template-columns:32px 1fr auto;align-items:center;gap:9px;padding:11px 0;border-bottom:1px solid var(--line);font-size:12px}.hr:last-child{border-bottom:0}.hi{width:30px;height:30px;border-radius:8px;background:#D8CFBC;display:grid;place-items:center}.healthy{color:#11120D}.danger{color:#11120D}.warning{color:#11120D}.btn{display:inline-flex;align-items:center;justify-content:center;gap:7px;border-radius:8px;padding:9px 13px;font-size:12px;font-weight:700;transition:transform .15s,box-shadow .15s,opacity .15s}.btn:hover{transform:translateY(-1px)}.btn:disabled{opacity:.5;cursor:not-allowed;transform:none}.primary{background:var(--red);color:#FFFBF4;box-shadow:0 4px 12px rgba(225,29,46,.18)}.secondary{background:#D8CFBC;color:#11120D}.success{background:#e4f8ef;color:#11120D}.dangerbtn{background:#D8CFBC;color:#11120D}.ghost{background:transparent;color:#11120D;border:1px solid var(--line)}.filters{display:flex;gap:9px;flex-wrap:wrap}.rowactions{display:inline-flex;align-items:center;gap:4px;white-space:nowrap}.iconbtn{width:27px;height:27px;min-width:27px;padding:0;display:inline-flex;align-items:center;justify-content:center;border:1px solid #D8CFBC;border-radius:6px;background:#FFFBF4;color:#11120D;font-size:13px;font-weight:700;line-height:1}.iconbtn:hover{background:#D8CFBC}.iconbtn:disabled{opacity:.4;cursor:not-allowed}.status-detail{margin-top:5px;white-space:normal;line-height:1.35}.upload-layout{grid-template-columns:minmax(0,1fr)}.runtime-metrics{grid-template-columns:repeat(3,minmax(0,1fr))}.extraction-mini{min-width:0}.extract-live{display:flex;align-items:center;gap:7px;margin-top:5px;min-height:17px}.extract-progress{font-size:17px!important;white-space:nowrap}.extract-file{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:2px}.commit-progress{padding:8px 2px}.commit-progress-head{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.commit-progress-head strong{margin-left:auto;font-size:24px}.commit-track{height:12px;border-radius:999px;overflow:hidden;background:#D8CFBC;margin:18px 0 10px}.commit-bar{height:100%;width:0;background:#11120D;transition:width .25s ease}.commit-progress-stats{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;font-size:12px;font-weight:700}.commit-progress .muted{margin-top:12px;line-height:1.5}.import-queue th:last-child,.import-queue td:last-child{width:1%;white-space:nowrap}.openbtn{min-width:58px}.trashbtn{width:34px;height:34px;display:inline-flex;align-items:center;justify-content:center;border:1px solid #D8CFBC;background:#FFFBF47f8;color:#11120D;border-radius:8px;font-size:15px}.trashbtn:hover{background:#D8CFBC}.trashbtn:disabled{opacity:.35;cursor:not-allowed;background:#FFFBF4;border-color:var(--line);color:#11120D}.input,.select{height:37px;border:1px solid var(--line);background:#FFFBF4;border-radius:8px;padding:0 10px;color:#11120D;outline:none}.input:focus,.select:focus{border-color:#D8CFBC;box-shadow:0 0 0 3px rgba(37,99,235,.08)}.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.metric{padding:16px}.metric .label{font-size:11px;color:var(--muted)}.metric .value{font-size:25px;font-weight:800;margin-top:4px}.pagegrid{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:14px}.notice{padding:12px 14px;border-radius:9px;background:#FFFBF4;border:1px solid var(--line);font-size:12px;color:#11120D}.issue{padding:12px 14px;border-left:4px solid var(--amber);background:#FFFBF4af0;border-radius:8px;margin-bottom:8px;font-size:12px}.issue.good{border-left-color:var(--green);background:#FFFBF4}.skeleton{position:relative;overflow:hidden;background:#D8CFBC;border-radius:6px;color:transparent!important}.skeleton:after{content:'';position:absolute;inset:0;transform:translateX(-100%);background:linear-gradient(90deg,transparent,rgba(255,255,255,.75),transparent);animation:shimmer 1.25s infinite}.empty{text-align:center;padding:42px 18px;color:var(--muted);font-size:13px}.modalback{position:fixed;inset:0;z-index:50;background:rgba(10,20,35,.42);backdrop-filter:blur(3px);display:none;align-items:center;justify-content:center;padding:18px}.modalback.show{display:flex;animation:fadeIn .18s ease}.modal{width:min(760px,100%);max-height:90vh;overflow:auto;background:#FFFBF4;border-radius:14px;box-shadow:0 25px 80px rgba(0,0,0,.2);animation:modalIn .2s ease}.modalhead{padding:18px 20px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center}.modalbody{padding:20px}.modalfoot{padding:15px 20px;border-top:1px solid var(--line);display:flex;justify-content:flex-end;gap:8px}.close{background:#D8CFBC;border-radius:50%;width:32px;height:32px;color:#11120D}.toastbox{position:fixed;right:18px;bottom:18px;z-index:100;display:grid;gap:8px}.toast{background:#11120D;color:#FFFBF4;border-radius:9px;padding:11px 14px;font-size:12px;box-shadow:0 10px 30px rgba(0,0,0,.18);animation:toastIn .25s ease}.toast.ok{background:#11120D}.toast.err{background:#11120D}.timeline{display:grid;gap:0}.event{display:grid;grid-template-columns:20px 1fr;gap:10px;position:relative;padding:0 0 17px}.event:before{content:'';position:absolute;left:8px;top:18px;bottom:0;width:2px;background:#D8CFBC}.event:last-child:before{display:none}.eventdot{width:16px;height:16px;border-radius:50%;background:#D8CFBC;border:4px solid #FFFBF4;box-shadow:0 0 0 1px #D8CFBC;z-index:1}.event.active .eventdot{background:var(--blue);box-shadow:0 0 0 5px rgba(37,99,235,.1);animation:pulse 1.6s infinite}.event h4{margin:0;font-size:12px}.event p{margin:3px 0 0;font-size:11px;color:var(--muted)}pre.json{background:#0f172a;color:#d7e1ef;padding:13px;border-radius:9px;overflow:auto;font-size:11px;max-height:300px}
.admin-locked .main{display:none}.admin-tab-lock{position:fixed;inset:0;z-index:9999;display:none;align-items:center;justify-content:center;background:#FFFBF4;padding:24px}.admin-tab-lock.show{display:flex}.admin-tab-lock-card{width:min(440px,100%);background:#FFFBF4;border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow);padding:28px;text-align:center}.admin-tab-lock-card h2{margin:0 0 8px;font-size:20px}.admin-tab-lock-card p{margin:0 0 18px;color:var(--muted);font-size:13px;line-height:1.55}.admin-tab-lock-card button{background:var(--ink);color:#FFFBF4;border-radius:8px;padding:10px 16px;font-weight:700}.admin-tab-lock-card small{display:block;margin-top:12px;color:var(--muted)}@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(16,185,129,.45)}70%{box-shadow:0 0 0 8px rgba(16,185,129,0)}100%{box-shadow:0 0 0 0 rgba(16,185,129,0)}}@keyframes statusSpin{0%,100%{transform:scale(.75);opacity:.55}50%{transform:scale(1.15);opacity:1}}@keyframes pdfSpin{to{transform:rotate(360deg)}}@keyframes floatPulse{50%{transform:translateY(-3px)}}@keyframes shimmer{100%{transform:translateX(100%)}}@keyframes fadeIn{from{opacity:0}to{opacity:1}}@keyframes modalIn{from{opacity:0;transform:translateY(8px) scale(.99)}to{opacity:1;transform:none}}@keyframes toastIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
@media(max-width:1050px){.cards,.grid4{grid-template-columns:repeat(2,1fr)}.layout,.pagegrid{grid-template-columns:1fr}}@media(max-width:720px){.side{display:none}.main{margin-left:0}.content{padding:20px 14px}.top{padding:0 14px}.search{width:55%}.title h1{font-size:25px}.cards,.grid4{grid-template-columns:1fr}.pipeline{min-width:800px}.table{min-width:760px}.pagegrid{grid-template-columns:1fr}.top .user b{display:none}}

/* Final CETFind palette override: every admin surface uses only the three approved colors. */
:root{--bg:#FFFBF4;--panel:#FFFBF4;--ink:#11120D;--muted:#11120D;--line:#D8CFBC;--red:#11120D;--blue:#11120D;--green:#11120D;--amber:#D8CFBC;--purple:#11120D}
body,.main{background:#FFFBF4;color:#11120D}.side,.top,.card,.panel,.modal,.admin-tab-lock,.admin-tab-lock-card{background:#FFFBF4;border-color:#D8CFBC}.top{box-shadow:0 1px 0 #D8CFBC}.search{background:#FFFBF4;border-color:#D8CFBC;color:#11120D}.nav a{color:#11120D}.nav a:hover,.nav a.active{background:#D8CFBC;color:#11120D}.sidefoot,.muted,.title p,.stage small,.metric .label,.empty,.event p{color:#11120D}.online,.live,.healthy,.danger,.warning{color:#11120D}.dot{background:#11120D}.ki,.si,.hi,.secondary,.dangerbtn,.gray,.blue,.purple,.red,.rose,.mint,.sky,.lav,.green,.success,.amber{background:#D8CFBC!important;color:#11120D!important}.primary,.toast,.toast.ok,.toast.err{background:#11120D!important;color:#FFFBF4!important}.btn.ghost,.ghost{background:#FFFBF4;color:#11120D;border-color:#D8CFBC}.input,.select{background:#FFFBF4;color:#11120D;border-color:#D8CFBC}.input:focus,.select:focus{border-color:#11120D;box-shadow:0 0 0 3px rgba(216,207,188,.55)}.table th{background:#D8CFBC;color:#11120D}.table td{color:#11120D;border-color:#D8CFBC}.table tbody tr:hover{background:#D8CFBC}.processbtn,.trashbtn{background:#FFFBF4;color:#11120D;border-color:#D8CFBC}.processbtn:hover,.trashbtn:hover,.close{background:#D8CFBC;color:#11120D}.stage.active .si,.event.active .eventdot{box-shadow:0 0 0 4px rgba(216,207,188,.65)}.bar{background:#D8CFBC!important}.bar.g{background:#11120D!important}.skeleton{background:#D8CFBC}.modalback{background:rgba(17,18,13,.42)}.timeline .event:before{background:#D8CFBC}.eventdot{background:#D8CFBC;border-color:#FFFBF4;box-shadow:0 0 0 1px #D8CFBC}.admin-close-btn{border-color:#D8CFBC!important}
/* White-led refinement: beige is reserved for borders, selection and subtle highlights. */
body,.side,.top,.content,.card,.panel,.modal,.admin-tab-lock,.admin-tab-lock-card{background:#FFFBF4!important}
.search,.ki,.si,.hi,.secondary,.dangerbtn,.gray,.blue,.purple,.red,.rose,.mint,.sky,.lav,.green,.success,.amber,.table th,.table tbody tr:hover,.processbtn:hover,.trashbtn:hover,.close{background:#FFFBF4!important;color:#11120D!important}
.ki,.si,.hi,.secondary,.dangerbtn,.gray,.blue,.purple,.red,.rose,.mint,.sky,.lav,.green,.success,.amber{border:1px solid #D8CFBC}
.nav a.active{background:#D8CFBC!important;color:#11120D!important}

/* Premium monochrome admin theme */
:root{
  --bg:#F4F4F4;--panel:#FFFFFF;--ink:#111111;--muted:#5F5F5F;
  --line:#DEDEDE;--red:#050505;--blue:#111111;--green:#111111;
  --amber:#BDBDBD;--purple:#111111;--shadow:0 8px 28px rgba(0,0,0,.055)
}
html,body,.main,.content{background:#F4F4F4!important;color:#111111!important}
.side{background:#080808!important;border-right:1px solid #252525!important;color:#FFFFFF!important}
.brand b,.brand span,.brand .mark,.sidefoot,.online{color:#FFFFFF!important}
.brand span,.sidefoot{opacity:.72}
.nav a{color:#C9C9C9!important;background:transparent!important;border:1px solid transparent}
.nav a:hover{background:#1B1B1B!important;color:#FFFFFF!important;border-color:#303030;transform:translateX(2px)}
.nav a.active{background:#FFFFFF!important;color:#080808!important;border-color:#FFFFFF;font-weight:800}
.top{background:rgba(255,255,255,.96)!important;border-bottom:1px solid #DEDEDE!important;box-shadow:0 3px 16px rgba(0,0,0,.035)!important}
.search{background:#F6F6F6!important;border:1px solid #E0E0E0!important;color:#555!important}
.avatar{background:#080808!important;color:#FFFFFF!important}
.card,.panel,.modal,.admin-tab-lock-card{background:#FFFFFF!important;border:1px solid #E1E1E1!important;box-shadow:0 7px 24px rgba(0,0,0,.045)!important}
.card:hover{box-shadow:0 12px 30px rgba(0,0,0,.075)!important}
.title h1,.title p,.khead,.stage b,.stage small,.table td,.metric .label,.metric .value,.muted,.small,.event p,.sidefoot{color:inherit}
.title p,.muted,.metric .label,.stage small,.event p{color:#666666!important}
.live,.online,.healthy,.danger,.warning{color:#222222!important}
.dot{background:#111111!important;box-shadow:0 0 0 4px rgba(0,0,0,.07)!important}
.ki,.si,.hi{background:#F0F0F0!important;color:#111111!important}
.stage.done .si,.stage.warn .si,.stage.review .si,.stage.publish .si{background:#E8E8E8!important;color:#111111!important}
.stage.active .si{background:#111111!important;color:#FFFFFF!important;box-shadow:0 0 0 5px rgba(0,0,0,.09)!important}
.table th{background:#F0F0F0!important;color:#111111!important;border-bottom:1px solid #DCDCDC}
.table td{color:#222222!important;border-color:#E7E7E7!important}
.table tbody tr:hover{background:#F7F7F7!important}
.status{background:#EFEFEF!important;color:#222222!important}
.primary,.toast,.toast.ok,.toast.err{background:#080808!important;color:#FFFFFF!important;box-shadow:0 4px 12px rgba(0,0,0,.13)!important}
.secondary,.dangerbtn,.success,.red,.green,.blue,.purple,.amber,.gray{background:#EEEEEE!important;color:#111111!important}
.btn.ghost,.ghost{background:#FFFFFF!important;color:#111111!important;border:1px solid #D5D5D5!important}
.btn.success{background:#111111!important;color:#FFFFFF!important}
.btn.dangerbtn{background:#F0F0F0!important;color:#111111!important;border:1px solid #D8D8D8}
.input,.select,textarea{background:#FFFFFF!important;color:#111111!important;border:1px solid #D8D8D8!important}
.input:focus,.select:focus,textarea:focus{border-color:#111111!important;box-shadow:0 0 0 3px rgba(0,0,0,.08)!important}
.processbtn,.iconbtn,.trashbtn{background:#FFFFFF!important;color:#111111!important;border:1px solid #D8D8D8!important}
.processbtn:hover,.iconbtn:hover,.trashbtn:hover,.close{background:#111111!important;color:#FFFFFF!important;border-color:#111111!important}
.pdfspin,.activityspin{border-color:#D6D6D6!important;border-top-color:#111111!important;border-right-color:#111111!important}
.commit-track{background:#E8E8E8!important}.commit-bar{background:#111111!important}
.bars{border-color:#E1E1E1!important}.bar{background:#D2D2D2!important}.bar.g{background:#111111!important}
.notice{background:#F7F7F7!important;border-color:#DDDDDD!important;color:#222222!important}
.issue{background:#F5F5F5!important;border-left-color:#777777!important;color:#222222!important}
.skeleton{background:#EAEAEA!important}
.modalback{background:rgba(0,0,0,.58)!important;backdrop-filter:blur(5px)}
.modalhead,.modalfoot{border-color:#E5E5E5!important}
.close{background:#F0F0F0!important;color:#111111!important}
.timeline .event:before{background:#E0E0E0!important}.eventdot{background:#DADADA!important;border-color:#FFFFFF!important;box-shadow:0 0 0 1px #DADADA!important}
.event.active .eventdot{background:#111111!important;box-shadow:0 0 0 5px rgba(0,0,0,.08)!important}
.admin-tab-lock{background:#F4F4F4!important}
.admin-tab-lock-card button{background:#080808!important;color:#FFFFFF!important}
pre.json{background:#111111!important;color:#F1F1F1!important}
/* Soft pearl theme with restrained color and a subtle raised-card depth. */
:root{--bg:#F2F4F7;--panel:#FFFFFF;--ink:#263244;--muted:#697586;--line:#E0E5EC;--red:#355D91;--blue:#4777B7;--green:#32866D;--amber:#B58A45;--purple:#7768A8;--shadow:0 2px 4px rgba(32,48,70,.035),0 9px 22px rgba(32,48,70,.065),inset 0 1px 0 rgba(255,255,255,.95)}
html,body,.main,.content{background:#F2F4F7!important;color:#263244!important}
.side{background:linear-gradient(180deg,#FFFFFF 0%,#F5F7FA 100%)!important;color:#344256!important;border-right:1px solid #E0E5EC!important;box-shadow:3px 0 14px rgba(32,48,70,.035)}
.brand b,.brand span,.brand .mark,.sidefoot,.online{color:#344256!important}.brand span,.sidefoot{opacity:.8}
.nav a{color:#59677A!important;background:transparent!important;border:1px solid transparent}
.nav a:hover{background:#EAF0F8!important;color:#315C91!important;border-color:#DCE6F4;transform:translateX(2px)}
.nav a.active{background:linear-gradient(180deg,#E7EFFA,#DCE8F8)!important;color:#315C91!important;border-color:#D3E0F2!important;box-shadow:inset 0 1px 0 #FFFFFF,0 2px 5px rgba(55,92,145,.08);font-weight:800}
.top{background:rgba(255,255,255,.94)!important;border-bottom:1px solid #E0E5EC!important;box-shadow:0 3px 14px rgba(32,48,70,.04)!important}
.search{background:#F7F9FC!important;border:1px solid #E1E7EF!important;color:#697586!important}
.avatar{background:#E4ECF7!important;color:#355D91!important;border:1px solid #D6E1F0}
.card,.panel,.modal,.admin-tab-lock-card{background:linear-gradient(145deg,#FFFFFF 0%,#FCFDFE 100%)!important;border:1px solid #E0E5EC!important;box-shadow:0 2px 4px rgba(32,48,70,.035),0 9px 22px rgba(32,48,70,.065),inset 0 1px 0 rgba(255,255,255,.98)!important;transition:transform .2s ease,box-shadow .2s ease,border-color .2s ease}
.card:hover{transform:translateY(-2px);border-color:#D5DFEC!important;box-shadow:0 4px 8px rgba(32,48,70,.045),0 14px 28px rgba(32,48,70,.085),inset 0 1px 0 #FFFFFF!important}
.kpi{position:relative;overflow:hidden}.kpi:before{content:"";position:absolute;inset:0 0 auto;height:3px;background:linear-gradient(90deg,#C8D9EF,#E7EDF6);opacity:.9}
.title h1{color:#263244!important}.title p,.muted,.metric .label,.stage small,.event p{color:#697586!important}
.live,.online{color:#3F7D69!important}.dot{background:#4A9B7B!important;box-shadow:0 0 0 4px rgba(74,155,123,.12)!important}
.ki,.si,.hi{background:linear-gradient(145deg,#F4F7FB,#E8EEF6)!important;color:#47668E!important;border:1px solid #DFE7F1;box-shadow:inset 0 1px 0 #FFFFFF,0 2px 4px rgba(32,48,70,.04)}
.khead{color:#526176!important}.num,.metric .value{color:#263244!important}
.table th{background:#F2F5F9!important;color:#526176!important;border-bottom:1px solid #E0E5EC}.table td{color:#354256!important;border-color:#E8ECF1!important}.table tbody tr:hover{background:#F7F9FC!important}
.status{background:#EEF2F7!important;color:#526176!important}.status.loading{background:#EAF1FB!important;color:#426DA8!important}
.primary,.toast,.toast.ok,.toast.err{background:#355D91!important;color:#FFFFFF!important;box-shadow:0 4px 10px rgba(53,93,145,.18)!important}
.secondary,.dangerbtn,.success,.red,.green,.blue,.purple,.amber,.gray{background:#EDF2F8!important;color:#45658D!important;border:1px solid #DDE6F1!important}
.btn.ghost,.ghost{background:#FFFFFF!important;color:#53647A!important;border:1px solid #DDE4ED!important}
.btn.success{background:#E8F4EF!important;color:#2F7D65!important;border:1px solid #D3E9DF!important}
.btn.dangerbtn{background:#F7F1ED!important;color:#986747!important;border:1px solid #EDE0D6!important}
.input,.select,textarea{background:#FFFFFF!important;color:#344256!important;border:1px solid #DCE3EC!important;box-shadow:inset 0 1px 2px rgba(32,48,70,.025)}
.input:focus,.select:focus,textarea:focus{border-color:#9DB6D8!important;box-shadow:0 0 0 3px rgba(100,143,196,.13)!important}
.processbtn,.iconbtn,.trashbtn{background:linear-gradient(180deg,#FFFFFF,#F5F7FA)!important;color:#53647A!important;border:1px solid #DCE3EC!important;box-shadow:0 1px 2px rgba(32,48,70,.04),inset 0 1px 0 #FFFFFF}
.processbtn:hover,.iconbtn:hover,.trashbtn:hover,.close{background:#EAF0F8!important;color:#355D91!important}
.commit-track{background:#E8EDF4!important}.commit-bar{background:linear-gradient(90deg,#5F86BA,#355D91)!important}
.bars{border-color:#E0E5EC!important}.bar{background:#C8D8EA!important}.bar.g{background:#5F86BA!important}
.notice{background:#F7F9FC!important;border-color:#E0E6EF!important;color:#526176!important}.issue{background:#FBF8F5!important;border-left-color:#C5A27D!important;color:#655448!important}
.skeleton{background:#EDF1F6!important}.modalback{background:rgba(43,57,77,.28)!important;backdrop-filter:blur(5px)}.modalhead,.modalfoot{border-color:#E5EAF0!important}.close{background:#EEF2F7!important;color:#526176!important}
.timeline .event:before{background:#E0E7F0!important}.eventdot{background:#DCE6F2!important;border-color:#FFFFFF!important;box-shadow:0 0 0 1px #D5DFEC!important}.event.active .eventdot{background:#5F86BA!important;box-shadow:0 0 0 5px rgba(95,134,186,.13)!important}
.admin-tab-lock{background:#F2F4F7!important}.admin-tab-lock-card button{background:#355D91!important;color:#FFFFFF!important}pre.json{background:#354256!important;color:#F4F7FB!important}
.dashboard-imports{min-height:260px}.dashboard-imports .toolbar{margin-bottom:18px}.dashboard-imports .table{font-size:13px}.dashboard-imports .table th{padding:13px 11px}.dashboard-imports .table td{padding:13px 11px}
@media(max-width:720px){.side{display:none!important}.dashboard-imports .toolbar{align-items:flex-start}}

/* Refinement: warm neutral accents, downward-only card depth, consistent badges. */
:root{--bg:#F3F1EC;--panel:#FFFEFB;--ink:#383832;--muted:#77766F;--line:#E4E0D7;--red:#8C8272;--blue:#8C8272;--green:#7C8875;--amber:#9A8B6E;--purple:#8C8272;--shadow:0 5px 8px rgba(54,49,39,.035),0 13px 24px rgba(54,49,39,.075)}
html,body,.main,.content{background:#F3F1EC!important;color:#383832!important}
.side{background:linear-gradient(180deg,#FFFEFB,#F6F4EF)!important;color:#4A4942!important;border-right:1px solid #E4E0D7!important;box-shadow:3px 0 12px rgba(54,49,39,.035)!important}
.nav a{color:#68675F!important}.nav a:hover,.nav a.active{background:#EAE5DA!important;color:#514D42!important;border-color:#E1DACC!important;box-shadow:0 3px 7px rgba(54,49,39,.06)!important}
.top{box-shadow:0 4px 10px rgba(54,49,39,.045)!important;border-color:#E4E0D7!important}
.card,.panel,.modal,.admin-tab-lock-card{background:linear-gradient(150deg,#FFFEFC 0%,#FBFAF6 100%)!important;border:1px solid #E4E0D7!important;box-shadow:0 4px 7px rgba(54,49,39,.035),0 12px 24px rgba(54,49,39,.075)!important;transition:transform .2s ease,box-shadow .2s ease,border-color .2s ease}
.card:hover{transform:translateY(-1px);border-color:#DCD5C8!important;box-shadow:0 6px 10px rgba(54,49,39,.04),0 16px 29px rgba(54,49,39,.09)!important}
/* Remove the top-edge highlight; depth is cast below each card. */
.card,.panel,.modal,.admin-tab-lock-card,.ki,.si,.hi,.btn,.processbtn,.iconbtn,.trashbtn{inset:auto;}
.card,.panel,.modal,.admin-tab-lock-card{box-shadow:0 4px 7px rgba(54,49,39,.035),0 12px 24px rgba(54,49,39,.075)!important}
.kpi:before{background:linear-gradient(90deg,#D9D1C2,#ECE7DD)!important}
.avatar,.ki,.si,.hi{background:#EEEAE1!important;color:#77705F!important;border-color:#E2DCCE!important;box-shadow:0 2px 4px rgba(54,49,39,.045)!important}
.primary,.toast,.toast.ok,.toast.err{background:#777D6B!important;color:#FFFFFF!important;box-shadow:0 5px 10px rgba(79,87,68,.15)!important}
.secondary,.dangerbtn,.success,.red,.green,.blue,.purple,.amber,.gray,.rose,.mint,.sky,.lav{background:#F0EDE6!important;color:#716B5E!important;border:1px solid #E3DED3!important}
.btn.success{background:#E9EDE5!important;color:#66745D!important;border:1px solid #DCE3D5!important}
.btn.dangerbtn{background:#F3ECE6!important;color:#8C7562!important;border:1px solid #E8DCD1!important}
.status,.status.loading,.status.green,.status.red,.status.purple,.status.blue,.status.amber,.status.gray,.status.rose,.status.mint,.status.sky,.status.lav{background:#F0EDE6!important;color:#6E695E!important;border:1px solid #E4DFD5!important;box-shadow:none!important}
.status.loading{background:#F5F1E7!important;color:#8B7957!important;border-color:#EAE2D1!important}
.status.green{background:#EDF0E9!important;color:#69745F!important;border-color:#DEE5D7!important}
.status.red{background:#F3ECE6!important;color:#8C7562!important;border-color:#E8DCD1!important}
.status.purple,.status.blue,.status.amber,.status.gray{background:#F0EDE6!important;color:#6E695E!important;border-color:#E4DFD5!important}
.table th{background:#F1EEE7!important;color:#6E6B62!important}.table tbody tr:hover{background:#FAF8F3!important}
.commit-track{background:#E8E3D9!important}.commit-bar{background:linear-gradient(90deg,#A5AA98,#7C8875)!important}
.bars{border-color:#E4E0D7!important}.bar{background:#D6D0C3!important}.bar.g{background:#8E9781!important}
.processbtn,.iconbtn,.trashbtn{background:linear-gradient(180deg,#FFFEFC,#F5F2EB)!important;color:#6F6A5F!important;border:1px solid #E2DDD2!important;box-shadow:0 3px 6px rgba(54,49,39,.055)!important}
.processbtn:hover,.iconbtn:hover,.trashbtn:hover,.close{background:#EEE9DF!important;color:#625C4F!important}
.notice{background:#F7F4ED!important;border-color:#E7E0D2!important;color:#6E695E!important}.issue{background:#F8F3ED!important;border-left-color:#B9A58A!important;color:#6D5D4C!important}
.eventdot{background:#DCD7CB!important;box-shadow:0 0 0 1px #DCD7CB!important}.event.active .eventdot{background:#8E9781!important;box-shadow:0 0 0 5px rgba(142,151,129,.14)!important}
.modalback{background:rgba(49,47,40,.30)!important}
.admin-tab-lock-card button{background:#777D6B!important;color:#FFFFFF!important}


/* Statuses are plain text, not badges: remove pill shape, fill, border and status dot. */
.status{
  display:inline;
  padding:0!important;
  border:0!important;
  border-radius:0!important;
  background:transparent!important;
  box-shadow:none!important;
  font-size:11px!important;
  font-weight:600!important;
  line-height:inherit;
  white-space:nowrap;
}
.status:before{display:none!important;content:none!important}


/* Complete admin panel: bright white surfaces, restrained grey borders, soft downward shadows. */
:root{--bg:#FFFFFF;--panel:#FFFFFF;--ink:#171717;--muted:#666666;--line:#E7E7E7;--red:#171717;--blue:#171717;--green:#171717;--amber:#EEEEEE;--purple:#171717;--shadow:0 10px 26px rgba(0,0,0,.06)}
html,body,.main,.content,.side,.top,.card,.panel,.modal,.modalhead,.modalbody,.modalfoot,.admin-tab-lock,.admin-tab-lock-card,.notice,.issue,.search,.input,.select,textarea,.table th,.table td,.metric,.kpi,.toolbar,.filters,.health,.hr,.event,.runtime-metrics,.extraction-mini,.commit-progress,.pagegrid,.layout,.sidepanel,.tablewrap{background-color:#FFFFFF!important;color:#171717!important}
.side{border-right:1px solid #E7E7E7!important}
.top{border-bottom:1px solid #E7E7E7!important;box-shadow:0 3px 14px rgba(0,0,0,.035)!important}
.brand b,.brand span,.brand .mark,.sidefoot,.online{color:#171717!important;opacity:1}
.nav a{color:#333333!important;background:#FFFFFF!important;border-color:transparent!important}
.nav a:hover,.nav a.active{background:#F2F2F2!important;color:#111111!important;border-color:#E5E5E5!important}
.card,.panel,.modal,.admin-tab-lock-card{border:1px solid #E7E7E7!important;box-shadow:0 9px 24px rgba(0,0,0,.06)!important}
.card:hover{box-shadow:0 13px 28px rgba(0,0,0,.075)!important}
.title h1,.title p,.khead,.stage b,.stage small,.table td,.table th,.metric .label,.metric .value,.muted,.small,.event p,.live,.healthy,.danger,.warning{color:#171717!important}
.title p,.muted,.metric .label,.stage small,.event p,.sidefoot{color:#666666!important}
.search,.input,.select,textarea{border:1px solid #E2E2E2!important;box-shadow:none}
.input:focus,.select:focus,textarea:focus{border-color:#AFAFAF!important;box-shadow:0 0 0 3px rgba(0,0,0,.045)!important}
.table th{background:#F8F8F8!important;border-bottom:1px solid #E7E7E7!important}
.table td{border-color:#EEEEEE!important}
.table tbody tr:hover{background:#FAFAFA!important}
.ki,.si,.hi,.stage.done .si,.stage.warn .si,.stage.review .si,.stage.publish .si{background:#F5F5F5!important;color:#222222!important;border:1px solid #EAEAEA}
.stage.active .si{background:#222222!important;color:#FFFFFF!important;box-shadow:0 4px 10px rgba(0,0,0,.12)!important}
.primary,.btn.primary,.toast,.toast.ok,.toast.err{background:#171717!important;color:#FFFFFF!important;border-color:#171717!important}
.secondary,.success,.dangerbtn,.btn.ghost,.ghost,.processbtn,.iconbtn,.trashbtn,.close{background:#FFFFFF!important;color:#171717!important;border:1px solid #E0E0E0!important}
.secondary:hover,.success:hover,.dangerbtn:hover,.ghost:hover,.processbtn:hover,.iconbtn:hover,.trashbtn:hover,.close:hover{background:#F5F5F5!important}
.status{display:inline!important;padding:0!important;border:0!important;border-radius:0!important;background:transparent!important;box-shadow:none!important;color:#222222!important;font-size:11px!important;font-weight:600!important}
.status:before{display:none!important;content:none!important}
.red,.green,.blue,.purple,.amber,.gray{background:transparent!important;color:#222222!important}
.notice,.issue{border:1px solid #E8E8E8!important;border-radius:8px}
.commit-track{background:#EEEEEE!important}
.commit-bar{background:#222222!important}
.skeleton{background:#EEEEEE!important}
.modalback{background:rgba(0,0,0,.28)!important}
pre.json{background:#F7F7F7!important;color:#222222!important;border:1px solid #E7E7E7}


/* Clean enterprise light UI: white working surfaces on a soft neutral canvas. */
:root{
  --bg:#F5F7FA;--panel:#FFFFFF;--ink:#17191C;--muted:#68717D;
  --line:#E4E8ED;--red:#17191C;--blue:#17191C;--green:#17191C;
  --amber:#ECEFF2;--purple:#17191C;--shadow:0 2px 5px rgba(20,28,38,.025),0 8px 22px rgba(20,28,38,.045)
}
html,body{background:#F5F7FA!important;color:#17191C!important}
.main,.content{background:#F5F7FA!important;color:#17191C!important}
.side,.top{background:#FFFFFF!important;color:#17191C!important}
.side{border-right:1px solid #E5E9EE!important}
.top{border-bottom:1px solid #E5E9EE!important;box-shadow:0 2px 7px rgba(20,28,38,.025)!important}
.brand b,.brand .mark,.brand span,.sidefoot,.online{color:#17191C!important}
.brand span,.sidefoot{color:#78818C!important}
.nav{gap:4px!important}
.nav a{background:transparent!important;color:#515B67!important;border:1px solid transparent!important;border-radius:7px!important;padding:10px 12px!important;font-weight:500!important}
.nav a:hover{background:#F5F7F9!important;color:#17191C!important;border-color:#EEF0F3!important;transform:none!important}
.nav a.active{position:relative;background:#F1F3F5!important;color:#17191C!important;border-color:#E8EBEF!important;font-weight:650!important}
.nav a.active:before{content:"";position:absolute;left:-1px;top:7px;bottom:7px;width:3px;background:#17191C;border-radius:0 3px 3px 0}
.search{background:#F7F8FA!important;border:1px solid #E4E8ED!important;color:#68717D!important;border-radius:8px!important}
.avatar{background:#17191C!important;color:#FFFFFF!important}
.content{padding-top:30px!important}
.title{margin-bottom:25px!important}
.title h1{font-size:29px!important;letter-spacing:-.7px!important;font-weight:650!important;color:#17191C!important}
.title p{font-size:13px!important;line-height:1.55!important;color:#68717D!important}
.card,.panel,.modal,.admin-tab-lock-card{background:#FFFFFF!important;border:1px solid #E4E8ED!important;border-radius:11px!important;box-shadow:var(--shadow)!important}
.card:hover{box-shadow:0 3px 7px rgba(20,28,38,.03),0 11px 25px rgba(20,28,38,.055)!important;transform:translateY(-1px)}
.kpi{padding:19px!important}
.khead{font-size:12px!important;font-weight:550!important;color:#5E6874!important}
.num,.metric .value{font-size:27px!important;font-weight:650!important;letter-spacing:-.45px!important;color:#17191C!important}
.trend{font-size:11px!important;color:#69737F!important}
.ki,.si,.hi{background:#F2F4F6!important;color:#343B44!important;border:1px solid #E9EDF1!important;border-radius:9px!important}
.stage.active .si{background:#17191C!important;color:#FFFFFF!important;box-shadow:0 3px 8px rgba(23,25,28,.12)!important}
.stage b{font-size:10px!important;font-weight:600!important;color:#424B56!important}
.stage small{color:#78818C!important}
.tablewrap{border-radius:8px!important}
.table{font-size:12px!important}
.table th{background:#F7F8FA!important;color:#68717D!important;font-size:10px!important;font-weight:650!important;text-transform:uppercase;letter-spacing:.045em;border-bottom:1px solid #E4E8ED!important;padding:12px 11px!important}
.table td{background:#FFFFFF!important;color:#303741!important;border-bottom:1px solid #EDF0F3!important;padding:12px 11px!important}
.table tbody tr:hover td{background:#FAFBFC!important}
.toolbar h2,.panel h2{font-size:14px!important;font-weight:650!important;color:#252A31!important}
.muted,.small,.metric .label,.event p,.stage small{color:#68717D!important}
.live{color:#4E5864!important;font-weight:550!important}
.dot{background:#4C8A70!important;box-shadow:0 0 0 4px rgba(76,138,112,.10)!important}
.primary,.btn.primary{background:#17191C!important;color:#FFFFFF!important;border:1px solid #17191C!important;box-shadow:0 2px 3px rgba(20,28,38,.08)!important}
.primary:hover,.btn.primary:hover{background:#30343A!important}
.secondary,.success,.dangerbtn,.btn.ghost,.ghost,.processbtn,.iconbtn,.trashbtn,.close{background:#FFFFFF!important;color:#303741!important;border:1px solid #DCE2E8!important;box-shadow:none!important}
.secondary:hover,.success:hover,.dangerbtn:hover,.ghost:hover,.processbtn:hover,.iconbtn:hover,.trashbtn:hover,.close:hover{background:#F5F7F9!important;border-color:#CBD3DC!important}
.btn{border-radius:7px!important;font-weight:600!important}
.input,.select,textarea{background:#FFFFFF!important;color:#252A31!important;border:1px solid #DCE2E8!important;border-radius:7px!important}
.input::placeholder,textarea::placeholder{color:#89929D!important}
.input:focus,.select:focus,textarea:focus{border-color:#8A949F!important;box-shadow:0 0 0 3px rgba(85,98,112,.10)!important}
.status{display:inline!important;padding:0!important;border:0!important;border-radius:0!important;background:transparent!important;box-shadow:none!important;color:#4B5561!important;font-size:11px!important;font-weight:600!important}
.status:before{display:none!important;content:none!important}
.red,.green,.blue,.purple,.amber,.gray{background:transparent!important;color:#4B5561!important}
.notice{background:#F8FAFB!important;border:1px solid #E5EAF0!important;color:#4D5864!important;border-radius:8px!important}
.issue{background:#FBF8F3!important;border-left-color:#B6A17D!important;color:#655A49!important}
.commit-track{background:#E9EDF1!important;border-radius:5px!important}
.commit-bar{background:#303943!important}
.skeleton{background:#ECEFF3!important}
.bars{border-color:#E5E9EE!important}
.bar{background:#D9DEE5!important}
.bar.g{background:#65717E!important}
.hr,.event:before{border-color:#E8ECF0!important;background:#E8ECF0!important}
.eventdot{background:#D6DCE3!important;border-color:#FFFFFF!important;box-shadow:0 0 0 1px #D6DCE3!important}
.event.active .eventdot{background:#65717E!important;box-shadow:0 0 0 4px rgba(101,113,126,.12)!important}
.modalback{background:rgba(22,28,35,.34)!important}
.modalhead,.modalfoot{border-color:#E5E9EE!important}
pre.json{background:#F7F9FB!important;color:#303741!important;border:1px solid #E5E9EE!important}
.toast,.toast.ok,.toast.err{background:#17191C!important;color:#FFFFFF!important;box-shadow:0 8px 22px rgba(20,28,38,.16)!important}
@media(max-width:720px){.content{padding:20px 14px 32px!important}.title h1{font-size:25px!important}.card,.panel{border-radius:9px!important}}


/* Strict monochrome finish: black, white, and neutral greys only. */
:root{--bg:#FFFFFF;--panel:#FFFFFF;--ink:#111111;--muted:#666666;--line:#E5E5E5;--red:#111111;--blue:#111111;--green:#111111;--amber:#EAEAEA;--purple:#111111;--shadow:0 2px 5px rgba(0,0,0,.025),0 8px 22px rgba(0,0,0,.045)}
html,body,.main,.content{background:#F5F5F5!important;color:#111111!important}
.side,.top,.card,.panel,.modal,.modalhead,.modalbody,.modalfoot,.admin-tab-lock,.admin-tab-lock-card{background:#FFFFFF!important;color:#111111!important}
.side{border-right:1px solid #E5E5E5!important}
.top{border-bottom:1px solid #E5E5E5!important;box-shadow:0 2px 7px rgba(0,0,0,.03)!important}
.brand b,.brand .mark,.brand span,.sidefoot,.online{color:#111111!important;opacity:1}
.sidefoot,.brand span{color:#666666!important}
.nav a{background:transparent!important;color:#444444!important;border:1px solid transparent!important}
.nav a:hover,.nav a.active{background:#F0F0F0!important;color:#111111!important;border-color:#E5E5E5!important;transform:none!important}
.nav a.active{font-weight:650!important}
.nav a.active:before{content:"";position:absolute;left:-1px;top:7px;bottom:7px;width:3px;background:#111111;border-radius:0 2px 2px 0}
.search{background:#F7F7F7!important;border:1px solid #E5E5E5!important;color:#666666!important}
.avatar{background:#111111!important;color:#FFFFFF!important}
.card,.panel,.modal,.admin-tab-lock-card{border:1px solid #E5E5E5!important;border-radius:10px!important;box-shadow:var(--shadow)!important}
.card:hover{box-shadow:0 3px 7px rgba(0,0,0,.03),0 11px 25px rgba(0,0,0,.055)!important;transform:translateY(-1px)}
.title h1,.khead,.stage b,.table td,.table th,.metric .label,.metric .value,.toolbar h2,.panel h2{color:#111111!important}
.title p,.muted,.small,.metric .label,.stage small,.event p{color:#666666!important}
.live,.healthy,.danger,.warning,.online{color:#333333!important}
.dot{background:#111111!important;box-shadow:0 0 0 4px rgba(0,0,0,.08)!important}
.ki,.si,.hi,.stage.done .si,.stage.warn .si,.stage.review .si,.stage.publish .si{background:#F2F2F2!important;color:#222222!important;border:1px solid #E8E8E8!important}
.stage.active .si{background:#111111!important;color:#FFFFFF!important;box-shadow:0 3px 8px rgba(0,0,0,.12)!important}
.table th{background:#F5F5F5!important;color:#555555!important;border-bottom:1px solid #E5E5E5!important}
.table td{background:#FFFFFF!important;color:#222222!important;border-color:#EEEEEE!important}
.table tbody tr:hover td{background:#FAFAFA!important}
.primary,.btn.primary{background:#111111!important;color:#FFFFFF!important;border:1px solid #111111!important;box-shadow:0 2px 4px rgba(0,0,0,.08)!important}
.primary:hover,.btn.primary:hover{background:#292929!important}
.secondary,.success,.dangerbtn,.btn.ghost,.ghost,.processbtn,.iconbtn,.trashbtn,.close{background:#FFFFFF!important;color:#222222!important;border:1px solid #DDDDDD!important;box-shadow:none!important}
.secondary:hover,.success:hover,.dangerbtn:hover,.ghost:hover,.processbtn:hover,.iconbtn:hover,.trashbtn:hover,.close:hover{background:#F3F3F3!important;border-color:#CCCCCC!important}
.btn{border-radius:7px!important;font-weight:600!important}
.input,.select,textarea{background:#FFFFFF!important;color:#222222!important;border:1px solid #DDDDDD!important;border-radius:7px!important}
.input::placeholder,textarea::placeholder{color:#888888!important}
.input:focus,.select:focus,textarea:focus{border-color:#777777!important;box-shadow:0 0 0 3px rgba(0,0,0,.07)!important}
.status{display:inline!important;padding:0!important;border:0!important;border-radius:0!important;background:transparent!important;box-shadow:none!important;color:#333333!important;font-size:11px!important;font-weight:600!important}
.status:before{display:none!important;content:none!important}
.red,.green,.blue,.purple,.amber,.gray{background:transparent!important;color:#333333!important}
.notice{background:#F8F8F8!important;border:1px solid #E7E7E7!important;color:#444444!important;border-radius:8px!important}
.issue{background:#F7F7F7!important;border-left-color:#777777!important;color:#333333!important}
.commit-track{background:#EAEAEA!important;border-radius:5px!important}
.commit-bar{background:#222222!important}
.skeleton{background:#EEEEEE!important}
.bars{border-color:#E5E5E5!important}
.bar{background:#D5D5D5!important}
.bar.g{background:#666666!important}
.hr,.event:before{border-color:#E8E8E8!important;background:#E8E8E8!important}
.eventdot{background:#D6D6D6!important;border-color:#FFFFFF!important;box-shadow:0 0 0 1px #D6D6D6!important}
.event.active .eventdot{background:#555555!important;box-shadow:0 0 0 4px rgba(0,0,0,.09)!important}
.modalback{background:rgba(0,0,0,.34)!important}
.modalhead,.modalfoot{border-color:#E5E5E5!important}
pre.json{background:#F7F7F7!important;color:#222222!important;border:1px solid #E5E5E5!important}
.toast,.toast.ok,.toast.err{background:#111111!important;color:#FFFFFF!important;box-shadow:0 8px 22px rgba(0,0,0,.16)!important}


/* Strict black-and-white, white-led pass: no beige, grey fills, or tinted shadows. */
:root{--bg:#FFFFFF;--panel:#FFFFFF;--ink:#000000;--muted:#000000;--line:#FFFFFF;--red:#000000;--blue:#000000;--green:#000000;--amber:#000000;--purple:#000000;--shadow:none}
html,body,.main,.content,.side,.top,.card,.panel,.modal,.admin-tab-lock,.admin-tab-lock-card,
.search,.ki,.si,.hi,.sky,.rose,.mint,.lav,.secondary,.dangerbtn,.success,.red,.green,.blue,.purple,.amber,.gray,
.table th,.table tbody tr:hover,.processbtn,.iconbtn,.trashbtn,.close,.notice,.issue,.skeleton,.stage .si,
.commit-track,.bars,.bar,.eventdot,.event:before,.admin-tab-lock-card button,.input,.select,textarea{
  background:#FFFFFF!important;color:#000000!important;border-color:#FFFFFF!important;box-shadow:none!important
}
body,.main,.content,.side,.top,.card,.panel,.modal,.admin-tab-lock,.admin-tab-lock-card{background:#FFFFFF!important}
*{box-shadow:none!important;text-shadow:none!important}
html,body{color:#000000!important}
.brand b,.brand span,.brand .mark,.sidefoot,.online,.nav a,.nav a:hover,.nav a.active,
.title h1,.title p,.khead,.stage b,.stage small,.table th,.table td,.metric .label,.metric .value,
.muted,.small,.event p,.live,.healthy,.danger,.warning,.status,.status-detail,.empty,.search{color:#000000!important}
.nav a{background:#FFFFFF!important;border:0!important;border-radius:0!important}
.nav a:hover,.nav a.active{background:#FFFFFF!important;color:#000000!important;border-bottom:1px solid #000000!important}
.primary,.toast,.toast.ok,.toast.err,.commit-bar{background:#000000!important;color:#FFFFFF!important;border-color:#000000!important}
.btn.ghost,.ghost,.input,.select,textarea,.processbtn,.iconbtn,.trashbtn{background:#FFFFFF!important;color:#000000!important;border:1px solid #000000!important}
.btn.secondary,.btn.success,.btn.dangerbtn,.secondary,.success,.dangerbtn{background:#FFFFFF!important;color:#000000!important;border:1px solid #FFFFFF!important}
.table th,.table td{border-color:#FFFFFF!important}
.status{display:inline!important;padding:0!important;border:0!important;border-radius:0!important;font-weight:600!important}
.status:before{display:none!important}
.dot,.bar.g,.event.active .eventdot{background:#000000!important;box-shadow:none!important}
.bar{background:#000000!important}
.pdfspin,.activityspin{border-color:#000000!important;border-top-color:#FFFFFF!important;border-right-color:#FFFFFF!important}
.skeleton:after{background:linear-gradient(90deg,transparent,rgba(0,0,0,.06),transparent)!important}
.modalback{background:rgba(0,0,0,.35)!important}


/* Final shadow tuning: white-led UI with only subtle neutral black depth. */
:root{--shadow:0 3px 10px rgba(0,0,0,.035)}
.card,.panel,.modal,.admin-tab-lock-card{
  box-shadow:0 3px 10px rgba(0,0,0,.035)!important;
}
.card:hover{
  box-shadow:0 5px 14px rgba(0,0,0,.055)!important;
}
.top{
  box-shadow:0 2px 7px rgba(0,0,0,.025)!important;
}


/* Restore the original blue admin theme; retain current layout and processing UI */
:root{
  --bg:#f6f8fb!important;--panel:#ffffff!important;--ink:#14213d!important;
  --muted:#6b7c93!important;--line:#e5eaf0!important;--red:#e11d2e!important;
  --blue:#2563eb!important;--green:#10b981!important;--amber:#f59e0b!important;
  --purple:#8b5cf6!important;--shadow:0 8px 28px rgba(20,33,61,.06)!important;
}
html,body,.main,.content{background:#f6f8fb!important;color:#14213d!important}
.side{background:#ffffff!important;color:#14213d!important;border-right:1px solid #e5eaf0!important}
.brand b,.brand span,.brand .mark,.sidefoot{color:#14213d!important}
.brand span,.sidefoot,.muted,.title p,.metric .label,.stage small,.event p{color:#6b7c93!important}
.online,.live,.healthy{color:#10a875!important}
.nav a{color:#36506f!important;background:transparent!important;border-color:transparent!important}
.nav a:hover{background:#fff4f5!important;color:#e11d2e!important;border-color:#ffe1e5!important}
.nav a.active{background:#fff0f1!important;color:#e11d2e!important;border-color:#ffe1e5!important}
.top{background:rgba(255,255,255,.96)!important;border-bottom:1px solid #e5eaf0!important;box-shadow:0 3px 16px rgba(20,33,61,.035)!important}
.search{background:#f5f7fa!important;border:1px solid #eef1f5!important;color:#6b7c93!important}
.avatar{background:#14213d!important;color:#ffffff!important}
.card,.panel,.modal,.admin-tab-lock-card{background:#ffffff!important;border:1px solid #e5eaf0!important;box-shadow:0 8px 28px rgba(20,33,61,.06)!important}
.card:hover{box-shadow:0 12px 32px rgba(20,33,61,.08)!important}
.khead,.stage b,.table td,.metric .value,.title h1{color:#14213d!important}
.dot{background:#10b981!important;box-shadow:0 0 0 4px rgba(16,185,129,.10)!important}
.ki,.si,.hi{background:#eef4ff!important;color:#2563eb!important}
.sky,.lav{background:#eaf2ff!important;color:#2563eb!important}
.rose{background:#fff0f1!important;color:#e11d2e!important}
.mint,.stage.done .si,.stage.publish .si{background:#e8fbf3!important;color:#0a9c70!important}
.stage.warn .si{background:#fff7e6!important;color:#b7791f!important}
.stage.review .si{background:#fff0f1!important;color:#e11d2e!important}
.stage.active .si{background:#2563eb!important;color:#ffffff!important;box-shadow:0 0 0 5px rgba(37,99,235,.10)!important}
.table th{background:#f5f7fa!important;color:#36506f!important;border-bottom:1px solid #e5eaf0!important}
.table td{color:#14213d!important;border-color:#edf0f5!important}
.table tbody tr:hover{background:#f6f9ff!important}
.status{background:#eef4ff!important;color:#2563eb!important}
.primary,.toast,.toast.ok{background:#2563eb!important;color:#ffffff!important;box-shadow:0 4px 12px rgba(37,99,235,.18)!important}
.toast.err,.dangerbtn,.red,.danger{background:#fff0f1!important;color:#d92332!important}
.secondary,.gray,.processbtn,.iconbtn,.trashbtn,.btn.ghost,.ghost{background:#ffffff!important;color:#36506f!important;border:1px solid #dbe3ef!important}
.success,.green,.btn.success{background:#e8fbf3!important;color:#087f5b!important}
.blue,.purple{background:#eef4ff!important;color:#2563eb!important}
.amber{background:#fff7e6!important;color:#b7791f!important}
.input,.select,textarea{background:#ffffff!important;color:#14213d!important;border:1px solid #dbe3ef!important}
.input:focus,.select:focus,textarea:focus{border-color:#2563eb!important;box-shadow:0 0 0 3px rgba(37,99,235,.10)!important}
.processbtn:hover,.iconbtn:hover,.trashbtn:hover,.close{background:#2563eb!important;color:#ffffff!important;border-color:#2563eb!important}
.pdfspin,.activityspin{border-color:#dbe3ef!important;border-top-color:#2563eb!important;border-right-color:#2563eb!important}
.commit-track{background:#e5eaf0!important}.commit-bar{background:#2563eb!important}
.bars{border-color:#e5eaf0!important}.bar{background:#cbd8eb!important}.bar.g{background:#10b981!important}
.notice{background:#f5f8ff!important;border-color:#dce7fa!important;color:#36506f!important}
.issue{background:#fff7f7!important;border-left-color:#e11d2e!important;color:#7f1d1d!important}
.skeleton{background:#edf1f7!important}
.modalback{background:rgba(20,33,61,.48)!important}
.modalhead,.modalfoot{border-color:#e5eaf0!important}
.close{background:#f5f7fa!important;color:#36506f!important}
.timeline .event:before{background:#dbe3ef!important}.eventdot{background:#cbd8eb!important;border-color:#ffffff!important;box-shadow:0 0 0 1px #dbe3ef!important}
.event.active .eventdot{background:#2563eb!important;box-shadow:0 0 0 5px rgba(37,99,235,.10)!important}
.admin-tab-lock{background:#f6f8fb!important}
.admin-tab-lock-card button{background:#2563eb!important;color:#ffffff!important}
pre.json{background:#14213d!important;color:#f6f8fb!important}


/* Final palette correction: cool violet + slate; remove blue/red/green accents and warm shadows */
:root{
  --bg:#f7f7fb!important;--panel:#ffffff!important;--ink:#29263d!important;
  --muted:#77758a!important;--line:#e7e6ef!important;--red:#6d5bd0!important;
  --blue:#6d5bd0!important;--green:#6d5bd0!important;--amber:#6d5bd0!important;
  --purple:#6d5bd0!important;--shadow:0 4px 14px rgba(49,46,129,.075)!important;
}
html,body,.main,.content{background:#f7f7fb!important;color:#29263d!important}
.side{background:#ffffff!important;color:#29263d!important;border-right:1px solid #e7e6ef!important}
.brand b,.brand span,.brand .mark,.sidefoot,.khead,.stage b,.table td,.metric .value,.title h1{color:#29263d!important}
.brand span,.sidefoot,.muted,.title p,.metric .label,.stage small,.event p{color:#77758a!important}
.online,.live,.healthy{color:#6d5bd0!important}
.nav a{color:#59566f!important;background:transparent!important;border-color:transparent!important}
.nav a:hover,.nav a.active{background:#f0edff!important;color:#5b4ac4!important;border-color:#e2dcff!important}
.top{background:rgba(255,255,255,.97)!important;border-bottom:1px solid #e7e6ef!important;box-shadow:0 2px 8px rgba(49,46,129,.035)!important}
.search{background:#fafaff!important;border:1px solid #e7e6ef!important;color:#77758a!important}
.avatar{background:#393451!important;color:#ffffff!important}
.card,.panel,.modal,.admin-tab-lock-card{background:#ffffff!important;border:1px solid #e7e6ef!important;box-shadow:0 4px 14px rgba(49,46,129,.075)!important}
.card:hover{box-shadow:0 6px 18px rgba(49,46,129,.10)!important}
.dot{background:#6d5bd0!important;box-shadow:0 0 0 4px rgba(109,91,208,.10)!important}
.ki,.si,.hi,.sky,.lav,.rose,.mint,.stage.done .si,.stage.publish .si,.stage.warn .si,.stage.review .si{
  background:#f0edff!important;color:#5b4ac4!important;
}
.stage.active .si{background:#6d5bd0!important;color:#ffffff!important;box-shadow:0 0 0 5px rgba(109,91,208,.12)!important}
.table th{background:#f8f7fc!important;color:#59566f!important;border-bottom:1px solid #e7e6ef!important}
.table td{color:#29263d!important;border-color:#eeedf4!important}
.table tbody tr:hover{background:#faf9ff!important}
.status,.blue,.purple,.green,.success,.amber,.primary,.toast,.toast.ok,.btn.success{
  background:#f0edff!important;color:#5b4ac4!important;border-color:#e2dcff!important;
}
.toast.err,.dangerbtn,.red,.danger{background:#f0edff!important;color:#5b4ac4!important;border-color:#e2dcff!important}
.secondary,.gray,.processbtn,.iconbtn,.trashbtn,.btn.ghost,.ghost,.close{
  background:#ffffff!important;color:#59566f!important;border:1px solid #e1dfec!important;
}
.input,.select,textarea{background:#ffffff!important;color:#29263d!important;border:1px solid #e1dfec!important}
.input:focus,.select:focus,textarea:focus{border-color:#8b7ce8!important;box-shadow:0 0 0 3px rgba(109,91,208,.10)!important}
.processbtn:hover,.iconbtn:hover,.trashbtn:hover,.close:hover,.primary:hover{
  background:#6d5bd0!important;color:#ffffff!important;border-color:#6d5bd0!important;
}
.pdfspin,.activityspin{border-color:#e1dfec!important;border-top-color:#6d5bd0!important;border-right-color:#6d5bd0!important}
.commit-track{background:#e7e6ef!important}.commit-bar{background:#6d5bd0!important}
.bars{border-color:#e7e6ef!important}.bar,.bar.g{background:#b8afea!important}
.notice{background:#f8f7ff!important;border-color:#e2dcff!important;color:#59566f!important}
.issue{background:#f8f7ff!important;border-left-color:#8b7ce8!important;color:#59566f!important}
.skeleton{background:#eeedf5!important}
.modalback{background:rgba(41,38,61,.38)!important}
.modalhead,.modalfoot{border-color:#e7e6ef!important}
.timeline .event:before{background:#e1dfec!important}
.eventdot{background:#b8afea!important;border-color:#ffffff!important;box-shadow:0 0 0 1px #e1dfec!important}
.event.active .eventdot{background:#6d5bd0!important;box-shadow:0 0 0 5px rgba(109,91,208,.10)!important}
.admin-tab-lock{background:#f7f7fb!important}
.admin-tab-lock-card button{background:#6d5bd0!important;color:#ffffff!important}
pre.json{background:#29263d!important;color:#f7f7fb!important}


/* Strict neutral theme: white, greys, and charcoal only */
:root{
 --bg:#f4f4f4!important;--panel:#ffffff!important;--ink:#262626!important;
 --muted:#707070!important;--line:#dedede!important;
 --red:#666666!important;--blue:#666666!important;--green:#666666!important;
 --amber:#666666!important;--purple:#666666!important;
 --shadow:0 3px 12px rgba(0,0,0,.07)!important;
}
html,body,.main,.content,.admin-tab-lock{background:#f4f4f4!important;color:#262626!important}
.side,.top,.card,.panel,.modal,.admin-tab-lock-card{background:#fff!important;color:#262626!important;border-color:#dedede!important;box-shadow:0 3px 12px rgba(0,0,0,.06)!important}
.brand b,.brand span,.brand .mark,.sidefoot,.khead,.stage b,.table td,.metric .value,.title h1,
.label,.value,h1,h2,h3,strong,b{color:#262626!important}
.brand span,.sidefoot,.muted,.title p,.metric .label,.stage small,.event p,.small{color:#707070!important}
.nav a,.secondary,.gray,.processbtn,.iconbtn,.trashbtn,.btn.ghost,.ghost{color:#555!important;background:#fff!important;border-color:#d6d6d6!important}
.nav a:hover,.nav a.active{background:#e9e9e9!important;color:#222!important;border-color:#d0d0d0!important}
.online,.live,.healthy{color:#555!important}
.avatar,pre.json{background:#333!important;color:#fff!important}
.card:hover{box-shadow:0 5px 15px rgba(0,0,0,.09)!important}
.dot{background:#777!important;box-shadow:0 0 0 4px rgba(0,0,0,.07)!important}
.ki,.si,.hi,.sky,.lav,.rose,.mint,.stage.done .si,.stage.publish .si,.stage.warn .si,.stage.review .si,
.status,.blue,.purple,.green,.success,.amber,.primary,.toast,.toast.ok,.btn.success,.toast.err,.dangerbtn,.red,.danger{
 background:#e9e9e9!important;color:#333!important;border-color:#d2d2d2!important;box-shadow:none!important
}
.stage.active .si,.processbtn:hover,.iconbtn:hover,.trashbtn:hover,.close,.admin-tab-lock-card button{
 background:#555!important;color:#fff!important;border-color:#555!important;box-shadow:none!important
}
.table th{background:#f0f0f0!important;color:#444!important;border-color:#dedede!important}
.table td{color:#292929!important;border-color:#e5e5e5!important}
.table tbody tr:hover{background:#f7f7f7!important}
.input,.select,textarea,.search{background:#fff!important;color:#333!important;border:1px solid #d4d4d4!important}
.input:focus,.select:focus,textarea:focus{border-color:#888!important;box-shadow:0 0 0 2px rgba(0,0,0,.07)!important}
.pdfspin,.activityspin{border-color:#d8d8d8!important;border-top-color:#666!important;border-right-color:#666!important}
.commit-track,.bars{background:#e5e5e5!important;border-color:#d8d8d8!important}
.commit-bar,.bar,.bar.g,.eventdot,.event.active .eventdot{background:#777!important;border-color:#fff!important;box-shadow:none!important}
.notice,.issue,.issue.good{background:#f3f3f3!important;border-color:#d8d8d8!important;border-left-color:#888!important;color:#444!important}
.skeleton{background:#e9e9e9!important}
.modalback{background:rgba(0,0,0,.42)!important}
.modalhead,.modalfoot,.timeline .event:before{border-color:#dedede!important}
.close{background:#eee!important;color:#444!important}
.admin-tab-lock{background:#f4f4f4!important}

'''


def _shell(title: str, active: str, body: str, extra_js: str = '') -> str:
    links = [
        ('dashboard','⌂','Dashboard','/admin'),
        ('imports','⇧','Import Center','/admin/imports'),
        ('review','▤','Review Center','/admin/review'),
        ('releases','◉','Releases','/admin/releases'),
        ('health','♡','Data Health','/admin/health'),
        ('derived','▦','CET Data Calculator','/admin/derived-data'),
        ('audit','◷','Audit Log','/admin/audit'),
        ('feedback','✦','Feedback','/admin/feedback'),
        ('resolver','⌁','Website Resolver','/admin/resolver'),
        ('rollback','↶','Rollback','/admin/rollback'),
    ]
    nav=''.join(f'<a class="{"active" if active==k else ""}" href="{href}">{icon} &nbsp; {label}</a>' for k,icon,label,href in links)
    return f'''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} - CET CAP Admin</title><style>{CSS}</style></head><body class="admin-locked">
<div id="adminTabLock" class="admin-tab-lock"><div class="admin-tab-lock-card"><h2 id="adminTabLockTitle">Checking admin connection</h2><p id="adminTabLockMessage">Verifying the active admin tab with the server.</p><button id="adminTabLockRetry" type="button" onclick="window.__cetAdminTabRetry&&window.__cetAdminTabRetry()">Retry connection</button><small id="adminTabLockHint">A temporary connection failure does not necessarily mean another tab is open.</small></div></div>
<aside class="side"><div class="brand"><div class="mark">╫</div><div><b>CET CAP PORTAL</b></div></div><nav class="nav">{nav}</nav><div class="sidefoot">CET CAP Portal v1.0.0<br>Maharashtra Admissions System<br><span class="online">● System Online</span></div></aside>
<main class="main"><section class="content">{body}</section></main><div id="toastbox" class="toastbox"></div>{extra_js}
</body></html>'''


def _common_js():
    return r'''<script>
const ADMIN_AUTH_KEY='cet-cap-admin-auth-v1';
if(sessionStorage.getItem(ADMIN_AUTH_KEY)!=='1'){
  window.location.replace('/admin/login');
  throw new Error('Admin login required for this browser tab.');
}
window.__cetAdminTabReady=false;
window.__cetAdminLockMessage='Admin connection is unavailable. Retry the connection.';
(function(){
  const LOCK_KEY='cet-cap-admin-active-tab-v1';
  const TAB_KEY='cet-cap-admin-tab-id-v1';
  const TTL=45000;
  const body=document.body, gate=document.getElementById('adminTabLock');
  const title=document.getElementById('adminTabLockTitle');
  const message=document.getElementById('adminTabLockMessage');
  const retry=document.getElementById('adminTabLockRetry');
  const hint=document.getElementById('adminTabLockHint');
  const newId=()=>crypto.randomUUID?crypto.randomUUID():Date.now().toString(36)+'-'+Math.random().toString(36).slice(2)+'-'+Math.random().toString(36).slice(2);
  const instanceId=newId(); // unique to this live document; never copied with sessionStorage
  let tabId=sessionStorage.getItem(TAB_KEY);
  if(!tabId){tabId=newId();sessionStorage.setItem(TAB_KEY,tabId);}
  function csrf(){const m=document.cookie.match(/(?:^|; )cet_admin_csrf=([^;]+)/);return m?decodeURIComponent(m[1]):'';}
  function readLock(){try{return JSON.parse(localStorage.getItem(LOCK_KEY)||'null')}catch(_){return null}}
  function rotateTabId(){tabId=newId();sessionStorage.setItem(TAB_KEY,tabId);}
  async function resolveClonedTabIdentity(){
    const existing=readLock();
    const fresh=existing&&existing.id===tabId&&Number(existing.ts)>Date.now()-TTL;
    const owner=fresh?(existing.instanceId||null):null;
    if(!('BroadcastChannel' in window)){
      if(owner&&owner!==instanceId)rotateTabId();
      return;
    }
    const peers=new Set();
    let channel;
    try{
      channel=new BroadcastChannel('cet-cap-admin-tab-identity-v1');
      channel.onmessage=event=>{
        const data=event.data||{};
        if(data.tabId!==tabId||data.instanceId===instanceId)return;
        if(data.type==='probe')channel.postMessage({type:'peer',tabId,instanceId});
        if(data.type==='peer')peers.add(data.instanceId);
      };
      channel.postMessage({type:'probe',tabId,instanceId});
      await new Promise(resolve=>setTimeout(resolve,180));
      channel.close();
    }catch(_){
      try{if(channel)channel.close()}catch(__){}
      if(owner&&owner!==instanceId)rotateTabId();
      return;
    }
    // If a live tab owns this copied ID, only the copy rotates. A stale lock
    // without a live peer is retained so the same tab can recover after reload.
    if(owner&&owner!==instanceId&&peers.has(owner)){rotateTabId();return;}
    // Simultaneously opened duplicate tabs elect one deterministic owner.
    if(!owner&&peers.size&&[instanceId,...peers].sort()[0]!==instanceId)rotateTabId();
  }
  function showBlocked(kind='connection'){
    window.__cetAdminTabReady=false;
    body.classList.add('admin-locked');gate.classList.add('show');
    if(kind==='other-tab'){
      title.textContent='Admin panel active in another tab';
      message.textContent='Another browser tab currently holds the admin lock. Close that tab, or wait for its lock to expire, then retry.';
      retry.textContent='Retry admin lock';
      hint.textContent='For security, only one admin tab is allowed at a time.';
      window.__cetAdminLockMessage='Admin panel is active in another tab. Close the other tab or retry the lock.';
    }else{
      title.textContent='Cannot verify admin connection';
      message.textContent='The server did not confirm this tab’s admin lock. This can happen during a temporary outage; it does not prove another tab is open.';
      retry.textContent='Retry connection';
      hint.textContent='Your extraction worker continues independently while this PC remains on.';
      window.__cetAdminLockMessage='Admin server is temporarily unavailable. Retry the connection.';
    }
  }
  async function acquire(){
    // localStorage is only a cross-tab hint and can be stale during navigation.
    // The server-side lock is authoritative; never reject a tab locally first.
    try{
      const r=await fetch('/admin/api/admin-lock/acquire',{method:'POST',headers:{'X-CSRF-Token':csrf(),'X-Admin-Client-ID':tabId},cache:'no-store'});
      if(r.status===401){window.location.replace('/admin/login');return false;}
      if(r.status===409){showBlocked('other-tab');return false;}
      if(!r.ok){showBlocked('connection');return false;}
      try{localStorage.setItem(LOCK_KEY,JSON.stringify({id:tabId,ts:Date.now(),instanceId}));}catch(_){}
      body.classList.remove('admin-locked');gate.classList.remove('show');window.__cetAdminTabReady=true;window.__cetAdminLockMessage='';return true;
    }catch(_){showBlocked('connection');return false;}
  }
  window.__cetAdminTabRetry=acquire;
  const NAVIGATION_KEY='cet-cap-admin-same-tab-navigation-v1';
  let sameTabNavigation=false;
  try{
    sameTabNavigation=sessionStorage.getItem(NAVIGATION_KEY)==='1';
    sessionStorage.removeItem(NAVIGATION_KEY);
  }catch(_){}
  // A marker written by this document's pagehide means this is the next page
  // in the same tab. Preserve its tab ID rather than treating the previous
  // document, briefly alive during navigation, as a duplicated tab.
  window.__cetAdminLockPromise=(sameTabNavigation?Promise.resolve():resolveClonedTabIdentity()).then(acquire);
  // Backpressure is essential: a slow database heartbeat must not spawn a
  // new request every five seconds and worsen pool exhaustion.
  let heartbeatBusy=false;
  setInterval(async function(){
    if(!window.__cetAdminTabReady||heartbeatBusy)return;
    heartbeatBusy=true;
    try{
      const r=await fetch('/admin/api/admin-lock/heartbeat',{method:'POST',headers:{'X-CSRF-Token':csrf(),'X-Admin-Client-ID':tabId},cache:'no-store'});
      if(r.status===401){window.location.replace('/admin/login');return;}
      if(r.status===409){await acquire();return;}
      if(!r.ok){showBlocked('connection');return;}
      try{localStorage.setItem(LOCK_KEY,JSON.stringify({id:tabId,ts:Date.now(),instanceId}));}catch(_){}
    }catch(_){showBlocked('connection');}
    finally{heartbeatBusy=false;}
  },5000);
  // Do not block on storage events: a stale write from a previous page can
  // race with successful server acquisition. The next API/heartbeat response
  // will enforce the single-tab lock using the authoritative database row.
  // Clear only the browser-side ownership marker on page exit. A new document
  // in the same tab must reuse sessionStorage's tab ID, not mistake the old
  // document's instance ID for a duplicated tab. Do not DELETE the server lock
  // here: a keepalive release can race with the next page's acquire request.
  window.addEventListener('pagehide',function(){
    try{sessionStorage.setItem('cet-cap-admin-same-tab-navigation-v1','1');}catch(_){}
    const x=readLock();
    const ownsLock=x&&x.id===tabId&&(!x.instanceId||x.instanceId===instanceId);
    if(ownsLock){try{localStorage.removeItem(LOCK_KEY);}catch(_){}}
  });

})();
window.__cetAdminPollBusy=false;
window.__cetAdminRunPoll=async function(fn){if(window.__cetAdminPollBusy)return;window.__cetAdminPollBusy=true;try{if(!window.__cetAdminTabReady&&window.__cetAdminLockPromise)await window.__cetAdminLockPromise;if(!window.__cetAdminTabReady)return;await fn()}finally{window.__cetAdminPollBusy=false}};
const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const csrfHeaders=(extra={})=>{const m=document.cookie.match(/(?:^|; )cet_admin_csrf=([^;]+)/);return Object.assign({'X-CSRF-Token':m?decodeURIComponent(m[1]):'','X-Admin-Client-ID':sessionStorage.getItem('cet-cap-admin-tab-id-v1')||''},extra)};
async function toast(msg,type=''){const d=document.createElement('div');d.className='toast '+type;d.textContent=msg;document.querySelector('#toastbox').appendChild(d);setTimeout(()=>d.remove(),3500)}
async function api(url,opts={}){if(window.__cetAdminLockPromise)await window.__cetAdminLockPromise;if(!window.__cetAdminTabReady)throw new Error(window.__cetAdminLockMessage||'Admin connection is unavailable. Retry the connection.');const h=Object.assign({},opts.headers||{},{'X-Admin-Client-ID':sessionStorage.getItem('cet-cap-admin-tab-id-v1')||''});const r=await fetch(url,Object.assign({},opts,{headers:h}));const raw=await r.text();let data=raw;try{data=raw?JSON.parse(raw):null}catch{}if(r.status===401){window.location='/admin/login';throw new Error('Admin session expired. Please sign in again.')}if(!r.ok)throw new Error(typeof data==='string'?data:(data?.detail||'Request failed'));return data}
function fmtTime(v){if(!v)return '—';const d=new Date(String(v).replace(' ','T')+'Z');if(Number.isNaN(d.getTime()))return esc(v);return d.toLocaleString([], {dateStyle:'medium',timeStyle:'short'})}
function bytes(value){const n=Number(value);if(!Number.isFinite(n)||n<0)return '—';if(n<1024)return n+' B';const units=['KiB','MiB','GiB','TiB'];let size=n/1024,i=0;while(size>=1024&&i<units.length-1){size/=1024;i++}return size.toFixed(size>=100?0:size>=10?1:2)+' '+units[i]}
function badge(s){const x=String(s||'').toUpperCase(),c=x.includes('REVIEW')?'red':x.includes('FAIL')||x.includes('QUARANT')?'red':x.includes('PUBLISH')||x.includes('COMPLETE')||x.includes('VALID')?'green':x.includes('STAGED')||x.includes('COMMIT')?'purple':x.includes('RECEIVED')||x.includes('EXTRACT')||x.includes('NORMAL')?'blue':x.includes('WARN')?'amber':'gray';const loading=['RECEIVED','IDENTIFIED','EXTRACTING','NORMALIZING','VALIDATING','COMPARING'].includes(x);const label=(x==='COMMITTING'||x==='COMMITTED')?'DB COMMITTED • AWAITING PUBLISH':x==='CANDIDATE'?'UNVERIFIED':x.replaceAll('_',' ');return `<span class="status ${c}${loading?' loading':''}">${esc(label)}</span>`}
function countUp(el,to){const n=Number(to)||0,from=Number(el.dataset.value||0),start=performance.now(),dur=450;function tick(t){const p=Math.min(1,(t-start)/dur),e=1-Math.pow(1-p,3);el.textContent=Math.round(from+(n-from)*e).toLocaleString();if(p<1)requestAnimationFrame(tick)}el.dataset.value=n;requestAnimationFrame(tick)}
async function removeImport(id,btn){if(btn?.disabled)return;if(!confirm('Delete this import? The uploaded PDF and all uncommitted import data will be removed.'))return;try{if(btn)btn.disabled=true;await api('/admin/api/imports/'+id,{method:'DELETE',headers:csrfHeaders()});toast('Import deleted','ok');if(typeof load==='function')load()}catch(e){if(btn)btn.disabled=false;toast(e.message,'err')}}
async function retryImport(id,btn){if(btn?.disabled)return;if(!confirm('Retry processing this PDF?'))return;try{if(btn)btn.disabled=true;await api('/admin/api/imports/'+id+'/process',{method:'POST',headers:csrfHeaders()});toast('Processing restarted','ok');if(typeof load==='function')load()}catch(e){if(btn)btn.disabled=false;toast(e.message,'err')}}
async function cancelImport(id,btn){if(btn?.disabled)return;if(!confirm('Stop processing this PDF? The import will be marked Cancelled and can be retried later.'))return;try{if(btn)btn.disabled=true;await api('/admin/api/imports/'+id+'/cancel',{method:'POST',headers:csrfHeaders()});toast('Processing stopped','ok');if(typeof load==='function')load()}catch(e){if(btn)btn.disabled=false;toast(e.message,'err')}}
async function toggleProcess(id,btn){const d=await api('/admin/api/imports/'+id);const s=String(d.job?.status||'');if(['RECEIVED','IDENTIFIED','EXTRACTING','NORMALIZING','VALIDATING','COMPARING'].includes(s)){await cancelImport(id,btn)}else if(s==='CANCELLED'||s==='FAILED'){await retryImport(id,btn)}else{toast('This import is not currently stoppable or retryable','err')}}
</script>'''


def dashboard() -> str:
    body='''<div class="title"><div><h1>Admin Dashboard</h1><p>Live overview of imports, processing, releases and data quality.</p></div><div class="live"><span class="dot"></span>Live · <span id="lastRefresh">updating</span></div></div>
<div class="cards"><div class="card kpi"><div class="khead"><span class="ki sky">⇧</span>Imports Today</div><div class="num" id="today">0</div><div class="trend up">Real-time import history</div></div><div class="card kpi"><div class="khead"><span class="ki rose">▤</span>Pending Review</div><div class="num" id="pending">0</div><div class="trend warn">Needs admin action</div></div><div class="card kpi"><div class="khead"><span class="ki mint">▣</span>Production Records</div><div class="num" id="production">0</div><div class="trend up">Published database rows</div></div><div class="card kpi"><div class="khead"><span class="ki lav">♡</span>Data Health</div><div class="num" id="health">—</div><div class="trend" id="healthHint">Checking runtime…</div></div></div>
<div class="card panel" style="margin-bottom:14px"><div class="toolbar"><h2>◌ &nbsp;Website Usage</h2><span class="muted small">last 30 days</span></div><div class="cards" style="grid-template-columns:repeat(4,1fr);margin-top:14px"><div class="card kpi"><div class="khead">Visitors</div><div class="num" id="siteVisitors">—</div></div><div class="card kpi"><div class="khead">Searches</div><div class="num" id="siteSearches">—</div></div><div class="card kpi"><div class="khead">College Opens</div><div class="num" id="siteCollegeOpens">—</div></div><div class="card kpi"><div class="khead">Website Clicks</div><div class="num" id="siteClicks">—</div></div></div><div id="siteUsageDetail" class="muted small">Loading anonymous usage totals…</div></div>
<div class="card panel recent dashboard-imports"><div class="toolbar"><div><h2>Recent Imports</h2><div class="small muted" style="margin-top:4px">Latest uploaded files and their current processing status</div></div><a class="btn secondary" href="/admin/review">View All →</a></div><div class="tablewrap"><table class="table"><thead><tr><th>File</th><th>Year</th><th>Round</th><th>Type</th><th>Status</th><th>Updated</th><th></th></tr></thead><tbody id="rows"><tr><td colspan="7" class="skeleton">Loading</td></tr></tbody></table></div></div>'''
    js=_common_js()+r'''<script>

async function loadSiteUsage(){try{const d=await api('/admin/api/analytics/summary?days=30'),t=d.totals||{};for(const [id,key] of [['siteVisitors','visitors'],['siteSearches','searches'],['siteCollegeOpens','college_opens'],['siteClicks','website_clicks']])document.querySelector('#'+id).textContent=Number(t[key]||0).toLocaleString();document.querySelector('#siteUsageDetail').textContent='Anonymous usage totals · updated '+new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'})}catch(e){document.querySelector('#siteUsageDetail').textContent='Usage statistics are temporarily unavailable.'}}
async function load(){loadSiteUsage();try{const [o,j]=await Promise.all([api('/admin/api/overview'),api('/admin/api/imports')]);countUp(document.querySelector('#today'),o.imports_today);countUp(document.querySelector('#pending'),o.pending_review);countUp(document.querySelector('#production'),o.production_rows);document.querySelector('#health').textContent=o.health.ok?'Healthy':'Check';document.querySelector('#healthHint').className='trend '+(o.health.ok?'up':'warn');document.querySelector('#healthHint').textContent=o.health.ok?'All runtime checks passing':'Attention required';document.querySelector('#lastRefresh').textContent=new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'});document.querySelector('#rows').innerHTML=j.slice(0,8).map(x=>`<tr><td>📄 ${esc(x.original_filename)}</td><td>${esc(x.year||'—')}</td><td>${esc(x.round||'—')}</td><td>${esc(x.course_family||x.data_type||'—')}</td><td>${badge(x.status)}</td><td>${fmtTime(x.updated_at||x.created_at)}</td><td><div class="rowactions">${['RECEIVED','IDENTIFIED','EXTRACTING','NORMALIZING','VALIDATING','COMPARING'].includes(String(x.status||'').toUpperCase())?'<span class="activityspin" title="Processing" aria-label="Processing"></span>':''}${x.status==='FAILED'?'<button class="btn secondary" onclick="retryImport('+x.id+',this)">Retry</button>':''}<button class="trashbtn" title="Delete import" aria-label="Delete import" onclick="removeImport(${x.id},this)" ${['RECEIVED','IDENTIFIED','REVIEW_REQUIRED','STAGED','FAILED','CANCELLED','QUARANTINED'].includes(String(x.status||'').toUpperCase())?'':'disabled'}>🗑</button></div></td></tr>`).join('')||'<tr><td colspan="7" class="empty">No imports yet.</td></tr>';}catch(e){toast(e.message,'err')}}window.refreshAdminData=load;window.__cetAdminRunPoll(load);setInterval(()=>window.__cetAdminRunPoll(load),5000);
</script>'''
    return _shell('Admin Dashboard','dashboard',body,js)



def import_center() -> str:
    body="""<div class="title"><div><h1>Import Center</h1><p>Upload PDFs to the server, monitor extraction, and control queued jobs.</p></div><div class="live"><span class="dot"></span>Server-side processing</div></div>
<div class="grid4 runtime-metrics" style="margin-bottom:14px">
  <div class="card metric"><div class="label">Backend RAM</div><div class="value" id="ramValue">—</div><div class="small muted" id="ramDetail">Reading cgroup metrics</div></div>
  <div class="card metric"><div class="label">CPU usage</div><div class="value" id="cpuValue">—</div><div class="small muted" id="cpuDetail">Measured between polls</div></div>
  <div class="card metric extraction-mini"><div class="label">Extraction <span id="queueCount" class="muted">0 queued</span></div><div class="extract-live"><span id="extractSpinner" class="activityspin" style="display:none" aria-label="Extraction running"></span><span id="activeJobStatus" class="small muted">Idle</span></div><div class="value extract-progress" id="pageProgressText">— pages · — chunks</div><div class="small muted extract-file" id="activeJobMessage">Waiting for a job.</div></div>
 </div>
<div class="pagegrid upload-layout"><div class="card panel"><h2>Upload CAP PDFs</h2><form id="uploadForm" style="margin-top:12px"><label class="notice" style="display:block;text-align:center;padding:26px;border:1px dashed #D8CFBC"><input id="file" type="file" accept="application/pdf,.pdf" multiple required style="display:block;margin:auto auto 12px"><b>Select PDFs</b><div class="small muted">Maximum 50 MiB per PDF · Uploads run on the server</div></label><div id="selectedFiles" class="small muted" style="margin-top:8px">No PDFs selected.</div><div style="margin-top:12px"><button class="btn primary" id="uploadBtn">Upload</button></div></form><div id="uploadState" class="small muted" style="margin-top:10px"></div></div></div>
<div class="card panel" style="margin-top:14px"><div class="toolbar"><h2>Import queue</h2><button class="btn secondary" onclick="window.refreshAdminData()">↻ Refresh</button></div><div class="tablewrap"><table class="table import-queue"><thead><tr><th>Metadata</th><th>Status</th><th>Updated</th><th>Controls</th></tr></thead><tbody id="list"></tbody></table></div></div>"""
    js=_common_js()+r'''<script>
const form=document.querySelector('#uploadForm'),fileInput=document.querySelector('#file'),uploadBtn=document.querySelector('#uploadBtn'),uploadState=document.querySelector('#uploadState');
fileInput.addEventListener('change',()=>{const files=[...fileInput.files];document.querySelector('#selectedFiles').textContent=files.length?files.map(f=>f.name+' ('+bytes(f.size)+')').join(' · '):'No PDFs selected.'});
form.addEventListener('submit',async e=>{e.preventDefault();const files=[...fileInput.files];if(!files.length)return;if(files.some(f=>f.size>50*1024*1024)){toast('Each PDF must be 50 MiB or smaller.','err');return}uploadBtn.disabled=true;fileInput.disabled=true;try{for(let i=0;i<files.length;i++){uploadState.textContent='Uploading '+(i+1)+' of '+files.length+': '+files[i].name;const data=new FormData();data.append('file',files[i],files[i].name);const result=await api('/admin/api/imports',{method:'POST',headers:csrfHeaders(),body:data});toast('Queued '+files[i].name+' · job #'+(result.id||result.job_id),'ok');await load()}uploadState.textContent='All selected PDFs were submitted. Processing continues when this page is closed.';fileInput.value='';document.querySelector('#selectedFiles').textContent='No PDFs selected.'}catch(err){uploadState.textContent='Upload stopped: '+err.message;toast(err.message,'err')}finally{uploadBtn.disabled=false;fileInput.disabled=false;await load()}});
async function control(id,action){const labels={pause:'Pause extraction at the next safe checkpoint?',resume:'Resume this extraction?',cancel:'Cancel this import? You can retry it later.'};if(!confirm(labels[action]||'Continue?'))return;try{await api('/admin/api/imports/'+id+'/'+action,{method:'POST',headers:csrfHeaders()});toast(action==='pause'?'Pause requested':action==='resume'?'Resume requested':'Cancellation requested','ok');await load()}catch(e){toast(e.message,'err')}}
async function removeJob(id){const job=(await api('/admin/api/imports')).find(x=>Number(x.id)===Number(id));const drive=String(job?.stored_path||'').startsWith('gdrive://');if(!confirm(drive?'Delete this CAPFind import record and its uncommitted staging data? The original PDF will remain in Google Drive.':'Permanently delete this import, its source PDF and uncommitted staging data?'))return;try{await api('/admin/api/imports/'+id,{method:'DELETE',headers:csrfHeaders()});toast(drive?'Import deleted; original Drive PDF remains':'Import deleted','ok');await load()}catch(e){toast(e.message,'err')}}

async function retryJob(id){if(!confirm('Retry this failed or cancelled import?'))return;try{await api('/admin/api/imports/'+id+'/process',{method:'POST',headers:csrfHeaders()});toast('Retry queued','ok');await load()}catch(e){toast(e.message,'err')}}
function renderRuntime(d){const m=d.memory||{},c=d.cpu||{},j=d.active_job;window.activeRuntimeJob=j;document.querySelector('#queueCount').textContent=Number(d.queued_jobs||0)+' queued';document.querySelector('#ramValue').textContent=m.used_bytes==null?'n/a':bytes(m.used_bytes);document.querySelector('#ramDetail').textContent=m.limit_bytes?bytes(m.used_bytes)+' / '+bytes(m.limit_bytes)+' · '+(m.used_percent??'—')+'%':'Host limit not exposed';document.querySelector('#cpuValue').textContent=c.percent_of_available_capacity==null?'n/a':c.percent_of_available_capacity+'%';document.querySelector('#cpuDetail').textContent=c.quota_cores?'Quota '+c.quota_cores+' CPU core(s)':'CPU quota not exposed';document.querySelector('#activeJobStatus').textContent=j?('Job #'+j.id+' · '+j.status):'Idle';document.querySelector('#extractSpinner').style.display=j&&['EXTRACTING','QUEUED','PAUSED'].includes(String(j.status||'').toUpperCase())?'inline-block':'none';document.querySelector('#activeJobMessage').textContent=j?(j.filename+' · '+(j.paused_at_checkpoint?'Paused at checkpoint':(j.pause_requested?'Pause requested':(j.page?'Extracting':'Preparing')))):'Waiting for a job.';document.querySelector('#pageProgressText').textContent=j?((j.page??0)+' / '+(j.total_pages??'—')+' pages · '+(j.chunk_count??0)+' / '+(j.total_chunks??'—')+' chunks'):'— pages · — chunks'}
function queueStatusDetail(x,s){const j=window.activeRuntimeJob&&Number(window.activeRuntimeJob.id)===Number(x.id)?window.activeRuntimeJob:null;if(['EXTRACTING','NORMALIZING','VALIDATING','COMPARING','QUEUED','PAUSED'].includes(s)){if(j&&s!=='QUEUED')return 'Page '+(j.page??'—')+' / '+(j.total_pages??'—')+' · Chunk '+(j.chunk_count??'—')+' / '+(j.total_chunks??'—');return s==='QUEUED'?'Queued':s==='PAUSED'?'Paused':'Processing'}if(['STAGED','REVIEW_REQUIRED'].includes(s))return 'Staged';if(['COMMITTING','COMMITTED'].includes(s))return 'DB committed · Awaiting publish';if(s==='COMPLETED')return 'Published / verified';return s.replaceAll('_',' ').toLowerCase()}
async function load(){try{const [jobs,runtime]=await Promise.all([api('/admin/api/imports'),api('/admin/api/runtime')]);renderRuntime(runtime);document.querySelector('#list').innerHTML=jobs.slice(0,50).map(x=>{const s=String(x.status||'').toUpperCase(),active=['QUEUED','EXTRACTING','NORMALIZING','VALIDATING','COMPARING','PAUSED'].includes(s),canDelete=['RECEIVED','IDENTIFIED','REVIEW_REQUIRED','STAGED','FAILED','CANCELLED','QUARANTINED'].includes(s),isDrive=String(x.stored_path||'').startsWith('gdrive://'),canDeleteSource=!isDrive&&!active&&!x.source_deleted&&['REVIEW_REQUIRED','STAGED','FAILED','CANCELLED','QUARANTINED','COMPLETED'].includes(s),meta=[x.original_filename,x.job_key?'Job '+x.job_key:null,'#'+x.id,x.data_type,x.course_family,x.year,x.round,isDrive?'Google Drive source':null].filter(Boolean).join(' · ');let controls='';if(active){const pauseState=s==='PAUSED'||(window.activeRuntimeJob&&Number(window.activeRuntimeJob.id)===Number(x.id)&&(window.activeRuntimeJob.pause_requested||window.activeRuntimeJob.paused_at_checkpoint));controls+='<button class="iconbtn" title="'+(pauseState?'Resume':'Pause')+'" aria-label="'+(pauseState?'Resume':'Pause')+'" onclick="control('+x.id+',\''+(pauseState?'resume':'pause')+'\')">'+(pauseState?'▶':'Ⅱ')+'</button><button class="iconbtn" title="Cancel" aria-label="Cancel" onclick="control('+x.id+',\'cancel\')">×</button>'}else if(s==='FAILED'||s==='CANCELLED'){controls+='<button class="iconbtn" title="Retry" aria-label="Retry" onclick="retryJob('+x.id+')">↻</button>'}if(canDelete)controls+='<button class="iconbtn" title="Delete import and source PDF" aria-label="Delete import and source PDF" onclick="removeJob('+x.id+')">🗑</button>';return '<tr><td><b>'+esc(meta||'Awaiting identification')+'</b></td><td>'+badge(s)+'<div class="small muted status-detail">'+esc(queueStatusDetail(x,s))+'</div></td><td>'+fmtTime(x.updated_at||x.created_at)+'</td><td><div class="rowactions">'+controls+'</div></td></tr>'}).join('')||'<tr><td colspan="4" class="empty">No imports yet.</td></tr>'}catch(e){toast(e.message,'err')}}window.refreshAdminData=load;window.__cetAdminRunPoll(load);setInterval(()=>window.__cetAdminRunPoll(load),15000);
</script>'''
    return _shell('Import Center','imports',body,js)


def review_center() -> str:
    body='''<div class="title"><div><h1>Review Center</h1><p>Inspect staged records before they are committed to production.</p></div><div class="live"><span class="dot"></span>Auto-refresh · 5s</div></div>
<div class="grid4"><div class="card metric"><div class="label">Awaiting Review</div><div class="value" id="mReview">0</div></div><div class="card metric"><div class="label">Committing</div><div class="value" id="mCommit">0</div></div><div class="card metric"><div class="label">Staged Rows</div><div class="value" id="mRows">0</div></div><div class="card metric"><div class="label">Validation Issues</div><div class="value" id="mIssues">0</div></div></div>
<div class="card panel" style="margin-top:14px"><div class="toolbar"><div class="filters"><input id="q" class="input" placeholder="Search file, job, course…"><select id="status" class="select"><option value="">All statuses</option><option>STAGED</option><option>REVIEW_REQUIRED</option><option>COMMITTING</option></select><select id="year" class="select"><option value="">All years</option></select></div><button class="btn secondary" onclick="window.refreshAdminData()">↻ Refresh</button></div><div class="tablewrap"><table class="table"><thead><tr><th>Import</th><th>Source</th><th>Metadata</th><th>Rows</th><th>Status</th><th>Updated</th><th>Action</th></tr></thead><tbody id="list"><tr><td colspan="7" class="skeleton">Loading</td></tr></tbody></table></div></div>
<div class="modalback" id="modal"><div class="modal"><div class="modalhead"><b id="modalTitle">Review Import</b><button class="close" onclick="closeModal()">×</button></div><div class="modalbody" id="modalBody"></div><div class="modalfoot" id="modalFoot"></div></div></div>'''
    js=_common_js()+r'''<script>
let jobs=[];const reviewSpinStyle=document.createElement('style');reviewSpinStyle.textContent='@keyframes reviewSpin{to{transform:rotate(360deg)}}';document.head.appendChild(reviewSpinStyle);const q=document.querySelector('#q'),st=document.querySelector('#status'),yr=document.querySelector('#year');[q,st,yr].forEach(x=>x.addEventListener('input',render));
async function load(){try{jobs=await api('/admin/api/review');const years=[...new Set(jobs.map(x=>x.year).filter(Boolean))].sort().reverse();yr.innerHTML='<option value="">All years</option>'+years.map(y=>`<option>${esc(y)}</option>`).join('');document.querySelector('#mReview').textContent=jobs.filter(x=>['STAGED','REVIEW_REQUIRED'].includes(x.status)).length;document.querySelector('#mCommit').textContent=jobs.filter(x=>x.status==='COMMITTING').length;document.querySelector('#mRows').textContent=jobs.reduce((n,d)=>n+Number(d.staging_row_count||0),0).toLocaleString();document.querySelector('#mIssues').textContent=jobs.reduce((n,d)=>n+Number(d.validation_issue_count||0),0).toLocaleString();render()}catch(e){toast(e.message,'err')}}
function render(){const term=q.value.trim().toLowerCase(),sv=st.value,yv=yr.value;const data=jobs.filter(x=>(!sv||x.status===sv)&&(!yv||String(x.year)===yv)&&(!term||[x.job_key,x.original_filename,x.course_family,x.data_type].some(v=>String(v||'').toLowerCase().includes(term))));document.querySelector('#list').innerHTML=data.map(x=>`<tr><td><b>${esc(x.job_key)}</b><div class="small muted">#${x.id}</div></td><td>${esc(x.original_filename)}</td><td>${esc([x.data_type,x.course_family,x.year,x.round].filter(Boolean).join(' · '))}</td><td>${esc(x.staging_row_count??'—')}</td><td>${badge(x.status)}</td><td>${fmtTime(x.updated_at||x.created_at)}</td><td><button class="btn primary" onclick="openReview(${x.id})">Review</button></td></tr>`).join('')||'<tr><td colspan="7" class="empty">No imports match the current filters.</td></tr>'}
async function openReview(id){const modal=document.querySelector('#modal');const body=document.querySelector('#modalBody');const foot=document.querySelector('#modalFoot');document.querySelector('#modalTitle').textContent='Loading review…';body.innerHTML='<div style="padding:28px 12px;text-align:center"><div class="spinner" style="margin:0 auto 12px;width:28px;height:28px;border:3px solid #D8CFBC;border-top-color:#11120D;border-radius:50%;animation:reviewSpin .8s linear infinite"></div><b>Loading review details…</b><div class="small muted" style="margin-top:6px">Fetching staged records and validation results.</div></div>';foot.innerHTML='<button class="btn secondary" onclick="closeModal()">Cancel</button>';modal.classList.add('show');try{const d=await api('/admin/api/imports/'+id+'/review');const j=d.job;document.querySelector('#modalTitle').textContent=`${j.job_key} · Review`;const allReview=(d.rows||[]).filter(r=>String(r.validation_status||'').toUpperCase()==='REVIEW');const failedFiles=(d.results||[]).filter(r=>String(r.validation_status||'').toUpperCase()!=='PASS');const legacyFileLevel=allReview.length>0&&allReview.every(r=>String(r.validation_message||'').includes('Total issues:'));const reportText=failedFiles.map(r=>{try{return String(JSON.parse(r.summary_json||'{}').validation||'')}catch{return ''}}).join('\n');const unknownCategories=[...reportText.matchAll(/\[([^\]]+)\]\s*:\s*\d+/g)].map(m=>m[1].trim().toUpperCase());const issue=legacyFileLevel?allReview.filter(r=>{try{return unknownCategories.includes(String(JSON.parse(r.normalized_json||'{}').category||'').trim().toUpperCase())}catch{return false}}).map(r=>({...r,validation_message:'Unknown category: '+String(JSON.parse(r.normalized_json||'{}').category||'')})):allReview;const fileReview=(d.rows||[]).filter(r=>String(r.validation_status||'').toUpperCase()==='FILE_REVIEW').length+(legacyFileLevel?allReview.length-issue.length:0);const validationSummary=failedFiles.length?`<div class="issue"><b>File-level validation failed</b><br>${esc(failedFiles.map(r=>{try{const s=JSON.parse(r.summary_json||'{}');return String(s.validation||'').match(/Total issues:\s*\d+[^\n]*/)?.[0]||'See validation report';}catch{return 'See validation report';}}).filter(Boolean).join(' · '))}</div>`:'';document.querySelector('#modalBody').innerHTML=`<div class="grid4" style="grid-template-columns:repeat(3,1fr)"><div class="notice"><b>Source</b><br>${esc(j.original_filename)}</div><div class="notice"><b>Status</b><br>${badge(j.status)}</div><div class="notice"><b>Validation</b><br>${issue.length?issue.length+' row issue(s)':failedFiles.length?'File-level review required':'No issues reported'}</div></div>${validationSummary}${fileReview?`<div class="issue">${fileReview} row(s) are flagged by the file-level validation gate; this is not a count of distinct row errors. Review the validation report before approving.</div>`:''}<h3 style="font-size:13px;margin:20px 0 9px">Staged records (${d.rows?.length||0}${(d.rows?.length||0)>=500?'+':''})</h3>${issue.length?issue.slice(0,20).map(r=>`<div class="issue"><b>${esc(r.result_type||'Record')}</b> · page ${esc(r.source_page||'—')}<br>${esc(r.validation_message||r.validation_status)}</div>`).join(''):'<div class="issue good">No individual row errors detected in the returned staged records.</div>'}<details style="margin-top:12px"><summary>Raw staged JSON (first 10)</summary><pre class="json">${esc(JSON.stringify((d.rows||[]).slice(0,10),null,2))}</pre></details>`;const legacyMhNeedsRevalidation=j.status==='REVIEW_REQUIRED'&&j.original_filename==='2026BCA_CAP2_MH_CutOff.pdf'&&failedFiles.some(r=>String(r.validation_status||'').toUpperCase()!=='PASS');document.querySelector('#modalFoot').innerHTML=(['STAGED','REVIEW_REQUIRED'].includes(j.status))?(legacyMhNeedsRevalidation?`<button class="btn dangerbtn" onclick="reject(${id})">Reject / Quarantine</button><button class="btn primary" onclick="revalidateLegacyMH(${id})">Revalidate legacy MH mapping</button>`:`<button class="btn dangerbtn" onclick="reject(${id})">Reject / Quarantine</button><button class="btn success" onclick="approve(${id})">Approve & Commit</button>`):'<button class="btn secondary" onclick="closeModal()">Close</button>';document.querySelector('#modal').classList.add('show')}catch(e){document.querySelector('#modalTitle').textContent='Unable to load review';body.innerHTML='<div class="issue"><b>Review details could not be loaded.</b><br>'+esc(e.message||'Unknown error')+'</div><p class="small muted">Check your admin connection and try opening this import again.</p>';foot.innerHTML='<button class="btn secondary" onclick="closeModal()">Close</button><button class="btn primary" onclick="openReview('+id+')">Retry</button>';modal.classList.add('show')}}
function closeModal(){document.querySelector('#modal').classList.remove('show')}
async function revalidateLegacyMH(id){if(!confirm('Revalidate the 2026 BCA CAP-2 staged rows against the current MH → MI category rule? This does not commit or publish data.'))return;try{const d=await api('/admin/api/imports/'+id+'/revalidate-legacy-mh',{method:'POST',headers:csrfHeaders({'Content-Type':'application/json'}),body:JSON.stringify({})});toast('Revalidated '+d.rows_revalidated+' staged rows. Review them, then approve and publish separately.','ok');await openReview(id);load()}catch(e){toast(e.message,'err')}}
async function approve(id){
  const notes=prompt('Approval note (optional):','');if(notes===null)return;
  const foot=document.querySelector('#modalFoot'),body=document.querySelector('#modalBody'),title=document.querySelector('#modalTitle');
  const buttons=[...foot.querySelectorAll('button')];buttons.forEach(b=>b.disabled=true);
  let polling=true, postFinished=false, lastProgress=null;
  title.textContent='Committing import #'+id;
  body.innerHTML='<div class="commit-progress"><div class="commit-progress-head"><span class="activityspin"></span><b id="commitStage">Starting commit…</b><strong id="commitPercent">0%</strong></div><div class="commit-track"><div id="commitBar" class="commit-bar"></div></div><div class="commit-progress-stats"><span id="commitRows">Preparing row count…</span><span id="commitUpdated">Waiting for server progress</span></div><p id="commitMessage" class="small muted">Keep this window open. The server is committing staged rows in a database transaction.</p></div>';
  foot.innerHTML='<button class="btn secondary" disabled>Commit in progress…</button>';
  document.querySelector('#modal').classList.add('show');
  const updateProgress=async()=>{
    while(polling){
      try{
        const p=await api('/admin/api/imports/'+id+'/commit-progress');lastProgress=p;
        const pct=Math.max(0,Math.min(100,Number(p.progress)||0));
        const stage=document.querySelector('#commitStage'),percent=document.querySelector('#commitPercent'),bar=document.querySelector('#commitBar'),rows=document.querySelector('#commitRows'),updated=document.querySelector('#commitUpdated'),message=document.querySelector('#commitMessage');
        if(stage)stage.textContent=p.stage||'Preparing commit';
        if(percent)percent.textContent=pct+'%';
        if(bar)bar.style.width=pct+'%';
        if(rows)rows.textContent=(Number(p.processed)||0).toLocaleString()+' / '+(Number(p.total)||0).toLocaleString()+' rows processed';
        if(updated)updated.textContent=p.updated_at?'Updated '+fmtTime(p.updated_at):'Waiting for first progress update';
        if(message)message.textContent=p.message||'Commit is running…';
      }catch(e){
        const updated=document.querySelector('#commitUpdated');
        if(updated)updated.textContent='Reconnecting to progress updates…';
      }
      if(!polling)break;
      await new Promise(resolve=>setTimeout(resolve,800));
    }
  };
  const pollTask=updateProgress();
  try{
    const result=await api('/admin/api/imports/'+id+'/approve',{method:'POST',headers:csrfHeaders({'Content-Type':'application/json'}),body:JSON.stringify({notes})});
    postFinished=true;polling=false;await pollTask;
    body.innerHTML='<div class="notice"><b>Database commit completed.</b><p>'+(Number(result.rows_inserted)||0).toLocaleString()+' rows were committed successfully.</p><p>Release '+esc(result.release_key||'created')+' is awaiting publish. This step does not publish it automatically.</p></div>';
    foot.innerHTML='<button class="btn primary" onclick="closeModal();load()">Close</button>';
    toast('Commit completed; release is awaiting publish','ok');await load();
  }catch(e){
    postFinished=true;polling=false;await pollTask;
    let status='';
    try{const current=await api('/admin/api/imports/'+id);status=String((current.job||current).status||'').toUpperCase()}catch(_){}
    if(lastProgress&&String(lastProgress.status||'').toUpperCase()==='COMPLETED'){
      body.innerHTML='<div class="notice"><b>Database commit completed.</b><p>'+(Number(lastProgress.processed)||0).toLocaleString()+' staged rows processed.</p><p>The release may still need to be published.</p></div>';
      foot.innerHTML='<button class="btn primary" onclick="closeModal();load()">Close</button>';
      toast('Commit completed; refreshing review list','ok');await load();
    }else{
      body.insertAdjacentHTML('beforeend','<div class="issue" style="margin-top:12px"><b>Commit did not complete.</b><br>'+esc(e.message||'Unknown error')+(status==='FAILED'?'<br>The transaction was rolled back.':'')+'</div>');
      foot.innerHTML='<button class="btn secondary" onclick="closeModal()">Close</button><button class="btn primary" onclick="openReview('+id+')">Retry review</button>';
      toast(e.message||'Commit failed','err');await load();
    }
  }
}
async function reject(id){const reason=prompt('Rejection reason (required):');if(!reason)return;try{await api('/admin/api/imports/'+id+'/reject',{method:'POST',headers:csrfHeaders({'Content-Type':'application/json'}),body:JSON.stringify({reason})});toast('Import quarantined','ok');closeModal();load()}catch(e){toast(e.message,'err')}}
window.refreshAdminData=load;window.__cetAdminRunPoll(load);setInterval(()=>window.__cetAdminRunPoll(load),15000);
</script>'''
    return _shell('Review Center','review',body,js)


def releases_page(active: str = 'releases', title: str = 'Releases') -> str:
    body='''<div class="title"><div><h1>Releases</h1><p>Build, verify, publish and roll back production data releases.</p></div><div class="live"><span class="dot"></span>Live state</div></div><div class="grid4"><div class="card metric"><div class="label">Total Releases</div><div class="value" id="total">0</div></div><div class="card metric"><div class="label">Published</div><div class="value" id="published">0</div></div><div class="card metric"><div class="label">Ready to Publish</div><div class="value" id="ready">0</div></div><div class="card metric"><div class="label">Latest Status</div><div class="value" id="latest" style="font-size:18px">—</div></div></div><div class="notice" style="margin-top:14px"><b>Why two steps?</b> Commit writes the approved records into the production database and creates a release. <b>Publish &amp; Verify</b> then builds the runtime data, switches the public site to it, and verifies the result. A release marked <b>DB COMMITTED • AWAITING PUBLISH</b> is not live yet.</div><div class="card panel" style="margin-top:14px"><div class="toolbar"><h2>Release History</h2><button class="btn secondary" onclick="window.refreshAdminData()">↻ Refresh</button></div><div class="tablewrap"><table class="table"><thead><tr><th>Release</th><th>Source Job</th><th>Status</th><th>Created</th><th>Published</th><th>Actions</th></tr></thead><tbody id="list"></tbody></table></div></div>'''
    js=_common_js()+r'''<script>
async function load(){try{const d=await api('/admin/api/releases');document.querySelector('#total').textContent=d.length;document.querySelector('#published').textContent=d.filter(x=>x.status==='PUBLISHED').length;document.querySelector('#ready').textContent=d.filter(x=>x.status==='COMMITTED').length;document.querySelector('#latest').textContent=d[0]?.status||'—';document.querySelector('#list').innerHTML=d.map(x=>`<tr><td><b>${esc(x.release_key)}</b><div class="small muted">#${x.id}</div></td><td>${esc(x.source_job_id)}</td><td>${badge(x.status)}</td><td>${fmtTime(x.created_at)}</td><td>${fmtTime(x.published_at)}</td><td>${x.status==='COMMITTED'?`<button class="btn primary" onclick="publish(${x.id})">Publish & Verify</button> <button class="btn dangerbtn" onclick="rollback(${x.id})">Revoke & Delete</button>`:x.status==='PUBLISHED'?`<button class="btn dangerbtn" onclick="rollback(${x.id})">Revoke & Delete</button>`:x.status==='ROLLED_BACK'?`<button class="btn dangerbtn" onclick="purge(${x.id})">Delete Permanently</button>`:'<span class="muted small">No action</span>'}</td></tr>`).join('')||'<tr><td colspan="6" class="empty">No releases yet.</td></tr>'}catch(e){toast(e.message,'err')}}
async function publish(id){try{await api('/admin/api/releases/'+id+'/publish',{method:'POST',headers:csrfHeaders()});toast('Release published successfully','ok');load()}catch(e){toast(e.message,'err')}}
async function rollback(id){const reason=prompt('Revoke reason (required):');if(!reason)return;try{await api('/admin/api/releases/'+id+'/rollback',{method:'POST',headers:csrfHeaders({'Content-Type':'application/json'}),body:JSON.stringify({reason})});toast('Release revoked and production data deleted','ok');load()}catch(e){toast(e.message,'err')}} async function purge(id){try{await api('/admin/api/releases/'+id,{method:'DELETE',headers:csrfHeaders()});toast('Release and source import permanently deleted','ok');load()}catch(e){toast(e.message,'err')}}window.__cetAdminRunPoll(load);setInterval(()=>window.__cetAdminRunPoll(load),15000);
</script>'''
    body=body.replace('<h1>Releases</h1>', '<h1>'+escape(title)+'</h1>')
    if active == 'rollback':
        body=body.replace('Build, verify, publish and roll back production data releases.', 'Review production releases and manage rollback actions.')
        body=body.replace('Release History', 'Rollback & Release History')
    return _shell(title,active,body,js)


def derived_data() -> str:
    body='''<div class="title"><div><h1>CET Data Calculator</h1><p>Manually calculate and store the precomputed data used by the public college drawer.</p></div><div class="live"><span class="dot"></span>Admin controlled</div></div>
<div class="pagegrid"><div class="card panel"><div class="toolbar"><h2>Build derived data</h2><span class="muted small">No automatic rebuilds</span></div>
<div class="notice">The source-of-truth tables remain untouched. This job only rebuilds the small runtime tables used by <b>graph/trend points, college category/quota options, and seat matrix</b>.</div>
<div class="filters" style="margin-top:14px"><select id="course" class="select"><option value="">All courses in production DB</option></select><button id="buildBtn" class="btn primary" onclick="startBuild()">▶ Calculate & Store</button></div>
<div class="notice" style="margin-top:12px">Run this when you are comfortable with the server load. While it runs, the public site continues using the last successfully built derived dataset.</div>
<div id="buildProgress" class="notice" style="margin-top:12px;display:none"><div style="display:flex;justify-content:space-between;gap:12px"><b id="progressTitle">Calculating…</b><span id="progressPct">0%</span></div><div style="height:4px;background:#D8CFBC;border-radius:99px;overflow:hidden;margin-top:6px"><div id="progressBar" style="height:100%;width:0%;background:#11120D;transition:width .35s"></div></div><div id="progressMessage" class="small muted" style="margin-top:7px">Waiting for server…</div></div>
<div style="margin-top:18px"><div class="toolbar"><h2>Latest build</h2><span id="latestStatus" class="muted small">Loading…</span></div><div id="latest" class="notice">Loading build status…</div></div></div>
<div class="card panel"><div class="toolbar"><h2>What gets calculated</h2></div><div class="timeline"><div class="event"><div class="eventdot"></div><div><h4>Trend / graph points</h4><p>Per college, program, category, quota, year and CAP round.</p></div></div><div class="event"><div class="eventdot"></div><div><h4>Category & quota options</h4><p>Only combinations actually present for that particular college are stored.</p></div></div><div class="event"><div class="eventdot"></div><div><h4>Seat matrix</h4><p>Latest available seat matrix is reduced to the rows the drawer needs.</p></div></div><div class="event"><div class="eventdot"></div><div><h4>Public requests</h4><p>Fast indexed reads only. No heavy aggregation happens when candidates open Slide 2.</p></div></div></div></div></div>
<div class="card panel" style="margin-top:14px"><div class="toolbar"><h2>Build history</h2><button class="btn secondary" onclick="window.refreshAdminData()">↻ Refresh</button></div><div class="tablewrap"><table class="table"><thead><tr><th>ID</th><th>Course</th><th>Status</th><th>Progress</th><th>Message</th><th>Started</th><th>Finished</th><th>Actions</th></tr></thead><tbody id="history"></tbody></table></div></div>'''
    js=_common_js()+r'''<script>
let jobs=[];
const activeStates=['QUEUED','RUNNING'];
const terminalStates=['COMPLETED','FAILED','CANCELLED'];
function actionButtons(j){
  const s=String(j.status||'').toUpperCase();
  if(activeStates.includes(s)) return '<span class="small muted">Running…</span>';
  let out='';
  if(s==='FAILED'||s==='CANCELLED') out+='<button class="btn success" style="padding:6px 9px" onclick="retryBuild('+j.id+',this)">↻ Retry</button>';
  if(terminalStates.includes(s)) out+='<button class="trashbtn" title="Delete build history" aria-label="Delete build history" onclick="deleteBuild('+j.id+',this)">🗑</button>';
  return out||'<span class="small muted">—</span>';
}
async function load(){
  try{
    const d=await api('/admin/api/derived-data/status');jobs=d.jobs||[];
    const sel=document.querySelector('#course'),current=sel.value;
    sel.innerHTML='<option value="">All courses in production DB</option>'+d.courses.map(c=>'<option value="'+esc(c)+'">'+esc(c)+'</option>').join('');
    if([...sel.options].some(o=>o.value===current))sel.value=current;
    const j=jobs[0],box=document.querySelector('#buildProgress');
    document.querySelector('#latestStatus').textContent=j?(j.status+' · '+j.progress+'%'):'No build yet';
    if(j){
      const pct=Math.max(0,Math.min(100,Number(j.progress)||0)),running=activeStates.includes(String(j.status).toUpperCase());
      box.style.display=running?'block':'none';document.querySelector('#progressTitle').textContent=running?'Calculating CET Data Calculator…':j.status;
      document.querySelector('#progressPct').textContent=Math.round(pct)+'%';document.querySelector('#progressBar').style.width=pct+'%';document.querySelector('#progressMessage').textContent=j.message||'';
      document.querySelector('#latest').innerHTML='<b>Build #'+j.id+'</b> · '+badge(j.status)+'<div style="margin-top:8px">'+esc(j.message||'—')+'</div>';
    }else{box.style.display='none';document.querySelector('#latest').textContent='No derived dataset has been built yet.'}
    const active=jobs.some(x=>activeStates.includes(String(x.status).toUpperCase()));document.querySelector('#buildBtn').disabled=active;
    document.querySelector('#history').innerHTML=jobs.map(x=>'<tr><td>#'+x.id+'</td><td>'+esc(x.course_family||'ALL')+'</td><td>'+badge(x.status)+'</td><td>'+esc(x.progress)+'%</td><td>'+esc(x.message||'—')+'</td><td>'+fmtTime(x.started_at)+'</td><td>'+fmtTime(x.finished_at)+'</td><td><span class="rowactions">'+actionButtons(x)+'</span></td></tr>').join('')||'<tr><td colspan="8" class="empty">No builds yet.</td></tr>';
  }catch(e){toast(e.message,'err')}
}
async function startBuild(){
  const course=document.querySelector('#course').value;

  try{document.querySelector('#buildBtn').disabled=true;const form=new FormData();if(course)form.append('course',course);await api('/admin/api/derived-data/build',{method:'POST',headers:csrfHeaders(),body:form});toast('Derived-data build started','ok');await load()}catch(e){toast(e.message,'err');await load()}
}
async function retryBuild(id,btn){
  if(btn.disabled)return;
  btn.disabled=true;const old=btn.textContent;btn.textContent='Retrying…';
  try{await api('/admin/api/derived-data/retry/'+id,{method:'POST',headers:csrfHeaders()});toast('Retry started','ok');await load()}catch(e){btn.disabled=false;btn.textContent=old;toast(e.message,'err')}
}
async function deleteBuild(id,btn){
  if(btn.disabled)return;
  btn.disabled=true;
  try{await api('/admin/api/derived-data/'+id,{method:'DELETE',headers:csrfHeaders()});toast('Build history deleted','ok');await load()}catch(e){btn.disabled=false;toast(e.message,'err')}
}
window.refreshAdminData=load;window.__cetAdminRunPoll(load);setInterval(()=>window.__cetAdminRunPoll(load),15000);
</script>'''
    return _shell('CET Data Calculator','derived',body,js)


def health_page() -> str:
    body='''<div class="title"><div><h1>Data Health</h1><p>Live checks for the application, database, published site and production datasets.</p></div><div class="live"><span class="dot"></span>Continuous checks</div></div><div class="card panel" id="overall" style="margin-bottom:14px">Checking health…</div><div class="grid4" id="metrics"></div><div class="pagegrid" style="margin-top:14px"><div class="card panel"><div class="toolbar"><h2>Production Data</h2><span class="muted small" id="refreshAt">—</span></div><div class="tablewrap"><table class="table"><thead><tr><th>Dataset</th><th>Rows</th><th>State</th></tr></thead><tbody id="counts"></tbody></table></div></div><div class="card panel"><div class="toolbar"><h2>Detected Issues</h2></div><div id="issues"></div><h2 style="margin-top:20px">Latest Release</h2><div id="release" class="notice">—</div></div></div>'''
    js=_common_js()+r'''<script>
async function load(){try{const d=await api('/admin/api/health');const c=d.counts||{},r=d.runtime||{},ok=!!d.ok&&!!r.site_exists;document.querySelector('#overall').innerHTML=`<div style="display:flex;align-items:center;justify-content:space-between;gap:12px"><div><b style="font-size:18px">${ok?'System healthy':'Attention required'}</b><div class="small muted">${ok?'Core runtime checks are passing.':'One or more checks need attention.'}</div></div><span class="status ${ok?'green':'red'}">${ok?'HEALTHY':'CHECK'}</span></div>`;const names=[['Institutes','institutes'],['Programs','programs'],['Cutoffs','cutoffs'],['Seats','seats']];document.querySelector('#metrics').innerHTML=names.map(([n,k])=>`<div class="card metric"><div class="label">${n}</div><div class="value">${Number(c[k]||0).toLocaleString()}</div></div>`).join('');document.querySelector('#counts').innerHTML=Object.entries(c).map(([k,v])=>`<tr><td>${esc(k.replaceAll('_',' '))}</td><td><b>${Number(v).toLocaleString()}</b></td><td>${Number(v)>0||['audit_log','import_jobs'].includes(k)?badge('HEALTHY'):badge('EMPTY')}</td></tr>`).join('');const issues=[];if(!r.site_exists)issues.push('Published site directory is missing.');if(!r.latest_release)issues.push('No release has been created yet.');if((c.programs||0)===0)issues.push('Programs table is empty.');document.querySelector('#issues').innerHTML=issues.length?issues.map(x=>`<div class="issue">${esc(x)}</div>`).join(''):'<div class="issue good">No obvious data-health issues detected.</div>';document.querySelector('#release').innerHTML=r.latest_release?`<b>${esc(r.latest_release.release_key)}</b><br>${badge(r.latest_release.status)}<div class="small muted" style="margin-top:6px">Published: ${fmtTime(r.latest_release.published_at)} · Verified: ${fmtTime(r.latest_release.verified_at)}</div>`:'No releases yet';document.querySelector('#refreshAt').textContent='Updated '+new Date().toLocaleTimeString()}catch(e){toast(e.message,'err')}}window.refreshAdminData=load;window.__cetAdminRunPoll(load);setInterval(()=>window.__cetAdminRunPoll(load),15000);
</script>'''
    return _shell('Data Health','health',body,js)


def audit_page(rows) -> str:
    data=json.dumps(rows,ensure_ascii=False,default=str).replace('</','<\\/')
    body='''<div class="title"><div><h1>Audit Log</h1><p>Trace administrative actions, imports, approvals, releases and rollbacks.</p></div><div class="live">''' + '<span class="dot"></span>Last 200 events</div></div>' + '''<div class="card panel"><div class="toolbar"><div class="filters"><input id="q" class="input" placeholder="Search user, action, entity, reason…"></div><span class="muted small" id="count"></span></div><div class="tablewrap"><table class="table"><thead><tr><th>Time</th><th>User</th><th>Action</th><th>Entity</th><th>Reason</th></tr></thead><tbody id="list"></tbody></table></div></div>'''
    js=_common_js()+f'''<script>const rows={data};const q=document.querySelector('#q');q.addEventListener('input',render);function render(){{const t=q.value.toLowerCase();const d=rows.filter(x=>!t||Object.values(x).some(v=>String(v??'').toLowerCase().includes(t)));document.querySelector('#count').textContent=d.length+' event(s)';document.querySelector('#list').innerHTML=d.map(x=>`<tr><td>${{fmtTime(x.created_at)}}</td><td>${{esc(x.username||'system')}}</td><td>${{badge(x.action)}}</td><td>${{esc(x.entity_type)}} #${{esc(x.entity_id)}}</td><td>${{esc(x.reason||'—')}}</td></tr>`).join('')||'<tr><td colspan="5" class="empty">No audit events match.</td></tr>'}}render();</script>'''
    return _shell('Audit Log','audit',body,js)


def feedback_page(rows) -> str:
    data=json.dumps(rows,ensure_ascii=False,default=str).replace('</','<\\/')
    body='<div class="title"><div><h1>Public Feedback</h1><p>Review feedback submitted from the candidate-facing website.</p></div><div class="live"><span class="dot"></span>Live inbox</div></div><div class="grid4"><div class="card metric"><div class="label">Total</div><div class="value" id="total">0</div></div><div class="card metric"><div class="label">New</div><div class="value" id="newCount">0</div></div><div class="card metric"><div class="label">Reviewed</div><div class="value" id="reviewed">0</div></div><div class="card metric"><div class="label">Resolved</div><div class="value" id="resolved">0</div></div></div><div class="card panel" style="margin-top:14px"><div class="toolbar"><div class="filters"><input id="q" class="input" placeholder="Search feedback…"><select id="status" class="select"><option value="">All statuses</option><option>NEW</option><option>REVIEWED</option><option>RESOLVED</option><option>SPAM</option></select></div><button class="btn secondary" onclick="window.refreshAdminData()">↻ Refresh</button></div><div class="tablewrap"><table class="table"><thead><tr><th>Time</th><th>Rating</th><th>Feedback</th><th>Page</th><th>Status</th><th>Action</th></tr></thead><tbody id="list"></tbody></table></div></div>'
    js=_common_js()+f'''<script>
let rows={data};
const q=document.querySelector('#q'), st=document.querySelector('#status');
function render(){{const term=q.value.toLowerCase(),filter=st.value;const d=rows.filter(x=>(!filter||x.status===filter)&&(!term||String(x.message+' '+x.page).toLowerCase().includes(term)));document.querySelector('#total').textContent=rows.length;document.querySelector('#newCount').textContent=rows.filter(x=>x.status==='NEW').length;document.querySelector('#reviewed').textContent=rows.filter(x=>x.status==='REVIEWED').length;document.querySelector('#resolved').textContent=rows.filter(x=>x.status==='RESOLVED').length;document.querySelector('#list').innerHTML=d.map(x=>`<tr><td>${{fmtTime(x.created_at)}}</td><td>${{x.rating?('★'.repeat(x.rating)+'☆'.repeat(5-x.rating)):'—'}}</td><td style="max-width:520px;white-space:normal"><b>${{esc(x.message)}}</b></td><td>${{esc(x.page||'/')}}</td><td>${{badge(x.status)}}</td><td><select class="select" onchange="setStatus(${{x.id}},this.value)">${{['NEW','REVIEWED','RESOLVED','SPAM'].map(v=>`<option ${{v===x.status?'selected':''}}>${{v}}</option>`).join('')}}</select></td></tr>`).join('')||'<tr><td colspan="6" class="empty">No feedback matches.</td></tr>'}}
q.addEventListener('input',render);st.addEventListener('change',render);
async function load(){{try{{rows=await api('/admin/api/feedback');render()}}catch(e){{toast(e.message,'err')}}}}
async function setStatus(id,status){{try{{await api('/admin/api/feedback/'+id+'/status',{{method:'POST',headers:csrfHeaders({{'Content-Type':'application/json'}}),body:JSON.stringify({{status}})}});toast('Feedback updated','ok');await load()}}catch(e){{toast(e.message,'err');load()}}}}
render();window.refreshAdminData=load;setInterval(()=>window.__cetAdminRunPoll(load),15000);
</script>'''
    return _shell('Public Feedback','feedback',body,js)

def live_processing(job_id: int) -> str:
    body=f'''<div class="title"><div><h1>Live Processing</h1><p>Import #{job_id} · live server-side processing status.</p></div><a class="btn secondary" href="/admin/review">← Review Center</a></div>
<div class="pagegrid"><div class="card panel"><div class="toolbar"><h2 id="jobTitle">Loading…</h2><span id="jobStatus">—</span></div>
<div id="meta" class="notice">Loading import metadata…</div>
<div id="currentStep" class="notice" style="margin-top:10px;background:#FFFBF4;border-color:#D8CFBC">Current step: checking…</div>
<div style="margin-top:18px"><div class="toolbar"><b>Overall progress</b><span class="muted small" id="progressText">0%</span></div><div style="height:10px;background:#D8CFBC;border-radius:999px;overflow:hidden"><div id="progress" style="height:100%;width:0;background:linear-gradient(90deg,#11120D,#11120D);transition:width .35s"></div></div></div>
<div id="steps" style="display:grid;gap:8px;margin-top:20px"></div>
<div class="timeline" id="events" style="margin-top:22px"></div></div>
<div class="card panel"><h2>Controls</h2><p class="small muted">Processing runs in the background. This page refreshes the actual job status from the server every second.</p><div id="actions"></div><div id="controlNote" class="notice" style="margin-top:10px">Checking status…</div></div></div>'''
    js=_common_js()+f'''<script>const terminal=['COMPLETED','FAILED','CANCELLED','QUARANTINED','ROLLED_BACK'];async function load(){{try{{const d=await api('/admin/api/imports/{job_id}'),j=d.job;document.querySelector('#jobTitle').textContent=j.job_key+' · '+j.original_filename;document.querySelector('#jobStatus').innerHTML=badge(j.status);document.querySelector('#currentStep').textContent='Current step: '+String(j.status||'').replaceAll('_',' ');document.querySelector('#meta').innerHTML=`${{esc(j.data_type||'')}} · ${{esc(j.course_family||'')}} · ${{esc(j.year||'')}} · ${{esc(j.round||'')}}`;const ev=d.events||[];const last=ev[ev.length-1],pct=last?.progress??(j.status==='REVIEW_REQUIRED'?100:0);document.querySelector('#progress').style.width=Math.max(0,Math.min(100,pct))+'%';document.querySelector('#progressText').textContent=Math.round(pct)+'%';document.querySelector('#events').innerHTML=ev.slice().reverse().map((x,i)=>`<div class="event ${{i===0&&!terminal.includes(j.status)?'active':''}}"><div class="eventdot"></div><div><h4>${{esc(x.event_type||'Event')}} · ${{esc(x.progress??'')}}%</h4><p>${{esc(x.message)}} · ${{fmtTime(x.created_at)}}</p></div></div>`).join('')||'<div class="empty">No events yet.</div>';const actions=document.querySelector('#actions');actions.innerHTML=['RECEIVED','IDENTIFIED','REVIEW_REQUIRED','STAGED','FAILED','CANCELLED','QUARANTINED'].includes(j.status)?'<button class="btn dangerbtn" onclick="removeImport()">Delete import</button>':'';if(j.status==='STAGED')actions.innerHTML+='<button class="btn success" style="margin-left:8px" onclick="approve()">Approve & Commit</button>';if(j.status==='REVIEW_REQUIRED')actions.innerHTML+='<a class="btn primary" style="margin-left:8px" href="/admin/review">Open Review Center</a>';document.querySelector('#controlNote').textContent=terminal.includes(j.status)?'Processing has finished.':'Live status will refresh automatically.';if(!terminal.includes(j.status))setTimeout(()=>window.__cetAdminRunPoll(load),3000)}}catch(e){{toast(e.message,'err')}}}}async function removeImport(){{if(!confirm('Delete this import? The uploaded PDF and all uncommitted import data will be removed.'))return;try{{await api('/admin/api/imports/{job_id}',{{method:'DELETE',headers:csrfHeaders()}});toast('Import deleted','ok');location.href='/admin'}}catch(e){{toast(e.message,'err')}}}}async function approve(){{const notes=prompt('Approval note (optional):','');if(notes===null)return;try{{await api('/admin/api/imports/{job_id}/approve',{{method:'POST',headers:csrfHeaders({{'Content-Type':'application/json'}}),body:JSON.stringify({{notes}})}});toast('Import approved and committed','ok');load()}}catch(e){{toast(e.message,'err')}}}}load();</script>'''
    return _shell('Live Processing','processing',body,js)


def resolver_page(rows) -> str:
    data=json.dumps(rows,ensure_ascii=False,default=str).replace('</','<\\/')
    server_rows=[]
    for x in rows:
        code=escape(str(x.get('institution_code') or ''))
        name=escape(str(x.get('institution_name') or ''))
        city=escape(str(x.get('city') or '—'))
        website=str(x.get('website') or '').strip()
        website_html=(f'<a href="{escape(website, quote=True)}" target="_blank" rel="noopener">{escape(website)}</a>' if website else '—')
        status=escape(str(x.get('status') or 'PENDING'))
        source=escape(str(x.get('source') or '—'))
        checked=escape(str(x.get('last_checked_at') or x.get('updated_at') or '—'))
        action=(f'<span class="small muted">Verified</span>' if status=='VERIFIED' else
                (f'<button class="btn success" style="padding:6px 9px" data-code="{code}" data-name="{name}" data-website="{escape(website, quote=True)}" onclick="manualVerify(this)">✓ Verify</button>' if website else '<span class="small muted">No URL</span>'))
        server_rows.append(f'<tr><td><input type="checkbox" class="pick" value="{code}"></td><td><b>{code}</b></td><td>{name}</td><td>{city}</td><td>{website_html}</td><td><span class="status gray">{status}</span></td><td>{source}</td><td>{checked}</td><td>{action}</td></tr>')
    server_table=''.join(server_rows)
    body='''<div class="title"><div><h1>College Website Resolver</h1><p>Resolve and permanently verify official college websites. Course data is intentionally ignored.</p></div><div class="live"><span class="dot"></span>Resolver</div></div><div class="grid4"><div class="card metric"><div class="label">Total Colleges</div><div class="value" id="total">{len(rows)}</div></div><div class="card metric"><div class="label">Verified</div><div class="value" id="verified">0</div></div><div class="card metric"><div class="label">Needs Review</div><div class="value" id="review">0</div></div><div class="card metric"><div class="label">Pending</div><div class="value" id="pending">0</div></div></div><div class="card panel" style="margin-top:14px"><div class="toolbar"><div class="filters"><input id="q" class="input" placeholder="Search college name or ID…"><select id="status" class="select"><option value="">All statuses</option><option>PENDING</option><option value="CANDIDATE">UNVERIFIED</option><option>VERIFIED</option><option>NEEDS_REVIEW</option><option>FAILED</option></select></div><div class="filters"><button class="btn secondary" onclick="seed()">↻ Sync CAP institutes</button></div></div><div class="notice" style="margin-bottom:12px">The resolver is scoped to CAP institutes. Existing website and city data is checked first; only unresolved colleges are sent to Gemini + Google Search. PDF extraction and AI website resolution are separate. AI resolution runs one college at a time only when the server is idle. Unverified/Pending entries are never treated as verified.</div><div id="resolverProgress" class="notice" style="margin-bottom:12px;display:none"><div style="display:flex;justify-content:space-between;gap:12px"><b id="resolverProgressTitle">AI resolver idle</b><span id="resolverProgressCount" class="small muted">0 / 0</span></div><div style="height:9px;background:#e8edf3;border-radius:99px;overflow:hidden;margin-top:9px"><div id="resolverProgressBar" style="height:100%;width:0%;background:#11120D;transition:width .25s"></div></div><div id="resolverProgressCollege" class="small muted" style="margin-top:7px">Waiting to start.</div></div><div class="tablewrap"><table class="table"><thead><tr><th><input type="checkbox" id="all"></th><th>ID</th><th>College</th><th>City</th><th>Website</th><th>Status</th><th>Source</th><th>Checked</th><th>Action</th></tr></thead><tbody id="list"></tbody></table></div></div><div class="modalback" id="resolverModal"><div class="modal"><div class="modalhead"><b id="modalTitle">Resolver result</b><button class="close" onclick="closeModal()">×</button></div><div class="modalbody" id="modalBody"></div><div class="modalfoot"><button class="btn secondary" onclick="closeModal()">Close</button></div></div></div>'''
    js=_common_js()+f'''<script>let rows={data};const q=document.querySelector('#q'),st=document.querySelector('#status');function render(){{const t=q.value.toLowerCase(),f=st.value,d=rows.filter(x=>(!f||x.status===f)&&(!t||String(x.institution_code+' '+x.institution_name+' '+(x.city||'')).toLowerCase().includes(t)));for(const [id,v] of [['total',rows.length],['verified',rows.filter(x=>x.status==='VERIFIED').length],['review',rows.filter(x=>x.status==='NEEDS_REVIEW').length],['pending',rows.filter(x=>x.status==='PENDING').length]])document.querySelector('#'+id).textContent=v;function resolverAction(x){{if(!x.website)return '<span class="small muted">No URL</span>';const verify=x.status==='VERIFIED'?'<span class="small muted">Verified</span>':'<button class="btn success" style="padding:6px 9px" data-code="'+esc(x.institution_code)+'" data-name="'+esc(x.institution_name)+'" data-website="'+esc(x.website||'')+'" onclick="manualVerify(this)">✓ Verify</button>';const research='<button class="btn ghost" style="padding:6px 9px" data-code="'+esc(x.institution_code)+'" data-name="'+esc(x.institution_name)+'" data-website="'+esc(x.website||'')+'" onclick="researchAgain(this)">↻ Wrong website</button>';return '<span class="rowactions">'+verify+research+'</span>'}}document.querySelector('#list').innerHTML=d.map(x=>'<tr><td><input type="checkbox" class="pick" value="'+esc(x.institution_code)+'"></td><td><b>'+esc(x.institution_code)+'</b></td><td>'+esc(x.institution_name)+'</td><td>'+esc(x.city||'—')+'</td><td>'+(x.website?'<a href="'+esc(x.website)+'" target="_blank" rel="noopener">'+esc(x.website)+'</a>':'—')+'</td><td>'+badge(x.status)+'</td><td>'+esc(x.source||'—')+'</td><td>'+fmtTime(x.last_checked_at||x.updated_at)+'</td><td>'+resolverAction(x)+'</td></tr>').join('')||'<tr><td colspan="9" class="empty">No colleges match.</td></tr>'}}
q.addEventListener('input',render);st.addEventListener('change',render);document.querySelector('#all').onchange=e=>document.querySelectorAll('.pick').forEach(x=>x.checked=e.target.checked);async function load(){{try{{rows=await api('/admin/api/resolver');render()}}catch(e){{toast(e.message,'err')}}}}async function seed(){{const btn=[...document.querySelectorAll('.btn')].find(x=>x.textContent.includes('Sync CAP institutes'));if(btn?.disabled)return;const old=btn?.textContent;if(btn){{btn.disabled=true;btn.textContent='↻ Syncing…'}}try{{const r=await api('/admin/api/resolver/seed',{{method:'POST',headers:csrfHeaders()}});await load();toast('CAP institutes synchronized: '+Number(r.count||0)+' records checked','ok')}}catch(e){{toast('CAP sync failed: '+e.message,'err')}}finally{{if(btn){{btn.disabled=false;btn.textContent=old||'↻ Sync CAP institutes'}}}}}}async function findSelected(){{const ids=[...document.querySelectorAll('.pick:checked')].map(x=>x.value);if(!ids.length)return toast('Select at least one college','err');document.querySelector('#modalTitle').textContent='Resolving '+ids.length+' college(s)…';document.querySelector('#modalBody').innerHTML='<div class="notice">Existing candidates are verified first. Gemini is only used for unresolved colleges.</div>';document.querySelector('#resolverModal').classList.add('show');try{{const r=await api('/admin/api/resolver/find',{{method:'POST',headers:csrfHeaders({{'Content-Type':'application/json'}}),body:JSON.stringify({{ids}})}});document.querySelector('#modalTitle').textContent='Resolver results';document.querySelector('#modalBody').innerHTML=r.results.map(x=>`<div class="notice" style="margin-bottom:8px"><b>${{esc(x.institution_name)}}</b><br>${{x.website?`<a href="${{esc(x.website)}}" target="_blank" rel="noopener">${{esc(x.website)}}</a>`:'No URL found'}}<br><span class="small muted">${{esc(x.status)}} · ${{esc(x.note||'')}}</span></div>`).join('');await load()}}catch(e){{document.querySelector('#modalBody').innerHTML='<div class="issue">'+esc(e.message)+'</div>'}}}}async function startResolver(){{if(window.resolverRunning)return;window.resolverRunning=true;const box=document.querySelector('#resolverProgress'),title=document.querySelector('#resolverProgressTitle'),count=document.querySelector('#resolverProgressCount'),bar=document.querySelector('#resolverProgressBar'),college=document.querySelector('#resolverProgressCollege');box.style.display='block';let total=rows.filter(x=>x.status!=='VERIFIED').length,done=0;try{{while(resolverRunning){{const r=await api('/admin/api/resolver/next',{{method:'POST',headers:csrfHeaders()}});if(r.busy){{title.textContent='AI resolver paused — server busy';college.textContent=r.reason+'; waiting safely…';await new Promise(x=>setTimeout(x,3000));continue}}if(r.current){{college.textContent='AI working on: '+r.current.institution_name+' ('+r.current.institution_code+')';}}done+=Number(r.processed||0);const remaining=Number(r.remaining||0);total=Math.max(total,done+remaining);const pct=total?Math.min(100,(done/total)*100):100;bar.style.width=pct+'%';count.textContent=done+' / '+total;if(!remaining){{title.textContent='AI resolver complete';college.textContent='All queued colleges have been processed. Unverified/Pending entries remain unverified.';break}}title.textContent='AI resolver running';await load();await new Promise(x=>setTimeout(x,500))}}}}catch(e){{title.textContent='AI resolver stopped';college.textContent=e.message;toast(e.message,'err')}}finally{{window.resolverRunning=false;await load()}}}}async function researchAgain(btn){{if(btn.disabled)return;btn.disabled=true;const oldText=btn.textContent;btn.textContent='Researching…';try{{const r=await api('/admin/api/resolver/find',{{method:'POST',headers:csrfHeaders({{'Content-Type':'application/json'}}),body:JSON.stringify({{ids:[btn.dataset.code],force_research:true,exclude_website:btn.dataset.website}})}});const x=r.results?.[0];if(!x)throw new Error('No resolver result returned');toast(x.status==='VERIFIED'?'New website verified':'New website researched — review the result','ok');await load()}}catch(e){{btn.disabled=false;btn.textContent=oldText;toast(e.message,'err')}}}}
async function manualVerify(btn){{if(btn.disabled)return;btn.disabled=true;const oldText=btn.textContent;btn.textContent='Verifying…';try{{await api('/admin/api/resolver/verify',{{method:'POST',headers:csrfHeaders({{'Content-Type':'application/json'}}),body:JSON.stringify({{institution_code:btn.dataset.code,institution_name:btn.dataset.name,website:btn.dataset.website}})}});toast('Website marked verified','ok');await load()}}catch(e){{btn.disabled=false;btn.textContent=oldText;toast(e.message,'err')}}}}
function closeModal(){{document.querySelector('#resolverModal').classList.remove('show')}}render();setInterval(()=>window.__cetAdminRunPoll(load),15000);</script>'''
    body=body.replace('id="total">{len(rows)}','id="total">'+str(len(rows)))
    body=body.replace('<tbody id="list"></tbody>', '<tbody id="list">'+server_table+'</tbody>')
    return _shell('College Website Resolver','resolver',body,js)
