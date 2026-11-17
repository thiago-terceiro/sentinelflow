import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(__dirname, "..");

const syncStandaloneAssets = (standaloneDir) => {
  const staticSrc = path.join(frontendRoot, ".next", "static");
  const staticDest = path.join(standaloneDir, ".next", "static");
  if (fs.existsSync(staticSrc)) {
    fs.mkdirSync(path.dirname(staticDest), { recursive: true });
    fs.cpSync(staticSrc, staticDest, { recursive: true, force: true });
  }

  const publicSrc = path.join(frontendRoot, "public");
  const publicDest = path.join(standaloneDir, "public");
  if (fs.existsSync(publicSrc)) {
    fs.cpSync(publicSrc, publicDest, { recursive: true, force: true });
  }
};

const main = () => {
  const standaloneDir = path.join(frontendRoot, ".next", "standalone");
  const standaloneServer = path.join(standaloneDir, "server.js");

  let args;
  let cwd;

  try {
    if (fs.existsSync(standaloneServer)) {
      syncStandaloneAssets(standaloneDir);
      args = [standaloneServer];
      cwd = standaloneDir;
    } else {
      const nextBin = path.join(frontendRoot, "node_modules", "next", "dist", "bin", "next");
      args = [nextBin, "start"];
      cwd = frontendRoot;
    }
  } catch (err) {
    console.error("Failed to prepare production server startup:", err);
    process.exit(1);
  }

  const child = spawn(process.execPath, args, {
    cwd,
    env: process.env,
    stdio: "inherit",
  });

  const forwardSignal = (signal) => {
    if (!child.killed) {
      child.kill(signal);
    }
  };

  process.on("SIGINT", () => {
    forwardSignal("SIGINT");
  });
  process.on("SIGTERM", () => {
    forwardSignal("SIGTERM");
  });

  child.on("exit", (code, signal) => {
    if (signal) {
      process.kill(process.pid, signal);
      return;
    }
    process.exit(code ?? 0);
  });
};

main();
