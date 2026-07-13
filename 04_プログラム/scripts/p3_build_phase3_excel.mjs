import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const projectRoot = process.cwd();
const evaluationDir = path.join(
  projectRoot,
  "04_プログラム",
  "output",
  "sumo",
  "regions",
  "08211",
  "evaluation",
);
const outputDir = path.join(projectRoot, "outputs", "p3-impl-8");
const outputPath = path.join(outputDir, "phase3_results_excel.xlsx");

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;
  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    if (char === '"') {
      if (quoted && text[i + 1] === '"') {
        field += '"';
        i += 1;
      } else {
        quoted = !quoted;
      }
    } else if (char === "," && !quoted) {
      row.push(field);
      field = "";
    } else if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && text[i + 1] === "\n") i += 1;
      row.push(field);
      if (row.some((value) => value !== "")) rows.push(row);
      row = [];
      field = "";
    } else {
      field += char;
    }
  }
  if (field !== "" || row.length > 0) {
    row.push(field);
    rows.push(row);
  }
  return rows;
}

function typedRows(rows) {
  return rows.map((row, rowIndex) => row.map((value) => {
    if (rowIndex === 0 || value === "") return value;
    if (/^-?\d+(\.\d+)?$/.test(value)) return Number(value);
    return value;
  }));
}

function styleTable(sheet, rangeAddress, headerAddress, widths = []) {
  sheet.showGridLines = false;
  const tableRange = sheet.getRange(rangeAddress);
  tableRange.format.font = { name: "Aptos", size: 10, color: "#1F2937" };
  tableRange.format.borders = {
    insideHorizontal: { style: "thin", color: "#E5E7EB" },
    bottom: { style: "thin", color: "#CBD5E1" },
  };
  const header = sheet.getRange(headerAddress);
  header.format = {
    fill: "#1F4E78",
    font: { name: "Aptos", size: 10, bold: true, color: "#FFFFFF" },
    wrapText: true,
    verticalAlignment: "center",
  };
  header.format.rowHeight = 32;
  widths.forEach(([column, width]) => {
    sheet.getRange(`${column}:${column}`).format.columnWidth = width;
  });
  sheet.freezePanes.freezeRows(1);
}

async function readCsv(name) {
  const text = await fs.readFile(path.join(evaluationDir, name), "utf8");
  return typedRows(parseCsv(text));
}

const [replicates, signs, s10Replicates, s10Signs, band, s10Band] = await Promise.all([
  readCsv("phase3r_e1_replicate_metrics.csv"),
  readCsv("phase3r_e1_15_combination_signs.csv"),
  readCsv("phase3_s10_replicate_metrics.csv"),
  readCsv("phase3_s10_15_combination_signs.csv"),
  fs.readFile(path.join(evaluationDir, "phase3r_e1_band_summary.json"), "utf8").then(JSON.parse),
  fs.readFile(path.join(evaluationDir, "phase3_s10_band_summary.json"), "utf8").then(JSON.parse),
]);

const workbook = Workbook.create();
const summary = workbook.worksheets.add("概要");
const replicateSheet = workbook.worksheets.add("8run完了率");
const signSheet = workbook.worksheets.add("15組符号表");
const bandSheet = workbook.worksheets.add("raw保守帯");
const s10RunSheet = workbook.worksheets.add("S10_5run");
const s10SignSheet = workbook.worksheets.add("S10_15組符号表");
const sourceSheet = workbook.worksheets.add("出典・注記");

summary.showGridLines = false;
summary.getRange("A1:H1").merge();
summary.getRange("A1").values = [["Phase 3 シミュレーション結果"]];
summary.getRange("A1:H1").format = {
  fill: "#17365D",
  font: { name: "Aptos Display", size: 18, bold: true, color: "#FFFFFF" },
  verticalAlignment: "center",
};
summary.getRange("A1:H1").format.rowHeight = 34;
summary.getRange("A3:B3").values = [["判定", "値"]];
summary.getRange("A4:B11").values = [
  ["主結論", "本モデルの分解能ではA/B差は検出されない"],
  ["8run", band.replicate_count],
  ["15組合せ", band.combination_count],
  ["raw符号", `正${band.raw_sign_counts.positive} / 負${band.raw_sign_counts.negative} / 零${band.raw_sign_counts.zero}`],
  ["保守符号", `正${band.conservative_sign_counts.positive} / 負${band.conservative_sign_counts.negative} / 零${band.conservative_sign_counts.zero}`],
  ["raw点推定 (%pt)", band.raw_point_delta_percentage_points],
  ["raw帯 (%pt)", `${band.raw_delta_min_percentage_points.toFixed(4)} ～ ${band.raw_delta_max_percentage_points.toFixed(4)}`],
  ["保守点推定 (%pt)", band.conservative_point_delta_percentage_points],
];
summary.getRange("D3:E3").values = [["S系10台", "値"]];
summary.getRange("D4:E12").values = [
  ["run数", s10Band.replicate_count],
  ["15組合せ", s10Band.combination_count],
  ["raw符号", `正${s10Band.raw_sign_counts.positive} / 負${s10Band.raw_sign_counts.negative} / 零${s10Band.raw_sign_counts.zero}`],
  ["保守符号", `正${s10Band.conservative_sign_counts.positive} / 負${s10Band.conservative_sign_counts.negative} / 零${s10Band.conservative_sign_counts.zero}`],
  ["raw完了率最小", s10Band.raw_completion_rate_min_percent / 100],
  ["raw完了率最大", s10Band.raw_completion_rate_max_percent / 100],
  ["保守完了率最小", s10Band.conservative_completion_rate_min_percent / 100],
  ["保守完了率最大", s10Band.conservative_completion_rate_max_percent / 100],
  ["決定109", s10Band.decision109_stop_s_series ? "S系終了・追加run禁止" : "未確定"],
];
for (const header of ["A3:B3", "D3:E3"]) {
  summary.getRange(header).format = { fill: "#4472C4", font: { bold: true, color: "#FFFFFF" } };
}
summary.getRange("A4:A11").format.font = { bold: true, color: "#374151" };
summary.getRange("D4:D12").format.font = { bold: true, color: "#374151" };
summary.getRange("B9").format.numberFormat = "0.0000";
summary.getRange("B11").format.numberFormat = "0.0000";
summary.getRange("E8:E11").format.numberFormat = "0.00%";
summary.getRange("A13:H15").merge();
summary.getRange("A13:H15").values = [["注記：完了率の方向主張は禁止。raw/保守の15組合せ符号はいずれも非一貫で、帯はゼロをまたぐ。S10#4の100%超は削減54台固定の感度設計に伴う二重計上バイアスを含むためraw値を保持する。"]];
summary.getRange("A13:H15").format = { fill: "#FFF2CC", font: { color: "#7F6000" }, wrapText: true, verticalAlignment: "top" };
summary.getRange("A:A").format.columnWidth = 23;
summary.getRange("B:B").format.columnWidth = 44;
summary.getRange("C:C").format.columnWidth = 4;
summary.getRange("D:D").format.columnWidth = 22;
summary.getRange("E:E").format.columnWidth = 28;
summary.freezePanes.freezeRows(1);

replicateSheet.getRangeByIndexes(0, 0, replicates.length, replicates[0].length).values = replicates;
styleTable(replicateSheet, `A1:N${replicates.length}`, "A1:N1", [["A", 10], ["B", 10], ["C", 10], ["D", 28], ["N", 42]]);
replicateSheet.getRange(`L2:M${replicates.length}`).format.numberFormat = "0.0000%";

signSheet.getRangeByIndexes(0, 0, signs.length, signs[0].length).values = signs;
styleTable(signSheet, `A1:J${signs.length}`, "A1:J1", [["A", 10], ["B", 10], ["C", 10], ["D", 10], ["E", 17], ["F", 23], ["G", 13], ["H", 23], ["I", 29], ["J", 18]]);
signSheet.getRange(`E2:E${signs.length}`).format.numberFormat = "0.000000";
signSheet.getRange(`F2:F${signs.length}`).format.numberFormat = "0.0000";
signSheet.getRange(`H2:H${signs.length}`).format.numberFormat = "0.000000";
signSheet.getRange(`I2:I${signs.length}`).format.numberFormat = "0.0000";

bandSheet.showGridLines = false;
bandSheet.getRange("A1:G1").values = [["系列", "A中央値", "B中央値", "点推定Δ率", "点推定Δ (%pt)", "Δ最小 (%pt)", "Δ最大 (%pt)"]];
bandSheet.getRange("A2:G3").values = [
  ["raw", band.a_completion_rate_median, band.b_raw_completion_rate_median, band.raw_point_delta_rate, band.raw_point_delta_percentage_points, band.raw_delta_min_percentage_points, band.raw_delta_max_percentage_points],
  ["保守", band.a_completion_rate_median, band.b_conservative_completion_rate_median, band.conservative_point_delta_rate, band.conservative_point_delta_percentage_points, band.conservative_delta_min_percentage_points, band.conservative_delta_max_percentage_points],
];
bandSheet.getRange("A6:D6").values = [["系列", "最小", "中央値", "最大"]];
bandSheet.getRange("A7:D9").values = [
  ["A", band.a_completion_rate_min, band.a_completion_rate_median, band.a_completion_rate_max],
  ["B raw", band.b_raw_completion_rate_min, band.b_raw_completion_rate_median, band.b_raw_completion_rate_max],
  ["B 保守", band.b_conservative_completion_rate_min, band.b_conservative_completion_rate_median, band.b_conservative_completion_rate_max],
];
styleTable(bandSheet, "A1:G3", "A1:G1", [["A", 15], ["B", 14], ["C", 14], ["D", 17], ["E", 19], ["F", 17], ["G", 17]]);
bandSheet.getRange("A6:D6").format = { fill: "#4472C4", font: { bold: true, color: "#FFFFFF" } };
bandSheet.getRange("B2:D3").format.numberFormat = "0.0000%";
bandSheet.getRange("E2:G3").format.numberFormat = "0.0000";
bandSheet.getRange("B7:D9").format.numberFormat = "0.0000%";

s10RunSheet.getRangeByIndexes(0, 0, s10Replicates.length, s10Replicates[0].length).values = s10Replicates;
styleTable(s10RunSheet, `A1:M${s10Replicates.length}`, "A1:M1", [["A", 12], ["B", 10], ["C", 30], ["D", 12], ["M", 44]]);
s10RunSheet.getRange(`I2:J${s10Replicates.length}`).format.numberFormat = "0.0000%";
s10RunSheet.getRange(`K2:L${s10Replicates.length}`).format.numberFormat = "0.0000";

s10SignSheet.getRangeByIndexes(0, 0, s10Signs.length, s10Signs[0].length).values = s10Signs;
styleTable(s10SignSheet, `A1:I${s10Signs.length}`, "A1:I1", [["A", 12], ["B", 10], ["C", 10], ["D", 18], ["E", 25], ["F", 14], ["G", 24], ["H", 30], ["I", 18]]);
s10SignSheet.getRange(`D2:D${s10Signs.length}`).format.numberFormat = "0.000000";
s10SignSheet.getRange(`E2:E${s10Signs.length}`).format.numberFormat = "0.0000";
s10SignSheet.getRange(`G2:G${s10Signs.length}`).format.numberFormat = "0.000000";
s10SignSheet.getRange(`H2:H${s10Signs.length}`).format.numberFormat = "0.0000";

sourceSheet.showGridLines = false;
sourceSheet.getRange("A1:C1").values = [["区分", "ファイル", "注記"]];
sourceSheet.getRange("A2:C7").values = [
  ["8run", "phase3r_e1_replicate_metrics.csv", "A 3run＋B 5run。完了率は率（0～1）"],
  ["15組符号", "phase3r_e1_15_combination_signs.csv", "raw/保守。delta_rateとdelta_percentage_pointsを分離"],
  ["帯", "phase3r_e1_band_summary.json", "raw/保守の中央値・min–max・点推定"],
  ["S10 run", "phase3_s10_replicate_metrics.csv", "バス10台×5seed。追加run禁止"],
  ["S10符号", "phase3_s10_15_combination_signs.csv", "raw/保守。delta_rateとdelta_percentage_pointsを分離"],
  ["S10帯", "phase3_s10_band_summary.json", "raw/保守とも符号非一貫、決定109でS系終了"],
];
styleTable(sourceSheet, "A1:C7", "A1:C1", [["A", 15], ["B", 45], ["C", 60]]);
sourceSheet.getRange("A9:C11").merge();
sourceSheet.getRange("A9:C11").values = [["再現条件：既存成果物のみを集約し、新規SUMO run・追加seedは実施していない。Type3/4分母は3,231.5人、救出走行1台当たり2.3人、保守バス上限は124.2人。"]];
sourceSheet.getRange("A9:C11").format = { fill: "#E2F0D9", font: { color: "#375623" }, wrapText: true };

await fs.mkdir(outputDir, { recursive: true });
for (const sheetName of ["概要", "8run完了率", "15組符号表", "raw保守帯", "S10_5run", "S10_15組符号表", "出典・注記"]) {
  const preview = await workbook.render({ sheetName, autoCrop: "all", scale: 1, format: "png" });
  await fs.writeFile(path.join(outputDir, `preview_${sheetName}.png`), new Uint8Array(await preview.arrayBuffer()));
}

const keyCheck = await workbook.inspect({
  kind: "table",
  range: "概要!A1:H15",
  include: "values,formulas",
  tableMaxRows: 15,
  tableMaxCols: 8,
});
const errorCheck = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  summary: "final formula error scan",
});
console.log(keyCheck.ndjson);
console.log(errorCheck.ndjson);

const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(JSON.stringify({ outputPath, sheets: 7 }));
