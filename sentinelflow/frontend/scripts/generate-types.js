import { execSync } from "node:child_process";
import { existsSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const frontendDir = resolve(__dirname, "..");
const backendDir = resolve(frontendDir, "../backend");
const schemaFile = resolve(backendDir, "openapi.json");
const outputFile = resolve(frontendDir, "lib/types/api.generated.ts");

const exportBackendOpenApi = () => {
    console.log("[codegen] 1/2 Exporting OpenAPI schema from FastAPI backend...");
    const pythonCommand = `uv run python -c "import json; from app.main import app; open(r'${schemaFile}', 'w', encoding='utf-8').write(json.dumps(app.openapi(), indent=2))"`;
    try {
        execSync(pythonCommand, {
            cwd: backendDir,
            stdio: "inherit",
        });
    } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        console.error(`[codegen] Failed to extract OpenAPI schema from backend: ${message}`);
        process.exit(1);
    }
};

const generateTypeScriptContracts = () => {
    console.log("[codegen] 2/2 Generating TypeScript contracts with openapi-typescript...");
    mkdirSync(dirname(outputFile), { recursive: true });
    const npxCommand = `npx --yes openapi-typescript "${schemaFile}" -o "${outputFile}"`;
    try {
        execSync(npxCommand, {
            cwd: frontendDir,
            stdio: "inherit",
        });
        console.log(`[codegen] Successfully generated contracts at: ${outputFile}`);
    } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        console.error(`[codegen] Failed to generate TypeScript types: ${message}`);
        process.exit(1);
    }
};

const run = () => {
    exportBackendOpenApi();
    generateTypeScriptContracts();
};

run();
