import Svg, { Line, Path } from "react-native-svg";

type LawkeyLogoProps = {
  compact?: boolean;
  monochrome?: boolean;
  style?: object;
};

export function LawkeyLogo({ compact = false, monochrome = false, style }: LawkeyLogoProps) {
  const stroke = monochrome ? "#ffffff" : "#111111";
  const size = compact ? 20 : 24;

  return (
    <Svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      stroke={stroke}
      strokeWidth={2}
      fill="none"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={style}
    >
      <Line x1="12" y1="3" x2="12" y2="21" />
      <Line x1="9" y1="21" x2="15" y2="21" />
      <Line x1="3" y1="7" x2="21" y2="7" />
      <Path d="M4 7l-2 9c0 1.1.9 2 2 2s2-.9 2-2l-2-9Z" />
      <Path d="M20 7l-2 9c0 1.1.9 2 2 2s2-.9 2-2l-2-9Z" />
      <Line x1="12" y1="3" x2="12" y2="7" />
    </Svg>
  );
}
