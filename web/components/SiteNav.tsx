"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "첫 화면" },
  { href: "/results", label: "측정 결과" },
  { href: "/run", label: "실행 기록" },
  { href: "/attacks", label: "공격 기록" },
  { href: "/repro", label: "재현과 자료" },
];
const INTAKE_LINK = { href: "/intake", label: "접수 시험" };

/** The intake page works only with a server key, so the link appears only in a build that has one. */
export function SiteNav({ showIntake }: { showIntake: boolean }) {
  const path = usePathname();
  return (
    <nav className="site-nav" aria-label="주요 페이지">
      {[...LINKS, ...(showIntake ? [INTAKE_LINK] : [])].map((link) => (
        <Link key={link.href} href={link.href} prefetch={false} aria-current={path === link.href ? "page" : undefined}>
          {link.label}
        </Link>
      ))}
    </nav>
  );
}
