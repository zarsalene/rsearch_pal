import { AnimatePresence, motion, useDragControls } from "motion/react";
import { Icon } from "./icons.jsx";
import ThemeToggle from "./ThemeToggle.jsx";

// The sheet "More" of the phone. The bottom bar has room for four tabs. The other pages are here, with the choice of the theme.
// You close it with a tap outside, with the grip (pull it down) or with the back button of Android.
export default function MoreSheet({ open, tabs, current, onPick, onClose }) {
  const controls = useDragControls();
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.button className="sheet-scrim" aria-label="Close" tabIndex={-1} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} />
          <motion.div
            className="more-sheet"
            role="dialog"
            aria-label="More"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", stiffness: 380, damping: 36 }}
            drag="y"
            dragControls={controls}
            dragListener={false}
            dragConstraints={{ top: 0, bottom: 0 }}
            dragElastic={{ top: 0, bottom: 0.7 }}
            onDragEnd={(_, info) => (info.offset.y > 90 || info.velocity.y > 500) && onClose()}
          >
            <div className="sheet-grip on" onPointerDown={(e) => controls.start(e)} aria-hidden="true" />
            <ul className="more-list">
              {tabs.map(([k, label, icon]) => (
                <li key={k}>
                  <button className={"more-row" + (current === k ? " on" : "")} onClick={() => onPick(k)}>
                    <span className="more-ico">
                      <Icon name={icon} size={20} />
                    </span>
                    <span className="more-name">{label}</span>
                    <Icon name="arrow" size={16} />
                  </button>
                </li>
              ))}
            </ul>
            <div className="more-theme">
              <span className="more-name">Appearance</span>
              <ThemeToggle />
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
