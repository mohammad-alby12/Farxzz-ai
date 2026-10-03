const $=s=>document.querySelector(s);let conv=null,files=[],images=[],busy=false;
const J={'Content-Type':'application/json'};
async function api(p,o={}){const r=await fetch('/api'+p,o);const d=await r.json().catch(()=>({}));if(!r.ok)throw new Error(d.detail||r.status);return d}
const fmt=b=>b==null?'—':(b/1e9).toFixed(1)+' GB';
async function list(){const c=await api('/conversations');$('#list').innerHTML='';
 c.forEach(x=>{const d=document.createElement('div');d.className='c'+(x.id===conv?' on':'');
  d.innerHTML='<span></span><i title="Favorit">'+(x.favorite?'★':'☆')+'</i><i title="Hapus">✕</i><i title="Ubah nama">✎</i>';d.firstChild.textContent=x.title;
  d.children[3].onclick=async e=>{e.stopPropagation();const t=prompt('Nama baru',x.title);if(t&&t.trim()){await api('/conversations/'+x.id,{method:'PATCH',headers:J,body:JSON.stringify({title:t.trim()})});list()}};
  d.onclick=()=>{open(x.id);$('#side').classList.remove('open')};
  d.children[1].onclick=async e=>{e.stopPropagation();await api('/conversations/'+x.id,{method:'PATCH',headers:J,body:JSON.stringify({favorite:!x.favorite})});list()};
  d.children[2].onclick=async e=>{e.stopPropagation();if(!confirm('Hapus percakapan ini?'))return;await api('/conversations/'+x.id,{method:'DELETE'});if(conv===x.id){conv=null;$('#msgs').innerHTML=''}list()};
  $('#list').append(d)})}
function add(role,text){const d=document.createElement('div');d.className='m '+role;d.textContent=text;$('#msgs').append(d);$('#msgs').scrollTop=1e9;return d}
async function open(id){conv=id;const c=await api('/conversations/'+id);$('#msgs').innerHTML='';c.messages.forEach(m=>add(m.role,m.content));list()}
$('#new').onclick=async()=>{conv=(await api('/conversations',{method:'POST'})).id;$('#msgs').innerHTML='';files=[];images=[];$('#att').textContent='';$('#side').classList.remove('open');list()};
$('#menu').onclick=()=>$('#side').classList.toggle('open');
$('#file').onchange=async e=>{const f=e.target.files[0];if(!f)return;const fd=new FormData();fd.append('file',f);
 try{const r=await api('/files/upload',{method:'POST',body:fd});(r.kind==='image'?images:files).push(r.id);attInfo(r)}catch(x){alert(x.message)}e.target.value=''};
async function send(){
 if(busy){await api('/chat/stop',{method:'POST'});return}
 const t=$('#in').value.trim();if(!t)return;
 if(!conv)conv=(await api('/conversations',{method:'POST'})).id;
 $('.empty')?.remove();add('user',t);$('#in').value='';const out=add('ai','…');busy=true;$('#send').textContent='Stop';
 try{const r=await fetch('/api/chat/stream',{method:'POST',headers:J,body:JSON.stringify({conversation_id:conv,message:t,files,images})});
  if(!r.ok){out.textContent=(await r.json()).detail;throw 0}
  files=[];images=[];$('#att').textContent='';const rd=r.body.getReader(),dec=new TextDecoder();let buf='',txt='';
  for(;;){const{done,value}=await rd.read();if(done)break;buf+=dec.decode(value,{stream:true});const parts=buf.split('\n\n');buf=parts.pop();
   for(const p of parts){const d=p.slice(6);if(d==='[DONE]')continue;const j=JSON.parse(d);if(j.error)out.textContent=j.error;else{txt+=j.t;out.textContent=txt;$('#msgs').scrollTop=1e9}}}
 }catch(e){}
 busy=false;$('#send').textContent='Kirim';list()}
$('#send').onclick=send;
$('#in').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!/Android|iPhone/.test(navigator.userAgent)){e.preventDefault();send()}};
let poll;async function panel(){
 const [m,s]=await Promise.all([api('/models'),api('/system')]);
 $('#sys').textContent=`CPU ${s.cpu}% · RAM ${fmt(s.ram_used)} / ${fmt(s.ram_total)} · GPU ${s.gpu?s.gpu.name+' '+s.gpu.vram_used_mb+'/'+s.gpu.vram_total_mb+' MB':'tidak tersedia'} · Disk bebas ${fmt(s.disk_free)}`;
 const act=m.find(x=>x.status==='Loaded');$('#mname').textContent=act?(act.kind==='Cloud'?'☁ ':'')+act.name:'Belum ada model aktif';
 $('#mlist').innerHTML='';let dl=false;
 m.forEach(x=>{const d=document.createElement('div');d.className='mod';const p=x.download;const run=p&&p.state==='downloading';dl=dl||run||x.status==='Loading';
  d.innerHTML='<div><b></b><small></small></div>';d.querySelector('b').textContent=x.name;
  d.querySelector('small').textContent=`${x.kind}${x.quant?' · '+x.quant:''}${x.note?' · '+x.note:''} · ${fmt(x.size)} · ${x.status}${x.error?' — '+x.error:''}${p&&p.state==='error'?' — '+p.error:''}`;
  if(run){const g=document.createElement('progress');g.max=p.total||1;g.value=p.done;d.firstChild.append(g)}
  const b=document.createElement('button');b.className='btn sm';
  const go=(path,body)=>async()=>{if(x.kind==='Cloud'&&path.endsWith('load')&&!path.includes('un')&&!confirm('Model cloud: chat dan gambar Anda dikirim ke Anthropic dan dikenai biaya API. Lanjutkan?'))return;b.disabled=true;try{await api(path,{method:'POST',headers:J,body:JSON.stringify(body)})}catch(e){alert(e.message)}panel()};
  if(x.status==='No API key'){b.textContent='Butuh API key';b.disabled=true}
  else if(x.status==='Ready'){b.textContent='Pakai';b.onclick=go('/models/load',{id:x.id})}
  else if(x.status==='Not Installed'||(x.status==='Error'&&!x.size)){b.textContent='Unduh';b.onclick=go('/models/download',{id:x.id});if(run)b.disabled=true}
  else if(x.status==='Loaded'){b.textContent='Bongkar';b.onclick=go('/models/unload',{})}
  else if(x.status==='Loading'){b.textContent='Memuat…';b.disabled=true}
  else{b.textContent='Muat';b.onclick=go('/models/load',{id:x.id})}
  d.append(b);$('#mlist').append(d)});
 clearTimeout(poll);if(dl&&!$('#modal').hidden)poll=setTimeout(panel,1000)}
$('#models').onclick=()=>{$('#modal').hidden=false;panel()};$('#close').onclick=()=>{$('#modal').hidden=true};
list();panel();

function attInfo(r){const a=$('#att');a.textContent='Terlampir: '+r.name+(r.chars?' ('+r.chars+' karakter)':r.size?' ('+r.size.join('×')+')':'')+' ';
 if(r.kind!=='image')return;
 const b=document.createElement('button');b.className='btn ghost sm';b.textContent='Ambil teks (OCR)';
 b.onclick=async()=>{b.disabled=true;$('.empty')?.remove();const o=add('ai','Membaca teks…');
  try{const t=await api('/images/ocr',{method:'POST',headers:J,body:JSON.stringify({id:r.id})});o.textContent=(t.text||'Tidak ada teks yang terbaca.')+'\n\n'+t.note}catch(e){o.textContent=e.message}b.disabled=false};
 const h=document.createElement('button');h.className='btn ghost sm';h.textContent='Baca tulisan tangan';
 h.onclick=()=>{$('#in').value='Transkripsikan semua tulisan tangan pada gambar ini apa adanya. Tandai bagian yang tidak terbaca dengan [tidak terbaca], jangan menebak.';$('#in').focus()};
 a.append(b,h)}
$('#export').onclick=async()=>{if(!conv)return;const c=await api('/conversations/'+conv);
 const md='# '+c.title+'\n\n'+c.messages.map(m=>'**'+(m.role==='user'?'Anda':'Farxzz AI')+':**\n'+m.content).join('\n\n');
 const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([md],{type:'text/markdown'}));a.download=(c.title||'chat')+'.md';a.click()};
