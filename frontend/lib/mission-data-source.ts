export function curatedEvidenceSourceLabel(useMock: boolean): string {
  return useMock
    ? "Fixture-backed serving projection"
    : "Aurora serving projection";
}
