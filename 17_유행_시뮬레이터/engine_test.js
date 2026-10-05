#!/usr/bin/env node
/* 계산 엔진 검산 — 화면 없이 숫자만 본다.
   실행:  node 17_유행_시뮬레이터/engine_test.js
   하나라도 실패하면 1을 돌려준다. */
'use strict';
const path = require('path');
const fs = require('fs');
const ROOT = path.dirname(__dirname);
const E = require(path.join(ROOT, 'scripts', 'templates', 'sim.engine.js'));
const P = JSON.parse(fs.readFileSync(path.join(ROOT, '17_유행_시뮬레이터', 'data', '모형_매개변수.json'), 'utf8'));

let pass = 0, fail = 0;
function ok(name, cond, note) {
  if (cond) { pass++; console.log('  ✓ ' + name); }
  else { fail++; console.log('  ✗ ' + name + (note ? '  — ' + note : '')); }
}
function head(t) { console.log('\n── ' + t); }

/* 도감 잠복기는 build_sim 이 붙이므로, 시험에서는 매개변수 파일의 값으로 대신 채운다. */
const INC = {
  '홍역': 11, '백일해': 8.5, '수두': 15, '유행성이하선염': 16, '풍진': 16,
  '디프테리아': 3.5, '폴리오': 4.5, '인플루엔자': 2, '신종인플루엔자': 2.5,
  '코로나바이러스감염증-19': 6, '중증급성호흡기증후군': 5, '중동호흡기증후군': 5.5,
  '에볼라바이러스병': 11.5, '엠폭스': 9.5, '니파바이러스감염증': 9
};
const DZ = {};
P.diseases.forEach(d => { DZ[d.name] = Object.assign({}, d, {incubation: {typ: INC[d.name]}}); });

const D = P.intervention_defaults;
const common = {N: D.N, I0: D.I0, days: D.days};
const base = {r0: null, delay: D.iso_delay, eff: D.iso_eff * 100, trace: D.trace * 100, vacc: D.vacc * 100};
const assume = {vaccEff: D.vacc_eff * 100, traceEff: D.trace_eff * 100, dt: 0.25};
const S = (name, over, com, as) =>
  E.simulate(DZ[name], Object.assign({}, common, com || {}),
             Object.assign({}, base, over || {}), Object.assign({}, assume, as || {}));

head('기본 — 모든 질환이 계산되는가');
let allOk = true, bad = [];
for (const n of Object.keys(DZ)) {
  const r = S(n);
  if (!r.ok || r.warnings.length) { allOk = false; bad.push(n + (r.ok ? ' 경고:' + r.warnings[0] : ' 실패')); }
}
ok(`15종 모두 계산되고 경고가 없다`, allOk, bad.join(' / '));

head('보존 — 사람 수는 늘지도 줄지도 않는다');
let consOk = true, worst = 0;
for (const n of Object.keys(DZ)) {
  const r = S(n);
  for (const h of r.history) {
    const t = h.S + h.E + h.I + h.R;
    const rel = Math.abs(t - common.N) / common.N;
    if (rel > worst) worst = rel;
    if (rel > 1e-8) consOk = false;
  }
}
ok('모든 시점 S+E+I+R = N (상대오차 1e-8 이내)', consOk, '최대 ' + worst.toExponential(2));

head('음수·무한 — 나오면 안 된다');
let negOk = true;
for (const n of Object.keys(DZ)) {
  for (const over of [{}, {eff: 100, trace: 100, vacc: 99}, {delay: 14, eff: 0}, {r0: 0}]) {
    const r = S(n, over);
    if (!r.ok) continue;
    for (const h of r.history) {
      if (!isFinite(h.S + h.E + h.I + h.R) || h.S < -1e-9 || h.E < -1e-9 || h.I < -1e-9 || h.R < -1e-9) negOk = false;
    }
  }
}
ok('극단 입력에서도 음수·NaN·Infinity 가 없다', negOk);

head('단조 — 누적 감염은 줄지 않는다');
let monoOk = true;
for (const n of Object.keys(DZ)) {
  const r = S(n);
  for (let i = 1; i < r.history.length; i++) if (r.history[i].cumInf < r.history[i - 1].cumInf - 1e-9) monoOk = false;
}
ok('누적 감염이 어느 날도 줄지 않는다', monoOk);

head('상한 — 걸릴 수 있는 사람보다 많이 걸릴 수 없다');
let capOk = true, capNote = '';
for (const n of Object.keys(DZ)) {
  const r = S(n, {vacc: 30});
  const cap = r.meta.N - r.meta.initialProtected;        // I0 포함 누적이므로 보호 인구를 뺀 전체가 상한
  const got = r.totals.cumInf;
  if (got > cap + 1e-6) { capOk = false; capNote = n + ' ' + got.toFixed(1) + ' > ' + cap.toFixed(1); }
}
ok('누적 감염 ≤ 인구 − 처음부터 보호받던 사람', capOk, capNote);

head('A = B — 같은 조건이면 같은 결과');
const a1 = S('홍역'), b1 = S('홍역');
let sameOk = a1.history.length === b1.history.length;
for (let i = 0; sameOk && i < a1.history.length; i++) {
  const x = a1.history[i], y = b1.history[i];
  if (x.S !== y.S || x.E !== y.E || x.I !== y.I || x.R !== y.R || x.newInf !== y.newInf) sameOk = false;
}
ok('전체 시계열이 한 값도 다르지 않다', sameOk);
ok('정점과 누적도 같다', a1.peak.day === b1.peak.day && a1.peak.newInf === b1.peak.newInf
   && a1.totals.cumInf === b1.totals.cumInf);

head('꺼진 손잡이 — 0이면 짝이 되는 값은 결과를 바꾸지 못한다');
const noIso = [S('홍역', {eff: 0, delay: 0}), S('홍역', {eff: 0, delay: 14})];
ok('격리 효과 0이면 지연을 바꿔도 같다', noIso[0].totals.cumInf === noIso[1].totals.cumInf);
const noVac = [S('홍역', {vacc: 0}, null, {vaccEff: 0}), S('홍역', {vacc: 0}, null, {vaccEff: 100})];
ok('접종률 0이면 백신 효과를 바꿔도 같다', noVac[0].totals.cumInf === noVac[1].totals.cumInf);
const noTr = [S('홍역', {trace: 0}, null, {traceEff: 0}), S('홍역', {trace: 0}, null, {traceEff: 100})];
ok('추적률 0이면 추적 효과를 바꿔도 같다', noTr[0].totals.cumInf === noTr[1].totals.cumInf);

head('전파 0 — 새 감염이 생기지 않는다');
const zero = S('홍역', {r0: 0});
ok('R₀=0 이면 새 감염 합계가 0', zero.ok && zero.history.every(h => h.newInf === 0));
ok('R₀=0 이면 누적이 첫 감염자 그대로', zero.totals.cumInf === common.I0);

head('첫 감염자 0 — 유행이 시작되지 않는다');
const i0 = S('홍역', {}, {I0: 0});
ok('I0=0 을 받아들인다', i0.ok);
ok('I0=0 이면 새 감염이 없다', i0.ok && i0.history.every(h => h.newInf === 0));

head('0일 기록 — 정의대로인가');
const h0 = S('홍역').history[0];
ok('0일의 새 감염은 0', h0.newInf === 0);
ok('0일의 누적은 첫 감염자 수', h0.cumInf === common.I0);
ok('0일의 I 는 첫 감염자 수', h0.I === common.I0);
ok('기록 길이는 관찰 기간 + 1(0일 포함)', S('홍역').history.length === common.days + 1);

head('잘못된 입력 — 받아들이면 안 된다');
const bads = [
  ['인구가 비었다', {N: ''}, {}],
  ['인구가 숫자가 아니다', {N: 'abc'}, {}],
  ['인구가 Infinity', {N: Infinity}, {}],
  ['기간이 상한을 넘는다', {days: 5000}, {}],
  ['기간이 하한보다 작다', {days: 1}, {}],
  ['첫 감염자가 음수', {I0: -5}, {}],
  ['첫 감염자가 인구보다 많다', {N: 1000, I0: 2000}, {}],
  ['접종률이 100을 넘는다', {}, {vacc: 150}],
  ['격리 효과가 NaN', {}, {eff: NaN}],
  ['지연이 범위를 넘는다', {}, {delay: 99}]
];
for (const [name, com, over] of bads) {
  const r = S('홍역', over, com);
  ok(name + ' → 거부', r.ok === false && r.errors.length > 0);
}

head('보호 인구 + 첫 감염자 > 인구 — 막는다');
const over = S('홍역', {vacc: 100}, {N: 1000, I0: 999}, {vaccEff: 100});
ok('S 가 음수가 될 입력을 거부한다', over.ok === false, over.ok ? '통과해 버림' : '');

head('전국 인구 — 역산 실험이 쓰는 크기로도 돈다');
const nation = S('코로나바이러스감염증-19', {}, {N: 51700000});
ok('인구 5,170만으로 계산된다', nation.ok, nation.ok ? '' : (nation.errors||[])[0]);
ok('그 결과도 사람 수가 맞는다', nation.ok &&
   Math.abs((nation.history[nation.history.length-1].S + nation.history[nation.history.length-1].E
           + nation.history[nation.history.length-1].I + nation.history[nation.history.length-1].R) - 51700000) / 51700000 < 1e-8);
ok('인구 상한을 넘으면 여전히 거부', S('홍역', {}, {N: 200000000}).ok === false);

head('관찰 종료와 유행 종료를 가른다');
const shortRun = S('홍역', {}, {days: 30});
ok('30일만 보면 아직 진행 중으로 표시', shortRun.totals.stillRunning === true && shortRun.totals.endDay === null);
const mers = S('중동호흡기증후군');
ok('메르스는 관찰 기간 안에 잦아든다', mers.totals.stillRunning === false && mers.totals.endDay !== null);

head('점 배분 — 합계가 늘 같다');
let dotOk = true;
for (const vals of [[1, 0, 0, 0], [0.5, 0.2, 0.2, 0.1], [99999, 1, 0, 0], [0, 0, 0, 0]]) {
  const a = E.allocate(vals, 300);
  const sum = a.reduce((x, y) => x + y, 0);
  if (vals.some(v => v > 0) && sum !== 300) dotOk = false;
  if (a.some(v => v < 0)) dotOk = false;
}
ok('어떤 비율이어도 점 합계는 300', dotOk);
ok('아주 작은 비율은 0개가 될 수 있다', E.allocate([99999, 1, 0, 0], 300)[1] === 0);

head('시간 칸 — 줄여도 답이 크게 달라지지 않는다');
const c1 = S('홍역', {}, {}, {dt: 0.25}).totals.cumInf;
const c2 = S('홍역', {}, {}, {dt: 0.05}).totals.cumInf;
ok('dt 0.25 와 0.05 의 누적 차이가 1% 미만', Math.abs(c1 - c2) / c1 < 0.01,
   ((Math.abs(c1 - c2) / c1) * 100).toFixed(3) + '%');
const big = S('홍역', {r0: 40}, {}, {dt: 1});
ok('칸이 커도 엔진이 알아서 줄여 음수가 안 난다', big.ok && big.history.every(h => h.S >= -1e-9) && big.meta.dt < 1);

console.log(`\n── 결과: 통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
