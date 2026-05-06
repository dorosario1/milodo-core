import { readFileSync, writeFileSync } from "fs";

function average(values) {
  if (values.length === 0) return 0;
  return values.reduce((total, value) => total + value, 0) / values.length;
}

function round(value) {
  return Number(value.toFixed(3));
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function variance(values) {
  if (values.length === 0) return 0;

  const mean = average(values);
  return average(values.map((value) => (value - mean) ** 2));
}

function parseRuns(filePath) {
  const content = readFileSync(filePath, "utf8").trim();
  if (!content) return [];

  const runs = [];

  for (const line of content.split(/\r?\n/)) {
    const trimmedLine = line.trim();
    if (!trimmedLine || !trimmedLine.startsWith("{")) continue;

    try {
      const parsed = JSON.parse(trimmedLine);
      if (parsed && typeof parsed.runId === "string" && Array.isArray(parsed.data)) {
        runs.push(parsed);
      }
    } catch {
      // Ignore non-JSONL fragments from older pretty-printed exports.
    }
  }

  if (runs.length > 0) return runs;

  try {
    const legacyData = JSON.parse(content);
    if (Array.isArray(legacyData)) {
      return [{ runId: "legacy", data: legacyData }];
    }
  } catch {
    // Keep the parser strict enough to fail clearly below.
  }

  throw new Error(`No valid metrics runs found in ${filePath}`);
}

function stabilityScore(populationVariance, fitnessVariance) {
  const populationPenalty = clamp(populationVariance / 16, 0, 0.6);
  const fitnessPenalty = clamp(fitnessVariance / 0.12, 0, 0.4);

  return round(clamp(1 - populationPenalty - fitnessPenalty, 0, 1));
}

function recommendAction(avgPopulation, efficiencyTrend, score) {
  if (score < 0.55) return "augmenter pression";
  if (efficiencyTrend === "-") return "augmenter mutation";
  if (avgPopulation < 4) return "reduire cout reproduction";
  if (avgPopulation > 10) return "augmenter pression";
  return "maintenir parametres";
}

function analyzeRun(run) {
  const data = run.data.filter((metric) => metric && typeof metric === "object");
  const populations = data
    .map((metric) => metric.population)
    .filter((population) => typeof population === "number");
  const fitnessValues = data
    .map((metric) => metric.bestFitness)
    .filter((fitness) => typeof fitness === "number");
  const efficiencyValues = data
    .map((metric) => metric.avgEfficiency)
    .filter((efficiency) => typeof efficiency === "number");

  const avgPopulation = round(average(populations));
  const maxFitness = round(Math.max(0, ...fitnessValues));
  const startEfficiency = efficiencyValues[0] ?? 0;
  const endEfficiency = efficiencyValues[efficiencyValues.length - 1] ?? 0;
  const efficiencyTrend = endEfficiency >= startEfficiency ? "+" : "-";
  const lowPopulationCount = populations.filter((population) => population < 3).length;
  const convergenceFrequent =
    populations.length > 0 && lowPopulationCount / populations.length > 0.2;
  const populationVariance = round(variance(populations));
  const fitnessVariance = round(variance(fitnessValues));
  const score = stabilityScore(populationVariance, fitnessVariance);

  return {
    runId: run.runId,
    avgPopulation,
    maxFitness,
    efficiencyTrend,
    populationVariance,
    fitnessVariance,
    stabilityScore: score,
    stable: !convergenceFrequent,
    recommendation: recommendAction(avgPopulation, efficiencyTrend, score)
  };
}

function buildConfig(results) {
  const recommendations = new Set(results.map((result) => result.recommendation));

  return {
    mutationBoost: recommendations.has("augmenter mutation"),
    reproductionCostFactor: recommendations.has("reduire cout reproduction") ? 0.8 : 1,
    pressureFactor: recommendations.has("augmenter pression") ? 1.2 : 1
  };
}

const runs = parseRuns("metrics.json");
const results = runs.map(analyzeRun);

for (const result of results) {
  console.log(`RUN ${result.runId}`);
  console.log(`avgPopulation: ${result.avgPopulation}`);
  console.log(`maxFitness: ${result.maxFitness}`);
  console.log(`efficiencyTrend: ${result.efficiencyTrend}`);
  console.log(`populationVariance: ${result.populationVariance}`);
  console.log(`fitnessVariance: ${result.fitnessVariance}`);
  console.log(`stabilityScore: ${result.stabilityScore}`);
  console.log(`stable: ${result.stable}`);
  console.log(`recommendation: "${result.recommendation}"`);
  console.log("");
}

const config = buildConfig(results);
writeFileSync("config.json", JSON.stringify(config, null, 2));
console.log("config.json written");
