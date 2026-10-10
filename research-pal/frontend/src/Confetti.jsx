import { useEffect, useRef } from "react";

// Confetti on a canvas. It listens to the event "rp-confetti" (see juice.js) and draws a short burst. No library.
const COLORS = ["#FFD43B", "#3B6FE0", "#30D158", "#FF6B6B", "#B197FC", "#FF922B"];

export default function Confetti() {
  const ref = useRef(null);

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext?.("2d");
    if (!ctx) return undefined; // a test browser has no canvas
    let parts = [];
    let raf = 0;
    const size = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    size();
    window.addEventListener("resize", size);

    const tick = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      for (const p of parts) {
        p.vy += 0.16;
        p.vx *= 0.992;
        p.x += p.vx;
        p.y += p.vy;
        p.rot += p.vr;
        p.life -= 1;
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate(p.rot);
        ctx.globalAlpha = Math.max(0, Math.min(1, p.life / 40));
        ctx.fillStyle = p.color;
        ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
        ctx.restore();
      }
      parts = parts.filter((p) => p.life > 0 && p.y < canvas.height + 30);
      raf = parts.length ? requestAnimationFrame(tick) : 0;
      if (!parts.length) ctx.clearRect(0, 0, canvas.width, canvas.height);
    };

    const burst = (e) => {
      const big = e.detail?.power === "big";
      const n = big ? 150 : 55;
      const W = canvas.width;
      const H = canvas.height;
      for (let i = 0; i < n; i++) {
        // Two cannons at the bottom corners for a big burst. One burst from the middle for a small one.
        const left = big ? i % 2 === 0 : false;
        const x = big ? (left ? W * 0.12 : W * 0.88) : W * 0.5 + (Math.random() - 0.5) * W * 0.2;
        const y = big ? H * 0.85 : H * 0.35;
        const angle = big ? (left ? -Math.PI / 3 : (-2 * Math.PI) / 3) + (Math.random() - 0.5) * 0.9 : -Math.PI / 2 + (Math.random() - 0.5) * 2.4;
        const speed = (big ? 9 : 5) + Math.random() * (big ? 9 : 5);
        parts.push({
          x, y, vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed,
          w: 6 + Math.random() * 6, h: 4 + Math.random() * 5, rot: Math.random() * 6, vr: (Math.random() - 0.5) * 0.4,
          color: COLORS[(Math.random() * COLORS.length) | 0], life: 90 + Math.random() * 60,
        });
      }
      if (!raf) raf = requestAnimationFrame(tick);
    };

    window.addEventListener("rp-confetti", burst);
    return () => {
      window.removeEventListener("rp-confetti", burst);
      window.removeEventListener("resize", size);
      cancelAnimationFrame(raf);
    };
  }, []);

  return <canvas ref={ref} className="confetti" aria-hidden="true" />;
}
