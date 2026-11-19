const fs = require('node:fs');
const path = require('node:path');
const { randomUUID } = require('node:crypto');
const { appendObservation } = require('./observe-message.cjs');

const root = path.resolve(__dirname, '..');
const output = path.join(root, 'output');
const chatIndex = path.join(output, '.chat-ids');
const timestampName = /^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}Z(?:-\d{3,})?$/;

function id(value, field) {
  if (typeof value !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$/.test(value)) {
    throw new Error(`Expected a path-safe ${field}.`);
  }
  return value;
}

function reserveTimestampDirectory(parent, receivedAt) {
  const stamp = receivedAt.slice(0, 19).replace('T', '_').replaceAll(':', '-') + 'Z';
  for (let sequence = 1; ; sequence += 1) {
    const name = sequence === 1 ? stamp : `${stamp}-${String(sequence).padStart(3, '0')}`;
    const directory = path.join(parent, name);
    try {
      fs.mkdirSync(directory);
      return directory;
    } catch (error) {
      if (error.code !== 'EEXIST') throw error;
    }
  }
}

function findSession(chatId) {
  const key = id(chatId, 'chat ID');
  try {
    const target = fs.readlinkSync(path.join(chatIndex, key));
    const name = path.basename(target);
    if (target !== path.join('..', name) || !timestampName.test(name)) {
      throw new Error('Invalid chat directory in the output index.');
    }
    return path.join(output, name);
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
  const legacy = path.join(output, key);
  return fs.existsSync(legacy) ? legacy : null;
}

function sessionDirectory(chatId) {
  const existing = findSession(chatId);
  if (existing) return existing;

  fs.mkdirSync(chatIndex, { recursive: true });
  const startedAt = new Date().toISOString();
  const directory = reserveTimestampDirectory(output, startedAt);
  const metadata = path.join(directory, '.chat.json');
  try {
    fs.writeFileSync(metadata, JSON.stringify({ chat_id: chatId, started_at: startedAt }, null, 2) + '\n');
    fs.symlinkSync(path.join('..', path.basename(directory)), path.join(chatIndex, chatId));
    return directory;
  } catch (error) {
    fs.rmSync(metadata, { force: true });
    fs.rmdirSync(directory);
    if (error.code !== 'EEXIST') throw error;
    return findSession(chatId);
  }
}

function resolveChatArgument(chatId) {
  if (!timestampName.test(chatId ?? '')) return chatId;
  const metadata = path.join(output, chatId, '.chat.json');
  if (!fs.existsSync(metadata)) return chatId;
  return id(JSON.parse(fs.readFileSync(metadata, 'utf8')).chat_id, 'chat ID');
}

function messageDirectory(chatId, { turnId = null, messageId, rawInput = null } = {}) {
  if (turnId !== null) id(turnId, 'turn ID');
  const chat = sessionDirectory(chatId);
  const receivedAt = new Date().toISOString();
  const directory = messageId
    ? path.join(chat, id(messageId, 'message ID'))
    : reserveTimestampDirectory(chat, receivedAt);
  if (messageId) fs.mkdirSync(directory, { recursive: true });
  try {
    fs.writeFileSync(path.join(directory, 'message.json'), JSON.stringify({
      chat_id: chatId,
      message_id: path.basename(directory),
      turn_id: turnId,
      received_at: receivedAt,
      raw_input: rawInput,
    }, null, 2) + '\n', { flag: 'wx' });
  } catch (error) {
    if (error.code !== 'EEXIST') throw error;
  }
  return directory;
}

function activeMessage(chatId, turnId) {
  if (!turnId) return null;
  const chat = findSession(chatId);
  if (!chat) return null;
  const legacyPrefix = `${id(turnId, 'turn ID')}__`;
  const names = fs.readdirSync(chat, { withFileTypes: true })
    .filter(entry => entry.isDirectory())
    .map(entry => entry.name)
    .sort()
    .reverse();

  function newestCandidate(matches) {
    for (const name of names.filter(matches)) {
      const directory = path.join(chat, name);
      try {
        const metadata = JSON.parse(fs.readFileSync(path.join(directory, 'message.json'), 'utf8'));
        if (metadata.turn_id === turnId) return { directory, receivedAt: metadata.received_at };
      } catch (error) {
        if (error.code !== 'ENOENT') throw error;
      }
    }
    return null;
  }

  const current = newestCandidate(name => timestampName.test(name));
  const legacy = newestCandidate(name => name.startsWith(legacyPrefix));
  if (current && (!legacy || current.receivedAt >= legacy.receivedAt)) return current.directory;
  return legacy?.directory ?? null;
}

function onHook(event) {
  if (process.env.RESTAURANTE_EVAL_WORKER === '1') return;

  const { hook_event_name: name, session_id: chatId, turn_id: turnId } = event;
  if (name === 'SessionStart') {
    sessionDirectory(chatId);
    return;
  }
  if (name === 'UserPromptSubmit') {
    const rawInput = typeof event.prompt === 'string' ? event.prompt : null;
    const directory = messageDirectory(chatId, { turnId, rawInput });
    appendObservation(directory, event);
    const messagePath = path.relative(root, directory);
    process.stdout.write(JSON.stringify({
      hookSpecificOutput: {
        hookEventName: name,
        additionalContext: `Restaurante output directory for this message: ${messagePath}. Use this exact directory for the current message and pass it to all selected ICMs.`,
      },
    }) + '\n');
    return;
  }

  const directory = activeMessage(chatId, turnId);
  if (!directory) return;
  appendObservation(directory, event);
  if (name === 'Stop' || name === 'Interrupt') {
    const legacy = path.join(output, id(chatId, 'chat ID'));
    const currentChat = path.dirname(directory);
    if (currentChat !== legacy && fs.lstatSync(legacy, { throwIfNoEntry: false })?.isSymbolicLink() &&
        fs.realpathSync(legacy) === currentChat) {
      fs.unlinkSync(legacy);
    }
  }
}

try {
  const [command, ...args] = process.argv.slice(2);
  const fromStdin = command === 'message' && args[0] === '--stdin';
  const [chatId, messageId] = fromStdin ? args.slice(1) : args;
  const currentChat = resolveChatArgument(chatId) || process.env.CODEX_SESSION_ID || process.env.CODEX_THREAD_ID;
  if (command === 'hook') {
    onHook(JSON.parse(fs.readFileSync(0, 'utf8')));
  } else if (command === 'session') {
    console.log(path.relative(root, sessionDirectory(currentChat || randomUUID())));
  } else if (command === 'message') {
    const rawInput = fromStdin ? fs.readFileSync(0, 'utf8') : null;
    console.log(path.relative(root, messageDirectory(currentChat, { messageId, rawInput })));
  } else {
    throw new Error('Usage: node .codex/chat-output.cjs session [chat-id] | message [--stdin] [chat-id [message-id]]');
  }
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
