#!/usr/bin/env node

import { readFile, writeFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";

async function loadKordoc() {
  try {
    return await import("kordoc");
  } catch (_error) {
    const fallbackUrl = pathToFileURL("/opt/lawkey/node_modules/kordoc/dist/index.js").href;
    return await import(fallbackUrl);
  }
}

function parseArgs(argv) {
  const args = { inputPath: "", outputPath: "" };
  for (let index = 2; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === "--in") {
      args.inputPath = argv[index + 1] ?? "";
      index += 1;
    } else if (token === "--out") {
      args.outputPath = argv[index + 1] ?? "";
      index += 1;
    }
  }
  if (!args.inputPath || !args.outputPath) {
    throw new Error("Usage: markdown_to_hwpx.mjs --in input.md --out output.hwpx");
  }
  return args;
}

async function main() {
  const { inputPath, outputPath } = parseArgs(process.argv);
  const markdown = await readFile(inputPath, "utf8");
  const kordoc = await loadKordoc();
  const buffer = await kordoc.markdownToHwpx(markdown);
  await writeFile(outputPath, Buffer.from(buffer));
}

main().catch((error) => {
  console.error(error instanceof Error ? error.stack || error.message : String(error));
  process.exitCode = 1;
});
