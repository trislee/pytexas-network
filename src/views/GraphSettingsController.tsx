import { useSetSettings, useSigma } from "@react-sigma/core";
import { Attributes } from "graphology-types";
import { FC, PropsWithChildren, useEffect } from "react";

import { drawHover, drawLabel } from "../canvas-utils";
import { IS_MOBILE } from "../is-mobile";
import useDebounce from "../use-debounce";

const NODE_FADE_COLOR = "#bbb";
const EDGE_FADE_COLOR = "#eee";

const GraphSettingsController: FC<PropsWithChildren<{ hoveredNode: string | null }>> = ({ children, hoveredNode }) => {
  const sigma = useSigma();
  const setSettings = useSetSettings();
  const graph = sigma.getGraph();

  const debouncedHoveredNode = useDebounce(hoveredNode, 40);

  useEffect(() => {
    const hoveredColor: string = (debouncedHoveredNode && sigma.getNodeDisplayData(debouncedHoveredNode)?.color) || "";
    const displaySizeMultiplier = IS_MOBILE ? 0.5 : 1;

    setSettings({
      defaultDrawNodeLabel: drawLabel,
      defaultDrawNodeHover: drawHover,
      nodeReducer: (node: string, data: Attributes) => {
        const displaySize = (data.size ?? 1) * displaySizeMultiplier;
        if (debouncedHoveredNode) {
          return node === debouncedHoveredNode ||
            graph.hasEdge(node, debouncedHoveredNode) ||
            graph.hasEdge(debouncedHoveredNode, node)
            ? { ...data, zIndex: 1, size: displaySize }
            : { ...data, zIndex: 0, label: "", color: NODE_FADE_COLOR, highlighted: false, size: displaySize };
        }
        return { ...data, size: displaySize };
      },
      edgeReducer: (edge: string, data: Attributes) => {
        const displaySize = (data.size ?? 1) * displaySizeMultiplier;
        if (debouncedHoveredNode) {
          return graph.hasExtremity(edge, debouncedHoveredNode)
            ? { ...data, color: hoveredColor, size: displaySize * 3 }
            : { ...data, color: EDGE_FADE_COLOR, hidden: true };
        }
        return { ...data, size: displaySize };
      },
    });
  }, [sigma, graph, debouncedHoveredNode, setSettings]);

  return <>{children}</>;
};

export default GraphSettingsController;
