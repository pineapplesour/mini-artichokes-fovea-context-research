import { Pressable, StyleSheet, Text } from "react-native";

import { theme } from "../constants/theme";

type LoginButtonProps = {
  onPress: () => void;
  onDoubleClick?: () => void;
};

// Top-right "로그인" button. A normal click opens login; a fast double-click is
// still reserved for the hidden demo path.
export function LoginButton({ onPress, onDoubleClick }: LoginButtonProps) {
  const doubleClickProps = onDoubleClick ? ({ onDoubleClick } as Record<string, unknown>) : {};
  return (
    <Pressable
      {...doubleClickProps}
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [styles.button, pressed ? styles.buttonPressed : null]}
    >
      <Text style={styles.buttonText}>로그인</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: theme.colors.line,
    backgroundColor: "#ffffff",
  },
  buttonText: {
    color: theme.colors.text,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 0.4,
  },
  buttonPressed: {
    opacity: 0.85,
  },
});
