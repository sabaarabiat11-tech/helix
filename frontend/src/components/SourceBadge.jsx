import Badge from "./ui/Badge";

const TONE_BY_SOURCE = {
  "SearXNG (local)": "accent",
  SearXNG: "accent",
  GitHub: "neutral",
  "Company Page": "warning",
  "Google Scholar": "neutral",
  "Manual Research": "neutral",
};

export default function SourceBadge({ source }) {
  return (
    <Badge tone={TONE_BY_SOURCE[source] || "neutral"} dot={false}>
      {source}
    </Badge>
  );
}
