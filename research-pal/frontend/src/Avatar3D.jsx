import { useEffect, useRef, useState } from "react";
import { ITEMS, avatarShown, lookFor, setAvatarShown, webglOk } from "./avatar.js";

const reduceMotion = () => document.documentElement.getAttribute("data-anim") === "off" || (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);

// A flat picture with the same items. Used when the browser has no WebGL.
export function AvatarFallback({ items }) {
  const has = (c) => items.includes(c);
  return (
    <svg className="avatar-flat" viewBox="0 0 120 150" role="img" aria-label={`Avatar with: ${items.join(", ")}`}>
      {has("backpack") && <rect x="22" y="58" width="22" height="42" rx="6" fill="#8a5a2b" />}
      <rect x="40" y="55" width="40" height="50" rx="10" fill="#4f7cff" />
      <circle cx="60" cy="35" r="20" fill="#f3c9a0" />
      {has("glasses") && <path d="M44 33h14M62 33h14" stroke="#222" strokeWidth="4" />}
      {has("cap") && <path d="M36 22h48l-24-14z" fill="#222" />}
      {has("lens") && <circle cx="92" cy="86" r="9" fill="none" stroke="#c9a227" strokeWidth="3" />}
      {has("pen") && <path d="M84 60l12 30" stroke="#444" strokeWidth="3" />}
      {has("rope") && <path d="M40 98c10 8 30 8 40 0" fill="none" stroke="#b08850" strokeWidth="4" />}
      <rect x="44" y="105" width="12" height="36" rx="5" fill="#333" />
      <rect x="64" y="105" width="12" height="36" rx="5" fill="#333" />
    </svg>
  );
}

function build(THREE, items) {
  const has = (c) => items.includes(c);
  const mat = (color) => new THREE.MeshStandardMaterial({ color, roughness: 0.6 });
  const part = (geo, color, x = 0, y = 0, z = 0) => {
    const m = new THREE.Mesh(geo, mat(color));
    m.position.set(x, y, z);
    return m;
  };
  const g = new THREE.Group();
  g.add(part(new THREE.CapsuleGeometry(0.42, 0.7, 6, 12), 0x4f7cff, 0, 0.2, 0)); // body
  g.add(part(new THREE.SphereGeometry(0.4, 20, 16), 0xf3c9a0, 0, 1.15, 0)); // head
  g.add(part(new THREE.SphereGeometry(0.06, 8, 8), 0x222222, -0.14, 1.2, 0.36));
  g.add(part(new THREE.SphereGeometry(0.06, 8, 8), 0x222222, 0.14, 1.2, 0.36));
  g.add(part(new THREE.CapsuleGeometry(0.14, 0.5, 4, 8), 0x333333, -0.2, -0.75, 0)); // legs
  g.add(part(new THREE.CapsuleGeometry(0.14, 0.5, 4, 8), 0x333333, 0.2, -0.75, 0));
  g.add(part(new THREE.CapsuleGeometry(0.1, 0.5, 4, 8), 0x4f7cff, -0.58, 0.2, 0)); // arms
  g.add(part(new THREE.CapsuleGeometry(0.1, 0.5, 4, 8), 0x4f7cff, 0.58, 0.2, 0));
  if (has("backpack")) g.add(part(new THREE.BoxGeometry(0.55, 0.7, 0.3), 0x8a5a2b, 0, 0.25, -0.5));
  if (has("glasses")) {
    for (const x of [-0.14, 0.14]) {
      const r = part(new THREE.TorusGeometry(0.1, 0.02, 8, 16), 0x222222, x, 1.2, 0.39);
      g.add(r);
    }
    g.add(part(new THREE.BoxGeometry(0.5, 0.35, 0.08), 0xd9534f, -0.62, 0, 0.3)); // a book in the left hand
  }
  if (has("lens")) {
    const ring = part(new THREE.TorusGeometry(0.16, 0.03, 8, 20), 0xc9a227, 0.7, 0.1, 0.3);
    g.add(ring, part(new THREE.CylinderGeometry(0.02, 0.02, 0.35, 8), 0x444444, 0.7, -0.15, 0.3));
  }
  if (has("rope")) {
    const rope = part(new THREE.TorusGeometry(0.5, 0.04, 8, 28), 0xb08850, 0, 0.55, 0);
    rope.rotation.x = Math.PI / 2;
    g.add(rope, part(new THREE.SphereGeometry(0.09, 8, 8), 0xb08850, 0.5, 0.55, 0));
  }
  if (has("pen")) {
    g.add(part(new THREE.CylinderGeometry(0.03, 0.03, 0.6, 8), 0x333333, 0.62, 0.55, 0.15));
    g.add(part(new THREE.CylinderGeometry(0.08, 0.08, 0.45, 12), 0xf5e6b3, 0.78, -0.25, 0.2));
  }
  if (has("cap")) {
    g.add(part(new THREE.CylinderGeometry(0.42, 0.42, 0.1, 16), 0x222222, 0, 1.55, 0));
    g.add(part(new THREE.BoxGeometry(0.9, 0.04, 0.9), 0x222222, 0, 1.63, 0));
    g.add(part(new THREE.OctahedronGeometry(0.1), 0xffd700, 0.4, 1.5, 0));
  }
  return g;
}

// A small 3D character. The look comes from the level. The student turns it with the pointer.
export function Avatar3D({ level }) {
  const box = useRef(null);
  const look = lookFor(level);
  const [flat, setFlat] = useState(!webglOk());
  useEffect(() => {
    if (flat || !box.current) return;
    let stop = false;
    let cleanup = () => {};
    import("three")
      .then((THREE) => {
        if (stop || !box.current) return;
        const el = box.current;
        const w = el.clientWidth || 240;
        const h = 260;
        const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        renderer.setSize(w, h);
        el.appendChild(renderer.domElement);
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(40, w / h, 0.1, 50);
        camera.position.set(0, 0.6, 5.2);
        scene.add(new THREE.HemisphereLight(0xffffff, 0x8899aa, 1.6));
        const sun = new THREE.DirectionalLight(0xffffff, 1.4);
        sun.position.set(3, 5, 4);
        scene.add(sun);
        const model = build(THREE, look.items);
        scene.add(model);
        let drag = null;
        const down = (e) => (drag = e.clientX);
        const move = (e) => {
          if (drag !== null) {
            model.rotation.y += (e.clientX - drag) * 0.012;
            drag = e.clientX;
          }
        };
        const up = () => (drag = null);
        const c = renderer.domElement;
        c.addEventListener("pointerdown", down);
        window.addEventListener("pointermove", move);
        window.addEventListener("pointerup", up);
        let raf = 0;
        const tick = () => {
          if (!reduceMotion() && drag === null && !document.hidden) model.rotation.y += 0.008;
          renderer.render(scene, camera);
          raf = requestAnimationFrame(tick);
        };
        tick();
        cleanup = () => {
          cancelAnimationFrame(raf);
          c.removeEventListener("pointerdown", down);
          window.removeEventListener("pointermove", move);
          window.removeEventListener("pointerup", up);
          model.traverse((o) => {
            o.geometry?.dispose();
            o.material?.dispose();
          });
          renderer.dispose();
          renderer.domElement.remove();
        };
      })
      .catch(() => setFlat(true));
    return () => {
      stop = true;
      cleanup();
    };
  }, [flat, look.items.join(",")]);
  return flat ? <AvatarFallback items={look.items} /> : <div ref={box} className="avatar3d" role="img" aria-label={`3D avatar with: ${look.items.join(", ")}. Drag to turn it.`} />;
}

export default function AvatarCard({ level }) {
  const [shown, setShown] = useState(avatarShown());
  const look = lookFor(level);
  const names = ITEMS.filter((it) => look.items.includes(it.code)).map((it) => it.name);
  return (
    <section className="today-block avatarcard" aria-label="Avatar">
      <h2>Avatar</h2>
      {shown ? <Avatar3D level={level} /> : <p className="small muted">The avatar is hidden.</p>}
      <p className="small">Items: {names.join(", ")}.</p>
      <p className="small muted">{look.next ? `At the next level you get: ${look.next.name}.` : "You have all the items. Thank you for the work."}</p>
      <button
        className="link"
        onClick={() => {
          setAvatarShown(!shown);
          setShown(!shown);
        }}
      >
        {shown ? "Hide avatar" : "Show avatar"}
      </button>
    </section>
  );
}
