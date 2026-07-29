import { useState } from "react";
import { ChatTab } from "./components/ChatTab";
import { SubmitTab } from "./components/SubmitTab";
import "./styles.css";

type TabId = "chat" | "submit";

export default function App() {
  const [tab, setTab] = useState<TabId>("submit");

  return (
    <div className="app">
      <header className="hero">
        <p className="hero-brand">AthleteCare</p>
        <p className="hero-tag">
          Sports medicine triage for the club — chat with the local assistant or
          submit an injury report into the n8n pipeline.
        </p>
      </header>

      <div className="tabs" role="tablist" aria-label="AthleteCare surfaces">
        <button
          type="button"
          className="tab"
          role="tab"
          aria-selected={tab === "chat"}
          onClick={() => setTab("chat")}
        >
          Assistant
        </button>
        <button
          type="button"
          className="tab"
          role="tab"
          aria-selected={tab === "submit"}
          onClick={() => setTab("submit")}
        >
          Submit report
        </button>
      </div>

      {tab === "chat" ? <ChatTab /> : <SubmitTab />}
    </div>
  );
}
