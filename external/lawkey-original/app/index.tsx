import { SafeAreaView } from "react-native-safe-area-context";

import { LawkeyWorkspace } from "../components/lawkey/workspace";

export default function IndexScreen() {
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: "#ffffff" }}>
      <LawkeyWorkspace />
    </SafeAreaView>
  );
}
