import { useState, useMemo } from "react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar, Cell, ReferenceLine, Line, LineChart, ScatterChart, Scatter, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Legend } from "recharts";
const T={bg:"#F8F9FB",surface:"#FFF",sAlt:"#F3F5F7",border:"#E4E8ED",bLt:"#EEF1F4",text:"#141B2B",tS:"#4E5D73",tM:"#8B99AD",accent:"#1D4ED8",aLt:"#EBF0FF",green:"#0A7B4F",gLt:"#E8F8F0",red:"#C8220D",rLt:"#FDF0EE",amber:"#A85D00",amLt:"#FFF7EB",purple:"#6B21A8",pLt:"#F3EEFF",cyan:"#0E7490"};
const M=`'IBM Plex Mono','Menlo',monospace`,S=`'Instrument Sans',sans-serif`,SE=`'Source Serif 4',serif`;
const pc=v=>v>0?T.green:v<0?T.red:T.tM,pp=v=>v>0?"+":"",fm=(n,d=2)=>n?.toLocaleString("en-US",{minimumFractionDigits:d,maximumFractionDigits:d})??"—",fK=n=>n>=1e6?`$${(n/1e6).toFixed(2)}M`:n>=1e3?`$${(n/1e3).toFixed(1)}K`:`$${n.toFixed(0)}`;
const PF={nav:1023847.52,cash:48291.33,pos:247,dayPct:0.38,weekPnL:-8291.44,weekPct:-0.81,monthPnL:21483.92,monthPct:2.14,ytdPnL:67291.33,ytdPct:7.03,aytdPct:9.57,maxDD:-8.3,beta:0.91,alpha:3.2,vol:14.8,sharpe:1.42,sortino:1.87};
const AYTD_CURVE=[{d:"Sep",pf:100,spy:100},{d:"Oct",pf:102.1,spy:101.4},{d:"Nov",pf:104.8,spy:103.6},{d:"Dec",pf:103.4,spy:102.8},{d:"Jan",pf:107.2,spy:105.8},{d:"Feb",pf:109.6,spy:107.1}];
const MAX_CURVE=[{d:"2024-09",pf:100,spy:100},{d:"2024-12",pf:103.2,spy:101.8},{d:"2025-03",pf:107.8,spy:105.1},{d:"2025-06",pf:110.4,spy:107.2},{d:"2025-09",pf:106.1,spy:103.8},{d:"2025-12",pf:111.8,spy:108.4},{d:"2026-02",pf:113.8,spy:110.2}];
const SECTORS=[{name:"Technology",weight:22.4,pos:41,bench:29.1,color:"#1D4ED8"},{name:"Healthcare",weight:15.1,pos:32,bench:13.2,color:"#0A7B4F"},{name:"Financials",weight:13.8,pos:28,bench:13.5,color:"#A85D00"},{name:"Consumer Disc.",weight:11.2,pos:24,bench:10.8,color:"#C8220D"},{name:"Industrials",weight:9.7,pos:21,bench:8.9,color:"#6B21A8"},{name:"Energy",weight:7.3,pos:18,bench:3.7,color:"#C2410C"},{name:"Comm. Services",weight:6.1,pos:16,bench:8.7,color:"#0E7490"},{name:"Materials",weight:5.2,pos:14,bench:2.5,color:"#65A30D"},{name:"Utilities",weight:4.1,pos:12,bench:2.4,color:"#A21CAF"},{name:"Real Estate",weight:3.0,pos:9,bench:2.3,color:"#BE185D"},{name:"Cons. Staples",weight:2.1,pos:8,bench:5.9,color:"#0D9488"}];
const TREE=[{s:"Technology",i:"Semiconductors",t:"NVDA",w:4.2,dc:1.2,wc:3.4},{s:"Technology",i:"Semiconductors",t:"AVGO",w:2.5,dc:2.3,wc:4.8},{s:"Technology",i:"Semiconductors",t:"AMAT",w:1.7,dc:1.5,wc:2.1},{s:"Technology",i:"Software",t:"MSFT",w:3.8,dc:0.3,wc:0.8},{s:"Technology",i:"Software",t:"CRM",w:1.8,dc:0.4,wc:1.2},{s:"Technology",i:"Software",t:"DDOG",w:0.9,dc:1.1,wc:2.8},{s:"Technology",i:"Cybersecurity",t:"PANW",w:1.1,dc:0.6,wc:1.9},{s:"Technology",i:"Solar",t:"ENPH",w:0.5,dc:-2.1,wc:-4.8},{s:"Healthcare",i:"Pharma",t:"LLY",w:3.5,dc:-0.8,wc:-1.4},{s:"Healthcare",i:"Pharma",t:"MRK",w:1.3,dc:0.2,wc:-0.6},{s:"Healthcare",i:"Managed Care",t:"UNH",w:2.3,dc:-0.2,wc:-1.8},{s:"Healthcare",i:"Life Sciences",t:"DHR",w:1.6,dc:-0.3,wc:0.4},{s:"Healthcare",i:"DTC Health",t:"HIMS",w:0.6,dc:3.2,wc:8.1},{s:"Financials",i:"Banks",t:"JPM",w:3.1,dc:0.5,wc:-0.4},{s:"Financials",i:"Payments",t:"MA",w:2.1,dc:0.1,wc:0.6},{s:"Financials",i:"Payments",t:"V",w:1.3,dc:0.3,wc:0.9},{s:"Financials",i:"Fintech",t:"SOFI",w:0.5,dc:1.8,wc:5.2},{s:"Consumer Disc.",i:"E-Commerce",t:"AMZN",w:2.9,dc:1.8,wc:2.4},{s:"Consumer Disc.",i:"Travel",t:"ABNB",w:0.8,dc:-1.2,wc:-3.1},{s:"Consumer Disc.",i:"Beverages",t:"CELH",w:0.4,dc:-0.4,wc:-2.8},{s:"Industrials",i:"Machinery",t:"CAT",w:1.9,dc:0.7,wc:1.1},{s:"Industrials",i:"Aerospace",t:"GE",w:1.5,dc:0.9,wc:2.2},{s:"Industrials",i:"Uniforms",t:"CTAS",w:0.8,dc:0.2,wc:0.4},{s:"Industrials",i:"Space",t:"RKLB",w:0.3,dc:4.1,wc:12.4},{s:"Energy",i:"Integrated",t:"XOM",w:2.7,dc:-1.1,wc:-3.2},{s:"Energy",i:"Services",t:"SLB",w:1.4,dc:-1.4,wc:-4.1},{s:"Comm. Services",i:"Internet",t:"GOOG",w:2.0,dc:0.5,wc:1.3},{s:"Materials",i:"Copper",t:"FCX",w:1.0,dc:-0.8,wc:-2.1},{s:"Utilities",i:"Renewables",t:"NEE",w:1.2,dc:0.1,wc:0.3}];
const MOV=[...TREE].sort((a,b)=>b.wc-a.wc);const TOP10=MOV.slice(0,10),BOT10=MOV.slice(-10).reverse();
const VAR_DIST=Array.from({length:40},(_,i)=>{const x=-6+i*0.35;return{ret:x.toFixed(1),freq:Math.round(Math.exp(-0.5*Math.pow((x-0.4)/1.8,2))*100),isVaR:x<=-3.2,isCVaR:x<=-4.5}});
const DD_DATA=[{date:"Jul",dd:0},{date:"Aug",dd:-2.1},{date:"Sep",dd:-0.8},{date:"Oct",dd:0},{date:"Nov",dd:-1.4},{date:"Dec",dd:-8.3},{date:"Jan",dd:-3.2},{date:"Feb",dd:-0.8}];
const CT=["NVDA","MSFT","LLY","JPM","AMZN","XOM","AVGO","UNH"],CP=[[1,.72,.18,.31,.65,-.12,.85,.14],[.72,1,.22,.38,.71,-.08,.68,.19],[.18,.22,1,.29,.15,.08,.12,.61],[.31,.38,.29,1,.34,.42,.28,.33],[.65,.71,.15,.34,1,-.05,.58,.11],[-.12,-.08,.08,.42,-.05,1,-.10,.06],[.85,.68,.12,.28,.58,-.10,1,.09],[.14,.19,.61,.33,.11,.06,.09,1]];
const CSN=["Tech","Health","Fin.","ConsD","Indust","Energy","Comm","Matl"],CSM=[[1,.35,.48,.72,.55,-.08,.68,.32],[.35,1,.28,.22,.31,.12,.24,.18],[.48,.28,1,.42,.58,.38,.34,.45],[.72,.22,.42,1,.48,-.02,.62,.28],[.55,.31,.58,.48,1,.28,.38,.62],[-.08,.12,.38,-.02,.28,1,.08,.42],[.68,.24,.34,.62,.38,.08,1,.22],[.32,.18,.45,.28,.62,.42,.22,1]];
const ROLL=[{p:"30d",sh:1.68,so:2.12,vo:12.4,be:0.88,dd:-2.1},{p:"90d",sh:1.42,so:1.87,vo:14.8,be:0.91,dd:-5.6},{p:"180d",sh:1.31,so:1.64,vo:15.9,be:0.93,dd:-8.3},{p:"1Y",sh:1.24,so:1.52,vo:16.2,be:0.94,dd:-8.3}];
const CLOSED=[{ticker:"META",exit:"2025-12-18",entry:"2025-03-10",pnl:22.4,pnlD:8420,days:283,reason:"Target hit",sector:"Technology",eP:482.30,xP:590.40},{ticker:"TSLA",exit:"2025-11-02",entry:"2025-06-15",pnl:-12.8,pnlD:-4210,days:140,reason:"Stop loss",sector:"Consumer Disc.",eP:248.10,xP:216.30},{ticker:"COST",exit:"2025-10-21",entry:"2025-01-08",pnl:18.7,pnlD:6890,days:286,reason:"Valuation stretch",sector:"Cons. Staples",eP:698.20,xP:828.80},{ticker:"AMD",exit:"2025-09-14",entry:"2025-04-22",pnl:31.2,pnlD:9130,days:145,reason:"Target hit",sector:"Technology",eP:148.40,xP:194.70},{ticker:"PFE",exit:"2025-08-30",entry:"2025-02-18",pnl:-8.4,pnlD:-2180,days:193,reason:"Thesis broken",sector:"Healthcare",eP:28.40,xP:26.02},{ticker:"NFLX",exit:"2025-12-01",entry:"2025-05-20",pnl:16.9,pnlD:5420,days:195,reason:"Target hit",sector:"Comm. Services",eP:648.20,xP:757.80},{ticker:"BA",exit:"2025-07-22",entry:"2025-03-01",pnl:-18.2,pnlD:-6340,days:143,reason:"Stop loss",sector:"Industrials",eP:192.40,xP:157.38},{ticker:"ORCL",exit:"2025-11-15",entry:"2025-06-01",pnl:9.8,pnlD:3120,days:167,reason:"Rebalance",sector:"Technology",eP:128.40,xP:140.98},{ticker:"SHOP",exit:"2025-10-05",entry:"2025-04-12",pnl:27.3,pnlD:7840,days:176,reason:"Target hit",sector:"Technology",eP:68.20,xP:86.82},{ticker:"INTC",exit:"2025-08-15",entry:"2025-05-10",pnl:-24.8,pnlD:-8420,days:97,reason:"Stop loss",sector:"Technology",eP:32.10,xP:24.14}];
const ALERTS=[{cat:"Position Size",sev:"high",msg:"NVDA at 4.2% — approaching 5% hard cap. Trim $8.2K to target 3.5%.",ticker:"NVDA",time:"Now",icon:"◆"},{cat:"Position Size",sev:"med",msg:"AVGO up 42.1% — weight drifted from 1.8% entry to 2.5%.",ticker:"AVGO",time:"Today",icon:"◆"},{cat:"Factor Breach",sev:"high",msg:"Momentum factor at +0.8σ — above 0.6σ threshold.",time:"2h ago",icon:"◇"},{cat:"Factor Breach",sev:"med",msg:"Quality factor at +0.8σ — nearing 1.0σ ceiling.",time:"Today",icon:"◇"},{cat:"Drawdown",sev:"high",msg:"Energy sector −4.1% this week. Approaching −5% review trigger.",time:"Today",icon:"▾"},{cat:"Drawdown",sev:"low",msg:"UNH down 5.4% from cost — not at 8% stop yet.",ticker:"UNH",time:"2d ago",icon:"▾"},{cat:"Correlation",sev:"med",msg:"NVDA–AVGO 90d corr at 0.85 — combined 6.7% weight.",time:"Weekly",icon:"⬡"},{cat:"Correlation",sev:"low",msg:"Tech internal correlation rising: 0.68 avg (was 0.61).",time:"Weekly",icon:"⬡"},{cat:"Earnings",sev:"info",msg:"5 positions reporting next week: MSFT, AMZN, MA, CAT, XOM.",time:"Upcoming",icon:"◈"},{cat:"Earnings",sev:"info",msg:"Fed rate decision Feb 19. Sensitivity: −0.12% per 25bps.",time:"Feb 19",icon:"◈"},{cat:"Macro",sev:"med",msg:"CPI Thursday — 7.3% energy exposure vs 3.7% benchmark.",time:"Feb 12",icon:"◈"}];
// ═══ MANAGER DATA ═══
const TEAMS=[
  {id:"alpha",name:"Alpha Equity",lead:"J. Morrison",inception:"2024-09-01",capital:419840,capitalPct:41.0,cumRet:14.2,aytdRet:11.1,sharpe:1.52,winRate:72,active:12,inactive:4,realized:38200,unrealized:21400,color:T.accent,
    typeMix:{fundamental:{count:10,capital:285000},systematic:{count:4,capital:98000},macroeconomic:{count:2,capital:36840}}},
  {id:"quant",name:"Quant Systems",lead:"R. Chen",inception:"2024-11-15",capital:310220,capitalPct:30.3,cumRet:8.7,aytdRet:6.3,sharpe:0.94,winRate:58,active:8,inactive:3,realized:12100,unrealized:-3200,color:T.purple,
    typeMix:{fundamental:{count:0,capital:0},systematic:{count:9,capital:278000},macroeconomic:{count:2,capital:32220}}},
  {id:"macro",name:"Macro Themes",lead:"S. Patel",inception:"2025-01-10",capital:245496,capitalPct:23.9,cumRet:18.4,aytdRet:13.9,sharpe:1.78,winRate:80,active:6,inactive:1,realized:29800,unrealized:18600,color:T.green,
    typeMix:{fundamental:{count:2,capital:52000},systematic:{count:1,capital:38000},macroeconomic:{count:4,capital:155496}}}
];
const TEAM_CURVES=[{d:"Sep",alpha:100,quant:100,macro:100},{d:"Oct",alpha:101.8,quant:100.9,macro:103.2},{d:"Nov",alpha:104.2,quant:102.1,macro:106.8},{d:"Dec",alpha:103.1,quant:101.4,macro:105.2},{d:"Jan",alpha:108.4,quant:104.8,macro:112.1},{d:"Feb",alpha:111.1,quant:106.3,macro:113.9}];
const STRATEGIES=[
  // Alpha Equity
  {id:"s1",teamId:"alpha",name:"Long LLY — GLP-1 Thesis",type:"fundamental",status:"active",positions:1,inception:"2025-02-18",lastRecon:null,reconCount:0,invested:35830,cumRet:24.1,aytdRet:18.2,realized:0,unrealized:6920,tickers:["LLY"]},
  {id:"s2",teamId:"alpha",name:"Long NVDA — AI Capex",type:"fundamental",status:"active",positions:1,inception:"2025-05-12",lastRecon:null,reconCount:0,invested:43490,cumRet:38.2,aytdRet:22.4,realized:0,unrealized:11980,tickers:["NVDA"]},
  {id:"s3",teamId:"alpha",name:"Semiconductor Cycle Play",type:"systematic",status:"active",positions:3,inception:"2025-04-01",lastRecon:"2025-10-01",reconCount:1,invested:62800,cumRet:22.8,aytdRet:14.6,realized:9130,unrealized:8420,tickers:["AVGO","AMAT","PANW"],
    reconHistory:[{date:"2025-10-01",period:"P1→P2",out:["AMD"],inn:["PANW"],note:"Rotated AMD after +31% target hit, added PANW on cybersec thesis",priorRet:18.4}]},
  {id:"s4",teamId:"alpha",name:"Payments Duopoly",type:"fundamental",status:"active",positions:2,inception:"2025-03-20",lastRecon:null,reconCount:0,invested:34100,cumRet:9.8,aytdRet:6.2,realized:0,unrealized:3380,tickers:["MA","V"]},
  {id:"s5",teamId:"alpha",name:"Long META — Reels Monetization",type:"fundamental",status:"inactive",positions:0,inception:"2025-03-10",lastRecon:null,reconCount:0,invested:0,cumRet:22.4,aytdRet:0,realized:8420,unrealized:0,tickers:[]},
  {id:"s6",teamId:"alpha",name:"E-Commerce Recovery",type:"fundamental",status:"active",positions:1,inception:"2025-01-15",lastRecon:null,reconCount:0,invested:29680,cumRet:15.8,aytdRet:10.1,realized:0,unrealized:4060,tickers:["AMZN"]},
  // Quant Systems
  {id:"s7",teamId:"quant",name:"Momentum Top Decile Q4-25",type:"systematic",status:"active",positions:8,inception:"2025-10-01",lastRecon:"2026-01-02",reconCount:1,invested:124000,cumRet:12.4,aytdRet:12.4,realized:4200,unrealized:11200,tickers:["HIMS","SOFI","RKLB","DDOG","GE","CRM","AVGO","AMZN"],
    reconHistory:[{date:"2026-01-02",period:"P1→P2",out:["NFLX","SHOP"],inn:["DDOG","CRM"],note:"Q1-26 quarterly rebalance — momentum signal refresh",priorRet:8.1}]},
  {id:"s8",teamId:"quant",name:"Low Vol Quality Screen",type:"systematic",status:"active",positions:6,inception:"2025-07-01",lastRecon:"2026-01-02",reconCount:2,invested:92000,cumRet:6.8,aytdRet:4.2,realized:3120,unrealized:-2800,tickers:["MSFT","JPM","UNH","DHR","CTAS","NEE"],
    reconHistory:[{date:"2025-10-01",period:"P1→P2",out:["PFE"],inn:["DHR"],note:"PFE failed quality screen, replaced with DHR",priorRet:2.1},{date:"2026-01-02",period:"P2→P3",out:["COST"],inn:["NEE"],note:"COST hit valuation ceiling, rotated to NEE",priorRet:3.8}]},
  {id:"s9",teamId:"quant",name:"Mean Reversion Basket",type:"systematic",status:"inactive",positions:0,inception:"2025-04-15",lastRecon:null,reconCount:0,invested:0,cumRet:-6.2,aytdRet:0,realized:-4800,unrealized:0,tickers:[]},
  // Macro Themes
  {id:"s10",teamId:"macro",name:"Inflation Hedge — Energy + Commodities",type:"macroeconomic",status:"active",positions:4,inception:"2025-03-01",lastRecon:"2025-11-15",reconCount:2,invested:82400,cumRet:-1.2,aytdRet:-4.8,realized:-6340,unrealized:-2100,tickers:["XOM","SLB","FCX","CAT"],
    reconHistory:[{date:"2025-07-01",period:"P1→P2",out:["BA"],inn:["CAT"],note:"BA thesis broken on delivery delays, CAT better infra play",priorRet:-8.4},{date:"2025-11-15",period:"P2→P3",out:[],inn:["FCX"],note:"Added copper exposure on electrification thesis",priorRet:3.2}]},
  {id:"s11",teamId:"macro",name:"Rate Sensitivity — Financials",type:"macroeconomic",status:"active",positions:2,inception:"2025-06-01",lastRecon:null,reconCount:0,invested:36800,cumRet:12.1,aytdRet:8.4,realized:3680,unrealized:4120,tickers:["JPM","SOFI"]},
  {id:"s12",teamId:"macro",name:"AI Infrastructure Build-Out",type:"macroeconomic",status:"active",positions:3,inception:"2025-05-01",lastRecon:"2025-11-01",reconCount:1,invested:98200,cumRet:28.6,aytdRet:19.2,realized:5420,unrealized:18200,tickers:["NVDA","MSFT","GOOG"],
    reconHistory:[{date:"2025-11-01",period:"P1→P2",out:["ORCL"],inn:["GOOG"],note:"ORCL hit target, added GOOG on cloud AI ramp",priorRet:9.8}]},
];
const ATTRIBUTION=[
  {team:"Alpha Equity",weight:41.0,ret:14.2,contrib:5.82},
  {team:"Quant Systems",weight:30.3,ret:8.7,contrib:2.64},
  {team:"Macro Themes",weight:23.9,ret:18.4,contrib:4.40},
  {team:"Cash",weight:4.7,ret:0.2,contrib:0.01}
];
const TYPE_ATTR=[
  {type:"Fundamental",weight:48.2,ret:12.1,contrib:5.83},
  {type:"Systematic",weight:32.4,ret:14.8,contrib:4.80},
  {type:"Macroeconomic",weight:14.7,ret:15.3,contrib:2.25}
];
const ALL_POS=[{ticker:"NVDA",name:"NVIDIA",weight:4.2,pnl:38.2,dayChg:1.2,cost:98.42,price:135.87,sector:"Technology",industry:"Semiconductors",days:187,cap:"Large"},{ticker:"MSFT",name:"Microsoft",weight:3.8,pnl:12.4,dayChg:0.3,cost:348.20,price:391.40,sector:"Technology",industry:"Software",days:312,cap:"Large"},{ticker:"LLY",name:"Eli Lilly",weight:3.5,pnl:24.1,dayChg:-0.8,cost:582.10,price:722.30,sector:"Healthcare",industry:"Pharma",days:245,cap:"Large"},{ticker:"JPM",name:"JPMorgan",weight:3.1,pnl:8.7,dayChg:0.5,cost:178.50,price:194.02,sector:"Financials",industry:"Banks",days:198,cap:"Large"},{ticker:"AMZN",name:"Amazon",weight:2.9,pnl:15.8,dayChg:1.8,cost:158.30,price:183.30,sector:"Consumer Disc.",industry:"E-Commerce",days:276,cap:"Large"},{ticker:"XOM",name:"Exxon",weight:2.7,pnl:-3.2,dayChg:-1.1,cost:112.40,price:108.80,sector:"Energy",industry:"Integrated",days:142,cap:"Large"},{ticker:"AVGO",name:"Broadcom",weight:2.5,pnl:42.1,dayChg:2.3,cost:124.80,price:177.30,sector:"Technology",industry:"Semiconductors",days:320,cap:"Large"},{ticker:"UNH",name:"UnitedHealth",weight:2.3,pnl:-5.4,dayChg:-0.2,cost:548.90,price:519.20,sector:"Healthcare",industry:"Managed Care",days:88,cap:"Large"},{ticker:"MA",name:"Mastercard",weight:2.1,pnl:11.3,dayChg:0.1,cost:432.10,price:480.90,sector:"Financials",industry:"Payments",days:201,cap:"Large"},{ticker:"CAT",name:"Caterpillar",weight:1.9,pnl:6.8,dayChg:0.7,cost:318.40,price:340.10,sector:"Industrials",industry:"Machinery",days:156,cap:"Large"},{ticker:"CRM",name:"Salesforce",weight:1.8,pnl:9.2,dayChg:0.4,cost:272.30,price:297.40,sector:"Technology",industry:"Software",days:134,cap:"Large"},{ticker:"AMAT",name:"Applied Mat.",weight:1.7,pnl:18.4,dayChg:1.5,cost:178.90,price:211.80,sector:"Technology",industry:"Semiconductors",days:198,cap:"Large"},{ticker:"DHR",name:"Danaher",weight:1.6,pnl:4.2,dayChg:-0.3,cost:248.10,price:258.50,sector:"Healthcare",industry:"Life Sciences",days:167,cap:"Large"},{ticker:"GE",name:"GE Aero",weight:1.5,pnl:22.8,dayChg:0.9,cost:152.30,price:187.00,sector:"Industrials",industry:"Aerospace",days:234,cap:"Large"},{ticker:"SLB",name:"Schlumberger",weight:1.4,pnl:-7.8,dayChg:-1.4,cost:52.10,price:48.04,sector:"Energy",industry:"Services",days:112,cap:"Large"},{ticker:"MRK",name:"Merck",weight:1.3,pnl:-2.1,dayChg:0.2,cost:118.40,price:115.91,sector:"Healthcare",industry:"Pharma",days:178,cap:"Large"},{ticker:"V",name:"Visa",weight:1.3,pnl:7.4,dayChg:0.3,cost:274.80,price:295.10,sector:"Financials",industry:"Payments",days:189,cap:"Large"},{ticker:"NEE",name:"NextEra",weight:1.2,pnl:3.8,dayChg:0.1,cost:72.40,price:75.15,sector:"Utilities",industry:"Renewables",days:145,cap:"Large"},{ticker:"PANW",name:"Palo Alto",weight:1.1,pnl:14.2,dayChg:0.6,cost:312.40,price:356.80,sector:"Technology",industry:"Cybersecurity",days:98,cap:"Large"},{ticker:"FCX",name:"Freeport",weight:1.0,pnl:-4.1,dayChg:-0.8,cost:44.20,price:42.39,sector:"Materials",industry:"Copper",days:121,cap:"Mid"},{ticker:"DDOG",name:"Datadog",weight:0.9,pnl:16.8,dayChg:1.1,cost:118.20,price:138.05,sector:"Technology",industry:"Software",days:142,cap:"Mid"},{ticker:"ABNB",name:"Airbnb",weight:0.8,pnl:-8.2,dayChg:-1.2,cost:148.30,price:136.14,sector:"Consumer Disc.",industry:"Travel",days:92,cap:"Mid"},{ticker:"HIMS",name:"Hims & Hers",weight:0.6,pnl:52.4,dayChg:3.2,cost:18.40,price:28.04,sector:"Healthcare",industry:"DTC Health",days:156,cap:"Small"},{ticker:"ENPH",name:"Enphase",weight:0.5,pnl:-22.1,dayChg:-2.1,cost:128.40,price:100.02,sector:"Technology",industry:"Solar",days:201,cap:"Mid"},{ticker:"SOFI",name:"SoFi",weight:0.5,pnl:28.4,dayChg:1.8,cost:8.92,price:11.45,sector:"Financials",industry:"Fintech",days:234,cap:"Small"},{ticker:"CELH",name:"Celsius",weight:0.4,pnl:-31.2,dayChg:-0.4,cost:58.10,price:39.97,sector:"Consumer Disc.",industry:"Beverages",days:178,cap:"Small"},{ticker:"RKLB",name:"Rocket Lab",weight:0.3,pnl:68.4,dayChg:4.1,cost:12.80,price:21.56,sector:"Industrials",industry:"Space",days:112,cap:"Small"}];
const SL=[...new Set(ALL_POS.map(p=>p.sector))].sort();
function Stat({label,value,sub,color}){return(<div style={{padding:"12px 14px",background:T.surface,border:`1px solid ${T.border}`,borderRadius:8}}><div style={{fontSize:12,color:T.tM,fontFamily:M,textTransform:"uppercase",letterSpacing:"0.06em",marginBottom:5}}>{label}</div><div style={{fontSize:22,fontWeight:600,color:color||T.text,fontFamily:M,letterSpacing:"-0.02em"}}>{value}</div>{sub&&<div style={{fontSize:13,color:typeof sub==="string"&&sub.startsWith("+")?T.green:typeof sub==="string"&&sub.startsWith("-")?T.red:T.tM,marginTop:3,fontFamily:M}}>{sub}</div>}</div>)}
function Panel({title,subtitle,children,full,accent,right}){return(<div style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:10,gridColumn:full?"1/-1":undefined,overflow:"hidden",boxShadow:"0 1px 3px rgba(0,0,0,0.03)"}}><div style={{padding:"11px 16px",borderBottom:`1px solid ${T.bLt}`,display:"flex",justifyContent:"space-between",alignItems:"center"}}><div style={{display:"flex",alignItems:"baseline",gap:8}}>{accent&&<div style={{width:3,height:13,borderRadius:2,background:accent}}/>}<span style={{fontSize:15,fontWeight:600,color:T.text,fontFamily:S}}>{title}</span>{subtitle&&<span style={{fontSize:13,color:T.tM,fontFamily:M}}>{subtitle}</span>}</div>{right}</div><div style={{padding:"12px 16px"}}>{children}</div></div>)}
function Tog({opts,value,onChange}){return(<div style={{display:"flex",background:T.sAlt,borderRadius:6,padding:2,border:`1px solid ${T.bLt}`}}>{opts.map(o=>(<button key={o.v} onClick={()=>onChange(o.v)} style={{padding:"3px 10px",borderRadius:4,border:"none",cursor:"pointer",background:value===o.v?T.surface:"transparent",color:value===o.v?T.text:T.tM,fontSize:12,fontFamily:S,fontWeight:value===o.v?600:400,boxShadow:value===o.v?"0 1px 2px rgba(0,0,0,0.06)":"none"}}>{o.l}</button>))}</div>)}
const CTip=({active,payload,label})=>{if(!active||!payload?.length)return null;return(<div style={{background:"#fff",border:`1px solid ${T.border}`,borderRadius:6,padding:"8px 12px",boxShadow:"0 4px 12px rgba(0,0,0,0.08)",fontSize:13,fontFamily:M}}><div style={{color:T.tS,marginBottom:4}}>{label}</div>{payload.map((p,i)=>(<div key={i} style={{color:p.color,display:"flex",justifyContent:"space-between",gap:16}}><span>{p.name}</span><span style={{fontWeight:600}}>{typeof p.value==="number"?p.value.toFixed(1):p.value}</span></div>))}</div>)};
function corrColor(v){if(v>=.7)return"#C8220D";if(v>=.4)return"#C2410C";if(v>=.1)return"#A85D00";if(v>-.1)return"#8B99AD";return"#0E7490"}
function corrBg(v){const a=Math.abs(v);if(a>=.7)return v>0?"rgba(200,34,13,0.08)":"rgba(14,116,144,0.08)";if(a>=.4)return v>0?"rgba(194,65,12,0.05)":"rgba(14,116,144,0.05)";return"transparent"}
function TreeMap({data,mode}){const g=useMemo(()=>{const s={};data.forEach(d=>{if(!s[d.s])s[d.s]={w:0,items:[]};s[d.s].w+=d.w;s[d.s].items.push(d)});return s},[data]);const tw=data.reduce((a,d)=>a+d.w,0);const k=mode==="day"?"dc":"wc";const gc=v=>{if(v>=3)return"#065F46";if(v>=1.5)return"#0A7B4F";if(v>=.5)return"#34D399";if(v>=-.5)return"#94A3B8";if(v>=-1.5)return"#F87171";if(v>=-3)return"#C8220D";return"#7F1D1D"};
return(<div style={{display:"flex",flexWrap:"wrap",gap:2,minHeight:240}}>{Object.entries(g).sort((a,b)=>b[1].w-a[1].w).map(([sn,sec])=>{const sp=(sec.w/tw)*100;return(<div key={sn} style={{width:`calc(${sp}% - 2px)`,minWidth:50,display:"flex",flexDirection:"column",gap:1}}><div style={{fontSize:10,fontFamily:M,color:T.tM,padding:"1px 3px",textTransform:"uppercase",letterSpacing:".04em",overflow:"hidden",whiteSpace:"nowrap"}}>{sn}</div><div style={{display:"flex",flexWrap:"wrap",gap:1,flex:1}}>{sec.items.sort((a,b)=>b.w-a.w).map(it=>{const pct=(it.w/sec.w)*100;const c=it[k];return(<div key={it.t} style={{width:`calc(${pct}% - 1px)`,minWidth:36,minHeight:34,background:gc(c),borderRadius:3,padding:"2px 3px",display:"flex",flexDirection:"column",justifyContent:"space-between"}} title={`${it.t} | ${it.i} | Wt:${it.w}% | ${mode==="day"?"Day":"Wk"}:${pp(c)}${c}%`}><div style={{fontSize:11,fontWeight:700,color:"#fff",fontFamily:M}}>{it.t}</div><div style={{fontSize:10,color:"rgba(255,255,255,.8)",fontFamily:M}}>{pp(c)}{c.toFixed(1)}%</div></div>)})}</div></div>)})}</div>)}
const TABS=[{id:"weekly",l:"Weekly Review"},{id:"risk",l:"Risk Analytics"},{id:"construction",l:"Construction"},{id:"closed",l:"Closed Positions"},{id:"alerts",l:"Alerts & Attention"},{id:"managers",l:"Manager Performance"}];
const sevC={high:T.red,med:T.amber,low:T.tS,info:T.accent},sevBg={high:T.rLt,med:T.amLt,low:T.sAlt,info:T.aLt};
export default function App(){
const[tab,setTab]=useState("weekly"),[curveM,setCurveM]=useState("AYTD"),[heatM,setHeatM]=useState("week"),[corrV,setCorrV]=useState("position");
const[search,setSearch]=useState(""),[secF,setSecF]=useState(""),[capF,setCapF]=useState(""),[pnlF,setPnlF]=useState(""),[sortK,setSortK]=useState("weight"),[sortD,setSortD]=useState("desc");
const[whatIf,setWhatIf]=useState([{ticker:"",action:"Buy",amount:"5000"}]),[closedV,setClosedV]=useState("table"),[alertCat,setAlertCat]=useState("");
const[selTeam,setSelTeam]=useState("all"),[stratFilter,setStratFilter]=useState("active"),[selStrat,setSelStrat]=useState(null),[attrPeriod,setAttrPeriod]=useState("AYTD");
const handleSort=k=>{if(sortK===k)setSortD(d=>d==="asc"?"desc":"asc");else{setSortK(k);setSortD("desc")}};
const filtered=useMemo(()=>{let d=[...ALL_POS];if(search)d=d.filter(p=>p.ticker.toLowerCase().includes(search.toLowerCase())||p.name.toLowerCase().includes(search.toLowerCase()));if(secF)d=d.filter(p=>p.sector===secF);if(capF)d=d.filter(p=>p.cap===capF);if(pnlF==="winners")d=d.filter(p=>p.pnl>0);else if(pnlF==="losers")d=d.filter(p=>p.pnl<0);d.sort((a,b)=>(a[sortK]>b[sortK]?1:-1)*(sortD==="asc"?1:-1));return d},[search,secF,capF,pnlF,sortK,sortD]);
const wiCalc=useMemo(()=>{let db=0,sd={};whatIf.forEach(w=>{if(!w.ticker)return;const a=parseFloat(w.amount)||0,sg=w.action==="Buy"?1:-1;const p=ALL_POS.find(x=>x.ticker===w.ticker.toUpperCase());const sb={Technology:1.15,Healthcare:0.82,Financials:1.08,Energy:1.2,"Consumer Disc.":1.1,Industrials:1.05};const sc=p?.sector||"Technology";db+=sg*(a/PF.nav)*(sb[sc]||1);if(!sd[sc])sd[sc]=0;sd[sc]+=sg*(a/PF.nav)*100});return{nb:(PF.beta+db).toFixed(3),sd}},[whatIf]);
const radar=useMemo(()=>{const b=[{axis:"Momentum",pf:0.6,pos:0},{axis:"Quality",pf:0.8,pos:0},{axis:"Value",pf:-0.3,pos:0},{axis:"Size",pf:-0.2,pos:0},{axis:"Volatility",pf:-0.4,pos:0}];const fm={NVDA:{m:0.9,q:0.7,v:-0.6,s:0.3,vo:0.8},MSFT:{m:0.4,q:0.9,v:0.1,s:0.5,vo:-0.2},AMZN:{m:0.6,q:0.6,v:-0.4,s:0.4,vo:0.3},XOM:{m:-0.3,q:0.4,v:0.8,s:0.2,vo:0.5},LLY:{m:0.7,q:0.8,v:-0.5,s:0.3,vo:0.4}};const f=fm[whatIf[0]?.ticker?.toUpperCase()]||{m:0,q:0,v:0,s:0,vo:0};b[0].pos=f.m;b[1].pos=f.q;b[2].pos=f.v;b[3].pos=f.s;b[4].pos=f.vo;return b},[whatIf]);
const cS=useMemo(()=>{const w=CLOSED.filter(c=>c.pnl>0),l=CLOSED.filter(c=>c.pnl<=0);const byR={},byM={};CLOSED.forEach(c=>{if(!byR[c.reason])byR[c.reason]={n:0,pnl:0,w:0};byR[c.reason].n++;byR[c.reason].pnl+=c.pnl;if(c.pnl>0)byR[c.reason].w++;const m=c.exit.substring(0,7);if(!byM[m])byM[m]={month:m,pnl:0};byM[m].pnl+=c.pnlD});return{tp:CLOSED.reduce((s,c)=>s+c.pnlD,0),ap:CLOSED.reduce((s,c)=>s+c.pnl,0)/CLOSED.length,wr:w.length/CLOSED.length*100,aw:w.length?w.reduce((s,c)=>s+c.pnl,0)/w.length:0,al:l.length?l.reduce((s,c)=>s+c.pnl,0)/l.length:0,ad:Math.round(CLOSED.reduce((s,c)=>s+c.days,0)/CLOSED.length),best:Math.max(...CLOSED.map(c=>c.pnl)),worst:Math.min(...CLOSED.map(c=>c.pnl)),byR,byM:Object.values(byM).sort((a,b)=>a.month.localeCompare(b.month)),dist:CLOSED.map(c=>({ticker:c.ticker,pnl:c.pnl,days:c.days}))}},[]);
const fAlerts=useMemo(()=>alertCat?ALERTS.filter(a=>a.cat===alertCat||a.cat==="Macro"&&alertCat==="Earnings"):ALERTS,[alertCat]);
const teamStrats=useMemo(()=>{let s=selTeam==="all"?STRATEGIES:STRATEGIES.filter(x=>x.teamId===selTeam);if(stratFilter==="active")s=s.filter(x=>x.status==="active");else if(stratFilter==="inactive")s=s.filter(x=>x.status==="inactive");return s.sort((a,b)=>b.invested-a.invested)},[selTeam,stratFilter]);
const selStratData=useMemo(()=>selStrat?STRATEGIES.find(s=>s.id===selStrat):null,[selStrat]);
const stratReturnCurve=useMemo(()=>{if(!selStratData)return[];const base=100;const months=["Sep","Oct","Nov","Dec","Jan","Feb"];const ret=selStratData.cumRet/100;const step=ret/5;return months.map((m,i)=>({d:m,idx:+(base*(1+step*i+(Math.random()-.3)*step*.5)).toFixed(1)}));},[selStratData]);
const SH=({label,k,align})=>(<th onClick={()=>handleSort(k)} style={{padding:"5px 6px",textAlign:align||"left",fontSize:11,color:sortK===k?T.accent:T.tM,fontFamily:M,fontWeight:500,textTransform:"uppercase",cursor:"pointer",userSelect:"none"}}>{label}{sortK===k&&<span style={{fontSize:9,marginLeft:1}}>{sortD==="desc"?"▼":"▲"}</span>}</th>);
return(<div style={{background:T.bg,minHeight:"100vh",fontFamily:S,color:T.text,transform:"scale(1.15)",transformOrigin:"top left",width:"calc(100% / 1.15)",height:"calc(100% / 1.15)"}}>
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:wght@400;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Instrument+Sans:wght@400;500;600;700&display=swap" rel="stylesheet"/>
<header style={{background:T.surface,borderBottom:`1px solid ${T.border}`,padding:"0 24px",display:"flex",justifyContent:"space-between",alignItems:"center",height:50}}>
<div style={{display:"flex",alignItems:"center",gap:12}}><span style={{fontSize:21,fontWeight:700,fontFamily:SE,letterSpacing:"-.03em"}}>Meridian</span><div style={{width:1,height:16,background:T.border}}/><span style={{fontSize:12,color:T.tM,fontFamily:M}}>Equity Portfolio</span></div>
<div style={{display:"flex",alignItems:"center",gap:12}}><span style={{fontSize:12,color:T.tM,fontFamily:M}}>{new Date().toLocaleDateString("en-US",{weekday:"short",month:"short",day:"numeric"})}</span><div style={{padding:"3px 8px",borderRadius:4,fontSize:13,fontFamily:M,fontWeight:600,background:T.gLt,color:T.green}}>{pp(PF.dayPct)}{PF.dayPct}%</div></div>
</header>
<nav style={{background:T.surface,borderBottom:`1px solid ${T.border}`,padding:"0 24px",display:"flex"}}>{TABS.map(t=>(<button key={t.id} onClick={()=>setTab(t.id)} style={{padding:"9px 14px",background:"none",border:"none",cursor:"pointer",borderBottom:tab===t.id?`2px solid ${T.accent}`:"2px solid transparent",color:tab===t.id?T.text:T.tM,fontSize:13,fontFamily:S,fontWeight:tab===t.id?600:400}}>{t.l}</button>))}</nav>
<main style={{padding:"16px 24px 36px",maxWidth:1380,margin:"0 auto"}}>
{/* WEEKLY */}
{tab==="weekly"&&(<div style={{display:"flex",flexDirection:"column",gap:12}}>
<div style={{display:"grid",gridTemplateColumns:"repeat(7,1fr)",gap:8}}>
<Stat label="NAV" value={fK(PF.nav)} sub={`${pp(PF.weekPct)}${PF.weekPct}% wk`}/>
<Stat label="Cash" value={fK(PF.cash)} sub={`${((PF.cash/PF.nav)*100).toFixed(1)}%`}/>
<Stat label="Positions" value={PF.pos} sub="of 300"/>
<Stat label="Week" value={`${pp(PF.weekPct)}${PF.weekPct}%`} color={pc(PF.weekPnL)} sub={`$${fm(Math.abs(PF.weekPnL))}`}/>
<Stat label="Month" value={`${pp(PF.monthPct)}${PF.monthPct}%`} color={pc(PF.monthPnL)}/>
<Stat label="YTD" value={`${pp(PF.ytdPct)}${PF.ytdPct}%`} color={pc(PF.ytdPnL)}/>
<Stat label="AYTD" value={`${pp(PF.aytdPct)}${PF.aytdPct}%`} color={pc(PF.aytdPct)} sub="Since Sep 1"/>
</div>
<div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
<Panel title="Rate of Return" subtitle="Index (Base 100)" accent={T.accent} right={<Tog opts={[{v:"AYTD",l:"AYTD"},{v:"Max",l:"Max"}]} value={curveM} onChange={setCurveM}/>}>
<ResponsiveContainer width="100%" height={165}><AreaChart data={curveM==="AYTD"?AYTD_CURVE:MAX_CURVE} margin={{top:4,right:4,bottom:0,left:0}}>
<defs><linearGradient id="af" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={T.accent} stopOpacity={.12}/><stop offset="100%" stopColor={T.accent} stopOpacity={0}/></linearGradient></defs>
<XAxis dataKey="d" tick={{fontSize:10,fill:T.tM,fontFamily:M}} axisLine={false} tickLine={false}/><YAxis tick={{fontSize:10,fill:T.tM,fontFamily:M}} axisLine={false} tickLine={false} domain={["dataMin-1","dataMax+1"]}/>
<Tooltip content={<CTip/>}/><Area type="monotone" dataKey="pf" name="Portfolio" stroke={T.accent} strokeWidth={2} fill="url(#af)"/><Line type="monotone" dataKey="spy" name="SPY" stroke={T.tM} strokeWidth={1.5} strokeDasharray="4 3" dot={false}/>
</AreaChart></ResponsiveContainer>
<div style={{display:"flex",gap:14,marginTop:4,fontSize:10,fontFamily:M,color:T.tM}}><span style={{color:T.accent}}>━</span><span>Portfolio {curveM==="AYTD"?"+9.6%":"+13.8%"}</span><span style={{color:T.tM}}>┅</span><span>SPY {curveM==="AYTD"?"+7.1%":"+10.2%"}</span></div>
</Panel>
<Panel title="Top Alerts" subtitle={`${ALERTS.filter(a=>a.sev==="high").length} critical`} accent={T.red} right={<button onClick={()=>setTab("alerts")} style={{fontSize:10,color:T.accent,background:"none",border:"none",cursor:"pointer",fontFamily:M}}>View all →</button>}>
<div style={{display:"flex",flexDirection:"column",gap:4}}>{ALERTS.filter(a=>a.sev==="high"||a.sev==="med").slice(0,5).map((a,i)=>(<div key={i} style={{display:"flex",gap:8,padding:"6px 8px",borderRadius:5,background:sevBg[a.sev],border:`1px solid ${T.bLt}`}}>
<span style={{color:sevC[a.sev],fontSize:11,fontFamily:M,marginTop:1}}>{a.icon}</span>
<div style={{flex:1}}><div style={{fontSize:11,color:T.text,lineHeight:1.4}}>{a.msg.length>85?a.msg.slice(0,85)+"…":a.msg}</div>
<div style={{display:"flex",gap:8,marginTop:2}}><span style={{fontSize:9,color:T.tM,fontFamily:M}}>{a.cat}</span><span style={{fontSize:9,color:T.tM,fontFamily:M}}>{a.time}</span></div></div>
</div>))}</div>
</Panel>
</div>
<Panel title="Portfolio Heatmap" subtitle="Sector → Industry → Ticker" full accent={T.accent} right={<Tog opts={[{v:"day",l:"Daily"},{v:"week",l:"Weekly"}]} value={heatM} onChange={setHeatM}/>}>
<TreeMap data={TREE} mode={heatM}/>
<div style={{display:"flex",gap:4,marginTop:8,justifyContent:"center"}}>{[{c:"#7F1D1D",l:"≤−3%"},{c:"#C8220D",l:"−3"},{c:"#F87171",l:"−1.5"},{c:"#94A3B8",l:"~0"},{c:"#34D399",l:"+0.5"},{c:"#0A7B4F",l:"+1.5"},{c:"#065F46",l:"≥+3%"}].map((x,i)=>(<div key={i} style={{display:"flex",alignItems:"center",gap:2}}><div style={{width:10,height:10,borderRadius:2,background:x.c}}/><span style={{fontSize:8,color:T.tM,fontFamily:M}}>{x.l}</span></div>))}</div>
</Panel>
<div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
<Panel title="Top 10 Movers" subtitle="Week" accent={T.green}>{TOP10.map((p,i)=>(<div key={i} style={{display:"flex",justifyContent:"space-between",padding:"4px 0",borderBottom:`1px solid ${T.bLt}`}}><div style={{display:"flex",gap:6,alignItems:"center"}}><span style={{fontSize:10,color:T.tM,fontFamily:M,width:14}}>{i+1}</span><span style={{fontFamily:M,fontWeight:600,fontSize:11}}>{p.t}</span><span style={{color:T.tM,fontSize:9}}>{p.i}</span></div><div style={{display:"flex",gap:10}}><span style={{fontFamily:M,fontSize:10,color:T.tM}}>{p.w}%</span><span style={{fontFamily:M,fontSize:11,fontWeight:600,color:T.green,minWidth:44,textAlign:"right"}}>{pp(p.wc)}{p.wc.toFixed(1)}%</span></div></div>))}</Panel>
<Panel title="Bottom 10 Movers" subtitle="Week" accent={T.red}>{BOT10.map((p,i)=>(<div key={i} style={{display:"flex",justifyContent:"space-between",padding:"4px 0",borderBottom:`1px solid ${T.bLt}`}}><div style={{display:"flex",gap:6,alignItems:"center"}}><span style={{fontSize:10,color:T.tM,fontFamily:M,width:14}}>{i+1}</span><span style={{fontFamily:M,fontWeight:600,fontSize:11}}>{p.t}</span><span style={{color:T.tM,fontSize:9}}>{p.i}</span></div><div style={{display:"flex",gap:10}}><span style={{fontFamily:M,fontSize:10,color:T.tM}}>{p.w}%</span><span style={{fontFamily:M,fontSize:11,fontWeight:600,color:T.red,minWidth:44,textAlign:"right"}}>{p.wc.toFixed(1)}%</span></div></div>))}</Panel>
</div>
</div>)}
{/* RISK */}
{tab==="risk"&&(<div style={{display:"flex",flexDirection:"column",gap:12}}>
<div style={{display:"grid",gridTemplateColumns:"repeat(6,1fr)",gap:8}}>
<Stat label="VaR (95%)" value="−$32.8K" color={T.red} sub="Daily"/><Stat label="CVaR" value="−$48.2K" color={T.red} sub="Exp. shortfall"/>
<Stat label="Max DD" value={`${PF.maxDD}%`} color={T.red} sub="−$85.1K"/><Stat label="Vol" value={`${PF.vol}%`} sub="Ann. σ"/>
<Stat label="Beta" value={PF.beta.toFixed(2)} sub={`α: ${pp(PF.alpha)}${PF.alpha}%`}/><Stat label="Track. Err" value="6.8%" sub="vs S&P"/>
</div>
<div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
<Panel title="Return Distribution" accent={T.red}>
<ResponsiveContainer width="100%" height={175}><BarChart data={VAR_DIST} margin={{top:4,right:4,bottom:0,left:0}}>
<XAxis dataKey="ret" tick={{fontSize:9,fill:T.tM,fontFamily:M}} axisLine={false} tickLine={false} interval={4}/><YAxis hide/><Tooltip content={<CTip/>}/>
<ReferenceLine x="-3.2" stroke={T.red} strokeDasharray="4 3"/><ReferenceLine x="-4.5" stroke={T.purple} strokeDasharray="4 3"/>
<Bar dataKey="freq" name="Freq" radius={[2,2,0,0]}>{VAR_DIST.map((d,i)=><Cell key={i} fill={d.isCVaR?T.purple:d.isVaR?T.red:T.accent} opacity={d.isCVaR?.55:d.isVaR?.45:.2}/>)}</Bar>
</BarChart></ResponsiveContainer></Panel>
<Panel title="Drawdown History" accent={T.red}>
<ResponsiveContainer width="100%" height={175}><AreaChart data={DD_DATA} margin={{top:4,right:4,bottom:0,left:0}}>
<defs><linearGradient id="ddf" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={T.red} stopOpacity={.15}/><stop offset="100%" stopColor={T.red} stopOpacity={.02}/></linearGradient></defs>
<XAxis dataKey="date" tick={{fontSize:10,fill:T.tM,fontFamily:M}} axisLine={false} tickLine={false}/><YAxis tick={{fontSize:10,fill:T.tM,fontFamily:M}} axisLine={false} tickLine={false} domain={[-10,0]} tickFormatter={v=>`${v}%`}/>
<Tooltip content={<CTip/>}/><ReferenceLine y={-8.3} stroke={T.red} strokeDasharray="4 3"/>
<Area type="monotone" dataKey="dd" name="Drawdown" stroke={T.red} strokeWidth={2} fill="url(#ddf)"/>
</AreaChart></ResponsiveContainer></Panel>
</div>
<Panel title="Correlation Matrix" subtitle="90-day" full accent={T.amber} right={<Tog opts={[{v:"position",l:"Positions"},{v:"sector",l:"Sectors"}]} value={corrV} onChange={setCorrV}/>}>
<div style={{overflowX:"auto"}}><table style={{borderCollapse:"separate",borderSpacing:2,width:"100%"}}><thead><tr><th style={{padding:4}}></th>{(corrV==="position"?CT:CSN).map(t=><th key={t} style={{padding:"4px 3px",fontSize:10,fontFamily:M,color:T.tS,fontWeight:600,textAlign:"center",minWidth:46}}>{t}</th>)}</tr></thead>
<tbody>{(corrV==="position"?CT:CSN).map((row,ri)=>(<tr key={row}><td style={{padding:"4px 5px",fontSize:10,fontFamily:M,fontWeight:600,color:T.tS}}>{row}</td>
{(corrV==="position"?CP:CSM)[ri].map((v,ci)=>(<td key={ci} style={{padding:"4px 3px",textAlign:"center",fontSize:11,fontFamily:M,color:ri===ci?T.tM:corrColor(v),background:ri===ci?"transparent":corrBg(v),borderRadius:4,fontWeight:ri===ci?400:500}}>{ri===ci?"—":v.toFixed(2)}</td>))}
</tr>))}</tbody></table></div></Panel>
<div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
<Panel title="Rolling Metrics" accent={T.accent}>
<table style={{width:"100%",borderCollapse:"collapse",fontSize:11}}><thead><tr style={{borderBottom:`1px solid ${T.border}`}}>{["Win","Sharpe","Sortino","Vol","Beta","DD"].map((h,i)=><th key={i} style={{padding:"5px",textAlign:i?"right":"left",fontSize:9,color:T.tM,fontFamily:M,fontWeight:500,textTransform:"uppercase"}}>{h}</th>)}</tr></thead>
<tbody>{ROLL.map((r,i)=>(<tr key={i} style={{borderBottom:`1px solid ${T.bLt}`}}><td style={{padding:"6px 5px",fontFamily:M,fontWeight:600}}>{r.p}</td><td style={{padding:"6px 5px",textAlign:"right",fontFamily:M,color:r.sh>=1.5?T.green:T.tS}}>{r.sh}</td><td style={{padding:"6px 5px",textAlign:"right",fontFamily:M,color:r.so>=2?T.green:T.tS}}>{r.so}</td><td style={{padding:"6px 5px",textAlign:"right",fontFamily:M}}>{r.vo}%</td><td style={{padding:"6px 5px",textAlign:"right",fontFamily:M}}>{r.be}</td><td style={{padding:"6px 5px",textAlign:"right",fontFamily:M,color:T.red}}>{r.dd}%</td></tr>))}</tbody></table></Panel>
<Panel title="Factor Decomposition" accent={T.purple}>
{[{f:"Market (β)",p:62,c:T.accent},{f:"Sector",p:14,c:T.purple},{f:"Momentum",p:8,c:T.green},{f:"Size",p:5,c:T.amber},{f:"Value",p:4,c:T.cyan},{f:"Idiosyncratic",p:7,c:T.tM}].map((f,i)=>(<div key={i} style={{display:"flex",alignItems:"center",gap:8,marginBottom:7}}>
<div style={{width:85,fontSize:11,color:T.tS}}>{f.f}</div>
<div style={{flex:1,height:7,background:T.sAlt,borderRadius:4}}><div style={{height:"100%",width:`${f.p}%`,background:f.c,borderRadius:4,opacity:.6}}/></div>
<div style={{width:28,textAlign:"right",fontFamily:M,fontSize:11,fontWeight:600,color:f.c}}>{f.p}%</div>
</div>))}</Panel>
</div>
</div>)}
{/* CONSTRUCTION */}
{tab==="construction"&&(<div style={{display:"flex",flexDirection:"column",gap:12}}>
<Panel title="Allocation Views" subtitle="Current vs target" full accent={T.accent}>
<div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:16}}>
<div><div style={{fontSize:11,fontWeight:600,color:T.tS,marginBottom:8}}>Sector Drift</div>
{SECTORS.map((s,i)=>{const tgt=s.bench,drift=(s.weight-tgt).toFixed(1);return(<div key={i} style={{display:"grid",gridTemplateColumns:"82px 1fr 36px 36px 44px",alignItems:"center",gap:5,marginBottom:3}}>
<span style={{fontSize:10,color:T.tS,fontFamily:M}}>{s.name}</span>
<div style={{height:9,background:T.sAlt,borderRadius:3,position:"relative"}}><div style={{position:"absolute",height:"100%",width:`${(s.weight/30)*100}%`,background:s.color,borderRadius:3,opacity:.45}}/><div style={{position:"absolute",height:"100%",width:2,left:`${(tgt/30)*100}%`,background:T.text,opacity:.2}}/></div>
<span style={{textAlign:"right",fontFamily:M,fontSize:10}}>{s.weight}%</span>
<span style={{textAlign:"right",fontFamily:M,fontSize:10,color:T.tM}}>{tgt}%</span>
<span style={{textAlign:"right",fontFamily:M,fontSize:10,fontWeight:600,color:Math.abs(drift)>3?T.red:Math.abs(drift)>1.5?T.amber:T.green}}>{Number(drift)>0?"+":""}{drift}%</span>
</div>)})}</div>
<div><div style={{fontSize:11,fontWeight:600,color:T.tS,marginBottom:8}}>Factor Drift & Cash</div>
{[{f:"Momentum",c:0.6,t:0.4},{f:"Quality",c:0.8,t:0.6},{f:"Value",c:-0.3,t:0.0},{f:"Size",c:-0.2,t:0.0},{f:"Volatility",c:-0.4,t:-0.2}].map((f,i)=>{const d=(f.c-f.t).toFixed(1);return(<div key={i} style={{display:"flex",justifyContent:"space-between",padding:"4px 0",borderBottom:`1px solid ${T.bLt}`,fontSize:11}}>
<span style={{color:T.tS}}>{f.f}</span>
<div style={{display:"flex",gap:10}}><span style={{fontFamily:M,color:T.tM}}>Tgt:{f.t>0?"+":""}{f.t}σ</span><span style={{fontFamily:M}}>Cur:{f.c>0?"+":""}{f.c}σ</span><span style={{fontFamily:M,fontWeight:600,color:Math.abs(Number(d))>.3?T.amber:T.green}}>{Number(d)>0?"+":""}{d}σ</span></div>
</div>)})}
<div style={{marginTop:10,padding:"9px 11px",background:T.sAlt,borderRadius:6}}>
<div style={{fontSize:9,fontFamily:M,color:T.tM,textTransform:"uppercase",marginBottom:4}}>Cash Utilization</div>
<div style={{display:"flex",justifyContent:"space-between",fontSize:11}}><span>Available: <strong style={{fontFamily:M}}>{fK(PF.cash)}</strong></span><span style={{fontFamily:M,color:T.tM}}>{((PF.cash/PF.nav)*100).toFixed(1)}%</span></div>
<div style={{height:5,background:T.border,borderRadius:3,marginTop:5}}><div style={{height:"100%",width:`${((PF.nav-PF.cash)/PF.nav)*100}%`,background:T.accent,borderRadius:3,opacity:.5}}/></div>
<div style={{display:"flex",justifyContent:"space-between",marginTop:3,fontSize:9,fontFamily:M,color:T.tM}}><span>Invested: {(((PF.nav-PF.cash)/PF.nav)*100).toFixed(1)}%</span><span>Target: 96%</span></div>
</div></div></div></Panel>
<Panel title="What-If Staging Area" subtitle="Pre-trade impact" full accent={T.purple}>
<div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:16}}>
<div><div style={{display:"flex",flexDirection:"column",gap:6}}>
{whatIf.map((w,i)=>(<div key={i} style={{display:"flex",gap:5,alignItems:"center"}}>
<select value={w.action} onChange={e=>{const n=[...whatIf];n[i].action=e.target.value;setWhatIf(n)}} style={{padding:"4px 5px",borderRadius:4,border:`1px solid ${T.border}`,fontSize:11,fontFamily:S,width:56,color:w.action==="Buy"?T.green:T.red}}><option value="Buy">Buy</option><option value="Sell">Sell</option></select>
<input value={w.ticker} onChange={e=>{const n=[...whatIf];n[i].ticker=e.target.value;setWhatIf(n)}} placeholder="Ticker" style={{padding:"4px 7px",borderRadius:4,border:`1px solid ${T.border}`,fontSize:11,fontFamily:M,width:65,textTransform:"uppercase"}}/>
<div style={{display:"flex",alignItems:"center",gap:2}}><span style={{fontSize:10,color:T.tM}}>$</span><input value={w.amount} onChange={e=>{const n=[...whatIf];n[i].amount=e.target.value;setWhatIf(n)}} placeholder="Amt" style={{padding:"4px 7px",borderRadius:4,border:`1px solid ${T.border}`,fontSize:11,fontFamily:M,width:70}}/></div>
{whatIf.length>1&&<button onClick={()=>setWhatIf(whatIf.filter((_,j)=>j!==i))} style={{background:"none",border:"none",color:T.red,cursor:"pointer",fontSize:13,padding:0}}>×</button>}
</div>))}
<button onClick={()=>setWhatIf([...whatIf,{ticker:"",action:"Buy",amount:"5000"}])} style={{alignSelf:"flex-start",padding:"4px 10px",borderRadius:4,border:`1px dashed ${T.border}`,background:"none",color:T.accent,fontSize:10,fontFamily:S,cursor:"pointer"}}>+ Add trade</button>
</div>
<div style={{marginTop:10,padding:"9px 11px",background:T.sAlt,borderRadius:7,border:`1px solid ${T.bLt}`}}>
<div style={{fontSize:9,fontFamily:M,color:T.tM,textTransform:"uppercase",marginBottom:5}}>Projected Impact</div>
<div style={{display:"flex",justifyContent:"space-between",marginBottom:4,fontSize:12}}><span style={{color:T.tS}}>Portfolio Beta</span><span style={{fontFamily:M}}>{PF.beta} → <strong style={{color:T.accent}}>{wiCalc.nb}</strong></span></div>
{Object.entries(wiCalc.sd).map(([sec,d],i)=>(<div key={i} style={{display:"flex",justifyContent:"space-between",fontSize:11,padding:"2px 0"}}><span style={{color:T.tM}}>{sec}</span><span style={{fontFamily:M,color:d>0?T.green:T.red}}>{d>0?"+":""}{d.toFixed(2)}%</span></div>))}
</div></div>
<div><div style={{fontSize:11,fontWeight:600,color:T.tS,marginBottom:4}}>Factor Shape</div>
<ResponsiveContainer width="100%" height={210}><RadarChart data={radar} outerRadius={75}>
<PolarGrid stroke={T.bLt}/><PolarAngleAxis dataKey="axis" tick={{fontSize:10,fill:T.tS,fontFamily:M}}/><PolarRadiusAxis tick={{fontSize:8,fill:T.tM}} domain={[-1,1]} axisLine={false}/>
<Radar name="Portfolio" dataKey="pf" stroke={T.accent} fill={T.accent} fillOpacity={.15} strokeWidth={2}/><Radar name="Position" dataKey="pos" stroke={T.purple} fill={T.purple} fillOpacity={.1} strokeWidth={2} strokeDasharray="4 3"/>
<Tooltip content={<CTip/>}/></RadarChart></ResponsiveContainer>
<div style={{display:"flex",gap:12,justifyContent:"center",fontSize:10,fontFamily:M,color:T.tM}}><span><span style={{color:T.accent}}>━</span> Portfolio</span><span><span style={{color:T.purple}}>┅</span> Position</span></div>
</div></div></Panel>
<div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
<Panel title="Diversification" accent={T.cyan}>
<div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:6}}>{[{l:"HHI",v:"342",n:"Well diversified",c:T.green},{l:"Eff. Pos.",v:"29.2",n:"of 247",c:T.accent},{l:"Entropy",v:"0.91",n:"High",c:T.green},{l:"Avg Corr.",v:"0.38",n:"Moderate",c:T.amber},{l:"Gini",v:"0.64",n:"Moderate",c:T.amber},{l:"Active Share",v:"72%",n:"vs S&P",c:T.purple}].map((m,i)=>(<div key={i} style={{background:T.sAlt,borderRadius:5,padding:"7px 9px"}}><div style={{fontSize:9,color:T.tM,fontFamily:M,textTransform:"uppercase"}}>{m.l}</div><div style={{fontSize:15,fontWeight:600,fontFamily:M,margin:"2px 0"}}>{m.v}</div><div style={{fontSize:9,color:m.c}}>{m.n}</div></div>))}</div></Panel>
<div style={{display:"flex",flexDirection:"column",gap:12}}>
<Panel title="Trim" accent={T.red}>{[{t:"NVDA",r:"Near 5% cap",a:"−0.8%"},{t:"AVGO",r:"+42%",a:"−0.5%"},{t:"XOM",r:"Energy OW",a:"−1.0%"}].map((x,i)=>(<div key={i} style={{display:"flex",justifyContent:"space-between",padding:"4px 0",borderBottom:`1px solid ${T.bLt}`,fontSize:11}}><div><span style={{fontFamily:M,fontWeight:600}}>{x.t}</span><span style={{color:T.tM,marginLeft:6,fontSize:10}}>{x.r}</span></div><span style={{fontFamily:M,color:T.red,fontSize:10}}>{x.a}</span></div>))}</Panel>
<Panel title="Add" accent={T.green}>{[{t:"Cons.Staples",r:"UW 3.8%",a:"+3.8%"},{t:"PANW",r:"Sc.82",a:"+1.5%"},{t:"VST",r:"Sc.79",a:"+1.0%"}].map((x,i)=>(<div key={i} style={{display:"flex",justifyContent:"space-between",padding:"4px 0",borderBottom:`1px solid ${T.bLt}`,fontSize:11}}><div><span style={{fontFamily:M,fontWeight:600}}>{x.t}</span><span style={{color:T.tM,marginLeft:6,fontSize:10}}>{x.r}</span></div><span style={{fontFamily:M,color:T.green,fontSize:10}}>{x.a}</span></div>))}</Panel>
</div></div>
<Panel title="All Positions" subtitle={`${filtered.length} shown`} full accent={T.accent}
right={<div style={{display:"flex",gap:5,alignItems:"center"}}>
<input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search…" style={{padding:"4px 7px",borderRadius:4,border:`1px solid ${T.border}`,fontSize:10,fontFamily:S,width:130,outline:"none"}}/>
<select value={secF} onChange={e=>setSecF(e.target.value)} style={{padding:"3px 5px",borderRadius:4,border:`1px solid ${T.border}`,fontSize:10,fontFamily:S,cursor:"pointer"}}><option value="">All Sectors</option>{SL.map(s=><option key={s}>{s}</option>)}</select>
<select value={capF} onChange={e=>setCapF(e.target.value)} style={{padding:"3px 5px",borderRadius:4,border:`1px solid ${T.border}`,fontSize:10,fontFamily:S,cursor:"pointer"}}><option value="">All Cap</option>{["Large","Mid","Small"].map(s=><option key={s}>{s}</option>)}</select>
<select value={pnlF} onChange={e=>setPnlF(e.target.value)} style={{padding:"3px 5px",borderRadius:4,border:`1px solid ${T.border}`,fontSize:10,fontFamily:S,cursor:"pointer"}}><option value="">All P&L</option><option value="winners">W</option><option value="losers">L</option></select>
</div>}>
<div style={{maxHeight:340,overflowY:"auto"}}><table style={{width:"100%",borderCollapse:"collapse",fontSize:11}}>
<thead style={{position:"sticky",top:0,background:T.surface,zIndex:1}}><tr style={{borderBottom:`1px solid ${T.border}`}}>
<SH label="Ticker" k="ticker"/><th style={{padding:"5px 6px",fontSize:9,color:T.tM,fontFamily:M,fontWeight:500,textTransform:"uppercase",textAlign:"left"}}>Name</th>
<SH label="Sector" k="sector"/><SH label="Industry" k="industry"/><SH label="Cap" k="cap"/>
<SH label="Wt" k="weight" align="right"/><SH label="Price" k="price" align="right"/><SH label="Cost" k="cost" align="right"/>
<SH label="P&L" k="pnl" align="right"/><SH label="Day" k="dayChg" align="right"/><SH label="Days" k="days" align="right"/>
</tr></thead>
<tbody>{filtered.map((p,i)=>(<tr key={i} style={{borderBottom:`1px solid ${T.bLt}`}} onMouseEnter={e=>e.currentTarget.style.background=T.sAlt} onMouseLeave={e=>e.currentTarget.style.background="transparent"}>
<td style={{padding:"5px 6px",fontFamily:M,fontWeight:600,fontSize:11}}>{p.ticker}</td>
<td style={{padding:"5px 6px",color:T.tS,fontSize:10}}>{p.name}</td>
<td style={{padding:"5px 6px",color:T.tM,fontSize:10}}>{p.sector}</td>
<td style={{padding:"5px 6px",color:T.tM,fontSize:10}}>{p.industry}</td>
<td style={{padding:"5px 6px"}}><span style={{padding:"1px 4px",borderRadius:3,background:p.cap==="Small"?T.pLt:p.cap==="Mid"?T.amLt:T.aLt,color:p.cap==="Small"?T.purple:p.cap==="Mid"?T.amber:T.accent,fontFamily:M,fontSize:9}}>{p.cap}</span></td>
<td style={{padding:"5px 6px",textAlign:"right",fontFamily:M}}>{p.weight}%</td>
<td style={{padding:"5px 6px",textAlign:"right",fontFamily:M,color:T.tS}}>${fm(p.price)}</td>
<td style={{padding:"5px 6px",textAlign:"right",fontFamily:M,color:T.tM,fontSize:10}}>${fm(p.cost)}</td>
<td style={{padding:"5px 6px",textAlign:"right",fontFamily:M,fontWeight:600,color:pc(p.pnl)}}>{pp(p.pnl)}{p.pnl}%</td>
<td style={{padding:"5px 6px",textAlign:"right",fontFamily:M,color:pc(p.dayChg)}}>{pp(p.dayChg)}{p.dayChg}%</td>
<td style={{padding:"5px 6px",textAlign:"right",fontFamily:M,color:T.tM,fontSize:10}}>{p.days}</td>
</tr>))}</tbody></table></div></Panel>
</div>)}
{/* CLOSED */}
{tab==="closed"&&(<div style={{display:"flex",flexDirection:"column",gap:12}}>
<div style={{display:"grid",gridTemplateColumns:"repeat(6,1fr)",gap:8}}>
<Stat label="Realized" value={`$${fm(cS.tp)}`} color={pc(cS.tp)}/><Stat label="Avg Ret" value={`${pp(cS.ap)}${cS.ap.toFixed(1)}%`} color={pc(cS.ap)}/>
<Stat label="Win Rate" value={`${cS.wr.toFixed(0)}%`} sub={`${CLOSED.filter(c=>c.pnl>0).length}W/${CLOSED.filter(c=>c.pnl<=0).length}L`}/>
<Stat label="Avg W/L" value={`+${cS.aw.toFixed(1)}%`} sub={`${cS.al.toFixed(1)}%`}/>
<Stat label="Hold" value={`${cS.ad}d`}/><Stat label="Best/Worst" value={`+${cS.best}%`} sub={`${cS.worst}%`}/>
</div>
<Panel title="Trade Log" full accent={T.accent} right={<Tog opts={[{v:"table",l:"Table"},{v:"chart",l:"Analytics"}]} value={closedV} onChange={setClosedV}/>}>
{closedV==="table"?(<div style={{maxHeight:320,overflowY:"auto"}}><table style={{width:"100%",borderCollapse:"collapse",fontSize:11}}>
<thead style={{position:"sticky",top:0,background:T.surface}}><tr style={{borderBottom:`1px solid ${T.border}`}}>{["Ticker","Sector","Entry","Exit","Entry$","Exit$","Ret","P&L","Hold","Reason"].map((h,i)=><th key={i} style={{padding:"5px 6px",textAlign:i>=2?"right":"left",fontSize:9,color:T.tM,fontFamily:M,fontWeight:500,textTransform:"uppercase"}}>{h}</th>)}</tr></thead>
<tbody>{CLOSED.sort((a,b)=>new Date(b.exit)-new Date(a.exit)).map((p,i)=>(<tr key={i} style={{borderBottom:`1px solid ${T.bLt}`,borderLeft:`3px solid ${pc(p.pnl)}`}}>
<td style={{padding:"5px 6px",fontFamily:M,fontWeight:600}}>{p.ticker}</td><td style={{padding:"5px 6px",color:T.tM,fontSize:10}}>{p.sector}</td>
<td style={{padding:"5px 6px",textAlign:"right",fontFamily:M,fontSize:9,color:T.tM}}>{p.entry}</td><td style={{padding:"5px 6px",textAlign:"right",fontFamily:M,fontSize:9}}>{p.exit}</td>
<td style={{padding:"5px 6px",textAlign:"right",fontFamily:M,fontSize:10,color:T.tM}}>${fm(p.eP)}</td><td style={{padding:"5px 6px",textAlign:"right",fontFamily:M,fontSize:10}}>${fm(p.xP)}</td>
<td style={{padding:"5px 6px",textAlign:"right",fontFamily:M,fontWeight:600,color:pc(p.pnl)}}>{pp(p.pnl)}{p.pnl}%</td>
<td style={{padding:"5px 6px",textAlign:"right",fontFamily:M,color:pc(p.pnlD)}}>{pp(p.pnlD)}${fm(Math.abs(p.pnlD),0)}</td>
<td style={{padding:"5px 6px",textAlign:"right",fontFamily:M,fontSize:9,color:T.tM}}>{p.days}d</td>
<td style={{padding:"5px 6px",textAlign:"right",fontSize:10,color:p.reason==="Stop loss"?T.red:p.reason==="Thesis broken"?T.amber:T.tS}}>{p.reason}</td>
</tr>))}</tbody></table></div>):(
<div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
<div><div style={{fontSize:11,fontWeight:600,color:T.tS,marginBottom:6}}>Returns</div><ResponsiveContainer width="100%" height={150}><BarChart data={CLOSED.sort((a,b)=>b.pnl-a.pnl)} margin={{top:4,right:4,bottom:0,left:0}}><XAxis dataKey="ticker" tick={{fontSize:9,fill:T.tM,fontFamily:M}} axisLine={false} tickLine={false}/><YAxis tick={{fontSize:9,fill:T.tM,fontFamily:M}} axisLine={false} tickLine={false} tickFormatter={v=>`${v}%`}/><Tooltip content={<CTip/>}/><ReferenceLine y={0} stroke={T.border}/><Bar dataKey="pnl" name="Ret" radius={[3,3,0,0]}>{CLOSED.sort((a,b)=>b.pnl-a.pnl).map((c,i)=><Cell key={i} fill={c.pnl>=0?T.green:T.red} opacity={.6}/>)}</Bar></BarChart></ResponsiveContainer></div>
<div><div style={{fontSize:11,fontWeight:600,color:T.tS,marginBottom:6}}>Hold vs Return</div><ResponsiveContainer width="100%" height={150}><ScatterChart margin={{top:4,right:4,bottom:4,left:0}}><XAxis type="number" dataKey="days" tick={{fontSize:9,fill:T.tM,fontFamily:M}} axisLine={false} tickLine={false}/><YAxis type="number" dataKey="pnl" tick={{fontSize:9,fill:T.tM,fontFamily:M}} axisLine={false} tickLine={false} tickFormatter={v=>`${v}%`}/><Tooltip content={<CTip/>}/><ReferenceLine y={0} stroke={T.border}/><Scatter data={cS.dist} fill={T.accent}>{cS.dist.map((d,i)=><Cell key={i} fill={d.pnl>=0?T.green:T.red} fillOpacity={.7}/>)}</Scatter></ScatterChart></ResponsiveContainer></div>
</div>)}</Panel>
<div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
<Panel title="Exit Analysis" accent={T.amber}>{Object.entries(cS.byR).map(([k,v],i)=>(<div key={i} style={{display:"flex",justifyContent:"space-between",padding:"5px 0",borderBottom:`1px solid ${T.bLt}`}}><div><span style={{fontSize:11}}>{k}</span><span style={{fontSize:10,color:T.tM,marginLeft:6}}>{v.n}x</span></div><div style={{display:"flex",gap:10,fontSize:11,fontFamily:M}}><span style={{color:pc(v.pnl)}}>{pp(v.pnl/v.n)}{(v.pnl/v.n).toFixed(1)}%</span><span style={{color:T.tM}}>{v.w}/{v.n}W</span></div></div>))}</Panel>
<Panel title="Lessons" accent={T.green}>{[{t:"Target hit avg +22% — discipline pays",k:"g"},{t:"Stop losses avg −15.5% — tighten?",k:"w"},{t:"Winners held 218d vs losers 141d",k:"g"},{t:"Best: Tech (+$22.4K, 3/6 trades)",k:"g"},{t:"Worst single: INTC −24.8%",k:"w"}].map((l,i)=>(<div key={i} style={{padding:"5px 8px",borderRadius:5,marginBottom:3,background:l.k==="g"?T.gLt:T.amLt,borderLeft:`3px solid ${l.k==="g"?T.green:T.amber}`,fontSize:11,color:T.tS,lineHeight:1.4}}>{l.t}</div>))}</Panel>
</div></div>)}
{/* ALERTS */}
{tab==="alerts"&&(<div style={{display:"flex",flexDirection:"column",gap:12}}>
<div style={{display:"grid",gridTemplateColumns:"repeat(5,1fr)",gap:8}}>
{[{cat:"Position Size",c:T.red,icon:"◆"},{cat:"Factor Breach",c:T.purple,icon:"◇"},{cat:"Drawdown",c:T.amber,icon:"▾"},{cat:"Correlation",c:T.cyan,icon:"⬡"},{cat:"Earnings",c:T.accent,icon:"◈"}].map((g,i)=>{
const cnt=ALERTS.filter(a=>g.cat==="Earnings"?(a.cat==="Earnings"||a.cat==="Macro"):a.cat===g.cat).length;
return(<button key={i} onClick={()=>setAlertCat(alertCat===g.cat?"":g.cat)} style={{padding:"10px 12px",background:alertCat===g.cat?T.surface:T.sAlt,border:`1px solid ${alertCat===g.cat?g.c:T.border}`,borderRadius:8,cursor:"pointer",textAlign:"left",boxShadow:alertCat===g.cat?`0 0 0 1px ${g.c}22`:"none"}}>
<div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:4}}><span style={{fontSize:14,color:g.c}}>{g.icon}</span><span style={{fontSize:16,fontWeight:700,fontFamily:M,color:g.c}}>{cnt}</span></div>
<div style={{fontSize:10,color:T.tS,fontFamily:S,fontWeight:500}}>{g.cat}</div>
</button>)})}
</div>
<Panel title={alertCat||"All Alerts"} subtitle={`${fAlerts.length} items`} full accent={T.red}>
<div style={{display:"flex",flexDirection:"column",gap:5}}>
{fAlerts.map((a,i)=>(<div key={i} style={{display:"flex",gap:10,padding:"9px 11px",borderRadius:6,background:sevBg[a.sev],border:`1px solid ${T.bLt}`,borderLeft:`4px solid ${sevC[a.sev]}`}}>
<div style={{fontSize:14,color:sevC[a.sev],marginTop:1}}>{a.icon}</div>
<div style={{flex:1}}>
<div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:3}}>
<div style={{display:"flex",gap:6,alignItems:"center"}}><span style={{fontSize:9,fontFamily:M,padding:"1px 5px",borderRadius:3,background:sevC[a.sev]+"18",color:sevC[a.sev],textTransform:"uppercase",fontWeight:600}}>{a.sev}</span><span style={{fontSize:10,color:T.tM,fontFamily:M}}>{a.cat}</span></div>
<span style={{fontSize:10,color:T.tM,fontFamily:M}}>{a.time}</span>
</div>
<div style={{fontSize:12,color:T.text,lineHeight:1.5}}>{a.msg}</div>
{a.ticker&&<div style={{marginTop:3}}><span style={{fontSize:10,fontFamily:M,fontWeight:600,padding:"1px 5px",borderRadius:3,background:T.aLt,color:T.accent}}>{a.ticker}</span></div>}
</div></div>))}
</div></Panel>
<div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:12}}>
<Panel title="Severity" accent={T.red}>
{[{s:"high",l:"Critical"},{s:"med",l:"Warning"},{s:"low",l:"Monitor"},{s:"info",l:"Info"}].map((x,i)=>{const n=ALERTS.filter(a=>a.sev===x.s).length;return(<div key={i} style={{display:"flex",justifyContent:"space-between",alignItems:"center",padding:"5px 0",borderBottom:`1px solid ${T.bLt}`}}>
<div style={{display:"flex",alignItems:"center",gap:6}}><div style={{width:8,height:8,borderRadius:"50%",background:sevC[x.s]}}/><span style={{fontSize:11,color:T.tS}}>{x.l}</span></div>
<span style={{fontFamily:M,fontWeight:600,fontSize:14,color:sevC[x.s]}}>{n}</span>
</div>)})}
</Panel>
<Panel title="This Week's Focus" accent={T.amber}>
{["Trim NVDA before 5% cap","Review UNH thesis — reg. headwinds","Energy 2× OW vs benchmark","5 earnings next week","Tech corr creep 0.68 avg"].map((t,i)=>(<div key={i} style={{padding:"4px 0",borderBottom:`1px solid ${T.bLt}`,fontSize:11,color:T.tS,display:"flex",gap:5}}>
<span style={{color:T.tM,fontFamily:M,fontSize:10,minWidth:12}}>{i+1}.</span>{t}
</div>))}</Panel>
<Panel title="Thresholds" accent={T.tM}>
{[{t:"Max position",v:"5%"},{t:"Max sector OW",v:"±5%"},{t:"Factor ceiling",v:"±1.0σ"},{t:"DD trigger",v:"−5%"},{t:"Corr flag",v:"≥0.75"},{t:"Stop loss",v:"−8%"}].map((r,i)=>(<div key={i} style={{display:"flex",justifyContent:"space-between",padding:"4px 0",borderBottom:`1px solid ${T.bLt}`,fontSize:11}}>
<span style={{color:T.tS}}>{r.t}</span><span style={{fontFamily:M,fontWeight:500}}>{r.v}</span>
</div>))}</Panel>
</div></div>)}
{/* MANAGERS */}
{tab==="managers"&&(<div style={{display:"flex",flexDirection:"column",gap:12}}>
{/* Team selector */}
<div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
<div style={{display:"flex",gap:4}}>
{[{id:"all",l:"All Teams"},...TEAMS.map(t=>({id:t.id,l:t.name}))].map(t=>(<button key={t.id} onClick={()=>{setSelTeam(t.id);setSelStrat(null)}} style={{padding:"5px 12px",borderRadius:5,border:`1px solid ${selTeam===t.id?T.accent:T.border}`,background:selTeam===t.id?T.aLt:T.surface,color:selTeam===t.id?T.accent:T.tS,fontSize:11,fontFamily:S,fontWeight:selTeam===t.id?600:400,cursor:"pointer"}}>{t.l}</button>))}
</div>
<Tog opts={[{v:"active",l:"Active"},{v:"all",l:"All"},{v:"inactive",l:"Inactive"}]} value={stratFilter} onChange={setStratFilter}/>
</div>

{/* Team comparison or single team summary */}
{selTeam==="all"?(<>
<div style={{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:10}}>
{TEAMS.map(t=>(<div key={t.id} style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:10,padding:"14px 16px",borderTop:`3px solid ${t.color}`}}>
<div style={{display:"flex",justifyContent:"space-between",marginBottom:8}}><span style={{fontSize:14,fontWeight:700,fontFamily:S}}>{t.name}</span><span style={{fontSize:10,color:T.tM,fontFamily:M}}>{t.lead}</span></div>
<div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:6}}>
<div><div style={{fontSize:9,color:T.tM,fontFamily:M,textTransform:"uppercase"}}>Capital</div><div style={{fontSize:15,fontWeight:600,fontFamily:M}}>{fK(t.capital)}</div><div style={{fontSize:10,color:T.tM}}>{t.capitalPct}% of NAV</div></div>
<div><div style={{fontSize:9,color:T.tM,fontFamily:M,textTransform:"uppercase"}}>Cumul. Return</div><div style={{fontSize:15,fontWeight:600,fontFamily:M,color:pc(t.cumRet)}}>{pp(t.cumRet)}{t.cumRet}%</div><div style={{fontSize:10,color:T.tM}}>AYTD: {pp(t.aytdRet)}{t.aytdRet}%</div></div>
<div><div style={{fontSize:9,color:T.tM,fontFamily:M,textTransform:"uppercase"}}>Sharpe</div><div style={{fontSize:15,fontWeight:600,fontFamily:M,color:t.sharpe>=1.5?T.green:T.tS}}>{t.sharpe}</div></div>
<div><div style={{fontSize:9,color:T.tM,fontFamily:M,textTransform:"uppercase"}}>Strategies</div><div style={{fontSize:15,fontWeight:600,fontFamily:M}}>{t.active}</div><div style={{fontSize:10,color:T.tM}}>{t.inactive} closed</div></div>
</div>
<div style={{display:"flex",gap:3,marginTop:8}}>{Object.entries(t.typeMix).map(([k,v])=>v.count>0&&(<div key={k} style={{flex:v.capital,height:5,borderRadius:3,background:k==="fundamental"?T.accent:k==="systematic"?T.purple:T.green,opacity:.5}}/>))}</div>
<div style={{display:"flex",gap:8,marginTop:4,fontSize:9,color:T.tM,fontFamily:M}}>{Object.entries(t.typeMix).map(([k,v])=>v.count>0&&(<span key={k}>{k.charAt(0).toUpperCase()+k.slice(1,4)}: {v.count}</span>))}</div>
</div>))}
</div>
<div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12}}>
<Panel title="Team Return Overlay" subtitle="AYTD (Base 100)" accent={T.accent}>
<ResponsiveContainer width="100%" height={180}><LineChart data={TEAM_CURVES} margin={{top:4,right:4,bottom:0,left:0}}>
<XAxis dataKey="d" tick={{fontSize:10,fill:T.tM,fontFamily:M}} axisLine={false} tickLine={false}/>
<YAxis tick={{fontSize:10,fill:T.tM,fontFamily:M}} axisLine={false} tickLine={false} domain={[98,"dataMax+2"]}/>
<Tooltip content={<CTip/>}/>
<Line type="monotone" dataKey="alpha" name="Alpha Eq." stroke={T.accent} strokeWidth={2} dot={false}/>
<Line type="monotone" dataKey="quant" name="Quant Sys." stroke={T.purple} strokeWidth={2} dot={false}/>
<Line type="monotone" dataKey="macro" name="Macro" stroke={T.green} strokeWidth={2} dot={false}/>
</LineChart></ResponsiveContainer>
<div style={{display:"flex",gap:14,marginTop:4,fontSize:10,fontFamily:M,color:T.tM}}><span><span style={{color:T.accent}}>━</span> Alpha +{TEAMS[0].aytdRet}%</span><span><span style={{color:T.purple}}>━</span> Quant +{TEAMS[1].aytdRet}%</span><span><span style={{color:T.green}}>━</span> Macro +{TEAMS[2].aytdRet}%</span></div>
</Panel>
<Panel title="Return Attribution" subtitle={attrPeriod} accent={T.purple} right={<Tog opts={[{v:"AYTD",l:"AYTD"},{v:"Max",l:"Max"}]} value={attrPeriod} onChange={setAttrPeriod}/>}>
<div style={{marginBottom:10}}>
<div style={{fontSize:10,fontWeight:600,color:T.tS,marginBottom:5}}>By Team</div>
<table style={{width:"100%",borderCollapse:"collapse",fontSize:11}}><thead><tr style={{borderBottom:`1px solid ${T.border}`}}>{["Source","Weight","Return","Contrib."].map((h,i)=><th key={i} style={{padding:"4px 5px",textAlign:i?"right":"left",fontSize:9,color:T.tM,fontFamily:M,fontWeight:500,textTransform:"uppercase"}}>{h}</th>)}</tr></thead>
<tbody>{ATTRIBUTION.map((a,i)=>(<tr key={i} style={{borderBottom:`1px solid ${T.bLt}`,fontWeight:a.team==="Cash"?400:500}}><td style={{padding:"5px",fontSize:11}}>{a.team}</td><td style={{padding:"5px",textAlign:"right",fontFamily:M,color:T.tM}}>{a.weight}%</td><td style={{padding:"5px",textAlign:"right",fontFamily:M,color:pc(a.ret)}}>{pp(a.ret)}{a.ret}%</td><td style={{padding:"5px",textAlign:"right",fontFamily:M,fontWeight:600,color:pc(a.contrib)}}>{pp(a.contrib)}{a.contrib}%</td></tr>))}</tbody></table>
</div>
<div>
<div style={{fontSize:10,fontWeight:600,color:T.tS,marginBottom:5}}>By Strategy Type</div>
<table style={{width:"100%",borderCollapse:"collapse",fontSize:11}}><thead><tr style={{borderBottom:`1px solid ${T.border}`}}>{["Type","Weight","Return","Contrib."].map((h,i)=><th key={i} style={{padding:"4px 5px",textAlign:i?"right":"left",fontSize:9,color:T.tM,fontFamily:M,fontWeight:500,textTransform:"uppercase"}}>{h}</th>)}</tr></thead>
<tbody>{TYPE_ATTR.map((a,i)=>(<tr key={i} style={{borderBottom:`1px solid ${T.bLt}`}}><td style={{padding:"5px",fontSize:11}}>{a.type}</td><td style={{padding:"5px",textAlign:"right",fontFamily:M,color:T.tM}}>{a.weight}%</td><td style={{padding:"5px",textAlign:"right",fontFamily:M,color:pc(a.ret)}}>{pp(a.ret)}{a.ret}%</td><td style={{padding:"5px",textAlign:"right",fontFamily:M,fontWeight:600,color:pc(a.contrib)}}>{pp(a.contrib)}{a.contrib}%</td></tr>))}</tbody></table>
</div>
</Panel>
</div>
</>):(<>
{/* Single team header */}
{(()=>{const t=TEAMS.find(x=>x.id===selTeam);if(!t)return null;return(<div style={{display:"grid",gridTemplateColumns:"repeat(5,1fr)",gap:8}}>
<Stat label="Capital" value={fK(t.capital)} sub={`${t.capitalPct}% NAV`}/>
<Stat label="Cumul. Return" value={`${pp(t.cumRet)}${t.cumRet}%`} color={pc(t.cumRet)} sub={`AYTD: ${pp(t.aytdRet)}${t.aytdRet}%`}/>
<Stat label="Sharpe" value={t.sharpe.toFixed(2)} color={t.sharpe>=1.5?T.green:T.tS}/>
<Stat label="Win Rate" value={`${t.winRate}%`} sub={`${t.active} active / ${t.inactive} closed`}/>
<Stat label="P&L" value={fK(t.realized+t.unrealized)} sub={`R: ${fK(t.realized)} U: ${fK(t.unrealized)}`} color={pc(t.realized+t.unrealized)}/>
</div>)})()}
</>)}

{/* Strategy table */}
<Panel title="Strategies" subtitle={`${teamStrats.length} shown`} full accent={T.purple}>
<div style={{maxHeight:selStrat?220:340,overflowY:"auto"}}><table style={{width:"100%",borderCollapse:"collapse",fontSize:11}}>
<thead style={{position:"sticky",top:0,background:T.surface,zIndex:1}}><tr style={{borderBottom:`1px solid ${T.border}`}}>
{["Name","Type","Status","Pos","Inception","Last Recon","#R","Invested","Return","AYTD","Realized","Unrealized"].map((h,i)=><th key={i} style={{padding:"5px 5px",textAlign:i>=7?"right":"left",fontSize:9,color:T.tM,fontFamily:M,fontWeight:500,textTransform:"uppercase",whiteSpace:"nowrap"}}>{h}</th>)}
</tr></thead>
<tbody>{teamStrats.map((s,i)=>(<tr key={i} onClick={()=>setSelStrat(selStrat===s.id?null:s.id)} style={{borderBottom:`1px solid ${T.bLt}`,cursor:"pointer",background:selStrat===s.id?T.aLt:"transparent"}} onMouseEnter={e=>{if(selStrat!==s.id)e.currentTarget.style.background=T.sAlt}} onMouseLeave={e=>{if(selStrat!==s.id)e.currentTarget.style.background="transparent"}}>
<td style={{padding:"6px 5px",fontWeight:600,fontSize:11,maxWidth:200,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{s.name}</td>
<td style={{padding:"6px 5px"}}><span style={{padding:"1px 5px",borderRadius:3,fontSize:9,fontFamily:M,background:s.type==="fundamental"?T.aLt:s.type==="systematic"?T.pLt:T.gLt,color:s.type==="fundamental"?T.accent:s.type==="systematic"?T.purple:T.green}}>{s.type.slice(0,5)}</span></td>
<td style={{padding:"6px 5px"}}><span style={{display:"inline-block",width:6,height:6,borderRadius:"50%",background:s.status==="active"?T.green:T.tM,marginRight:4}}/><span style={{fontSize:10,color:s.status==="active"?T.green:T.tM}}>{s.status}</span></td>
<td style={{padding:"6px 5px",fontFamily:M,fontSize:10}}>{s.positions}</td>
<td style={{padding:"6px 5px",fontFamily:M,fontSize:9,color:T.tM}}>{s.inception}</td>
<td style={{padding:"6px 5px",fontFamily:M,fontSize:9,color:s.lastRecon?T.tS:T.tM}}>{s.lastRecon||"—"}</td>
<td style={{padding:"6px 5px",fontFamily:M,fontSize:10,color:T.tM}}>{s.reconCount}</td>
<td style={{padding:"6px 5px",textAlign:"right",fontFamily:M}}>{s.invested?fK(s.invested):"—"}</td>
<td style={{padding:"6px 5px",textAlign:"right",fontFamily:M,fontWeight:600,color:pc(s.cumRet)}}>{pp(s.cumRet)}{s.cumRet}%</td>
<td style={{padding:"6px 5px",textAlign:"right",fontFamily:M,color:s.aytdRet?pc(s.aytdRet):T.tM}}>{s.aytdRet?`${pp(s.aytdRet)}${s.aytdRet}%`:"—"}</td>
<td style={{padding:"6px 5px",textAlign:"right",fontFamily:M,color:pc(s.realized)}}>{s.realized?`${pp(s.realized)}${fK(Math.abs(s.realized))}`:"—"}</td>
<td style={{padding:"6px 5px",textAlign:"right",fontFamily:M,color:pc(s.unrealized)}}>{s.unrealized?`${pp(s.unrealized)}${fK(Math.abs(s.unrealized))}`:"—"}</td>
</tr>))}</tbody></table></div></Panel>

{/* Strategy Detail */}
{selStratData&&(<Panel title={selStratData.name} subtitle={`${selStratData.type} · ${selStratData.status}`} full accent={selStratData.type==="fundamental"?T.accent:selStratData.type==="systematic"?T.purple:T.green}>
<div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:16}}>
<div>
<div style={{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:6,marginBottom:12}}>
<div style={{background:T.sAlt,borderRadius:5,padding:"7px 9px"}}><div style={{fontSize:9,color:T.tM,fontFamily:M,textTransform:"uppercase"}}>Cumul. Return</div><div style={{fontSize:16,fontWeight:600,fontFamily:M,color:pc(selStratData.cumRet)}}>{pp(selStratData.cumRet)}{selStratData.cumRet}%</div></div>
<div style={{background:T.sAlt,borderRadius:5,padding:"7px 9px"}}><div style={{fontSize:9,color:T.tM,fontFamily:M,textTransform:"uppercase"}}>Realized</div><div style={{fontSize:16,fontWeight:600,fontFamily:M,color:pc(selStratData.realized)}}>{selStratData.realized?`${pp(selStratData.realized)}${fK(Math.abs(selStratData.realized))}`:"—"}</div></div>
<div style={{background:T.sAlt,borderRadius:5,padding:"7px 9px"}}><div style={{fontSize:9,color:T.tM,fontFamily:M,textTransform:"uppercase"}}>Unrealized</div><div style={{fontSize:16,fontWeight:600,fontFamily:M,color:pc(selStratData.unrealized)}}>{selStratData.unrealized?`${pp(selStratData.unrealized)}${fK(Math.abs(selStratData.unrealized))}`:"—"}</div></div>
</div>
{/* Current positions */}
<div style={{fontSize:11,fontWeight:600,color:T.tS,marginBottom:5}}>Current Positions</div>
{selStratData.tickers.length>0?(<div style={{display:"flex",flexWrap:"wrap",gap:4}}>{selStratData.tickers.map(t=>{const p=ALL_POS.find(x=>x.ticker===t);return(<div key={t} style={{padding:"5px 8px",background:T.sAlt,borderRadius:5,border:`1px solid ${T.bLt}`}}>
<div style={{fontFamily:M,fontWeight:600,fontSize:11}}>{t}</div>
{p&&<div style={{display:"flex",gap:8,fontSize:10,color:T.tM,marginTop:2}}><span>{p.weight}%</span><span style={{color:pc(p.pnl)}}>{pp(p.pnl)}{p.pnl}%</span></div>}
</div>)})}</div>):(<div style={{fontSize:11,color:T.tM,fontStyle:"italic"}}>All positions closed</div>)}
{/* Reconstruction timeline */}
{selStratData.reconHistory&&selStratData.reconHistory.length>0&&(<div style={{marginTop:12}}>
<div style={{fontSize:11,fontWeight:600,color:T.tS,marginBottom:5}}>Reconstruction History</div>
{selStratData.reconHistory.map((r,i)=>(<div key={i} style={{padding:"8px 10px",marginBottom:4,background:T.sAlt,borderRadius:6,borderLeft:`3px solid ${T.purple}`}}>
<div style={{display:"flex",justifyContent:"space-between",marginBottom:3}}><span style={{fontFamily:M,fontSize:10,fontWeight:600}}>{r.date}</span><span style={{fontFamily:M,fontSize:10,color:T.tM}}>{r.period}</span><span style={{fontFamily:M,fontSize:10,color:pc(r.priorRet)}}>Period: {pp(r.priorRet)}{r.priorRet}%</span></div>
<div style={{display:"flex",gap:10,marginBottom:3,fontSize:10}}>{r.out.length>0&&<span style={{color:T.red}}>Out: {r.out.join(", ")}</span>}{r.inn.length>0&&<span style={{color:T.green}}>In: {r.inn.join(", ")}</span>}</div>
{r.note&&<div style={{fontSize:10,color:T.tS,lineHeight:1.4}}>{r.note}</div>}
</div>))}
</div>)}
</div>
<div>
<div style={{fontSize:11,fontWeight:600,color:T.tS,marginBottom:5}}>Strategy Return Index</div>
<ResponsiveContainer width="100%" height={180}><AreaChart data={stratReturnCurve} margin={{top:4,right:4,bottom:0,left:0}}>
<defs><linearGradient id="sg" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={selStratData.cumRet>=0?T.green:T.red} stopOpacity={.12}/><stop offset="100%" stopColor={selStratData.cumRet>=0?T.green:T.red} stopOpacity={0}/></linearGradient></defs>
<XAxis dataKey="d" tick={{fontSize:10,fill:T.tM,fontFamily:M}} axisLine={false} tickLine={false}/>
<YAxis tick={{fontSize:10,fill:T.tM,fontFamily:M}} axisLine={false} tickLine={false} domain={["dataMin-2","dataMax+2"]}/>
<Tooltip content={<CTip/>}/>
{selStratData.reconHistory&&selStratData.reconHistory.map((r,i)=><ReferenceLine key={i} x={r.date.startsWith("2025-10")?"Nov":r.date.startsWith("2025-11")?"Nov":r.date.startsWith("2026-01")?"Jan":"Oct"} stroke={T.purple} strokeDasharray="4 3" strokeWidth={1}/>)}
<Area type="monotone" dataKey="idx" name="Index" stroke={selStratData.cumRet>=0?T.green:T.red} strokeWidth={2} fill="url(#sg)"/>
</AreaChart></ResponsiveContainer>
<div style={{display:"flex",gap:12,marginTop:4,fontSize:10,fontFamily:M,color:T.tM}}>
<span>Inception: {selStratData.inception}</span>
<span>Duration: {Math.round((new Date()-new Date(selStratData.inception))/(86400000))}d</span>
{selStratData.reconCount>0&&<span style={{color:T.purple}}>┊ = reconstruction</span>}
</div>
<div style={{marginTop:10,padding:"8px 10px",background:T.sAlt,borderRadius:6}}>
<div style={{fontSize:9,color:T.tM,fontFamily:M,textTransform:"uppercase",marginBottom:3}}>Strategy Info</div>
<div style={{display:"grid",gridTemplateColumns:"70px 1fr",gap:2,fontSize:10}}>
<span style={{color:T.tM}}>Team:</span><span>{TEAMS.find(t=>t.id===selStratData.teamId)?.name}</span>
<span style={{color:T.tM}}>Type:</span><span style={{textTransform:"capitalize"}}>{selStratData.type}</span>
<span style={{color:T.tM}}>Recon:</span><span>{selStratData.reconCount} ({selStratData.type==="fundamental"?"N/A":"quarterly"})</span>
<span style={{color:T.tM}}>Status:</span><span style={{color:selStratData.status==="active"?T.green:T.tM,textTransform:"capitalize"}}>{selStratData.status}</span>
</div>
</div>
</div>
</div>
</Panel>)}
</div>)}
</main>
<footer style={{borderTop:`1px solid ${T.border}`,padding:"8px 24px",display:"flex",justifyContent:"space-between",fontSize:10,color:T.tM,fontFamily:M}}>
<span>Meridian · v5.0</span><span>{new Date().toLocaleTimeString()}</span>
</footer></div>);}
