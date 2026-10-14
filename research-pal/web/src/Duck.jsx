import { motion } from "motion/react";
import { useApp } from "./store.js";

// The Duck: the companion of the student. It is a small SVG, so it is sharp at each size and costs no image file.
// mood: idle | happy | cheer | sleepy | oops (a kind "oops", never an angry face)
// stage: duckling | duck | scholar (it grows with the level)
// outfit: { head, eyes, neck, body } with the items that the student bought in the shop
const Y = "#FFD43B";
const Y_DARK = "#F2B705";
const ORANGE = "#FF922B";
const INK = "#1E1E24";

function Eyes({ mood }) {
  if (mood === "happy" || mood === "cheer") {
    return (
      <g stroke={INK} strokeWidth="3" strokeLinecap="round" fill="none">
        <path d="M45 40 q5 -6 10 0" />
        <path d="M65 40 q5 -6 10 0" />
      </g>
    );
  }
  if (mood === "sleepy") {
    return (
      <g stroke={INK} strokeWidth="3" strokeLinecap="round" fill="none">
        <path d="M45 40 q5 4 10 0" />
        <path d="M65 40 q5 4 10 0" />
      </g>
    );
  }
  return (
    <g>
      <g className="duck-eye">
        <circle cx="50" cy="39" r="4" fill={INK} />
        <circle cx="51.4" cy="37.6" r="1.3" fill="#fff" />
      </g>
      <g className="duck-eye">
        <circle cx="70" cy="39" r="4" fill={INK} />
        <circle cx="71.4" cy="37.6" r="1.3" fill="#fff" />
      </g>
      {mood === "oops" && (
        <g stroke={INK} strokeWidth="2.4" strokeLinecap="round">
          <path d="M44 33 l9 -3" />
          <path d="M76 33 l-9 -3" />
        </g>
      )}
    </g>
  );
}

function Head({ item, stage }) {
  if (item === "cap") {
    return (
      <g>
        <path d="M38 27 q22 -22 44 0 z" fill="#3B6FE0" />
        <path d="M60 14 q20 0 33 12 l-10 0 q-10 -6 -23 -6 z" fill="#2F58B8" />
        <circle cx="60" cy="13" r="2.4" fill="#fff" />
      </g>
    );
  }
  if (item === "mortarboard") {
    return (
      <g>
        <path d="M44 24 h32 v-6 h-32 z" fill="#2B2B33" />
        <path d="M60 8 L92 18 L60 28 L28 18 z" fill="#3A3A44" />
        <path d="M86 20 v14" stroke="#F2B705" strokeWidth="2.4" strokeLinecap="round" />
        <circle cx="86" cy="36" r="3" fill="#F2B705" />
      </g>
    );
  }
  if (item === "crown") {
    return (
      <g>
        <path d="M42 24 l-4 -16 l12 8 l10 -12 l10 12 l12 -8 l-4 16 z" fill="#F5B301" stroke="#C98A00" strokeWidth="1.5" strokeLinejoin="round" />
        <circle cx="60" cy="10" r="2.6" fill="#E8463A" />
        <circle cx="38" cy="9" r="2" fill="#3B6FE0" />
        <circle cx="82" cy="9" r="2" fill="#3B6FE0" />
      </g>
    );
  }
  if (!item && stage === "duckling") {
    return <path d="M56 20 q4 -10 4 -2 q2 -8 5 0" stroke={Y_DARK} strokeWidth="3" strokeLinecap="round" fill="none" />;
  }
  return null;
}

export default function Duck({ mood = "idle", size = 120, outfit = {}, stage = "duck", className = "", label = "" }) {
  const calm = useApp((s) => s.prefs.calm);
  const scale = stage === "duckling" ? 0.88 : 1;
  const cheer = mood === "cheer" && !calm;
  return (
    <svg className={"duck " + className} width={size} height={size} viewBox="0 0 120 120" role={label ? "img" : undefined} aria-label={label || undefined} aria-hidden={label ? undefined : "true"}>
      <ellipse cx="60" cy="110" rx="30" ry="5" fill="rgba(24,24,27,.12)" />
      <motion.g
        style={{ transformOrigin: "60px 108px" }}
        initial={false}
        animate={calm ? { y: 0 } : cheer ? { y: [0, -14, 0, -9, 0], rotate: [0, -4, 4, -2, 0] } : { y: [0, -2.5, 0] }}
        transition={cheer ? { duration: 0.9, repeat: Infinity, repeatDelay: 0.3 } : { duration: 3.2, repeat: Infinity, ease: "easeInOut" }}
      >
        <g transform={`translate(${60 - 60 * scale} ${108 - 108 * scale}) scale(${scale})`}>
          {/* body */}
          <ellipse cx="60" cy="82" rx="33" ry="27" fill={Y} />
          <ellipse cx="60" cy="88" rx="21" ry="17" fill="#FFE88A" />
          {/* wing: it goes up when the Duck cheers */}
          <motion.path
            d="M28 78 q-12 6 -6 22 q16 2 24 -10 z"
            fill={Y_DARK}
            style={{ transformOrigin: "30px 80px" }}
            animate={cheer ? { rotate: [0, -38, 0] } : { rotate: 0 }}
            transition={cheer ? { duration: 0.45, repeat: Infinity } : { duration: 0.2 }}
          />
          <path d="M92 78 q12 6 6 22 q-16 2 -24 -10 z" fill={Y_DARK} />
          {/* feet */}
          <path d="M44 106 q-6 4 -2 6 h12 q2 -4 -4 -6 z" fill={ORANGE} />
          <path d="M76 106 q6 4 2 6 h-12 q-2 -4 4 -6 z" fill={ORANGE} />
          {outfit.body === "labcoat" && (
            <g>
              <path d="M32 74 q28 26 56 0 l4 30 q-32 14 -64 0 z" fill="#F4F6FA" stroke="#C9D1E0" strokeWidth="1.5" />
              <path d="M60 86 v22" stroke="#C9D1E0" strokeWidth="1.5" />
              <circle cx="56" cy="94" r="1.4" fill="#8A94A8" />
              <circle cx="56" cy="102" r="1.4" fill="#8A94A8" />
            </g>
          )}
          {/* head */}
          <circle cx="60" cy="42" r="26" fill={Y} />
          <circle cx="43" cy="50" r="5" fill="#FF8FA3" opacity=".45" />
          <circle cx="77" cy="50" r="5" fill="#FF8FA3" opacity=".45" />
          <Eyes mood={mood} />
          {/* beak */}
          <path d="M50 49 q10 -5 20 0 q-2 10 -10 10 q-8 0 -10 -10 z" fill={ORANGE} />
          <path d="M53 52 q7 2 14 0" stroke="#D9680B" strokeWidth="1.6" strokeLinecap="round" fill="none" />
          {mood === "cheer" || mood === "happy" ? <path d="M54 55 q6 5 12 0 q-6 1 -12 0 z" fill="#C94A0A" /> : null}
          {mood === "oops" && <path d="M92 30 q4 6 0 9 q-4 -3 0 -9 z" fill="#7CC4F5" />}
          {outfit.neck === "scarf" && (
            <g>
              <path d="M36 66 q24 14 48 0 l2 9 q-26 14 -52 0 z" fill="#E8463A" />
              <path d="M78 72 l8 22 l-9 2 l-5 -20 z" fill="#C7352B" />
              <path d="M36 70 h48" stroke="#FFB4AD" strokeWidth="1.4" strokeDasharray="3 4" opacity=".7" />
            </g>
          )}
          {outfit.eyes === "glasses" && (
            <g fill="rgba(255,255,255,.35)" stroke="#2B2B33" strokeWidth="2.2">
              <circle cx="50" cy="39" r="9" />
              <circle cx="70" cy="39" r="9" />
              <path d="M59 38 h2" fill="none" />
            </g>
          )}
          <Head item={outfit.head} stage={stage} />
          {stage === "scholar" && <path d="M88 20 l2 5 l5 1 l-4 4 l1 5 l-4 -3 l-4 3 l1 -5 l-4 -4 l5 -1 z" fill="#F5B301" />}
        </g>
      </motion.g>
    </svg>
  );
}
