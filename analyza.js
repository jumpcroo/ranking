/* ===================== ROZBOR ZÁVODNICE =====================
   Podklady z build.py:
     DATA.fields  pole každého eventu z oficiálních výsledků (vč. zahraničních
                  oddílů): [soutěž, disciplína, pohlaví, věk, úroveň, způsob,
                  záznamy[[skóre, umístění, oddíl, [D,P,Q,M]|0, index výkonu|-1]]]
     výkon.fv/pl  pole a oficiální umístění
     výkon.fs     rozpad freestylu, výkon.sm srážka za chybný start (rychlost)
   Co je přímo z výsledků, je přesné. Výpočty typu „kdyby nebyly chyby“ jsou
   odhad a v textu jsou tak označené. */
const FIELDS=DATA.fields||[],CLUBS=DATA.clubs||[];
const PRES_LAB={ent:'Entertainment',form:'Provedení (form)',music:'Hudebnost',crea:'Kreativita',vari:'Pestrost'};
const PRES_ORDER=['ent','form','music','crea','vari'];
const DT_LAB={p:'power / gymnastika',m:'multiples',r:'rope manipulation',a:'obtížnost A',b:'obtížnost B',j:'jumper',t:'turner'};
const REQ_LAB={p:'power / gymnastika',m:'multiples',r:'rope manipulation',i:'interakce'};
const LV_SR=['0,5','1','2','3','4','5','6','7','8'],LV_DD=['1','2','3','4','5'];
const presCoef=fs=>fs&&fs.fm==='dd'?2*0.4/24:2*0.6/24;
const isSpeed=d=>!['SRIF','SRPF','SRTF','DDSF','DDPF','WHPF','SCTF'].includes(d);

function skoky(n){const a=Math.abs(n);const t=Number.isInteger(a)?(a===1?'skok':(a>=2&&a<=4?'skoky':'skoků')):'skoku';return fmt(a)+' '+t;}
function body(n){const a=Math.round(Math.abs(n)*100)/100;
  const t=!Number.isInteger(a)?'bodu':(a===1?'bod':(a>=2&&a<=4?'body':'bodů'));return fmt(a)+' '+t;}
/* sloveso podle čísla: chyběl 1 skok / chyběly 2 skoky / chybělo 5 skoků i 1,5 skoku */
function chybelo(n){const a=Math.abs(n);return Number.isInteger(a)?(a===1?'chyběl':(a>=2&&a<=4?'chyběly':'chybělo')):'chybělo';}
/* rod podle závodníka: byla / byl, u neznámého byl(a) */
let _gen=null;
const byl=()=>_gen==='Female'?'byla':_gen==='Male'?'byl':'byl(a)';
function pct(x){return Math.round(x*100)+' %';}
function fieldOf(p){if(p.fv==null||!FIELDS[p.fv])return null;const f=FIELDS[p.fv];
  return{comp:f[0],disc:f[1],gen:f[2],age:f[3],lc:f[4],how:f[5],e:f[6]};}
function clubOf(e){return CLUBS[e[2]]||'?';}

/* Odstupy na umístění: vždy proti CELÉMU poli z výsledkovky. U sloučené
   kategorie je v poli i druhá kategorie, se kterou byla vyhodnocena. */
function gapInfo(p){
  const f=fieldOf(p);if(!f)return null;
  const me=p.score,pl=p.pl,n=f.e.length,targets=[];
  const best=k=>{const c=f.e.filter(e=>e[1]!=null&&e[1]<=k);return c.length?c.reduce((m,e)=>e[0]<m[0]?e:m):null;};
  if(pl>1){
    const above=f.e.filter(e=>e[1]!=null&&e[1]<pl);
    const next=above.reduce((m,e)=>(m==null||e[1]>m[1]||(e[1]===m[1]&&e[0]<m[0]))?e:m,null);
    if(next)targets.push({k:next[1],e:next,lab:'o místo výš'});
    if(pl>3){const b=best(3);if(b&&(!next||b[1]!==next[1]))targets.push({k:b[1],e:b,lab:'na bednu'});}
    const w=f.e.find(e=>e[1]===1);
    if(w&&!targets.some(t=>t.k===1))targets.push({k:1,e:w,lab:'na 1. místo'});
  }
  return{f,n,pl,me,targets:targets.map(t=>({k:t.k,lab:t.lab,score:t.e[0],club:clubOf(t.e),gap:Math.round((t.e[0]-me)*100)/100}))};
}

/* Kam by se výkon zařadil se skóre x (pro „kdyby“). U shody sdílí místo. */
function placeWith(f,x,self){
  let better=0;for(const e of f.e){if(e[4]===self)continue;if(e[0]>x+1e-9)better++;}
  return better+1;
}

/* Rozpad freestylu: ztráty a odhad bez chyb */
function fsAnalysis(p){
  const fs=p.fs;if(!fs||fs.D==null)return null;
  const D=fs.D,Pp=fs.P||0,Q=fs.Q==null?1:fs.Q,M=fs.M==null?1:fs.M;
  const base=D*(1+Pp);
  const ded=Math.max(0,1-M),raw=(fs.xm||0)+(fs.xb||0)+(fs.xv||0);
  const share=k=>raw>0?(fs[k]||0)/raw:0;
  const dedLoss=base*Q*ded;                      // přesně: R bez srážek − R (z oficiálních složek)
  const loss={miss:dedLoss*share('xm'),brk:dedLoss*share('xb'),viol:dedLoss*share('xv'),
              req:fs.fm==='dd'?0:base*M*(1-Q)};
  const coef=presCoef(fs);
  loss.presMiss=D*coef*(fs.pm||0)*Q*M;           // odhad: každý miss strhává i v prezentaci
  const clean=D*(1+Pp+coef*(fs.pm||0));          // odhad: bez missů, breaků, porušení a se všemi povinnými prvky
  const f=fieldOf(p);
  const cleanPlace=f?placeWith(f,clean,P.indexOf(p)):null;
  return{fs,D,P:Pp,Q,M,loss,clean,cleanPlace,f};
}

/* Srovnání s bednou: z pole (vč. zahraničních) průměr D/P/Q/M míst 1–3 */
function podiumOf(f,selfIdx){
  if(!f)return null;
  const pod=f.e.filter(e=>e[1]!=null&&e[1]<=3&&e[4]!==selfIdx&&e[3]);
  if(!pod.length)return null;
  const avg=i=>pod.reduce((t,e)=>t+(e[3][i]||0),0)/pod.length;
  const me=f.e.find(e=>e[4]===selfIdx);
  const refPl=me&&me[1]===1?2:1;
  const win=f.e.find(e=>e[1]===refPl&&e[3]&&e[4]!==selfIdx);
  const czech=pod.filter(e=>e[4]>=0&&P[e[4]]&&P[e[4]].fs).map(e=>P[e[4]].fs);
  return{D:avg(0),P:avg(1),Q:avg(2),M:avg(3),R:pod.reduce((t,e)=>t+e[0],0)/pod.length,refPl,
    win:win?{D:win[3][0],P:win[3][1],Q:win[3][2],M:win[3][3],R:win[0],club:clubOf(win)}:null,czech,n:pod.length};
}

/* Postavení v ČR za rozhodné období: nejlepší výkon (A i B) proti všem
   českým závodníkům / týmům ve stejné kategorii a pohlaví. Zahraniční
   oddíly v datech nástroje záměrně nejsou. */
let _stand=null;
function standingsAll(){
  if(_stand)return _stand;
  const pool=P.filter(r=>r.cL&&(!r.date||r.date>=WIN_FROM));
  const ents=entities(pool).filter(o=>o.lvl!=null);
  const buckets={};
  ents.forEach(o=>{o.best=Math.max.apply(null,o.recs.map(r=>r.score));
    const k=o.disc+'|'+o.lvl+'|'+(o.gender||'');(buckets[k]=buckets[k]||[]).push(o);});
  _stand={ents,buckets};return _stand;
}
function standingsFor(aid){
  const {ents,buckets}=standingsAll();
  const mine={};
  ents.forEach(o=>{
    const has=o.kind==='ind'?o.aid===aid:o.members.some(m=>m.aid===aid);
    if(!has)return;
    const k=o.disc+'|'+o.lvl+'|'+(o.gender||'');
    if(!mine[o.disc]||o.best>mine[o.disc].o.best)mine[o.disc]={o,k};
  });
  return Object.values(mine).map(({o,k})=>{
    const b=buckets[k];const rank=1+b.filter(x=>x.best>o.best+1e-9).length;
    const n=b.length,pc=n>1?(rank-1)/(n-1):0;
    let tier,cls;
    if(rank<=3&&n>=3){tier='Špička ČR';cls='t1';}
    else if(pc<=0.25){tier='Silná stránka';cls='t2';}
    else if(pc<=0.6){tier='Střed';cls='t3';}
    else{tier='Rezerva';cls='t4';}
    const leader=b.reduce((m,x)=>x.best>m.best?x:m);
    return{disc:o.disc,team:o.kind==='team',rank,n,pc,tier,cls,best:o.best,lvl:o.lvl,gender:o.gender,
           leader:{best:leader.best,club:leader.club,name:leader.kind==='ind'?leader.ath:null}};
  }).sort((a,b)=>a.pc-b.pc||a.rank-b.rank);
}

/* Poslední start v disciplíně (s polem z výsledkovky) */
function lastStarts(aid,disc){
  const mine=P.filter(r=>r.disc===disc&&r.fv!=null&&r.members.some(m=>m.aid===aid));
  if(!mine.length)return[];
  const last=mine.reduce((m,r)=>(r.date||'')>(m.date||'')?r:m).date;
  return mine.filter(r=>r.date===last).sort((a,b)=>a.pl-b.pl);
}

/* Doporučení: deterministická pravidla, jen věci doložitelné čísly.
   Pořadí podle toho, co reálně přinese body nebo místa:
     ~0,95  chyby „zadarmo“: porušení času/prostoru, chybný start
     ~0,85  nesplněný povinný prvek (snadné body)
     0,5–0,9 čistota (missy, breaky) – podle podílu ztracené sestavy
     ~0,8   bedna na dosah (rychlost: malý odstup; freestyle: bez chyb na bedně)
     ~0,7   limit na dosah
     ~0,45  obtížnost výrazně pod bednou
     ~0,3   o místo výš (jen když nejde o bednu)  */
function recommendations(a){
  _gen=a.gender;
  const out=[];
  const discs=[...new Set(P.filter(r=>r.members.some(m=>m.aid===a.aid)).map(r=>r.disc))];
  const lc=a.lvl===2?'junior':a.lvl===3?'senior':null;
  for(const d of discs){
    const nm=dcName(d);
    for(const p of lastStarts(a.aid,d)){
      const where=shortComp(p.comp);
      if(p.fs){
        const A=fsAnalysis(p);if(!A)continue;
        const ref=Math.max(A.clean,0.01);
        const missAll=A.loss.miss+A.loss.presMiss;
        if((p.fs.am||0)>0&&missAll/ref>=0.06)
          out.push({pr:0.5+Math.min(0.4,missAll/ref),d,kind:'Čistota',
            t:'<b>'+esc(nm)+'</b>: '+(p.fs.am===1?'jeden miss':'missy ('+fmt(p.fs.am)+'×)')+' na '+esc(where)+' tě stál'+(p.fs.am===1?'':'y')+' asi <b>'+body(missAll)+'</b> ('+pct(missAll/ref)+' sestavy). '
             +'Miss bere dvakrát – srážkou a ještě bod v každé kategorii prezentace.'});
        if(A.loss.brk/ref>=0.06)
          out.push({pr:0.48+Math.min(0.4,A.loss.brk/ref),d,kind:'Čistota',
            t:'<b>'+esc(nm)+'</b>: '+(p.fs.ab===1?'jeden break':'breaky ('+fmt(p.fs.ab)+'×)')+' na '+esc(where)+' – srážka <b>'+body(A.loss.brk)+'</b> ('+pct(A.loss.brk/ref)+' sestavy).'});
        if(A.loss.viol>0.005)
          out.push({pr:0.95,d,kind:'Zadarmo',
            t:'<b>'+esc(nm)+'</b>: porušení času nebo prostoru na '+esc(where)+' – srážka <b>'+body(A.loss.viol)+'</b>. Tohle je zadarmo.'});
        if(p.fs.q){const miss=Object.keys(p.fs.q).filter(k=>p.fs.q[k]>0);
          if(miss.length&&A.loss.req>0.005)
            out.push({pr:0.85+Math.min(0.1,A.loss.req/ref),d,kind:'Povinné prvky',
              t:'<b>'+esc(nm)+'</b>: '+(miss.reduce((t,k)=>t+p.fs.q[k],0)>1?'nesplněné povinné prvky':'nesplněný povinný prvek')+' ('+miss.map(k=>REQ_LAB[k]+(p.fs.q[k]>1?' '+fmt(p.fs.q[k])+'×':'')).join(', ')+') – <b>'+body(A.loss.req)+'</b>. Snadno získané body.'});}
        if(A.cleanPlace!=null&&p.pl>3&&A.cleanPlace<=3)
          out.push({pr:0.82,d,kind:'Bedna na dosah',
            t:'<b>'+esc(nm)+'</b>: na '+esc(where)+' jsi '+byl()+' '+p.pl+'., <b>bez chyb by to bylo asi '+A.cleanPlace+'. místo</b> ('+fmt(Math.round(A.clean*100)/100)+' místo '+fmt(p.score)+'). Obtížnost na bednu máš – rozhoduje čistota. <i>odhad</i>'});
        const pod=podiumOf(A.f,P.indexOf(p));
        if(pod&&p.pl>3&&A.D<pod.D*0.85){
          let weak='';
          if(p.fs.d&&pod.czech.length){
            const rel=Object.keys(p.fs.d).map(k=>{const ref2=pod.czech.map(c=>(c.d||{})[k]).filter(v=>v!=null);
              const avg=ref2.length?ref2.reduce((t,v)=>t+v,0)/ref2.length:null;return{k,r:avg?p.fs.d[k]/avg:null};}).filter(x=>x.r!=null);
            if(rel.length){const w=rel.reduce((m,x)=>x.r<m.r?x:m);weak=' Nejvíc rezervy je v části <b>'+DT_LAB[w.k]+'</b>.';}
          }
          out.push({pr:0.4+Math.min(0.2,(pod.D-A.D)/pod.D*0.5),d,kind:'Obtížnost',
            t:'<b>'+esc(nm)+'</b>: obtížnost '+fmt(A.D)+' proti průměru bedny '+fmt(Math.round(pod.D*100)/100)+' na '+esc(where)+'.'+weak});
        }
      }else{
        if(p.sm)out.push({pr:0.95,d,kind:'Zadarmo',
          t:'<b>'+esc(nm)+'</b>: chybný start nebo výměna na '+esc(where)+' – srážka <b>'+skoky(p.sm)+'</b>.'});
        const g=gapInfo(p);
        if(g&&g.targets.length){
          const near=t=>t.gap>0&&t.gap<=Math.max(2,0.04*p.score);
          const pod=g.targets.find(t=>t.k<=3&&near(t));
          const nx=g.targets[0];
          const chyb=t=>chybelo(t.gap)+' jen <b>'+skoky(t.gap)+'</b>';
          if(pod)
            out.push({pr:0.8-pod.gap/p.score,d,kind:p.pl<=3?'O stupeň výš':'Bedna na dosah',
              t:'<b>'+esc(nm)+'</b>: na '+esc(where)+' jsi '+byl()+' '+p.pl+'., na '+pod.k+'. místo '+chyb(pod)+' ('+esc(pod.club)+').'});
          else if(near(nx))
            out.push({pr:0.3-nx.gap/p.score,d,kind:'Kousek',
              t:'<b>'+esc(nm)+'</b>: na '+esc(where)+' jsi '+byl()+' '+p.pl+'., na '+nx.k+'. místo '+chyb(nx)+' ('+esc(nx.club)+').'});
        }
      }
    }
    // limity – z nejlepšího výkonu v rozhodném období
    const win=P.filter(r=>r.disc===d&&r.members.some(m=>m.aid===a.aid)&&r.cL&&(!r.date||r.date>=WIN_FROM));
    if(win.length){
      const best=Math.max.apply(null,win.map(r=>r.score));
      const mcr=limitFor(d,lc,'mcr'),ms=lc?limitFor(d,lc,'ms'):null;
      for(const [lim,lab] of [[mcr,'MČR'],[ms,'MS']]){
        if(lim==null||best>=lim)continue;
        const gap=Math.round((lim-best)*100)/100;
        if(gap<=0.05*lim){
          out.push({pr:0.7-gap/lim,d,kind:'Limit na dosah',
            t:'<b>'+esc(nm)+'</b>: do limitu '+lab+' ('+fmt(lim)+') ti chybí <b>'+(isSpeed(d)?skoky(gap):body(gap))+'</b>.'+(lab==='MČR'?' Pozor, limit MČR je i strop pro soutěže B.':'')});
          break;
        }
      }
    }
  }
  // max. 2 doporučení na disciplínu, celkem 6
  out.sort((x,y)=>y.pr-x.pr);
  const per={},res=[];
  for(const r of out){per[r.d]=(per[r.d]||0)+1;if(per[r.d]<=2)res.push(r);if(res.length>=6)break;}
  return res;
}

/* ---------- vykreslení ---------- */
function bar(v,max,cls){const w=Math.max(0,Math.min(100,max>0?v/max*100:0));return '<span class="anBar '+(cls||'')+'"><i style="width:'+w.toFixed(1)+'%"></i></span>';}

function renderStandings(host,a){
  const st=standingsFor(a.aid);if(!st.length)return;
  const c=document.createElement('div');c.className='anCard';
  let h='<div class="anH">Kde velíš a kde zabrat</div><div class="anSub">Postavení v ČR podle nejlepšího výkonu za rozhodné období (od '+czDate(WIN_FROM)+'), ve stejné kategorii a pohlaví. Zahraniční závodníci se tu nepočítají.</div>';
  st.forEach(s=>{
    h+='<div class="anRow"><span class="anTier '+s.cls+'">'+s.tier+'</span><span class="anD"><b>'+esc(dcName(s.disc))+'</b>'+(s.team?' <span class="tag">tým</span>':'')+
      '<small>'+catLabelLvl(s.lvl)+(s.gender?' · '+genLabel(s.gender):'')+'</small></span>'+
      '<span class="anRk"><b>'+s.rank+'.</b> z '+s.n+'</span>'+
      '<span class="anBest">nejlepší '+fmt(s.best)+(s.rank>1?'<small>1. má '+fmt(s.leader.best)+(s.leader.club?' · '+esc(s.leader.club):'')+'</small>':'<small>jsi první v ČR</small>')+'</span>'+
      bar(1-s.pc,1,s.cls)+'</div>';
  });
  c.innerHTML=h;host.appendChild(c);
}

function renderRecs(host,a){
  const rs=recommendations(a);
  const c=document.createElement('div');c.className='anCard';
  let h='<div class="anH">Na co se zaměřit</div>';
  if(!rs.length){h+='<div class="anSub">Z posledních závodů nevyplývá nic konkrétního – žádné velké ztráty za chyby ani těsné odstupy. Rezervu hledej v obtížnosti a v disciplínách označených jako Rezerva.</div>';}
  else{h+='<div class="anSub">Seřazené podle toho, kolik by to přineslo. Počítá se z posledního závodu v každé disciplíně.</div><ol class="anRecs">';
    rs.forEach(r=>{h+='<li><span class="anKind">'+r.kind+'</span>'+r.t+'</li>';});h+='</ol>';}
  c.innerHTML=h;host.appendChild(c);
}

function startDetail(p,a){
  const g=gapInfo(p);if(!g)return '';
  const f=g.f;
  let h='<div class="anStart"><div class="anSt1"><b>'+esc(shortComp(p.comp))+'</b> '+czDate(p.date)+
    ' · <span class="anPl">'+p.pl+'. místo</span> z '+g.n+
    (f.how===2?' <span class="anNote" title="Pořadatel tuto kategorii vyhodnotil společně s jinou – odstupy jsou proti celému sloučenému poli.">sloučená kategorie</span>':'')+
    (f.how===0?' <span class="anNote" title="Smíšená soutěž A+B – umístění v rámci úrovně '+(f.lc||'')+', dopočtené podle IJRU.">soutěž '+(f.lc||'')+'</span>':'')+
    (TEAM.has(p.disc)?'<small> · s '+p.members.filter(m=>m.aid!==a.aid).map(m=>esc(m.name.split(' ')[0])).join(', ')+'</small>':'')+'</div>';
  if(g.targets.length){
    h+='<div class="anGaps">';
    g.targets.forEach(t=>{
      h+='<div><span>'+t.lab+' ('+t.k+'.)</span><b>'+(isSpeed(p.disc)?'+'+skoky(t.gap):'+'+body(t.gap))+'</b><small>'+esc(t.club)+' · '+fmt(t.score)+'</small></div>';
    });
    h+='</div>';
  }else h+='<div class="anWin">🏆 Vítězství</div>';
  if(p.sm)h+='<div class="anWarn">Chybný start nebo výměna: srážka '+skoky(p.sm)+'.</div>';
  if(p.fs)h+=fsDetail(p);
  return h+'</div>';
}

function fsDetail(p){
  const A=fsAnalysis(p);if(!A)return '';
  const pod=podiumOf(A.f,P.indexOf(p));
  const fs=p.fs;
  const row=(lab,me,pv,wv,fmtv)=>'<tr><td>'+lab+'</td><td><b>'+fmtv(me)+'</b></td><td>'+(pv==null?'–':fmtv(pv))+'</td><td>'+(wv==null?'–':fmtv(wv))+'</td></tr>';
  const f2=v=>fmt(Math.round(v*100)/100),fq=v=>pct(v),fm=v=>v>=1?'0 %':'−'+pct(1-v);
  const onPod=p.pl<=3,refLab=pod&&pod.refPl===2?'2. místo':'vítěz';
  let h='<table class="anTab"><tr><th></th><th>ty</th><th>'+(onPod?'zbytek bedny ⌀':'bedna ⌀')+'</th><th>'+refLab+(pod&&pod.win?'<small>'+esc(pod.win.club)+'</small>':'')+'</th></tr>';
  h+=row('Obtížnost D',A.D,pod&&pod.D,pod&&pod.win&&pod.win.D,f2);
  h+=row('Prezentace P',A.P,pod&&pod.P,pod&&pod.win&&pod.win.P,f2);
  if(fs.fm!=='dd')h+=row('Povinné prvky',A.Q,pod&&pod.Q,pod&&pod.win&&pod.win.Q,fq);
  h+=row('Srážky',A.M,pod&&pod.M,pod&&pod.win&&pod.win.M,fm);
  h+=row('Výsledek',p.score,pod&&pod.R,pod&&pod.win&&pod.win.R,f2);
  h+='</table>';
  const L=A.loss,items=[];
  if(L.miss>0.005)items.push(['Missy ('+fmt(fs.am)+'×)',L.miss,false]);
  if(L.presMiss>0.005)items.push(['… a jejich vliv na prezentaci',L.presMiss,true]);
  if(L.brk>0.005)items.push(['Breaky ('+fmt(fs.ab)+'×)',L.brk,false]);
  if(L.viol>0.005)items.push(['Porušení času / prostoru',L.viol,false]);
  if(L.req>0.005)items.push(['Nesplněné povinné prvky',L.req,false]);
  if(items.length){
    const mx=Math.max.apply(null,items.map(x=>x[1]));
    h+='<div class="anLoss"><div class="anLh">Kolik stály chyby</div>';
    items.forEach(([lab,v,est])=>{h+='<div class="anLr"><span>'+lab+(est?' <i>odhad</i>':'')+'</span>'+bar(v,mx,'loss')+'<b>−'+fmt(Math.round(v*100)/100)+'</b></div>';});
    if(A.cleanPlace!=null)h+='<div class="anClean">Bez chyb by to bylo asi <b>'+fmt(Math.round(A.clean*100)/100)+'</b>'+
      (A.cleanPlace<p.pl?' → <b>'+A.cleanPlace+'. místo</b>':' – umístění by se nezměnilo')+' <i>odhad</i></div>';
    h+='</div>';
  }
  // podrobně
  let det='';
  if(fs.d){
    const ref={};
    if(pod&&pod.czech.length)Object.keys(fs.d).forEach(k=>{const v=pod.czech.map(c=>(c.d||{})[k]).filter(x=>x!=null);if(v.length)ref[k]=v.reduce((t,x)=>t+x,0)/v.length;});
    const mx=Math.max.apply(null,Object.keys(fs.d).map(k=>Math.max(fs.d[k]||0,ref[k]||0)));
    det+='<div class="anSec"><div class="anLh">Obtížnost podle částí</div>';
    Object.keys(fs.d).forEach(k=>{det+='<div class="anLr"><span>'+DT_LAB[k]+'</span>'+bar(fs.d[k],mx)+'<b>'+fmt(fs.d[k])+'</b>'+(ref[k]!=null?'<small>bedna ČR '+fmt(Math.round(ref[k]*100)/100)+'</small>':'')+'</div>';});
    det+='</div>';
  }
  if(fs.pc){
    const vals=PRES_ORDER.map(k=>fs.pc[k]).filter(v=>v!=null);
    if(vals.length){
      const mean=vals.reduce((t,v)=>t+v,0)/vals.length;
      const lo=PRES_ORDER.reduce((m,k)=>fs.pc[k]!=null&&(m==null||fs.pc[k]<fs.pc[m])?k:m,null);
      det+='<div class="anSec"><div class="anLh">Prezentace po kategoriích <small>(škála 0–24, 12 = průměr)</small></div>';
      PRES_ORDER.forEach(k=>{if(fs.pc[k]==null)return;det+='<div class="anLr"><span>'+PRES_LAB[k]+(k===lo&&fs.pc[k]<mean-0.4?' <i>nejslabší</i>':'')+'</span>'+bar(fs.pc[k],24,fs.pc[k]>=12?'okb':'')+'<b>'+fmt(fs.pc[k])+'</b></div>';});
      if(fs.pm)det+='<div class="anFoot">Rozhodčí prezentace viděli '+fmt(fs.pm)+'× miss a za každý strhli bod v každé kategorii.</div>';
      det+='</div>';
    }
  }
  if(fs.lv){
    const labs=fs.fm==='dd'?LV_DD:LV_SR;
    const tot=labs.map((_,i)=>Object.values(fs.lv).reduce((t,arr)=>t+(arr[i]||0),0));
    const sum=tot.reduce((t,v)=>t+v,0);
    if(sum>0){
      const mx=Math.max.apply(null,tot);
      const hiFrom=fs.fm==='dd'?2:3; // DD: úroveň 3+, SR/Wheel: úroveň 3+
      const hi=tot.reduce((t,v,i)=>t+((fs.fm==='dd'?i>=2:i>=3)?v:0),0);
      det+='<div class="anSec"><div class="anLh">Úrovně prvků <small>(průměr rozhodčích obtížnosti)</small></div><div class="anLv">';
      tot.forEach((v,i)=>{if(!v&&i>5)return;det+='<div><i style="height:'+(mx?Math.max(2,v/mx*48):2)+'px"></i><b>'+(v?fmt(Math.round(v*10)/10):'')+'</b><span>L'+labs[i]+'</span></div>';});
      det+='</div><div class="anFoot">'+pct(hi/sum)+' prvků je v úrovni 3 a výš.</div></div>';
    }
  }
  if(det)h+='<details class="anDet"><summary>Podrobný rozbor</summary>'+det+'</details>';
  return h;
}
