const API = "http://127.0.0.1:8000";

async function apiFetchPlans(){
  const r = await fetch(API + "/api/plans");
  if(!r.ok) throw new Error("plans fetch failed");
  return r.json();
}

async function apiSignup(name, email){
  const r = await fetch(API + "/api/accounts/signup", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({name, email})
  });
  if(!r.ok) throw new Error("signup failed");
  return r.json();
}

async function apiGetAccount(accountId){
  const r = await fetch(API + `/api/accounts/${accountId}`);
  if(!r.ok) throw new Error("account fetch failed");
  return r.json();
}

async function apiCreditPacks(){
  const r = await fetch(API + "/api/credits/packs");
  if(!r.ok) throw new Error("packs fetch failed");
  return r.json();
}

async function apiAddCredits(accountId, packId){
  const r = await fetch(API + `/api/credits/${accountId}/add`, {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({account_id: accountId, pack_id: packId})
  });
  if(!r.ok) throw new Error("add credits failed");
  return r.json();
}

async function apiBuy(planId, email, accountId, payWithCredits, dataMb = null, days = null){
  const r = await fetch(API + "/api/buy", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({
      plan_id: planId, 
      email: email, 
      account_id: accountId, 
      pay_with_credits: !!payWithCredits,
      custom_data_mb: dataMb,
      custom_days: days
    })
  });
  if(!r.ok) throw new Error("buy failed");
  return r.json();
}

async function apiFetchEsim(iccid){
  const r = await fetch(API + "/api/esims/" + iccid);
  if(!r.ok) throw new Error("esim fetch failed");
  return r.json();
}

async function apiListEsims(accountId){
  const r = await fetch(API + `/api/accounts/${accountId}/esims`);
  if(!r.ok) throw new Error("esims list failed");
  return r.json();
}

async function apiBurn(iccid, mb){
  const r = await fetch(API + `/api/esims/${iccid}/usage`, {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({mb})
  });
  if(!r.ok) throw new Error("burn failed");
  return r.json();
}

async function apiTopupPacks(){
  const r = await fetch(API + "/api/topup/packs");
  if(!r.ok) throw new Error("packs fetch failed");
  return r.json();
}

async function apiTopup(iccid, packId){
  const r = await fetch(API + `/api/esims/${iccid}/topup`, {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({pack_id: packId})
  });
  if(!r.ok) throw new Error("topup failed");
  return r.json();
}

async function apiCreditHistory(accountId){
  const r = await fetch(API + `/api/credits/${accountId}/history`);
  if(!r.ok) throw new Error("history failed");
  return r.json();
}

async function apiLogCall(accountId, number, durationSec){
  const r = await fetch(API + "/api/calls", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({account_id: accountId, number, duration_sec: durationSec})
  });
  if(!r.ok) throw new Error("log call failed");
  return r.json();
}

async function apiBuyCustom(accountId, email, dataGb, days){
  const r = await fetch(API + "/api/custom-buy", {
    method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({account_id: accountId, email: email, data_gb: dataGb, days: days})
  });
  if(!r.ok) throw new Error("custom buy failed");
  return r.json();
}