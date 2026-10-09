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

export async function initNative(onBack) {
  if (!isNative) return;
  document.documentElement.classList.add("native");
  syncStatusBar();
  new MutationObserver(syncStatusBar).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  try {
    const { App } = await import("@capacitor/app");
    // The back button of Android closes a drawer first. Then it leaves the app.
    App.addListener("backButton", () => {
      if (!onBack()) App.exitApp();
    });
    const { SplashScreen } = await import("@capacitor/splash-screen");
    await SplashScreen.hide();
  } catch {}
}
