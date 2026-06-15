import { Command } from "commander";
import { config } from "dotenv";
import { spawn } from "child_process";
import path from "path";

config();

const program = new Command();

const pythonBackend = path.resolve(__dirname, "..", "src", "main.py");

function runPython(args: string[]): Promise<void> {
  return new Promise((resolve, reject) => {
    const proc = spawn("python", ["-m", "src.main", ...args], {
      cwd: path.resolve(__dirname, ".."),
      stdio: "inherit",
    });
    proc.on("close", (code) => {
      if (code === 0) resolve();
      else reject(new Error(`Python backend exited with code ${code}`));
    });
  });
}

program
  .name("acquisition-engine")
  .description("TypeScript CLI wrapper around the Python acquisition engine")
  .version("0.1.0");

program
  .command("run")
  .description("Run the full pipeline")
  .requiredOption("--region <region>", "Target region (e.g., Cyberjaya)")
  .requiredOption("--keywords <keywords...>", "Search keywords")
  .action(async (options) => {
    await runPython(["run", "--region", options.region, "--keywords", ...options.keywords]);
  });

program
  .command("scrape")
  .description("Run only the scraper")
  .requiredOption("--region <region>", "Target region")
  .requiredOption("--keywords <keywords...>", "Search keywords")
  .action(async (options) => {
    await runPython(["scrape", "--region", options.region, "--keywords", ...options.keywords]);
  });

program
  .command("audit")
  .description("Run audit on existing JSON")
  .requiredOption("--input <input>", "Path to raw_businesses.json")
  .action(async (options) => {
    await runPython(["audit", "--input", options.input]);
  });

program.parse();
