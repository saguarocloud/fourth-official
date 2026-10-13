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
  /** Screens arrive phase by phase; unbuilt ones are listed but not linked. */
  readonly available: boolean;
}

const SCREENS: readonly Screen[] = [
  { label: "Control Room", href: "/", icon: LayoutGrid, available: true },
  { label: "Match Live", href: "/match", icon: Activity, available: true },
  { label: "Broadcast Preview", href: "/preview", icon: MonitorPlay, available: true },
  { label: "Approvals", href: "/approvals", icon: ClipboardCheck, available: true },
  { label: "Corrections", href: "/corrections", icon: Undo2, available: true },
  { label: "Provenance", href: "/provenance", icon: FileBadge, available: true },
  { label: "Policy Studio", href: "/policy", icon: ScrollText, available: true },
  { label: "Proving Ground", href: "/proving-ground", icon: FlaskConical, available: true },
  { label: "Operations", href: "/operations", icon: Gauge, available: false },
];

interface NavRailProps {
  readonly current: string;
}

export function NavRail({ current }: NavRailProps) {
  return (
    <nav aria-label="Primary" className="nav-rail">
      <ul>
        {SCREENS.map(({ label, href, icon: Icon, available }) => (
          <li key={href}>
            {available ? (
              <Link
                href={href}
                className="nav-rail__item"
                aria-current={current === href ? "page" : undefined}
              >
                <Icon aria-hidden="true" strokeWidth={1.75} />
                <span>{label}</span>
              </Link>
            ) : (
              <span
                className="nav-rail__item"
                data-unavailable
                title={`${label}: not yet available`}
              >
                <Icon aria-hidden="true" strokeWidth={1.75} />
                <span>{label}</span>
                <span className="sr-only">(not yet available)</span>
              </span>
            )}
          </li>
        ))}
      </ul>
    </nav>
  );
}
