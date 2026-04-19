import type { Extent } from "sigma/types";

export interface NodeData {
  key: string;
  label: string;
  cluster: string;
  x: number;
  y: number;
  size: number;
}

export interface Cluster {
  key: string;
  color: string;
  clusterLabel: string;
}

export interface Dataset {
  nodes: NodeData[];
  /** Edge list: [sourceKey, targetKey] or [sourceKey, targetKey, weight]. Weight is used for edge size when present. */
  edges: [string | number, string | number][] | [string | number, string | number, number][];
  clusters: Cluster[];
  bbox?: { x: Extent; y: Extent };
  labelThreshold: number;
}

export interface FiltersState {
  clusters: Record<string, boolean>;
}
