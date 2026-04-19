import { useSigma } from "@react-sigma/core";
import { FC, useEffect, useState } from "react";

import { FiltersState } from "../types";

function prettyPercentage(val: number): string {
  return (val * 100).toFixed(1) + "%";
}

const GraphTitle: FC<{ filters: FiltersState; dataReady: boolean }> = ({ filters, dataReady }) => {
  const sigma = useSigma();
  const graph = sigma.getGraph();

  const [visibleItems, setVisibleItems] = useState<{ nodes: number; edges: number }>({ nodes: 0, edges: 0 });
  useEffect(() => {
    requestAnimationFrame(() => {
      const index = { nodes: 0, edges: 0 };
      graph.forEachNode((_, { hidden }) => !hidden && index.nodes++);
      graph.forEachEdge((_, __, source, target) => {
        const sh = graph.getNodeAttribute(source, "hidden");
        const th = graph.getNodeAttribute(target, "hidden");
        if (!sh && !th) index.edges++;
      });
      setVisibleItems(index);
    });
  }, [filters, graph, dataReady]);

  const hasNodes = graph.order > 0;

  return (
    <div className="graph-title">
      <h1>PyTexas Network</h1>
      {hasNodes && (
        <h2>
          <i>
            {graph.order} node{graph.order > 1 ? "s" : ""}{" "}
            {visibleItems.nodes !== graph.order
              ? ` (only ${prettyPercentage(visibleItems.nodes / graph.order)} visible)`
              : ""}
            , {graph.size} edge
            {graph.size > 1 ? "s" : ""}{" "}
            {visibleItems.edges !== graph.size
              ? ` (only ${prettyPercentage(visibleItems.edges / graph.size)} visible)`
              : ""}
          </i>
        </h2>
      )}
    </div>
  );
};

export default GraphTitle;
