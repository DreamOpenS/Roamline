let dialString = "";
let callInterval = null;
let callDuration = 0;
let isCalling = false;

async function initPlans(){
  try{
    plans = await apiFetchPlans();
    renderPlans();
  }catch(e){
    document.getElementById("planGrid").innerHTML = `<div style="padding:40px;color:var(--accent);font-style:italic">Backend unreachable.</div>`;
  }
}

function applyAccountHeader(){
  const emailEl = document.getElementById("headEmail");
  const balEl = document.getElementById("headBalance");
  const cta = document.getElementById("headCta");
  const navMine = document.getElementById("navMine");
  const navWallet = document.getElementById("navWallet");

  if(currentAccount){
    emailEl.textContent = currentAccount.email;
    balEl.textContent = money(currentAccount.balance);
    balEl.classList.remove("hidden");
    cta.textContent = "Sign out";
    cta.onclick = signOut;
    navMine.classList.remove("hidden");
    navWallet.classList.remove("hidden");
    document.getElementById("navDialer").classList.remove("hidden");
  } else {
    emailEl.textContent = "not signed in";
    balEl.classList.add("hidden");
    cta.textContent = "Sign in";
    cta.onclick = openSignup;
    navMine.classList.add("hidden");
    navWallet.classList.add("hidden");
    document.getElementById("navDialer").classList.add("hidden");
  }
}

function openSignup(){
  if(currentAccount){ signOut(); return; }
  document.getElementById("modalSignup").classList.remove("hidden");
}

function closeModal(id){
  document.getElementById(id).classList.add("hidden");
}

async function doSignup(){
  const name = document.getElementById("signupName").value.trim();
  const email = document.getElementById("signupEmail").value.trim();
  if(!name || !email) return;
  try{
    const acct = await apiSignup(name, email);
    currentAccount = acct;
    ui.accountId = acct.account_id;
    save();
    applyAccountHeader();
    closeModal("modalSignup");
  }catch(e){ alert("Sign-in failed. Check backend."); }
}

function signOut(){
  currentAccount = null;
  ui.accountId = null;
  save();
  applyAccountHeader();
  goMarket();
}

async function pay(){
  if(!checkoutPlan) return;
  const email = document.getElementById("buyerEmail").value.trim() || (currentAccount ? currentAccount.email : "");
  if(!email){ document.getElementById("buyerEmail").focus(); return; }

  if(payMethod === "credits" && (!currentAccount || currentAccount.balance < checkoutPlan.price)){
    alert("Insufficient credits. Add credit in the wallet.");
    return;
  }

  show("view-processing");
  try{
    const data = await apiBuy(
      checkoutPlan.id,
      email,
      currentAccount ? currentAccount.account_id : null,
      payMethod === "credits"
    );
    ui.log = [{at:Date.now(), text:`Activated ${checkoutPlan.name}`, cost:0}];
    ui.activeIccid = data.iccid;
    ui.country = ui.country || "FR";
    save();
    if(data.new_balance !== null && data.new_balance !== undefined && currentAccount){
      currentAccount = await apiGetAccount(currentAccount.account_id);
      applyAccountHeader();
    }
    checkoutPlan = null;
    await enterDash();
  }catch(e){
    show("view-market");
    alert("Purchase failed.");
  }
}

async function enterDash(){
  if(!ui.activeIccid){ show("view-market"); return; }
  buildCountrySel();
  await renderDash();
  show("view-dash");
}

function openEsim(iccid){
  ui.activeIccid = iccid;
  save();
  enterDash();
}

async function burn(mb){
  try{
    await apiBurn(ui.activeIccid, mb);
    pushLog("Data used", mb);
    await renderDash();
  }catch(e){}
}

async function doTopup(packId){
  try{
    const data = await apiTopup(ui.activeIccid, packId);
    pushLog(`Top-up · ${fmtMB(data.added_mb)}`, 0);
    await renderDash();
  }catch(e){}
}

async function doAddCredits(packId){
  if(!currentAccount) return;
  try{
    const res = await apiAddCredits(currentAccount.account_id, packId);
    currentAccount = await apiGetAccount(currentAccount.account_id);
    applyAccountHeader();
    await renderWallet();
  }catch(e){ alert("Could not add credits."); }
}

async function apiCreditHistory(accountId){
  const r = await fetch(API + `/api/credits/${accountId}/history`);
  if(!r.ok) throw new Error("history failed");
  return r.json();
}

function goMarket(){ show("view-market"); }
async function goMine(){ show("view-mine"); await renderMine(); }
async function goWallet(){ show("view-wallet"); await renderWallet(); }

document.getElementById("payBtn").addEventListener("click", pay);

(async () => {
  await initPlans();
  if(ui.accountId){
    try{
      currentAccount = await apiGetAccount(ui.accountId);
    }catch(e){ currentAccount = null; }
  }
  applyAccountHeader();
  if(ui.activeIccid) enterDash();
  else show("view-market");
})();

function goDialer(){
  document.getElementById("modalDialer").classList.remove("hidden");
  dialString = "";
  document.getElementById("dialerDisplay").textContent = "Enter number";
  document.getElementById("callBtn").classList.remove("hidden");
  document.getElementById("endBtn").classList.add("hidden");
  isCalling = false;
}

function dialNum(num){
  if(isCalling) return;
  dialString += num;
  document.getElementById("dialerDisplay").textContent = dialString;
}

function startCall(){
  if(!dialString || !currentAccount) return;
  if(currentAccount.balance < 0.1){
    alert("Insufficient credits for a call.");
    return;
  }
  isCalling = true;
  callDuration = 0;
  document.getElementById("callBtn").classList.add("hidden");
  document.getElementById("endBtn").classList.remove("hidden");
  
  callInterval = setInterval(() => {
    callDuration++;
    const m = Math.floor(callDuration / 60).toString().padStart(2, '0');
    const s = (callDuration % 60).toString().padStart(2, '0');
    document.getElementById("dialerDisplay").textContent = `${m}:${s}`;
  }, 1000);
}

async function endCall(){
  if(!isCalling) return;
  isCalling = false;
  clearInterval(callInterval);
  
  document.getElementById("dialerDisplay").textContent = "Calling...";
  
  try {
    const res = await apiLogCall(currentAccount.account_id, dialString, callDuration);
    currentAccount.balance = res.new_balance;
    applyAccountHeader();
    document.getElementById("dialerDisplay").textContent = `Cost: ${money(res.cost)}`;
    setTimeout(() => closeModal("modalDialer"), 1500);
  } catch(e) {
    document.getElementById("dialerDisplay").textContent = "Error saving call";
  }
}

function runSpeedTest(){
  const el = document.getElementById("speedDisplay");
  const original = el.innerHTML;
  el.innerHTML = `📶 Testing...`;
  setTimeout(() => {
    const currentCountry = COUNTRIES.find(c => c.code === (ui.country || "IQ")) || COUNTRIES[0];
    const speeds = { IQ: "45 Mbps", KRD: "60 Mbps", AE: "180 Mbps", TR: "75 Mbps", US: "220 Mbps", FR: "150 Mbps" };
    const speed = speeds[currentCountry.code] || "50 Mbps";
    el.innerHTML = `📶 ${speed} · <span style="color:#0a7a52">Fast</span>`;
    setTimeout(() => { el.innerHTML = original; }, 3000);
  }, 1500);
}

function openCustomBuilder(){
  if(!currentAccount){ 
    alert("Please sign in first."); 
    return; 
  }
  console.log("Opening custom builder...");
  document.getElementById("modalCustom").classList.remove("hidden");
  updateCustomPrice();
}

function updateCustomPrice(){
  const gb = parseInt(document.getElementById("customData").value);
  const days = parseInt(document.getElementById("customDays").value);
  const price = (gb * 3) + (days * 1);
  
  document.getElementById("customDataLabel").textContent = `${gb} GB`;
  document.getElementById("customDaysLabel").textContent = `${days} Days`;
  document.getElementById("customPrice").textContent = `$${price.toFixed(2)}`;
}

async function buyCustomPlan(){
  const gb = parseInt(document.getElementById("customData").value);
  const days = parseInt(document.getElementById("customDays").value);
  const price = (gb * 3) + (days * 1);

  if(currentAccount.balance < price){
    alert("Insufficient credits. Add funds to your wallet.");
    return;
  }

  try {
    const res = await apiBuyCustom(currentAccount.account_id, currentAccount.email, gb, days);
    
    // Update local wallet and state
    currentAccount = await apiGetAccount(currentAccount.account_id);
    applyAccountHeader();

    ui.log = [{at:Date.now(), text:`Activated Custom Plan: ${gb}GB / ${days} Days`, cost:0}];
    ui.activeIccid = res.iccid;
    ui.country = ui.country || "IQ";
    save();
    
    closeModal("modalCustom");
    alert(`Success! ${gb}GB / ${days} Days activated. Paid $${price.toFixed(2)}.`);
    enterDash();

  } catch(e) {
    alert("Purchase failed. Check backend terminal.");
    console.error(e);
  }
}