/**
 * WhatsApp Web sidecar — keeps a persistent session alive and exposes a tiny
 * HTTP API for the Python orchestrator (Agent 3).
 *
 * Endpoints:
 *   GET  /status        {ready, connected, hasQr}
 *   GET  /qr            {qr}  (current QR string, or "")
 *   POST /send          {to, text}  -> {id, status} ; to = E.164 without '+'
 *   GET  /inbox?after=<ISO or unix>  -> [{from, body, when}]
 *
 * Run: npm install && npm start   (first run prints a QR to the terminal)
 */
const { Client, LocalAuth } = require("whatsapp-web.js");
const qrcode = require("qrcode-terminal");
const express = require("express");

const PORT = process.env.WA_SIDECAR_PORT || 3001;
const AUTOSTART = process.env.WA_AUTOSTART !== "false";

const app = express();
app.use(express.json());

let state = { ready: false, qr: "" };
const inbox = []; // bounded recent inbound messages

function normalize(wid) {
  const s = String(wid || "").split("@")[0].replace(/[^0-9]/g, "");
  return s;
}

const client = new Client({
  authStrategy: new LocalAuth({ dataPath: "./session-data" }),
  puppeteer: { args: ["--no-sandbox", "--disable-setuid-sandbox"] },
});

client.on("qr", (qr) => {
  state.qr = qr;
  console.log("[wa] QR scan required:");
  qrcode.generate(qr, { small: true });
});

client.on("ready", () => {
  state.qr = "";
  state.ready = true;
  console.log("[wa] session ready");
});

client.on("authenticated", () => console.log("[wa] authenticated"));
client.on("auth_failure", (msg) => console.error("[wa] auth failure:", msg));
client.on("disconnected", (reason) => {
  state.ready = false;
  console.error("[wa] disconnected:", reason);
});

client.on("message", (msg) => {
  inbox.push({
    from: normalize(msg.from),
    body: msg.body || "",
    when: msg.timestamp ? msg.timestamp * 1000 : Date.now(),
  });
  if (inbox.length > 500) inbox.shift();
});

app.get("/status", (_req, res) => res.json({ ready: state.ready, hasQr: !!state.qr, port: PORT }));

app.get("/qr", (_req, res) => res.json({ qr: state.qr }));

app.post("/send", async (req, res) => {
  if (!state.ready) return res.status(503).json({ error: "session not ready" });
  const { to, text } = req.body || {};
  if (!to || !text) return res.status(400).json({ error: "to and text are required" });
  try {
    const chatId = normalize(to) + "@c.us";
    const sent = await client.sendMessage(chatId, String(text));
    res.json({ id: sent.id.id, status: "sent" });
  } catch (err) {
    res.status(502).json({ error: String(err && err.message || err) });
  }
});

app.get("/inbox", (req, res) => {
  const after = Number(req.query.after) || 0;
  res.json(inbox.filter((m) => m.when > after));
});

app.listen(PORT, () => {
  console.log(`[wa] sidecar on :${PORT}${AUTOSTART ? "" : " (manual start via /qr+init)"}`);
  if (AUTOSTART) client.initialize();
});