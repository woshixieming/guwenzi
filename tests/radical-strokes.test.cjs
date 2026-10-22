const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'assets/radical-strokes.js'), 'utf8');
const strokes = vm.runInNewContext(source + '\nMODERN_RADICAL_STROKES;');
const main = JSON.parse(fs.readFileSync(path.join(root, 'data.js'), 'utf8').slice('const HANZI = '.length).trim().replace(/;$/, ''));
assert.equal(Object.keys(strokes).length, main.radicals.length);
for (const radical of main.radicals) {
  assert.ok(Number.isInteger(strokes[radical]) && strokes[radical] >= 1 && strokes[radical] <= 17, radical);
}
// 简化偏旁按自身笔画，不能沿用繁体地区或部首本字的笔画。
for (const [radical, count] of Object.entries({'一':1,'阝':2,'氵':3,'扌':3,'艹':3,'辶':3,'水':4,'骨':9,'⺁':2,'⺮':6,'⻊':7,'⺗':4,'⺪':5})) {
  assert.equal(strokes[radical], count, radical);
}
assert.notEqual(strokes['氵'], strokes['水']);
assert.notEqual(strokes['扌'], strokes['手']);
console.log('PASS: all 259 modern radicals have own stroke counts, simplified variants and supplemental radical glyphs covered.');
