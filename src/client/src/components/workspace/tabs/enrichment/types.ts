export type EnrichmentLabel = {
  scheme: string;
  key: string;
  value: string;
};

export type EnrichmentResult = {
  label: EnrichmentLabel;
  p_value: number;
  p_adjusted: number;
  in_group_count: number;
  background_count: number;
  in_group_fraction: number;
  background_fraction: number;
};

export type EnrichmentSummary = {
  neighbors_requested: number;
  total_neighbors: number;
  population_total: number;
  in_group: number;
  out_group: number;
  threshold_pct: number;
  self_alignment_score: number;
  alignment_threshold: number;
};

export type EnrichmentResponse = {
  summary: EnrichmentSummary;
  warnings: string[];
  results: EnrichmentResult[];
};
