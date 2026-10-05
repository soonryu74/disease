/* 유행 시뮬레이터 계산 엔진 — 화면과 떼어 놓은 순수 계산.

   왜 떼어 놓았나
     화면에 붙어 있으면 시험할 수가 없다. 이 파일은 DOM 을 쓰지 않으므로
     브라우저 밖(node)에서 그대로 불러 검산할 수 있다.
     빌드할 때 build_sim.py 가 이 내용을 HTML 안에 그대로 넣는다 —
     따로 받아 가는 파일이 늘지 않는다.

   이 모형이 무엇인가
     구획 하나하나가 '사람 묶음'인 결정론적 SEIR 모형이다.
     개인을 따라다니지 않는다. 그래서 '누가 누구에게 옮겼는지'는 이 모형에 없다.
     같은 입력이면 언제나 같은 결과가 나온다(무작위 요소 없음).

   S 아직 안 걸린 사람 / E 걸렸지만 아직 남에게 못 옮기는 사람 /
   I 남에게 옮길 수 있는 사람 / R 회복했거나 처음부터 보호받던 사람.
*/
(function (root) {
  'use strict';

  var MODEL = 'SEIR-deterministic';
  var VERSION = '2.0.0';
  var SCHEMA = 'disease-sim/1';

  /* 입력이 받아들일 수 있는 범위. 화면·JSON·코드가 모두 이 표 하나를 본다. */
  var LIMITS = {
    N:      {min: 1000,  max: 50000000, int: true,  label: '인구'},
    I0:     {min: 0,     max: 1000000,  int: true,  label: '첫 감염자'},
    days:   {min: 30,    max: 730,      int: true,  label: '관찰 기간(일)'},
    r0:     {min: 0,     max: 50,       int: false, label: 'R₀'},
    delay:  {min: 0,     max: 14,       int: false, label: '증상→격리(일)'},
    eff:    {min: 0,     max: 100,      int: false, label: '격리 효과(%)'},
    trace:  {min: 0,     max: 100,      int: false, label: '접촉자 추적(%)'},
    vacc:   {min: 0,     max: 100,      int: false, label: '접종률(%)'},
    vaccEff:  {min: 0,   max: 100,      int: false, label: '백신 감염예방 효과(%) — 가정'},
    traceEff: {min: 0,   max: 100,      int: false, label: '추적 효과(%) — 가정'}
  };

  function num(v) {
    if (typeof v === 'string') v = v.trim();
    if (v === '' || v === null || v === undefined) return NaN;
    var n = Number(v);
    return isFinite(n) ? n : NaN;
  }

  /* 값 하나를 검사한다. 고치지 않고, 무엇이 왜 틀렸는지만 돌려준다. */
  function checkOne(key, value) {
    var L = LIMITS[key];
    if (!L) return null;
    var n = num(value);
    if (isNaN(n)) return L.label + ': 숫자가 아닙니다';
    if (L.int && Math.floor(n) !== n) return L.label + ': 정수여야 합니다';
    if (n < L.min || n > L.max) return L.label + ': ' + L.min + '~' + L.max + ' 사이여야 합니다 (넣은 값 ' + n + ')';
    return null;
  }

  /* 한 번에 전부 검사한다. 하나라도 틀리면 계산을 시작하지 않는다. */
  function validate(common, scen, assume) {
    var errs = [];
    ['N', 'I0', 'days'].forEach(function (k) { var e = checkOne(k, common[k]); if (e) errs.push(e); });
    ['delay', 'eff', 'trace', 'vacc'].forEach(function (k) { var e = checkOne(k, scen[k]); if (e) errs.push(e); });
    if (scen.r0 !== null && scen.r0 !== undefined) {
      var e0 = checkOne('r0', scen.r0); if (e0) errs.push(e0);
    }
    ['vaccEff', 'traceEff'].forEach(function (k) { var e = checkOne(k, assume[k]); if (e) errs.push(e); });
    if (errs.length) return errs;

    /* 사람 수가 서로 어긋나지 않는지. 보호받는 사람과 첫 감염자를 더해
       전체 인구를 넘으면 아직 안 걸린 사람이 음수가 된다. */
    var N = num(common.N), I0 = num(common.I0);
    var prot = N * (num(scen.vacc) / 100) * (num(assume.vaccEff) / 100);
    if (I0 > N) errs.push('첫 감염자가 인구보다 많습니다');
    else if (prot + I0 > N) {
      errs.push('보호받는 사람 ' + Math.round(prot).toLocaleString('ko-KR') + '명과 첫 감염자 ' +
                I0.toLocaleString('ko-KR') + '명을 더하면 인구 ' + N.toLocaleString('ko-KR') + '명을 넘습니다');
    }
    return errs;
  }

  /* 한 칸이 너무 크면 값이 튄다. 가장 빠른 흐름에 맞춰 칸을 줄인다.
     4차 룽게–쿠타는 같은 칸에서 전진 오일러보다 훨씬 정확하므로 여유를 둘 수 있다.
     쓴 칸 크기는 결과(meta.dt)에 적어 둔다. */
  function pickStep(beta, latent, Dinf, want) {
    var fastest = Math.max(beta, 1 / latent, 1 / Dinf, 1e-9);
    var safe = 0.5 / fastest;
    var dt = Math.min(want, safe);
    if (!(dt > 0) || !isFinite(dt)) dt = 0.01;
    return Math.max(dt, 1e-4);
  }

  /* 변화율. y = [S, E, I, R, 누적 새 감염]
     누적을 같이 적분해야 하루치 새 감염이 S 의 감소와 어긋나지 않는다. */
  function deriv(y, beta, N, latent, Dinf) {
    var S = y[0], E = y[1], I = y[2];
    var ne = beta * I * S / N;
    var ei = E / latent;
    var ir = I / Dinf;
    return [-ne, ne - ei, ei - ir, ir, ne];
  }

  function rk4(y, h, beta, N, latent, Dinf) {
    var k1 = deriv(y, beta, N, latent, Dinf);
    var y2 = [], y3 = [], y4 = [], i;
    for (i = 0; i < 5; i++) y2[i] = y[i] + h / 2 * k1[i];
    var k2 = deriv(y2, beta, N, latent, Dinf);
    for (i = 0; i < 5; i++) y3[i] = y[i] + h / 2 * k2[i];
    var k3 = deriv(y3, beta, N, latent, Dinf);
    for (i = 0; i < 5; i++) y4[i] = y[i] + h * k3[i];
    var k4 = deriv(y4, beta, N, latent, Dinf);
    var out = [];
    for (i = 0; i < 5; i++) out[i] = y[i] + h / 6 * (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i]);
    return out;
  }

  /* 본 계산.
       disease  모형 매개변수(이름·R₀ 범위·전염 기간·증상 전 전염 일수·잠복기)
       common   인구·첫 감염자·관찰 기간
       scen     이 시나리오의 대응 조건
       assume   교육용 가정값(백신 효과·추적 효과·시간 칸)
     돌려주는 것은 하루치 기록이 든 배열과 그 요약이다. */
  function simulate(disease, common, scen, assume) {
    assume = assume || {};
    var A = {
      vaccEff: assume.vaccEff === undefined ? 90 : num(assume.vaccEff),
      traceEff: assume.traceEff === undefined ? 90 : num(assume.traceEff),
      dt: assume.dt === undefined ? 0.25 : num(assume.dt)
    };
    var errs = validate(common, scen, A);
    if (errs.length) return {ok: false, errors: errs};

    var N = num(common.N), I0 = num(common.I0), days = num(common.days);
    var R0 = (scen.r0 === null || scen.r0 === undefined)
      ? Math.round((disease.r0[0] + disease.r0[1]) / 2 * 10) / 10 : num(scen.r0);
    var Dinf = disease.d_inf, presym = disease.presym;
    var latent = Math.max(1, disease.incubation.typ - presym);

    /* 격리가 손대지 못하는 전염 기간의 몫.
       증상 전 기간과 격리까지의 지연을 전염 기간으로 나눈 것이다.
       하루하루 전염력이 같다고 본 기간 비율이지, 실제 전파의 몇 %가
       그때 일어났는지를 잰 값이 아니다. */
    var cov = Math.min(presym + num(scen.delay), Dinf) / Dinf;
    var fIso = cov + (1 - cov) * (1 - num(scen.eff) / 100);
    var fCt = 1 - (num(scen.trace) / 100) * (A.traceEff / 100);
    var initialProtected = N * (num(scen.vacc) / 100) * (A.vaccEff / 100);
    var S0 = N - initialProtected - I0;              // 처음에 아직 안 걸린 사람
    var beta = R0 / Dinf * fIso * fCt;

    /* 처음의 유효 재생산수. 실제 초기 S 를 쓴다.
       예전에는 첫 감염자를 빼기 전 수를 썼다 — 첫 감염자가 적으면 차이가 거의 없지만
       정의로는 S(0)/N 이 맞다. */
    var Reff0 = R0 * fIso * fCt * (S0 / N);

    var dt = pickStep(beta, latent, Dinf, A.dt);
    var steps = Math.max(1, Math.round(1 / dt));
    dt = 1 / steps;                                   // 하루가 정수 칸으로 나뉘게 맞춘다

    var y = [S0, 0, I0, initialProtected, 0];        // S, E, I, R, 누적 새 감염
    var history = [{day: 0, S: y[0], E: y[1], I: y[2], R: y[3], newInf: 0, cumInf: I0}];
    var peak = {day: 0, newInf: 0};
    var warnings = [];

    for (var day = 1; day <= days; day++) {
      var before = y[4];
      for (var k = 0; k < steps; k++) y = rk4(y, dt, beta, N, latent, Dinf);
      /* 아주 작은 음수는 계산 오차다. 0으로 눌러 두되 사람 수가 늘지 않게 한다. */
      for (var q = 0; q < 4; q++) if (y[q] < 0 && y[q] > -1e-6) y[q] = 0;
      var dayNew = y[4] - before;
      if (dayNew < 0) dayNew = 0;
      history.push({day: day, S: y[0], E: y[1], I: y[2], R: y[3],
                    newInf: dayNew, cumInf: I0 + y[4]});
      if (dayNew > peak.newInf) { peak = {day: day, newInf: dayNew}; }
    }
    var cum = I0 + y[4];

    /* 끝까지 돌린 뒤 사람 수가 맞는지 본다. 어긋나면 숨기지 않고 알린다. */
    var last = history[history.length - 1];
    var total = last.S + last.E + last.I + last.R;
    var relErr = Math.abs(total - N) / N;
    if (relErr > 1e-8) warnings.push('사람 수 합계가 ' + relErr.toExponential(2) + ' 만큼 어긋났습니다');
    for (var h = 0; h < history.length; h++) {
      var x = history[h];
      if (!isFinite(x.S + x.E + x.I + x.R + x.newInf + x.cumInf)) {
        warnings.push(x.day + '일째 계산이 수로 나오지 않았습니다');
        break;
      }
    }

    /* 관찰이 끝난 날에도 E·I 가 남아 있으면 '끝났다'고 말하지 않는다. */
    var stillRunning = (last.E + last.I) >= 1;
    var endDay = null;
    for (var j = peak.day + 1; j < history.length; j++) {
      if (history[j].E + history[j].I < 1) { endDay = history[j].day; break; }
    }

    return {
      ok: true,
      model: MODEL, version: VERSION,
      meta: {
        name: disease.name, R0: R0, Reff0: Reff0, beta: beta, latent: latent,
        Dinf: Dinf, presym: presym, cov: cov, fIso: fIso, fCt: fCt,
        initialProtected: initialProtected, S0: S0, N: N, I0: I0, days: days,
        dt: dt, stepsPerDay: steps,
        vaccEff: A.vaccEff, traceEff: A.traceEff
      },
      history: history,
      peak: peak,
      totals: {
        cumInf: cum,                 // 첫 감염자 I0 를 포함한 누적이다
        cumIncludesI0: true,
        attack: cum / N,
        recovered: last.R - initialProtected,
        endDay: endDay,
        stillRunning: stillRunning
      },
      warnings: warnings
    };
  }

  /* 비율을 점 개수로 바꾼다. 최대잔여법이라 합계가 늘 같다.
     아주 작은 비율은 0개가 될 수 있다 — 그래서 실제 숫자를 따로 보여 줘야 한다. */
  function allocate(values, dots) {
    var sum = values.reduce(function (a, b) { return a + b; }, 0);
    if (!(sum > 0)) return values.map(function () { return 0; });
    var exact = values.map(function (v) { return v / sum * dots; });
    var base = exact.map(Math.floor);
    var used = base.reduce(function (a, b) { return a + b; }, 0);
    var rest = exact.map(function (v, i) { return {i: i, f: v - base[i]}; })
                    .sort(function (a, b) { return b.f - a.f; });
    for (var k = 0; k < dots - used; k++) base[rest[k % rest.length].i]++;
    return base;
  }

  var api = {
    MODEL: MODEL, VERSION: VERSION, SCHEMA: SCHEMA, LIMITS: LIMITS,
    simulate: simulate, validate: validate, checkOne: checkOne, allocate: allocate
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.SimEngine = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
