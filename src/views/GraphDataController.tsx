import { useSigma } from "@react-sigma/core";
import { FC, PropsWithChildren, useEffect } from "react";
import { keyBy, omit } from "lodash";

import { Dataset, FiltersState } from "../types";

const GraphDataController: FC<PropsWithChildren<{ dataset: Dataset | null; filters: FiltersState }>> = ({
  dataset,
  filters,
  children,
}) => {
  const sigma = useSigma();
  const graph = sigma.getGraph();

  /**
   * Feed graphology with the new dataset:
   */
  useEffect(() => {
    if (!graph || !dataset) return;

    const clusters = keyBy(dataset.clusters, "key");

    dataset.nodes.forEach((node) =>
      graph.addNode(node.key, {
        ...node,
        ...omit(clusters[node.cluster], "key"),
      }),
    );
    dataset.edges.forEach((edge) => {
      const source = String(edge[0]);
      const target = String(edge[1]);
      const weight = edge.length === 3 ? Number(edge[2]) : 1;
      graph.addEdge(source, target, { size: weight });
    });

    if (dataset.bbox && typeof (sigma as { setCustomBBox?: (b: NonNullable<Dataset["bbox"]>) => void }).setCustomBBox === "function") {
      (sigma as { setCustomBBox: (b: NonNullable<Dataset["bbox"]>) => void }).setCustomBBox(dataset.bbox);
    }

    sigma.getCamera().animatedReset({ duration: 0 });

    return () => graph.clear();
  }, [graph, dataset, sigma]);

  /**
   * Apply filters to graphology:
   */
  useEffect(() => {
    const { clusters } = filters;
    graph.forEachNode((node, { cluster }) =>
      graph.setNodeAttribute(node, "hidden", !clusters[cluster]),
    );
  }, [graph, filters]);

  return <>{children}</>;
};

export default GraphDataController;
