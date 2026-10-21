/* 异体查字共用规则；保留原码位，不对输入做繁简转换或兼容归一化。 */
(function(root){
  'use strict';
  function isHan(c){
    if (typeof c !== 'string' || [...c].length !== 1) return false;
    const n = c.codePointAt(0);
    return (n >= 0x3400 && n <= 0x4dbf) || (n >= 0x4e00 && n <= 0x9fff) ||
      (n >= 0xf900 && n <= 0xfaff) || (n >= 0x20000 && n <= 0x323af);
  }
  function matches(data, ch){
    const grouped = new Map();
    for (const [target, type, source] of data.chars[ch]?.m || []) {
      if (!grouped.has(target)) grouped.set(target, {character:target, evidence:[], reference:true});
      const item = grouped.get(target);
      item.evidence.push({type, source});
      if (type !== 'reference') item.reference = false;
    }
    return [...grouped.values()].sort((a,b) => Number(a.reference) - Number(b.reference));
  }
  function uniqueTarget(data, ch){
    const options = matches(data,ch).filter(x => !x.reference);
    return options.length === 1 ? options[0].character : null;
  }
  function filter(data, options){
    const radical = Number(options.radical || 0), strokes = options.strokes;
    const useStrokes = strokes !== '' && strokes != null;
    const tolerance = options.nearby ? 1 : 0;
    const components = [...(options.components || '').replace(/[\s+、，,]/g,'')];
    return Object.entries(data.chars).filter(([ch,r]) => {
      if (options.mappedOnly && !(r.m || []).length) return false;
      const radicalEntries = radical ? r.r.filter(([n]) => n === radical) : r.r;
      if (radical && !radicalEntries.length) return false;
      if (useStrokes) {
        const numbers = options.strokeKind === 'remaining' ? radicalEntries.map(x => x[1]) : r.s;
        if (!numbers.some(n => n >= 0 && Math.abs(n - Number(strokes)) <= tolerance)) return false;
      }
      if (components.length && !(r.k || []).some(parts => components.every(c => parts.includes(c)))) return false;
      return true;
    }).sort(([a,ar],[b,br]) => (ar.s[0] ?? 999) - (br.s[0] ?? 999) || a.codePointAt(0) - b.codePointAt(0));
  }
  root.VariantCore = {isHan, matches, uniqueTarget, filter};
})(typeof window === 'undefined' ? globalThis : window);
