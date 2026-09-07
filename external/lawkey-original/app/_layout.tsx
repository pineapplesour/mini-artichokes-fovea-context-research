import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useEffect } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";


function injectScrollbarHide() {
  if (typeof document === "undefined") return;
  if (document.getElementById("lawkey-scrollbar-hide")) return;
  const style = document.createElement("style");
  style.id = "lawkey-scrollbar-hide";
  style.textContent = `#lawkey-history-scroll::-webkit-scrollbar { display: none; width: 0; height: 0; }`;
  document.head.appendChild(style);
}

export default function RootLayout() {
  useEffect(() => {
    injectScrollbarHide();
  }, []);
  return (
    <SafeAreaProvider>
      <StatusBar style="dark" />
      <Stack
        screenOptions={{
          headerShown: false,
          animation: "fade",
          contentStyle: {
            backgroundColor: "#ffffff",
          },
        }}
      />
    </SafeAreaProvider>
  );
}
