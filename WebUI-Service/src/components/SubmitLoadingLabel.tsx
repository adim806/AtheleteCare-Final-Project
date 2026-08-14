import { useEffect, useState } from "react";

const LOADING_MESSAGES = [
  "Analyzing image…",
  "Consulting LangGraph agents…",
  "Generating report…",
];

type SubmitLoadingLabelProps = {
  active: boolean;
};

export function SubmitLoadingLabel({ active }: SubmitLoadingLabelProps) {
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (!active) {
      setIndex(0);
      return;
    }

    const timer = window.setInterval(() => {
      setIndex((i) => (i + 1) % LOADING_MESSAGES.length);
    }, 3500);

    return () => window.clearInterval(timer);
  }, [active]);

  if (!active) return null;

  return (
    <span className="btn-loading">
      <span className="btn-spinner" aria-hidden="true" />
      {LOADING_MESSAGES[index]}
    </span>
  );
}
