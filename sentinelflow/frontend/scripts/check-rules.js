import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(__dirname, "..");

const FUNCTION_DECLARATION_REGEX = /^\s*(export\s+default\s+function|export\s+function|function)\b/;
const PROMISE_CHAIN_REGEX = /\.(catch|then)\(/;

const scanDirectory = (dir, violations) => {
  const entries = fs.readdirSync(dir, { withFileTypes: true });

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);

    if (entry.isDirectory()) {
      if (entry.name === "node_modules" || entry.name === ".next") {
        continue;
      }
      scanDirectory(fullPath, violations);
    } else if (entry.isFile()) {
      const isTsFile = entry.name.endsWith(".ts") || entry.name.endsWith(".tsx");
      const isGenerated = entry.name.endsWith(".generated.ts") || entry.name.endsWith(".d.ts");

      if (isTsFile && !isGenerated) {
        checkFile(fullPath, violations);
      }
    }
  }
};

const checkFile = (filePath, violations) => {
  const content = fs.readFileSync(filePath, "utf-8");
  const lines = content.split("\n");

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const lineNumber = i + 1;

    if (FUNCTION_DECLARATION_REGEX.test(line)) {
      violations.push({
        file: path.relative(frontendRoot, filePath),
        line: lineNumber,
        rule: "Arrow functions only (no 'function' keyword)",
        snippet: line.trim(),
      });
    }

    if (PROMISE_CHAIN_REGEX.test(line)) {
      violations.push({
        file: path.relative(frontendRoot, filePath),
        line: lineNumber,
        rule: "No promise chains (use try/catch blocks)",
        snippet: line.trim(),
      });
    }
  }
};

const main = () => {
  const violations = [];
  scanDirectory(frontendRoot, violations);

  if (violations.length > 0) {
    console.error(
      `\n[rules-check] FAILED: Found ${violations.length} AGENTS.md rule violation(s):\n`
    );
    for (const v of violations) {
      console.error(`  - ${v.file}:${v.line} [${v.rule}]: ${v.snippet}`);
    }
    process.exit(1);
  }

  console.log(
    "[rules-check] PASS: 100% compliance with AGENTS.md guardrails (arrow functions & try/catch blocks)."
  );
};

main();
