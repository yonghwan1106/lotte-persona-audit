import { NextResponse } from "next/server";
import rulesData from "@/data/intake.json";
import { CAPS, takeSlot } from "@/lib/caps";
import { ANSWER_SCHEMA, codeCheck, decide, INSTRUCTIONS, MAX_CHARS, MIN_CLEAN_CHARS, parseModelAnswer, type IntakeRules } from "@/lib/intakeCore";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const rules = rulesData as unknown as IntakeRules;
const MODEL = "gpt-6-luna";
const ENDPOINT = "https://api.openai.com/v1/responses";
const MAX_OUTPUT_TOKENS = 600;
const MAX_BODY_BYTES = 4096;
const TIMEOUT_MS = 25000;

function reply(status: number, body: Record<string, unknown>) {
  return NextResponse.json(body, { status, headers: { "Cache-Control": "no-store" } });
}

function clientIp(request: Request): string {
  const forwarded = request.headers.get("x-forwarded-for");
  if (forwarded) return forwarded.split(",")[0].trim().slice(0, 64);
  return request.headers.get("x-real-ip")?.slice(0, 64) ?? "local";
}

function capsInfo() {
  return { per_ip_daily: CAPS.perIpDaily, global_daily: CAPS.globalDaily, max_chars: MAX_CHARS, max_output_tokens: MAX_OUTPUT_TOKENS };
}

export async function GET() {
  return reply(200, { available: Boolean(process.env.OPENAI_API_KEY), model: MODEL, caps: capsInfo() });
}

export async function POST(request: Request) {
  const key = process.env.OPENAI_API_KEY;
  if (!key) {
    return reply(503, { error: "no_api_key", notice: "이 서버에는 OPENAI_API_KEY가 없어 접수 시험을 쓸 수 없습니다. 사이트의 나머지 페이지는 그대로 볼 수 있습니다." });
  }
  const declared = Number(request.headers.get("content-length") ?? 0);
  if (declared > MAX_BODY_BYTES) return reply(413, { error: "too_large", notice: `입력은 ${MAX_CHARS}자까지 받습니다.` });

  let raw: string;
  try {
    raw = await request.text();
  } catch {
    return reply(400, { error: "bad_request", notice: "요청을 읽지 못했습니다." });
  }
  if (Buffer.byteLength(raw, "utf8") > MAX_BODY_BYTES) return reply(413, { error: "too_large", notice: `입력은 ${MAX_CHARS}자까지 받습니다.` });

  let input: unknown;
  try {
    input = (JSON.parse(raw) as { card?: unknown }).card;
  } catch {
    return reply(400, { error: "bad_request", notice: "요청 형식이 맞지 않습니다." });
  }
  if (typeof input !== "string") return reply(400, { error: "bad_request", notice: "카드 문장을 문자열로 보내 주세요." });
  const card = input.trim();
  if ([...card].length > MAX_CHARS) return reply(413, { error: "too_long", notice: `입력은 ${MAX_CHARS}자까지 받습니다.` });
  if ([...card].length < MIN_CLEAN_CHARS) return reply(400, { error: "too_short", notice: `콘셉트 문장을 ${MIN_CLEAN_CHARS}자 이상 적어 주세요.` });

  const slot = takeSlot(clientIp(request));
  if (!slot.ok) {
    const notice = slot.which === "ip" ? `이 주소의 오늘 한도 ${CAPS.perIpDaily}회를 다 썼습니다.` : `서버 전체의 오늘 한도 ${CAPS.globalDaily}회를 다 썼습니다.`;
    return reply(429, { error: "daily_cap", which: slot.which, notice });
  }

  const check = codeCheck(card, rules);
  let body: unknown = null;
  let upstreamStatus = 0;
  try {
    const response = await fetch(ENDPOINT, {
      method: "POST",
      headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        model: MODEL,
        instructions: INSTRUCTIONS,
        input: [{ role: "user", content: [{ type: "input_text", text: `<card>${card}</card>` }] }],
        text: { format: { type: "json_schema", name: "intake_answer", strict: true, schema: ANSWER_SCHEMA } },
        store: false,
        reasoning: { effort: "medium" },
        service_tier: "default",
        prompt_cache_options: { mode: "explicit" },
        max_output_tokens: MAX_OUTPUT_TOKENS,
      }),
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    upstreamStatus = response.status;
    // An upstream error message can quote part of the key, so it is never read or passed on. Only the status counts.
    if (response.ok) body = await response.json();
    else await response.body?.cancel();
  } catch {
    upstreamStatus = 0;
  }

  if (!body) {
    return reply(502, { error: "upstream", upstream_status: upstreamStatus, notice: "모델 호출이 실패했습니다. 재시도하지 않았고 결과를 만들지 않았습니다." });
  }

  const answer = parseModelAnswer(body);
  const result = decide(card, check, answer, rules);
  const usage = (body as { usage?: { input_tokens?: number; output_tokens?: number }; model?: string }).usage ?? {};
  const price = rules.models.cheap.usd_per_1m;
  const inputTokens = usage.input_tokens ?? 0;
  const outputTokens = usage.output_tokens ?? 0;
  return reply(200, {
    ...result,
    this_call: {
      model: MODEL,
      input_tokens: inputTokens,
      output_tokens: outputTokens,
      usd_at_list_price: Math.round(((inputTokens * price.input + outputTokens * price.output) / 1_000_000) * 1_000_000) / 1_000_000,
      store: false,
      ran_personas: false,
    },
    left_today: { this_address: slot.ipLeft, whole_server: slot.globalLeft },
  });
}
