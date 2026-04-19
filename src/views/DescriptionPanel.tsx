import { FC } from "react";
import { BsInfoCircle } from "react-icons/bs";

import Panel from "./Panel";

const DescriptionPanel: FC = () => {
  return (
    <Panel
      initiallyDeployed
      title={
        <>
          <BsInfoCircle className="text-muted" /> Description
        </>
      }
    >
      <p>
        This map is a <i>network</i> of <strong>named entities</strong> extracted from <strong>transcripts</strong> of{" "}
        <a target="_blank" rel="noreferrer" href="https://www.pytexas.org/">
          PyTexas
        </a>{" "}
        conference talks <strong>since 2017</strong>. Each <i>node</i> is an entity (technologies, products, topics, and
        similar). Edges connect pairs of entities that are <strong>co-mentioned</strong> in talk transcripts—how often
        they appear close together in text drives edge weight.
      </p>
      <p>
        Node size reflects prominence in the graph layout; colors cluster entities by thematic community. Use search and
        the cluster list to filter the view. Hover a node to emphasize its connections.
      </p>
    </Panel>
  );
};

export default DescriptionPanel;
