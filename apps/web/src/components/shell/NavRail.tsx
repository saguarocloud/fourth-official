import {
  Activity,
  ClipboardCheck,
  FileBadge,
  FlaskConical,
  Gauge,
  LayoutGrid,
  MonitorPlay,
  ScrollText,
  Undo2,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";

interface Screen {
  readonly label: string;
  readonly href: string;
  readonly icon: LucideIcon;
}

const SCREENS: readonly Screen[] = [
  { label: "Control Room", href: "/", icon: LayoutGrid },
  { label: "Match Live", href: "/match", icon: Activity },
  { label: "Broadcast Preview", href: "/preview", icon: MonitorPlay },
  { label: "Approvals", href: "/approvals", icon: ClipboardCheck },
  { label: "Corrections", href: "/corrections", icon: Undo2 },
  { label: "Provenance", href: "/provenance", icon: FileBadge },
  { label: "Policy Studio", href: "/policy", icon: ScrollText },
  { label: "Proving Ground", href: "/proving-ground", icon: FlaskConical },
  { label: "Operations", href: "/operations", icon: Gauge },
];

interface NavRailProps {
  readonly current: string;
}

export function NavRail({ current }: NavRailProps) {
  return (
    <nav aria-label="Primary" className="nav-rail">
      <ul>
        {SCREENS.map(({ label, href, icon: Icon }) => (
          <li key={href}>
            <Link
              href={href}
              className="nav-rail__item"
              aria-current={current === href ? "page" : undefined}
            >
              <Icon aria-hidden="true" strokeWidth={1.75} />
              <span>{label}</span>
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
