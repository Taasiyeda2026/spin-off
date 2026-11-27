(()=> {
'use strict';
const root=document.getElementById('research-sheet'), content=document.getElementById('research-content'), toggle=document.getElementById('research-toggle');
let answers={}, readonly=true, enabled=false, shown=false, panelWasOpen=false;
const openStages=new Set();
const ar=()=>new URLSearchParams(location.search).get('lang')==='ar';
const tr=(he,arabic)=>ar()?arabic:he;
function node(tag,text,parent){const e=document.createElement(tag);if(text)e.textContent=text;if(parent)parent.append(e);return e;}
function changed(){window.posterEditor?.markChanged();}
function field(parent,key,label,initial=''){
 const wrap=node('label','',parent);wrap.className='research-field';node('span',label,wrap);
 const input=node('textarea','',wrap);input.rows=2;input.value=typeof answers[key]==='string'?answers[key]:initial;input.readOnly=readonly;
 const printable=node('div',input.value,wrap);printable.className='research-print-value';
 const resize=()=>{input.style.height='auto';input.style.height=Math.min(240,Math.max(62,input.scrollHeight+2))+'px';};
 input.addEventListener('input',()=>{if(readonly)return;answers[key]=input.value;printable.textContent=input.value;resize();changed();});
 requestAnimationFrame(resize);
}
function choices(parent,key,part){
 const multi=part[0]==='#', labels=part.slice(1).split(';'), box=node('div','',parent);box.className='research-options';
 labels.forEach((label,i)=>{
  const wrap=node('label','',box), input=node('input','',wrap);input.type=multi?'checkbox':'radio';input.name=key;input.value=String(i);input.disabled=readonly;input.checked=multi?(Array.isArray(answers[key])&&answers[key].includes(i)):answers[key]===i;
  node('span',label,wrap);
  input.addEventListener('change',()=>{if(readonly)return;if(multi){const set=new Set(Array.isArray(answers[key])?answers[key]:[]);input.checked?set.add(i):set.delete(i);answers[key]=[...set];}else answers[key]=i;changed();});
 });
 if(multi)field(parent,key+'-other',labels.at(-1)+':');
}
function render(){
 if(!enabled)return;
 content.replaceChildren();root.lang=ar()?'ar':'he';root.dir='rtl';
 const lines=window.researchSource[ar()?'ar':'he'].split('\n');
 const actions=node('div','',content);actions.className='research-actions';
 const back=node('button',tr('חזרה לפוסטר','العودة إلى الملصق'),actions);back.type='button';back.onclick=hide;

 node('h1',lines.shift(),content);
 const info=node('div','',content);info.className='research-identity';
 lines.shift().split('|').forEach((label,i)=>field(info,'identity-'+i,label,i===0?'':document.getElementById(['','poster-students','poster-school','poster-class'][i])?.value??''));
 let section, stageIndex=0;
 for(const line of lines){
  const parts=line.split('|'), first=parts.shift();
  if(first[0]==='@'){
   const stage=node('section','',content);stage.className='research-stage';
   const index=++stageIndex, heading=node('h2','',stage), button=node('button','',heading);
   button.type='button';button.className='research-stage-toggle';
   node('span',first.slice(1),button);const arrow=node('span','⌄',button);arrow.className='research-stage-arrow';arrow.setAttribute('aria-hidden','true');
   section=node('div','',stage);section.className='research-stage-body';section.id='research-stage-body-'+index;
   button.setAttribute('aria-controls',section.id);
   const sync=()=>{const expanded=openStages.has(index);button.setAttribute('aria-expanded',String(expanded));stage.classList.toggle('is-expanded',expanded);if(expanded)section.querySelectorAll('textarea').forEach(input=>{input.style.height='auto';input.style.height=Math.min(240,Math.max(62,input.scrollHeight+2))+'px';});};
   button.onclick=()=>{openStages.has(index)?openStages.delete(index):openStages.add(index);sync();};sync();
   if(parts[0])node('p',parts[0],section);continue;
  }
  const question=node('article','',section);question.className='research-question';
  node('h3',first+'. '+parts.shift(),question);
  parts.forEach((part,i)=>{const key='q'+first+'-'+i;if(part[0]==='!')node('p',part.slice(1),question);else if(part[0]==='#'||part[0]==='%')choices(question,key,part);else field(question,key,part);});
 }
 const bottom=node('div','',content);bottom.className='research-actions research-actions-bottom';
 const pdf=node('button',tr('הפקת PDF','إنشاء PDF'),bottom);pdf.type='button';pdf.onclick=async()=>{pdf.disabled=true;try{if(!readonly&&!(await window.posterEditor.flush())){alert(tr('השמירה נכשלה – נסו שוב','تعذّر الحفظ، حاولوا مجددًا'));return;}window.print();}finally{pdf.disabled=false;}};
}
function show(){if(!enabled)return;shown=true;openStages.clear();panelWasOpen=document.body.classList.contains('panel-open');document.body.classList.add('research-active');document.body.classList.remove('panel-open');root.hidden=false;render();toggle.textContent=tr('פוסטר חקר','ملصق البحث');window.scrollTo(0,0);}
function hide(){shown=false;root.hidden=true;document.body.classList.remove('research-active');if(panelWasOpen&&!readonly)document.body.classList.add('panel-open');toggle.textContent=tr('שאלות חקר','أسئلة الاستقصاء');window.dispatchEvent(new Event('resize'));}
toggle.onclick=()=>shown?hide():show();
window.addEventListener('poster:language-changed',()=>{toggle.textContent=shown?tr('פוסטר חקר','ملصق البحث'):tr('שאלות חקר','أسئلة الاستقصاء');if(shown)render();});
window.researchWorksheet={snapshot:()=>structuredClone(answers),load(data,readOnly,allowed){hide();answers=data&&typeof data==='object'&&!Array.isArray(data)?structuredClone(data):{};readonly=readOnly;enabled=allowed;toggle.hidden=!enabled;},close(){hide();enabled=false;readonly=true;answers={};toggle.hidden=true;content.replaceChildren();},show};
})();