// Illustration of the Hawa Mahal ("Palace of Winds", Jaipur), drawn with SVG in code:
// stepped storeys covered in small arched windows (jharokhas), with domed pavilions on the
// ledges. On load some windows light up one after another, like lamps at dusk. The colours come
// from the theme, so it works in light and dark mode; the animation is switched off for people
// who prefer reduced motion (theme.css).

type Tier = { left: number; right: number; top: number; bottom: number; rows: number };

const TIERS: Tier[] = [
  { left: 40, right: 480, top: 280, bottom: 360, rows: 2 },
  { left: 72, right: 448, top: 214, bottom: 280, rows: 2 },
  { left: 112, right: 408, top: 158, bottom: 214, rows: 2 },
  { left: 158, right: 362, top: 116, bottom: 158, rows: 1 },
  { left: 206, right: 314, top: 82, bottom: 116, rows: 1 },
];

const WINDOW_WIDTH = 14;
const WINDOW_PITCH = 22;
const DOOR = { left: 240, right: 280, top: 312 }; // the gateway in the ground storey

// An arched window whose top comes to a soft point, like a jharokha.
function windowPath(x: number, y: number, w: number, h: number): string {
  const spring = y + w * 0.55;
  return `M${x} ${y + h}V${spring}Q${x} ${y} ${x + w / 2} ${y - 2}Q${x + w} ${y} ${x + w} ${spring}V${y + h}Z`;
}

// A small domed pavilion (chhatri) standing on a ledge at height y.
function Chhatri({ cx, y, size = 1 }: { cx: number; y: number; size?: number }) {
  const w = 8 * size;
  return (
    <g>
      <rect className="hm-stone" x={cx - w} y={y - 10 * size} width={w * 2} height={10 * size} />
      <path
        className="hm-stone"
        d={`M${cx - w - 2} ${y - 10 * size}Q${cx - w} ${y - 24 * size} ${cx} ${y - 28 * size}Q${cx + w} ${y - 24 * size} ${cx + w + 2} ${y - 10 * size}Z`}
      />
      <path className="hm-line" d={`M${cx} ${y - 28 * size}V${y - 34 * size}`} />
    </g>
  );
}

type WindowSpec = { d: string; lit: boolean; delay: number };

function buildWindows(): WindowSpec[] {
  const windows: WindowSpec[] = [];
  TIERS.forEach((tier) => {
    const count = Math.floor((tier.right - tier.left - 12) / WINDOW_PITCH);
    const startX = tier.left + (tier.right - tier.left - (count - 1) * WINDOW_PITCH - WINDOW_WIDTH) / 2;
    const rowHeight = (tier.bottom - tier.top) / tier.rows;
    for (let row = 0; row < tier.rows; row++) {
      const y = tier.top + row * rowHeight + 9;
      const h = rowHeight - 15;
      for (let i = 0; i < count; i++) {
        const x = startX + i * WINDOW_PITCH;
        const inDoorway = y + h > DOOR.top && x + WINDOW_WIDTH > DOOR.left - 4 && x < DOOR.right + 4;
        if (inDoorway) continue;
        const n = windows.length;
        windows.push({
          d: windowPath(x, y, WINDOW_WIDTH, h),
          lit: (n * 37 + 11) % 10 < 4, // a fixed, scattered ~40 % of windows
          delay: 0.5 + ((n * 53) % 97) * 0.03,
        });
      }
    }
  });
  return windows;
}

const WINDOWS = buildWindows();

export default function HawaMahal() {
  return (
    <svg viewBox="0 0 520 390" role="img" aria-labelledby="hawa-mahal-title">
      <title id="hawa-mahal-title">Illustration of the Hawa Mahal in Jaipur</title>

      <circle cx="452" cy="64" r="30" fill="var(--art-sun)" />

      {TIERS.map((tier) => (
        <g key={tier.top}>
          <rect
            className="hm-stone"
            x={tier.left}
            y={tier.top}
            width={tier.right - tier.left}
            height={tier.bottom - tier.top}
          />
          <path className="hm-line" d={`M${tier.left - 6} ${tier.top}H${tier.right + 6}`} />
        </g>
      ))}

      {/* Pavilions on the exposed part of each ledge, and a crown of three on top. */}
      {TIERS.slice(0, -1).map((tier, index) => {
        const next = TIERS[index + 1];
        const leftX = (tier.left + next.left) / 2;
        const rightX = (tier.right + next.right) / 2;
        return (
          <g key={`chhatri-${tier.top}`}>
            <Chhatri cx={leftX} y={tier.top} />
            <Chhatri cx={rightX} y={tier.top} />
          </g>
        );
      })}
      <Chhatri cx={226} y={82} />
      <Chhatri cx={294} y={82} />
      <Chhatri cx={260} y={82} size={1.35} />

      {WINDOWS.map((w, index) => (
        <path
          key={index}
          className="hm-window"
          d={w.d}
          data-lit={w.lit}
          style={{ ["--delay" as string]: `${w.delay}s` }}
        />
      ))}

      <path
        className="hm-stone"
        d={`M${DOOR.left} 360V${DOOR.top + 16}Q${DOOR.left} ${DOOR.top} 260 ${DOOR.top - 6}Q${DOOR.right} ${DOOR.top} ${DOOR.right} ${DOOR.top + 16}V360Z`}
      />
      <rect className="hm-stone" x="28" y="360" width="464" height="12" />
      <path className="hm-ground" d="M8 372H512" />
      <path className="hm-ground" d="M60 384H150M190 384H330M370 384H460" opacity="0.5" />
    </svg>
  );
}
