// The code for the phone app (Capacitor). In a normal browser, all of this does nothing.
import { Capacitor } from "@capacitor/core";

export const isNative = Capacitor.isNativePlatform();

// A small tap feedback on a phone. It is safe to call anywhere.
export async function tap() {
  if (!isNative) return;
  try {
    const { Haptics, ImpactStyle } = await import("@capacitor/haptics");
    await Haptics.impact({ style: ImpactStyle.Light });
  } catch {}
}

// The color of the status bar follows the theme of the app.
export async function syncStatusBar() {
  if (!isNative) return;
  try {
    const { StatusBar, Style } = await import("@capacitor/status-bar");
    const dark = document.documentElement.getAttribute("data-theme") === "dark";
    await StatusBar.setStyle({ style: dark ? Style.Dark : Style.Light });
    if (Capacitor.getPlatform() === "android") await StatusBar.setBackgroundColor({ color: dark ? "#0B0B0E" : "#F6F6F7" });
  } catch {}
}

// Starts the phone functions. It gives back a cleanup function, so a second start (React strict mode) never leaves a double listener.
export function initNative(onBack) {
  if (!isNative) return () => {};
  document.documentElement.classList.add("native");
  syncStatusBar();
  const observer = new MutationObserver(syncStatusBar);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  let stopped = false;
  let handle = null;
  (async () => {
    try {
      const { App } = await import("@capacitor/app");
      // The back button of Android closes a drawer first. Then it leaves the app.
      const h = await App.addListener("backButton", () => {
        if (!onBack()) App.exitApp();
      });
      if (stopped) h.remove();
      else handle = h;
      const { SplashScreen } = await import("@capacitor/splash-screen");
      await SplashScreen.hide();
    } catch {}
  })();
  return () => {
    stopped = true;
    observer.disconnect();
    handle?.remove();
  };
}

// A stronger feedback for the game: "light" (a small tap), "success" (a win), "warn" (a wrong answer, soft). Safe to call anywhere.
export async function buzz(kind = "light") {
  if (!isNative) return;
  try {
    const { Haptics, ImpactStyle, NotificationType } = await import("@capacitor/haptics");
    if (kind === "success") await Haptics.notification({ type: NotificationType.Success });
    else if (kind === "warn") await Haptics.notification({ type: NotificationType.Warning });
    else await Haptics.impact({ style: ImpactStyle.Light });
  } catch {}
}
