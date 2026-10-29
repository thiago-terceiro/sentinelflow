import React from "react";

import { getStructuredDataGraph } from "@/lib/geo";

export const StructuredData = () => {
  const structuredDataGraph = getStructuredDataGraph();

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredDataGraph) }}
    />
  );
};
