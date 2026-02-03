/**
 * Slack Auto Thread Comment + Edit + Global Template (Beginner-friendly)
 *
 * 기능
 * - 특정 채널(TARGET_CHANNEL_ID)에 "새 원글"이 올라오면 스레드로 자동 댓글을 1회만 작성
 * - 스레드 안에서 "!edit ..." 또는 ".edit ..."를 쓰면
 *   1) 그 스레드의 자동 댓글을 수정하고
 *   2) 동시에 "기본 템플릿"도 갱신해서, 이후 새 글에도 같은 내용이 자동 댓글로 달리게 함
 * - 관리자 제한(선택): ADMIN_USER_IDS에 등록된 사용자만 수정 가능
 *
 * 준비
 * - npm i @slack/bolt dotenv
 * - .env
 *   SLACK_BOT_TOKEN=xoxb-...
 *   SLACK_SIGNING_SECRET=...
 *   TARGET_CHANNEL_ID=C0123456789
 *   ADMIN_USER_IDS=U0123456789,U0987654321   (선택)
 */

const fs = require("fs");
const path = require("path");
const { App, ExpressReceiver } = require("@slack/bolt");
require("dotenv").config();

const receiver = new ExpressReceiver({
  signingSecret: process.env.SLACK_SIGNING_SECRET,
});

const app = new App({
  token: process.env.SLACK_BOT_TOKEN,
  receiver,
});

const targetChannel = (process.env.TARGET_CHANNEL_ID || "").trim();
if (!targetChannel) {
  console.error("TARGET_CHANNEL_ID가 .env에 없습니다");
  process.exit(1);
}

const adminUserIds = (process.env.ADMIN_USER_IDS || "")
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean);

const STORE_PATH = path.join(__dirname, "comment_store.json");

// store 내부에 템플릿을 저장하는 고정 키
const TEMPLATE_KEY = "__template__";

// 템플릿이 한 번도 설정되지 않았을 때의 기본 텍스트
const DEFAULT_TEMPLATE_TEXT = "자동 댓글입니다\n링크: https://example.com";

function loadStore() {
  try {
    return JSON.parse(fs.readFileSync(STORE_PATH, "utf8"));
  } catch {
    return {};
  }
}

function saveStore(store) {
  fs.writeFileSync(STORE_PATH, JSON.stringify(store, null, 2), "utf8");
}

function makeKey(channel, rootTs) {
  return `${channel}:${rootTs}`;
}

function isEditCommand(text) {
  const t = (text || "").trim();
  return t.startsWith("!edit") || t.startsWith(".edit");
}

function extractEditText(text) {
  return (text || "")
    .trim()
    .replace(/^(!edit|\.edit)\s*/i, "")
    .trim();
}

// message 이벤트 처리
app.event("message", async ({ event, client, logger }) => {
  try {
    // 0) 봇/시스템/수정(message_changed 등) 이벤트는 무시 (루프/중복 방지)
    if (event.subtype) return;

    // 1) 특정 채널만 처리
    if (event.channel !== targetChannel) return;

    const text = (event.text || "").trim();

    // 2) 수정 명령 처리: 스레드 안에서 !edit 또는 .edit
    if (isEditCommand(text)) {
      // 관리자 제한(ADMIN_USER_IDS가 설정된 경우만 적용)
      if (adminUserIds.length > 0 && !adminUserIds.includes(event.user)) {
        return;
      }

      // 반드시 스레드 안에서만 (rootTs = 원글 ts)
      const rootTs = event.thread_ts;
      if (!rootTs) return;

      const newText = extractEditText(text);
      if (!newText) return;

      const store = loadStore();
      const key = makeKey(event.channel, rootTs);
      const commentTs = store[key];

      // 저장된 자동 댓글이 없으면 수정할 대상이 없으므로 종료
      if (!commentTs) return;

      // 2-1) 해당 스레드의 자동 댓글 수정
      await client.chat.update({
        channel: event.channel,
        ts: commentTs,
        text: newText,
      });

      // 2-2) "전역 템플릿"도 갱신: 이후 새 글에도 이 내용이 기본으로 달림
      store[TEMPLATE_KEY] = newText;
      saveStore(store);

      return; // 중요: 아래 자동댓글 로직으로 내려가지 않게
    }

    // 3) 자동 댓글 달기: "새 원글"에만
    // 스레드 댓글은 event.thread_ts가 존재하므로 제외
    if (event.thread_ts) return;

    // 3-1) 중복 방지: 같은 원글에 대해 자동댓글이 이미 있으면 다시 달지 않음
    const store = loadStore();
    const key = makeKey(event.channel, event.ts);
    if (store[key]) return;

    // 3-2) 템플릿 텍스트 결정
    const templateText = store[TEMPLATE_KEY] || DEFAULT_TEMPLATE_TEXT;

    // 3-3) 자동 댓글 작성
    const res = await client.chat.postMessage({
      channel: event.channel,
      thread_ts: event.ts,
      text: templateText,
    });

    // 3-4) 자동 댓글 ts 저장 (원글 ts -> 자동댓글 ts)
    store[key] = res.ts;
    saveStore(store);
  } catch (e) {
    logger.error(e);
  }
});

(async () => {
  const port = process.env.PORT || 3000;
  await app.start(port);
  console.log(`Slack app is running on port ${port}`);
})();