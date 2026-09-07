import { buildConstrainedModeBootstrapScript } from "../lib/performance-mode";

export default function Root({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <head>
        <meta charSet="utf-8" />
        <meta httpEquiv="X-UA-Compatible" content="IE=edge" />
        <meta
          name="viewport"
          content="width=device-width, initial-scale=1, shrink-to-fit=no, viewport-fit=cover"
        />
        <script dangerouslySetInnerHTML={{ __html: buildConstrainedModeBootstrapScript() }} />
        <style
          dangerouslySetInnerHTML={{
            __html: `
html, body {
  min-height: 100%;
  width: 100%;
}

body {
  margin: 0;
  background: #ffffff;
  color: #101010;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Apple SD Gothic Neo", "Noto Sans KR", sans-serif;
  min-height: 100svh;
  min-height: 100dvh;
  overflow: hidden;
}

#root,
#root > div,
#root > div > div {
  width: 100%;
  min-height: 100svh;
  min-height: 100dvh;
}

button,
input,
textarea {
  font: inherit;
}

html[data-lawkey-constrained="1"] *,
html[data-lawkey-constrained="1"] *::before,
html[data-lawkey-constrained="1"] *::after {
  animation-duration: 0.01ms !important;
  animation-iteration-count: 1 !important;
  transition-duration: 0.01ms !important;
  scroll-behavior: auto !important;
  backdrop-filter: none !important;
}
`,
          }}
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
