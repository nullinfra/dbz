const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '../../../..');
const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8'));
const writeJson = (file, value) => fs.writeFileSync(file, JSON.stringify(value, null, 2) + '\n');
const turnName = index => String(index + 1).padStart(2, '0');
const workDirectory = evaluation => path.join(path.dirname(evaluation), '.ola_click_eval_work');

function evaluationDirectory(input, message = false) {
  if (process.cwd() !== root) throw new Error('Run from the Restaurante root.');
  if (!input) throw new Error(`Supply the ${message ? 'allocated message' : 'evaluation'} directory.`);
  const dir = fs.realpathSync(message ? input : path.dirname(input));
  const parts = path.relative(root, dir).split(path.sep);
  if (parts.length !== 3 || parts[0] !== 'output' || parts.includes('..') ||
      !fs.existsSync(path.join(dir, 'message.json')) ||
      (!message && path.basename(input) !== 'ola_click_eval')) {
    throw new Error('Use output/<chat>/<message>/ola_click_eval and its allocated message.');
  }
  const evaluation = path.join(dir, 'ola_click_eval');
  const entry = fs.lstatSync(evaluation, { throwIfNoEntry: false });
  if (entry && !entry.isDirectory()) throw new Error('Expected a local evaluation directory.');
  return evaluation;
}

module.exports = { root, readJson, writeJson, turnName, evaluationDirectory, workDirectory };
