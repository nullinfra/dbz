const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '../../../../..');
const evaluation = path.resolve(process.argv[2] || '.');
const relativeEvaluation = path.relative(root, evaluation);
const segments = relativeEvaluation.split(path.sep);
if (segments.length !== 4 || segments[0] !== 'output' || segments[3] !== 'geolocation_eval') {
  throw new Error('Expected output/<chat_folder>/<message_folder>/geolocation_eval.');
}

const prompts = fs.readdirSync(evaluation, { recursive: true, withFileTypes: true })
  .filter(entry => entry.isFile() && entry.name === 'prompt.md')
  .map(entry => path.join(entry.parentPath, entry.name));
if (!prompts.length) throw new Error('No prepared case prompts found.');

const updates = prompts.map(file => {
  const prepared = path.dirname(file);
  const name = path.basename(prepared);
  const caseDirectory = path.join(relativeEvaluation, 'cases', name);
  const mapsFile = path.join(caseDirectory, 'maps_raw_output.json');
  const oldDirectory = `maps/output/evals/${evaluation}/cases/${name}`;
  const oldMapsFile = path.join(prepared, 'maps_raw_output.json');
  const content = fs.readFileSync(file, 'utf8');
  const message = content.indexOf('\n\nCustomer message:');
  if (message < 0) throw new Error(`No customer message in ${name}/prompt.md.`);
  const header = content.slice(0, message);
  if (header.includes(`--out-dir ${caseDirectory} --maps ${mapsFile}`) && header.includes(`--out ${mapsFile}`)) {
    return { file, content };
  }
  if (!header.includes(`--out-dir ${oldDirectory} --maps ${oldMapsFile}`) || !header.includes(`--out ${oldMapsFile}`)) {
    throw new Error(`Unexpected output assignment in ${name}/prompt.md.`);
  }
  const updated = header.replaceAll(oldDirectory, caseDirectory).replaceAll(oldMapsFile, mapsFile);
  return { file, content: updated + content.slice(message) };
});
for (const update of updates) fs.writeFileSync(update.file, update.content);
console.log(`Assigned ${updates.length} case output directories under ${relativeEvaluation}.`);
