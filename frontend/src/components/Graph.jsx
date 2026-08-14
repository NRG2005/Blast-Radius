import { useCallback, useEffect, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import Logo from "./Logo";

const RISK_COLORS = {
  change: "#9b8cf0",       // violet — the changed node
  will_break: "#ee5257",   // red
  might_break: "#f0a63e",  // amber
  review: "#4fa6f2",       // blue
  safe: "#34c17e",         // green
};

const RISK_CONFIRMED_COLORS = {
  pass: "#34c17e",
  fail: "#ee5257",
  error: "#f2884a",
  not_run: "#56565f",
};

const NODE_SIZES = {
  change: 14,
  will_break: 11,
  might_break: 9,
  review: 7,
  safe: 6,
};

function nodeColor(node, sandboxResults) {
  if (sandboxResults) {
    // Find any result matching this node
    const result = sandboxResults.find((r) => r.node_id === node.id);
    if (result) return RISK_CONFIRMED_COLORS[result.status] || RISK_CONFIRMED_COLORS.not_run;
  }
  return RISK_COLORS[node.risk] || "#56565f";
}

export default function Graph({ graphData, sandboxResults, onNodeClick, animating }) {
  const containerRef = useRef(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const graphRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const obs = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      setDimensions({ width, height });
    });
    obs.observe(containerRef.current);
    return () => obs.disconnect();
  }, []);

  // Auto-zoom to fit after data loads
  useEffect(() => {
    if (graphRef.current && graphData.nodes.length > 0) {
      setTimeout(() => graphRef.current?.zoomToFit(400, 80), 300);
    }
  }, [graphData]);

  const paintNode = useCallback(
    (node, ctx, globalScale) => {
      const color = nodeColor(node, sandboxResults);
      const size = NODE_SIZES[node.risk] || 7;
      const label = node.label || node.id;

      // Glow effect for "will_break" and "change" nodes
      const glow = node.risk === "will_break" || node.risk === "change";
      if (glow) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, size * 1.8, 0, 2 * Math.PI);
        const gradient = ctx.createRadialGradient(node.x, node.y, size * 0.3, node.x, node.y, size * 1.8);
        gradient.addColorStop(0, color + "55");
        gradient.addColorStop(1, color + "00");
        ctx.fillStyle = gradient;
        ctx.fill();
      }

      // Main circle
      ctx.beginPath();
      ctx.arc(node.x, node.y, size, 0, 2 * Math.PI);
      ctx.fillStyle = color;
      ctx.fill();

      // Ring for "change" node
      if (node.risk === "change") {
        ctx.beginPath();
        ctx.arc(node.x, node.y, size + 3, 0, 2 * Math.PI);
        ctx.strokeStyle = "#ffffff55";
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }

      // Pulse animation ring for animating nodes
      if (animating && sandboxResults) {
        const result = sandboxResults.find((r) => r.node_id === node.id);
        if (result) {
          const pulseSize = size + (Math.sin(Date.now() / 200) * 3 + 3);
          ctx.beginPath();
          ctx.arc(node.x, node.y, pulseSize, 0, 2 * Math.PI);
          ctx.strokeStyle = color + "88";
          ctx.lineWidth = 2;
          ctx.stroke();
        }
      }

      // Label
      const fontSize = Math.max(10 / globalScale, 3);
      ctx.font = `${fontSize}px Inter, sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillStyle = "#ffffff";
      ctx.shadowColor = "#000000";
      ctx.shadowBlur = 4;
      const short = label.length > 18 ? label.slice(0, 16) + "…" : label;
      ctx.fillText(short, node.x, node.y + size + fontSize + 2);
      ctx.shadowBlur = 0;
    },
    [sandboxResults, animating]
  );

  if (!graphData.nodes.length) {
    return (
      <div ref={containerRef} className="graph-empty">
        <div className="graph-empty-inner">
          <Logo size={46} />
          <p>Select a scenario and click <strong>Analyze</strong> to visualize the blast radius</p>
        </div>
      </div>
    );
  }

  // Build force-graph compatible data
  const fgData = {
    nodes: graphData.nodes.map((n) => ({ ...n, id: n.id })),
    links: graphData.edges.map((e) => ({
      source: e.source,
      target: e.target,
      relationship: e.relationship,
    })),
  };

  return (
    <div ref={containerRef} className="graph-container">
      <ForceGraph2D
        ref={graphRef}
        width={dimensions.width}
        height={dimensions.height}
        graphData={fgData}
        nodeCanvasObject={paintNode}
        nodeCanvasObjectMode={() => "replace"}
        nodePointerAreaPaint={(node, color, ctx) => {
          const size = (NODE_SIZES[node.risk] || 7) + 4;
          ctx.beginPath();
          ctx.arc(node.x, node.y, size, 0, 2 * Math.PI);
          ctx.fillStyle = color;
          ctx.fill();
        }}
        onNodeClick={onNodeClick}
        linkColor={() => "#ffffff18"}
        linkWidth={1}
        linkDirectionalArrowLength={4}
        linkDirectionalArrowRelPos={1}
        linkDirectionalParticles={1}
        linkDirectionalParticleColor={(link) => {
          const risk = fgData.nodes.find((n) => n.id === link.target)?.risk;
          return RISK_COLORS[risk] || "#ffffff33";
        }}
        linkDirectionalParticleSpeed={0.004}
        backgroundColor="transparent"
        cooldownTicks={80}
        d3AlphaDecay={0.02}
        d3VelocityDecay={0.3}
      />
    </div>
  );
}
