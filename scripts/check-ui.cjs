/* Source and server-render regression checks. No network calls or browser automation. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const Module = require("node:module");
const ts = require("typescript");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const root = path.resolve(__dirname, "..");
const resolve = Module._resolveFilename;
Module._resolveFilename = function (name, parent, ...args) {
  return resolve.call(this, name.startsWith("@/") ? path.join(root, name.slice(2)) : name, parent, ...args);
};
for (const extension of [".ts", ".tsx"]) {
  require.extensions[extension] = (module, filename) => {
    const result = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
      compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
      fileName: filename,
    });
    module._compile(result.outputText, filename);
  };
}

const { ReportSection } = require("../components/report/ReportSections.tsx");
const { DEMO_REPORT } = require("../lib/demo-report.ts");
const { ConfidenceGauge } = require("../components/report/primitives.tsx");
const { OrbitLogo } = require("../components/OrbitLogo.tsx");
const sections = ["Architecture", "User flows", "Features", "Entities", "Permissions", "Database", "API", "Tech stack", "Insights"];
for (const active of sections) {
  const markup = renderToStaticMarkup(React.createElement(ReportSection, { active, doc: DEMO_REPORT }));
  assert(markup.includes("section-panel"), `${active} needs a section panel`);
  assert(!markup.includes("This section is not available"), `${active} fell through to the fallback`);
  assert(markup.includes(`<h2>${active === "Insights" ? "Engineering insights" : active}</h2>`), `${active} has no matching heading`);
  if (active === "API") assert(markup.includes("/api/graphql"));
  if (active === "Entities" || active === "Database") assert(markup.includes("Workspace") && markup.includes("assignee_id"));
  console.log(`PASS: ${active} renders distinct content`);
}
assert.equal(DEMO_REPORT.meta.features_count, DEMO_REPORT.features.items.length);
assert.equal(DEMO_REPORT.meta.technologies_count, DEMO_REPORT.tech_stack.items.length);
assert.equal(DEMO_REPORT.meta.insights_count, DEMO_REPORT.insights.items.length);
const gauge = renderToStaticMarkup(React.createElement(ConfidenceGauge, { score: 86 }));
assert(gauge.includes('class="confidence-label"'));
assert(!gauge.includes("<small>Overall confidence</small>"));
assert(gauge.indexOf('class="confidence-label"') > gauge.indexOf('class="confidence-score"'));
const logo = renderToStaticMarkup(React.createElement(OrbitLogo));
assert(logo.includes("orbit-logo-path") && !logo.includes("<circle"));
console.log("PASS: confidence caption separated and new logo rendered");

let buttonCount = 0;
const deadButtons = [];
function audit(folder) {
  for (const file of fs.readdirSync(folder, { withFileTypes: true })) {
    const filename = path.join(folder, file.name);
    if (file.isDirectory()) { audit(filename); continue; }
    if (!file.name.endsWith(".tsx")) continue;
    const source = ts.createSourceFile(filename, fs.readFileSync(filename, "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
    function visit(node) {
      if ((ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) && node.tagName.getText(source) === "button") {
        buttonCount++;
        const attrs = node.attributes.properties.filter(ts.isJsxAttribute);
        const attribute = (name) => attrs.find((a) => a.name.getText(source) === name);
        const disabled = attribute("disabled");
        const deliberatelyDisabled = disabled && (!disabled.initializer || (ts.isJsxExpression(disabled.initializer) && disabled.initializer.expression?.kind === ts.SyntaxKind.TrueKeyword));
        const type = attribute("type");
        const submits = type && ts.isStringLiteral(type.initializer) && type.initializer.text === "submit";
        if (!attribute("onClick") && !deliberatelyDisabled && !submits) {
          const line = source.getLineAndCharacterOfPosition(node.getStart()).line + 1;
          deadButtons.push(`${path.relative(root, filename)}:${line}`);
        }
      }
      ts.forEachChild(node, visit);
    }
    visit(source);
  }
}
audit(path.join(root, "app"));
audit(path.join(root, "components"));
assert.deepEqual(deadButtons, [], `Enabled buttons without an action: ${deadButtons.join(", ")}`);
console.log(`PASS: ${buttonCount} native button declarations have an action, submit behavior, or explicit disabled state`);

const { downloadText } = require("../lib/download.ts");
const actions = [];
const anchor = { click: () => actions.push("clicked"), remove: () => actions.push("removed") };
global.document = { createElement: () => anchor, body: { appendChild: () => actions.push("attached") } };
global.window = { setTimeout: (callback) => { actions.push("cleanup scheduled"); callback(); } };
downloadText("orbit-demo.json", JSON.stringify(DEMO_REPORT), "application/json");
assert.equal(anchor.download, "orbit-demo.json");
assert.deepEqual(actions, ["attached", "clicked", "removed", "cleanup scheduled"]);
console.log("PASS: report export creates a downloadable file and cleans up its URL");

// Exercise the demo's real click callbacks without a browser or external account.
const load = Module._load;
const routes = [];
Module._load = function (name, ...args) {
  if (name === "next/navigation") return { useRouter: () => ({ push: (route) => routes.push(route) }) };
  return load.call(this, name, ...args);
};
const DemoPage = require("../app/report/demo/page.tsx").default;
const originalUseState = React.useState;
let active = "Overview";
React.useState = () => [active, (value) => { active = value; }];
function elements(tree, predicate, result = []) {
  if (!React.isValidElement(tree)) return result;
  if (predicate(tree)) result.push(tree);
  React.Children.forEach(tree.props.children, (child) => elements(child, predicate, result));
  return result;
}
try {
  for (const label of sections) {
    const tree = DemoPage();
    const button = elements(tree, (element) => element.type === "button" && React.Children.toArray(element.props.children).includes(label))[0];
    assert(button, `${label} navigation missing`);
    button.props.onClick();
    const selected = elements(DemoPage(), (element) => element.type === ReportSection)[0];
    assert.equal(selected.props.active, label);
    console.log(`PASS: ${label} click selects its section`);
  }
  const tree = DemoPage();
  for (const [label, component] of [["Overview", "DemoOverview"], ["Ask Orbit", "AskOrbit"], ["Workflow Lab", "WorkflowStudio"]]) {
    elements(DemoPage(), (element) => element.type === "button" && React.Children.toArray(element.props.children).includes(label))[0].props.onClick();
    assert(elements(DemoPage(), (element) => typeof element.type === "function" && element.type.name === component).length > 0);
    console.log(`PASS: ${label} click selects its experience`);
  }
  elements(tree, (element) => element.props["aria-label"] === "Report account")[0].props.onClick();
  assert.deepEqual(routes, ["/settings"]);
  elements(tree, (element) => element.type === "button" && element.props.className === "export-nav")[0].props.onClick();
  assert.equal(anchor.download, "orbit-linear-demo.json");
  console.log("PASS: demo account and export click handlers perform their actions");
} finally {
  React.useState = originalUseState;
  Module._load = load;
}
