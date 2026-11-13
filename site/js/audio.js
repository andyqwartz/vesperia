// audio.js — drone génératif dont le timbre suit le froid moyen (Phase 7). Aucun son sans clic de l'utilisateur.
export function createAudio(audio) {
  let ctx = null;
  let nodes = null;

  function build() {
    ctx = new AudioContext();
    const filter = ctx.createBiquadFilter();
    filter.type = 'lowpass';
    const gain = ctx.createGain();
    gain.gain.value = 0;
    [[55, 'sine', 0], [82.5, 'sine', 3], [110.6, 'triangle', -4]].forEach(([f, type, cents]) => {
      const o = ctx.createOscillator();
      o.type = type; o.frequency.value = f; o.detune.value = cents;
      o.connect(filter); o.start();
    });
    filter.connect(gain); gain.connect(ctx.destination);
    nodes = { filter, gain };
  }

  function apply() {
    if (!nodes) return;
    const t = ctx.currentTime;
    nodes.filter.frequency.setTargetAtTime(200 + 1800 * audio.level, t, 0.4);
    nodes.gain.gain.setTargetAtTime(audio.state === 'on' ? 0.02 + 0.08 * audio.level : 0, t, 0.3);
  }

  return {
    async toggle() {
      if (audio.state === 'on') { audio.state = 'off'; apply(); return; }
      audio.state = 'on';
      try {
        if (!ctx) build();
        await ctx.resume();
      } catch (e) { audio.state = 'off'; return; }
      apply();
    },
    update(level) { audio.level = level; apply(); },
  };
}
