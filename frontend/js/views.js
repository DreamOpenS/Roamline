let plans = [];
let checkoutPlan = null;
let payMethod = "card";
let currentAccount = null;

function show(id){
  ["view-market","view-checkout","view-processing","view-mine","view-wallet","view-dash"]
    .forEach(v => document.getElementById(v).classList.toggle("hidden", v!==id));
}

function renderPlans(){
  const grid = document.getElementById("planGrid");
  grid.innerHTML = "";
  document.getElementById("planCount").textContent = plans.length;
  document.getElementById("catalogueCount").textContent = String(plans.length).padStart(2,"0") + " entries";
  for(const p of plans){
    const el = document.createElement("div");
    el.className = "plan";
    el.innerHTML = `
      <div class="plan-top">
        <span class="plan-region">${p.region}</span>
        <span class="plan-days">${p.days} days</span>
      </div>
      <div class="plan-data">${fmtMB(p.data_mb)}</div>
      <div class="plan-name">${p.name}</div>
      <div class="plan-foot">
        <div class="plan-price">${money(p.price)}<small>one-off</small></div>
        <button class="buy" data-plan="${p.id}">Buy</button>
      </div>`;
    el.querySelector("button").addEventListener("click", () => startCheckout(p));
    grid.appendChild(el);
  }
}

function startCheckout(p){
  checkoutPlan = p;
  renderPayMethods();
  document.getElementById("orderSummary").innerHTML = `
    <div class="label">Order summary</div>
    <div class="big">${fmtMB(p.data_mb)}</div>
    <div class="sub">${p.name} · ${p.region}</div>
    <div class="rowline"><span>Validity</span><b>${p.days} days</b></div>
    <div class="rowline"><span>Activation</span><b>Instant</b></div>
    <div class="rowline"><span>Total</span><b>${money(p.price)}</b></div>`;
  show("view-checkout");
}

function renderPayMethods(){
  const box = document.getElementById("payMethodBox");
  box.innerHTML = "";
  const cards = [
    {id:"card", label:"Card", sub:"simulated"},
    {id:"credits", label:"Credits", sub: currentAccount ? `balance ${money(currentAccount.balance)}` : "sign in first"}
  ];
  for(const c of cards){
    const b = document.createElement("button");
    if(payMethod === c.id) b.classList.add("active");
    b.disabled = c.id === "credits" && !currentAccount;
    b.innerHTML = `${c.label}<small>${c.sub}</small>`;
    b.addEventListener("click", () => { payMethod = c.id; renderPayMethods(); });
    box.appendChild(b);
  }
}

function backToMarket(){ show("view-market"); }

function buildCountrySel(){
  const sel = document.getElementById("countrySel");
  sel.innerHTML = "";
  for(const c of COUNTRIES){
    const o = document.createElement("option");
    o.value = c.code; o.textContent = `${c.flag} ${c.name}`;
    sel.appendChild(o);
  }
  sel.value = ui.country || "IQ"; // Defaults to Iraq
  sel.onchange = () => {
    ui.country = sel.value;
    save();
    const selectedCountry = COUNTRIES.find(c=>c.code===sel.value);
    pushLog(`Roamed to ${selectedCountry.name}`, 0);
    renderDash();
  };
}

async function renderDash(){
  let e;
  try{ e = await apiFetchEsim(ui.activeIccid); }
  catch(err){ show("view-market"); return; }

  const pct = e.total_mb > 0 ? (e.left_mb / e.total_mb) * 100 : 0;
  document.getElementById("leftBig").innerHTML = fmtMB(e.left_mb) + ` <small>left of ${fmtMB(e.total_mb)}</small>`;
  document.getElementById("barFill").style.width = pct + "%";
  document.getElementById("usedMeta").textContent = fmtMB(e.used_mb) + " used";
  document.getElementById("pctMeta").textContent = pct.toFixed(0) + "% remaining";
  document.getElementById("qrImg").src = e.qr_data_uri;

  // --- NEW: Update Carrier + Speed ---
  const currentCountry = COUNTRIES.find(c => c.code === (ui.country || "IQ")) || COUNTRIES[0];
  document.getElementById("networkCarrier").textContent = `${currentCountry.carrier}`;
  
  // Fake latency/speed based on country
  const latencies = { IQ: "42ms", KRD: "38ms", AE: "18ms", TR: "55ms", SA: "45ms", US: "120ms", FR: "85ms" };
  const latency = latencies[currentCountry.code] || "50ms";
  document.getElementById("speedDisplay").innerHTML = `📶 5G · ${latency} · <span style="color:#c8442b">Test</span>`;

  const slot = document.getElementById("bannerSlot");
  slot.innerHTML = "";
  if(e.status === "expired") slot.innerHTML = `<div class="banner dark">Plan expired. Buy a new plan to reconnect.</div>`;
  else if(e.status === "depleted" || e.left_mb === 0) slot.innerHTML = `<div class="banner dark">Data exhausted. Top up below.</div>`;
  else if(pct <= 10) slot.innerHTML = `<div class="banner">Less than ${fmtMB(e.left_mb)} left. Top up soon.</div>`;
  else if(pct <= 30) slot.innerHTML = `<div class="banner">${pct.toFixed(0)}% data remaining.</div>`;

  const ug = document.getElementById("usageGrid");
  ug.innerHTML = "";
  for(const u of USAGE){
    const b = document.createElement("button");
    b.disabled = e.expired || e.left_mb === 0;
    b.innerHTML = `${u.label}<small>${u.cost} MB · ${u.unit}</small>`;
    b.addEventListener("click", () => burn(u.cost));
    ug.appendChild(b);
  }

  await renderPacks();
  renderLog();
}

async function renderPacks(){
  const pg = document.getElementById("packsGrid");
  pg.innerHTML = "";
  try{
    const packs = await apiTopupPacks();
    for(const p of packs){
      const b = document.createElement("button");
      b.innerHTML = `${p.label}<small>${money(p.price)}</small>`;
      b.addEventListener("click", () => doTopup(p.id));
      pg.appendChild(b);
    }
  }catch(e){}
}

function renderLog(){
  const rows = document.getElementById("logRows");
  const log = ui.log || [];
  if(!log.length){ rows.innerHTML = `<div class="log-empty">No activity yet.</div>`; return; }
  rows.innerHTML = log.slice().reverse().map(e => `
    <div class="log-row">
      <span>${e.text}</span>
      <span class="${e.cost?"neg":""}" style="${e.cost?"":"color:var(--ink-soft)"}">${e.cost?"-"+fmtMB(e.cost):new Date(e.at).toLocaleTimeString()}</span>
    </div>`).join("");
}

async function renderMine(){
  if(!currentAccount){ goMarket(); return; }
  const grid = document.getElementById("mineGrid");
  grid.innerHTML = "";
  try{
    const list = await apiListEsims(currentAccount.account_id);
    document.getElementById("mineCount").textContent = list.length + " plans";
    if(!list.length){
      grid.innerHTML = `<div class="mine-empty">No eSIMs yet. Buy one from the catalogue.</div>`;
      return;
    }
    for(const e of list){
      const el = document.createElement("div");
      el.className = "esim-card";
      el.innerHTML = `
        <div class="ec-top">
          <span class="ec-plan">${e.plan_name}</span>
          <span class="ec-status ${e.status}">${e.status}</span>
        </div>
        <div class="ec-region">${e.region}</div>
        <div class="ec-data">${fmtMB(e.left_mb)} <span style="font-family:var(--sans);font-size:14px;color:var(--ink-soft)">left</span></div>
        <div class="ec-meta">${fmtMB(e.used_mb)} used · expires ${new Date(e.expires_at).toLocaleDateString()}</div>`;
      el.addEventListener("click", () => openEsim(e.iccid));
      grid.appendChild(el);
    }
  }catch(err){ grid.innerHTML = `<div class="mine-empty">Could not load eSIMs.</div>`; }
}

async function renderWallet(){
  if(!currentAccount){ goMarket(); return; }
  document.getElementById("walletBalance").textContent = money(currentAccount.balance);
  try{
    const packs = await apiCreditPacks();
    const box = document.getElementById("creditPacks");
    box.innerHTML = "";
    for(const p of packs){
      const b = document.createElement("button");
      b.innerHTML = `${p.label}<small>${p.label}</small>`;
      b.addEventListener("click", () => doAddCredits(p.id));
      box.appendChild(b);
    }
  }catch(e){}
  try{
    const hist = await apiCreditHistory(currentAccount.account_id);
    const rows = document.getElementById("txnRows");
    if(!hist.length){ rows.innerHTML = `<div class="log-empty">No transactions yet.</div>`; return; }
    rows.innerHTML = hist.map(t => `
      <div class="log-row">
        <span>${t.kind}</span>
        <span class="${t.amount<0?"neg":""}">${t.amount>0?"+":""}${money(t.amount)}</span>
      </div>`).join("");
  }catch(e){}
}