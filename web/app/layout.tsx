import type { Metadata, Viewport } from "next";
import { Black_Han_Sans, IBM_Plex_Sans_KR } from "next/font/google";
import "./globals.css";
import { SiteNav } from "@/components/SiteNav";

// Korean has no preload subset in next/font, so both load through their unicode-range slices when used.
const display = Black_Han_Sans({ weight: "400", preload: false, display: "swap", variable: "--font-display" });
const body = IBM_Plex_Sans_KR({ weight: ["400", "500", "700"], preload: false, display: "swap", variable: "--font-body" });

export const metadata: Metadata = {
  title: "합성 패널 감사 기록",
  description: "GPT 패널은 기존 음료 행동을 실제 응답보다 높게 답했습니다. 콘셉트를 실제 200명 조사에 넘기기 전에 패널로 안을 훑어 판단 자료를 내고, 패널을 실제 응답과 겨룬 기록을 남기는 서비스의 시연과 측정 기록입니다.",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko" className={`${display.variable} ${body.variable}`}>
      <body>
        <div className="top-note">롯데 자료를 쓰지 않았습니다. 이 사이트는 롯데와 제휴 관계가 없는 공모전 응모자의 개인 작업입니다.</div>
        <header className="site-head">
          <a className="site-name" href="/">
            합성 패널 감사 기록
          </a>
          <SiteNav showIntake={Boolean(process.env.OPENAI_API_KEY)} />
        </header>
        <main>{children}</main>
        <footer className="site-foot">
          <p>롯데 자료를 쓰지 않았고, 롯데와 제휴 관계가 없습니다. 수치 출처는 저장소의 results/numbers_sheet.json입니다.</p>
          <p>
            자료: 한국농촌경제연구원, 식품소비행태조사 2025 원자료(2023, 2024 원자료 포함)의 집계입니다. 공공누리 제4유형이고, 이 응모 이용은 KREI 학술정보팀 메일 회신(2026-11-02)을 따랐습니다. 원자료와 응답자 단위 파생본은 이 사이트에 없습니다. <a href="/repro">출처와 이용 조건</a>
          </p>
          <p>
            코드와 집계: <a href="https://github.com/yonghwan1106/lotte-persona-audit" rel="noreferrer">github.com/yonghwan1106/lotte-persona-audit</a>
          </p>
        </footer>
      </body>
    </html>
  );
}
