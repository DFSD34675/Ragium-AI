const API_BASE = "http://127.0.0.1:8000";
const fileInput=document.getElementById('fileInput');
const fileName=document.getElementById('fileName');
const docTitle=document.getElementById('docTitle');
const docStatus=document.getElementById('docStatus');
const emptyDoc=document.getElementById('emptyDoc');
const paper=document.getElementById('paper');
const messages=document.getElementById('messages');
const questionInput=document.getElementById('questionInput');
const toast=document.getElementById('toast');
let documentId=null;
let currentPdfUrl=null;
let busy=false;
let zoom=100;

function notify(message){
  toast.textContent=message;toast.classList.add('show');
  clearTimeout(window.toastTimer);window.toastTimer=setTimeout(()=>toast.classList.remove('show'),3200);
}
function addMessage(text,type,sources=[]){
  const row=document.createElement('div');
  row.className='message-row '+(type==='user'?'user-row':'assistant-row');
  if(type==='assistant'){
    const av=document.createElement('div');av.className='message-avatar';av.textContent='✦';row.appendChild(av);
  }
  const bubble=document.createElement('div');
  bubble.className='bubble '+(type==='user'?'user-bubble':'assistant-bubble');
  bubble.textContent=text;
  if(type==='assistant' && sources.length){
    const sourceBox=document.createElement('div');sourceBox.className='source-card';
    const title=document.createElement('strong');title.textContent='Sources from your document';sourceBox.appendChild(title);
    sources.forEach(s=>{
      const line=document.createElement('div');
      line.textContent=`Chunk ${s.chunk} · relevance ${s.similarity}`;
      line.style.marginTop='6px';
      sourceBox.appendChild(line);
    });
    bubble.appendChild(sourceBox);
  }
  row.appendChild(bubble);messages.appendChild(row);messages.scrollTop=messages.scrollHeight;
}
function setBusy(value){
  busy=value;
  document.querySelector('.send-btn').disabled=value;
  document.querySelector('.send-btn').style.opacity=value?'.55':'1';
}
function showPreview(file,previewText){
  const stage=document.getElementById('documentStage');
  const old=stage.querySelector('.live-preview');
  if(old)old.remove();
  paper.style.display='none';emptyDoc.style.display='none';
  if(file.type==='application/pdf'){
    if(currentPdfUrl)URL.revokeObjectURL(currentPdfUrl);
    currentPdfUrl=URL.createObjectURL(file);
    const frame=document.createElement('iframe');
    frame.className='live-preview';
    frame.src=currentPdfUrl;
    frame.title='Uploaded PDF preview';
    frame.style.cssText='width:100%;height:100%;min-height:700px;border:0;background:#fff;border-radius:3px;';
    stage.appendChild(frame);
  }else{
    const preview=document.createElement('div');
    preview.className='live-preview';
    preview.style.cssText='width:min(100%,700px);min-height:600px;background:#f7f4f2;color:#211;padding:30px;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.65;font:13px "DM Sans",sans-serif;';
    preview.textContent=previewText || 'Document processed. You can ask questions about it in the chat panel.';
    stage.appendChild(preview);
  }
}
async function uploadFile(file){
  const form=new FormData();form.append('file',file);
  docStatus.textContent='Uploading and processing document...';
  notify('Uploading document and creating embeddings...');
  try{
    const response=await fetch(`${API_BASE}/api/upload`,{method:'POST',body:form});
    const data=await response.json();
    if(!response.ok)throw new Error(data.detail||'Upload failed.');
    documentId=data.document_id;
    fileName.textContent=file.name;
    docTitle.textContent=file.name;
    docStatus.textContent=`Ready · ${data.chunks} chunks indexed`;
    showPreview(file,data.preview_text);
    addMessage(`Your document "${data.filename}" is ready. I indexed ${data.chunks} chunks. Ask me anything about it.`,'assistant');
    notify('Document ready. You can now ask questions.');
  }catch(error){
    documentId=null;docStatus.textContent='Upload failed';
    notify(error.message);
  }
}
fileInput.addEventListener('change',()=>{const file=fileInput.files[0];if(file)uploadFile(file);});
document.getElementById('attachBtn').addEventListener('click',()=>fileInput.click());
document.getElementById('zoomIn').addEventListener('click',()=>{zoom=Math.min(150,zoom+10);const frame=document.querySelector('.live-preview');if(frame)frame.style.zoom=zoom+'%';else{paper.style.transform=`scale(${zoom/100})`;}document.getElementById('zoomValue').textContent=zoom+'%';});
document.getElementById('zoomOut').addEventListener('click',()=>{zoom=Math.max(60,zoom-10);const frame=document.querySelector('.live-preview');if(frame)frame.style.zoom=zoom+'%';else{paper.style.transform=`scale(${zoom/100})`;}document.getElementById('zoomValue').textContent=zoom+'%';});
document.getElementById('fullscreenBtn').addEventListener('click',()=>{const el=document.querySelector('.live-preview')||document.getElementById('documentStage');if(el.requestFullscreen)el.requestFullscreen();});
document.getElementById('themeBtn').addEventListener('click',()=>document.body.classList.toggle('light'));
document.getElementById('historyBtn').addEventListener('click',()=>notify('Chat history is not persisted in this prototype.'));
document.getElementById('settingsBtn').addEventListener('click',()=>notify('Settings can be added after the core workflow is tested.'));
document.getElementById('chatOptions').addEventListener('click',()=>notify('Ragium AI is using the uploaded document as its knowledge source.'));
document.querySelectorAll('.suggestion').forEach(btn=>btn.addEventListener('click',()=>{questionInput.value=btn.textContent;questionInput.focus();}));
document.getElementById('chatForm').addEventListener('submit',async e=>{
  e.preventDefault();
  const question=questionInput.value.trim();
  if(!question||busy)return;
  if(!documentId){notify('Please upload a document first.');return;}
  addMessage(question,'user');questionInput.value='';setBusy(true);
  const waiting=document.createElement('div');waiting.className='message-row assistant-row';
  waiting.innerHTML='<div class="message-avatar">✦</div><div class="bubble assistant-bubble">Searching your document and generating an answer...</div>';
  messages.appendChild(waiting);messages.scrollTop=messages.scrollHeight;
  try{
    const response=await fetch(`${API_BASE}/api/chat`,{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({document_id:documentId,question})
    });
    const data=await response.json();
    if(!response.ok)throw new Error(data.detail||'Chat request failed.');
    waiting.remove();addMessage(data.answer,'assistant',data.sources||[]);
  }catch(error){
    waiting.remove();addMessage(`Sorry, I couldn't get an answer: ${error.message}`,'assistant');
    notify(error.message);
  }finally{setBusy(false);}
});
