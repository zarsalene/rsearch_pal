import { useSyncExternalStore } from "react";

export const PHONE = "(max-width: 820px)";
export const isPhone = () => window.matchMedia(PHONE).matches;

// True on a phone, and it changes when the window changes (a phone turned sideways, a window resized).
export function usePhone() {
  return useSyncExternalStore(
    (cb) => {
      const mq = window.matchMedia(PHONE);
      mq.addEventListener("change", cb);
      return () => mq.removeEventListener("change", cb);
    },
    isPhone,
    () => false,
  );
}
