import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams } from "expo-router";

import { DomainWorkspace } from "../../components/domain/domain-workspace";
import { buildDomainPalette, getDomainProduct } from "../../lib/domain-factory";

export default function DomainScreen() {
  const params = useLocalSearchParams<{ domain?: string }>();
  const product = getDomainProduct(typeof params.domain === "string" ? params.domain : "islam");
  const palette = buildDomainPalette(product.key);
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: palette.page }}>
      <DomainWorkspace domain={product.key} />
    </SafeAreaView>
  );
}
