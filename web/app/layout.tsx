import type { Metadata, Viewport } from "next";
import "pretendard/dist/web/variable/pretendardvariable-dynamic-subset.css";
import "./globals.css";
import { SiteNav } from "@/components/SiteNav";

export const metadata: Metadata = {
  title: "합성 패널 감사 기록",
  description: "콘셉트를 실측 설문에 넘기기 전에 어떤 안을 넣을지 판단 자료를 내는 시연과, LLM 페르소나 패널이 실제 응답자의 숨긴 답을 어디까지 재현하는지 잰 기록입니다. 기존 음료 행동만 쟀습니다.",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body>
        <div className="disclosure">
          <div className="wrap">롯데 자료를 쓰지 않았습니다. 이 사이트는 롯데와 제휴 관계가 없는 공모전 응모자의 개인 작업입니다.</div>
        </div>
        <header className="site-head">
          <div className="wrap">
            <a className="site-name" href="/">
              합성 패널 감사 기록
            </a>
            <SiteNav showIntake={Boolean(process.env.OPENAI_API_KEY)} />
          </div>
        </header>
        <main>
          <div className="wrap">{children}</div>
        </main>
        <footer className="site-foot">
          <div className="wrap">
            <p>롯데 자료를 쓰지 않았고, 롯데와 제휴 관계가 없습니다. 수치 출처는 저장소의 results/numbers_sheet.json입니다.</p>
            <p>
              자료: 한국농촌경제연구원, 식품소비행태조사 2025 원자료(2023, 2024 원자료 포함)의 집계입니다. 공공누리 제4유형이고, 이 응모 이용은 KREI 학술정보팀 메일 회신(2026-11-02)을 따랐습니다. 원자료와 응답자 단위 파생본은 이 사이트에 없습니다. <a href="/repro">출처와 이용 조건</a>
            </p>
            <p>
              코드와 집계: <a href="https://github.com/yonghwan1106/lotte-persona-audit" rel="noreferrer">github.com/yonghwan1106/lotte-persona-audit</a>
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
