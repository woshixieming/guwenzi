/* 按部首找字与截图识字共用本地反查结果。 */
(function(){
  'use strict';
  const $ = id => document.getElementById(id);
  const core = window.VariantCore;
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let data = null, loading = null, page = 0, current = [], query = 0;
  let submode = 'radical', ocrReady = false, ocrAbort = null, statusVersion = 0;
  let image = null, imageVersion = 0, selection = null, dragStart = null, crop = '';
  const canvas = $('vfCanvas'), ctx = canvas.getContext('2d');
  const kindText = {traditional:'繁简对应', variant:'异体对应', reference:'语义关联 · 仅供参考'};

  function active(){ return document.querySelector('.tab.on')?.dataset.mode; }
  function status(message, error=false){
    $('vfStatus').textContent = message;
    $('vfStatus').classList.toggle('error', error);
  }
  async function ensure(){
    if (data) return data;
    if (!loading) loading = (async () => {
      const response = await fetch('assets/variant-index.json');
      if (!response.ok) throw new Error('索引加载失败');
      const value = await response.json();
      if (value.version !== 1 || !value.chars || !Array.isArray(value.radicals)) throw new Error('索引格式异常');
      data = value;
      return data;
    })().finally(() => { loading = null; });
    return loading;
  }
  function options(){
    return {radical:$('vfRadical').value, strokes:$('vfStrokes').value,
      strokeKind:$('vfStrokeKind').value, nearby:$('vfNearby').checked,
      mappedOnly:$('vfMapped').checked, components:$('vfParts').value};
  }
  function radicalControls(){
    const opts = options();
    $('vfRadical').innerHTML = '<option value="">全部部首</option>' + data.radicals.map(r =>
      `<option value="${r.id}">${escape(r.c + (r.a ? ' / ' + r.a : ''))}部</option>`).join('');
    $('vfRadical').value = opts.radical;
    let previous = 0;
    $('vfRadicals').innerHTML = data.radicals.map(r => {
      const group = r.s !== previous ? `<span class="rgroup">${r.s} 画部首</span>` : '';
      previous = r.s;
      return group + `<button type="button" class="rchip${String(r.id) === opts.radical ? ' on' : ''}" data-radical="${r.id}" aria-pressed="${String(r.id) === opts.radical}" title="${escape(r.c + '部 ' + r.s + '画 ' + r.a)}">${escape(r.c)}${r.a ? `<small>${escape(r.a)}</small>` : ''}</button>`;
    }).join('');
  }
  function paginate(){
    const size = 60, pages = Math.max(1, Math.ceil(current.length / size));
    page = Math.max(0, Math.min(page, pages - 1));
    const cards = current.slice(page * size, (page + 1) * size).map(([ch,r]) => {
      const targets = core.matches(data,ch).filter(x => !x.reference).map(x => x.character);
      const hint = targets.length ? '→ ' + targets.join(' / ') : r.m?.length ? '有参考关系' : r.std ? '规范字' : '暂未收录对应字';
      return `<button type="button" class="cell vf-card" data-vchar="${escape(ch)}" aria-label="查看 ${escape(ch)} ${escape(hint)}"><div class="big">${escape(ch)}</div>` +
        `<div class="py">${escape(hint)}</div><div class="rd">${r.s.length ? r.s.join('/') + '画' : '笔画未知'} · U+${ch.codePointAt(0).toString(16).toUpperCase()}</div></button>`;
    }).join('');
    $('result').innerHTML = `<div class="result-head"><h2>按字形找异体字</h2><span>${current.length} 字 · 第 ${page + 1}/${pages} 页</span></div>` +
      (cards ? `<div class="grid">${cards}</div>` : '<div class="empty">没有符合条件的字。可取消笔画限定、改选相邻部首，或尝试截图识字。</div>') +
      `<div class="vf-paging"><button type="button" class="copy-btn" id="vfPrevious" ${page === 0 ? 'disabled' : ''}>上一页</button><span>${page + 1} / ${pages}</span>` +
      `<button type="button" class="copy-btn" id="vfNext" ${page + 1 >= pages ? 'disabled' : ''}>下一页</button></div>`;
    $('vfPrevious').onclick = () => { page--; paginate(); };
    $('vfNext').onclick = () => { page++; paginate(); };
  }
  async function filter(){
    const version = ++query;
    const opts = options();
    if (opts.strokes !== '' && (!Number.isInteger(Number(opts.strokes)) || +opts.strokes < 0 || +opts.strokes > 100)) {
      status('笔画数请输入 0–100 的整数。', true); return;
    }
    if (opts.strokeKind === 'remaining' && !opts.radical && opts.strokes !== '') {
      status('按部外笔画筛选时，请先选择部首。', true); return;
    }
    status('正在载入并筛选字库…');
    try {
      await ensure();
      if (version !== query || active() !== 'variant' || submode !== 'radical') return;
      if ($('vfRadical').options.length < 2) radicalControls();
      current = core.filter(data,opts); page = 0; paginate();
      status('按原字自身的部首与笔画检索。看不清笔画可先留空；候选字显示为方框时，仍可复制字符与编码核对。');
    } catch (error) {
      if (version === query) status('异体字索引加载失败，请点击“筛选”重试。',true);
    }
  }
  async function lookup(raw){
    const version = ++query;
    const chs = [...raw.trim()];
    if (chs.length !== 1 || !core.isHan(chs[0])) {
      $('result').innerHTML = '<div class="vf-result">请粘贴一个汉字；多字文本请使用家谱识别。</div>'; return;
    }
    const ch = chs[0], expectedMode = active();
    $('result').innerHTML = '<div class="vf-result">正在查找对应关系…</div>';
    try {
      await ensure();
      if (version !== query || expectedMode !== active()) return;
      renderLookup(ch);
    } catch (error) {
      if (version !== query || expectedMode !== active()) return;
      $('result').innerHTML = '<div class="vf-result">异体字索引加载失败。<button type="button" class="copy-btn" id="vfRetry">重试</button></div>';
      $('vfRetry').onclick = () => lookup(ch);
    }
  }
  function renderLookup(ch){
    const r = data.chars[ch], matches = core.matches(data,ch);
    const definite = matches.filter(x => !x.reference);
    const warning = r?.std ? '本字也在规范字表中，不能一律替换；人名、地名尤其需要核对原文。' :
      definite.length > 1 ? '有多个对应候选，请结合读音、含义与上下文选择。' :
      !definite.length ? '暂未收录明确的规范字对应关系；参考关联不代表可以直接替换。' : '以下对应关系来自本地字库，使用时请保留原文核对。';
    let html = `<div class="vf-result"><span class="original">${escape(ch)}</span><small>U+${ch.codePointAt(0).toString(16).toUpperCase()}${r?.p ? ' · ' + escape(r.p.join(' / ')) : ''}</small>` +
      `<p>${escape(warning)}</p><button type="button" class="copy-btn" data-copy="${escape(ch)}">复制原字</button> <button type="button" class="copy-btn" data-detail="${escape(ch)}">查看原字详情</button></div>`;
    for (const m of matches) {
      const target = data.chars[m.character];
      html += `<div class="vf-result"><span class="candidate">${escape(m.character)}</span> ${escape(target?.p?.join(' / ') || '')}` +
        `<p>${m.reference ? '参考字，不能直接作规范转写' : '对应规范字候选'}</p>` +
        m.evidence.map(e => `<p>${escape(kindText[e.type])} · ${escape(e.source)}</p>`).join('') +
        `<button type="button" class="copy-btn" data-copy="${escape(m.character)}">复制${m.reference ? '参考' : '对应'}字</button> <button type="button" class="copy-btn" data-detail="${escape(m.character)}">查看字义与书体</button></div>`;
    }
    if (r?.k?.length) html += `<div class="vf-result"><p>原字部件结构（用于检索，不代表字源）</p><p>${escape(r.k.map(parts => parts.join(' + ')).join(' / '))}</p></div>`;
    if (!matches.length) html += '<div class="vf-result">没有对应关系不代表原字不存在或写错。可以更换部首条件继续查找。</div>';
    $('result').innerHTML = html;
  }
  async function checkStatus(){
    const version = ++statusVersion;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 6000);
    $('vfOcrStatus').textContent = '正在检查截图识字服务…';
    ocrReady = false; refreshRecognize();
    try {
      const response = await fetch('/api/ocr/status', {signal:controller.signal, cache:'no-store'});
      const value = response.ok ? await response.json() : null;
      if (version !== statusVersion) return;
      ocrReady = value?.configured === true;
      $('vfOcrStatus').textContent = ocrReady ? '识别时仅将选区图片发送给识字服务，请先对照裁剪预览。' : '截图识字暂未配置。可以先裁剪图片，或使用部首查字。';
    } catch (error) {
      if (version === statusVersion) $('vfOcrStatus').textContent = '截图识字服务暂不可用，请使用部首查字，或稍后重新检查。';
    } finally { clearTimeout(timer); if (version === statusVersion) refreshRecognize(); }
  }
  function refreshRecognize(){ $('vfRecognize').disabled = !ocrReady || !crop || !!ocrAbort; }
  function cancelOcr(){ if (ocrAbort) ocrAbort.abort(); ocrAbort = null; refreshRecognize(); }
  function clearCandidates(){
    $('vfOcrCandidates').innerHTML = ''; $('vfOcrMessage').textContent = '';
    if (active() === 'variant' && submode === 'ocr') $('result').innerHTML = '';
  }
  function cropChanged(){
    cancelOcr(); clearCandidates();
    if (!image || !selection) { crop = ''; refreshRecognize(); return; }
    const {x,y,w,h} = selection;
    const output = document.createElement('canvas');
    const scale = Math.min(1, 1600 / Math.max(w,h));
    output.width = Math.max(1,Math.round(w * scale)); output.height = Math.max(1,Math.round(h * scale));
    const draw = output.getContext('2d');
    draw.fillStyle = '#fff'; draw.fillRect(0,0,output.width,output.height);
    draw.drawImage(image, x,y,w,h, 0,0,output.width,output.height);
    crop = output.toDataURL('image/jpeg',0.92);
    $('vfPreview').src = crop;
    refreshRecognize();
  }
  function paint(){
    if (!image) return;
    ctx.clearRect(0,0,canvas.width,canvas.height);
    ctx.drawImage(image,0,0,canvas.width,canvas.height);
    if (selection) {
      const sx = canvas.width / image.width, sy = canvas.height / image.height;
      ctx.strokeStyle = '#b5493a'; ctx.lineWidth = 3;
      ctx.strokeRect(selection.x*sx,selection.y*sy,selection.w*sx,selection.h*sy);
    }
  }
  function fullImage(){
    if (!image) return;
    selection = {x:0,y:0,w:image.width,h:image.height};
    for (const [id,value] of [['vfX',0],['vfY',0],['vfW',100],['vfH',100]]) $(id).value = value;
    paint(); cropChanged();
  }
  async function chooseImage(file){
    const version = ++imageVersion;
    cancelOcr(); clearCandidates();
    image = null; crop = ''; selection = null; dragStart = null; refreshRecognize();
    $('vfCrop').classList.remove('show');
    if (!file || !['image/png','image/jpeg','image/webp'].includes(file.type) || file.size > 12*1024*1024) {
      $('vfOcrMessage').textContent = '请选择 12 MiB 以内的 PNG、JPEG 或 WebP 图片。'; return;
    }
    const url = URL.createObjectURL(file);
    try {
      const img = new Image(); img.src = url; await img.decode();
      if (version !== imageVersion) return;
      if (img.width*img.height > 24_000_000) throw new Error('图片尺寸过大，请先截取目标区域后重试。');
      image = img;
      const scale = Math.min(1,1000/img.width,800/img.height);
      canvas.width = Math.round(img.width*scale); canvas.height = Math.round(img.height*scale);
      $('vfCrop').classList.add('show'); fullImage();
      $('vfOcrMessage').textContent = '请拖动框选一个字，或用下方滑块调整选区。';
    } catch (error) {
      if (version === imageVersion) $('vfOcrMessage').textContent = error.message === '图片尺寸过大，请先截取目标区域后重试。' ? error.message : '图片无法读取，请更换图片。';
    } finally { URL.revokeObjectURL(url); }
  }
  function point(event){
    const rect = canvas.getBoundingClientRect();
    return {x:Math.max(0,Math.min(image.width,(event.clientX-rect.left)/rect.width*image.width)),
      y:Math.max(0,Math.min(image.height,(event.clientY-rect.top)/rect.height*image.height))};
  }
  canvas.onpointerdown = event => {
    if (!image) return;
    dragStart = point(event); cancelOcr(); clearCandidates(); crop = ''; refreshRecognize();
    canvas.setPointerCapture(event.pointerId);
  };
  canvas.onpointermove = event => {
    if (!dragStart || !image) return;
    const end = point(event);
    selection = {x:Math.min(end.x,dragStart.x),y:Math.min(end.y,dragStart.y),w:Math.abs(end.x-dragStart.x),h:Math.abs(end.y-dragStart.y)};
    paint();
  };
  canvas.onpointerup = () => {
    if (!dragStart || !image) return;
    dragStart = null;
    if (!selection || selection.w < 4 || selection.h < 4) { fullImage(); return; }
    $('vfX').value = selection.x/image.width*100; $('vfY').value = selection.y/image.height*100;
    $('vfW').value = selection.w/image.width*100; $('vfH').value = selection.h/image.height*100;
    cropChanged();
  };
  canvas.onpointercancel = () => { dragStart = null; if (image) fullImage(); };
  for (const id of ['vfX','vfY','vfW','vfH']) $(id).oninput = () => {
    if (!image) return;
    const x = +$('vfX').value/100*image.width, y = +$('vfY').value/100*image.height;
    selection = {x,y,w:Math.max(1,Math.min(image.width-x,+$('vfW').value/100*image.width)),h:Math.max(1,Math.min(image.height-y,+$('vfH').value/100*image.height))};
    paint(); cropChanged();
  };
  async function recognize(){
    if (!crop || !ocrReady || ocrAbort) return;
    if (crop.length > 5.5*1024*1024) { $('vfOcrMessage').textContent = '选区图片过大，请缩小选区。'; return; }
    const controller = new AbortController(); ocrAbort = controller; refreshRecognize(); clearCandidates();
    const snapshot = crop;
    $('vfOcrMessage').textContent = '正在识别原字形，请稍候…';
    const timer = setTimeout(() => controller.abort(),65000);
    try {
      const response = await fetch('/api/ocr', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({image:snapshot}),signal:controller.signal});
      let value;
      try { value = await response.json(); } catch (error) { throw new Error('识字服务返回异常，请稍后重试。'); }
      if (ocrAbort !== controller || crop !== snapshot || active() !== 'variant' || submode !== 'ocr') return;
      if (!response.ok) throw new Error(typeof value.error === 'string' ? value.error : '识别失败，请稍后重试。');
      if (!Array.isArray(value.candidates) || value.candidates.length > 5 || value.candidates.some(x => !core.isHan(x.character))) throw new Error('候选字格式异常，请重试。');
      $('vfOcrMessage').textContent = (value.candidates.length ? '请对照选区，点击确认原字。模型候选不代表规范字转换结论。' : '未能识别原字。请重新裁剪、换清晰图片，或改用部首查字。') + (value.note ? '\n'+String(value.note).slice(0,300) : '');
      $('vfOcrCandidates').innerHTML = value.candidates.map(x => `<button type="button" data-ocrchar="${escape(x.character)}"><b>${escape(x.character)}</b><small>${escape(x.reason || '请对照原图确认')}</small></button>`).join('');
    } catch (error) {
      if (ocrAbort === controller) $('vfOcrMessage').textContent = error.name === 'AbortError' ? '识别已取消或超时，可以重新识别。' : error.message;
    } finally {
      clearTimeout(timer);
      if (ocrAbort === controller) { ocrAbort = null; refreshRecognize(); }
    }
  }
  function setSubmode(value){
    ++query; submode = value; cancelOcr();
    $('vfRadicalMode').hidden = value !== 'radical'; $('vfOcrMode').hidden = value !== 'ocr';
    document.querySelectorAll('[data-vf-mode]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.vfMode === value)));
    if (value === 'ocr') {
      $('result').innerHTML = ''; status('上传截图后框选一个字，再确认识别候选。'); checkStatus();
    } else { clearCandidates(); filter(); }
  }
  async function enter(){
    ++query;
    setSubmode(submode);
    if (submode === 'radical') {
      try { await ensure(); if (active() === 'variant') radicalControls(); }
      catch (error) { status('异体字索引加载失败，请点击“筛选”重试。',true); }
    }
  }
  function leave(){ ++query; ++statusVersion; cancelOcr(); clearCandidates(); }
  $('vfFilter').onclick = () => { filter(); if (data) radicalControls(); };
  $('vfReset').onclick = () => {
    $('vfRadical').value=''; $('vfStrokes').value=''; $('vfParts').value='';
    $('vfStrokeKind').value='total'; $('vfNearby').checked=false; $('vfMapped').checked=true;
    if (data) radicalControls(); filter();
  };
  $('vfRadicals').onclick = event => {
    const button = event.target.closest('[data-radical]');
    if (!button) return;
    $('vfRadical').value = button.dataset.radical; radicalControls(); filter();
  };
  for (const id of ['vfRadical','vfStrokeKind','vfNearby','vfMapped']) $(id).onchange = () => { if(data) radicalControls(); filter(); };
  for (const id of ['vfParts','vfStrokes']) $(id).onkeydown = e => { if(e.key==='Enter') filter(); };
  document.querySelectorAll('[data-vf-mode]').forEach(b => b.onclick = () => setSubmode(b.dataset.vfMode));
  $('vfFile').onchange = () => { const file = $('vfFile').files[0]; if(file) chooseImage(file); $('vfFile').value=''; };
  document.addEventListener('paste', event => {
    if (active() !== 'variant' || submode !== 'ocr') return;
    const item = [...(event.clipboardData?.items || [])].find(x=>x.type.startsWith('image/'));
    if (item) { event.preventDefault(); chooseImage(item.getAsFile()); }
  });
  $('vfFullImage').onclick = fullImage;
  $('vfRecognize').onclick = recognize;
  $('vfCancel').onclick = () => { cancelOcr(); $('vfOcrMessage').textContent='识别已取消。'; };
  $('vfCheckService').onclick = checkStatus;
  $('vfOcrCandidates').onclick = event => {
    const button = event.target.closest('[data-ocrchar]'); if (button) lookup(button.dataset.ocrchar);
  };
  $('result').addEventListener('click',async event => {
    const button = event.target.closest('[data-vchar],[data-copy],[data-detail]'); if(!button) return;
    if (button.dataset.vchar) return lookup(button.dataset.vchar);
    if (button.dataset.copy) {
      try { await navigator.clipboard.writeText(button.dataset.copy); button.textContent='已复制'; }
      catch(error) { button.textContent='复制失败，请手动选择字符'; }
    } else if (button.dataset.detail) {
      const char = button.dataset.detail;
      if (CMAP[char] != null) openDetail(CMAP[char]);
      else loadExt(ok => {
        if (ok && EXT.idx[char] != null) openExtDetail(char);
        else showMini(char, '<div class="var-block">当前字库没有更多释义，原字编码为 U+'+char.codePointAt(0).toString(16).toUpperCase()+'。</div>');
      });
    }
  });
  window.VariantFinder = {ensure, lookup, enter, leave, get data(){return data;}};
})();
