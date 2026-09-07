import { useEffect, useState, type ReactNode } from "react";
import { Platform, Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { theme } from "../constants/theme";
import { isPresentationAuthValid, loadAuthState, persistAuthState } from "../lib/auth-gate";
import { LawkeyLogo } from "./lawkey/lawkey-logo";

type LoginGateProps = {
  children: ReactNode;
};

const webTextInputFocusReset =
  Platform.OS === "web"
    ? ({
        outlineColor: "transparent",
        outlineStyle: "none",
        outlineWidth: 0,
      } as any)
    : null;

export function LoginGate({ children }: LoginGateProps) {
  const [hydrated, setHydrated] = useState(false);
  const [authed, setAuthed] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    setAuthed(loadAuthState());
    setHydrated(true);
  }, []);

  if (!hydrated) {
    return null;
  }

  if (authed) {
    return <>{children}</>;
  }

  const submit = () => {
    if (!isPresentationAuthValid(username, password)) {
      setError("아이디 또는 비밀번호가 올바르지 않습니다.");
      return;
    }
    persistAuthState(true);
    setError("");
    setAuthed(true);
  };

  return (
    <View style={styles.shell}>
      <View style={styles.card}>
        <View style={styles.brandRow}>
          <LawkeyLogo />
          <Text style={styles.brand}>Lawkey AI</Text>
        </View>
        <Text style={styles.title}>로그인</Text>
        <Text style={styles.subtitle}>관리자 계정으로 로그인해 주세요.</Text>

        <Text style={styles.label}>아이디</Text>
        <TextInput
          accessibilityLabel="아이디"
          autoCapitalize="none"
          autoCorrect={false}
          placeholder="admin"
          placeholderTextColor="#9ca3af"
          style={[styles.input, webTextInputFocusReset as any]}
          value={username}
          onChangeText={(value) => {
            setUsername(value);
            if (error) setError("");
          }}
          onSubmitEditing={submit}
        />

        <Text style={styles.label}>비밀번호</Text>
        <TextInput
          accessibilityLabel="비밀번호"
          autoCapitalize="none"
          autoCorrect={false}
          placeholder="비밀번호"
          placeholderTextColor="#9ca3af"
          secureTextEntry
          style={[styles.input, webTextInputFocusReset as any]}
          value={password}
          onChangeText={(value) => {
            setPassword(value);
            if (error) setError("");
          }}
          onSubmitEditing={submit}
        />

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <Pressable
          accessibilityRole="button"
          onPress={submit}
          style={({ pressed }) => [styles.submit, pressed ? styles.pressed : null]}
        >
          <Text style={styles.submitText}>로그인</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  shell: {
    flex: 1,
    backgroundColor: "#f5f6f8",
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
  },
  card: {
    width: "100%",
    maxWidth: 380,
    backgroundColor: "#ffffff",
    borderRadius: 14,
    borderWidth: 1,
    borderColor: theme.colors.line,
    paddingHorizontal: 28,
    paddingVertical: 32,
    gap: 12,
    shadowColor: "#000000",
    shadowOpacity: 0.05,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: 8 },
  },
  brandRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginBottom: 8,
  },
  brand: {
    color: theme.colors.text,
    fontFamily: theme.fonts.serif,
    fontSize: 20,
    fontWeight: "800",
    letterSpacing: 0.4,
  },
  title: {
    color: theme.colors.text,
    fontSize: 22,
    fontWeight: "700",
    fontFamily: theme.fonts.serif,
  },
  subtitle: {
    color: theme.colors.subtle,
    fontSize: 13,
    lineHeight: 20,
    marginBottom: 8,
  },
  label: {
    color: theme.colors.muted,
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 0.5,
    textTransform: "uppercase",
    marginTop: 4,
  },
  input: {
    borderWidth: 1,
    borderColor: theme.colors.line,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
    color: theme.colors.text,
    backgroundColor: "#ffffff",
  },
  submit: {
    marginTop: 12,
    backgroundColor: "#0a0a0a",
    borderRadius: 8,
    paddingVertical: 12,
    alignItems: "center",
  },
  submitText: {
    color: "#ffffff",
    fontSize: 15,
    fontWeight: "700",
  },
  pressed: {
    opacity: 0.85,
  },
  error: {
    color: "#b53737",
    fontSize: 13,
    marginTop: 4,
  },
});
