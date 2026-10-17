import tseslint from "typescript-eslint";
import sonarjs from "eslint-plugin-sonarjs";
import prettierConfig from "eslint-config-prettier";

export default tseslint.config(
  {
    ignores: [
      ".next/**",
      "node_modules/**",
      "playwright-report/**",
      "test-results/**",
      "lib/types/api.generated.ts",
      "scripts/**",
    ],
  },
  ...tseslint.configs.recommended,
  sonarjs.configs.recommended,
  prettierConfig,
  {
    files: ["**/*.ts", "**/*.tsx"],
    rules: {
      // Rule 1: Always use arrow function for TS stuff (AGENTS.md)
      "func-style": ["error", "expression"],
      "prefer-arrow-callback": ["error", { allowNamedFunctions: false }],

      // Rule 2: Never use chain for try catch, always the full block (AGENTS.md)
      "no-restricted-syntax": [
        "error",
        {
          selector: "CallExpression[callee.property.name='catch']",
          message:
            "Do not use .catch() promise chains. Use full try/catch blocks as required by AGENTS.md.",
        },
        {
          selector: "CallExpression[callee.property.name='then']",
          message:
            "Do not use .then() promise chains. Use async/await with try/catch blocks as required by AGENTS.md.",
        },
      ],

      // OWASP Top 10 & CWE Security Rules (A02 Cryptographic Failures, A03 Injection, CWE-95, CWE-798, CWE-1333)
      "no-eval": "error",
      "no-implied-eval": "error",
      "no-new-func": "error",
      "no-script-url": "error",
      "sonarjs/no-hardcoded-passwords": "error",
      "sonarjs/slow-regex": "error",

      // Code quality & complexity guardrails
      "@typescript-eslint/no-explicit-any": "warn",
      "@typescript-eslint/no-unused-vars": [
        "warn",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      "sonarjs/cognitive-complexity": ["warn", 30],
      "sonarjs/no-nested-conditional": "warn",
      "sonarjs/no-duplicate-string": "off",
    },
  },
  {
    files: ["lib/testAuth.ts", "e2e/**", "**/*.test.ts"],
    rules: {
      "sonarjs/no-hardcoded-passwords": "off",
    },
  }
);
