export type StatisticsScope = {
  version: 1;
  buildScope: "full" | "madrid-public";
  geography: string;
  coverage: "partial";
  sources: string[];
  territories: string[];
  period: { min: string | null; max: string | null };
  checkedAt: string;
  denominator: { population: "all-published-announcements"; count: number };
  limitations: string;
};
export type NationalStatisticsScope = StatisticsScope & { title: string };
export function createStatisticsScope(summary: unknown): StatisticsScope;
export function assertStatisticsScope(summary: unknown): StatisticsScope;
export function nationalStatisticsScope(summary: unknown): NationalStatisticsScope | null;
