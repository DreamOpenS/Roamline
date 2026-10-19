const STORE = "roamline.frontend.v1";

let ui = load();

function load(){
  try{ return JSON.parse(localStorage.getItem(STORE)) || {}; }
  catch(e){ return {}; }
}

function save(){
  localStorage.setItem(STORE, JSON.stringify(ui));
}

function resetApp(){
  if(!confirm("Reset simulator? Deletes local state.")) return;
  localStorage.removeItem(STORE);
  ui = {};
  location.reload();
}

const COUNTRIES = [
  {code:"IQ",name:"Iraq",flag:"🇮🇶",carrier:"Asiacell"},
  {code:"KRD",name:"Kurdistan",flag:"☀️",carrier:"Korek Telecom"},
  {code:"AE",name:"UAE",flag:"🇦🇪",carrier:"Etisalat"},
  {code:"TR",name:"Turkey",flag:"🇹🇷",carrier:"Turkcell"},
  {code:"SA",name:"Saudi Arabia",flag:"🇸🇦",carrier:"STC"},
  {code:"JO",name:"Jordan",flag:"🇯🇴",carrier:"Zain"},
  {code:"LB",name:"Lebanon",flag:"🇱🇧",carrier:"Alfa"},
  {code:"QA",name:"Qatar",flag:"🇶🇦",carrier:"Ooredoo"},
  {code:"KW",name:"Kuwait",flag:"🇰🇼",carrier:"Zain"},
  {code:"OM",name:"Oman",flag:"🇴🇲",carrier:"Omantel"},
  {code:"BH",name:"Bahrain",flag:"🇧🇭",carrier:"Batelco"},
  {code:"FR",name:"France",flag:"🇫🇷",carrier:"Orange"},
  {code:"US",name:"United States",flag:"🇺🇸",carrier:"T-Mobile"},
];

const USAGE = [
  {label:"Maps",cost:6,unit:"~10 min"},
  {label:"Web browsing",cost:12,unit:"~10 min"},
  {label:"Social scrolling",cost:45,unit:"~15 min"},
  {label:"Video streaming",cost:180,unit:"~10 min"},
  {label:"Voice call",cost:3,unit:"~5 min"},
  {label:"Photo upload",cost:8,unit:"~1 photo"},
];

function fmtMB(mb){
  if(mb>=1024) return (mb/1024).toFixed(2).replace(/\.?0+$/,"") + " GB";
  return Math.round(mb) + " MB";
}

function money(n){ return "$" + n.toFixed(2); }

function pushLog(text, cost){
  ui.log = ui.log || [];
  ui.log.push({at:Date.now(), text, cost});
  save();
}