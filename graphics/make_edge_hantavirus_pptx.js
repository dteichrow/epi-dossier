const pptxgen = require("pptxgenjs");
const path = require("path");

const outDir = __dirname;
const imgPath = path.join(outDir, "sin_nombre_hantavirus_cdc_phil_1136.jpg");

const pptx = new pptxgen();
pptx.author = "The Edge of Epidemiology";
pptx.subject = "Editable infectious disease situation brief";
pptx.title = "MV Hondius Hantavirus Situation Brief";
pptx.company = "The Edge of Epidemiology";
pptx.lang = "en-US";
pptx.defineLayout({ name: "EDGE_POSTER", width: 8.5, height: 12.0 });
pptx.layout = "EDGE_POSTER";
pptx.theme = {
  headFontFace: "Arial",
  bodyFontFace: "Arial",
  lang: "en-US",
};
pptx.margin = 0;

const C = {
  paper: "F6F0E8",
  ink: "142126",
  teal: "155D66",
  teal2: "2A7F8E",
  rust: "B84A3E",
  amber: "D69A3A",
  plum: "5A4E63",
  slate: "46545B",
  mist: "D8E5E3",
  white: "FFFFFF",
};

const slide = pptx.addSlide();
slide.background = { color: C.paper };

function addText(text, x, y, w, h, opts = {}) {
  slide.addText(text, {
    x, y, w, h,
    margin: opts.margin ?? 0.02,
    fontFace: opts.fontFace ?? "Arial",
    fontSize: opts.fontSize ?? 12,
    bold: opts.bold ?? false,
    italic: opts.italic ?? false,
    color: opts.color ?? C.ink,
    align: opts.align ?? "left",
    valign: opts.valign ?? "top",
    breakLine: false,
    fit: opts.fit ?? "shrink",
  });
}

function rect(x, y, w, h, color, opts = {}) {
  slide.addShape(pptx.ShapeType.rect, {
    x, y, w, h,
    fill: { color, transparency: opts.transparency ?? 0 },
    line: opts.line ?? { color, transparency: 100 },
    radius: opts.radius ?? 0,
  });
}

function line(x1, y1, x2, y2, color = C.ink, width = 1) {
  slide.addShape(pptx.ShapeType.line, {
    x: x1, y: y1, w: x2 - x1, h: y2 - y1,
    line: { color, width },
  });
}

function metric(y, value, label1, label2, color) {
  rect(0.24, y, 1.42, 1.42, color);
  addText(value, 0.24, y + 0.2, 1.42, 0.5, { fontSize: 35, bold: true, color: C.white, align: "center" });
  addText(label1, 0.32, y + 0.82, 1.26, 0.28, { fontSize: 14.5, bold: true, color: C.white, align: "center" });
  addText(label2, 0.32, y + 1.1, 1.26, 0.26, { fontSize: 13, bold: true, color: C.white, align: "center" });
}

function bullet(text, x, y, w, opts = {}) {
  addText("• " + text, x, y, w, 0.24, { fontSize: opts.fontSize ?? 10.7, color: opts.color ?? C.ink, bold: opts.bold ?? false });
}

// Header
rect(0, 0, 8.5, 1.25, C.teal);
rect(0.24, 0.22, 1.42, 0.78, C.paper);
addText("PATHOGEN\nDISPATCH", 0.39, 0.35, 1.12, 0.5, { fontSize: 13, bold: true, color: C.teal, align: "center" });
rect(0.38, 0.24, 0.08, 0.08, C.rust);
rect(0.49, 0.24, 0.08, 0.08, C.amber);
rect(0.60, 0.24, 0.08, 0.08, C.teal2);

addText("HANTAVIRUS OUTBREAK", 2.0, 0.21, 4.55, 0.36, { fontSize: 23, bold: true, color: C.white, align: "center" });
addText("SITUATION BRIEF #1", 2.0, 0.55, 4.55, 0.32, { fontSize: 21, bold: true, color: "DDEEEF", align: "center" });
addText("4 May 2026", 2.0, 0.88, 4.55, 0.25, { fontSize: 16, bold: true, color: "F8DFAE", align: "center" });
addText("The Edge\nof Epi", 6.95, 0.3, 1.22, 0.55, { fontSize: 14, bold: true, color: C.white, align: "center" });

// Left metric rail
metric(1.55, "1", "CONFIRMED", "CASE", C.teal);
metric(3.15, "5", "SUSPECTED", "CASES", C.teal2);
metric(4.75, "3", "DEATHS", "REPORTED", C.rust);
metric(6.35, "1", "IN ICU", "S. AFRICA", C.plum);

// Highlights
addText("HIGHLIGHTS:", 1.95, 1.55, 1.4, 0.22, { fontSize: 12.5, bold: true, color: C.ink });
line(1.95, 1.79, 2.82, 1.79, C.ink, 1);
bullet("WHO reports one lab-confirmed hantavirus case and five suspected cases.", 1.95, 1.86, 6.05);
bullet("Of six affected people, three have died; one person is in intensive care in South Africa.", 1.95, 2.12, 6.05);
bullet("Route signal: MV Hondius travelled from Ushuaia, Argentina, to Cabo Verde.", 1.95, 2.38, 6.05);
bullet("ECDC is monitoring with national public health authorities and WHO.", 1.95, 2.64, 6.05);
bullet("Sequencing is ongoing; the specific hantavirus strain has not yet been publicly clarified.", 1.95, 2.9, 6.05);

// Chart panel 1
rect(1.95, 3.32, 5.95, 1.62, C.white, { line: { color: C.teal, width: 1.4 } });
addText("Reported Hantavirus-Associated Illness Status, MV Hondius 2026", 2.4, 3.47, 5.05, 0.16, { fontSize: 9.5, bold: true, color: C.slate, align: "center" });
for (let i = 0; i < 4; i++) line(2.55, 3.78 + i * 0.25, 7.45, 3.78 + i * 0.25, "D3D7D8", 0.5);
line(2.55, 4.56, 7.45, 4.56, C.slate, 0.8);
const bars1 = [
  ["confirmed", 1, C.teal],
  ["suspected", 5, C.teal2],
  ["deaths", 3, C.rust],
  ["ICU", 1, C.plum],
];
bars1.forEach(([label, val, color], i) => {
  const x = 2.95 + i * 1.1;
  const h = val / 5 * 0.78;
  rect(x, 4.56 - h, 0.54, h, color);
  addText(label, x - 0.1, 4.64, 0.75, 0.16, { fontSize: 7.5, color: C.ink, align: "center" });
});
addText("5", 2.28, 3.73, 0.18, 0.12, { fontSize: 7, color: C.slate, align: "right" });
addText("3", 2.28, 4.12, 0.18, 0.12, { fontSize: 7, color: C.slate, align: "right" });
addText("0", 2.28, 4.52, 0.18, 0.12, { fontSize: 7, color: C.slate, align: "right" });

// Chart panel 2
rect(1.95, 5.15, 5.95, 1.62, C.white, { line: { color: C.teal, width: 1.4 } });
addText("Investigation Questions to Resolve", 2.8, 5.31, 4.2, 0.16, { fontSize: 9.5, bold: true, color: C.slate, align: "center" });
line(2.55, 6.39, 7.45, 6.39, C.slate, 0.8);
for (let i = 0; i < 3; i++) line(2.55, 5.68 + i * 0.24, 7.45, 5.68 + i * 0.24, "D3D7D8", 0.5);
const bars2 = [
  ["strain", 0.68, C.mist],
  ["source", 0.86, C.amber],
  ["crew", 0.5, C.rust],
  ["timeline", 0.77, C.mist],
  ["contacts", 0.38, C.amber],
  ["rodents", 0.58, C.rust],
];
bars2.forEach(([label, frac, color], i) => {
  const x = 2.75 + i * 0.74;
  const h = frac * 0.78;
  rect(x, 6.39 - h, 0.48, h, color);
  addText(label, x - 0.08, 6.47, 0.64, 0.16, { fontSize: 7.1, color: C.ink, align: "center" });
});
rect(2.55, 5.47, 0.12, 0.12, C.mist); addText("sequencing", 2.72, 5.46, 0.75, 0.12, { fontSize: 7.2, color: C.slate });
rect(3.55, 5.47, 0.12, 0.12, C.amber); addText("environment", 3.72, 5.46, 0.78, 0.12, { fontSize: 7.2, color: C.slate });
rect(4.76, 5.47, 0.12, 0.12, C.rust); addText("transmission", 4.93, 5.46, 0.86, 0.12, { fontSize: 7.2, color: C.slate });

// Response and recommendations
addText("RESPONSE ACTIVITIES:", 1.95, 7.08, 2.25, 0.22, { fontSize: 12.4, bold: true, color: C.ink });
line(1.95, 7.31, 3.69, 7.31, C.ink, 1);
bullet("Medical care, evacuation planning, and support for affected passengers and crew are ongoing.", 1.95, 7.38, 5.95, { fontSize: 9.8 });
bullet("Public health authorities are assessing shipboard risk, exposure history, and possible source.", 1.95, 7.61, 5.95, { fontSize: 9.8 });
bullet("Laboratory testing and sequencing are expected to clarify the virus and containment needs.", 1.95, 7.84, 5.95, { fontSize: 9.8 });
bullet("Contact tracing should focus on symptom timing, close contacts, and shared exposure spaces.", 1.95, 8.07, 5.95, { fontSize: 9.8 });

addText("PUBLIC RECOMMENDATIONS:", 1.95, 8.47, 2.55, 0.22, { fontSize: 12.4, bold: true, color: C.ink });
line(1.95, 8.7, 4.12, 8.7, C.ink, 1);
bullet("Wider public risk has been described by WHO Europe as low; no panic or broad travel restrictions.", 1.95, 8.77, 5.95, { fontSize: 9.8 });
bullet("Avoid exposure to rodent urine, feces, saliva, and dust in enclosed or poorly ventilated spaces.", 1.95, 9.0, 5.95, { fontSize: 9.8 });
bullet("Seek urgent medical care for fever plus worsening respiratory symptoms after possible exposure.", 1.95, 9.23, 5.95, { fontSize: 9.8 });
bullet("Watch for sequencing updates: Andes virus would raise different transmission concerns.", 1.95, 9.46, 5.95, { fontSize: 9.8 });

// Bottom image + rodent + symptoms
slide.addImage({ path: imgPath, x: 0.24, y: 9.88, w: 3.65, h: 1.15 });
rect(0.24, 10.79, 3.65, 0.24, C.ink, { transparency: 30 });
addText("CDC PHIL #1136: Sin Nombre hantavirus TEM", 0.32, 10.84, 3.2, 0.12, { fontSize: 7.5, color: C.white });

rect(4.14, 9.88, 1.8, 1.15, "EFE9DF");
slide.addShape(pptx.ShapeType.ellipse, { x: 4.55, y: 10.38, w: 1.0, h: 0.34, fill: { color: C.ink }, line: { color: C.ink } });
slide.addShape(pptx.ShapeType.ellipse, { x: 4.26, y: 10.26, w: 0.36, h: 0.36, fill: { color: C.ink }, line: { color: C.ink } });
slide.addShape(pptx.ShapeType.arc, { x: 5.34, y: 10.36, w: 0.54, h: 0.34, adjustPoint: 0.45, line: { color: C.ink, width: 3 } });
slide.addShape(pptx.ShapeType.triangle, { x: 4.18, y: 10.22, w: 0.28, h: 0.28, rotate: 315, fill: { color: C.ink }, line: { color: C.ink } });
slide.addShape(pptx.ShapeType.triangle, { x: 4.42, y: 10.2, w: 0.28, h: 0.28, rotate: 45, fill: { color: C.ink }, line: { color: C.ink } });
slide.addShape(pptx.ShapeType.ellipse, { x: 4.43, y: 10.39, w: 0.05, h: 0.05, fill: { color: C.white }, line: { color: C.white } });
["4.30,10.72", "4.50,10.78", "4.72,10.72"].forEach((p) => {
  const [x, y] = p.split(",").map(Number);
  slide.addShape(pptx.ShapeType.ellipse, { x, y, w: 0.06, h: 0.06, fill: { color: C.rust }, line: { color: C.rust } });
});
addText("Rodent-contaminated spaces", 4.28, 10.83, 1.44, 0.12, { fontSize: 7.4, bold: true, color: C.teal, align: "center" });

rect(6.18, 9.88, 1.94, 1.15, C.white, { line: { color: C.ink, width: 1 } });
addText("HANTAVIRUS\nSYMPTOMS:", 6.28, 9.97, 1.55, 0.28, { fontSize: 8.6, bold: true, color: C.ink });
line(6.28, 10.26, 7.62, 10.26, C.ink, 0.6);
addText("• Fever/chills\n• Muscle aches\n• GI symptoms\n• Cough or dyspnea\n• Rapid worsening", 6.28, 10.31, 1.65, 0.48, { fontSize: 7.0, color: C.ink, fit: "shrink" });
addText("SEVERE:", 6.28, 10.82, 0.58, 0.12, { fontSize: 7.4, bold: true, color: C.rust });
addText("low oxygen, shock", 6.82, 10.82, 0.96, 0.12, { fontSize: 7.0, color: C.ink });

// Footer
rect(0, 11.25, 8.5, 0.75, C.mist);
addText("For suspected exposure with respiratory symptoms, seek medical care urgently.", 0.35, 11.37, 7.8, 0.18, { fontSize: 13.4, bold: true, color: C.ink, align: "center" });
addText("Sources: WHO reporting via UN Geneva; ECDC news release; CDC hantavirus guidance and PHIL image library.", 0.55, 11.63, 7.4, 0.12, { fontSize: 7.9, color: C.ink, align: "center" });
addText("Numbers reflect public reporting available on 4 May 2026 and may change as the investigation develops.", 0.7, 11.79, 7.1, 0.1, { fontSize: 6.9, color: C.slate, align: "center" });

pptx.writeFile({ fileName: path.join(outDir, "mv_hondius_hantavirus_edge_template.pptx") });
