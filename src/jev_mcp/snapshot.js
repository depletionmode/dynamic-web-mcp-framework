() => {
  const visible = el => {
    const s = getComputedStyle(el), r = el.getBoundingClientRect();
    return s.visibility !== 'hidden' && s.display !== 'none' && r.width > 0 && r.height > 0 && r.bottom > 0 && r.right > 0 && r.top < innerHeight && r.left < innerWidth;
  };
  const all = [];
  function visit(root) {
    for (const el of root.querySelectorAll('*')) {
      all.push(el);
      if (el.shadowRoot) visit(el.shadowRoot);
    }
  }
  visit(document);
  const selector = 'a[href],button,input,textarea,select,[contenteditable="true"],[role="button"],[role="link"],[role="textbox"],[role="combobox"],[role="option"],[role="menuitem"],[role="tab"],[role="checkbox"],[role="treeitem"],[role="row"],[tabindex]';
  const scrollable = el => visible(el) && el.scrollHeight > el.clientHeight + 20 && ['auto','scroll'].includes(getComputedStyle(el).overflowY);
  const candidates = all.filter(el => (el.matches(selector) || scrollable(el)) && (visible(el) || el.type === 'file') && !el.disabled && el.getAttribute('aria-disabled') !== 'true');
  const nodes = candidates.slice(0, 350);
  const labelText = el => {
    const label = el.labels?.[0];
    if (!label) return '';
    const copy = label.cloneNode(true);
    copy.querySelectorAll('input,select,textarea,button').forEach(n => n.remove());
    return copy.textContent.trim();
  };
  const describe = el => ({
    tag: el.tagName.toLowerCase(), role: el.getAttribute('role'), type: el.type || '',
    name: (el.getAttribute('aria-label') || (el.getAttribute('aria-labelledby') || '').split(' ').map(id => document.getElementById(id)?.textContent || '').join(' ').trim() || labelText(el) || el.getAttribute('placeholder') || el.getAttribute('title') || el.innerText || el.getAttribute('name') || '').trim().slice(0, 400),
    value: el.type === 'password' ? '[redacted]' : String(el.value ?? (el.isContentEditable ? el.innerText : '')).slice(0, 3000),
    checked: el.checked ?? el.getAttribute('aria-checked'),
    context: (el.closest('tr,[role="row"],label')?.innerText || '').slice(0, 600),
    options: el.tagName === 'SELECT' ? Array.from(el.options).map(o => ({value:o.value, label:o.label, disabled:o.disabled})) : null,
    editable: el.isContentEditable || el.tagName === 'TEXTAREA' || (el.tagName === 'INPUT' && !['file','submit','button','checkbox','radio','hidden','password'].includes(el.type)),
    file: el.type === 'file', scrollable: scrollable(el),
  });
  const data = nodes.map(describe);
  const textParts = [];
  let textLength = 0;
  for (const root of [document.body, ...all.filter(el => el.shadowRoot).map(el => el.shadowRoot)]) {
    if (!root) continue;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode()) && textLength < 12000) {
      const text = node.textContent.trim();
      if (!text || !node.parentElement || !visible(node.parentElement) || node.parentElement.closest('script,style,noscript')) continue;
      const range = document.createRange(); range.selectNodeContents(node);
      const r = range.getBoundingClientRect();
      if (r.bottom <= 0 || r.top >= innerHeight || r.right <= 0 || r.left >= innerWidth) continue;
      textParts.push(text); textLength += text.length;
    }
  }

  return {nodes, data, truncated: candidates.length > nodes.length, text: textParts.join('\n').slice(0, 12000), text_truncated: textLength >= 12000, url:location.href,
    matches: (index, expected) => nodes[index]?.isConnected && JSON.stringify(describe(nodes[index])) === JSON.stringify(expected) && JSON.stringify(nodes.map(describe)) === JSON.stringify(data)};
}
