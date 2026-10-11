interface TallyLightProps {
  readonly live: boolean;
  readonly partner: string;
}

/**
 * Broadcast tally: lit red while a partner has one of our graphics on air. Deliberately not a
 * live region: a wall of tallies must not narrate every change; the activity log announces.
 */
export function TallyLight({ live, partner }: TallyLightProps) {
  return (
    <span
      role="img"
      aria-label={`${partner}: ${live ? "on air" : "off air"}`}
      data-live={live}
      className="tally"
    >
      <span aria-hidden="true" className="tally__lamp" />
      <span aria-hidden="true" className="tally__text">
        {live ? "On air" : "Off"}
      </span>
    </span>
  );
}
