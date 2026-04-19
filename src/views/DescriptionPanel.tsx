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
        This map is a <i>network</i> of named entities extracted from transcripts of{" "}
        <a target="_blank" rel="noreferrer" href="https://www.pytexas.org/">
          PyTexas
        </a>{" "}
        conference talks since 2017. Each <i>node</i> is an entity (for example a technology, framework, or package),
        and edges between nodes indicate that the two entities have been mentioned close together in talk transcripts.
      </p>
      <p>
        Node size indicates how many different talks mentioned that entity, and edge width indicates how often the two
        entities are mentioned together. Entities are colored based on a community detection algorithm.
      </p>
      <p>
        Videos were downloaded using{" "}
        <a target="_blank" rel="noreferrer" href="https://github.com/yt-dlp/yt-dlp">
          yt-dlp
        </a>{" "}
        and transcribed using{" "}
        <a target="_blank" rel="noreferrer" href="https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2">
          NVIDIA Parakeet
        </a>
        , entities were extracted using{" "}
        <a target="_blank" rel="noreferrer" href="https://spacy.io/">
          spaCy
        </a>{" "}
        and converted into a network using networkx, graph layout was computed using{" "}
        <a target="_blank" rel="noreferrer" href="https://gephi.org/">
          Gephi
        </a>
        , and the network was visualized using{" "}
        <a target="_blank" rel="noreferrer" href="https://www.sigmajs.org/">
          sigma.js
        </a>
        .
      </p>
    </Panel>
  );
};

export default DescriptionPanel;
