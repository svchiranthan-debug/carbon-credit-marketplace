// Regenerates CarbonCreditRegistry.json (ABI + bytecode) from CarbonCreditRegistry.sol.
// The committed artifact was verified to match solc 0.8.20 with the optimizer disabled.
//
//   cd backend/contracts
//   npm install --no-save solc@0.8.20
//   node compile_contract.js
const fs = require("fs");
const path = require("path");
const solc = require("solc");

const dir = __dirname;
const source = fs.readFileSync(path.join(dir, "CarbonCreditRegistry.sol"), "utf8");
const input = {
  language: "Solidity",
  sources: { "CarbonCreditRegistry.sol": { content: source } },
  settings: { optimizer: { enabled: false }, outputSelection: { "*": { "*": ["abi", "evm.bytecode.object"] } } },
};
const output = JSON.parse(solc.compile(JSON.stringify(input)));
const errors = (output.errors || []).filter((e) => e.severity === "error");
if (errors.length) {
  errors.forEach((e) => console.error(e.formattedMessage));
  process.exit(1);
}
const c = output.contracts["CarbonCreditRegistry.sol"].CarbonCreditRegistry;
fs.writeFileSync(
  path.join(dir, "CarbonCreditRegistry.json"),
  JSON.stringify({ contractName: "CarbonCreditRegistry", abi: c.abi, bytecode: "0x" + c.evm.bytecode.object }, null, 2)
);
console.log(`Compiled with solc ${solc.version()} -> CarbonCreditRegistry.json`);
