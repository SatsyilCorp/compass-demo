/**
 * Shared synthetic ONR S&T portfolio, the single base dataset every other
 * `lib/mock/*` fixture derives from, so numbers agree across the catalog,
 * dashboard, and analytics pages (a demo where the KPI tile and the chart
 * below it disagree is worse than no demo). Mirrors `grants_curated` in
 * db/migrations/001_schema.sql. All records are synthetic. No real ONR
 * program, award, or awardee data.
 */
import type { Role } from "@/lib/types";

export type MockGrant = {
  id: number;
  grant_no: string;
  title: string;
  abstract: string;
  program_area: string;
  fiscal_year: number;
  amount_usd: number;
  awardee: string;
  org_unit: string;
  classification_band: string;
  batch_id: string;
  created_at: string;
};

/** The two demo personas' org_units (docs/CONTRACTS.md "RLS") plus sibling
 * units so the "poweruser sees all / viewer sees only its own" story reads
 * clearly. ONR-Corporate itself owns no grant rows. It is the "sees all"
 * branch, not a line unit. */
export const ORG_UNITS = ["Code-30", "Code-31", "Code-32", "Code-34", "Code-35"] as const;

export const ORG_UNIT_LABELS: Record<string, string> = {
  "Code-30": "Code 30 · Expeditionary Warfare & Combat Systems",
  "Code-31": "Code 31 · Undersea, Ocean & Atmospheric Systems",
  "Code-32": "Code 32 · Naval Air Warfare & Weapons",
  "Code-34": "Code 34 · Sensors, EW & Ship Systems",
  "Code-35": "Code 35 · Human & Bioengineered Systems",
  "ONR-Corporate": "ONR Corporate (all units)",
};

export const PROGRAM_AREAS = [
  "Autonomous Systems",
  "Undersea Warfare",
  "Directed Energy",
  "Advanced Materials",
  "Human Performance",
  "Hypersonics",
  "Cyber & Information Systems",
  "Power & Energy",
] as const;

const AWARDEES = [
  "Naval Postgraduate School",
  "MIT Lincoln Laboratory",
  "Johns Hopkins Applied Physics Lab",
  "Woods Hole Oceanographic Institution",
  "Georgia Tech Research Institute",
  "Draper Laboratory",
  "Scripps Institution of Oceanography",
  "Penn State Applied Research Lab",
  "University of Michigan",
  "Carnegie Mellon Robotics Institute",
  "SRI International",
  "Sandia National Laboratories",
] as const;

/** Deterministic PRNG (mulberry32), with the same fixture data on every render and build. */
function mulberry32(seed: number) {
  let a = seed;
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const rand = mulberry32(0xc0417a55);
function pick<T>(arr: readonly T[]): T {
  return arr[Math.floor(rand() * arr.length)]!;
}
function int(min: number, max: number): number {
  return Math.floor(rand() * (max - min + 1)) + min;
}

const TITLES: { title: string; abstract: string; program_area: (typeof PROGRAM_AREAS)[number] }[] = [
  {
    title: "Distributed Autonomy for Contested Littoral Swarms",
    abstract: "Decentralized coordination algorithms enabling unmanned surface vessel swarms to maintain formation and mission tempo under degraded or denied communications.",
    program_area: "Autonomous Systems",
  },
  {
    title: "Bio-Inspired Gait Control for Amphibious Legged Robots",
    abstract: "Terrain-adaptive locomotion controllers derived from crustacean gait patterns for shore-to-inland reconnaissance platforms.",
    program_area: "Autonomous Systems",
  },
  {
    title: "Trust-Aware Human-Autonomy Teaming for UUV Task Handoff",
    abstract: "Operator trust calibration models for dynamic task reallocation between human controllers and unmanned underwater vehicles during multi-domain operations.",
    program_area: "Autonomous Systems",
  },
  {
    title: "Low-SWaP Vision Transformers for Onboard Target Classification",
    abstract: "Compressed transformer architectures for real-time target classification within the size, weight, and power envelope of small autonomous surface craft.",
    program_area: "Autonomous Systems",
  },
  {
    title: "Passive Acoustic Sensing for Diesel-Electric Submarine Detection",
    abstract: "Broadband hydrophone array processing techniques to improve detection range against quiet diesel-electric threats in shallow littoral water.",
    program_area: "Undersea Warfare",
  },
  {
    title: "Bistatic Sonar Performance in High-Clutter Continental Shelf Environments",
    abstract: "Characterization of bistatic sonar false-alarm rates across seasonal thermocline variation on the continental shelf.",
    program_area: "Undersea Warfare",
  },
  {
    title: "Long-Endurance Energy Harvesting for Distributed Undersea Sensor Nodes",
    abstract: "Thermal-gradient and wave-motion energy harvesting to extend the on-station duration of unattended undersea sensor grids.",
    program_area: "Undersea Warfare",
  },
  {
    title: "Machine Learning Classification of Marine Mammal vs. Threat Acoustic Signatures",
    abstract: "Supervised classifiers trained to distinguish biologic acoustic signatures from surface and subsurface threat contacts, reducing false positives.",
    program_area: "Undersea Warfare",
  },
  {
    title: "High-Repetition-Rate Fiber Laser Beam Combining for Ship Self-Defense",
    abstract: "Coherent beam-combining architectures to scale fiber laser output power for short-range counter-UAS applications aboard surface combatants.",
    program_area: "Directed Energy",
  },
  {
    title: "Thermal Management of High-Power Microwave Sources on Mobile Platforms",
    abstract: "Compact liquid-cooling architectures for sustained high-power microwave source operation aboard weight-constrained mobile platforms.",
    program_area: "Directed Energy",
  },
  {
    title: "Atmospheric Propagation Modeling for Maritime Directed Energy Effectiveness",
    abstract: "Refined beam-propagation models accounting for maritime aerosol and humidity effects on directed-energy weapon effective range.",
    program_area: "Directed Energy",
  },
  {
    title: "Self-Healing Polymer Composites for Hull Impact Damage Mitigation",
    abstract: "Microcapsule-based self-healing composite laminates that restore partial structural integrity after fragment or blast impact.",
    program_area: "Advanced Materials",
  },
  {
    title: "Additively Manufactured Refractory Alloys for Hypersonic Leading Edges",
    abstract: "Laser powder-bed fusion process parameters for refractory alloy leading-edge components surviving sustained hypersonic thermal loading.",
    program_area: "Advanced Materials",
  },
  {
    title: "Corrosion-Resistant Coatings for Extended Forward-Deployed Ship Life",
    abstract: "Multi-layer ceramic-metal coatings evaluated for corrosion resistance under extended forward-deployed tropical exposure cycles.",
    program_area: "Advanced Materials",
  },
  {
    title: "Cognitive Load Modeling for Multi-Sensor Watchstander Fusion Displays",
    abstract: "Physiological and behavioral cognitive-load models informing adaptive information density on multi-sensor fusion watchstation displays.",
    program_area: "Human Performance",
  },
  {
    title: "Circadian-Adaptive Scheduling for Sustained Shipboard Operations",
    abstract: "Watch-rotation scheduling algorithms informed by circadian biomarker data to reduce fatigue-related error rates during sustained operations.",
    program_area: "Human Performance",
  },
  {
    title: "Wearable Biosensor Fusion for Real-Time Diver Physiological Monitoring",
    abstract: "Multi-modal wearable sensor fusion for continuous physiological state estimation of combat divers during extended submerged operations.",
    program_area: "Human Performance",
  },
  {
    title: "Boundary-Layer Transition Prediction for Hypersonic Glide Vehicle Airframes",
    abstract: "Improved boundary-layer transition prediction methods reducing aerothermal design margin uncertainty on glide vehicle airframes.",
    program_area: "Hypersonics",
  },
  {
    title: "Scramjet Combustor Ignition Reliability Across Mach 5-8 Flight Envelope",
    abstract: "Ignition-reliability characterization for scramjet combustor geometries across the transition and cruise flight envelope.",
    program_area: "Hypersonics",
  },
  {
    title: "Zero-Trust Microsegmentation for Shipboard Combat System Networks",
    abstract: "Zero-trust network microsegmentation architectures adapted to the latency and availability constraints of shipboard combat system LANs.",
    program_area: "Cyber & Information Systems",
  },
  {
    title: "Adversarial Robustness Evaluation of ML Classifiers in Contested EW Environments",
    abstract: "Red-team evaluation methodology for machine-learning classifier robustness under adversarial electronic-warfare perturbation.",
    program_area: "Cyber & Information Systems",
  },
  {
    title: "Post-Quantum Key Exchange for Disadvantaged Tactical Datalinks",
    abstract: "Lightweight post-quantum key-exchange protocol variants suited to bandwidth-constrained, intermittent tactical datalinks.",
    program_area: "Cyber & Information Systems",
  },
  {
    title: "Solid-State Battery Chemistries for Cold-Weather UUV Endurance",
    abstract: "Solid-state lithium battery chemistry evaluated for capacity retention and safety margin in sub-zero unmanned underwater vehicle operations.",
    program_area: "Power & Energy",
  },
  {
    title: "Shipboard Microgrid Load Balancing for Pulsed Directed-Energy Loads",
    abstract: "Microgrid energy-storage and load-balancing architectures that absorb pulsed directed-energy weapon draw without destabilizing ship power quality.",
    program_area: "Power & Energy",
  },
  {
    title: "Fuel Cell Hybridization for Extended-Range Unmanned Aerial Systems",
    abstract: "Hybrid fuel-cell/battery powertrain architectures extending small unmanned aerial system endurance for persistent ISR missions.",
    program_area: "Power & Energy",
  },
  {
    title: "Swarm-Scale Coordination Protocols for Heterogeneous UxV Task Allocation",
    abstract: "Market-based task-allocation protocols coordinating heterogeneous unmanned air, surface, and undersea vehicles on a shared mission.",
    program_area: "Autonomous Systems",
  },
  {
    title: "Multistatic Sonar Network Geometry Optimization for Chokepoint Surveillance",
    abstract: "Optimization methods for multistatic sonar node placement maximizing detection probability across strait and chokepoint geometries.",
    program_area: "Undersea Warfare",
  },
  {
    title: "Radiation-Hardened Electronics Packaging for High-Power Laser Control Systems",
    abstract: "Radiation-hardened packaging techniques protecting laser weapon control electronics operating in elevated EMI environments.",
    program_area: "Directed Energy",
  },
];

const CLASSIFICATION_BANDS = ["CUI-Mock", "CUI-Mock", "CUI-Mock", "Public-Mock"] as const;

function grantNo(fy: number, seq: number): string {
  return `N00014-${String(fy).slice(-2)}-1-${String(seq).padStart(4, "0")}`;
}

function makeGrants(): MockGrant[] {
  const grants: MockGrant[] = [];
  let seq = 1000;
  for (let i = 0; i < TITLES.length; i++) {
    const t = TITLES[i]!;
    const fiscal_year = int(2022, 2026);
    const org_unit = pick(ORG_UNITS);
    const batch_id = `batch-fy${fiscal_year}-${String(int(1, 4)).padStart(2, "0")}`;
    seq += 1;
    grants.push({
      id: i + 1,
      grant_no: grantNo(fiscal_year, seq),
      title: t.title,
      abstract: t.abstract,
      program_area: t.program_area,
      fiscal_year,
      amount_usd: int(180, 4200) * 1000,
      awardee: pick(AWARDEES),
      org_unit,
      classification_band: pick(CLASSIFICATION_BANDS),
      batch_id,
      created_at: new Date(Date.UTC(fiscal_year - 1, 9, int(1, 28))).toISOString(),
    });
  }
  return grants;
}

/** The full synthetic portfolio with every grant and org unit. Poweruser sees this. */
export const ALL_GRANTS: MockGrant[] = makeGrants();

export const BATCH_IDS: string[] = Array.from(new Set(ALL_GRANTS.map((g) => g.batch_id))).sort();

/** RLS simulation: poweruser (ONR-Corporate) sees every row; a unit persona
 * (viewer/Code-30, or any other org unit) sees only its own. This mirrors
 * db/migrations/002_rls.sql `grants_rls_read`. */
export function visibleGrants(role: Role | null, orgUnit: string | null): MockGrant[] {
  if (role === "poweruser" || orgUnit === "ONR-Corporate") return ALL_GRANTS;
  if (!orgUnit) return [];
  return ALL_GRANTS.filter((g) => g.org_unit === orgUnit);
}

/** CLS simulation: viewers cannot read amount_usd (db/migrations/002_rls.sql
 * `REVOKE SELECT (amount_usd) ... FROM compass_app`). Poweruser reads the
 * corporate view (`grants_curated_corp`), which is not column-restricted. */
export function maskAmount(role: Role | null, amount: number): number | null {
  return role === "viewer" ? null : amount;
}

export function sum(nums: (number | null)[]): number | null {
  const present = nums.filter((n): n is number => n !== null);
  if (present.length === 0) return null;
  return present.reduce((a, b) => a + b, 0);
}
