import type { Metadata } from "next";
import { Caveats } from "@/components/Notes";
import { IntakeForm } from "@/components/IntakeForm";
import rules from "@/data/intake.json";
import { CAPS } from "@/lib/caps";
import { MAX_CHARS, MIN_CLEAN_CHARS } from "@/lib/intakeCore";
import { caveats, num } from "@/lib/numbers";

export const metadata: Metadata = { title: "접수 시험 · 합성 패널 감사 기록" };
export const dynamic = "force-dynamic";

export default function IntakePage() {
  const available = Boolean(process.env.OPENAI_API_KEY);
  const main = rules.models.main;
  const cheap = rules.models.cheap;
  const costKeys = ["cost.concept_prompt.terra.six_cards.per_respondent_usd", "cost.concept_prompt.luna.six_cards.per_respondent_usd"];
  return (
    <>
      <h1>접수 시험</h1>
      <p className="lead">콘셉트 카드 문장 하나를 넣으면 받은 항목, 거절한 항목, 호출 수와 비용 계획을 돌려줍니다. 페르소나를 돌리지 않고, 판정도 내지 않습니다. 맛 평가, 패키지 시안, 판매량, 성공 확률, 단일 점수는 거절합니다.</p>

      <IntakeForm available={available} maxChars={MAX_CHARS} minChars={MIN_CLEAN_CHARS} />

      <h2>이 화면의 한도</h2>
      <ul>
        <li>입력은 {MAX_CHARS}자까지, 모델은 {cheap.id} 한 번, 출력 토큰 상한 600, 재시도 없음.</li>
        <li>
          호출 횟수는 주소당 하루 {CAPS.perIpDaily}회, 서버 전체 하루 {CAPS.globalDaily}회입니다(한국 시간 자정 기준). 서버 메모리에 세므로 서버를 다시 시작하면 초기화되고, 인스턴스가 여럿이면 각자 셉니다.
        </li>
        <li>
          요청은 <code>store: false</code>로 보내고, 입력 문장을 이 서버에 저장하지 않습니다. 응답에는 키가 담기지 않고, 모델 호출이 실패하면 상위 오류 문구를 읽지 않고 고정 문구만 돌려줍니다.
        </li>
      </ul>

      <h2>판단은 어디서 하나</h2>
      <ul>
        <li>거절 패턴, 지시문 패턴, 사실형 유도 패턴은 코드입니다. 저장소의 config/agent_text.json에서 복사했습니다. 패턴은 시험한 형태만 잡으므로 다르게 쓴 문장은 통과할 수 있습니다. 예를 들어 「요즘 다들 이걸 마신다.」는 걸리지 않습니다.</li>
        <li>모델은 거절 분류를 더하거나 문장 전체를 지목하거나 입력 원문의 문구를 옮길 수만 있습니다. 입력에 없는 문구는 코드가 버립니다. 모델이 잘못 분류할 수 있고, 이 화면의 거절률은 재지 않았습니다.</li>
        <li>
          호출 수와 비용은 모델이 아니라 코드가 계산합니다. 시연 계획과 같은 식이고 같은 가격 값입니다. 입력 토큰 {rules.planning.tokens_per_call[main.id as keyof typeof rules.planning.tokens_per_call].input}, 출력 토큰 {rules.planning.tokens_per_call[main.id as keyof typeof rules.planning.tokens_per_call].output}을 쓴 {main.id}와 입력 {rules.planning.tokens_per_call[cheap.id as keyof typeof rules.planning.tokens_per_call].input}, 출력 {rules.planning.tokens_per_call[cheap.id as keyof typeof rules.planning.tokens_per_call].output}을 쓴 {cheap.id}의 계획값이고, 표준 tier 목록가({main.id} {main.usd_per_1m.input}/{main.usd_per_1m.output}, {cheap.id} {cheap.usd_per_1m.input}/{cheap.usd_per_1m.output} USD, 100만 토큰당, {rules.pricing_source.read_at} 읽음)를 곱했습니다.
        </li>
        <li>
          참고로 시연의 실제 호출 평균으로 환산한 응답자 1명 6카드 비용은 {main.id} USD {num(costKeys[0])}, {cheap.id} USD {num(costKeys[1])}입니다.
        </li>
        <li>사람 승인 화면은 없습니다. 이 화면의 계획은 미리보기이고, 어떤 패널도 시작하지 않습니다.</li>
      </ul>
      <Caveats items={caveats(costKeys)} />
    </>
  );
}
